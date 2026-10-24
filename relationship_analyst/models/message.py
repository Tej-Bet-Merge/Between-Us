"""Canonical Message and Project models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CanonicalMessage(BaseModel):
    """Normalized message representation across all chat import adapters."""
    id: Optional[int] = None
    project_id: str
    source_id: str = Field(description="Original ID in the export file")
    sender: str = Field(description="Normalized participant display name")
    sender_id: Optional[str] = Field(default=None, description="Platform-specific sender ID")
    timestamp: datetime = Field(description="Message timestamp in UTC")
    text: str = Field(default="", description="Cleaned text content")
    reply_to_id: Optional[str] = Field(default=None, description="Source ID of replied message")
    media_type: Optional[str] = Field(default=None, description="photo, audio, video, sticker, etc.")
    is_system: bool = Field(default=False, description="True if system notification (join, leave, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional platform metadata")

    def format_for_prompt(self) -> str:
        """Format message concisely for LLM prompt context."""
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        reply_str = f" [re: #{self.reply_to_id}]" if self.reply_to_id else ""
        text_content = self.text.strip()
        if not text_content and self.media_type:
            text_content = f"<{self.media_type}>"
        return f"[msg_id:{self.id or self.source_id}] [{time_str}] {self.sender}{reply_str}: {text_content}"


def format_compact_chunk_messages(messages: List[CanonicalMessage]) -> str:
    """
    Format a sequence of messages compactly for LLM prompt evaluation.
    Groups by date header once, and uses concise '#ID (HH:MM) Sender: text' format.
    Reduces prompt tokens by ~40% on CPU.
    """
    lines = []
    last_date = None
    for m in messages:
        cur_date = m.timestamp.strftime("%Y-%m-%d")
        if cur_date != last_date:
            lines.append(f"--- Date: {cur_date} ---")
            last_date = cur_date
        t_str = m.timestamp.strftime("%H:%M")
        reply = f" re:#{m.reply_to_id}" if m.reply_to_id else ""
        text = m.text.strip()
        if not text and m.media_type:
            text = f"<{m.media_type}>"
        msg_id = m.id if m.id is not None else m.source_id
        lines.append(f"#{msg_id} ({t_str}) {m.sender}{reply}: {text}")
    return "\n".join(lines)


class ProjectMetadata(BaseModel):
    """Metadata for an analysis project."""
    id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source_file_path: Optional[str] = None
    source_format: Optional[str] = None
    file_size_bytes: int = 0
    message_count: int = 0
    participants: List[str] = Field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = Field(default="imported", description="imported, analyzing, completed, failed")
