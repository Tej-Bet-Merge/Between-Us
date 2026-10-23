"""Import View: Native file picker, streaming parser progress, and validation."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from relationship_analyst.database.repository import Repository
from relationship_analyst.importers.detector import detect_importer
from relationship_analyst.ui.workers.import_worker import ImportWorker


class ImportView(QWidget):
    """View handling native file selection, streaming import, and preview."""

    def __init__(
        self,
        repository: Repository,
        on_import_completed: Callable[[str], None],
        on_back: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.on_import_completed = on_import_completed
        self.on_back = on_back

        self.selected_file: Optional[Path] = None
        self.worker: Optional[ImportWorker] = None
        self.current_project_id: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(25, 25, 25, 25)

        # Header
        header = QHBoxLayout()
        title = QLabel("Import Chat Export")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        header.addWidget(title)
        header.addStretch()

        btn_cancel = QPushButton("Back to Projects")
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.clicked.connect(self._handle_back)
        header.addWidget(btn_cancel)
        layout.addLayout(header)

        # File selection group
        grp_file = QGroupBox("1. Select Chat Export File")
        form_file = QFormLayout(grp_file)

        file_row = QHBoxLayout()
        self.txt_file = QLineEdit()
        self.txt_file.setPlaceholderText("Select a Telegram Desktop or standard JSON export file...")
        self.txt_file.setReadOnly(True)
        file_row.addWidget(self.txt_file)

        self.btn_browse = QPushButton("Browse Files...")
        self.btn_browse.clicked.connect(self._browse_file)
        file_row.addWidget(self.btn_browse)
        form_file.addRow("JSON Export File:", file_row)

        self.lbl_format = QLabel("Detected Format: None")
        self.lbl_format.setStyleSheet("color: #94a3b8; font-style: italic;")
        form_file.addRow("Format Detection:", self.lbl_format)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. Alex & Jordan Conversation")
        form_file.addRow("Project Name:", self.txt_name)

        layout.addWidget(grp_file)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_start_import = QPushButton("Start Streaming Import")
        self.btn_start_import.setEnabled(False)
        self.btn_start_import.clicked.connect(self._start_import)
        btn_row.addWidget(self.btn_start_import)

        self.btn_stop_import = QPushButton("Cancel Import")
        self.btn_stop_import.setProperty("class", "danger")
        self.btn_stop_import.setEnabled(False)
        self.btn_stop_import.clicked.connect(self._cancel_import)
        btn_row.addWidget(self.btn_stop_import)
        layout.addLayout(btn_row)

        # Progress group
        self.grp_progress = QGroupBox("2. Streaming Import Progress")
        v_prog = QVBoxLayout(self.grp_progress)

        self.lbl_status = QLabel("Ready to import.")
        v_prog.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate while streaming
        self.progress_bar.setVisible(False)
        v_prog.addWidget(self.progress_bar)

        layout.addWidget(self.grp_progress)

        # Summary group
        self.grp_summary = QGroupBox("3. Import Validation & Summary")
        self.grp_summary.setVisible(False)
        v_sum = QVBoxLayout(self.grp_summary)

        self.lbl_summary_text = QLabel()
        self.lbl_summary_text.setWordWrap(True)
        self.lbl_summary_text.setStyleSheet("font-size: 13px; line-height: 1.6; color: #f8fafc;")
        v_sum.addWidget(self.lbl_summary_text)

        self.btn_proceed = QPushButton("Proceed to Analysis Setup →")
        self.btn_proceed.setStyleSheet("background-color: #059669; font-size: 14px; padding: 10px;")
        self.btn_proceed.clicked.connect(self._proceed_to_analysis)
        v_sum.addWidget(self.btn_proceed)

        layout.addWidget(self.grp_summary)
        layout.addStretch()

    def _browse_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select JSON Chat Export",
            "",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        self.selected_file = path
        self.txt_file.setText(str(path))

        # Attempt format detection
        try:
            importer = detect_importer(path)
            self.lbl_format.setText(f"Detected Format: <b style='color: #34d399;'>{importer.format_name}</b>")
            self.btn_start_import.setEnabled(True)
            if not self.txt_name.text().strip():
                default_name = path.stem.replace("_", " ").title()
                self.txt_name.setText(default_name)
        except Exception as e:
            self.lbl_format.setText(f"Format Detection Error: <span style='color: #f87171;'>{str(e)}</span>")
            self.btn_start_import.setEnabled(False)

    def _start_import(self) -> None:
        if not self.selected_file:
            return

        proj_name = self.txt_name.text().strip() or self.selected_file.stem
        self.current_project_id = f"proj_{uuid.uuid4().hex[:12]}"

        self.btn_start_import.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.btn_stop_import.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.grp_summary.setVisible(False)

        self.worker = ImportWorker(
            file_path=self.selected_file,
            project_id=self.current_project_id,
            project_name=proj_name,
            repository=self.repository,
        )
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, count: int, msg: str) -> None:
        self.lbl_status.setText(msg)

    def _on_finished(self, summary: dict) -> None:
        self.progress_bar.setVisible(False)
        self.btn_start_import.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_stop_import.setEnabled(False)
        self.lbl_status.setText("Import completed successfully!")

        participants_str = ", ".join(summary.get("participants", [])) or "None identified"
        summary_html = f"""
        <b>Project:</b> {summary.get('project_name')}<br>
        <b>Messages Imported:</b> {summary.get('total_messages'):,}<br>
        <b>Participants:</b> {participants_str}<br>
        <b>Date Range:</b> {summary.get('start_date')} to {summary.get('end_date')}<br>
        <b>Format:</b> {summary.get('format_name')}<br>
        """

        warnings = summary.get("warnings", [])
        if warnings:
            summary_html += f"<br><b style='color: #fbbf24;'>Import Warnings ({len(warnings)}):</b><br>"
            summary_html += "<br>".join(f"• {w}" for w in warnings[:5])

        self.lbl_summary_text.setText(summary_html)
        self.grp_summary.setVisible(True)

    def _on_error(self, err_msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.btn_start_import.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_stop_import.setEnabled(False)
        self.lbl_status.setText(f"<span style='color: #f87171;'>{err_msg}</span>")
        QMessageBox.critical(self, "Import Failed", err_msg)

    def _cancel_import(self) -> None:
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Cancelling import...")
            self.worker.cancel()

    def _proceed_to_analysis(self) -> None:
        if self.current_project_id:
            self.on_import_completed(self.current_project_id)

    def _handle_back(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        self.on_back()
