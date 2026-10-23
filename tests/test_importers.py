"""Tests for streaming chat importers, format detection, and robustness."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from relationship_analyst.database.repository import Repository
from relationship_analyst.importers.base import ImportStats
from relationship_analyst.importers.detector import detect_importer
from relationship_analyst.importers.generic import GenericChatImporter
from relationship_analyst.importers.telegram import TelegramChatImporter
from relationship_analyst.models.message import CanonicalMessage


def test_telegram_importer_detection(synthetic_telegram_file):
    importer = detect_importer(synthetic_telegram_file)
    assert isinstance(importer, TelegramChatImporter)
    assert importer.format_id == "telegram_json"


def test_generic_importer_detection(synthetic_generic_file):
    importer = detect_importer(synthetic_generic_file)
    assert isinstance(importer, GenericChatImporter)
    assert importer.format_id == "generic_json"


def test_unsupported_format_detection(temp_dir):
    bad_file = temp_dir / "unsupported.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump({"random_key": "some value", "config": [1, 2, 3]}, f)

    with pytest.raises(ValueError) as excinfo:
        detect_importer(bad_file)
    assert "Unsupported JSON chat format" in str(excinfo.value)


def test_empty_file_detection(temp_dir):
    empty_file = temp_dir / "empty.json"
    empty_file.touch()

    with pytest.raises(ValueError) as excinfo:
        detect_importer(empty_file)
    assert "empty" in str(excinfo.value).lower()


def test_telegram_streaming_import_and_persistence(synthetic_telegram_file, temp_repo: Repository):
    importer = TelegramChatImporter()
    project_id = "test_tg_proj"

    stream = importer.parse_stream(
        file_path=synthetic_telegram_file,
        project_id=project_id,
        batch_size=20,
    )

    batches = []
    final_stats: ImportStats = None
    try:
        while True:
            batch = next(stream)
            batches.append(batch)
            temp_repo.insert_messages_batch(project_id, batch)
    except StopIteration as e:
        final_stats = e.value

    assert len(batches) >= 3  # 60 messages in batches of 20
    assert temp_repo.count_messages(project_id) == 60
    assert "Alex" in final_stats.participants
    assert "Jordan" in final_stats.participants

    # Test idempotency / duplicate protection
    second_insert = temp_repo.insert_messages_batch(project_id, batches[0])
    assert second_insert == 0
    assert temp_repo.count_messages(project_id) == 60


def test_generic_streaming_import(synthetic_generic_file, temp_repo: Repository):
    importer = GenericChatImporter()
    project_id = "test_gen_proj"

    stream = importer.parse_stream(
        file_path=synthetic_generic_file,
        project_id=project_id,
        batch_size=25,
    )

    total_inserted = 0
    try:
        while True:
            batch = next(stream)
            total_inserted += temp_repo.insert_messages_batch(project_id, batch)
    except StopIteration:
        pass

    assert total_inserted == 50
    assert temp_repo.count_messages(project_id) == 50


def test_importer_malformed_records(temp_dir, temp_repo: Repository):
    """Ensure malformed or missing fields are handled gracefully without crashing."""
    malformed_data = {
        "messages": [
            {"id": 1, "type": "message", "date": "2023-01-01T10:00:00", "from": "Alex", "text": "Valid message"},
            {"id": 2},  # Missing date, text, from
            {"type": "message", "date": "invalid_date", "text": "No id"},
            "this is not even a dict",
            {"id": 3, "type": "message", "date": "2023-01-01T10:05:00", "from": "Jordan", "text": "Another valid"},
        ]
    }
    file_path = temp_dir / "malformed.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(malformed_data, f)

    importer = TelegramChatImporter()
    stream = importer.parse_stream(file_path, "test_malformed", batch_size=10)

    try:
        batch = next(stream)
        temp_repo.insert_messages_batch("test_malformed", batch)
    except StopIteration:
        pass

    # Only the 2 valid records should be inserted
    assert temp_repo.count_messages("test_malformed") == 2


def test_importer_cancellation(synthetic_telegram_file, temp_repo: Repository):
    importer = TelegramChatImporter()
    cancelled = True

    stream = importer.parse_stream(
        file_path=synthetic_telegram_file,
        project_id="test_cancel",
        cancel_check=lambda: cancelled,
        batch_size=10,
    )

    batches = list(stream)
    # Since cancel_check returns True immediately, no full batches should be yielded
    assert len(batches) == 0
