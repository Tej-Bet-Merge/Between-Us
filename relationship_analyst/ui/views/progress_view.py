"""Analysis Progress View: Live stage tracking, elapsed timer, log window, and cancellation."""
from __future__ import annotations

import time
from typing import Callable, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from relationship_analyst.models.analysis import FinalReport
from relationship_analyst.ui.workers.analysis_worker import AnalysisWorker


class ProgressView(QWidget):
    """View rendering active pipeline progress, live logs, elapsed time, and cancellation controls."""

    def __init__(
        self,
        on_completed: Callable[[FinalReport], None],
        on_cancel_requested: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self.on_completed = on_completed
        self.on_cancel_requested = on_cancel_requested

        self.start_time = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(25, 25, 25, 25)

        # Header
        header = QHBoxLayout()
        self.lbl_title = QLabel("Running Relationship Analysis Pipeline")
        self.lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        header.addWidget(self.lbl_title)
        header.addStretch()

        self.lbl_timer = QLabel("Elapsed: 00:00")
        self.lbl_timer.setStyleSheet("font-size: 14px; font-weight: 600; color: #94a3b8;")
        header.addWidget(self.lbl_timer)
        layout.addLayout(header)

        # Stage cards
        stages_box = QGroupBox("Pipeline Stages")
        h_stages = QHBoxLayout(stages_box)
        h_stages.setSpacing(12)

        self.lbl_stage_a = self._create_stage_pill("A: Statistics")
        self.lbl_stage_b = self._create_stage_pill("B: Chunks")
        self.lbl_stage_c = self._create_stage_pill("C: Temporal")
        self.lbl_stage_d = self._create_stage_pill("D: Synthesis")

        h_stages.addWidget(self.lbl_stage_a)
        h_stages.addWidget(self.lbl_stage_b)
        h_stages.addWidget(self.lbl_stage_c)
        h_stages.addWidget(self.lbl_stage_d)
        layout.addWidget(stages_box)

        # Progress bar
        v_prog = QVBoxLayout()
        self.lbl_current_step = QLabel("Initializing analysis environment...")
        self.lbl_current_step.setStyleSheet("font-size: 14px; font-weight: 600; color: #f8fafc;")
        v_prog.addWidget(self.lbl_current_step)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        v_prog.addWidget(self.progress_bar)
        layout.addLayout(v_prog)

        # Live log output
        grp_log = QGroupBox("Execution Activity Log")
        v_log = QVBoxLayout(grp_log)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        v_log.addWidget(self.txt_log)
        layout.addWidget(grp_log)

        # Cancel / Pause action button
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.btn_cancel = QPushButton("Safe Pause / Cancel Analysis")
        self.btn_cancel.setProperty("class", "danger")
        self.btn_cancel.setStyleSheet("font-size: 14px; padding: 10px 20px;")
        self.btn_cancel.clicked.connect(self._handle_cancel)
        btn_bar.addWidget(self.btn_cancel)

        layout.addLayout(btn_bar)

    def _create_stage_pill(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "background-color: #1e293b; color: #64748b; padding: 10px 14px; border-radius: 6px; font-weight: 600; border: 1px solid #334155;"
        )
        return lbl

    def start_pipeline(self) -> None:
        self.start_time = time.time()
        self.timer.start(1000)
        self.txt_log.clear()
        self.progress_bar.setValue(0)
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("Safe Pause / Cancel Analysis")
        self.log_message("Analysis job started. SQLite checkpoints enabled.")

    def on_progress(self, stage: str, percentage: float, msg: str) -> None:
        self.progress_bar.setValue(int(percentage))
        self.lbl_current_step.setText(f"{stage}: {msg}")
        self.log_message(f"[{stage}] {msg}")

        # Update stage pill styling
        active_style = "background-color: #2563eb; color: #ffffff; padding: 10px 14px; border-radius: 6px; font-weight: bold; border: 1px solid #38bdf8;"
        done_style = "background-color: #065f46; color: #34d399; padding: 10px 14px; border-radius: 6px; font-weight: 600; border: 1px solid #059669;"
        idle_style = "background-color: #1e293b; color: #64748b; padding: 10px 14px; border-radius: 6px; font-weight: 600; border: 1px solid #334155;"

        if "Stage A" in stage:
            self.lbl_stage_a.setStyleSheet(active_style)
        elif "Stage B" in stage:
            self.lbl_stage_a.setStyleSheet(done_style)
            self.lbl_stage_b.setStyleSheet(active_style)
        elif "Stage C" in stage:
            self.lbl_stage_a.setStyleSheet(done_style)
            self.lbl_stage_b.setStyleSheet(done_style)
            self.lbl_stage_c.setStyleSheet(active_style)
        elif "Stage D" in stage:
            self.lbl_stage_a.setStyleSheet(done_style)
            self.lbl_stage_b.setStyleSheet(done_style)
            self.lbl_stage_c.setStyleSheet(done_style)
            self.lbl_stage_d.setStyleSheet(active_style)
        elif "Completed" in stage:
            self.lbl_stage_a.setStyleSheet(done_style)
            self.lbl_stage_b.setStyleSheet(done_style)
            self.lbl_stage_c.setStyleSheet(done_style)
            self.lbl_stage_d.setStyleSheet(done_style)

    def log_message(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.appendPlainText(f"[{timestamp}] {message}")

    def on_finished(self, report: FinalReport) -> None:
        self.timer.stop()
        self.progress_bar.setValue(100)
        self.btn_cancel.setEnabled(False)
        self.log_message("Analysis completed successfully. Loading report...")
        self.on_completed(report)

    def on_error(self, err_msg: str) -> None:
        self.timer.stop()
        self.lbl_current_step.setText(f"<span style='color: #f87171;'>{err_msg}</span>")
        self.log_message(f"ERROR: {err_msg}")
        self.btn_cancel.setText("Back to Setup")
        self.btn_cancel.setEnabled(True)

    def _update_timer(self) -> None:
        if self.start_time > 0:
            elapsed = int(time.time() - self.start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            self.lbl_timer.setText(f"Elapsed: {mins:02d}:{secs:02d}")

    def _handle_cancel(self) -> None:
        self.btn_cancel.setEnabled(False)
        self.lbl_current_step.setText("Cancelling safely... (saving checkpoint)")
        self.log_message("Cancellation requested. Checkpointing finished units...")
        self.on_cancel_requested()
