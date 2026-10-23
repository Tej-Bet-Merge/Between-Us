"""Models for Stage A Deterministic Statistics."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ParticipantStats(BaseModel):
    name: str
    message_count: int = 0
    message_percentage: float = 0.0
    total_words: int = 0
    avg_words_per_message: float = 0.0
    median_words_per_message: float = 0.0
    total_characters: int = 0
    avg_chars_per_message: float = 0.0
    questions_asked: int = 0
    media_shared: int = 0
    conversations_initiated: int = 0
    initiation_percentage: float = 0.0
    avg_response_time_minutes: Optional[float] = None
    median_response_time_minutes: Optional[float] = None
    p75_response_time_minutes: Optional[float] = None


class DeterministicStats(BaseModel):
    project_id: str
    total_messages: int = 0
    total_text_messages: int = 0
    system_messages: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration_days: float = 0.0
    total_sessions: int = 0
    messages_per_day: float = 0.0
    participants: Dict[str, ParticipantStats] = Field(default_factory=dict)
    hourly_distribution: Dict[str, int] = Field(default_factory=dict)
    weekday_distribution: Dict[str, int] = Field(default_factory=dict)
    monthly_counts: Dict[str, Dict[str, int]] = Field(default_factory=dict)

    def summary_text(self) -> str:
        """Concise text representation for feeding into LLM synthesis."""
        lines = [
            f"Total Messages: {self.total_messages} over {self.duration_days:.1f} days ({self.messages_per_day:.1f} msgs/day)",
            f"Date Range: {self.start_date.strftime('%Y-%m-%d') if self.start_date else 'N/A'} to {self.end_date.strftime('%Y-%m-%d') if self.end_date else 'N/A'}",
            f"Distinct Conversation Sessions: {self.total_sessions} (using 4h inactivity boundary)"
        ]
        for name, p in self.participants.items():
            resp_str = f"median resp: {p.median_response_time_minutes:.1f} min" if p.median_response_time_minutes is not None else "resp: N/A"
            lines.append(
                f"- {name}: {p.message_count} msgs ({p.message_percentage:.1f}%), "
                f"{p.avg_words_per_message:.1f} avg words/msg, "
                f"{p.questions_asked} questions, "
                f"initiated {p.conversations_initiated} sessions ({p.initiation_percentage:.1f}%), {resp_str}"
            )
        return "\n".join(lines)
