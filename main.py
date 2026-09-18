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

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import CheckInRequest, AnalysisResponse
from llm_service import analyze_with_llm
import database

# ---------------------------------------------------------------------------
# Logging (Phase 4): see incoming requests and outgoing payloads live.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("mental_health_api")

app = FastAPI(title="Student Mental Health Check-In API")

# ---------------------------------------------------------------------------
# CORS (Phase 1): allow the local React frontend to call this API.
# NOTE: allow_origins=["*"] is fine for a local demo/hackathon. Before any
# real deployment, replace "*" with your actual frontend origin(s), e.g.
# ["http://localhost:3000", "https://yourapp.vercel.app"], especially once
# this handles real student data.
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
    return {"status": "ok", "message": "Mental health check-in API is running."}


@app.post("/api/analyze", response_model=AnalysisResponse)
def analyze_checkin(payload: CheckInRequest):
    logger.info(f"Incoming check-in | student_id={payload.student_id} mood={payload.mood_score} "
                f"journal_len={len(payload.journal_text)}")

    result = analyze_with_llm(payload.journal_text, payload.mood_score)

    logger.info(f"Outgoing analysis | student_id={payload.student_id} "
                f"risk={result['risk_level']} flagged={result['flag_for_counselor']}")

    database.save_checkin(
        student_id=payload.student_id,
        journal_text=payload.journal_text,
        mood_score=payload.mood_score,
        analysis=result,
    )

    return result


@app.get("/api/history/{student_id}")
def get_history(student_id: str):
    history = database.get_history_for_student(student_id)
    return history  # [{"date": "...", "mood": 2, "risk": "HIGH"}, ...]


@app.get("/api/counselor/flags")
def get_flags():
    return database.get_flagged_entries()
