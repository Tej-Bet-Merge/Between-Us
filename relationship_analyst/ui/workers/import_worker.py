"""Background QThread worker for streaming chat export imports."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from relationship_analyst.database.repository import Repository
from relationship_analyst.importers.base import BaseChatImporter, ImportStats
from relationship_analyst.importers.detector import detect_importer
from relationship_analyst.models.message import ProjectMetadata

logger = logging.getLogger(__name__)


class ImportWorker(QThread):
    """Imports chat exports without freezing the GUI."""

    progress_signal = Signal(int, str)  # (count, message)
    finished_signal = Signal(dict)       # summary info dict
    error_signal = Signal(str)

    def __init__(
        self,
        file_path: Path | str,
        project_id: str,
        project_name: str,
        repository: Repository,
        parent=None,
    ):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.project_id = project_id
        self.project_name = project_name
        self.repository = repository
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            self.progress_signal.emit(0, "Detecting file format...")
            importer = detect_importer(self.file_path)

            file_size = self.file_path.stat().st_size
            project = ProjectMetadata(
                id=self.project_id,
                name=self.project_name,
                source_file_path=str(self.file_path),
                source_format=importer.format_name,
                file_size_bytes=file_size,
                status="importing",
            )
            self.repository.create_or_update_project(project)

            total_imported = 0

            def cancel_check() -> bool:
                return self._is_cancelled

            def on_progress(count: int, msg: str):
                self.progress_signal.emit(count, msg)

            stream = importer.parse_stream(
                file_path=self.file_path,
                project_id=self.project_id,
                cancel_check=cancel_check,
                progress_callback=on_progress,
                batch_size=1000,
            )

            # Consume batches and insert into SQLite
            final_stats: Optional[ImportStats] = None
            try:
                while True:
                    batch = next(stream)
                    inserted = self.repository.insert_messages_batch(self.project_id, batch)
                    total_imported += inserted
            except StopIteration as stop_ex:
                final_stats = stop_ex.value

            if self._is_cancelled:
                self.repository.delete_project(self.project_id)
                self.error_signal.emit("Import was cancelled by user.")
                return

            # Update project metadata
            participants = self.repository.get_project_participants(self.project_id)
            min_date, max_date = self.repository.get_date_range(self.project_id)
            total_count = self.repository.count_messages(self.project_id)

            project.message_count = total_count
            project.participants = participants
            project.start_date = min_date
            project.end_date = max_date
            project.status = "imported"
            self.repository.create_or_update_project(project)

            summary = {
                "project_id": self.project_id,
                "project_name": self.project_name,
                "total_messages": total_count,
                "participants": participants,
                "start_date": min_date.strftime("%Y-%m-%d") if min_date else "N/A",
                "end_date": max_date.strftime("%Y-%m-%d") if max_date else "N/A",
                "format_name": importer.format_name,
                "warnings": final_stats.warnings if final_stats else [],
            }
            self.finished_signal.emit(summary)

        except Exception as e:
            logger.exception("Import error: %s", e)
            self.error_signal.emit(f"Import failed: {str(e)}")
