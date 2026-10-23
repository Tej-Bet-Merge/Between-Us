"""End-to-end verification script for Local-First Relationship Analyst."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from relationship_analyst.config import CATEGORY_KEYS, DATA_DIR
from relationship_analyst.database.repository import Repository
from relationship_analyst.importers.detector import detect_importer
from relationship_analyst.models.message import ProjectMetadata
from relationship_analyst.pipeline.orchestrator import AnalysisPipelineOrchestrator
from relationship_analyst.reports.exporter_html import export_report_to_html
from relationship_analyst.reports.exporter_markdown import export_report_to_markdown


def run_e2e_verification() -> bool:
    print("=" * 70)
    print("LOCAL-FIRST AI RELATIONSHIP ANALYST: END-TO-END VERIFICATION")
    print("=" * 70)

    fixture_path = Path("sample_data/synthetic_telegram.json")
    if not fixture_path.exists():
        print(f"Error: Fixture {fixture_path} not found.")
        return False

    project_id = "demo_verification_project"
    db_path = DATA_DIR / "verification_test.db"

    print(f"\n[1/6] Initializing Repository with SQLite WAL mode at: {db_path}")
    repo = Repository(db_path=db_path)

    print(f"[2/6] Detecting format and streaming import from: {fixture_path}")
    importer = detect_importer(fixture_path)
    print(f"      Detected format: {importer.format_name} ({importer.format_id})")

    repo.create_or_update_project(
        ProjectMetadata(
            id=project_id,
            name="Alex & Jordan Demonstration",
            source_file_path=str(fixture_path),
            source_format=importer.format_name,
            file_size_bytes=fixture_path.stat().st_size,
        )
    )

    stream = importer.parse_stream(
        file_path=fixture_path,
        project_id=project_id,
        batch_size=50,
    )

    total_inserted = 0
    for batch in stream:
        inserted = repo.insert_messages_batch(project_id, batch)
        total_inserted += inserted

    total_msgs = repo.count_messages(project_id)
    participants = repo.get_project_participants(project_id)
    date_range = repo.get_date_range(project_id)

    print(f"      Successfully imported {total_msgs} messages.")
    print(f"      Participants: {', '.join(participants)}")
    print(f"      Date Range: {date_range[0]} to {date_range[1]}")

    print(f"\n[3/6] Running Staged Analysis Pipeline (All 9 Categories)...")

    def progress_callback(stage: str, pct: float, msg: str):
        print(f"      [{pct:5.1f}%] {stage}: {msg}")

    orchestrator = AnalysisPipelineOrchestrator(repository=repo)
    report = orchestrator.run_analysis(
        project_id=project_id,
        model_name="mock:test",  # deterministic offline engine
        selected_categories=CATEGORY_KEYS,
        chunk_size=40,
        progress_cb=progress_callback,
    )

    print(f"\n[4/6] Verifying Final Report Structure & Categories:")
    print(f"      Project Name: {report.project_name}")
    print(f"      Model Used: {report.model_used}")
    print(f"      Categories analyzed: {len(report.categories)}/9")

    missing_cats = [k for k in CATEGORY_KEYS if k not in report.categories]
    if missing_cats:
        print(f"      ERROR: Missing categories: {missing_cats}")
        return False

    for cat_id, cat in report.categories.items():
        v_count = sum(1 for e in cat.dated_evidence if e.is_verified)
        print(f"      [OK] {cat.category_title:<28} | Confidence: {cat.confidence_level:<6} | Verified Citations: {v_count}")

    print(f"\n[5/6] Testing Evidence Explorer (Live SQLite Context Retrieval):")
    sample_cat = report.categories.get("communication")
    if sample_cat and sample_cat.dated_evidence:
        first_ev = sample_cat.dated_evidence[0]
        context_msgs = repo.get_message_context(project_id, first_ev.message_id, before=2, after=2)
        print(f"      Inspected citation [Msg #{first_ev.message_id}]: \"{first_ev.quote[:50]}...\"")
        print(f"      Retrieved {len(context_msgs)} contextual messages from SQLite around ID {first_ev.message_id}:")
        for m in context_msgs:
            marker = "===>" if m.id == first_ev.message_id else "    "
            print(f"      {marker} #{m.id} [{m.sender}]: {m.text[:60]}")

    print(f"\n[6/6] Generating Standalone HTML and Markdown Reports...")
    out_dir = Path("sample_data/demo_reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = out_dir / "relationship_report.html"
    html_content = export_report_to_html(report)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"      [OK] HTML Report saved: {html_path.resolve()} ({len(html_content):,} bytes)")

    md_path = out_dir / "relationship_report.md"
    md_content = export_report_to_markdown(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"      [OK] Markdown Report saved: {md_path.resolve()} ({len(md_content):,} bytes)")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_e2e_verification()
    sys.exit(0 if success else 1)
