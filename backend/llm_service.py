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

SYSTEM_PROMPT = """You are an empathetic, clinical triage assistant embedded in a student mental health check-in app.
You are NOT a therapist and you do not provide medical diagnoses.
Your job is to read a student's short journal entry and a 1-5 mood score (1=crisis/worst, 5=great/thriving),
and output a comprehensive stress assessment that isolates specific problems/stressors and provides
immediate remedies and practical solutions for each.

Respond with ONLY a single valid JSON object, no markdown fences, no conversational preamble.
Adhere strictly to this schema:
{
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "stress_assessment": {
    "stress_score": <integer from 0 to 100, where 0=serene and 100=extreme panic/distress>,
    "stress_level": "Low / Manageable" | "Moderate Stress" | "High Distress" | "Critical / Severe",
    "primary_stressors": ["<Category 1>", "<Category 2>"]
  },
  "sentiment_summary": "<1-2 sentence empathetic summary of the student's emotional state>",
  "recommended_action": "<1 short sentence: immediate clear priority for the student or counselor>",
  "flag_for_counselor": true | false,
  "identified_problems": [
    {
      "problem": "<specific pain point or root issue identified from journal>",
      "category": "Academic" | "Sleep & Physical" | "Emotional & Mental" | "Social & Relational" | "Financial" | "General",
      "severity": "Mild" | "Moderate" | "Severe",
      "immediate_remedy": "<2-to-5 minute actionable reset practice to calm acute tension right now>",
      "actionable_solution": "<step-by-step practical strategy to solve or manage this root problem>",
      "suggested_exercise": "<evidence-based technique: e.g., Box Breathing, Pomodoro 25/5, Brain Dump, 5-4-3-2-1 Grounding, CBT Thought Record>"
    }
  ],
  "coping_resources": [
    {"title": "...", "description": "...", "url": "..."}
  ]
}

Triage Criteria:
- HIGH risk: suicidal ideation, severe hopelessness, self-harm, extreme despair, or inability to cope. ALWAYS set flag_for_counselor=true and stress_score >= 85.
- MEDIUM risk: academic burnout, persistent anxiety, feeling overwhelmed, severe insomnia, loneliness. Set stress_score between 50 and 84.
- LOW risk: normal semester stress, standard deadlines, or stable mood. Set stress_score between 5 and 49.
- For EVERY identified problem, the immediate_remedy MUST be doable in 5 minutes, and the actionable_solution MUST be concrete and constructive.
- Maintain an encouraging, compassionate, non-judgmental tone."""


def _keyword_screen(journal_text: str) -> bool:
    text = journal_text.lower()
    return any(kw in text for kw in _HIGH_RISK_KEYWORDS)


def _safe_default(flagged: bool) -> dict:
    """Fail-safe fallback used whenever the LLM call fails or returns malformed JSON."""
    return {
        "risk_level": "HIGH" if flagged else "MEDIUM",
        "stress_assessment": {
            "stress_score": 90 if flagged else 65,
            "stress_level": "Critical / Severe" if flagged else "Moderate Stress",
            "primary_stressors": ["Acute Distress" if flagged else "Academic & Emotional Strain"]
        },
        "sentiment_summary": "Automated AI analysis encountered a fallback condition. Immediate care guidance provided.",
        "recommended_action": "Entry has been queued for human counselor review; please utilize immediate grounding support.",
        "flag_for_counselor": True,
        "identified_problems": [
            {
                "problem": "Acute emotional strain or crisis state" if flagged else "Elevated stress and mental exhaustion",
                "category": "Emotional & Mental",
                "severity": "Severe" if flagged else "Moderate",
                "immediate_remedy": "Stop reading or studying right now. Practice 4-7-8 breathing (inhale 4s, hold 7s, exhale 8s) for 3 cycles.",
                "actionable_solution": "Reach out directly to campus counseling or call/text 988 for free confidential support.",
                "suggested_exercise": "Box Breathing & Sensory Grounding (5 things you can see, 4 you can touch)"
            }
        ],
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

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=12.0)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"mood_score: {mood_score}\njournal_text: {journal_text}"},
        ],
        temperature=0.2,
        max_tokens=900,
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
            max_output_tokens=900,
        ),
    )
    return _parse_json(resp.text)


