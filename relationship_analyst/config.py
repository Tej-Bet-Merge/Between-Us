"""Configuration constants and paths for Local-First Relationship Analyst."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

# Application directories
APP_NAME = "LocalRelationshipAnalyst"
DEFAULT_DATA_DIR = Path.home() / ".local_relationship_analyst"
DATA_DIR = Path(os.environ.get("RELATIONSHIP_ANALYST_DATA_DIR", str(DEFAULT_DATA_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR = DATA_DIR / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_FILE_NAME = "conversations.db"

# Local Ollama connection defaults
OLLAMA_DEFAULT_HOST = "http://127.0.0.1:11434"
OLLAMA_TIMEOUT_SECONDS = 300  # 5 minutes per request; CPU inference on 4B+ models can be slow
OLLAMA_MAX_RETRIES = 3

# Recommended models suitable for CPU / low-VRAM local inference
RECOMMENDED_MODELS = [
    ("llama3.2:3b", "Meta Llama 3.2 3B (Fastest, low memory, CPU friendly)"),
    ("qwen2.5:3b", "Qwen 2.5 3B (Very fast, highly structured JSON output)"),
    ("qwen2.5:7b", "Qwen 2.5 7B (High accuracy, excellent reasoning)"),
    ("llama3.1:8b", "Meta Llama 3.1 8B (Deep nuanced analysis)"),
    ("mistral:7b", "Mistral 7B Instruct (Balanced speed & depth)"),
    ("phi3:mini", "Microsoft Phi-3 Mini 3.8B (Compact & capable)"),
    ("mock:test", "Deterministic Mock Engine (Offline test & verification)")
]

# Pipeline defaults
DEFAULT_CHUNK_SIZE = 80
MIN_CHUNK_SIZE = 20
MAX_CHUNK_SIZE = 250
INACTIVITY_GAP_HOURS = 4.0  # Gap between messages indicating a new conversation session

# Review categories
CATEGORIES: Dict[str, Dict[str, str]] = {
    "communication": {
        "id": "communication",
        "title": "Communication",
        "description": "Openness, responsiveness, engagement, conversational rhythm, clarity, misunderstandings, and conversational pacing."
    },
    "effort_reciprocity": {
        "id": "effort_reciprocity",
        "title": "Effort & Reciprocity",
        "description": "Initiation balance, follow-through, mutual contribution, emotional investment, and apparent imbalances."
    },
    "emotional_support": {
        "id": "emotional_support",
        "title": "Emotional Support",
        "description": "Responses to vulnerability, distress, personal struggles, validation, empathy, and requests for help."
    },
    "affection_warmth": {
        "id": "affection_warmth",
        "title": "Affection & Warmth",
        "description": "Expressions of care, appreciation, closeness, shared humor, playful banter, and affirmation."
    },
    "conflict_repair": {
        "id": "conflict_repair",
        "title": "Conflict & Repair",
        "description": "Disagreements, defensiveness vs openness, accountability, apologies, de-escalation, reconciliation, and unresolved issues."
    },
    "trust_reliability": {
        "id": "trust_reliability",
        "title": "Trust & Reliability",
        "description": "Consistency, keeping commitments, dependability, honesty, and signs of broken trust or reliability."
    },
    "boundaries_respect": {
        "id": "boundaries_respect",
        "title": "Boundaries & Respect",
        "description": "Responses to needs, refusals, differing opinions, personal space, autonomy, and respecting stated limits."
    },
    "trajectory": {
        "id": "trajectory",
        "title": "Relationship Trajectory",
        "description": "Evolution of communication frequency, intimacy, engagement, stability, and tension over time."
    },
    "overall_assessment": {
        "id": "overall_assessment",
        "title": "Overall Relationship Assessment",
        "description": "Balanced synthesis of dynamics, core strengths, recurring friction, uncertainty, and realistic perspectives."
    }
}

CATEGORY_KEYS: List[str] = list(CATEGORIES.keys())


def get_effective_categories(repository=None) -> Dict[str, Dict[str, str]]:
    """
    Return the merged category registry: built-in CATEGORIES + any custom categories
    stored in the database. When repository is None, returns only built-in categories.
    This is the single source of truth used by prompts, parsers, and reports.
    """
    effective = dict(CATEGORIES)
    if repository is not None:
        try:
            for cat in repository.get_custom_categories():
                cid = cat["id"]
                effective[cid] = {
                    "id": cid,
                    "title": cat["title"],
                    "description": cat["description"],
                }
        except Exception:
            pass  # DB may not have the table yet on first run
    return effective
