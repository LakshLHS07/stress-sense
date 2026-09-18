"""
Simple in-memory 'database' for the demo.

This is intentionally NOT persistent — it resets when the server restarts.
That's fine for a hackathon/demo. If you need real persistence, swap this
module for a SQLite-backed version (see the README for the upgrade path)
without touching main.py, since main.py only calls the functions below.
"""

from datetime import datetime, timezone
from typing import List, Dict

# Each record: {student_id, date, timestamp, journal_text, mood_score, risk_level,
#               stress_score, stress_level, primary_stressors, sentiment_summary,
#               recommended_action, flag_for_counselor, identified_problems, coping_resources}
_records: List[Dict] = []

# In-memory storage for sleep records by student_id
_sleep_records: Dict[str, List[Dict]] = {}

DEFAULT_SLEEP_DATA: List[Dict] = [
    {"day": "Mon", "hours": 6.8, "quality": "Fair", "notes": "Late study session"},
    {"day": "Tue", "hours": 5.5, "quality": "Restless", "notes": "Exam preparation"},
    {"day": "Wed", "hours": 7.8, "quality": "Good", "notes": "Recovered sleep"},
    {"day": "Thu", "hours": 6.2, "quality": "Fair", "notes": "Thesis writing"},
    {"day": "Fri", "hours": 7.4, "quality": "Good", "notes": "Weekend start"},
    {"day": "Sat", "hours": 8.5, "quality": "Optimal", "notes": "Restful recovery"},
    {"day": "Sun", "hours": 7.5, "quality": "Good", "notes": "Balanced bedtime"},
]


def get_sleep_history(student_id: str) -> List[Dict]:
    """Retrieve 7-day sleep records for a given student, defaulting to standard baseline."""
    if student_id not in _sleep_records:
        _sleep_records[student_id] = [dict(entry) for entry in DEFAULT_SLEEP_DATA]
    return _sleep_records[student_id]


def save_sleep_history(student_id: str, records: List[Dict]) -> None:
    """Save updated sleep entries for a student."""
    if records:
        _sleep_records[student_id] = records


def save_checkin(student_id: str, journal_text: str, mood_score: int, analysis: dict) -> None:
    stress_info = analysis.get("stress_assessment", {})
    _records.append({
        "student_id": student_id,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "journal_text": journal_text,
        "mood_score": mood_score,
        "risk_level": analysis.get("risk_level", "LOW"),
        "stress_score": stress_info.get("stress_score", 50),
        "stress_level": stress_info.get("stress_level", "Moderate"),
        "primary_stressors": stress_info.get("primary_stressors", []),
        "sentiment_summary": analysis.get("sentiment_summary", ""),
        "recommended_action": analysis.get("recommended_action", ""),
        "flag_for_counselor": analysis.get("flag_for_counselor", False),
        "identified_problems": analysis.get("identified_problems", []),
        "coping_resources": analysis.get("coping_resources", []),
        "sleep_insights": analysis.get("sleep_insights"),
    })


def get_history_for_student(student_id: str) -> List[Dict]:
    return [
        {
            "date": r["date"],
            "mood": r["mood_score"],
            "risk": r["risk_level"],
            "stress_score": r.get("stress_score", 50),
            "primary_stressors": r.get("primary_stressors", []),
            "identified_problems": r.get("identified_problems", []),
            "recommended_action": r.get("recommended_action", ""),
            "sleep_insights": r.get("sleep_insights"),
        }
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
            "stress_score": r.get("stress_score", 85),
            "recommended_action": r["recommended_action"],
            "identified_problems": r.get("identified_problems", []),
            "sleep_insights": r.get("sleep_insights"),
        }
        for r in _records
        if r["flag_for_counselor"]
    ]


def all_records() -> List[Dict]:
    return list(_records)


