"""Base streaming chat importer interface and statistics tracking."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Generator, List, Optional, Set

from relationship_analyst.models.message import CanonicalMessage


@dataclass
class ImportStats:
    total_parsed: int = 0
    total_inserted: int = 0
    system_messages: int = 0
    skipped_malformed: int = 0
    warnings: List[str] = field(default_factory=list)
    participants: Set[str] = field(default_factory=set)
    earliest_date: Optional[datetime] = None
    latest_date: Optional[datetime] = None


class BaseChatImporter(ABC):
    """Abstract base class for streaming chat importers."""

    format_id: str = "base"
    format_name: str = "Base Importer"

    @classmethod
    @abstractmethod
    def can_handle(cls, file_path: Path) -> bool:
        """Inspect the first few KB of a file to check if this importer can handle it."""
        raise NotImplementedError

    @abstractmethod
    def parse_stream(
        self,
        file_path: Path,
        project_id: str,
        cancel_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        batch_size: int = 1000,
    ) -> Generator[List[CanonicalMessage], None, ImportStats]:
        """
        Streamingly yield batches of CanonicalMessage without loading entire file.
        Returns final ImportStats upon completion.
        """
        raise NotImplementedError
