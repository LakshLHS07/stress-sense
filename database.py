"""
Simple in-memory 'database' for the demo.

This is intentionally NOT persistent — it resets when the server restarts.
That's fine for a hackathon/demo. If you need real persistence, swap this
module for a SQLite-backed version (see the README for the upgrade path)
without touching main.py, since main.py only calls the functions below.
"""

from datetime import datetime, timezone
from typing import List, Dict

# Each record: {student_id, date, journal_text, mood_score, risk_level,
#               sentiment_summary, recommended_action, flag_for_counselor}
_records: List[Dict] = []


def save_checkin(student_id: str, journal_text: str, mood_score: int, analysis: dict) -> None:
    _records.append({
        "student_id": student_id,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "journal_text": journal_text,
        "mood_score": mood_score,
        "risk_level": analysis["risk_level"],
        "sentiment_summary": analysis["sentiment_summary"],
        "recommended_action": analysis["recommended_action"],
        "flag_for_counselor": analysis["flag_for_counselor"],
    })


def get_history_for_student(student_id: str) -> List[Dict]:
    return [
        {"date": r["date"], "mood": r["mood_score"], "risk": r["risk_level"]}
        for r in _records
        if r["student_id"] == student_id
    ]


def get_flagged_entries() -> List[Dict]:
    return [
        {
            "student_id": r["student_id"],
            "date": r["date"],
            "journal_text": r["journal_text"],
            "risk_level": r["risk_level"],
            "recommended_action": r["recommended_action"],
        }
        for r in _records
        if r["flag_for_counselor"]
    ]


def all_records() -> List[Dict]:
    return list(_records)
