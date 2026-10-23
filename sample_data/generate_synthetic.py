"""Synthetic conversation generator for testing and demonstration."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any, Dict, List


def generate_synthetic_telegram_chat(message_count: int = 150) -> Dict[str, Any]:
    """
    Generate synthetic Telegram Desktop JSON export with realistic relationship dynamics:
    - Alex and Jordan
    - Support, minor conflict, repair, affection, boundaries, humor
    """
    start_time = datetime(2023, 1, 15, 9, 30, 0)
    messages: List[Dict[str, Any]] = []

    dialogue_script = [
        # Intro & Pacing
        ("Alex", "Hey Jordan! Good morning, how did you sleep?", 0),
        ("Jordan", "Morning Alex! Pretty well, thanks. Did you finish that presentation last night?", 4),
        ("Alex", "Yeah, wrapped it up around midnight. Honestly feeling a little nervous about today.", 2),
        ("Jordan", "You're going to do great! You put so much thought into it. Remember slide 4 is your strongest point.", 3),
        ("Alex", "Thanks so much, that really helps calm my nerves :)", 1),

        # Workday break (gap)
        ("Alex", "Quick update: the presentation went really well! The team loved the direction.", 300),
        ("Jordan", "YES! I knew you'd crush it! So proud of you!", 5),
        ("Alex", "Could not have done it without your encouragement. Are we still on for dinner on Friday?", 2),
        ("Jordan", "Definitely! Let's try that Italian place downtown.", 3),

        # Inactivity gap to next day
        ("Jordan", "Hey, are you free for a quick call?", 1200),
        ("Alex", "In a meeting until 3, but can call right after! Everything okay?", 6),
        ("Jordan", "Yeah, just got some weird news from my manager, nothing urgent. Call me when you're out.", 2),
        ("Alex", "Calling now!", 45),

        # Minor conflict & boundary setting
        ("Jordan", "Hey, are you on your way? We were supposed to meet at 7:00 and it's 7:25.", 1440),
        ("Alex", "Oh no, traffic on 4th street is completely stopped. I should have texted sooner, so sorry!", 2),
        ("Jordan", "It's frustrating sitting here alone waiting. Please let me know in advance next time.", 3),
        ("Alex", "You are completely right, Jordan. I was rushing and didn't check the time. I apologize, I'll be more considerate.", 4),
        ("Jordan", "Thank you for understanding. See you when you get here.", 2),

        # Repair and warmth
        ("Jordan", "Dinner was really nice despite the rough start. Glad we talked it through.", 180),
        ("Alex", "Me too. I really appreciate how honest you are with me. Have a restful night!", 3),
        ("Jordan", "Goodnight Alex! Sleep well :)", 2),
    ]

    curr_time = start_time
    script_len = len(dialogue_script)
    msg_id = 1001

    for i in range(message_count):
        sender, text, gap_minutes = dialogue_script[i % script_len]
        curr_time += timedelta(minutes=gap_minutes if gap_minutes > 0 else 5)

        raw_msg: Dict[str, Any] = {
            "id": msg_id,
            "type": "message",
            "date": curr_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "date_unixtime": str(int(curr_time.timestamp())),
            "from": sender,
            "from_id": "user_alex" if sender == "Alex" else "user_jordan",
            "text": text,
        }

        # Add occasional replies or media
        if i % 7 == 3:
            raw_msg["reply_to_message_id"] = msg_id - 1
        elif i % 15 == 0 and i > 0:
            raw_msg["media_type"] = "sticker"
            raw_msg["text"] = "👍"

        messages.append(raw_msg)
        msg_id += 1

    return {
        "name": "Alex & Jordan",
        "type": "personal_chat",
        "id": 8839210,
        "messages": messages,
    }


def generate_synthetic_generic_chat(message_count: int = 100) -> List[Dict[str, Any]]:
    """Generate standard/generic JSON chat array."""
    data = generate_synthetic_telegram_chat(message_count)
    generic = []
    for m in data["messages"]:
        generic.append({
            "id": m["id"],
            "sender": m["from"],
            "timestamp": m["date"],
            "text": m["text"],
            "reply_to": m.get("reply_to_message_id"),
        })
    return generic


if __name__ == "__main__":
    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    tg_data = generate_synthetic_telegram_chat(200)
    with open(out_dir / "synthetic_telegram.json", "w", encoding="utf-8") as f:
        json.dump(tg_data, f, indent=2)

    gen_data = generate_synthetic_generic_chat(150)
    with open(out_dir / "synthetic_generic.json", "w", encoding="utf-8") as f:
        json.dump(gen_data, f, indent=2)

    print(f"Generated synthetic fixtures in {out_dir}")
