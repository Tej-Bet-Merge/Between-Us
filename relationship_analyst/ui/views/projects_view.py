"""Projects view: Manage, view, and select conversational projects."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from relationship_analyst.config import DATA_DIR
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.message import ProjectMetadata


class ProjectsView(QWidget):
    """View listing existing analysis projects."""

    def __init__(
        self,
        repository: Repository,
        on_create_project: Callable[[], None],
        on_open_project: Callable[[str], None],
        on_view_report: Callable[[str], None],
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.on_create_project = on_create_project
        self.on_open_project = on_open_project
        self.on_view_report = on_view_report

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("Chat Projects & Analysis History")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.btn_new = QPushButton("+ Import New Chat")
        self.btn_new.clicked.connect(self.on_create_project)
        header_layout.addWidget(self.btn_new)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setProperty("class", "secondary")
        self.btn_refresh.clicked.connect(self.refresh)
        header_layout.addWidget(self.btn_refresh)

        self.btn_folder = QPushButton("Open Data Folder")
        self.btn_folder.setProperty("class", "secondary")
        self.btn_folder.clicked.connect(self._open_data_folder)
        header_layout.addWidget(self.btn_folder)

        layout.addLayout(header_layout)

        # Privacy notice banner
        privacy_banner = QLabel(
            "🔒 <b>Local-First Privacy:</b> All conversations and analysis results remain stored exclusively on your local machine "
            f"in <code>{DATA_DIR}</code>. No chat contents or embeddings are ever transmitted to any external server."
        )
        privacy_banner.setWordWrap(True)
        privacy_banner.setStyleSheet(
            "background-color: #1e293b; border-left: 4px solid #34d399; padding: 12px; border-radius: 4px; color: #e2e8f0;"
        )
        layout.addWidget(privacy_banner)

        # Projects Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Project Name", "Messages", "Participants", "Date Range", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        projects = self.repository.list_projects()
        self.table.setRowCount(len(projects))

        for row, p in enumerate(projects):
            # Name
            item_name = QTableWidgetItem(p.name)
            self.table.setItem(row, 0, item_name)

            # Messages
            item_count = QTableWidgetItem(f"{p.message_count:,}")
            item_count.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_count)

            # Participants
            part_str = ", ".join(p.participants) if p.participants else "None"
            self.table.setItem(row, 2, QTableWidgetItem(part_str))

            # Date Range
            if p.start_date and p.end_date:
                range_str = f"{p.start_date.strftime('%Y-%m-%d')} to {p.end_date.strftime('%Y-%m-%d')}"
            else:
                range_str = "N/A"
            item_range = QTableWidgetItem(range_str)
            item_range.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_range)

            # Status
            item_status = QTableWidgetItem(p.status.capitalize())
            item_status.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_status)

            # Action Buttons widget
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            btn_analyze = QPushButton("Analyze")
            btn_analyze.clicked.connect(lambda _, pid=p.id: self.on_open_project(pid))
            actions_layout.addWidget(btn_analyze)

            latest_report = self.repository.get_latest_report_for_project(p.id)
            if latest_report:
                btn_report = QPushButton("View Report")
                btn_report.setProperty("class", "secondary")
                btn_report.clicked.connect(lambda _, pid=p.id: self.on_view_report(pid))
                actions_layout.addWidget(btn_report)

            btn_del = QPushButton("Delete")
            btn_del.setProperty("class", "danger")
            btn_del.clicked.connect(lambda _, pid=p.id, name=p.name: self._confirm_delete(pid, name))
            actions_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 5, actions_widget)

    def _confirm_delete(self, project_id: str, name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete '{name}' and all associated messages and reports?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.repository.delete_project(project_id)
            self.refresh()

    def _open_data_folder(self) -> None:
        try:
            os.startfile(str(DATA_DIR))
        except Exception:
            QMessageBox.information(self, "Data Directory", f"Local data is stored at:\n{DATA_DIR}")
