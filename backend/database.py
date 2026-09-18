"""
Simple in-memory 'database' for the demo.

This is intentionally NOT persistent — it resets when the server restarts.
That's fine for a hackathon/demo. If you need real persistence, swap this
module for a SQLite-backed version (see the README for the upgrade path)
without touching main.py, since main.py only calls the functions below.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

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


def _seed_initial_records():
    now = datetime.now(timezone.utc)
    seed_days = [
        # (day_offset, student_id, mood, stress, risk, text, problems)
        (0, "student_042", 4, 28, "LOW", "Feeling focused and clear-headed. Finished the morning project sprint on schedule.", [
            {"problem": "Coursework pacing", "category": "Academic", "severity": "Mild", "immediate_remedy": "Diaphragmatic breath and celebrate completed milestone.", "actionable_solution": "Maintain steady study blocks and designated rest buffers.", "suggested_exercise": "Habit Pacing & Mindful Reflection"}
        ]),
        (1, "student_042", 4, 32, "LOW", "Solid day in lab and good group discussion. Slept 8 hours last night.", [
            {"problem": "Group project coordination", "category": "Academic", "severity": "Mild", "immediate_remedy": "Quick stretch and hydration check.", "actionable_solution": "Keep active communication with team.", "suggested_exercise": "Postural Alignment & Hydration Check"}
        ]),
        (2, "student_042", 5, 20, "LOW", "Thriving today! Exercise in the morning helped me concentrate throughout all lectures.", [
            {"problem": "Physical stamina", "category": "Sleep & Physical", "severity": "Mild", "immediate_remedy": "Deep belly breathing and posture check.", "actionable_solution": "Sustain regular exercise schedule.", "suggested_exercise": "Postural Alignment & Hydration Check"}
        ]),
        (3, "student_042", 3, 58, "MEDIUM", "A bit stressed with upcoming midterms and project milestone due on Friday.", [
            {"problem": "Elevated academic workload", "category": "Academic", "severity": "Moderate", "immediate_remedy": "3-minute Brain Dump on paper.", "actionable_solution": "Implement 25/5 Pomodoro intervals.", "suggested_exercise": "Pomodoro Technique (25m study / 5m rest)"}
        ]),
        (4, "student_042", 3, 62, "MEDIUM", "Tired from late night study session. Head hurts a little bit.", [
            {"problem": "Sleep deficit & fatigue", "category": "Sleep & Physical", "severity": "Moderate", "immediate_remedy": "Glass of water and shoulder rolls.", "actionable_solution": "Wind-down buffer at 10:30 PM tonight.", "suggested_exercise": "Gentle Body Scan"}
        ]),
        (5, "student_042", 2, 85, "HIGH", "Felt panicked about the chemistry exam tomorrow. Overwhelmed by back-to-back quizzes.", [
            {"problem": "Acute academic panic", "category": "Academic", "severity": "Severe", "immediate_remedy": "4-4-4-4 Box Breathing immediately.", "actionable_solution": "Request extension and do 8h recovery sleep tonight.", "suggested_exercise": "Box Breathing (4-4-4-4)"}
        ]),
        (6, "student_042", 3, 50, "MEDIUM", "Recovering from yesterday. Studied with a classmate at the library.", [
            {"problem": "Academic workload pacing", "category": "Academic", "severity": "Moderate", "immediate_remedy": "5-minute walk outside.", "actionable_solution": "Focus on high-priority chapter only.", "suggested_exercise": "Pomodoro Technique"}
        ]),
        (7, "student_042", 4, 30, "LOW", "Weekend rest did wonders. Took a long walk and slept 9 hours.", [
            {"problem": "Energy maintenance", "category": "Sleep & Physical", "severity": "Mild", "immediate_remedy": "Mindful gratitude reflection.", "actionable_solution": "Maintain consistent sleep window.", "suggested_exercise": "Gratitude Log"}
        ]),
        (8, "student_042", 5, 22, "LOW", "Great Sunday afternoon with friends. Ready for the week ahead.", [
            {"problem": "Social connection", "category": "Social & Relational", "severity": "Mild", "immediate_remedy": "Diaphragmatic breath.", "actionable_solution": "Keep balanced study and leisure blocks.", "suggested_exercise": "Mindful Reflection"}
        ]),
        (9, "student_042", 4, 25, "LOW", "Started the week with strong momentum. Got positive feedback from prof.", [
            {"problem": "Daily coursework pacing", "category": "Academic", "severity": "Mild", "immediate_remedy": "Celebrate small win.", "actionable_solution": "Outline tomorrow's tasks.", "suggested_exercise": "Habit Pacing"}
        ]),
        (10, "student_042", 4, 34, "LOW", "Finished reading assignments early. Calm and balanced evening.", [
            {"problem": "Routine pacing", "category": "General", "severity": "Mild", "immediate_remedy": "Slow exhale.", "actionable_solution": "Sustain evening screen cutoff.", "suggested_exercise": "Habit Pacing"}
        ]),
        (11, "student_042", 3, 56, "MEDIUM", "Long lab session; hands and eyes feeling strained.", [
            {"problem": "Physical fatigue", "category": "Sleep & Physical", "severity": "Moderate", "immediate_remedy": "Shoulder rolls and screen break.", "actionable_solution": "Pomodoro breaks every 30m.", "suggested_exercise": "Progressive Muscle Relaxation"}
        ]),
        (12, "student_042", 2, 82, "HIGH", "Felt overwhelmed by multiple deadlines piling up at once.", [
            {"problem": "Cognitive overload", "category": "Emotional & Mental", "severity": "Severe", "immediate_remedy": "5-4-3-2-1 Sensory Grounding.", "actionable_solution": "Emergency triage of non-essential tasks.", "suggested_exercise": "5-4-3-2-1 Grounding"}
        ]),
    ]
    
    for offset, student_id, mood, stress, risk, text, problems in seed_days:
        dt = now - timedelta(days=offset)
        _records.append({
            "id": f"rec_{student_id}_{int(dt.timestamp())}_{offset}",
            "student_id": student_id,
            "date": dt.strftime("%Y-%m-%d"),
            "timestamp": dt.isoformat(),
            "journal_text": text,
            "mood_score": mood,
            "risk_level": risk,
            "stress_score": stress,
            "stress_level": "Critical / Severe" if risk == "HIGH" else ("Moderate Stress" if risk == "MEDIUM" else "Low / Manageable"),
            "primary_stressors": ["Academic Workload" if "Academic" in problems[0]["category"] else "Physical Fatigue"],
            "sentiment_summary": f"Reflective entry indicating {risk.lower()} distress state.",
            "recommended_action": "Maintain healthy pacing and restorative rest." if risk != "HIGH" else "Engage acute decompression circuit breaker.",
            "flag_for_counselor": (risk == "HIGH"),
            "identified_problems": problems,
            "coping_resources": [],
            "sleep_insights": None,
            "review": {
                "action_taken": "Practiced 4-4-4-4 Box Breathing and listened to Spotify mood booster playlist.",
                "outcome": "helped_lot",
                "status": "resolved",
                "reviewed_at": (now - timedelta(days=offset, hours=-2)).isoformat()
            } if (risk == "HIGH" and offset == 12) else None
        })

_seed_initial_records()


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
    now_dt = datetime.now(timezone.utc)
    _records.append({
        "id": f"rec_{student_id}_{int(now_dt.timestamp())}",
        "student_id": student_id,
        "date": now_dt.strftime("%Y-%m-%d"),
        "timestamp": now_dt.isoformat(),
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
        "review": None,
    })


def save_alert_review(record_id: str, action_taken: str, outcome: str, status: str = "resolved") -> Optional[Dict]:
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in _records:
        if r.get("id") == record_id or r.get("timestamp") == record_id or (r.get("date") == record_id and r.get("flag_for_counselor")):
            r["review"] = {
                "action_taken": action_taken,
                "outcome": outcome,
                "status": status,
                "reviewed_at": now_iso,
            }
            return r
    return None


def get_history_for_student(student_id: str) -> List[Dict]:
    return [
        {
            "id": r.get("id", f"rec_{r.get('date')}"),
            "date": r["date"],
            "timestamp": r.get("timestamp") or r["date"],
            "journal_text": r.get("journal_text", ""),
            "mood": r["mood_score"],
            "mood_score": r["mood_score"],
            "risk": r["risk_level"],
            "risk_level": r["risk_level"],
            "stress_score": r.get("stress_score", 50),
            "stress_level": r.get("stress_level", "Moderate"),
            "primary_stressors": r.get("primary_stressors", []),
            "identified_problems": r.get("identified_problems", []),
            "recommended_action": r.get("recommended_action", ""),
            "sentiment_summary": r.get("sentiment_summary", ""),
            "sleep_insights": r.get("sleep_insights"),
            "review": r.get("review"),
        }
        for r in _records
        if r["student_id"] == student_id
    ]


def get_flagged_entries() -> List[Dict]:
    return [
        {
            "id": r.get("id", f"rec_{r['student_id']}_{r['date']}"),
            "student_id": r["student_id"],
            "date": r["date"],
            "timestamp": r.get("timestamp") or r["date"],
            "journal_text": r["journal_text"],
            "risk_level": r["risk_level"],
            "stress_score": r.get("stress_score", 85),
            "recommended_action": r["recommended_action"],
            "identified_problems": r.get("identified_problems", []),
            "sleep_insights": r.get("sleep_insights"),
            "review": r.get("review"),
        }
        for r in _records
        if r["flag_for_counselor"]
    ]


def all_records() -> List[Dict]:
    return list(_records)


