"""Validation engine for verifying cited evidence and message references against SQLite."""
from __future__ import annotations

import logging
from typing import List, Optional

from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import CategoryReport, EvidenceItem, FinalReport
from relationship_analyst.models.message import CanonicalMessage

logger = logging.getLogger(__name__)


def validate_evidence_item(
    item: EvidenceItem,
    project_id: str,
    repository: Repository,
) -> EvidenceItem:
    """
    Validate an evidence reference against the SQLite messages table.
    Ensures message exists, verifies timestamp and sender, and marks verified status.
    """
    if not item.message_id:
        item.is_verified = False
        return item

    messages = repository.get_messages_by_ids(project_id, [item.message_id])
    if not messages:
        # Cited message ID does not exist in DB!
        logger.warning("Evidence references non-existent message ID %s", item.message_id)
        item.is_verified = False
        item.context = "[Unverified: message ID not found in database]"
        return item

    real_msg: CanonicalMessage = messages[0]
    item.is_verified = True
    item.timestamp = real_msg.timestamp.strftime("%Y-%m-%d %H:%M")
    item.sender = real_msg.sender

    # Quote check: verify quote has correspondence to real text
    real_text = (real_msg.text or "").strip()
    quote = (item.quote or "").strip()

    if not real_text and real_msg.media_type:
        item.quote = f"<{real_msg.media_type}>"
    elif quote and quote.lower() not in real_text.lower():
        # LLM paraphrased or truncated
        # If quote is partially present or not present, provide actual message snippet
        item.context = f"Actual message: \"{real_text[:120]}\""
    else:
        item.context = f"Sender: {real_msg.sender} at {item.timestamp}"

    return item


def validate_report_evidence(
    report: FinalReport,
    repository: Repository,
) -> FinalReport:
    """Validate all evidence items cited throughout the final report."""
    for cat_id, cat_report in report.categories.items():
        validated_evidence: List[EvidenceItem] = []
        for ev in cat_report.dated_evidence:
            val_ev = validate_evidence_item(ev, report.project_id, repository)
            validated_evidence.append(val_ev)
        cat_report.dated_evidence = validated_evidence

    return report
