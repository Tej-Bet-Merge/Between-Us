"""Main application window managing desktop navigation and views."""
from __future__ import annotations
from relationship_analyst.ai.ollama_client import OllamaClient

import logging
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from relationship_analyst.config import APP_NAME
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import FinalReport
from relationship_analyst.ui.theme import MAIN_STYLE_SHEET
from relationship_analyst.ui.views.import_view import ImportView
from relationship_analyst.ui.views.progress_view import ProgressView
from relationship_analyst.ui.views.projects_view import ProjectsView
from relationship_analyst.ui.views.report_view import ReportView
from relationship_analyst.ui.views.setup_view import SetupView
from relationship_analyst.ui.workers.analysis_worker import AnalysisWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Primary application window containing all view stacks."""

    def __init__(self, repository: Optional[Repository] = None):
        super().__init__()
        self.repository = repository or Repository()
        self.analysis_worker: Optional[AnalysisWorker] = None
        self.current_project_id: Optional[str] = None

        self.setWindowTitle(f"{APP_NAME} - Local-First AI Relationship Review")
        self.resize(1150, 780)
        self.setStyleSheet(MAIN_STYLE_SHEET)

        self._setup_views()
        self._setup_menus()

    def _setup_views(self) -> None:
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # 0: Projects View
        self.view_projects = ProjectsView(
            repository=self.repository,
            on_create_project=self._show_import_view,
            on_open_project=self._show_setup_view,
            on_view_report=self._show_existing_report,
        )
        self.stack.addWidget(self.view_projects)

        # 1: Import View
        self.view_import = ImportView(
            repository=self.repository,
            on_import_completed=self._on_import_completed,
            on_back=self._show_projects_view,
        )
        self.stack.addWidget(self.view_import)

        # 2: Setup View (Instantiated dynamically when project selected)
        self.view_setup: Optional[SetupView] = None

        # 3: Progress View
        self.view_progress = ProgressView(
            on_completed=self._on_analysis_completed,
            on_cancel_requested=self._cancel_active_analysis,
        )
        self.stack.addWidget(self.view_progress)

        # 4: Report View
        self.view_report = ReportView(
            repository=self.repository,
            on_back=self._show_projects_view,
        )
        self.stack.addWidget(self.view_report)

        # Start on projects view
        self.stack.setCurrentWidget(self.view_projects)

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        # File Menu
        menu_file = menubar.addMenu("File")

        action_new = QAction("Import New Chat...", self)
        action_new.setShortcut("Ctrl+N")
        action_new.triggered.connect(self._show_import_view)
        menu_file.addAction(action_new)

        action_projects = QAction("All Projects", self)
        action_projects.triggered.connect(self._show_projects_view)
        menu_file.addAction(action_projects)

        menu_file.addSeparator()

        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(self.close)
        menu_file.addAction(action_exit)

        # Help Menu
        menu_help = menubar.addMenu("Help")

        action_privacy = QAction("Privacy & Local-First Guarantee", self)
        action_privacy.triggered.connect(self._show_privacy_dialog)
        menu_help.addAction(action_privacy)

        action_about = QAction("About", self)
        action_about.triggered.connect(self._show_about_dialog)
        menu_help.addAction(action_about)

    # ------------------ Navigation Handlers ------------------

    def _show_projects_view(self) -> None:
        self.view_projects.refresh()
        self.stack.setCurrentWidget(self.view_projects)

    def _show_import_view(self) -> None:
        self.stack.setCurrentWidget(self.view_import)

    def _on_import_completed(self, project_id: str) -> None:
        self._show_setup_view(project_id)

    def _show_setup_view(self, project_id: str) -> None:
        self.current_project_id = project_id
        self.view_setup = SetupView(
            repository=self.repository,
            project_id=project_id,
            on_start_analysis=self._start_analysis,
            on_back=self._show_projects_view,
        )
        self.stack.addWidget(self.view_setup)
        self.stack.setCurrentWidget(self.view_setup)

    def _start_analysis(
        self,
        project_id: str,
        model_name: str,
        categories: List[str],
        chunk_size: int,
        is_sample: bool,
    ) -> None:
        self.stack.setCurrentWidget(self.view_progress)
        self.view_progress.start_pipeline()

        limit_msgs = 200 if is_sample else None

        ollama_client = OllamaClient() if model_name != "mock:test" else None

        self.analysis_worker = AnalysisWorker(
            repository=self.repository,
            project_id=project_id,
            model_name=model_name,
            categories=categories,
            chunk_size=chunk_size,
            ollama_client=ollama_client,
        )
        self.analysis_worker.progress_signal.connect(self.view_progress.on_progress)
        self.analysis_worker.finished_signal.connect(self.view_progress.on_finished)
        self.analysis_worker.error_signal.connect(self.view_progress.on_error)
        self.analysis_worker.start()

    def _cancel_active_analysis(self) -> None:
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.cancel()

    def _on_analysis_completed(self, report: FinalReport) -> None:
        self.view_report.load_report(report)
        self.stack.setCurrentWidget(self.view_report)

    def _show_existing_report(self, project_id: str) -> None:
        report = self.repository.get_latest_report_for_project(project_id)
        if report:
            self.view_report.load_report(report)
            self.stack.setCurrentWidget(self.view_report)
        else:
            QMessageBox.information(
                self, "No Report Found", "No analysis report exists for this project yet. Please run an analysis first."
            )

    def _show_privacy_dialog(self) -> None:
        QMessageBox.information(
            self,
            "Local-First Privacy Architecture",
            "🔒 <b>Zero-Cloud Guarantee:</b>\n\n"
            "• All chat exports and conversations are parsed directly on your CPU into a local SQLite database.\n"
            "• AI inference is performed locally via Ollama (127.0.0.1:11434) with local open-weights models.\n"
            "• No messages, statistics, or reports are ever sent over the internet.\n"
            "• You can inspect or permanently delete all stored data at any time.",
        )

    def _show_about_dialog(self) -> None:
        QMessageBox.information(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME} v1.0</b><br><br>"
            "An autonomous, local-first relationship communication analyzer designed to handle large-scale "
            "chat exports with evidence-based verification and multi-category reviews.",
        )

    def closeEvent(self, event) -> None:
        if self.analysis_worker and self.analysis_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Analysis In Progress",
                "An analysis pipeline is actively running. Checkpoints have been saved to SQLite.\n\nDo you want to stop and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.analysis_worker.cancel()
                self.analysis_worker.wait(2000)
                event.accept()
            else:
                event.ignore()
                return
        event.accept()
