import React, { useState, useEffect } from "react";

const API_BASE_URL = "http://localhost:8000";

const PRESETS = [
  {
    label: "🔥 Crisis / High Stress",
    mood: 1,
    text: "I haven't slept properly in days and I can't focus on anything. Everything feels pointless and I keep thinking everyone would be better off without me around.",
  },
  {
    label: "⚡ Midterm Burnout",
    mood: 2,
    text: "I have 3 exams back to back this week, my thesis draft is late, and I'm feeling completely overwhelmed and mentally exhausted.",
  },
  {
    label: "🌿 Balanced / Coping Well",
    mood: 4,
    text: "Had a productive day studying at the library. Went for a quick run and felt good about my progress on the machine learning assignment.",
  },
];

const MOOD_OPTIONS = [
  { score: 1, emoji: "😫", label: "Crisis", desc: "Severe distress" },
  { score: 2, emoji: "😔", label: "Low", desc: "Burnout / struggle" },
  { score: 3, emoji: "😐", label: "Neutral", desc: "Getting by" },
  { score: 4, emoji: "🙂", label: "Good", desc: "Coping well" },
  { score: 5, emoji: "✨", label: "Great", desc: "Thriving" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("checkin"); // "checkin" | "history" | "counselor"
  const [studentId, setStudentId] = useState("student_042");
  const [moodScore, setMoodScore] = useState(2);
  const [journalText, setJournalText] = useState("");
  
  // Analysis State
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Backend Health
  const [backendStatus, setBackendStatus] = useState("checking"); // "online" | "offline" | "checking"

  // History & Counselor Flags State
  const [historyData, setHistoryData] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [flaggedEntries, setFlaggedEntries] = useState([]);
  const [isLoadingFlags, setIsLoadingFlags] = useState(false);

  // Check backend health on mount
  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      setBackendStatus("checking");
      const res = await fetch(`${API_BASE_URL}/`, { method: "GET" });
      if (res.ok) {
        setBackendStatus("online");
      } else {
        setBackendStatus("offline");
      }
    } catch {
      setBackendStatus("offline");
    }
  };

  // Fetch History for active student
  const fetchHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/history/${encodeURIComponent(studentId)}`);
      if (res.ok) {
        const data = await res.json();
        setHistoryData(data);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Fetch Counselor Flagged Entries
  const fetchFlags = async () => {
    setIsLoadingFlags(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/counselor/flags`);
      if (res.ok) {
        const data = await res.json();
        setFlaggedEntries(data);
      }
    } catch (err) {
      console.error("Failed to load counselor flags:", err);
    } finally {
      setIsLoadingFlags(false);
    }
  };

  // Handle Tab Switch
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === "history") fetchHistory();
    if (tab === "counselor") fetchFlags();
  };

  // Submit Check-In to /api/analyze
  const handleAnalyze = async (e) => {
    e?.preventDefault();
    if (!journalText.trim()) {
      setErrorMsg("Please write a few words about your day before analyzing.");
      return;
    }

    setIsAnalyzing(true);
    setErrorMsg(null);

    const payload = {
      student_id: studentId.trim() || "anonymous_student",
      journal_text: journalText.trim(),
      mood_score: Number(moodScore),
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();
      setAnalysisResult(data);
      setBackendStatus("online");
    } catch (err) {
      setErrorMsg(`Could not connect to FastAPI server at ${API_BASE_URL}. Ensure uvicorn is running!`);
      setBackendStatus("offline");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const applyPreset = (preset) => {
    setMoodScore(preset.mood);
    setJournalText(preset.text);
    setErrorMsg(null);
  };

  // Risk styling helper
  const getRiskBadge = (level) => {
    switch (level) {
      case "HIGH":
        return {
          bg: "bg-rose-500/15 border-rose-500/30 text-rose-300",
          glow: "shadow-[0_0_20px_rgba(244,63,94,0.3)]",
          label: "HIGH RISK — Urgent Counselor Action Advised",
          pill: "bg-rose-500 text-white",
        };
      case "MEDIUM":
        return {
          bg: "bg-amber-500/15 border-amber-500/30 text-amber-300",
          glow: "shadow-[0_0_20px_rgba(245,158,11,0.25)]",
          label: "MEDIUM RISK — Elevated Stress / Burnout Detected",
          pill: "bg-amber-500 text-slate-950 font-bold",
        };
      default:
        return {
          bg: "bg-emerald-500/15 border-emerald-500/30 text-emerald-300",
          glow: "shadow-[0_0_20px_rgba(16,185,129,0.2)]",
          label: "LOW RISK — Emotionally Stable / Coping Well",
          pill: "bg-emerald-500 text-slate-950 font-bold",
        };
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col antialiased">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <span className="text-xl font-black tracking-tight text-white flex items-center gap-2">
                StressSense
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  AI Triage
                </span>
              </span>
              <p className="text-xs text-slate-400 hidden sm:block">Student Mental Health & Burnout Prediction</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center space-x-1 sm:space-x-2 bg-slate-950/60 p-1.5 rounded-xl border border-slate-800">
            <button
              onClick={() => handleTabChange("checkin")}
              className={`px-3 sm:px-4 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                activeTab === "checkin"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              ✍️ Daily Check-In
            </button>
            <button
              onClick={() => handleTabChange("history")}
              className={`px-3 sm:px-4 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                activeTab === "history"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              📈 History & Trends
            </button>
            <button
              onClick={() => handleTabChange("counselor")}
              className={`px-3 sm:px-4 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                activeTab === "counselor"
                  ? "bg-rose-600 text-white shadow-md shadow-rose-600/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              🚨 Counselor Hub
            </button>
          </nav>

          {/* Live Backend Indicator */}
          <div className="flex items-center space-x-2">
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border ${
                backendStatus === "online"
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  : backendStatus === "checking"
                  ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                  : "bg-rose-500/10 border-rose-500/30 text-rose-400"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  backendStatus === "online"
                    ? "bg-emerald-400 animate-ping"
                    : backendStatus === "checking"
                    ? "bg-amber-400"
                    : "bg-rose-400"
                }`}
              />
              <span className="hidden md:inline">
                {backendStatus === "online"
                  ? "API: localhost:8000"
                  : backendStatus === "checking"
                  ? "Connecting..."
                  : "API Offline"}
              </span>
            </div>
            <button
              onClick={checkHealth}
              title="Ping Backend Server"
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ========================================================================= */}
        {/* TAB 1: CHECK-IN PORTAL (POST /api/analyze)                                */}
        {/* ========================================================================= */}
        {activeTab === "checkin" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left: Input Form */}
            <div className="lg:col-span-6 space-y-6">
              <div className="glass-panel p-6 sm:p-7 rounded-2xl border border-slate-800 shadow-xl space-y-6">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    Student Reflection Check-In
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Logged entries are screened for distress, academic burnout, and crisis triggers in real time.
                  </p>
                </div>

                {/* Quick Fill Presets */}
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                    1-Click Test Presets (For Demo & Testing)
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {PRESETS.map((p, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => applyPreset(p)}
                        className="text-xs px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/60 text-slate-200 transition active:scale-95 flex items-center gap-1"
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                <form onSubmit={handleAnalyze} className="space-y-5">
                  {/* Student ID */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                      Student Identifier (`student_id`)
                    </label>
                    <div className="relative">
                      <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500 text-sm">
                        @
                      </span>
                      <input
                        type="text"
                        value={studentId}
                        onChange={(e) => setStudentId(e.target.value)}
                        placeholder="e.g. student_042"
                        className="w-full pl-9 pr-4 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-slate-100 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition font-mono"
                        required
                      />
                    </div>
                  </div>

                  {/* Mood Rating Selector (1 to 5) */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                        Self-Reported Mood (`mood_score`: 1 to 5)
                      </label>
                      <span className="text-xs font-medium text-indigo-400">
                        {MOOD_OPTIONS.find((m) => m.score === moodScore)?.label} — Score: {moodScore}/5
                      </span>
                    </div>

                    <div className="grid grid-cols-5 gap-2">
                      {MOOD_OPTIONS.map((item) => {
                        const isSelected = moodScore === item.score;
                        return (
                          <button
                            key={item.score}
                            type="button"
                            onClick={() => setMoodScore(item.score)}
                            className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                              isSelected
                                ? "bg-indigo-600/20 border-indigo-500 shadow-md shadow-indigo-500/20 scale-[1.03]"
                                : "bg-slate-950/60 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700"
                            }`}
                          >
                            <span className="text-2xl mb-1 select-none">{item.emoji}</span>
                            <span className="text-xs font-bold text-white">{item.score}</span>
                            <span className="text-[10px] text-slate-400 hidden sm:block truncate w-full">
                              {item.label}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Journal Reflection Textarea */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                        Journal Reflection (`journal_text`)
                      </label>
                      <span className="text-[11px] text-slate-500 font-mono">
                        {journalText.length} characters
                      </span>
                    </div>
                    <textarea
                      rows={5}
                      value={journalText}
                      onChange={(e) => setJournalText(e.target.value)}
                      placeholder="Share what's been on your mind today... How is your sleep, academic workload, or stress level?"
                      className="w-full px-4 py-3 bg-slate-950/80 border border-slate-800 rounded-xl text-slate-100 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition resize-none leading-relaxed"
                    />
                  </div>

                  {errorMsg && (
                    <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs flex items-center gap-2">
                      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>{errorMsg}</span>
                    </div>
                  )}

                  {/* Submit Button */}
                  <button
                    type="submit"
                    disabled={isAnalyzing}
                    className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-sm shadow-lg shadow-indigo-600/25 transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isAnalyzing ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Evaluating Mental Health Distress...
                      </>
                    ) : (
                      <>
                        <span>Submit Check-In for AI Triage</span>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                      </>
                    )}
                  </button>
                </form>
              </div>
            </div>

            {/* Right: Live Triage Results Dashboard (AnalysisResponse) */}
            <div className="lg:col-span-6 space-y-6">
              {!analysisResult && !isAnalyzing && (
                <div className="glass-panel p-8 rounded-2xl border border-slate-800 text-center space-y-4">
                  <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">Awaiting Check-In Submission</h3>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1 leading-relaxed">
                      Select your mood rating, describe how you feel, or click one of the test presets to trigger the AI risk assessment pipeline.
                    </p>
                  </div>

                  <div className="pt-4 border-t border-slate-800/80 text-left space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Returned Data Contract (`AnalysisResponse`):
                    </span>
                    <ul className="text-xs text-slate-400 space-y-1.5 font-mono">
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                        <span className="text-slate-300">risk_level:</span> LOW | MEDIUM | HIGH
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                        <span className="text-slate-300">sentiment_summary:</span> Neutral clinical overview
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                        <span className="text-slate-300">recommended_action:</span> Recommended next steps
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                        <span className="text-slate-300">flag_for_counselor:</span> true | false
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                        <span className="text-slate-300">coping_resources:</span> Verified campus & crisis resources
                      </li>
                    </ul>
                  </div>
                </div>
              )}

              {/* Loading Skeleton */}
              {isAnalyzing && (
                <div className="glass-panel p-8 rounded-2xl border border-indigo-500/30 space-y-6 animate-shimmer">
                  <div className="flex items-center space-x-3">
                    <div className="w-6 h-6 rounded-full bg-indigo-500 animate-pulse" />
                    <div className="h-5 bg-slate-800 rounded w-1/2" />
                  </div>
                  <div className="h-20 bg-slate-900 rounded-xl" />
                  <div className="h-16 bg-slate-900 rounded-xl" />
                  <div className="h-24 bg-slate-900 rounded-xl" />
                </div>
              )}

              {/* Full Analysis Result Card */}
              {analysisResult && !isAnalyzing && (
                <div className="space-y-5 animate-fadeIn">
                  {/* Urgent Counselor Alert Banner (if flag_for_counselor: true) */}
                  {analysisResult.flag_for_counselor && (
                    <div className="p-4 rounded-2xl bg-gradient-to-r from-rose-950/80 via-rose-900/60 to-slate-900 border border-rose-500/50 shadow-lg shadow-rose-900/20 flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-rose-600 flex items-center justify-center shrink-0 mt-0.5 animate-bounce">
                        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-rose-200">
                          Urgent Flagged for Counselor Attention
                        </h4>
                        <p className="text-xs text-rose-300/90 mt-0.5 leading-relaxed">
                          This entry contains acute distress or crisis triggers. A university mental health counselor has been automatically notified.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Triage Assessment Card */}
                  <div className="glass-panel p-6 sm:p-7 rounded-2xl border border-slate-800 shadow-xl space-y-6">
                    {/* Header Risk Badge */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
                          AI Triage Assessment
                        </span>
                        <h3 className="text-lg font-bold text-white mt-0.5">Clinical Risk Evaluation</h3>
                      </div>
                      <div
                        className={`px-3.5 py-1.5 rounded-full border text-xs font-bold uppercase tracking-wider flex items-center gap-2 ${
                          getRiskBadge(analysisResult.risk_level).bg
                        }`}
                      >
                        <span className={`w-2 h-2 rounded-full ${analysisResult.risk_level === 'HIGH' ? 'bg-rose-500 animate-ping' : analysisResult.risk_level === 'MEDIUM' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                        {analysisResult.risk_level} RISK
                      </div>
                    </div>

                    {/* Sentiment Summary */}
                    <div>
                      <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                        Sentiment & Emotional State Summary
                      </span>
                      <p className="text-sm text-slate-200 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 leading-relaxed">
                        {analysisResult.sentiment_summary}
                      </p>
                    </div>

                    {/* Recommended Action */}
                    <div>
                      <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                        Recommended Next Step
                      </span>
                      <div className="text-sm text-slate-200 bg-indigo-950/20 p-4 rounded-xl border border-indigo-500/20 flex items-start gap-2.5">
                        <svg className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <p className="leading-relaxed">{analysisResult.recommended_action}</p>
                      </div>
                    </div>

                    {/* Coping Resources */}
                    <div>
                      <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                        Attached Coping & Support Resources ({analysisResult.coping_resources?.length || 0})
                      </span>
                      <div className="space-y-2.5">
                        {analysisResult.coping_resources?.map((res, idx) => (
                          <div
                            key={idx}
                            className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/90 hover:border-slate-700 transition flex items-start justify-between gap-3"
                          >
                            <div className="space-y-0.5">
                              <h5 className="text-xs font-bold text-white">{res.title}</h5>
                              <p className="text-xs text-slate-400 leading-relaxed">{res.description}</p>
                            </div>
                            {res.url && (
                              <a
                                href={res.url}
                                target="_blank"
                                rel="noreferrer"
                                className="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white text-xs font-medium border border-indigo-500/30 transition shrink-0 self-center"
                              >
                                Access &rarr;
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: STUDENT HISTORY & TRENDS (/api/history/{student_id})                */}
        {/* ========================================================================= */}
        {activeTab === "history" && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white">
                  Past Mood & Risk Progression
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Showing historical check-in timeline for: <span className="font-mono text-indigo-400">@{studentId}</span>
                </p>
              </div>
              <button
                onClick={fetchHistory}
                disabled={isLoadingHistory}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition flex items-center gap-1.5"
              >
                <svg className={`w-3.5 h-3.5 ${isLoadingHistory ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh History
              </button>
            </div>

            {isLoadingHistory ? (
              <div className="text-center py-12">
                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-xs text-slate-400">Retrieving check-in history from /api/history/{studentId}...</p>
              </div>
            ) : historyData.length === 0 ? (
              <div className="glass-panel p-10 rounded-2xl border border-slate-800 text-center space-y-3">
                <span className="text-4xl">📭</span>
                <h3 className="text-sm font-bold text-white">No Past Check-Ins Found</h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  No submissions have been recorded for student ID <code className="text-indigo-300">"{studentId}"</code> yet.
                  Submit a check-in on the Daily Check-In tab to populate this list!
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {historyData.map((item, idx) => (
                  <div
                    key={idx}
                    className="glass-panel p-4 rounded-xl border border-slate-800 hover:border-slate-700 transition flex items-center justify-between gap-4"
                  >
                    <div className="flex items-center space-x-4">
                      <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center font-bold text-lg">
                        {item.mood <= 1 ? "😫" : item.mood <= 2 ? "😔" : item.mood <= 3 ? "😐" : item.mood <= 4 ? "🙂" : "✨"}
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white flex items-center gap-2">
                          <span>Mood Score: {item.mood} / 5</span>
                        </div>
                        <span className="text-[11px] font-mono text-slate-400">{item.date}</span>
                      </div>
                    </div>

                    <div
                      className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                        item.risk === "HIGH"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          : item.risk === "MEDIUM"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      }`}
                    >
                      {item.risk} RISK
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: COUNSELOR TRIAGE HUB (/api/counselor/flags)                        */}
        {/* ========================================================================= */}
        {activeTab === "counselor" && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
                  <h2 className="text-xl font-bold text-white">
                    Counselor Triage Hub
                  </h2>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Real-time urgent alerts feed: showing all submissions where <code className="text-rose-400">flag_for_counselor == True</code>
                </p>
              </div>
              <button
                onClick={fetchFlags}
                disabled={isLoadingFlags}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition flex items-center gap-1.5"
              >
                <svg className={`w-3.5 h-3.5 ${isLoadingFlags ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh Alert Feed
              </button>
            </div>

            {isLoadingFlags ? (
              <div className="text-center py-12">
                <div className="w-8 h-8 border-2 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-xs text-slate-400">Loading flagged cases from /api/counselor/flags...</p>
              </div>
            ) : flaggedEntries.length === 0 ? (
              <div className="glass-panel p-10 rounded-2xl border border-slate-800 text-center space-y-3">
                <span className="text-4xl">🎉</span>
                <h3 className="text-sm font-bold text-white">No Urgent Flags Pending</h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  There are currently no active high-risk check-in flags in the triage queue.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {flaggedEntries.map((flag, idx) => (
                  <div
                    key={idx}
                    className="glass-panel p-5 rounded-2xl border border-rose-500/30 bg-rose-950/10 space-y-4 shadow-lg shadow-rose-950/10"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className="px-2.5 py-0.5 rounded-lg bg-rose-500/20 text-rose-300 font-mono text-xs font-bold border border-rose-500/30">
                          {flag.student_id}
                        </span>
                        <span className="text-xs text-slate-400 font-mono">{flag.date}</span>
                      </div>
                      <span className="px-3 py-1 rounded-full bg-rose-600 text-white text-xs font-bold uppercase tracking-wider">
                        {flag.risk_level} RISK
                      </span>
                    </div>

                    {/* Student's raw journal entry */}
                    <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800">
                      <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                        Student Journal Text:
                      </span>
                      <p className="text-xs text-slate-200 leading-relaxed italic">
                        "{flag.journal_text}"
                      </p>
                    </div>

                    {/* Counselor Recommended Action */}
                    <div className="bg-indigo-950/20 p-3.5 rounded-xl border border-indigo-500/20 flex items-start gap-2.5">
                      <svg className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div>
                        <span className="text-[10px] uppercase font-bold text-indigo-300 block">
                          Triage Recommended Protocol:
                        </span>
                        <p className="text-xs text-slate-200 mt-0.5">{flag.recommended_action}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 text-center text-xs text-slate-500">
        <p>StressSense Mental Health Triage &copy; 2026. Built with FastAPI, React 19 & Tailwind CSS.</p>
        <p className="mt-1 text-[11px] text-slate-600">
          Emergency Support: 988 Suicide & Crisis Lifeline (24/7 Free & Confidential)
        </p>
      </footer>
    </div>
  );
}
