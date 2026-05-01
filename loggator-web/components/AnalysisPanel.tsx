"use client";

import type { AnalysisReport, RootCause, Recommendation } from "@/lib/types";

export const severityBadge: Record<string, string> = {
  critical: "bg-red-950/60 text-red-300 border-red-800",
  high:     "bg-red-950/40 text-red-400 border-red-900",
  medium:   "bg-amber-950/40 text-amber-400 border-amber-900",
  low:      "bg-card text-gray-400 border-border",
};

export const priorityBadge: Record<string, string> = {
  immediate:    "bg-red-950/40 text-red-400 border-red-900",
  "short-term": "bg-amber-950/40 text-amber-400 border-amber-900",
  "long-term":  "bg-primary/12 text-primary border-primary/35",
};

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

export default function AnalysisPanel({
  report,
  onClose,
}: {
  report: AnalysisReport;
  onClose?: () => void;
}) {
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-background/50">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-semibold text-foreground">Root Cause Analysis</span>
          <span className="text-xs text-muted-foreground">
            {fmt(report.from_ts)} → {fmt(report.to_ts)}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex gap-3 text-xs text-muted-foreground">
            <span><strong className="text-red-400">{report.error_count}</strong> errors</span>
            <span><strong className="text-amber-400">{report.warning_count}</strong> warnings</span>
            <span><strong className="text-foreground">{report.log_count}</strong> logs</span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground text-xs px-2 py-1 rounded border border-border hover:border-primary transition-colors"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="p-4 space-y-5">
        {/* Summary */}
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Summary</div>
          <p className="text-sm leading-relaxed">{report.summary}</p>
        </div>

        {/* Affected services */}
        {report.affected_services?.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Affected services</div>
            <div className="flex flex-wrap gap-1.5">
              {report.affected_services.map((s) => (
                <span key={s} className="px-2 py-0.5 rounded border border-border bg-card text-xs font-mono text-foreground">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Root causes */}
        {report.root_causes?.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Root causes</div>
            <div className="space-y-2">
              {report.root_causes.map((rc: RootCause, i: number) => (
                <div
                  key={i}
                  className={`rounded-lg border p-3 space-y-1.5 ${severityBadge[rc.severity] ?? severityBadge.low}`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${severityBadge[rc.severity] ?? severityBadge.low}`}>
                      {rc.severity}
                    </span>
                    <span className="text-sm font-semibold">{rc.title}</span>
                  </div>
                  <p className="text-xs leading-relaxed opacity-90">{rc.description}</p>
                  {rc.services?.length > 0 && (
                    <div className="flex gap-1 flex-wrap">
                      {rc.services.map((s) => (
                        <span key={s} className="text-[10px] font-mono opacity-70 border border-current/20 rounded px-1.5 py-0.5">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Timeline */}
        {report.timeline?.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Timeline</div>
            <ul className="space-y-1 border-l border-border pl-4">
              {report.timeline.map((event, i) => (
                <li
                  key={i}
                  className="relative text-xs text-muted-foreground before:absolute before:-left-[17px] before:top-1 before:h-2 before:w-2 before:rounded-full before:bg-border before:border before:border-border"
                >
                  {event}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommendations */}
        {report.recommendations?.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Recommendations</div>
            <div className="space-y-2">
              {report.recommendations.map((r: Recommendation, i: number) => (
                <div
                  key={i}
                  className={`rounded-lg border p-3 space-y-1 ${priorityBadge[r.priority] ?? priorityBadge["long-term"]}`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${priorityBadge[r.priority] ?? priorityBadge["long-term"]}`}>
                      {r.priority}
                    </span>
                    <span className="text-sm font-medium">{r.action}</span>
                  </div>
                  <p className="text-xs opacity-80 pl-0.5">{r.rationale}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
