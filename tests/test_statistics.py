"""Tests for Stage A Deterministic Statistics."""
from __future__ import annotations

from datetime import datetime
import pytest

from relationship_analyst.database.repository import Repository
from relationship_analyst.models.message import CanonicalMessage
from relationship_analyst.pipeline.stage_a_stats import calculate_deterministic_stats


def test_deterministic_statistics_calculation(temp_repo: Repository):
    project_id = "test_stats_proj"

    # Insert controlled chronological messages
    msgs = [
        # Session 1: Started by Alice at 10:00
        CanonicalMessage(
            project_id=project_id,
            source_id="1",
            sender="Alice",
            timestamp=datetime(2023, 1, 1, 10, 0, 0),
            text="Hello Bob, how are you today?",  # Question, 6 words
        ),
        # Bob replies 5 minutes later at 10:05
        CanonicalMessage(
            project_id=project_id,
            source_id="2",
            sender="Bob",
            timestamp=datetime(2023, 1, 1, 10, 5, 0),
            text="Hi Alice! I am doing great.",  # 6 words
        ),
        # Alice replies 2 minutes later at 10:07
        CanonicalMessage(
            project_id=project_id,
            source_id="3",
            sender="Alice",
            timestamp=datetime(2023, 1, 1, 10, 7, 0),
            text="Awesome! Ready for lunch?",  # Question, 4 words
        ),
        # Inactive gap: > 4 hours (next message at 18:00 -> 7hr 53min gap)
        # Session 2: Started by Bob at 18:00
        CanonicalMessage(
            project_id=project_id,
            source_id="4",
            sender="Bob",
            timestamp=datetime(2023, 1, 1, 18, 0, 0),
            text="Dinner was great, thanks!",
        ),
        # Alice replies 10 minutes later at 18:10
        CanonicalMessage(
            project_id=project_id,
            source_id="5",
            sender="Alice",
            timestamp=datetime(2023, 1, 1, 18, 10, 0),
            text="Agreed! Good night.",
        ),
    ]

    temp_repo.insert_messages_batch(project_id, msgs)

    stats = calculate_deterministic_stats(temp_repo, project_id)

    assert stats.total_messages == 5
    assert stats.total_sessions == 2

    # Check Alice
    alice = stats.participants["Alice"]
    assert alice.message_count == 3
    assert alice.questions_asked == 2
    assert alice.conversations_initiated == 1
    assert alice.initiation_percentage == 50.0
    # Alice response times: from Bob msg 2 to Alice msg 3 = 2 min; from Bob msg 4 to Alice msg 5 = 10 min
    # Average = (2 + 10) / 2 = 6.0 min
    assert alice.avg_response_time_minutes == 6.0

    # Check Bob
    bob = stats.participants["Bob"]
    assert bob.message_count == 2
    assert bob.conversations_initiated == 1
    assert bob.initiation_percentage == 50.0
    # Bob response times: from Alice msg 1 to Bob msg 2 = 5 min
    assert bob.median_response_time_minutes == 5.0
