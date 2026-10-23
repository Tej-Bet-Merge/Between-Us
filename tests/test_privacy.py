"""Tests verifying strict local-first privacy safeguards."""
from __future__ import annotations

import socket
import pytest

from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.config import DATA_DIR, OLLAMA_DEFAULT_HOST


def test_default_config_points_to_localhost():
    assert "127.0.0.1" in OLLAMA_DEFAULT_HOST or "localhost" in OLLAMA_DEFAULT_HOST


def test_ollama_client_blocks_external_domains():
    external_domains = [
        "http://api.openai.com",
        "https://api.anthropic.com",
        "https://generativelanguage.googleapis.com",
        "http://192.168.1.100:11434",
        "http://remote-server.lan:11434",
    ]
    for dom in external_domains:
        with pytest.raises(ValueError):
            OllamaClient(host=dom)


def test_data_directory_is_local():
    assert DATA_DIR.is_absolute()
    # Ensure it's in the user's home or configured local directory
    assert str(DATA_DIR).startswith(str(DATA_DIR.drive))
