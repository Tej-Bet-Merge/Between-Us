"""Importer discovery and file format detection."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Type

from relationship_analyst.importers.base import BaseChatImporter
from relationship_analyst.importers.generic import GenericChatImporter
from relationship_analyst.importers.telegram import TelegramChatImporter

REGISTERED_IMPORTERS: List[Type[BaseChatImporter]] = [
    TelegramChatImporter,
    GenericChatImporter,
]


def detect_importer(file_path: Path | str) -> BaseChatImporter:
    """
    Detect appropriate importer for the given file.
    Raises ValueError with actionable message if format is unsupported or file is not valid JSON.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Export file not found: {path}")

    if path.stat().st_size == 0:
        raise ValueError("Selected file is empty (0 bytes).")

    # Verify basic JSON viability
    try:
        with open(path, "rb") as f:
            chunk = f.read(512).strip()
            if not (chunk.startswith(b"{") or chunk.startswith(b"[")):
                raise ValueError("File does not appear to be a JSON document (does not begin with '{' or '[').")
    except Exception as e:
        raise ValueError(f"Could not read file header: {str(e)}")

    for importer_cls in REGISTERED_IMPORTERS:
        if importer_cls.can_handle(path):
            return importer_cls()

    raise ValueError(
        f"Unsupported JSON chat format. Supported formats include: "
        f"{', '.join(cls.format_name for cls in REGISTERED_IMPORTERS)}."
    )
