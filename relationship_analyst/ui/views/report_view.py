"""Report View: Navigable relationship review, metrics dashboard, interactive evidence explorer, and exports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from relationship_analyst.config import CATEGORIES
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import CategoryReport, EvidenceItem, FinalReport
from relationship_analyst.models.message import CanonicalMessage
from relationship_analyst.reports.exporter_html import export_report_to_html
from relationship_analyst.reports.exporter_markdown import export_report_to_markdown


class ReportView(QWidget):
    """Interactive multi-tab relationship review and evidence explorer."""

    def __init__(
        self,
        repository: Repository,
        on_back: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.on_back = on_back
        self.current_report: Optional[FinalReport] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Top Action Bar
        top_bar = QHBoxLayout()
        self.lbl_report_title = QLabel("Relationship Analysis Report")
        self.lbl_report_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        top_bar.addWidget(self.lbl_report_title)
        top_bar.addStretch()

        self.btn_export_html = QPushButton("Export HTML...")
        self.btn_export_html.clicked.connect(self._export_html)
        top_bar.addWidget(self.btn_export_html)

        self.btn_export_md = QPushButton("Export Markdown...")
        self.btn_export_md.clicked.connect(self._export_markdown)
        top_bar.addWidget(self.btn_export_md)

        self.btn_export_json = QPushButton("Export JSON...")
        self.btn_export_json.setProperty("class", "secondary")
        self.btn_export_json.clicked.connect(self._export_json)
        top_bar.addWidget(self.btn_export_json)

        self.btn_back = QPushButton("Back to Projects")
        self.btn_back.setProperty("class", "secondary")
        self.btn_back.clicked.connect(self.on_back)
        top_bar.addWidget(self.btn_back)

        main_layout.addLayout(top_bar)

        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Executive Summary
        self.tab_summary = QWidget()
        self._setup_summary_tab()
        self.tabs.addTab(self.tab_summary, "1. Executive Summary")

        # Tab 2: Conversational Metrics Dashboard
        self.tab_metrics = QWidget()
        self._setup_metrics_tab()
        self.tabs.addTab(self.tab_metrics, "2. Metrics Dashboard")

        # Tab 3: Category Reviews
        self.tab_categories = QWidget()
        self._setup_categories_tab()
        self.tabs.addTab(self.tab_categories, "3. Category Reviews")

        # Tab 4: Trajectory & Timeline
        self.tab_trajectory = QWidget()
        self._setup_trajectory_tab()
        self.tabs.addTab(self.tab_trajectory, "4. Trajectory & Evolution")

        # Tab 5: Evidence Explorer & Inspector
        self.tab_evidence = QWidget()
        self._setup_evidence_tab()
        self.tabs.addTab(self.tab_evidence, "5. Evidence Explorer")

    def _setup_summary_tab(self) -> None:
        layout = QVBoxLayout(self.tab_summary)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(14)

        self.browser_summary = QTextBrowser()
        self.browser_summary.setOpenExternalLinks(True)
        layout.addWidget(self.browser_summary)

    def _setup_metrics_tab(self) -> None:
        layout = QVBoxLayout(self.tab_metrics)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(14)

        # KPI row
        self.kpi_layout = QHBoxLayout()
        layout.addLayout(self.kpi_layout)

        # Metrics Table
        self.table_metrics = QTableWidget()
        self.table_metrics.verticalHeader().setVisible(False)
        layout.addWidget(self.table_metrics)

        # Monthly / hourly info browser
        self.browser_distributions = QTextBrowser()
        self.browser_distributions.setMaximumHeight(200)
        layout.addWidget(self.browser_distributions)

    def _setup_categories_tab(self) -> None:
        layout = QHBoxLayout(self.tab_categories)
        layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)

        # Sidebar list of categories
        self.list_categories = QListWidget()
        self.list_categories.setFixedWidth(240)
        self.list_categories.currentRowChanged.connect(self._on_category_selected)
        splitter.addWidget(self.list_categories)

        # Category detail browser
        self.browser_category_detail = QTextBrowser()
        splitter.addWidget(self.browser_category_detail)
        splitter.setSizes([240, 700])

        layout.addWidget(splitter)

    def _setup_trajectory_tab(self) -> None:
        layout = QVBoxLayout(self.tab_trajectory)
        layout.setContentsMargins(15, 15, 15, 15)

        self.browser_trajectory = QTextBrowser()
        layout.addWidget(self.browser_trajectory)

    def _setup_evidence_tab(self) -> None:
        layout = QHBoxLayout(self.tab_evidence)
        layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)

        # Evidence list
        v_left = QVBoxLayout()
        v_left.addWidget(QLabel("<b>Cited Evidence Items:</b>"))
        self.list_evidence = QListWidget()
        self.list_evidence.currentRowChanged.connect(self._on_evidence_selected)
        v_left.addWidget(self.list_evidence)
        left_widget = QWidget()
        left_widget.setLayout(v_left)
        splitter.addWidget(left_widget)

        # Surrounding context browser
        v_right = QVBoxLayout()
        v_right.addWidget(QLabel("<b>Surrounding Message Context (Fetched live from SQLite):</b>"))
        self.browser_context = QTextBrowser()
        v_right.addWidget(self.browser_context)
        right_widget = QWidget()
        right_widget.setLayout(v_right)
        splitter.addWidget(right_widget)

        splitter.setSizes([350, 600])
        layout.addWidget(splitter)

    # ------------------ Loading Data ------------------

    def load_report(self, report: FinalReport) -> None:
        self.current_report = report
        self.lbl_report_title.setText(f"Relationship Analysis: {report.project_name}")

        self._render_summary()
        self._render_metrics()
        self._render_categories()
        self._render_trajectory()
        self._render_evidence_list()

    def _render_summary(self) -> None:
        if not self.current_report:
            return

        rep = self.current_report
        html = f"""
        <div style="font-family: sans-serif; line-height: 1.6; color: #f8fafc;">
            <h2 style="color: #38bdf8; margin-bottom: 8px;">Executive Summary</h2>
            <div style="background: #1e293b; border-left: 4px solid #38bdf8; padding: 14px; border-radius: 4px; font-size: 14px; margin-bottom: 20px;">
                {rep.overall_assessment}
            </div>

            <h3 style="color: #94a3b8; margin-top: 15px;">Analysis Scope & Provenance</h3>
            <ul>
                <li><b>Inference Model:</b> {rep.model_used}</li>
                <li><b>Generated At:</b> {rep.generated_at.strftime('%Y-%m-%d %H:%M UTC')}</li>
                <li><b>Coverage:</b> {rep.coverage_summary}</li>
            </ul>

            <h3 style="color: #fbbf24; margin-top: 25px;">Ethical & Methodological Limitations</h3>
            <p style="color: #94a3b8; font-style: italic;">{rep.limitations_disclaimer}</p>
        </div>
        """
        self.browser_summary.setHtml(html)

    def _render_metrics(self) -> None:
        if not self.current_report or not self.current_report.deterministic_stats:
            return

        stats = self.current_report.deterministic_stats
        participants = stats.get("participants", {})

        # Clear and build KPIs
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def add_kpi(val_str: str, label_str: str):
            box = QFrame()
            box.setStyleSheet("background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 10px;")
            v = QVBoxLayout(box)
            v.setContentsMargins(8, 8, 8, 8)
            lbl_val = QLabel(val_str)
            lbl_val.setStyleSheet("font-size: 22px; font-weight: bold; color: #38bdf8;")
            lbl_lbl = QLabel(label_str)
            lbl_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; text-transform: uppercase;")
            v.addWidget(lbl_val)
            v.addWidget(lbl_lbl)
            self.kpi_layout.addWidget(box)

        add_kpi(f"{stats.get('total_messages', 0):,}", "Total Messages")
        add_kpi(f"{stats.get('duration_days', 0):.0f}", "Days Covered")
        add_kpi(f"{stats.get('messages_per_day', 0):.1f}", "Msgs / Day")
        add_kpi(f"{stats.get('total_sessions', 0):,}", "Sessions (4h Gap)")

        # Table
        p_names = list(participants.keys())
        self.table_metrics.clear()
        self.table_metrics.setColumnCount(len(p_names) + 1)
        self.table_metrics.setHorizontalHeaderLabels(["Metric", *p_names])
        self.table_metrics.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        metrics_rows = [
            ("Message Count", [f"{p.get('message_count', 0):,} ({p.get('message_percentage', 0)}%)" for p in participants.values()]),
            ("Total Words", [f"{p.get('total_words', 0):,}" for p in participants.values()]),
            ("Avg Words / Message", [f"{p.get('avg_words_per_message', 0)}" for p in participants.values()]),
            ("Median Words / Message", [f"{p.get('median_words_per_message', 0)}" for p in participants.values()]),
            ("Questions Asked", [f"{p.get('questions_asked', 0):,}" for p in participants.values()]),
            ("Media Shared", [f"{p.get('media_shared', 0):,}" for p in participants.values()]),
            ("Sessions Initiated", [f"{p.get('conversations_initiated', 0)} ({p.get('initiation_percentage', 0)}%)" for p in participants.values()]),
            ("Median Response Time", [f"{p.get('median_response_time_minutes', 'N/A')} min" for p in participants.values()]),
            ("75th Percentile Response Time", [f"{p.get('p75_response_time_minutes', 'N/A')} min" for p in participants.values()]),
        ]

        self.table_metrics.setRowCount(len(metrics_rows))
        for r_idx, (label, vals) in enumerate(metrics_rows):
            self.table_metrics.setItem(r_idx, 0, QTableWidgetItem(label))
            for c_idx, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_metrics.setItem(r_idx, c_idx + 1, item)

        # Monthly summary text
        monthly = stats.get("monthly_counts", {})
        month_lines = [f"• <b>{m}</b>: " + ", ".join(f"{k}: {v:,}" for k, v in counts.items()) for m, counts in monthly.items()]
        self.browser_distributions.setHtml(
            "<b>Monthly Volume Breakdown:</b><br>" + ("<br>".join(month_lines) if month_lines else "None")
        )

    def _render_categories(self) -> None:
        if not self.current_report:
            return

        self.list_categories.clear()
        for cat_id, cat_report in self.current_report.categories.items():
            item = QListWidgetItem(cat_report.category_title)
            item.setData(Qt.UserRole, cat_id)
            self.list_categories.addItem(item)

        if self.list_categories.count() > 0:
            self.list_categories.setCurrentRow(0)

    def _on_category_selected(self, row: int) -> None:
        if not self.current_report or row < 0:
            return
        item = self.list_categories.item(row)
        cat_id = item.data(Qt.UserRole)
        cat = self.current_report.categories.get(cat_id)
        if not cat:
            return

        obs_html = "".join(f"<li>{o}</li>" for o in cat.supporting_observations)

        evidence_html_parts = []
        for ev in cat.dated_evidence:
            v_badge = "<span style='color: #34d399; font-weight: bold;'>[Verified in DB]</span>" if ev.is_verified else "<span style='color: #f87171;'>[Unverified]</span>"
            evidence_html_parts.append(
                f"<div style='background: #131c2e; padding: 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #334155;'>"
                f"<b>Msg #{ev.message_id}</b> &bull; {ev.sender} &bull; <span style='color: #94a3b8;'>{ev.timestamp}</span> {v_badge}<br>"
                f"<i style='color: #e2e8f0;'>&ldquo;{ev.quote}&rdquo;</i><br>"
                f"<span style='color: #64748b; font-size: 11px;'>{ev.context or ''}</span>"
                f"</div>"
            )

        ev_section = "".join(evidence_html_parts) if evidence_html_parts else "<i>No specific citations.</i>"

        conf_color = "#34d399" if cat.confidence_level == "High" else ("#fbbf24" if cat.confidence_level == "Medium" else "#f87171")

        html = f"""
        <div style="font-family: sans-serif; line-height: 1.6; color: #f8fafc;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                <h2 style="color: #38bdf8; margin: 0;">{cat.category_title}</h2>
                <span style="background: rgba(56, 189, 248, 0.2); color: {conf_color}; padding: 4px 10px; border-radius: 12px; font-weight: bold;">
                    {cat.confidence_level} Confidence
                </span>
            </div>

            <div style="background: rgba(56, 189, 248, 0.1); border-left: 4px solid #38bdf8; padding: 12px; border-radius: 4px; margin: 15px 0; font-size: 14px;">
                <b>Core Assessment:</b> {cat.concise_assessment}
            </div>

            <p style="color: #94a3b8; font-style: italic;"><b>Confidence Rationale:</b> {cat.confidence_justification}</p>

            <h3 style="color: #38bdf8; margin-top: 20px;">Key Supporting Observations</h3>
            <ul>{obs_html}</ul>

            <h3 style="color: #38bdf8; margin-top: 20px;">Both Participants' Dynamics</h3>
            <p>{cat.both_participants_dynamics}</p>

            <h3 style="color: #38bdf8; margin-top: 20px;">Temporal Progression</h3>
            <p>{cat.temporal_patterns}</p>

            <h3 style="color: #38bdf8; margin-top: 20px;">Contradictory Evidence & Nuances</h3>
            <p>{cat.contradictory_evidence}</p>

            <h3 style="color: #fbbf24; margin-top: 20px;">Category Limitations</h3>
            <p style="color: #94a3b8; font-style: italic;">{cat.limitations}</p>

            <h3 style="color: #38bdf8; margin-top: 20px;">Attached Message Evidence</h3>
            {ev_section}
        </div>
        """
        self.browser_category_detail.setHtml(html)

    def _render_trajectory(self) -> None:
        if not self.current_report:
            return

        entries = self.current_report.trajectory_timeline
        lines = []
        for e in entries:
            lines.append(
                f"<div style='border-left: 3px solid #38bdf8; padding-left: 12px; margin-bottom: 16px;'>"
                f"<b style='color: #38bdf8; font-size: 15px;'>{e.get('period', '')}</b> "
                f"<span style='color: #34d399;'>({e.get('closeness_level', '')})</span><br>"
                f"<span style='color: #f8fafc;'>{e.get('summary', '')}</span>"
                f"</div>"
            )

        html = f"""
        <div style="font-family: sans-serif; line-height: 1.6; color: #f8fafc;">
            <h2 style="color: #38bdf8; margin-bottom: 15px;">Relationship Trajectory & Timeline</h2>
            {''.join(lines) if lines else '<p>No temporal shifts recorded.</p>'}
        </div>
        """
        self.browser_trajectory.setHtml(html)

    def _render_evidence_list(self) -> None:
        if not self.current_report:
            return

        self.list_evidence.clear()
        self.evidence_items: List[EvidenceItem] = []

        # Collect unique evidence items
        seen_ids = set()
        for cat in self.current_report.categories.values():
            for ev in cat.dated_evidence:
                if ev.message_id not in seen_ids:
                    seen_ids.add(ev.message_id)
                    self.evidence_items.append(ev)

        for ev in self.evidence_items:
            tag = "✓" if ev.is_verified else "✗"
            item_text = f"[{tag}] Msg #{ev.message_id}: {ev.sender} - \"{ev.quote[:45]}...\""
            item = QListWidgetItem(item_text)
            self.list_evidence.addItem(item)

        if self.evidence_items:
            self.list_evidence.setCurrentRow(0)

    def _on_evidence_selected(self, row: int) -> None:
        if not self.current_report or row < 0 or row >= len(self.evidence_items):
            return

        ev = self.evidence_items[row]
        context_msgs: List[CanonicalMessage] = self.repository.get_message_context(
            self.current_report.project_id, ev.message_id, before=3, after=3
        )

        msg_cards = []
        for m in context_msgs:
            is_target = (m.id == ev.message_id)
            bg = "#1e3a5f" if is_target else "#131c2e"
            border = "2px solid #38bdf8" if is_target else "1px solid #334155"
            target_badge = " <b style='color: #38bdf8;'>[TARGET CITED MESSAGE]</b>" if is_target else ""

            msg_cards.append(
                f"<div style='background: {bg}; border: {border}; border-radius: 6px; padding: 10px; margin-bottom: 8px;'>"
                f"<div style='color: #94a3b8; font-size: 11px; margin-bottom: 4px;'>"
                f"<b>#{m.id}</b> &bull; <b>{m.sender}</b> &bull; {m.timestamp.strftime('%Y-%m-%d %H:%M:%S')}{target_badge}"
                f"</div>"
                f"<div style='color: #f8fafc; font-size: 13px;'>{m.text or f'<{m.media_type}>'}</div>"
                f"</div>"
            )

        html = f"""
        <div style="font-family: sans-serif; line-height: 1.5; color: #f8fafc;">
            <div style="margin-bottom: 12px; padding: 10px; background: #1e293b; border-radius: 6px;">
                <b>Evidence Claim Verification:</b><br>
                Quote: <i>&ldquo;{ev.quote}&rdquo;</i><br>
                Status: {'<span style="color: #34d399;">Verified in SQLite Database</span>' if ev.is_verified else '<span style="color: #f87171;">Unverified Reference</span>'}
            </div>
            {''.join(msg_cards)}
        </div>
        """
        self.browser_context.setHtml(html)

    # ------------------ Exporters ------------------

    def _export_html(self) -> None:
        if not self.current_report:
            return
        default_name = f"{self.current_report.project_name.replace(' ', '_')}_report.html"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Standalone HTML Report", default_name, "HTML Files (*.html)"
        )
        if save_path:
            html_content = export_report_to_html(self.current_report)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            QMessageBox.information(self, "Export Successful", f"Report saved to:\n{save_path}")

    def _export_markdown(self) -> None:
        if not self.current_report:
            return
        default_name = f"{self.current_report.project_name.replace(' ', '_')}_report.md"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Markdown Report", default_name, "Markdown Files (*.md)"
        )
        if save_path:
            md_content = export_report_to_markdown(self.current_report)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            QMessageBox.information(self, "Export Successful", f"Markdown saved to:\n{save_path}")

    def _export_json(self) -> None:
        if not self.current_report:
            return
        default_name = f"{self.current_report.project_name.replace(' ', '_')}_report.json"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Raw Report JSON", default_name, "JSON Files (*.json)"
        )
        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self.current_report.model_dump_json(indent=2))
            QMessageBox.information(self, "Export Successful", f"JSON saved to:\n{save_path}")
