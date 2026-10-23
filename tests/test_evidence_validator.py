"""Tests for Evidence Validator and Message Context Retrieval."""
from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import CategoryReport, EvidenceItem, FinalReport
from relationship_analyst.models.message import CanonicalMessage
from relationship_analyst.pipeline.validator import validate_evidence_item, validate_report_evidence


def test_evidence_item_verification(temp_repo: Repository):
    project_id = "test_ev_proj"
    msg = CanonicalMessage(
        id=42,
        project_id=project_id,
        source_id="src_42",
        sender="Jordan",
        timestamp=datetime(2023, 2, 10, 14, 30, 0),
        text="I really appreciate you helping me yesterday with the presentation.",
    )
    temp_repo.insert_messages_batch(project_id, [msg])
    inserted = temp_repo.get_messages_paginated(project_id, limit=1)[0]

    # 1. Valid citation
    valid_ev = EvidenceItem(
        message_id=inserted.id,
        quote="I really appreciate you helping me",
    )
    res_valid = validate_evidence_item(valid_ev, project_id, temp_repo)
    assert res_valid.is_verified is True
    assert res_valid.sender == "Jordan"
    assert "2023-02-10" in res_valid.timestamp

    # 2. Non-existent citation (hallucinated by LLM)
    fake_ev = EvidenceItem(
        message_id=9999,
        quote="This message never existed.",
    )
    res_fake = validate_evidence_item(fake_ev, project_id, temp_repo)
    assert res_fake.is_verified is False
    assert "Unverified" in (res_fake.context or "")


def test_context_retrieval(temp_repo: Repository):
    project_id = "test_ctx_proj"
    start = datetime(2023, 3, 1, 12, 0, 0)
    msgs = [
        CanonicalMessage(
            id=i,
            project_id=project_id,
            source_id=f"msg_{i}",
            sender="Alex" if i % 2 == 1 else "Jordan",
            timestamp=start + timedelta(minutes=i),
            text=f"Line {i}",
        )
        for i in range(1, 10)
    ]
    temp_repo.insert_messages_batch(project_id, msgs)

    # Inspect context around message 5 with before=2, after=2
    context = temp_repo.get_message_context(project_id, message_id=5, before=2, after=2)
    ids = [m.id for m in context]
    assert ids == [3, 4, 5, 6, 7]
