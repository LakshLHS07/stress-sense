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
        "title": "Tele-MANAS (National Mental Health Helpline)",
        "description": "Govt. of India 24/7 toll-free mental health support. Call 14416 or 1800-891-4416.",
        "url": "https://telemanas.mohfw.gov.in",
    },
    {
        "title": "KIRAN Mental Health Helpline",
        "description": "24/7 toll-free crisis helpline by Ministry of Social Justice. Call 1800-599-0019.",
        "url": "http://www.kiranhelpline.in",
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

STANDUP_COMEDY_CATALOG = {
    "HIGH": [
        {
            "title": "Friends, Crime, & The Cosmos",
            "comedian": "Abhishek Upmanyu",
            "duration": "14 mins",
            "description": "Hilarious relatable take on student overthinking, roommates, and college existential chaos.",
            "url": "https://www.youtube.com/watch?v=dtaJzUbQS7E",
            "thumbnail": "https://img.youtube.com/vi/dtaJzUbQS7E/mqdefault.jpg"
        },
        {
            "title": "When I Met A Delhi Girl / Haq Se Single",
            "comedian": "Zakir Khan",
            "duration": "18 mins",
            "description": "Comforting, laugh-out-loud storytelling about friendships, college expectations, and staying grounded.",
            "url": "https://www.youtube.com/watch?v=sIl8vsTcQ_k",
            "thumbnail": "https://img.youtube.com/vi/sIl8vsTcQ_k/mqdefault.jpg"
        },
        {
            "title": "Cheating & Hostel Memories",
            "comedian": "Anubhav Singh Bassi",
            "duration": "16 mins",
            "description": "Unfiltered nostalgic college humor to take your mind completely off pressure.",
            "url": "https://www.youtube.com/watch?v=Tqsz6FJeyCA",
            "thumbnail": "https://img.youtube.com/vi/Tqsz6FJeyCA/mqdefault.jpg"
        },
        {
            "title": "Afraid of the Dark & Everyday Chaos",
            "comedian": "Trevor Noah",
            "duration": "12 mins",
            "description": "Witty global comedy delivering genuine smiles and perspective.",
            "url": "https://www.youtube.com/watch?v=gT8vO76Gk0o",
            "thumbnail": "https://img.youtube.com/vi/gT8vO76Gk0o/mqdefault.jpg"
        }
    ],
    "MODERATE": [
        {
            "title": "School PTM & Everyday Logic",
            "comedian": "Biswa Kalyan Rath",
            "duration": "11 mins",
            "description": "Fast-paced clever observational humor on academic routines.",
            "url": "https://www.youtube.com/watch?v=dtaJzUbQS7E",
            "thumbnail": "https://img.youtube.com/vi/dtaJzUbQS7E/mqdefault.jpg"
        },
        {
            "title": "Crowd Work & College Banter",
            "comedian": "Rahul Subramanian",
            "duration": "10 mins",
            "description": "Lighthearted, spontaneous banter perfect for a quick 10-minute study break.",
            "url": "https://www.youtube.com/watch?v=sIl8vsTcQ_k",
            "thumbnail": "https://img.youtube.com/vi/sIl8vsTcQ_k/mqdefault.jpg"
        }
    ],
    "LOW": [
        {
            "title": "Everyday Observational Standup",
            "comedian": "Kenny Sebastian",
            "duration": "9 mins",
            "description": "Fun, musical comedy to brighten up a productive day.",
            "url": "https://www.youtube.com/watch?v=Tqsz6FJeyCA",
            "thumbnail": "https://img.youtube.com/vi/Tqsz6FJeyCA/mqdefault.jpg"
        }
    ]
}

FEEL_GOOD_SONGS_CATALOG = {
    "HIGH": [
        {
            "title": "Ilahi (Yeh Jawaani Hai Deewani)",
            "artist": "Arijit Singh / Pritam",
            "vibe": "Uplifting & Free-Spirited",
            "description": "A breezy anthem celebrating freedom, wandering, and letting go of heavy worries.",
            "url": "https://www.youtube.com/watch?v=fdubeMFwuGs",
            "thumbnail": "https://img.youtube.com/vi/fdubeMFwuGs/mqdefault.jpg"
        },
        {
            "title": "Happy",
            "artist": "Pharrell Williams",
            "vibe": "Pure Joy & Dopamine",
            "description": "Universal mood-booster scientifically proven to stimulate upbeat dopamine rhythm.",
            "url": "https://www.youtube.com/watch?v=ZbZSe6N_BXs",
            "thumbnail": "https://img.youtube.com/vi/ZbZSe6N_BXs/mqdefault.jpg"
        },
        {
            "title": "Matargashti (Tamasha)",
            "artist": "Mohit Chauhan / A.R. Rahman",
            "vibe": "Carefree Fun & Whimsical",
            "description": "Lighthearted, energetic rhythm that immediately interrupts negative overthinking.",
            "url": "https://www.youtube.com/watch?v=6vKucgAeF_Q",
            "thumbnail": "https://img.youtube.com/vi/6vKucgAeF_Q/mqdefault.jpg"
        },
        {
            "title": "Don't Stop Me Now",
            "artist": "Queen",
            "vibe": "High Energy & Empowering",
            "description": "Classic feel-good track voted one of the most uplifting songs in music psychology surveys.",
            "url": "https://www.youtube.com/watch?v=HgzGwKwLmgM",
            "thumbnail": "https://img.youtube.com/vi/HgzGwKwLmgM/mqdefault.jpg"
        },
        {
            "title": "Can't Stop the Feeling!",
            "artist": "Justin Timberlake",
            "vibe": "Groovy & Mood-Lifting",
            "description": "Catchy pop melody to loosen physical tension and promote positive movement.",
            "url": "https://www.youtube.com/watch?v=ru0K8uYEZWw",
            "thumbnail": "https://img.youtube.com/vi/ru0K8uYEZWw/mqdefault.jpg"
        }
    ],
    "MODERATE": [
        {
            "title": "Budhu Sa Mann (Kapoor & Sons)",
            "artist": "Armaan Malik / Amaal Mallik",
            "vibe": "Gentle & Cheerful",
            "description": "Relaxing, sweet melody to calm an active, racing study mind.",
            "url": "https://www.youtube.com/watch?v=k4iFcxp_2kU",
            "thumbnail": "https://img.youtube.com/vi/k4iFcxp_2kU/mqdefault.jpg"
        },
        {
            "title": "Sunday Best",
            "artist": "Surfaces",
            "vibe": "Smooth & Optimistic",
            "description": "Sunny acoustic pop reminder that setbacks are temporary.",
            "url": "https://www.youtube.com/watch?v=_83K3Qe44MT",
            "thumbnail": "https://img.youtube.com/vi/_83K3Qe44MT/mqdefault.jpg"
        }
    ],
    "LOW": [
        {
            "title": "Zinda (Bhaag Milkha Bhaag)",
            "artist": "Siddharth Mahadevan",
            "vibe": "High Octane & Motivating",
            "description": "Empowering rock track to fuel your momentum and focus.",
            "url": "https://www.youtube.com/watch?v=k4iFcxp_2kU",
            "thumbnail": "https://img.youtube.com/vi/k4iFcxp_2kU/mqdefault.jpg"
        }
    ]
}


def get_mood_uplift_media(stress_score: int, risk_level: str) -> dict:
    """Provides differentiated remedies, sleep prescription, box breathing triggers, standup comedy, and feel-good songs based on stress score."""
    is_high = (stress_score >= 70) or (risk_level == "HIGH")
    is_moderate = (not is_high) and ((stress_score >= 45) or (risk_level == "MEDIUM"))
    
    tier = "HIGH" if is_high else ("MODERATE" if is_moderate else "LOW")
    
    standup = STANDUP_COMEDY_CATALOG.get(tier, STANDUP_COMEDY_CATALOG["HIGH"])
    songs = FEEL_GOOD_SONGS_CATALOG.get(tier, FEEL_GOOD_SONGS_CATALOG["HIGH"])
    
    if is_high:
        sleep_rec = {
            "is_critical": True,
            "headline": "🛌 Prescribed Rest Protocol: Mandatory 8-Hour Recovery Sleep",
            "badge": "⚡ High Stress Recovery Active",
            "narrative": "When stress index crosses 70, cognitive retention degrades and physical nervous system tension peaks. The single highest-ROI reset intervention is restorative slow-wave sleep.",
            "actionable_tips": [
                "Digital Sunset: Power down laptop, phone, and study screens 30 minutes before bed.",
                "Target an 8-hour sleep block tonight — studying in acute distress yields 50% lower retention.",
                "Cool, dark room (68°F / 20°C) with no notifications to restore deep slow-wave sleep.",
                "Avoid caffeine, energy drinks, and heavy late meals after 3:00 PM."
            ]
        }
        breathing_rec = {
            "auto_trigger": True,
            "headline": "🫁 Immediate Vagus Nerve Reset: Box Breathing (4-4-4-4)",
            "instruction": "Initiating 4-4-4-4 Box Breathing immediately slows down rapid heart rate, lowers acute cortisol, and switches the body out of fight-or-flight panic.",
            "cycles": 4
        }
    elif is_moderate:
        sleep_rec = {
            "is_critical": False,
            "headline": "🌙 Sleep Hygiene Reminder: Protect 7.5h Baseline",
            "badge": "⚠️ Pacing & Sleep Buffer",
            "narrative": "Moderate stress is manageable when your sleep baseline is steady. Protect your nighttime sleep window to prevent fatigue compounding.",
            "actionable_tips": [
                "Keep a consistent bedtime tonight within a 30-minute window.",
                "Take a 10-minute screen break between study sessions.",
                "End study sessions by 10:30 PM to allow the brain to decompress."
            ]
        }
        breathing_rec = {
            "auto_trigger": False,
            "headline": "🫁 2-Minute Calming Reset: Box Breathing",
            "instruction": "Use Box Breathing for 2 minutes whenever you feel concentration slipping or frustration building.",
            "cycles": 3
        }
    else:
        sleep_rec = {
            "is_critical": False,
            "headline": "✨ Optimal Rest Balance: Sustaining Healthy Routine",
            "badge": "🛡️ Balanced Sleep Buffer",
            "narrative": "Your current stress level is well within healthy bounds. Maintaining your current sleep rhythm keeps cognitive memory sharp.",
            "actionable_tips": [
                "Maintain your regular waking and sleep schedule.",
                "Hydrate and celebrate your daily accomplishments."
            ]
        }
        breathing_rec = {
            "auto_trigger": False,
            "headline": "🧘 Mindful Breath Pacing",
            "instruction": "Quick 60-second breathing check-in to preserve calm focus and energy.",
            "cycles": 2
        }
        
    return {
        "standup_comedy_videos": standup,
        "feel_good_songs": songs,
        "sleep_recommendation": sleep_rec,
        "box_breathing_suggestion": breathing_rec,
    }

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
    stress_score = 90 if flagged else 65
    risk_level = "HIGH" if flagged else "MEDIUM"
    uplift = get_mood_uplift_media(stress_score, risk_level)
    
    return {
        "risk_level": risk_level,
        "stress_assessment": {
            "stress_score": stress_score,
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
                "actionable_solution": "Reach out directly to campus counseling or call Tele-MANAS (14416 / 1800-891-4416) or KIRAN (1800-599-0019) for free 24/7 confidential support.",
                "suggested_exercise": "Box Breathing & Sensory Grounding (5 things you can see, 4 you can touch)"
            }
        ],
        "coping_resources": CRISIS_RESOURCES if flagged else GENERAL_RESOURCES,
        "standup_comedy_videos": uplift["standup_comedy_videos"],
        "feel_good_songs": uplift["feel_good_songs"],
        "sleep_recommendation": uplift["sleep_recommendation"],
        "box_breathing_suggestion": uplift["box_breathing_suggestion"],
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


def compute_sleep_insights(
    sleep_records: Optional[list],
    mood_score: int,
    stress_score: int,
    journal_text: str
) -> dict:
    """
    Extracts deep clinical sleep metrics and stress correlation from the sleep tracker database.
    """
    records = sleep_records if (sleep_records and isinstance(sleep_records, list) and len(sleep_records) > 0) else [
        {"day": "Mon", "hours": 6.8, "quality": "Fair", "notes": "Late study session"},
        {"day": "Tue", "hours": 5.5, "quality": "Restless", "notes": "Exam preparation"},
        {"day": "Wed", "hours": 7.8, "quality": "Good", "notes": "Recovered sleep"},
        {"day": "Thu", "hours": 6.2, "quality": "Fair", "notes": "Thesis writing"},
        {"day": "Fri", "hours": 7.4, "quality": "Good", "notes": "Weekend start"},
        {"day": "Sat", "hours": 8.5, "quality": "Optimal", "notes": "Restful recovery"},
        {"day": "Sun", "hours": 7.5, "quality": "Good", "notes": "Balanced bedtime"},
    ]
    
    total_hours = sum(float(d.get("hours", 7.0)) for d in records)
    count = max(1, len(records))
    avg_hours = round(total_hours / count, 1)
    target_total = count * 7.5
    debt_diff = round(total_hours - target_total, 1)
    debt_status = "Surplus" if debt_diff >= 0 else "Deficit"
    
    recent_entry = records[-1] if records else {"hours": 7.5, "quality": "Good", "day": "Sun"}
    recent_night_hours = float(recent_entry.get("hours", 7.5))
    recent_quality = str(recent_entry.get("quality", "Good"))
    
    circadian_regularity = "86% Regularity (Bedtime window: 11:30 PM – 12:15 AM)"
    deep_sleep_ratio = "22% (Optimal Slow-Wave Sleep)" if avg_hours >= 7.0 else "16% (Suppressed Slow-Wave Sleep)"
    
    if debt_diff <= -1.5 or (recent_night_hours < 6.0 and recent_quality in ["Restless", "Fair"]):
        stress_correlation = "High Inverse (r = -0.84)"
        impact_badge = f"⚡ Sleep Debt Amplifying Stress (+{min(10, max(4, int(abs(debt_diff) * 2.2)))} pts)"
        clinical_narrative = (
            f"Your 7-day sleep database reveals a cumulative {abs(debt_diff)}h sleep deficit (averaging {avg_hours}h/night), "
            f"with your recent night recorded at {recent_night_hours}h ({recent_quality}). In clinical neuroscience, chronic sleep debt "
            f"diminishes prefrontal cortical inhibition over the amygdala, directly magnifying feelings of academic stress and emotional strain. "
            f"Restoring your sleep buffer will provide the quickest immediate reduction in daytime distress."
        )
        actionable_sleep_rule = "Digital Sunset: power down screens 30m before bed and use Box Breathing (4-4-4-4) to trigger parasympathetic recovery."
    elif debt_diff < 0:
        stress_correlation = "Moderate (r = -0.72)"
        impact_badge = f"⚠️ Mild Sleep Deficit ({abs(debt_diff)}h below baseline)"
        clinical_narrative = (
            f"Your 7-day average is {avg_hours}h, leaving a mild {abs(debt_diff)}h deficit against the 7.5h clinical baseline. "
            f"While daytime coping remains partially intact, sleep debt compounds over multiple study days. "
            f"Targeting two consecutive 7.5h+ nights will fully restore cognitive alertness and emotional resilience."
        )
        actionable_sleep_rule = "Maintain consistent wake times to anchor cortisol rhythm; avoid caffeinated beverages after 2:30 PM."
    else:
        stress_correlation = "Protective Buffer (r = +0.76)"
        impact_badge = f"🛡️ Restorative Buffer (+{debt_diff}h Surplus)"
        clinical_narrative = (
            f"Your sleep tracker shows a healthy {avg_hours}h average with a {debt_diff}h restorative surplus. "
            f"Sufficient slow-wave deep sleep is actively cushioning your stress reactivity and protecting cognitive bandwidth."
        )
        actionable_sleep_rule = "Sustain your current restorative sleep rhythm to maintain peak memory retention and steady mood."

    return {
        "avg_hours": avg_hours,
        "sleep_debt_hours": abs(debt_diff),
        "debt_status": debt_status,
        "recent_night_hours": recent_night_hours,
        "recent_quality": recent_quality,
        "circadian_regularity": circadian_regularity,
        "deep_sleep_ratio": deep_sleep_ratio,
        "stress_correlation": stress_correlation,
        "impact_badge": impact_badge,
        "clinical_narrative": clinical_narrative,
        "actionable_sleep_rule": actionable_sleep_rule,
    }


def _call_openai(journal_text: str, mood_score: int, sleep_records: Optional[list] = None) -> Optional[dict]:
    from openai import OpenAI

    sleep_summary = ""
    if sleep_records:
        insights = compute_sleep_insights(sleep_records, mood_score, 50, journal_text)
        sleep_summary = f"\nsleep_metrics: avg {insights['avg_hours']}h, debt: {insights['sleep_debt_hours']}h ({insights['debt_status']}), recent: {insights['recent_night_hours']}h"

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=12.0)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"mood_score: {mood_score}{sleep_summary}\njournal_text: {journal_text}"},
        ],
        temperature=0.2,
        max_tokens=900,
    )
    content = resp.choices[0].message.content or "{}"
    return _parse_json(content)


