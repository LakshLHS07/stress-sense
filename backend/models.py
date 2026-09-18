"""
Pydantic data contracts for the mental health check-in API.
Supports deep stress assessment, problem extraction, and targeted remedies.
"""

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field


class SleepLogEntry(BaseModel):
    day: str
    hours: float
    quality: Optional[str] = "Good"
    notes: Optional[str] = ""


class SleepInsights(BaseModel):
    avg_hours: float
    sleep_debt_hours: float
    debt_status: str  # "Deficit" or "Surplus"
    recent_night_hours: float
    recent_quality: str
    circadian_regularity: str
    deep_sleep_ratio: str
    stress_correlation: str
    impact_badge: str
    clinical_narrative: str
    actionable_sleep_rule: str


class CheckInRequest(BaseModel):
    student_id: str
    journal_text: str
    mood_score: int = Field(..., ge=1, le=5, description="Self-reported mood, 1 (worst) to 5 (best)")
    sleep_records: Optional[List[Dict]] = Field(default=None, description="Optional 7-day sleep log from sleep tracker")


class CopingResource(BaseModel):
    title: str
    description: str
    url: str = ""


class ProblemRemedy(BaseModel):
    problem: str = Field(..., description="The specific root stressor or challenge identified from the journal")
    category: str = Field("General", description="Academic, Sleep & Physical, Emotional & Mental, Social & Relational, Financial, etc.")
    severity: Literal["Mild", "Moderate", "Severe"] = "Moderate"
    immediate_remedy: str = Field(..., description="Actionable 2-to-5 minute reset or relief practice")
    actionable_solution: str = Field(..., description="Structured practical plan to solve or manage the problem")
    suggested_exercise: str = Field("", description="Specific coping technique, e.g. Box breathing, Pomodoro, 5-4-3-2-1 grounding")


class StressAssessment(BaseModel):
    stress_score: int = Field(..., ge=0, le=100, description="Overall stress level score from 0 (very low) to 100 (extreme)")
    stress_level: str = Field(..., description="Low / Manageable, Moderate Stress, High Distress, or Critical")
    primary_stressors: List[str] = Field(default_factory=list, description="Top detected stress categories or triggers")


class AnalysisResponse(BaseModel):
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    stress_assessment: StressAssessment
    sentiment_summary: str
    recommended_action: str
    flag_for_counselor: bool
    identified_problems: List[ProblemRemedy] = Field(default_factory=list)
    coping_resources: List[Dict] = Field(default_factory=list)
    sleep_insights: Optional[SleepInsights] = None


class HistoryEntry(BaseModel):
    date: str
    mood: int
    risk: str
    stress_score: int = 50
    primary_stressors: List[str] = Field(default_factory=list)


class FlaggedEntry(BaseModel):
    student_id: str
    date: str
    journal_text: str
    risk_level: str
    stress_score: int = 80
    recommended_action: str
    identified_problems: List[Dict] = Field(default_factory=list)

