"""Analysis Setup View: Model configuration, category selection, and workload estimation."""
from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.config import CATEGORIES, CATEGORY_KEYS, DEFAULT_CHUNK_SIZE, RECOMMENDED_MODELS
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.message import ProjectMetadata


class AddCustomCategoryDialog(QDialog):
    """Modal dialog for creating a new custom analysis category."""

    def __init__(self, existing_ids: List[str], parent=None):
        super().__init__(parent)
        self.existing_ids = existing_ids
        self.setWindowTitle("Add Custom Category")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("Define a Custom Relationship Category")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(header)

        hint = QLabel(
            "The AI will analyze the conversation specifically looking for patterns, behaviors, and evidence "
            "relevant to your custom category — exactly like the built-in categories."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(10)

        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("e.g.  Future Planning  |  Humor & Inside Jokes  |  Shared Activities")
        form.addRow("Category Title:", self.input_title)

        self.input_desc = QTextEdit()
        self.input_desc.setPlaceholderText(
            "Describe what the AI should look for. Be specific.\n\n"
            "e.g. Discussion of shared future goals, making joint plans, expressing hopes and ambitions together, "
            "and coordinating long-term expectations."
        )
        self.input_desc.setFixedHeight(110)
        form.addRow("Analysis Focus\n(description):", self.input_desc)

        layout.addLayout(form)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #f87171; font-size: 12px;")
        layout.addWidget(self.lbl_error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        title = self.input_title.text().strip()
        desc = self.input_desc.toPlainText().strip()

        if not title:
            self.lbl_error.setText("Category title is required.")
            return
        if len(title) > 60:
            self.lbl_error.setText("Title must be 60 characters or fewer.")
            return
        if not desc:
            self.lbl_error.setText("Analysis focus description is required.")
            return

        # Generate a safe ID from the title
        cat_id = "custom_" + re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        if cat_id in self.existing_ids:
            self.lbl_error.setText(f"A category with the ID '{cat_id}' already exists.")
            return

        self.result_id = cat_id
        self.result_title = title
        self.result_desc = desc
        self.accept()


class SetupView(QWidget):
    """View to configure local model, categories, and scope before running analysis."""

    def __init__(
        self,
        repository: Repository,
        project_id: str,
        on_start_analysis: Callable[[str, str, List[str], int, bool], None],
        on_back: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.project_id = project_id
        self.on_start_analysis = on_start_analysis
        self.on_back = on_back

        self.ollama_client = OllamaClient()
        self.project: Optional[ProjectMetadata] = self.repository.get_project(project_id)
        self.category_checkboxes: Dict[str, QCheckBox] = {}
        # Container layout for the category list (so we can append custom ones)
        self._v_cat: Optional[QVBoxLayout] = None

        self._setup_ui()
        self.refresh_models()
        self._refresh_custom_categories()
        self._update_workload_estimate()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QHBoxLayout()
        proj_title = self.project.name if self.project else "Analysis Setup"
        title = QLabel(f"Configure Analysis: {proj_title}")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        header.addWidget(title)
        header.addStretch()

        btn_back = QPushButton("Back")
        btn_back.setProperty("class", "secondary")
        btn_back.clicked.connect(self.on_back)
        header.addWidget(btn_back)
        main_layout.addLayout(header)

        # Scroll Area for setup options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(20)

        # 1. Local AI Model Selection Group
        grp_model = QGroupBox("1. Local AI Model")
        v_model = QVBoxLayout(grp_model)

        model_row = QHBoxLayout()
        self.combo_models = QComboBox()
        self.combo_models.setMinimumWidth(340)
        self.combo_models.currentIndexChanged.connect(self._on_model_changed)
        model_row.addWidget(QLabel("Model:"))
        model_row.addWidget(self.combo_models)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setProperty("class", "secondary")
        btn_refresh.clicked.connect(self.refresh_models)
        model_row.addWidget(btn_refresh)
        model_row.addStretch()
        v_model.addLayout(model_row)

        self.lbl_ollama_status = QLabel("Checking Ollama status…")
        self.lbl_ollama_status.setStyleSheet("font-size: 12px;")
        v_model.addWidget(self.lbl_ollama_status)

        self.lbl_active_model_desc = QLabel("")
        self.lbl_active_model_desc.setStyleSheet("font-size: 12px;")
        v_model.addWidget(self.lbl_active_model_desc)

        self.lbl_instructions = QLabel(
            "<b>Ollama not detected.</b> "
            "<a href='https://ollama.com/download'>Download Ollama</a>, install it, then run: "
            "<code>ollama pull qwen2.5:3b</code>"
        )
        self.lbl_instructions.setOpenExternalLinks(True)
        self.lbl_instructions.setWordWrap(True)
        self.lbl_instructions.setStyleSheet(
            "background-color: #131c2e; border: 1px solid #334155; padding: 12px; border-radius: 6px; color: #94a3b8; font-size: 12px;"
        )
        v_model.addWidget(self.lbl_instructions)

        layout.addWidget(grp_model)

        # 2. Category Selection Group
        grp_categories = QGroupBox("2. Relationship Review Categories")
        self._v_cat = QVBoxLayout(grp_categories)

        cat_btn_row = QHBoxLayout()
        btn_select_all = QPushButton("Select All")
        btn_select_all.setProperty("class", "secondary")
        btn_select_all.clicked.connect(self._select_all_categories)
        cat_btn_row.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.setProperty("class", "secondary")
        btn_deselect_all.clicked.connect(self._deselect_all_categories)
        cat_btn_row.addWidget(btn_deselect_all)

        cat_btn_row.addStretch()

        btn_add_custom = QPushButton("+ Add Custom Category")
        btn_add_custom.setStyleSheet(
            "background-color: #1e3a5f; color: #38bdf8; border: 1px solid #38bdf8; padding: 5px 12px; border-radius: 5px; font-weight: 600;"
        )
        btn_add_custom.clicked.connect(self._add_custom_category)
        cat_btn_row.addWidget(btn_add_custom)

        self._v_cat.addLayout(cat_btn_row)

        # Built-in categories
        for cat_id, cat_info in CATEGORIES.items():
            chk = QCheckBox(f"{cat_info['title']} — {cat_info['description']}")
            chk.setChecked(True)
            self.category_checkboxes[cat_id] = chk
            self._v_cat.addWidget(chk)

        # Separator label (will appear just above custom categories)
        self._custom_separator = QLabel("── Custom Categories ──")
        self._custom_separator.setStyleSheet("color: #475569; font-size: 11px; margin-top: 6px;")
        self._custom_separator.setVisible(False)
        self._v_cat.addWidget(self._custom_separator)

        layout.addWidget(grp_categories)

        # 3. Scope & Chunk Parameters Group
        grp_scope = QGroupBox("3. Analysis Scope & Chunk Size")
        scope_form = QFormLayout(grp_scope)

        self.radio_full = QRadioButton("Full Analysis (Process all imported messages)")
        self.radio_full.setChecked(True)
        self.radio_full.toggled.connect(self._update_workload_estimate)
        scope_form.addRow("Scope:", self.radio_full)

        self.radio_sample = QRadioButton("Limited Test Run (Process first 200 messages for fast verification)")
        self.radio_sample.toggled.connect(self._update_workload_estimate)
        scope_form.addRow("", self.radio_sample)

        self.spin_chunk_size = QSpinBox()
        self.spin_chunk_size.setRange(20, 250)
        self.spin_chunk_size.setValue(DEFAULT_CHUNK_SIZE)
        self.spin_chunk_size.valueChanged.connect(self._update_workload_estimate)
        scope_form.addRow("Chunk Size (messages per window):", self.spin_chunk_size)

        self.lbl_workload = QLabel("Calculating estimated workload...")
        self.lbl_workload.setStyleSheet("color: #38bdf8; font-weight: 600;")
        scope_form.addRow("Workload Estimate:", self.lbl_workload)

        layout.addWidget(grp_scope)

        # Start button
        self.btn_start = QPushButton("Begin Multi-Stage Relationship Analysis →")
        self.btn_start.setStyleSheet(
            "background-color: #2563eb; font-size: 15px; font-weight: bold; padding: 12px; border-radius: 8px;"
        )
        self.btn_start.clicked.connect(self._start_analysis)
        layout.addWidget(self.btn_start)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def refresh_models(self) -> None:
        self.combo_models.clear()
        health = self.ollama_client.check_health()

        if health.get("status") == "ok":
            self.lbl_ollama_status.setText(
                f"<span style='color: #34d399;'>● Ollama Connected (v{health.get('version')})</span>"
            )
            self.lbl_instructions.setVisible(False)
            try:
                models = self.ollama_client.list_local_models()
                for m in models:
                    self.combo_models.addItem(f"{m} (Installed Ollama Model)", m)
            except Exception as e:
                self.combo_models.addItem(f"Error fetching models: {e}", "mock:test")
        else:
            self.lbl_ollama_status.setText(
                f"<span style='color: #fbbf24;'>▲ Ollama Offline: {health.get('message', 'Service not running')}</span>"
            )
            self.lbl_instructions.setVisible(True)

        self.combo_models.addItem("mock:test (Built-in Deterministic Offline Engine)", "mock:test")
        if self.combo_models.count() > 0:
            self.combo_models.setCurrentIndex(0)
            self._on_model_changed(0)

    def _on_model_changed(self, index: int) -> None:
        model = self.combo_models.currentData() or "mock:test"
        if model == "mock:test":
            self.lbl_active_model_desc.setText(
                "<span style='color: #fbbf24;'>Mode: Offline Deterministic Engine (No AI inference)</span>"
            )
        else:
            self.lbl_active_model_desc.setText(
                f"<span style='color: #34d399;'>Mode: Local Ollama Model ('{model}') - Non-generic, dynamic chat analysis</span>"
            )

    def _update_workload_estimate(self) -> None:
        total_msgs = self.repository.count_messages(self.project_id, exclude_system=True)
        if self.radio_sample.isChecked():
            total_msgs = min(200, total_msgs)

        chunk_size = self.spin_chunk_size.value()
        chunk_count = max(1, (total_msgs + chunk_size - 1) // chunk_size)

        self.lbl_workload.setText(
            f"{total_msgs:,} messages → ~{chunk_count} chunks in Stage B, followed by Stage C temporal aggregation and Stage D synthesis."
        )

    def _select_all_categories(self) -> None:
        for chk in self.category_checkboxes.values():
            chk.setChecked(True)

    def _deselect_all_categories(self) -> None:
        for chk in self.category_checkboxes.values():
            chk.setChecked(False)

    # ── Custom Category Management ──────────────────────────────────────────

    def _refresh_custom_categories(self) -> None:
        """Load custom categories from DB and populate checkboxes (idempotent)."""
        custom_cats = self.repository.get_custom_categories()
        has_custom = bool(custom_cats)
        self._custom_separator.setVisible(has_custom)

        for cat in custom_cats:
            cat_id = cat["id"]
            if cat_id in self.category_checkboxes:
                continue  # already rendered

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            chk = QCheckBox(f"[Custom] {cat['title']} — {cat['description']}")
            chk.setChecked(True)
            chk.setStyleSheet("color: #a5f3fc;")
            self.category_checkboxes[cat_id] = chk
            row_layout.addWidget(chk)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(22, 22)
            btn_del.setToolTip("Remove this custom category")
            btn_del.setStyleSheet(
                "background: transparent; color: #f87171; border: none; font-size: 14px; font-weight: bold;"
            )
            btn_del.clicked.connect(lambda checked=False, cid=cat_id, rw=row_widget: self._delete_custom_category(cid, rw))
            row_layout.addWidget(btn_del)

            self._v_cat.addWidget(row_widget)

    def _add_custom_category(self) -> None:
        existing_ids = list(self.category_checkboxes.keys())
        dlg = AddCustomCategoryDialog(existing_ids=existing_ids, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        cat_id = dlg.result_id
        title = dlg.result_title
        desc = dlg.result_desc

        self.repository.save_custom_category(cat_id, title, desc)
        self._refresh_custom_categories()

    def _delete_custom_category(self, cat_id: str, row_widget: QWidget) -> None:
        reply = QMessageBox.question(
            self,
            "Remove Custom Category",
            f"Remove the custom category '{self.category_checkboxes[cat_id].text().replace('[Custom] ', '').split(' — ')[0]}'?\n\nIt will be removed from future analyses. Existing reports are unaffected.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.repository.delete_custom_category(cat_id)
        self.category_checkboxes.pop(cat_id, None)
        row_widget.setVisible(False)
        row_widget.deleteLater()

        # Hide separator if no custom categories remain
        remaining_custom = self.repository.get_custom_categories()
        self._custom_separator.setVisible(bool(remaining_custom))

    # ── Start ────────────────────────────────────────────────────────────────

    def _start_analysis(self) -> None:
        selected_model = self.combo_models.currentData() or "mock:test"
        selected_cats = [cat_id for cat_id, chk in self.category_checkboxes.items() if chk.isChecked()]

        if not selected_cats:
            QMessageBox.warning(self, "No Categories Selected", "Please select at least one category to analyze.")
            return

        chunk_size = self.spin_chunk_size.value()
        is_sample = self.radio_sample.isChecked()

        self.on_start_analysis(self.project_id, selected_model, selected_cats, chunk_size, is_sample)
