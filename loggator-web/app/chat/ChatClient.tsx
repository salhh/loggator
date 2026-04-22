"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";
import type { AnalysisReport, LLMConfig } from "@/lib/types";
import AnalysisPanel from "@/components/AnalysisPanel";

interface Message {
  role: "user" | "assistant";
  content: string;
  contextLogs?: string[];
  ts: number;
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

const SUGGESTED = [
  "What errors occurred in the last hour?",
  "Which service has the most failures?",
  "Are there any authentication anomalies?",
  "Summarise the most critical issues right now.",
  "What's causing the slowdowns in payment-service?",
];

function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function levelColor(line: string) {
  if (/\bERROR\b/.test(line)) return "text-red-400";
  if (/\bWARN\b/.test(line))  return "text-amber-400";
  if (/\bDEBUG\b/.test(line)) return "text-gray-500";
  return "text-muted-foreground";
}

/* ─── Main component ─────────────────────────────────────────────────────── */
export default function ChatClient() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const [panelOpen, setPanelOpen] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [indexDone, setIndexDone] = useState(false);
  const [analysisReport, setAnalysisReport] = useState<AnalysisReport | null>(null);

  const [hoursBack, setHoursBack] = useState(1);
  const [customHours, setCustomHours] = useState("");
  const [useCustom, setUseCustom] = useState(false);
  const [maxLogs, setMaxLogs] = useState(500);
  const [indexPattern, setIndexPattern] = useState("");
  const [indices, setIndices] = useState<string[]>([]);
  const [llms, setLlms] = useState<LLMConfig[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>("");

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.logIndices().then((d) => setIndices(d.indices ?? [])).catch(() => {});
    api.llms().then(setLlms).catch(() => {});
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("loggator_chat_history");
      if (raw) setMessages(JSON.parse(raw).slice(-50));
    } catch { /* corrupt storage */ }
    setHistoryLoaded(true);
  }, []);

  useEffect(() => {
    if (!historyLoaded) return;
    try {
      localStorage.setItem("loggator_chat_history", JSON.stringify(messages.slice(-50)));
    } catch { /* quota exceeded */ }
  }, [messages, historyLoaded]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const effectiveHours = useCustom ? (parseFloat(customHours) || 1) : hoursBack;
  const rangeLabel = effectiveHours < 1
    ? `${Math.round(effectiveHours * 60)} min`
    : `${effectiveHours}h`;

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  async function triggerIndex() {
    setIndexing(true);
    setIndexDone(false);
    try {
      await api.triggerIndex(indexPattern || undefined, effectiveHours, maxLogs);
      setIndexDone(true);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `Indexing started for the last **${rangeLabel}** of logs${indexPattern ? ` (${indexPattern})` : ""} — up to ${maxLogs} entries. You can start asking questions now.`,
        ts: Date.now(),
      }]);
      setPanelOpen(false);
    } catch {
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: "Failed to start indexing — is the API reachable?",
        ts: Date.now(),
      }]);
    } finally {
      setIndexing(false);
    }
  }

  async function triggerAnalyze() {
    setAnalysing(true);
    setAnalysisReport(null);
    try {
      const report = await api.analyzeLogs(indexPattern || undefined, effectiveHours, maxLogs, selectedModelId || undefined);
      setAnalysisReport(report);
      setPanelOpen(false);
    } catch {
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: "Analysis failed — check that the LLM provider is reachable and configured correctly.",
        ts: Date.now(),
      }]);
    } finally {
      setAnalysing(false);
    }
  }

  async function send(text?: string) {
    const userMsg = (text ?? input).trim();
    if (!userMsg || loading) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setMessages((prev) => [...prev, { role: "user", content: userMsg, ts: Date.now() }]);
    setLoading(true);
    try {
      const res = await api.chat(userMsg, 10, selectedModelId || undefined);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: res.answer,
        contextLogs: res.context_logs,
        ts: Date.now(),
      }]);
    } catch {
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: "Could not reach the API — please check your connection.",
        ts: Date.now(),
      }]);
    } finally {
      setLoading(false);
    }
  }

  const isEmpty = messages.length === 0 && !analysisReport;

  return (
    <div className="flex flex-col gap-4">
      {/* Controls panel */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <button
          onClick={() => setPanelOpen((o) => !o)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-secondary/50 transition-colors"
        >
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium">Log analysis controls</span>
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

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Model</label>
              <select
                value={selectedModelId}
                onChange={(e) => setSelectedModelId(e.target.value)}
                className="w-full bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-cyan-400 transition-colors"
              >
                <option value="">System default</option>
                {llms.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} — {m.provider} / {m.model}
                  </option>
                ))}
              </select>
              {llms.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  Add models in <a href="/settings" className="text-cyan-400 hover:underline">Settings → LLMs</a>.
                </p>
              )}
            </div>

            <div className="flex gap-3 pt-1">
              <button onClick={triggerIndex} disabled={indexing || analysing || (useCustom && !customHours)}
                className="px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                {indexing
                  ? <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-foreground border-t-transparent animate-spin" />Indexing…</span>
                  : "Index for chat"}
              </button>
              <button onClick={triggerAnalyze} disabled={analysing || indexing || (useCustom && !customHours)}
                className="px-4 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                {analysing
                  ? <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-black border-t-transparent animate-spin" />Analysing…</span>
                  : "Analyse & root cause"}
              </button>
            </div>

            <p className="text-xs text-muted-foreground">
              <strong className="text-foreground">Index for chat</strong> — embeds logs into the vector DB so you can ask questions.<br />
              <strong className="text-foreground">Analyse & root cause</strong> — runs deep map-reduce RCA via the configured LLM and returns a structured report.
            </p>
          </div>
        )}
      </div>

      {/* Analysis report */}
      {analysisReport && (
        <AnalysisPanel report={analysisReport} onClose={() => setAnalysisReport(null)} />
      )}

      {/* Message list */}
      <div className="flex flex-col gap-3 min-h-[240px]">
        {isEmpty && (
          <div className="flex flex-col gap-4 py-4">
            <p className="text-sm text-muted-foreground">
              Index logs above, then ask anything about your infrastructure.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-xs border border-border rounded-full px-3 py-1.5 text-muted-foreground hover:border-cyan-400 hover:text-foreground transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

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

        {messages.map((m, i) => (
          <div key={i} className={`flex gap-2 ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
            {/* Avatar */}
            <div className={`flex-none h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-bold select-none mt-0.5 ${
              m.role === "user"
                ? "bg-cyan-400 text-black"
                : "bg-secondary text-muted-foreground border border-border"
            }`}>
              {m.role === "user" ? "You" : "AI"}
            </div>

            {/* Bubble */}
            <div className={`max-w-[75%] rounded-xl border px-3.5 py-2.5 space-y-2 ${
              m.role === "user"
                ? "bg-card border-cyan-400/40 rounded-tr-sm"
                : "bg-card border-border rounded-tl-sm"
            }`}>
              {m.role === "assistant" ? (
                <div className="text-sm leading-relaxed prose prose-invert prose-sm max-w-none
                  prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-headings:my-1
                  prose-code:bg-background prose-code:px-1 prose-code:rounded prose-code:text-cyan-300
                  prose-pre:bg-background prose-pre:border prose-pre:border-border">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              )}

              {m.contextLogs && m.contextLogs.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground select-none flex items-center gap-1.5">
                    <span className="text-[10px] border border-border rounded px-1.5 py-0.5 font-mono">{m.contextLogs.length}</span>
                    log lines used as context
                  </summary>
                  <ul className="mt-2 space-y-px font-mono text-[10px] bg-background rounded p-2 max-h-44 overflow-auto border border-border">
                    {m.contextLogs.map((l, j) => (
                      <li key={j} className={levelColor(l)}>{l}</li>
                    ))}
                  </ul>
                </details>
              )}

              <p className="text-[10px] text-muted-foreground/60 select-none">{fmtTime(m.ts)}</p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-2">
            <div className="flex-none h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-bold bg-secondary border border-border text-muted-foreground mt-0.5 select-none">
              AI
            </div>
            <div className="rounded-xl rounded-tl-sm border border-border bg-card px-3.5 py-2.5 flex items-center gap-2.5">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:300ms]" />
              </span>
              <p className="text-sm text-muted-foreground">Thinking…</p>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Active model indicator */}
      {selectedModelId && llms.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 inline-block" />
          Using <span className="text-foreground font-medium">{llms.find(m => m.id === selectedModelId)?.label ?? selectedModelId}</span>
          <button onClick={() => setSelectedModelId("")} className="hover:text-red-400 transition-colors">✕</button>
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none bg-card border border-border rounded-lg px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-cyan-400 transition-colors min-h-[42px] max-h-[160px]"
          rows={1}
          placeholder="Ask about your logs…"
          value={input}
          onChange={(e) => { setInput(e.target.value); autoResize(); }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
          disabled={loading}
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="px-4 py-2.5 rounded-lg bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          Send
        </button>
      </div>
    </div>
  );
}
