"""
Pydantic data contracts for the mental health check-in API.
Phase 1 deliverable.
"""

from typing import List, Dict, Literal
from pydantic import BaseModel, Field


class CheckInRequest(BaseModel):
    student_id: str
    journal_text: str
    mood_score: int = Field(..., ge=1, le=5, description="Self-reported mood, 1 (worst) to 5 (best)")


class CopingResource(BaseModel):
    title: str
    description: str
    url: str = ""


class AnalysisResponse(BaseModel):
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    sentiment_summary: str
    recommended_action: str
    flag_for_counselor: bool
    coping_resources: List[Dict] = []


class HistoryEntry(BaseModel):
    date: str
    mood: int
    risk: str


class FlaggedEntry(BaseModel):
    student_id: str
    date: str
    journal_text: str
    risk_level: str
    recommended_action: str
