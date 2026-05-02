"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { AnalysisReport } from "@/lib/types";
import AnalysisPanel from "@/components/AnalysisPanel";

const PRESETS = [
  { label: "1 h",  hours: 1 },
  { label: "3 h",  hours: 3 },
  { label: "6 h",  hours: 6 },
  { label: "12 h", hours: 12 },
  { label: "24 h", hours: 24 },
];

export default function DashboardAnalysis() {
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoursBack, setHoursBack] = useState(24);
  const [refreshing, setRefreshing] = useState(false);

  async function runAnalysis(hours: number, isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const result = await api.analyzeLogs(undefined, hours, 500);
      setReport(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  // Auto-run on mount with default 24h window
  useEffect(() => {
    runAnalysis(24);
  }, []);

  function handlePreset(hours: number) {
    setHoursBack(hours);
    runAnalysis(hours, !!report);
  }

  return (
    <div className="space-y-3">
      {/* Section header with time-range controls */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
          Log Analysis · Last {hoursBack}h
        </div>
        <div className="flex items-center gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => handlePreset(p.hours)}
              disabled={loading || refreshing}
              className={`text-[11px] px-2 py-0.5 rounded border transition-colors ${
                hoursBack === p.hours
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground hover:border-primary/50"
              } disabled:opacity-40`}
            >
              {p.label}
            </button>
          ))}
          {report && (
            <button
              onClick={() => runAnalysis(hoursBack, true)}
              disabled={loading || refreshing}
              className="text-[11px] px-2 py-0.5 rounded border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors disabled:opacity-40 ml-1"
              title="Re-run analysis"
            >
              ↻
            </button>
          )}
        </div>
      </div>

      {/* States */}
      {loading && (
        <div className="bg-card border border-border rounded-lg p-6 flex flex-col items-center gap-3 text-muted-foreground">
          <div className="flex gap-1">
            <span className="h-2 w-2 rounded-full bg-primary animate-bounce [animation-delay:0ms]" />
            <span className="h-2 w-2 rounded-full bg-primary animate-bounce [animation-delay:150ms]" />
            <span className="h-2 w-2 rounded-full bg-primary animate-bounce [animation-delay:300ms]" />
          </div>
          <span className="text-xs">Analysing logs with Ollama…</span>
        </div>
      )}

      {error && !loading && (
        <div className="bg-card border border-destructive/40 rounded-lg p-4 space-y-2">
          <p className="text-xs text-destructive">Analysis failed: {error}</p>
          <button
            onClick={() => runAnalysis(hoursBack, false)}
            className="text-xs text-primary hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {report && !loading && (
        <div className={refreshing ? "opacity-60 pointer-events-none transition-opacity" : ""}>
          <AnalysisPanel report={report} />
        </div>
      )}
    </div>
  );
}