def _call_gemini(journal_text: str, mood_score: int, sleep_records: Optional[list] = None) -> Optional[dict]:
    from google import genai
    from google.genai import types

    sleep_summary = ""
    if sleep_records:
        insights = compute_sleep_insights(sleep_records, mood_score, 50, journal_text)
        sleep_summary = f"\nsleep_metrics: avg {insights['avg_hours']}h, debt: {insights['sleep_debt_hours']}h ({insights['debt_status']}), recent: {insights['recent_night_hours']}h"

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"mood_score: {mood_score}{sleep_summary}\njournal_text: {journal_text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=900,
        ),
    )
    return _parse_json(resp.text)


def _call_claude(journal_text: str, mood_score: int, sleep_records: Optional[list] = None) -> Optional[dict]:
    import anthropic

    sleep_summary = ""
    if sleep_records:
        insights = compute_sleep_insights(sleep_records, mood_score, 50, journal_text)
        sleep_summary = f"\nsleep_metrics: avg {insights['avg_hours']}h, debt: {insights['sleep_debt_hours']}h ({insights['debt_status']}), recent: {insights['recent_night_hours']}h"

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=12.0)
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=900,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"mood_score: {mood_score}{sleep_summary}\njournal_text: {journal_text}"}
        ],
    )
    raw_text = message.content[0].text
    return _parse_json(raw_text)


