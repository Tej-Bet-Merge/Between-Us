"""Tests for HTML and Markdown report generation."""
from __future__ import annotations

from datetime import datetime
import pytest

from relationship_analyst.config import CATEGORIES
from relationship_analyst.models.analysis import CategoryReport, EvidenceItem, FinalReport
from relationship_analyst.reports.exporter_html import export_report_to_html
from relationship_analyst.reports.exporter_markdown import export_report_to_markdown


@pytest.fixture
def sample_final_report():
    categories = {}
    for cat_id, cat_info in CATEGORIES.items():
        categories[cat_id] = CategoryReport(
            category_id=cat_id,
            category_title=cat_info["title"],
            concise_assessment=f"Concise assessment for {cat_info['title']}.",
            supporting_observations=[f"Observation A for {cat_id}", f"Observation B for {cat_id}"],
            dated_evidence=[
                EvidenceItem(
                    message_id=101,
                    sender="Alex",
                    timestamp="2023-01-15 10:00",
                    quote="Direct quote from conversation",
                    is_verified=True,
                )
            ],
            temporal_patterns="Consistent communication over time.",
            both_participants_dynamics="Both contribute reciprocally.",
            contradictory_evidence="Occasional delays during busy days.",
            confidence_level="High",
            confidence_justification="Derived from verified message evidence.",
            limitations="Limited to exported text messages.",
        )

    return FinalReport(
        project_id="test_report_proj",
        project_name="Alex & Jordan Review",
        generated_at=datetime(2023, 6, 1, 12, 0, 0),
        model_used="llama3.2:3b",
        coverage_summary="Complete analysis of 1,200 messages over 120 days.",
        is_complete_run=True,
        deterministic_stats={
            "total_messages": 1200,
            "duration_days": 120.0,
            "messages_per_day": 10.0,
            "total_sessions": 85,
            "participants": {
                "Alex": {
                    "message_count": 620,
                    "message_percentage": 51.7,
                    "avg_words_per_message": 9.2,
                    "median_words_per_message": 7.0,
                    "questions_asked": 110,
                    "conversations_initiated": 45,
                    "initiation_percentage": 52.9,
                    "median_response_time_minutes": 4.5,
                    "p75_response_time_minutes": 14.0,
                },
                "Jordan": {
                    "message_count": 580,
                    "message_percentage": 48.3,
                    "avg_words_per_message": 8.7,
                    "median_words_per_message": 6.0,
                    "questions_asked": 95,
                    "conversations_initiated": 40,
                    "initiation_percentage": 47.1,
                    "median_response_time_minutes": 5.0,
                    "p75_response_time_minutes": 16.0,
                },
            },
        },
        overall_assessment="Overall, the relationship demonstrates strong reciprocity, emotional support, and collaborative communication.",
        categories=categories,
        trajectory_timeline=[
            {"period": "2023-Q1", "summary": "Frequent engagement and shared routines.", "closeness_level": "High"},
            {"period": "2023-Q2", "summary": "Maintained stability and clear boundaries.", "closeness_level": "High"},
        ],
    )


def test_markdown_report_generation(sample_final_report):
    md = export_report_to_markdown(sample_final_report)
    assert "# Relationship Analysis Report: Alex & Jordan Review" in md
    assert "## 1. Executive Summary" in md
    assert "## 2. Deterministic Conversational Metrics" in md
    assert "## 3. Category Reviews" in md

    # Check all 9 categories appear
    for cat_id, cat_info in CATEGORIES.items():
        assert cat_info["title"] in md

    # Check citations and verification
    assert "**[Msg #101]** [Verified in DB]" in md
    assert 'Direct quote from conversation' in md
    assert "No conversation data was sent to any cloud server" in md


def test_html_report_generation(sample_final_report):
    html = export_report_to_html(sample_final_report)
    assert "<!DOCTYPE html>" in html
    assert "Alex &amp; Jordan Review" in html or "Alex & Jordan Review" in html
    assert "badge verified" in html
    assert "1,200" in html
    assert "Total Messages" in html

    # Verify self-contained styling
    assert "<style>" in html
    assert "Offline Privacy Guaranteed" in html
