"""Pytest configuration and shared test fixtures."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import pytest

from relationship_analyst.database.repository import Repository
from sample_data.generate_synthetic import (
    generate_synthetic_generic_chat,
    generate_synthetic_telegram_chat,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_repo(temp_dir):
    db_path = temp_dir / "test_conversations.db"
    return Repository(db_path=db_path)


@pytest.fixture
def synthetic_telegram_file(temp_dir):
    data = generate_synthetic_telegram_chat(60)
    file_path = temp_dir / "telegram_export.json"
    import json
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return file_path


@pytest.fixture
def synthetic_generic_file(temp_dir):
    data = generate_synthetic_generic_chat(50)
    file_path = temp_dir / "generic_export.json"
    import json
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return file_path
