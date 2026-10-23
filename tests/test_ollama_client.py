"""Tests for Ollama client, privacy constraints, and JSON response parsing."""
from __future__ import annotations

import pytest

from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.ai.parser import extract_json_str, parse_and_validate
from relationship_analyst.models.analysis import ChunkAnalysisResult


def test_ollama_privacy_guard_enforces_local():
    """Ensure remote or external URLs are strictly rejected to preserve user privacy."""
    with pytest.raises(ValueError) as excinfo:
        OllamaClient(host="https://api.openai.com/v1")
    assert "Privacy violation" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo2:
        OllamaClient(host="http://remote-server.com:11434")
    assert "Privacy violation" in str(excinfo2.value)

    # Local hosts must be accepted
    client_local1 = OllamaClient(host="http://localhost:11434")
    assert client_local1.host == "http://localhost:11434"

    client_local2 = OllamaClient(host="http://127.0.0.1:11434")
    assert client_local2.host == "http://127.0.0.1:11434"


def test_json_extractor_handles_code_fences():
    raw_markdown = """
    Here is the analysis you requested:
    ```json
    {
      "chunk_index": 0,
      "start_msg_id": 1,
      "end_msg_id": 10,
      "start_time": "2023-01-01T10:00:00",
      "end_time": "2023-01-01T10:30:00",
      "message_count": 10,
      "observations": [
        {
          "category": "communication",
          "claim": "Regular check-ins observed",
          "sentiment": "positive",
          "evidence": [
            {
              "message_id": 1,
              "quote": "Good morning!"
            }
          ]
        }
      ]
    }
    ```
    I hope this is helpful!
    """

    extracted = extract_json_str(raw_markdown)
    assert extracted.startswith("{")
    assert extracted.endswith("}")

    result = parse_and_validate(raw_markdown, ChunkAnalysisResult)
    assert result.chunk_index == 0
    assert len(result.observations) == 1
    assert result.observations[0].claim == "Regular check-ins observed"


def test_parser_fails_on_unrecoverable_malformed_json():
    with pytest.raises(ValueError) as excinfo:
        parse_and_validate("This is not JSON at all and contains no brackets", ChunkAnalysisResult)
    assert "Failed to parse valid JSON" in str(excinfo.value)
