"""
Quick manual test script for /api/analyze.
Run the server first (uvicorn main:app --reload --port 8000), then:

    python test_client.py
"""

import requests
import json

URL = "http://localhost:8000/api/analyze"

# A deliberately high-stress entry to test the HIGH-risk / flagging path.
high_stress_payload = {
    "student_id": "student_042",
    "journal_text": (
        "I haven't slept properly in days and I can't focus on anything. "
        "Everything feels pointless and I keep thinking everyone would be "
        "better off without me around."
    ),
    "mood_score": 1,
}

# A low-stress entry to test the normal path.
low_stress_payload = {
    "student_id": "student_042",
    "journal_text": "Had a decent day. A bit tired from studying but nothing major.",
    "mood_score": 4,
}


def run(payload, label):
    print(f"\n--- {label} ---")
    resp = requests.post(URL, json=payload, timeout=10)
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    run(high_stress_payload, "HIGH-STRESS ENTRY")
    run(low_stress_payload, "LOW-STRESS ENTRY")

    print("\n--- History for student_042 ---")
    print(requests.get("http://localhost:8000/api/history/student_042").json())

    print("\n--- Counselor flags ---")
    print(requests.get("http://localhost:8000/api/counselor/flags").json())
