"""Stage A: Deterministic Statistics calculation on conversation data."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import statistics
from typing import Dict, List, Optional

from relationship_analyst.config import INACTIVITY_GAP_HOURS
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.message import CanonicalMessage
from relationship_analyst.models.statistics import DeterministicStats, ParticipantStats


def calculate_deterministic_stats(
    repository: Repository,
    project_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> DeterministicStats:
    """
    Calculate deterministic conversational statistics without AI speculation.
    Handles conversation sessions, response times between alternating speakers,
    and message distributions.
    """
    messages = repository.get_all_messages_for_stats(project_id, start_date, end_date)

    if not messages:
        return DeterministicStats(project_id=project_id)

    total_messages = len(messages)
    first_time = messages[0].timestamp
    last_time = messages[-1].timestamp
    duration_days = max(1.0, (last_time - first_time).total_seconds() / 86400.0)

    # Per participant trackers
    msg_counts: Dict[str, int] = defaultdict(int)
    word_counts: Dict[str, List[int]] = defaultdict(list)
    char_counts: Dict[str, int] = defaultdict(int)
    questions_count: Dict[str, int] = defaultdict(int)
    media_counts: Dict[str, int] = defaultdict(int)
    initiations_count: Dict[str, int] = defaultdict(int)
    response_times_minutes: Dict[str, List[float]] = defaultdict(list)

    # Overall distributions
    hourly_dist: Dict[str, int] = defaultdict(int)
    weekday_dist: Dict[str, int] = defaultdict(int)
    monthly_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    system_count = 0
    text_count = 0
    session_count = 0

    gap_threshold = timedelta(hours=INACTIVITY_GAP_HOURS)
    prev_msg: Optional[CanonicalMessage] = None

    for msg in messages:
        if msg.is_system:
            system_count += 1
            continue

        text_count += 1
        sender = msg.sender or "Unknown"
        msg_counts[sender] += 1

        words = len(msg.text.split()) if msg.text else 0
        word_counts[sender].append(words)
        char_counts[sender] += len(msg.text or "")

        if "?" in msg.text:
            questions_count[sender] += 1

        if msg.media_type:
            media_counts[sender] += 1

        # Hourly & weekday
        hour_key = f"{msg.timestamp.hour:02d}:00"
        hourly_dist[hour_key] += 1
        weekday_name = msg.timestamp.strftime("%A")
        weekday_dist[weekday_name] += 1

        # Monthly
        month_key = msg.timestamp.strftime("%Y-%m")
        monthly_counts[month_key][sender] += 1

        # Session and response time detection
        if prev_msg is None:
            # First message starts the first session
            session_count += 1
            initiations_count[sender] += 1
        else:
            time_diff = msg.timestamp - prev_msg.timestamp
            if time_diff >= gap_threshold:
                # Inactive period exceeded: new conversation session
                session_count += 1
                initiations_count[sender] += 1
            else:
                # Within the same session: calculate response time if alternating sender
                if msg.sender != prev_msg.sender:
                    diff_minutes = max(0.0, time_diff.total_seconds() / 60.0)
                    # Filter extreme outliers (> 4 hours is already a session break)
                    response_times_minutes[sender].append(diff_minutes)

        prev_msg = msg

    # Build participant stats
    participants_map: Dict[str, ParticipantStats] = {}
    valid_total_text = max(1, text_count)
    total_sessions_valid = max(1, session_count)

    for sender, count in msg_counts.items():
        w_list = word_counts[sender]
        total_w = sum(w_list)
        avg_w = total_w / max(1, len(w_list))
        median_w = statistics.median(w_list) if w_list else 0.0

        total_c = char_counts[sender]
        avg_c = total_c / max(1, count)

        # Response time percentiles
        resp_list = response_times_minutes[sender]
        avg_resp = (sum(resp_list) / len(resp_list)) if resp_list else None
        median_resp = statistics.median(resp_list) if resp_list else None
        p75_resp = None
        if resp_list:
            sorted_resp = sorted(resp_list)
            p75_idx = int(len(sorted_resp) * 0.75)
            p75_resp = sorted_resp[min(p75_idx, len(sorted_resp) - 1)]

        init_count = initiations_count[sender]

        participants_map[sender] = ParticipantStats(
            name=sender,
            message_count=count,
            message_percentage=round((count / valid_total_text) * 100.0, 1),
            total_words=total_w,
            avg_words_per_message=round(avg_w, 1),
            median_words_per_message=round(median_w, 1),
            total_characters=total_c,
            avg_chars_per_message=round(avg_c, 1),
            questions_asked=questions_count[sender],
            media_shared=media_counts[sender],
            conversations_initiated=init_count,
            initiation_percentage=round((init_count / total_sessions_valid) * 100.0, 1),
            avg_response_time_minutes=round(avg_resp, 1) if avg_resp is not None else None,
            median_response_time_minutes=round(median_resp, 1) if median_resp is not None else None,
            p75_response_time_minutes=round(p75_resp, 1) if p75_resp is not None else None,
        )

    # Sort distributions nicely
    sorted_hourly = {f"{h:02d}:00": hourly_dist.get(f"{h:02d}:00", 0) for h in range(24)}
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    sorted_weekday = {day: weekday_dist.get(day, 0) for day in day_order}
    sorted_monthly = {k: dict(v) for k, v in sorted(monthly_counts.items())}

    return DeterministicStats(
        project_id=project_id,
        total_messages=total_messages,
        total_text_messages=text_count,
        system_messages=system_count,
        start_date=first_time,
        end_date=last_time,
        duration_days=round(duration_days, 1),
        total_sessions=session_count,
        messages_per_day=round(text_count / duration_days, 1),
        participants=participants_map,
        hourly_distribution=sorted_hourly,
        weekday_distribution=sorted_weekday,
        monthly_counts=sorted_monthly,
    )