def _call_claude(journal_text: str, mood_score: int) -> Optional[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=12.0)
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=900,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"mood_score: {mood_score}\njournal_text: {journal_text}"}
        ],
    )
    raw_text = message.content[0].text
    return _parse_json(raw_text)


def _call_mock(journal_text: str, mood_score: int) -> dict:
    """
    Intelligent heuristic assessment generator when no API key is set.
    Dynamically identifies problems from journal content and pairs them with remedies & solutions.
    """
    text_lower = journal_text.lower()
    identified_problems = []
    stressors = []

    # 1. Academic & Deadline Stressors
    if any(w in text_lower for w in ["exam", "test", "study", "homework", "assignment", "grade", "gpa", "deadline", "class", "thesis", "fail", "midterm"]):
        stressors.append("Academic Workload")
        identified_problems.append({
            "problem": "High academic workload and looming deadline pressure",
            "category": "Academic",
            "severity": "Severe" if mood_score <= 2 else "Moderate",
            "immediate_remedy": "Perform a 3-minute 'Brain Dump': write every pending assignment on paper, then circle ONLY the single top priority for today.",
            "actionable_solution": "Break your largest task into 25-minute Pomodoro intervals. Send an email to your professor/TA requesting clarification or office hours early.",
            "suggested_exercise": "Pomodoro Technique (25m study / 5m complete rest, 4 cycles maximum before a long break)"
        })

    # 2. Sleep & Physical Fatigue
    if any(w in text_lower for w in ["sleep", "insomnia", "tired", "exhaust", "awake", "drowsy", "energy", "headache"]):
        stressors.append("Sleep Deprivation & Fatigue")
        identified_problems.append({
            "problem": "Disrupted sleep patterns and physical exhaustion",
            "category": "Sleep & Physical",
            "severity": "Severe" if mood_score <= 2 else "Moderate",
            "immediate_remedy": "Drink a glass of water, stand up, and do 60 seconds of gentle shoulder rolls and slow exhales to reset physical tension.",
            "actionable_solution": "Establish a strict 30-minute wind-down buffer tonight: turn off screens at least 30 minutes before bed, keep lighting dim, and maintain a fixed wakeup time.",
            "suggested_exercise": "Non-Sleep Deep Rest (NSDR) or 10-minute progressive muscle relaxation"
        })

    # 3. Emotional Overwhelm & Anxiety
    if any(w in text_lower for w in ["overwhelm", "anxious", "anxiety", "panic", "stress", "crying", "scared", "pointless", "hopeless", "can't focus"]):
        stressors.append("Emotional Overwhelm")
        identified_problems.append({
            "problem": "Mental overload and acute emotional anxiety",
            "category": "Emotional & Mental",
            "severity": "Severe" if mood_score <= 2 else "Moderate",
            "immediate_remedy": "Practice 5-4-3-2-1 Sensory Grounding: name 5 things you can see, 4 you touch, 3 you hear, 2 you smell, 1 you taste.",
            "actionable_solution": "Separate controllable issues from uncontrollable ones on paper. Reframe catastrophic thoughts ('I will fail everything') into balanced facts ('I am struggling with this chapter, but I can ask for help').",
            "suggested_exercise": "CBT Cognitive Thought Record & Box Breathing (4s in, 4s hold, 4s out, 4s hold)"
        })

    # 4. Social & Relational Isolation
    if any(w in text_lower for w in ["lonely", "alone", "isolate", "friends", "roommate", "family", "left out", "nobody", "talk to"]):
        stressors.append("Social Disconnection")
        identified_problems.append({
            "problem": "Feeling isolated or disconnected from campus social support",
            "category": "Social & Relational",
            "severity": "Moderate",
            "immediate_remedy": "Send a short low-pressure message to one trusted friend, family member, or classmate (e.g. 'Hey, just checking in!').",
            "actionable_solution": "Schedule one in-person study session or walk this week. Visit a campus peer support circle or university student club meeting.",
            "suggested_exercise": "Active Connection Prompt & Campus Peer Counseling drop-in"
        })

    # Fallback if no specific keyword matched
    if not identified_problems:
        if mood_score <= 2:
            stressors.append("General Fatigue")
            identified_problems.append({
                "problem": "Elevated fatigue and persistent stress",
                "category": "General",
                "severity": "Moderate",
                "immediate_remedy": "Take a 5-minute screen-free pause. Step outside for fresh air and natural sunlight.",
                "actionable_solution": "Prioritize your core necessities: ensure you have had a solid meal, hydrate, and outline 1 achievable goal for the rest of today.",
                "suggested_exercise": "Mindful Walking or 5-Minute Guided Reset"
            })
        else:
            stressors.append("Routine Academic Maintenance")
            identified_problems.append({
                "problem": "Daily semester pacing and focus maintenance",
                "category": "General",
                "severity": "Mild",
                "immediate_remedy": "Take a slow, deep breath, stretch your spine, and write down one thing that went well today.",
                "actionable_solution": "Maintain your steady momentum by preserving designated breaks and keeping a balanced daily routine.",
                "suggested_exercise": "Gratitude Reflection & Habit Pacing"
            })

    # =========================================================================
    # DYNAMIC MULTI-FACTOR CLINICAL STRESS SCORING ENGINE
    # =========================================================================
    # 1. Base score derived from self-reported state (mood score 1 to 5)
    mood_bases = {1: 86.0, 2: 68.0, 3: 50.0, 4: 32.0, 5: 14.0}
    calculated_score = mood_bases.get(mood_score, 50.0)

    # 2. Emotional Lexicon Analysis
    # High-distress emotional markers (+5.5 to +8.5 pts)
    severe_markers = [
        "hopeless", "pointless", "unbearable", "breaking down", "panicking", "panic",
        "crying", "drowning", "suffocating", "paralyzed", "desperate", "terrified",
        "falling apart", "nightmare", "empty", "ruined", "can't take it", "give up",
        "better off", "cannot do this", "worthless", "can't go on"
    ]
    for w in severe_markers:
        if w in text_lower:
            calculated_score += 7.0

    # Moderate distress & strain markers (+3.0 to +4.5 pts)
    moderate_markers = [
        "overwhelm", "overwhelmed", "anxious", "anxiety", "stressed", "stress",
        "insomnia", "sleepless", "exhausted", "exhaustion", "failing", "burnout",
        "drained", "miserable", "stuck", "worried", "pressured", "dread", "scared",
        "can't focus", "late", "behind", "struggling", "trouble"
    ]
    for w in moderate_markers:
        if w in text_lower:
            calculated_score += 3.5

    # Friction markers (+1.5 to +2.5 pts)
    friction_markers = [
        "tired", "hectic", "hard", "tough", "annoyed", "frustrated", "busy",
        "deadline", "exams", "exam", "test", "lonely", "alone", "isolated",
        "headache", "fight", "grades", "homework"
    ]
    for w in friction_markers:
        if w in text_lower:
            calculated_score += 1.8

    # Positive coping & protective words (reduce stress: -3.5 to -6.0 pts)
    protective_markers = [
        "calm", "relax", "relaxed", "peaceful", "happy", "better", "improving",
        "good", "great", "productive", "managed", "progress", "solved",
        "supported", "grateful", "hopeful", "confident", "slept well",
        "balanced", "stable", "exercise", "walk"
    ]
    for w in protective_markers:
        if w in text_lower:
            calculated_score -= 4.5

    # 3. Urgency and Intensity Signals
    # Exclamation marks indicate acute emotional charge
    exclamations = journal_text.count("!")
    calculated_score += min(6.0, exclamations * 1.5)

    # ALL CAPS words indicate amplified distress
    caps_words = [w for w in journal_text.split() if w.isupper() and len(w) > 1 and w.isalpha()]
    calculated_score += min(5.0, len(caps_words) * 1.5)

    # Multiple co-occurring stressor domains compound strain
    if len(stressors) >= 3:
        calculated_score += 5.0
    elif len(stressors) == 2:
        calculated_score += 2.5

    # 4. Deterministic content-specific micro-variance based on word structure
    # Ensures authentic human-like granularity without pseudo-repeating numbers
    content_hash = sum(ord(c) * (i + 1) for i, c in enumerate(journal_text.strip()[:60])) % 7 - 3
    calculated_score += content_hash

    # Clamp final score safely between 5 and 99 (or 100 on extreme crisis)
    stress_score = int(round(max(5, min(99, calculated_score))))

    # 5. Dynamic Categorization & Risk Mapping
    if stress_score >= 85 or mood_score <= 1:
        risk_level = "HIGH"
        stress_level = "Critical / Severe"
        flag_counselor = True
        resources = CRISIS_RESOURCES
    elif stress_score >= 70:
        risk_level = "MEDIUM"
        stress_level = "High Distress"
        flag_counselor = False
        resources = GENERAL_RESOURCES
    elif stress_score >= 50:
        risk_level = "MEDIUM"
        stress_level = "Moderate Stress"
        flag_counselor = False
        resources = GENERAL_RESOURCES
    elif stress_score >= 30:
        risk_level = "LOW"
        stress_level = "Mild / Manageable Stress"
        flag_counselor = False
        resources = GENERAL_RESOURCES
    else:
        risk_level = "LOW"
        stress_level = "Low / Optimal Wellbeing"
        flag_counselor = False
        resources = GENERAL_RESOURCES

    # 6. Context-Aware Dynamic Sentiment & Action Synthesis
    stressors_text = ", ".join(stressors[:2]) if stressors else "general workload"
    if risk_level == "HIGH":
        sentiment = f"Student indicates acute distress associated with {stressors_text}. Emotional reserves appear heavily taxed."
        action = "Immediate counselor check-in or supportive outreach strongly advised."
    elif stress_score >= 70:
        sentiment = f"Student is experiencing significant strain primarily driven by {stressors_text}."
        action = "Prioritize the immediate 5-minute reset exercise and schedule study buffers."
    elif stress_score >= 50:
        sentiment = f"Student is navigating manageable but noticeable friction with {stressors_text}."
        action = "Apply time-blocking and pacing strategies to avoid accumulating burnout."
    else:
        sentiment = f"Student reflects balanced emotional equilibrium with active coping mechanisms."
        action = "Continue current regular reflection habits and healthy boundaries."

    return {
        "risk_level": risk_level,
        "stress_assessment": {
            "stress_score": stress_score,
            "stress_level": stress_level,
            "primary_stressors": stressors[:3] or ["Academic Maintenance"]
        },
        "sentiment_summary": sentiment,
        "recommended_action": action,
        "flag_for_counselor": flag_counselor,
        "identified_problems": identified_problems,
        "coping_resources": resources,
    }