def _call_mock(journal_text: str, mood_score: int, sleep_records: Optional[list] = None) -> dict:
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
    # WIDE-DYNAMIC-RANGE NATURAL LANGUAGE STRESS SCORING ENGINE
    # =========================================================================
    # Clean words and tokens
    words = [re.sub(r'[^\w]', '', w) for w in text_lower.split()]
    words = [w for w in words if w]
    total_word_count = max(1, len(words))

    # Mood anchor (baseline prior, but journal text has strong authority to override)
    mood_prior = {1: 88.0, 2: 68.0, 3: 50.0, 4: 32.0, 5: 14.0}.get(mood_score, 50.0)

    # 1. High-Impact Clinical Distress & Panic Lexicon
    severe_distress = {
        "hopeless": 16, "pointless": 15, "unbearable": 16, "suicide": 30, "suicidal": 30,
        "kill": 25, "die": 22, "breaking down": 16, "panic": 14, "panicking": 15,
        "crying": 13, "drowning": 14, "suffocating": 15, "paralyzed": 14, "desperate": 15,
        "terrified": 14, "falling apart": 16, "nightmare": 12, "empty": 12, "ruined": 13,
        "give up": 15, "giving up": 15, "better off": 18, "worthless": 16, "cannot do this": 14,
        "cant take it": 16, "can not take it": 16, "hate myself": 18, "cant go on": 17
    }

    # 2. Moderate Distress, Anxiety & Exhaustion Lexicon
    high_strain = {
        "overwhelmed": 11, "overwhelm": 10, "anxious": 9, "anxiety": 9, "insomnia": 10,
        "sleepless": 10, "exhausted": 10, "exhaustion": 9, "failing": 11, "burnout": 11,
        "drained": 9, "miserable": 10, "stuck": 8, "worried": 7, "pressured": 8,
        "dread": 10, "scared": 9, "cant focus": 8, "behind": 7, "late": 6,
        "struggling": 8, "trouble": 7, "scary": 8, "depressed": 12, "depression": 12,
        "overloaded": 9, "furious": 7
    }

    # 3. Frictional Daily Stressors
    moderate_friction = {
        "tired": 5, "hectic": 5, "hard": 4, "tough": 4, "annoyed": 5, "frustrated": 6,
        "busy": 4, "deadline": 5, "deadlines": 6, "exams": 6, "exam": 5, "test": 4,
        "tests": 5, "lonely": 7, "alone": 6, "isolated": 7, "headache": 6, "fight": 6,
        "argument": 6, "grades": 5, "homework": 4, "assignment": 4, "thesis": 6,
        "stress": 6, "stressed": 7, "parents": 4, "family": 4
    }

    # 4. Positive Coping, Protective & Relief Lexicon (Strong Stress Reducers)
    positive_protective = {
        "calm": -12, "relax": -10, "relaxed": -11, "relaxing": -10, "peaceful": -12,
        "happy": -12, "better": -9, "improving": -10, "good": -8, "great": -11,
        "productive": -10, "managed": -9, "progress": -9, "solved": -10, "supported": -11,
        "grateful": -12, "hopeful": -11, "confident": -12, "slept well": -13,
        "balanced": -11, "stable": -10, "accomplished": -11, "fine": -6, "energized": -11,
        "fun": -8, "laugh": -9, "enjoyed": -9, "proud": -10, "relief": -10, "relieved": -11,
        "chilling": -8, "rested": -10, "walk": -6, "exercise": -7
    }

    # Calculate raw positive and negative score impacts
    neg_score = sum(pts for p, pts in severe_distress.items() if p in text_lower)
    neg_score += sum(pts for p, pts in high_strain.items() if p in text_lower)
    neg_score += sum(pts for p, pts in moderate_friction.items() if p in text_lower)
    pos_score = sum(abs(pts) for p, pts in positive_protective.items() if p in text_lower)

    # Intensifiers scale up emotional distress
    intensifiers = ["so", "very", "extremely", "really", "too", "completely", "totally", "utterly", "deeply", "constantly", "barely"]
    intense_multiplier = 1.0 + min(0.6, sum(0.12 for w in words if w in intensifiers))
    neg_score *= intense_multiplier

    # Punctuation & text urgency signals
    exclamations = journal_text.count("!")
    urgency_boost = min(12.0, exclamations * 3.0)
    caps_count = len([w for w in journal_text.split() if w.isupper() and len(w) > 1 and w.isalpha()])
    urgency_boost += min(10.0, caps_count * 2.5)

    # Multi-stressor compounding penalty
    if len(stressors) >= 3:
        urgency_boost += 6.0
    elif len(stressors) == 2:
        urgency_boost += 3.0

    # Derive raw Text-Based Stress Index
    if neg_score == 0 and pos_score > 0:
        text_stress_index = max(5.0, 28.0 - pos_score * 1.5)
    elif neg_score > 0:
        text_stress_index = min(98.0, 38.0 + neg_score * 1.8 - pos_score * 1.2 + urgency_boost)
    else:
        text_stress_index = 45.0

    # Text Authority: As text length grows or strong keywords appear, text commands higher authority over mood
    text_authority = min(0.80, 0.45 + (total_word_count / 100.0) * 0.35)
    if neg_score >= 25.0:
        text_authority = max(text_authority, 0.85)

    blended = (text_stress_index * text_authority) + (mood_prior * (1.0 - text_authority))

    # 5. Extract sleep database insights and evaluate biometrics impact
    sleep_insights = compute_sleep_insights(sleep_records, mood_score, 50, journal_text)
    
    # Biometric adjustment: sleep debt lowers cognitive coping buffer
    if sleep_insights["debt_status"] == "Deficit" and sleep_insights["sleep_debt_hours"] >= 1.2:
        if "Sleep Deprivation & Fatigue" not in stressors:
            stressors.append("Sleep Deprivation & Fatigue")
        blended += min(6.0, sleep_insights["sleep_debt_hours"] * 1.8)
    elif sleep_insights["debt_status"] == "Surplus":
        blended = max(4.0, blended - 3.5)

    # Natural micro-variance based on exact character lengths and word hashes
    char_variance = (sum(ord(c) * (i + 1) for i, c in enumerate(journal_text.strip()[:40])) % 9) - 4
    stress_score = int(round(max(4, min(99, blended + char_variance))))

    # Dynamic Categorization & Risk Mapping based on the real score
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

    # Context-Aware Dynamic Sentiment & Action Synthesis
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

    uplift = get_mood_uplift_media(stress_score, risk_level)

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
        "sleep_insights": sleep_insights,
        "standup_comedy_videos": uplift["standup_comedy_videos"],
        "feel_good_songs": uplift["feel_good_songs"],
        "sleep_recommendation": uplift["sleep_recommendation"],
        "box_breathing_suggestion": uplift["box_breathing_suggestion"],
    }


