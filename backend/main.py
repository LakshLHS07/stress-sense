"""
Mental health check-in API — FastAPI backend.

Run locally:
    uvicorn main:app --reload --port 8000

Docs (auto-generated, useful for testing without curl/Postman):
    http://localhost:8000/docs
"""

import logging
import time
from dotenv import load_dotenv
load_dotenv()  # must run before llm_service reads LLM_PROVIDER / API keys

import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import json
from models import CheckInRequest, AnalysisResponse
from llm_service import analyze_with_llm, compute_sleep_insights
import database

# ---------------------------------------------------------------------------
# Logging (Phase 4): see incoming requests and outgoing payloads live.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("mental_health_api")

app = FastAPI(
    title="Student Mental Health Check-In API",
    description="Backend service for student distress & burnout risk triage.",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# CORS (Phase 1): allow any client or local frontend to call this API.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)")
    return response


@app.get("/")
def root():
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return {"status": "ok", "message": "Mental health check-in API is running."}


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "Mental health check-in API is running."}



@app.post("/api/analyze", response_model=AnalysisResponse)
def analyze_checkin(payload: CheckInRequest):
    req_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    logger.info("--> [INCOMING REQUEST /api/analyze]\n%s", json.dumps(req_dict, indent=2))

    # Sync or retrieve sleep records from tracker database
    if payload.sleep_records:
        database.save_sleep_history(payload.student_id, payload.sleep_records)
        sleep_records = payload.sleep_records
    else:
        sleep_records = database.get_sleep_history(payload.student_id)

    result = analyze_with_llm(payload.journal_text, payload.mood_score, sleep_records=sleep_records)

    logger.info("<-- [OUTGOING PAYLOAD /api/analyze]\n%s", json.dumps(result, indent=2))

    database.save_checkin(
        student_id=payload.student_id,
        journal_text=payload.journal_text,
        mood_score=payload.mood_score,
        analysis=result,
    )

    return result


@app.get("/api/sleep/{student_id}")
def get_student_sleep(student_id: str):
    records = database.get_sleep_history(student_id)
    insights = compute_sleep_insights(records, mood_score=3, stress_score=50, journal_text="")
    return {"student_id": student_id, "records": records, "insights": insights}


@app.post("/api/sleep/{student_id}")
def save_student_sleep(student_id: str, records: list = Body(...)):
    database.save_sleep_history(student_id, records)
    return {"status": "ok", "records": database.get_sleep_history(student_id)}


@app.get("/api/history/{student_id}")
def get_history(student_id: str):
    history = database.get_history_for_student(student_id)
    return history  # [{"date": "...", "mood": 2, "risk": "HIGH"}, ...]


@app.get("/api/counselor/flags")
def get_flags():
    return database.get_flagged_entries()