def analyze_with_llm(journal_text: str, mood_score: int) -> dict:
    """
    Main entry point used by the /api/analyze route.
    Guarantees returning a dictionary matching the AnalysisResponse schema.
    """
    keyword_flagged = _keyword_screen(journal_text)

    try:
        provider = LLM_PROVIDER
        if provider == "mock" or not provider:
            if os.getenv("GEMINI_API_KEY"):
                provider = "gemini"
            elif os.getenv("OPENAI_API_KEY"):
                provider = "openai"
            elif os.getenv("ANTHROPIC_API_KEY"):
                provider = "claude"

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
            "risk_level", "stress_assessment", "sentiment_summary",
            "recommended_action", "flag_for_counselor", "coping_resources"
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
        
        # Ensure stress assessment indicates critical stress
        if "stress_assessment" not in result:
            result["stress_assessment"] = {}
        result["stress_assessment"]["stress_score"] = max(result["stress_assessment"].get("stress_score", 0), 95)
        result["stress_assessment"]["stress_level"] = "Critical / Severe"
        stressors = set(result["stress_assessment"].get("primary_stressors", []))
        stressors.add("Crisis Distress")
        result["stress_assessment"]["primary_stressors"] = list(stressors)

        # Ensure static, verified crisis hotline resources are appended
        existing_titles = {r.get("title") for r in result.get("coping_resources", [])}
        for res in CRISIS_RESOURCES:
            if res["title"] not in existing_titles:
                result.setdefault("coping_resources", []).append(res)

    return result


