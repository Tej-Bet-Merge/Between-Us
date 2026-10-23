"""Streaming Generic JSON chat export importer using ijson."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generator, List, Optional

import ijson

from relationship_analyst.importers.base import BaseChatImporter, ImportStats
from relationship_analyst.models.message import CanonicalMessage


class GenericChatImporter(BaseChatImporter):
    format_id = "generic_json"
    format_name = "Standard / Generic JSON"

    @classmethod
    def can_handle(cls, file_path: Path) -> bool:
        """Inspect the start of file to see if it is JSON array or generic object."""
        try:
            with open(file_path, "rb") as f:
                prefix = f.read(2048).decode("utf-8", errors="ignore").strip()
                if prefix.startswith("["):
                    return True
                if "messages" in prefix or "conversations" in prefix or "chat" in prefix:
                    return True
            return False
        except Exception:
            return False

    def parse_stream(
        self,
        file_path: Path,
        project_id: str,
        cancel_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        batch_size: int = 1000,
    ) -> Generator[List[CanonicalMessage], None, ImportStats]:
        stats = ImportStats()
        batch: List[CanonicalMessage] = []

        # Determine path in ijson: 'item' if root is list, or 'messages.item' if root is object
        is_root_list = False
        with open(file_path, "rb") as f:
            first_char = f.read(1024).strip()
            if first_char.startswith(b"["):
                is_root_list = True

        prefix_path = "item" if is_root_list else "messages.item"

        with open(file_path, "rb") as f:
            items = ijson.items(f, prefix_path)
            synthetic_id = 1
            for raw in items:
                if cancel_check and cancel_check():
                    stats.warnings.append("Import was cancelled by user.")
                    break

                try:
                    msg = self._normalize_record(raw, project_id, synthetic_id, stats)
                    synthetic_id += 1
                    if msg:
                        batch.append(msg)
                        stats.total_parsed += 1
                        if msg.sender and not msg.is_system:
                            stats.participants.add(msg.sender)
                        if stats.earliest_date is None or msg.timestamp < stats.earliest_date:
                            stats.earliest_date = msg.timestamp
                        if stats.latest_date is None or msg.timestamp > stats.latest_date:
                            stats.latest_date = msg.timestamp

                    if len(batch) >= batch_size:
                        if progress_callback:
                            progress_callback(stats.total_parsed, f"Processed {stats.total_parsed:,} messages...")
                        yield batch
                        batch = []
                except Exception as ex:
                    stats.skipped_malformed += 1
                    if len(stats.warnings) < 10:
                        stats.warnings.append(f"Skipped record: {str(ex)}")

        if batch:
            yield batch

        if progress_callback:
            progress_callback(stats.total_parsed, f"Completed: {stats.total_parsed:,} messages parsed.")

        return stats

    def _normalize_record(
        self, raw: dict, project_id: str, auto_id: int, stats: ImportStats
    ) -> Optional[CanonicalMessage]:
        if not isinstance(raw, dict):
            stats.skipped_malformed += 1
            return None

        # Resolve ID
        source_id = str(raw.get("id") or raw.get("message_id") or raw.get("mid") or f"gen_{auto_id}")

        # Resolve Sender
        sender = (
            raw.get("sender")
            or raw.get("author")
            or raw.get("from")
            or raw.get("user")
            or raw.get("name")
            or "Participant"
        )
        if isinstance(sender, dict):
            sender = sender.get("name") or sender.get("username") or str(sender.get("id", "User"))

        sender_id = str(raw.get("sender_id") or raw.get("author_id") or raw.get("user_id") or "")

        # Resolve Text
        text = raw.get("text") or raw.get("content") or raw.get("message") or raw.get("body") or ""
        if isinstance(text, (list, dict)):
            text = json.dumps(text, ensure_ascii=False)
        else:
            text = str(text)

        # Resolve Timestamp
        ts_val = (
            raw.get("timestamp")
            or raw.get("date")
            or raw.get("time")
            or raw.get("created_at")
            or raw.get("datetime")
        )
        timestamp: Optional[datetime] = None
        if isinstance(ts_val, (int, float)):
            try:
                # Detect whether seconds or milliseconds
                val = float(ts_val)
                if val > 1e11:  # milliseconds
                    val = val / 1000.0
                timestamp = datetime.fromtimestamp(val, tz=timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
        elif isinstance(ts_val, str):
            try:
                clean_ts = ts_val.replace("Z", "+00:00")
                timestamp = datetime.fromisoformat(clean_ts)
                if timestamp.tzinfo:
                    timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y, %H:%M"):
                    try:
                        timestamp = datetime.strptime(ts_val, fmt)
                        break
                    except Exception:
                        pass

        if not timestamp:
            stats.skipped_malformed += 1
            return None

        # System message flag
        is_system = bool(raw.get("is_system") or raw.get("system") or raw.get("type") in ("system", "notification"))
        if is_system:
            stats.system_messages += 1

        reply_to = str(raw.get("reply_to") or raw.get("reply_to_id") or "")
        media_type = str(raw.get("media_type") or raw.get("media") or "")

        return CanonicalMessage(
            project_id=project_id,
            source_id=source_id,
            sender=str(sender),
            sender_id=sender_id if sender_id else None,
            timestamp=timestamp,
            text=text,
            reply_to_id=reply_to if reply_to else None,
            media_type=media_type if media_type else None,
            is_system=is_system,
            metadata={},
        )
