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


def repair_truncated_json(raw_text: str) -> Any:
    """
    Attempt to recover valid JSON from a truncated or cut-off LLM response.
    Closes open strings, removes incomplete trailing key-values, and balances braces/brackets.
    """
    text = raw_text.strip()

    # 1. First heuristic: inside an array of objects (like "observations": [ {...}, ... ]),
    # walk backwards from the end to find the last fully completed object '}'
    idx = len(text)
    while idx > 0:
        last_brace = text.rfind("}", 0, idx)
        if last_brace == -1:
            break
        candidate = text[: last_brace + 1].strip()
        candidate = re.sub(r",\s*$", "", candidate)
        for suffix in ("]\n}", "}\n}", "]", "}"):
            try:
                return json.loads(candidate + "\n" + suffix)
            except Exception:
                pass
        idx = last_brace

    # 2. Stack-based closing heuristic: track unbalanced { and [
    in_string = False
    escape = False
    stack: List[str] = []
    out: List[str] = []

    for ch in text:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\" and in_string:
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string:
            out.append(ch)
            continue
        if ch in ("{", "["):
            stack.append("}" if ch == "{" else "]")
        elif ch in ("}", "]"):
            if stack and stack[-1] == ch:
                stack.pop()
        out.append(ch)

    repaired = "".join(out)
    if in_string:
        repaired += '"'

    # Strip dangling keys (e.g. '"claim":' at EOF) or trailing commas
    repaired = re.sub(r',\s*$', '', repaired.strip())
    repaired = re.sub(r',\s*("[^"]*"\s*:\s*)?$', '', repaired.strip())

    while stack:
        repaired += stack.pop()

    return json.loads(repaired)


def parse_and_validate(raw_text: str, model_cls: Type[T]) -> T:
    """Parse raw LLM output text into a Pydantic model with fallback heuristics and auto-repair."""
    json_candidate = extract_json_str(raw_text)
    sanitized = clean_json_text(json_candidate)

    data = None
    try:
        data = json.loads(sanitized)
    except json.JSONDecodeError:
        try:
            data = json.loads(raw_text.strip())
        except Exception:
            # Fall back to auto-repair of truncated or cut-off JSON
            try:
                data = repair_truncated_json(sanitized)
                logger.info("Successfully repaired truncated JSON for %s", model_cls.__name__)
            except Exception:
                try:
                    data = repair_truncated_json(raw_text)
                    logger.info("Successfully repaired truncated raw text for %s", model_cls.__name__)
                except Exception as repair_err:
                    raise ValueError(
                        f"Failed to parse valid JSON from LLM output: {repair_err}\n"
                        f"Output snippet: {raw_text[:200]}"
                    )

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
