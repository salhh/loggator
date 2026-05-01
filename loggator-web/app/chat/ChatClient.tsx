"use client";

import { useState, useEffect } from "react";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { AnalysisReport } from "@/lib/types";
import AnalysisPanel from "@/components/AnalysisPanel";

interface Message {
  role: "user" | "assistant";
  content: string;
  contextLogs?: string[];
}

const PRESETS = [
  { label: "15 min", hours: 0.25 },
  { label: "30 min", hours: 0.5 },
  { label: "1 h",    hours: 1 },
  { label: "3 h",    hours: 3 },
  { label: "6 h",    hours: 6 },
  { label: "12 h",   hours: 12 },
  { label: "24 h",   hours: 24 },
  { label: "48 h",   hours: 48 },
];

/* ─── Main component ─────────────────────────────────────────────────────── */
export default function ChatClient() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // Indexing / analysis panel
  const [panelOpen, setPanelOpen] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [indexDone, setIndexDone] = useState(false);
  const [analysisReport, setAnalysisReport] = useState<AnalysisReport | null>(null);

  // Time / scope controls (shared between index + analyze)
  const [hoursBack, setHoursBack] = useState(1);
  const [customHours, setCustomHours] = useState("");
  const [useCustom, setUseCustom] = useState(false);
  const [maxLogs, setMaxLogs] = useState(500);
  const [indexPattern, setIndexPattern] = useState("");
  const [indices, setIndices] = useState<string[]>([]);

  useEffect(() => {
    api.logIndices()
      .then((d) => setIndices(d.indices ?? []))
      .catch(() => {});
  }, []);

  // Load chat history from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem("loggator_chat_history");
      if (raw) setMessages(JSON.parse(raw).slice(-50));
    } catch { /* corrupt storage */ }
    setHistoryLoaded(true);
  }, []);

  // Persist chat history whenever messages change (after initial load)
  useEffect(() => {
    if (!historyLoaded) return;
    try {
      localStorage.setItem("loggator_chat_history", JSON.stringify(messages.slice(-50)));
    } catch { /* quota exceeded */ }
  }, [messages, historyLoaded]);

  const effectiveHours = useCustom ? (parseFloat(customHours) || 1) : hoursBack;
  const rangeLabel = effectiveHours < 1
    ? `${Math.round(effectiveHours * 60)} min`
    : `${effectiveHours}h`;

  async function triggerIndex() {
    setIndexing(true);
    setIndexDone(false);
    try {
      await api.triggerIndex(indexPattern || undefined, effectiveHours, maxLogs);
      setIndexDone(true);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `✓ Indexing started for the last **${rangeLabel}** of logs${indexPattern ? ` (${indexPattern})` : ""} — up to ${maxLogs} entries. Wait **~1–2 minutes** for embeddings to finish, then ask questions (semantic search). Until then, chat still uses **recent OpenSearch logs** as fallback context.`,
      }]);
      setPanelOpen(false);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Failed to start indexing — is the API reachable?" }]);
    } finally {
      setIndexing(false);
    }
  }

  async function triggerAnalyze() {
    setAnalysing(true);
    setAnalysisReport(null);
    try {
      const report = await api.analyzeLogs(indexPattern || undefined, effectiveHours, maxLogs);
      setAnalysisReport(report);
      setPanelOpen(false);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Analysis failed — is Ollama running?" }]);
    } finally {
      setAnalysing(false);
    }
  }

  async function send() {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    try {
      const res = await api.chat(userMsg);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, contextLogs: res.context_logs }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Controls panel */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <button
          onClick={() => setPanelOpen((o) => !o)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-secondary/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-foreground">Log analysis controls</span>
            {indexDone && (
              <span className="text-xs text-emerald-400 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 inline-block" />
                Indexed
              </span>
            )}
            {analysisReport && (
              <span className="text-xs text-cyan-400 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 inline-block" />
                Analysis ready
              </span>
            )}
            {!indexDone && !analysisReport && (
              <span className="text-xs text-muted-foreground">Configure time range, then index or analyse</span>
            )}
          </div>
          <span className="text-muted-foreground text-sm">{panelOpen ? "▲" : "▼"}</span>
        </button>

        {panelOpen && (
          <div className="border-t border-border px-4 py-4 space-y-4">
            {/* Time range */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Time window</label>
              <div className="flex flex-wrap gap-1.5">
                {PRESETS.map((p) => (
                  <button key={p.label} onClick={() => { setUseCustom(false); setHoursBack(p.hours); }}
                    className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
                      !useCustom && hoursBack === p.hours
                        ? "bg-cyan-400 text-black border-cyan-400"
                        : "border-border text-muted-foreground hover:border-cyan-400 hover:text-foreground"
                    }`}>
                    {p.label}
                  </button>
                ))}
                <button onClick={() => setUseCustom(true)}
                  className={`px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
                    useCustom ? "bg-cyan-400 text-black border-cyan-400" : "border-border text-muted-foreground hover:border-cyan-400 hover:text-foreground"
                  }`}>
                  Custom
                </button>
              </div>
              {useCustom && (
                <div className="flex items-center gap-2">
                  <input type="number" min="0.1" step="0.5" placeholder="e.g. 4" value={customHours}
                    onChange={(e) => setCustomHours(e.target.value)}
                    className="w-24 bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-cyan-400 transition-colors" />
                  <span className="text-sm text-muted-foreground">hours back from now</span>
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Window: last <strong className="text-foreground">{rangeLabel}</strong>
              </p>
            </div>

            {/* Advanced */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Max log entries</label>
                <div className="flex gap-1.5">
                  {[100, 250, 500, 1000].map((n) => (
                    <button key={n} onClick={() => setMaxLogs(n)}
                      className={`px-2.5 py-1 rounded text-xs font-mono border transition-colors ${
                        maxLogs === n ? "bg-cyan-400 text-black border-cyan-400" : "border-border text-muted-foreground hover:border-cyan-400 hover:text-foreground"
                      }`}>
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Index pattern</label>
                <select value={indexPattern} onChange={(e) => setIndexPattern(e.target.value)}
                  className="w-full bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-cyan-400 transition-colors">
                  <option value="">Default (logs-*)</option>
                  {indices.map((idx) => <option key={idx} value={idx}>{idx}</option>)}
                </select>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-3 pt-1">
              <button onClick={triggerIndex} disabled={indexing || analysing || (useCustom && !customHours)}
                className="px-4 py-2 rounded-md border border-border text-sm font-medium text-foreground hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                {indexing ? <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-foreground border-t-transparent animate-spin" />Indexing…</span> : "Index for chat"}
              </button>

              <button onClick={triggerAnalyze} disabled={analysing || indexing || (useCustom && !customHours)}
                className="px-4 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                {analysing
                  ? <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-black border-t-transparent animate-spin" />Analysing…</span>
                  : "Analyse & root cause"}
              </button>
            </div>

            <p className="text-xs text-muted-foreground">
              <strong className="text-foreground">Index for chat</strong> — embeds logs into vector DB so you can ask questions.<br />
              <strong className="text-foreground">Analyse & root cause</strong> — runs deep map-reduce analysis via Ollama and returns a structured RCA report.
            </p>
          </div>
        )}
      </div>

      {/* Analysis report */}
      {analysisReport && (
        <AnalysisPanel report={analysisReport} onClose={() => setAnalysisReport(null)} />
      )}

      {/* Messages */}
      <div className="space-y-3 min-h-[200px]">
        {messages.length > 0 && (
          <div className="flex justify-end">
            <button
              onClick={() => {
                setMessages([]);
                try { localStorage.removeItem("loggator_chat_history"); } catch { /* ignore */ }
              }}
              className="text-xs text-muted-foreground hover:text-red-400 border border-border hover:border-red-900 px-2 py-1 rounded transition-colors"
            >
              Clear history
            </button>
          </div>
        )}
        {messages.length === 0 && !analysisReport && (
          <p className="text-sm text-muted-foreground">Open the controls above to index logs or run a root cause analysis.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div className={`max-w-2xl rounded-lg border p-3 space-y-2 ${m.role === "user" ? "bg-card border-cyan-400/40" : "bg-card border-border"}`}>
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              {m.contextLogs && m.contextLogs.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                    {m.contextLogs.length} log lines used as context
                  </summary>
                  <ul className="mt-2 space-y-0.5 font-mono text-[10px] text-muted-foreground bg-background rounded p-2 max-h-40 overflow-auto">
                    {m.contextLogs.map((l, j) => <li key={j}>{l}</li>)}
                  </ul>
                </details>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="max-w-2xl rounded-lg border border-border bg-card p-3 flex items-center gap-2">
            <span className="h-3 w-3 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
            <p className="text-sm text-muted-foreground">Thinking…</p>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <Textarea className="resize-none bg-card border-border" rows={2}
          placeholder="Ask about your logs…" value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        />
        <button onClick={send} disabled={loading || !input.trim()}
          className="px-4 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          Send
        </button>
      </div>
    </div>
  );
}
