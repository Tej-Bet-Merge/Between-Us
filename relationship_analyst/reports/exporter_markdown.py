"""Markdown report exporter."""
from __future__ import annotations

from typing import Dict
from relationship_analyst.models.analysis import FinalReport


def export_report_to_markdown(report: FinalReport) -> str:
    """Generate comprehensive Markdown documentation of the relationship review."""
    lines = [
        f"# Relationship Analysis Report: {report.project_name}",
        f"",
        f"- **Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"- **Inference Model:** `{report.model_used}`",
        f"- **Scope / Coverage:** {report.coverage_summary}",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary & Overall Assessment",
        f"",
        f"{report.overall_assessment}",
        f"",
        f"---",
        f"",
        f"## 2. Deterministic Conversational Metrics",
        f"",
    ]

    stats = report.deterministic_stats
    if stats:
        total = stats.get("total_messages", 0)
        days = stats.get("duration_days", 0)
        per_day = stats.get("messages_per_day", 0)
        sessions = stats.get("total_sessions", 0)

        lines.extend([
            f"- **Total Messages:** {total:,}",
            f"- **Timespan:** {days} days ({per_day} msgs/day)",
            f"- **Conversation Sessions:** {sessions:,} (split by 4h inactivity breaks)",
            f"",
            f"### Participant Comparison",
            f"",
            f"| Metric | " + " | ".join(stats.get("participants", {}).keys()) + " |",
            f"| --- | " + " | ".join(["---"] * len(stats.get("participants", {}))) + " |",
        ])

        participants = stats.get("participants", {})
        lines.append("| **Message Count** | " + " | ".join(f"{p.get('message_count', 0):,} ({p.get('message_percentage', 0)}%)" for p in participants.values()) + " |")
        lines.append("| **Avg Words / Msg** | " + " | ".join(f"{p.get('avg_words_per_message', 0)}" for p in participants.values()) + " |")
        lines.append("| **Median Words / Msg** | " + " | ".join(f"{p.get('median_words_per_message', 0)}" for p in participants.values()) + " |")
        lines.append("| **Questions Asked** | " + " | ".join(f"{p.get('questions_asked', 0):,}" for p in participants.values()) + " |")
        lines.append("| **Initiations** | " + " | ".join(f"{p.get('conversations_initiated', 0)} ({p.get('initiation_percentage', 0)}%)" for p in participants.values()) + " |")
        lines.append("| **Median Response Time** | " + " | ".join(f"{p.get('median_response_time_minutes', 'N/A')} min" for p in participants.values()) + " |")
        lines.append("| **75th Percentile Response** | " + " | ".join(f"{p.get('p75_response_time_minutes', 'N/A')} min" for p in participants.values()) + " |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Category Reviews",
        f"",
    ])

    for cat_id, cat in report.categories.items():
        lines.extend([
            f"### {cat.category_title}",
            f"",
            f"> **Core Assessment:** {cat.concise_assessment}",
            f"",
            f"**Confidence Level:** `{cat.confidence_level}`  ",
            f"*{cat.confidence_justification}*",
            f"",
            f"#### Supporting Observations",
        ])
        for obs in cat.supporting_observations:
            lines.append(f"- {obs}")

        lines.extend([
            f"",
            f"#### Both Participants' Dynamics",
            f"{cat.both_participants_dynamics}",
            f"",
            f"#### Temporal Progression",
            f"{cat.temporal_patterns}",
            f"",
            f"#### Contradictory Evidence & Nuances",
            f"{cat.contradictory_evidence}",
            f"",
            f"#### Category Limitations",
            f"*{cat.limitations}*",
            f"",
            f"#### Concrete Evidence & Citations",
        ])

        if cat.dated_evidence:
            for ev in cat.dated_evidence:
                verified_tag = " [Verified in DB]" if ev.is_verified else " [Unverified]"
                sender_str = f"**{ev.sender}** " if ev.sender else ""
                time_str = f"({ev.timestamp})" if ev.timestamp else ""
                lines.append(f"- **[Msg #{ev.message_id}]**{verified_tag} {sender_str}{time_str}: *\"{ev.quote}\"*")
                if ev.context:
                    lines.append(f"  - Context: {ev.context}")
        else:
            lines.append("*(No specific message citations attached)*")

        lines.append("")

    if report.trajectory_timeline:
        lines.extend([
            f"---",
            f"",
            f"## 4. Relationship Trajectory & Evolution",
            f"",
        ])
        for entry in report.trajectory_timeline:
            period = entry.get("period", "")
            summary = entry.get("summary", "")
            closeness = entry.get("closeness_level", "")
            lines.append(f"- **{period}** ({closeness}): {summary}")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## 5. Limitations & Ethical Notice",
        f"",
        f"{report.limitations_disclaimer}",
        f"",
        f"*Report created with Local-First AI Relationship Analyst. No conversation data was sent to any cloud server.*"
    ])

    return "\n".join(lines)