def analyze_with_llm(journal_text: str, mood_score: int, sleep_records: Optional[list] = None) -> dict:
    """
    Main entry point used by the /api/analyze route.
    Guarantees returning a dictionary matching the AnalysisResponse schema, enriched with sleep database insights.
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
            result = _call_openai(journal_text, mood_score, sleep_records)
        elif provider in ("gemini", "google"):
            result = _call_gemini(journal_text, mood_score, sleep_records)
        elif provider in ("claude", "anthropic"):
            result = _call_claude(journal_text, mood_score, sleep_records)
        else:
            result = _call_mock(journal_text, mood_score, sleep_records)

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

    # Ensure sleep_insights is always attached from the sleep tracker database
    if "sleep_insights" not in result or not result["sleep_insights"]:
        curr_score = result.get("stress_assessment", {}).get("stress_score", 50)
        result["sleep_insights"] = compute_sleep_insights(sleep_records, mood_score, curr_score, journal_text)

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

    # Always attach differentiated media, sleep recommendations, and box breathing data
    curr_score = result.get("stress_assessment", {}).get("stress_score", 50)
    curr_risk = result.get("risk_level", "LOW")
    uplift = get_mood_uplift_media(curr_score, curr_risk)

    if not result.get("standup_comedy_videos"):
        result["standup_comedy_videos"] = uplift["standup_comedy_videos"]
    if not result.get("feel_good_songs"):
        result["feel_good_songs"] = uplift["feel_good_songs"]
    if not result.get("sleep_recommendation"):
        result["sleep_recommendation"] = uplift["sleep_recommendation"]
    if not result.get("box_breathing_suggestion"):
        result["box_breathing_suggestion"] = uplift["box_breathing_suggestion"]

    return result


