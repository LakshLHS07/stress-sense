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
import re
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
        "url": "https://campus.edu/counseling",
    },
    {
        "title": "5-Minute Guided Breathing",
        "description": "A short box-breathing exercise to reduce acute stress and reset heart rate.",
        "url": "https://mindful.org/box-breathing",
    },
    {
        "title": "Academic Peer Support",
        "description": "Connect with trained peer advisors for workload balancing strategies.",
        "url": "https://campus.edu/peer-support",
    },
]

# Deliberately simple substring screen. Case-insensitive.
_HIGH_RISK_KEYWORDS = [
    "kill myself", "end my life", "end it all", "suicide", "suicidal",
    "want to die", "better off dead", "better off without me",
    "no reason to live", "can't go on", "hurt myself", "self harm",
    "self-harm", "cutting myself", "don't want to wake up",
    "give up on living", "giving up on life", "nothing matters anymore",
]

SYSTEM_PROMPT = """You are a triage assistant embedded in a student mental health check-in app.
You are NOT a therapist and you do not provide medical diagnoses. Your job is to read a student's short
journal entry and a 1-5 mood score, and output a structured risk assessment so campus counselors
can prioritize urgent follow-ups.

Respond with ONLY a single valid JSON object, no markdown fences, no conversational preamble.
Adhere strictly to this schema:
{
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "sentiment_summary": "<1-2 sentence neutral summary of emotional state>",
  "recommended_action": "<1 short sentence: clear immediate action for student or counselor>",
  "flag_for_counselor": true | false,
  "coping_resources": [{"title": "...", "description": "...", "url": "..."}]
}

Triage Criteria:
- HIGH risk: any indication of suicidal ideation, self-harm, hopeless despair, severe panic, or crisis.
  ALWAYS set flag_for_counselor=true for HIGH risk.
- MEDIUM risk: academic burnout, persistent anxiety, feeling overwhelmed, severe insomnia, social isolation.
- LOW risk: typical semester stress, normal study fatigue, or stable emotional state.
- Never diagnose. Maintain an empathetic, objective, and supportive clinical triage tone.
- Include 2-3 safe, practical coping resources."""


def _keyword_screen(journal_text: str) -> bool:
    text = journal_text.lower()
    return any(kw in text for kw in _HIGH_RISK_KEYWORDS)


def _safe_default(flagged: bool) -> dict:
    """Fail-safe fallback used whenever the LLM call fails or returns malformed JSON."""
    return {
        "risk_level": "MEDIUM" if not flagged else "HIGH",
        "sentiment_summary": "Automated AI analysis encountered a fallback condition.",
        "recommended_action": "Entry has been queued for standard counselor review.",
        "flag_for_counselor": True,  # Fail safe: always route to human review on failure
        "coping_resources": CRISIS_RESOURCES if flagged else GENERAL_RESOURCES,
    }


def _parse_json(raw_text: str) -> dict:
    """Extract and parse JSON safely, stripping any markdown wrappers or preamble."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def _call_openai(journal_text: str, mood_score: int) -> Optional[dict]:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=8.0)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"mood_score: {mood_score}\njournal_text: {journal_text}"},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    content = resp.choices[0].message.content or "{}"
    return _parse_json(content)


def _call_gemini(journal_text: str, mood_score: int) -> Optional[dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"mood_score: {mood_score}\njournal_text: {journal_text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=600,
        ),
    )
    return _parse_json(resp.text)


def _call_claude(journal_text: str, mood_score: int) -> Optional[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=8.0)
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=600,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"mood_score: {mood_score}\njournal_text: {journal_text}"}
        ],
    )
    raw_text = message.content[0].text
    return _parse_json(raw_text)


def _call_mock(journal_text: str, mood_score: int) -> dict:
    """Deterministic stand-in so the app runs with zero API keys during demos."""
    if mood_score <= 1:
        return {
            "risk_level": "HIGH",
            "sentiment_summary": "Student expresses severe acute distress, extreme exhaustion, or hopelessness.",
            "recommended_action": "Immediate counselor outreach recommended within 24 hours.",
            "flag_for_counselor": True,
            "coping_resources": CRISIS_RESOURCES,
        }
    elif mood_score <= 2:
        return {
            "risk_level": "MEDIUM",
            "sentiment_summary": "Student reports low mood and noticeable academic stress or burnout.",
            "recommended_action": "Check in again within a few days; suggest attending campus peer support.",
            "flag_for_counselor": False,
            "coping_resources": GENERAL_RESOURCES,
        }
    return {
        "risk_level": "LOW",
        "sentiment_summary": "Student's entry reflects normal semester workload and stable coping mechanisms.",
        "recommended_action": "No clinical action needed; continue regular daily check-ins.",
        "flag_for_counselor": False,
        "coping_resources": GENERAL_RESOURCES,
    }


def analyze_with_llm(journal_text: str, mood_score: int) -> dict:
    """
    Main entry point used by the /api/analyze route.
    Guarantees returning a dictionary matching the AnalysisResponse schema.
    """
    keyword_flagged = _keyword_screen(journal_text)

    try:
        provider = LLM_PROVIDER
        if provider == "openai":
            result = _call_openai(journal_text, mood_score)
        elif provider in ("gemini", "google"):
            result = _call_gemini(journal_text, mood_score)
        elif provider in ("claude", "anthropic"):
            result = _call_claude(journal_text, mood_score)
        else:
            result = _call_mock(journal_text, mood_score)

        # Validate that required keys exist
        required = {
            "risk_level", "sentiment_summary", "recommended_action",
            "flag_for_counselor", "coping_resources"
        }
        if not result or not required.issubset(result.keys()):
            raise ValueError(f"LLM response missing keys: {required - (result.keys() if result else set())}")

    except Exception as e:
        logger.error(f"LLM call failed or returned invalid JSON: {e}")
        result = _safe_default(flagged=keyword_flagged)

    # Safety net overrides: keyword alerts always elevate to HIGH risk and flag counselor
    if keyword_flagged:
        result["risk_level"] = "HIGH"
        result["flag_for_counselor"] = True
        # Ensure static, verified crisis hotline resources are appended
        existing_titles = {r.get("title") for r in result.get("coping_resources", [])}
        for res in CRISIS_RESOURCES:
            if res["title"] not in existing_titles:
                result.setdefault("coping_resources", []).append(res)

    return result

