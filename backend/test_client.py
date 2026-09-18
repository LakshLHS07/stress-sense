"""
Automated test suite for the StressSense FastAPI application.
Tests:
  1. Built-in web frontend serving (GET /)
  2. Deep stress assessment and problem-remedy extraction (/api/analyze)
  3. Safety net & crisis escalation (/api/analyze)
  4. Student history timeline (/api/history/{student_id})
  5. Counselor triage urgent queue (/api/counselor/flags)

Run:
    python test_client.py
"""

import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_suite():
    print("================================================================")
    print("STRESSSENSE AUTOMATED ENDPOINT VERIFICATION")
    print("================================================================")

    # 1. Test Built-in Frontend Serving
    print("\n[TEST 1] Verifying built-in web frontend at GET / ...")
    resp_ui = client.get("/")
    assert resp_ui.status_code == 200, f"Expected 200, got {resp_ui.status_code}"
    assert "StressSense" in resp_ui.text, "StressSense branding not found in HTML"
    assert "Targeted Solutions" in resp_ui.text, "Targeted solutions section missing from HTML"
    print("  --> PASS: Built-in web frontend loaded successfully (HTTP 200, length:", len(resp_ui.text), "bytes)")

    # 2. Test Academic & Burnout Check-In (Multi-problem extraction)
    print("\n[TEST 2] Testing /api/analyze with Academic Burnout entry...")
    burnout_payload = {
        "student_id": "student_042",
        "journal_text": (
            "I have 3 exams back to back this week, my thesis draft is late, "
            "and I've had barely any sleep. Feeling completely overwhelmed."
        ),
        "mood_score": 2,
    }
    resp = client.post("/api/analyze", json=burnout_payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    assert "stress_assessment" in data, "stress_assessment missing from response"
    assert "identified_problems" in data, "identified_problems missing from response"
    assert len(data["identified_problems"]) > 0, "No problems were identified"
    
    stress_info = data["stress_assessment"]
    print(f"  --> Risk Level: {data['risk_level']}")
    print(f"  --> Stress Score: {stress_info['stress_score']}/100 ({stress_info['stress_level']})")
    print(f"  --> Detected Primary Stressors: {stress_info['primary_stressors']}")
    print(f"  --> Isolated Problems Count: {len(data['identified_problems'])}")
    
    for i, p in enumerate(data["identified_problems"], 1):
        print(f"\n      Problem #{i}: [{p['category']} | {p['severity']}] {p['problem']}")
        print(f"      Immediate Remedy: {p['immediate_remedy']}")
        print(f"      Actionable Solution: {p['actionable_solution']}")
        if p.get("suggested_exercise"):
            print(f"      Exercise: {p['suggested_exercise']}")
    
    print("\n  --> PASS: Burnout check-in analyzed with problems and remedies.")

    # 3. Test Safety Net Escalation (Crisis Entry)
    print("\n[TEST 3] Testing /api/analyze with acute crisis entry (Safety net keyword trigger)...")
    crisis_payload = {
        "student_id": "student_crisis_test",
        "journal_text": (
            "Everything feels pointless and I keep thinking everyone would be better off without me."
        ),
        "mood_score": 1,
    }
    crisis_resp = client.post("/api/analyze", json=crisis_payload)
    assert crisis_resp.status_code == 200
    crisis_data = crisis_resp.json()
    
    assert crisis_data["risk_level"] == "HIGH", "Risk level was not elevated to HIGH"
    assert crisis_data["flag_for_counselor"] is True, "flag_for_counselor was not set to True"
    assert crisis_data["stress_assessment"]["stress_score"] >= 85, "Stress score should be >= 85 for crisis"
    
    hotline_titles = [r["title"] for r in crisis_data["coping_resources"]]
    assert any("988" in t for t in hotline_titles), "988 hotline missing from coping resources"
    print("  --> Risk Level:", crisis_data["risk_level"])
    print("  --> Flagged for Counselor:", crisis_data["flag_for_counselor"])
    print("  --> Stress Score:", crisis_data["stress_assessment"]["stress_score"])
    print("  --> PASS: Safety net elevated risk, attached crisis hotlines, and flagged counselor.")

    # 4. Test History Endpoint
    print("\n[TEST 4] Testing /api/history/student_042 ...")
    hist_resp = client.get("/api/history/student_042")
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    assert len(history) >= 1, "Expected at least 1 history record"
    print(f"  --> Retrieved {len(history)} past check-in(s) for student_042.")
    print("  --> Latest entry stress score:", history[-1].get("stress_score"))
    print("  --> PASS: History endpoint operational.")

    # 5. Test Counselor Triage Flags Endpoint
    print("\n[TEST 5] Testing /api/counselor/flags ...")
    flags_resp = client.get("/api/counselor/flags")
    assert flags_resp.status_code == 200
    flags = flags_resp.json()
    assert len(flags) >= 1, "Expected flagged entries from the crisis test"
    flagged_ids = [f["student_id"] for f in flags]
    assert "student_crisis_test" in flagged_ids, "student_crisis_test missing from counselor queue"
    print(f"  --> Counselor queue currently has {len(flags)} urgent flag(s): {flagged_ids}")
    print("  --> PASS: Counselor triage flags endpoint operational.")

    # 6. Test Sleep Tracker Database & Cross-Analysis Insights
    print("\n[TEST 6] Testing Sleep Tracker Database & AI Insights (/api/sleep/student_042) ...")
    sleep_resp = client.get("/api/sleep/student_042")
    assert sleep_resp.status_code == 200, f"Expected 200, got {sleep_resp.status_code}"
    sleep_data = sleep_resp.json()
    assert "records" in sleep_data and len(sleep_data["records"]) == 7, "Expected 7-day sleep records"
    assert "insights" in sleep_data, "Expected insights in sleep data"
    
    insights = sleep_data["insights"]
    print(f"  --> 7-Day Average Sleep: {insights['avg_hours']}h/night")
    print(f"  --> Cumulative Debt: {insights['sleep_debt_hours']}h ({insights['debt_status']})")
    print(f"  --> Stress Correlation: {insights['stress_correlation']}")
    print(f"  --> Biometric Impact: {insights['impact_badge'].encode('ascii', 'replace').decode('ascii')}")
    print(f"  --> Clinical Narrative: {insights['clinical_narrative'][:120]}...")
    print("  --> PASS: Sleep tracker database and AI analysis insights verified.")

    print("\n================================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! APP IS READY FOR LOCAL VISITS.")
    print("================================================================\n")


if __name__ == "__main__":
    test_suite()


