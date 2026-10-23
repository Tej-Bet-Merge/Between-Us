"""Streaming Telegram Desktop JSON chat export importer using ijson."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generator, List, Optional

import ijson

from relationship_analyst.importers.base import BaseChatImporter, ImportStats
from relationship_analyst.models.message import CanonicalMessage


class TelegramChatImporter(BaseChatImporter):
    format_id = "telegram_json"
    format_name = "Telegram Desktop JSON"

    @classmethod
    def can_handle(cls, file_path: Path) -> bool:
        """Check if top-level contains Telegram chat export keys."""
        try:
            with open(file_path, "rb") as f:
                prefix = f.read(4096).decode("utf-8", errors="ignore")
                return ("messages" in prefix and ("personal_chat" in prefix or "date_unixtime" in prefix or "chats" in prefix or '"type":' in prefix))
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

        with open(file_path, "rb") as f:
            # ijson.items streams through 'messages.item'
            items = ijson.items(f, "messages.item")
            for raw in items:
                if cancel_check and cancel_check():
                    stats.warnings.append("Import was cancelled by user.")
                    break

                try:
                    msg = self._normalize_message(raw, project_id, stats)
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
                        stats.warnings.append(f"Skipped record due to error: {str(ex)}")

        if batch:
            yield batch

        if progress_callback:
            progress_callback(stats.total_parsed, f"Completed: {stats.total_parsed:,} messages parsed.")

        return stats

    def _normalize_message(
        self, raw: dict, project_id: str, stats: ImportStats
    ) -> Optional[CanonicalMessage]:
        if not isinstance(raw, dict):
            stats.skipped_malformed += 1
            return None

        source_id = str(raw.get("id") or "")
        if not source_id:
            stats.skipped_malformed += 1
            return None

        # Determine if system/service message
        msg_type = raw.get("type", "message")
        is_system = (msg_type == "service") or bool(raw.get("action"))

        # Sender
        sender = raw.get("from") or raw.get("actor") or ("System" if is_system else "Unknown")
        sender_id = str(raw.get("from_id") or raw.get("actor_id") or "")

        # Timestamp
        timestamp: Optional[datetime] = None
        if "date_unixtime" in raw:
            try:
                timestamp = datetime.fromtimestamp(int(raw["date_unixtime"]), tz=timezone.utc).replace(tzinfo=None)
            except Exception:
                pass

        if not timestamp and "date" in raw:
            try:
                # Format: 2023-01-01T12:00:00
                date_str = str(raw["date"]).replace("Z", "")
                timestamp = datetime.fromisoformat(date_str)
            except Exception:
                pass

        if not timestamp:
            stats.skipped_malformed += 1
            return None

        # Text extraction (Telegram formats text as str or list of dicts/strings)
        raw_text = raw.get("text", "")
        text = self._flatten_telegram_text(raw_text)

        # Reply reference
        reply_to = str(raw.get("reply_to_message_id")) if raw.get("reply_to_message_id") else None

        # Media type
        media_type = raw.get("media_type")
        if not media_type:
            if "photo" in raw:
                media_type = "photo"
            elif "file" in raw:
                media_type = "file"

        if is_system:
            stats.system_messages += 1

        metadata = {}
        if "reactions" in raw:
            metadata["reactions"] = raw["reactions"]
        if "edited" in raw:
            metadata["edited"] = raw["edited"]

        return CanonicalMessage(
            project_id=project_id,
            source_id=source_id,
            sender=sender,
            sender_id=sender_id if sender_id else None,
            timestamp=timestamp,
            text=text,
            reply_to_id=reply_to,
            media_type=media_type,
            is_system=is_system,
            metadata=metadata,
        )

    def _flatten_telegram_text(self, text_val: Any) -> str:
        if isinstance(text_val, str):
            return text_val
        if isinstance(text_val, list):
            parts = []
            for item in text_val:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
            return "".join(parts)
        return str(text_val or "")
