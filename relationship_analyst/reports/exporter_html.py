"""Standalone HTML report exporter with embedded responsive styling."""
from __future__ import annotations

import html
from typing import Dict
from relationship_analyst.models.analysis import FinalReport


def export_report_to_html(report: FinalReport) -> str:
    """Generate self-contained standalone HTML report."""
    stats = report.deterministic_stats or {}
    participants = stats.get("participants", {})

    # Participant table rows
    table_headers = "".join(f"<th>{html.escape(p)}</th>" for p in participants.keys())
    row_count = "".join(f"<td>{p.get('message_count', 0):,} ({p.get('message_percentage', 0)}%)</td>" for p in participants.values())
    row_words = "".join(f"<td>{p.get('avg_words_per_message', 0)} (med: {p.get('median_words_per_message', 0)})</td>" for p in participants.values())
    row_questions = "".join(f"<td>{p.get('questions_asked', 0):,}</td>" for p in participants.values())
    row_initiation = "".join(f"<td>{p.get('conversations_initiated', 0)} ({p.get('initiation_percentage', 0)}%)</td>" for p in participants.values())
    row_resp = "".join(f"<td>{p.get('median_response_time_minutes', 'N/A')} min (p75: {p.get('p75_response_time_minutes', 'N/A')}m)</td>" for p in participants.values())

    categories_html = []
    for cat_id, cat in report.categories.items():
        obs_items = "".join(f"<li>{html.escape(o)}</li>" for o in cat.supporting_observations)

        evidence_cards = []
        for ev in cat.dated_evidence:
            v_badge = '<span class="badge verified">Verified in DB</span>' if ev.is_verified else '<span class="badge unverified">Unverified</span>'
            evidence_cards.append(f"""
            <div class="evidence-card">
                <div class="evidence-header">
                    <strong>Msg #{ev.message_id}</strong> &bull; {html.escape(ev.sender or '')} &bull; <span class="time">{html.escape(ev.timestamp or '')}</span>
                    {v_badge}
                </div>
                <div class="quote">&ldquo;{html.escape(ev.quote)}&rdquo;</div>
                {f'<div class="context">{html.escape(ev.context)}</div>' if ev.context else ''}
            </div>
            """)

        evidence_section = "".join(evidence_cards) if evidence_cards else "<em>No specific evidence citations attached.</em>"

        conf_class = f"badge conf-{cat.confidence_level.lower()}"

        categories_html.append(f"""
        <div class="category-card" id="{cat_id}">
            <div class="category-title-bar">
                <h3>{html.escape(cat.category_title)}</h3>
                <span class="{conf_class}">{html.escape(cat.confidence_level)} Confidence</span>
            </div>
            <div class="concise-assessment">
                <strong>Assessment:</strong> {html.escape(cat.concise_assessment)}
            </div>
            <p class="confidence-reason"><em>Basis: {html.escape(cat.confidence_justification)}</em></p>

            <div class="grid-2">
                <div>
                    <h4>Key Observations</h4>
                    <ul class="obs-list">{obs_items}</ul>

                    <h4>Participant Dynamics</h4>
                    <p>{html.escape(cat.both_participants_dynamics)}</p>

                    <h4>Temporal Evolution</h4>
                    <p>{html.escape(cat.temporal_patterns)}</p>

                    <h4>Contradictory Evidence & Nuances</h4>
                    <p>{html.escape(cat.contradictory_evidence)}</p>

                    <h4>Category Limitations</h4>
                    <p class="limitation-text">{html.escape(cat.limitations)}</p>
                </div>
                <div>
                    <h4>Cited Message Evidence</h4>
                    {evidence_section}
                </div>
            </div>
        </div>
        """)

    timeline_items = []
    for entry in report.trajectory_timeline:
        timeline_items.append(f"""
        <div class="timeline-entry">
            <div class="timeline-period">{html.escape(entry.get('period', ''))} ({html.escape(entry.get('closeness_level', ''))})</div>
            <div class="timeline-summary">{html.escape(entry.get('summary', ''))}</div>
        </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relationship Analysis - {html.escape(report.project_name)}</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --border: #334155;
            --success: #34d399;
            --warning: #fbbf24;
            --danger: #f87171;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 30px 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            border-bottom: 1px solid var(--border);
            padding-bottom: 25px;
            margin-bottom: 30px;
        }}
        h1 {{ font-size: 2.2rem; font-weight: 700; color: #fff; margin-bottom: 8px; }}
        .meta-bar {{ color: var(--text-secondary); font-size: 0.95rem; display: flex; flex-wrap: wrap; gap: 20px; }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .badge.verified {{ background: rgba(52, 211, 153, 0.2); color: var(--success); }}
        .badge.unverified {{ background: rgba(248, 113, 113, 0.2); color: var(--danger); }}
        .badge.conf-high {{ background: rgba(52, 211, 153, 0.2); color: var(--success); }}
        .badge.conf-medium {{ background: rgba(251, 191, 36, 0.2); color: var(--warning); }}
        .badge.conf-low {{ background: rgba(248, 113, 113, 0.2); color: var(--danger); }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 25px;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .kpi-card {{
            background: #151e31;
            padding: 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        .kpi-val {{ font-size: 1.8rem; font-weight: 700; color: var(--accent); }}
        .kpi-lbl {{ font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            background: #151e31;
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ background: #1a253c; color: var(--text-secondary); font-size: 0.85rem; text-transform: uppercase; }}
        .category-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 25px;
        }}
        .category-title-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
            margin-bottom: 16px;
        }}
        .concise-assessment {{
            background: var(--accent-glow);
            border-left: 4px solid var(--accent);
            padding: 12px 16px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 16px;
            font-size: 1.05rem;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 25px;
        }}
        @media (max-width: 850px) {{
            .grid-2 {{ grid-template-columns: 1fr; }}
        }}
        h4 {{ color: var(--accent); margin: 16px 0 8px 0; font-size: 1rem; }}
        .obs-list {{ padding-left: 20px; margin-bottom: 15px; }}
        .evidence-card {{
            background: #131c2e;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 12px;
        }}
        .evidence-header {{ font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .quote {{ font-style: italic; color: #e2e8f0; font-size: 0.95rem; margin-bottom: 6px; }}
        .context {{ font-size: 0.85rem; color: #64748b; }}
        .limitation-text {{ font-style: italic; color: #94a3b8; font-size: 0.9rem; }}
        .timeline-entry {{
            border-left: 2px solid var(--accent);
            padding-left: 15px;
            margin-left: 10px;
            margin-bottom: 16px;
            position: relative;
        }}
        .timeline-period {{ font-weight: 700; color: var(--accent); }}
        footer {{
            margin-top: 40px;
            border-top: 1px solid var(--border);
            padding-top: 20px;
            color: var(--text-secondary);
            font-size: 0.85rem;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Relationship Review: {html.escape(report.project_name)}</h1>
            <div class="meta-bar">
                <span><strong>Generated:</strong> {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}</span>
                <span><strong>Model:</strong> {html.escape(report.model_used)}</span>
                <span><strong>Coverage:</strong> {html.escape(report.coverage_summary)}</span>
            </div>
        </header>

        <section class="card">
            <h2 style="margin-bottom: 12px; color: var(--accent);">Executive Summary & Overall Assessment</h2>
            <p style="font-size: 1.1rem; line-height: 1.7;">{html.escape(report.overall_assessment)}</p>
        </section>

        <section class="card">
            <h2 style="margin-bottom: 16px;">Conversational Metrics & Distribution</h2>
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-val">{stats.get('total_messages', 0):,}</div>
                    <div class="kpi-lbl">Total Messages</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-val">{stats.get('duration_days', 0):.0f}</div>
                    <div class="kpi-lbl">Days Covered</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-val">{stats.get('messages_per_day', 0):.1f}</div>
                    <div class="kpi-lbl">Msgs / Day</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-val">{stats.get('total_sessions', 0):,}</div>
                    <div class="kpi-lbl">Conversational Sessions</div>
                </div>
            </div>

            <table>
                <thead>
                    <tr><th>Metric</th>{table_headers}</tr>
                </thead>
                <tbody>
                    <tr><td><strong>Message Volume</strong></td>{row_count}</tr>
                    <tr><td><strong>Words per Message</strong></td>{row_words}</tr>
                    <tr><td><strong>Questions Asked</strong></td>{row_questions}</tr>
                    <tr><td><strong>Sessions Initiated</strong></td>{row_initiation}</tr>
                    <tr><td><strong>Median Response Time</strong></td>{row_resp}</tr>
                </tbody>
            </table>
        </section>

        <section>
            <h2 style="margin-bottom: 20px;">Category Reviews (9 Relational Dimensions)</h2>
            {''.join(categories_html)}
        </section>

        <section class="card">
            <h2 style="margin-bottom: 16px;">Trajectory & Temporal Evolution</h2>
            {''.join(timeline_items) if timeline_items else '<p>Continuous progression across analyzed periods.</p>'}
        </section>

        <section class="card" style="border-color: rgba(251, 191, 36, 0.3);">
            <h3 style="color: var(--warning); margin-bottom: 8px;">Methodological Limitations & Disclaimer</h3>
            <p>{html.escape(report.limitations_disclaimer)}</p>
        </section>

        <footer>
            Local-First AI Relationship Analyst &bull; Zero External AI Calls &bull; Offline Privacy Guaranteed
        </footer>
    </div>
</body>
</html>
"""
