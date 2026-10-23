"""Analysis Setup View: Model configuration, category selection, and workload estimation."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.config import CATEGORIES, CATEGORY_KEYS, DEFAULT_CHUNK_SIZE, RECOMMENDED_MODELS
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.message import ProjectMetadata


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

        self._setup_ui()
        self.refresh_models()
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
        grp_model = QGroupBox("1. Local AI Inference Backend (Ollama)")
        v_model = QVBoxLayout(grp_model)

        self.lbl_ollama_status = QLabel("Checking Ollama status...")
        v_model.addWidget(self.lbl_ollama_status)

        model_form = QFormLayout()
        model_row = QHBoxLayout()
        self.combo_models = QComboBox()
        self.combo_models.setMinimumWidth(300)
        model_row.addWidget(self.combo_models)

        self.btn_refresh_models = QPushButton("Refresh Models")
        self.btn_refresh_models.setProperty("class", "secondary")
        self.btn_refresh_models.clicked.connect(self.refresh_models)
        model_row.addWidget(self.btn_refresh_models)
        model_form.addRow("Selected Model:", model_row)

        self.lbl_active_model_desc = QLabel("Active Mode: Local Ollama Model")
        self.lbl_active_model_desc.setStyleSheet("color: #38bdf8; font-weight: bold; margin-top: 4px;")
        model_form.addRow("Backend Status:", self.lbl_active_model_desc)

        self.combo_models.currentIndexChanged.connect(self._on_model_changed)

        v_model.addLayout(model_form)

        # Instructions banner if Ollama not detected
        self.lbl_instructions = QLabel(
            "<b>Ollama Setup Guidance:</b><br>"
            "1. Download and install Ollama from <a href='https://ollama.com' style='color: #38bdf8;'>https://ollama.com</a>.<br>"
            "2. Open a terminal and run: <code>ollama pull llama3.2</code> (or <code>ollama pull qwen2.5:3b</code> for low RAM).<br>"
            "3. Click 'Refresh Models' above.<br>"
            "<i>Note: You can also choose the built-in <b>mock:test</b> model for instant offline verification.</i>"
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
        v_cat = QVBoxLayout(grp_categories)

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
        v_cat.addLayout(cat_btn_row)

        for cat_id, cat_info in CATEGORIES.items():
            chk = QCheckBox(f"{cat_info['title']} - {cat_info['description']}")
            chk.setChecked(True)
            self.category_checkboxes[cat_id] = chk
            v_cat.addWidget(chk)

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

        # Always add the mock engine option for test / offline usage
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

    def _start_analysis(self) -> None:
        selected_model = self.combo_models.currentData() or "mock:test"
        selected_cats = [cat_id for cat_id, chk in self.category_checkboxes.items() if chk.isChecked()]

        if not selected_cats:
            QMessageBox.warning(self, "No Categories Selected", "Please select at least one category to analyze.")
            return

        chunk_size = self.spin_chunk_size.value()
        is_sample = self.radio_sample.isChecked()

        self.on_start_analysis(self.project_id, selected_model, selected_cats, chunk_size, is_sample)
