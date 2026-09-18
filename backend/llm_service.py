"""
LLM integration for /api/analyze.

Design notes (read before you present this):

1. LLM_PROVIDER controls which backend is used: "mock", "openai", or "gemini".
   Default is "mock" so the app runs and demos with ZERO API keys. Flip the
   env var once you have a key.

2. SAFETY NET: risk detection for self-harm / suicidal ideation does NOT rely
   on the LLM alone. A simple keyword screen runs on every journal entry
   first. If it fires, we force risk_level=HIGH and flag_for_counselor=True
   regardless of what the LLM returns, and we always attach static crisis
   resources (not LLM-generated, so they can't be hallucinated or dropped).
   This is standard practice for any real wellbeing tool: a model
   occasionally mis-parsing JSON or softening language should never be the
   only thing standing between a student in crisis and a counselor alert.

   This keyword list is deliberately basic. For anything beyond a hackathon
   demo, this should be reviewed by a clinician/counselor on your team and
   probably replaced or supplemented with a proper triage rubric.

3. On any LLM failure (network error, timeout, malformed JSON), we return a
   SAFE DEFAULT that flags for counselor review rather than silently
   defaulting to "everything is fine". Fail safe, not fail quiet.
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger("mental_health_api")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()

CRISIS_RESOURCES = [
    {
        "title": "988 Suicide & Crisis Lifeline (US)",
        "description": "Free, confidential support 24/7. Call or text 988.",
        "url": "https://988lifeline.org",
    },
    {
        "title": "Crisis Text Line",
        "description": "Text HOME to 741741 to reach a crisis counselor.",
        "url": "https://www.crisistextline.org",
    },
]

GENERAL_RESOURCES = [
    {
        "title": "Campus Counseling Center",
        "description": "Free confidential sessions for enrolled students.",
        "url": "",
    },
    {
        "title": "5-Minute Breathing Exercise",
        "description": "A short guided breathing exercise to reduce acute stress.",
        "url": "",
    },
]

# Deliberately simple substring screen. Case-insensitive.
_HIGH_RISK_KEYWORDS = [
    "kill myself", "end my life", "end it all", "suicide", "suicidal",
    "want to die", "better off dead", "no reason to live", "can't go on",
    "hurt myself", "self harm", "self-harm", "cutting myself",
]

SYSTEM_PROMPT = """You are a triage assistant embedded in a student mental health check-in app.
You are NOT a therapist and you do not provide diagnoses. Your job is to read a short
journal entry and a 1-5 mood score, and output a structured risk assessment so a human
counselor can prioritize follow-ups.

Respond with ONLY a single JSON object, no markdown fences, no preamble, matching exactly
this schema:

{
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "sentiment_summary": "<1-2 sentence neutral summary of emotional state>",
  "recommended_action": "<1 short sentence: what a counselor or the student should do next>",
  "flag_for_counselor": true | false,
  "coping_resources": [{"title": "...", "description": "...", "url": "..."}]
}

Guidance:
- HIGH risk: any indication of suicidal ideation, self-harm, hopelessness framed as permanent,
  or acute crisis. Always set flag_for_counselor=true for HIGH.
- MEDIUM risk: burnout, persistent low mood, high stress, isolation, but no crisis indicators.
- LOW risk: normal stress, temporary sadness, or generally coping well.
- Never be dismissive. Never diagnose. Keep sentiment_summary neutral and factual.
- coping_resources should be 1-3 general, safe suggestions (breathing exercises, campus
  resources, sleep hygiene, talking to a friend) — not clinical advice or medication.
"""


def _keyword_screen(journal_text: str) -> bool:
    text = journal_text.lower()
    return any(kw in text for kw in _HIGH_RISK_KEYWORDS)


def _safe_default(flagged: bool) -> dict:
    """Fail-safe fallback used whenever the LLM call fails or returns malformed JSON."""
    return {
        "risk_level": "MEDIUM" if not flagged else "HIGH",
        "sentiment_summary": "Automated analysis was unavailable for this entry.",
        "recommended_action": "This entry could not be automatically analyzed and has been "
                               "queued for manual counselor review.",
        "flag_for_counselor": True,  # fail safe: always route to a human on failure
        "coping_resources": CRISIS_RESOURCES if flagged else GENERAL_RESOURCES,
    }


def _call_openai(journal_text: str, mood_score: int) -> Optional[dict]:
    from openai import OpenAI  # pip install openai

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"mood_score: {mood_score}\njournal_text: {journal_text}"},
        ],
        temperature=0.3,
    )
    return json.loads(resp.choices[0].message.content)


def _call_gemini(journal_text: str, mood_score: int) -> Optional[dict]:
    from google import genai  # pip install google-genai

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"{SYSTEM_PROMPT}\n\nmood_score: {mood_score}\njournal_text: {journal_text}",
        config={"response_mime_type": "application/json"},
    )
    return json.loads(resp.text)


def _call_mock(journal_text: str, mood_score: int) -> dict:
    """Deterministic stand-in so the app runs with no API key at all."""
    if mood_score <= 2:
        return {
            "risk_level": "MEDIUM",
            "sentiment_summary": "Student reports low mood and some stress in this entry.",
            "recommended_action": "Check in again within a few days; consider a light counselor touchpoint.",
            "flag_for_counselor": False,
            "coping_resources": GENERAL_RESOURCES,
        }
    return {
        "risk_level": "LOW",
        "sentiment_summary": "Student's entry reflects a generally stable emotional state.",
        "recommended_action": "No action needed; continue regular check-ins.",
        "flag_for_counselor": False,
        "coping_resources": GENERAL_RESOURCES,
    }


def analyze_with_llm(journal_text: str, mood_score: int) -> dict:
    """
    Main entry point used by the /api/analyze route.
    Always returns a dict matching the AnalysisResponse schema.
    """
    keyword_flagged = _keyword_screen(journal_text)

    try:
        if LLM_PROVIDER == "openai":
            result = _call_openai(journal_text, mood_score)
        elif LLM_PROVIDER == "gemini":
            result = _call_gemini(journal_text, mood_score)
        else:
            result = _call_mock(journal_text, mood_score)

        # Validate required keys exist; if not, treat as malformed.
        required = {"risk_level", "sentiment_summary", "recommended_action",
                    "flag_for_counselor", "coping_resources"}
        if not required.issubset(result.keys()):
            raise ValueError(f"LLM response missing keys: {required - result.keys()}")

    except Exception as e:
        logger.error(f"LLM call failed or returned malformed JSON: {e}")
        result = _safe_default(flagged=keyword_flagged)

    # Safety net overrides LLM output — never the other way around.
    if keyword_flagged:
        result["risk_level"] = "HIGH"
        result["flag_for_counselor"] = True
        # Make sure crisis resources are present even if the LLM didn't include them.
        existing_titles = {r.get("title") for r in result.get("coping_resources", [])}
        for res in CRISIS_RESOURCES:
            if res["title"] not in existing_titles:
                result.setdefault("coping_resources", []).append(res)

    return result
