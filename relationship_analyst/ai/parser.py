"""Robust JSON extractor and Pydantic validator for LLM outputs."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def extract_json_str(raw_text: str) -> str:
    """Extract innermost or fenced JSON string from LLM response."""
    text = raw_text.strip()

    # Handle ```json ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # If starts with { and ends with }, return
    if text.startswith("{") and text.endswith("}"):
        return text

    # Search for first { and last }
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        return text[start_brace : end_brace + 1]

    # Search for first [ and last ]
    start_bracket = text.find("[")
    end_bracket = text.rfind("]")
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        return text[start_bracket : end_bracket + 1]

    return text


def clean_json_text(json_str: str) -> str:
    """Sanitize common small JSON malformations like trailing commas."""
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([\}\]])", r"\1", json_str)
    return cleaned


def parse_and_validate(raw_text: str, model_cls: Type[T]) -> T:
    """Parse raw LLM output text into a Pydantic model with fallback heuristics."""
    json_candidate = extract_json_str(raw_text)
    sanitized = clean_json_text(json_candidate)

    try:
        data = json.loads(sanitized)
    except json.JSONDecodeError as err:
        # Try again with raw_text in case extraction was too aggressive
        try:
            data = json.loads(raw_text.strip())
        except Exception:
            raise ValueError(f"Failed to parse valid JSON from LLM output: {err}\nOutput snippet: {raw_text[:200]}")

    # Heuristic normalization for common LLM structure variations
    if model_cls.__name__ == "ChunkAnalysisResult":
        if isinstance(data, list):
            data = {"observations": data}
        elif isinstance(data, dict):
            if "observations" not in data:
                for alt_key in ("findings", "results", "patterns", "data", "analysis"):
                    if alt_key in data and isinstance(data[alt_key], list):
                        data["observations"] = data[alt_key]
                        break

    elif model_cls.__name__ == "FinalReport":
        if isinstance(data, dict):
            if "categories" in data and isinstance(data["categories"], list):
                cat_dict = {}
                for c in data["categories"]:
                    if isinstance(c, dict) and "category_id" in c:
                        cat_dict[c["category_id"]] = c
                data["categories"] = cat_dict

    try:
        return model_cls.model_validate(data)
    except ValidationError as val_err:
        raise ValueError(f"Output schema validation failed for {model_cls.__name__}: {val_err}")
