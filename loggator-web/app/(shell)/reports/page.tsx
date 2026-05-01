import Link from "next/link";
import { api } from "@/lib/api";
import type { ScheduledAnalysis } from "@/lib/types";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

function fmtWindow(start: string, end: string) {
  const s = new Date(start);
  const e = new Date(end);
  const sameDay = s.toDateString() === e.toDateString();
  if (sameDay) {
    return `${s.toLocaleDateString()} · ${s.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} → ${e.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }
  return `${fmt(start)} → ${fmt(end)}`;
}

function StatusBadge({ status }: { status: "success" | "failed" }) {
  return (
    <span
      className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
        status === "success"
          ? "border-emerald-800 bg-emerald-950/40 text-emerald-400"
          : "border-red-900 bg-red-950/40 text-red-400"
      }`}
    >
      {status}
    </span>
  );
}

function ReportCard({ r }: { r: ScheduledAnalysis }) {
  return (
    <Link href={`/reports/${r.id}`} className="block group">
      <div className="bg-card border border-border rounded-lg p-4 space-y-3 hover:border-cyan-400/40 transition-colors cursor-pointer">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-0.5">
            <div className="text-xs font-mono text-muted-foreground">
              {fmtWindow(r.window_start, r.window_end)}
            </div>
            <div className="text-[10px] text-muted-foreground/60 font-mono">
              {r.index_pattern}
            </div>
          </div>
          <StatusBadge status={r.status} />
        </div>

        {/* Summary preview */}
        <p className="text-sm leading-relaxed line-clamp-2 text-foreground/90">
          {r.summary}
        </p>

        {/* Stats + affected services */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex gap-3 text-xs text-muted-foreground">
            <span>
              <strong className="text-red-400">{r.error_count}</strong> errors
            </span>
            <span>
              <strong className="text-amber-400">{r.warning_count}</strong> warnings
            </span>
            <span>
              <strong className="text-foreground">{r.log_count}</strong> logs
            </span>
          </div>
          {r.affected_services?.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {r.affected_services.slice(0, 4).map((s) => (
                <span
                  key={s}
                  className="px-1.5 py-0.5 rounded border border-border bg-background text-[10px] font-mono text-muted-foreground"
                >
                  {s}
                </span>
              ))}
              {r.affected_services.length > 4 && (
                <span className="text-[10px] text-muted-foreground">
                  +{r.affected_services.length - 4} more
                </span>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="text-[10px] text-muted-foreground/60">
          Saved {fmt(r.created_at)} · model: {r.model_used}
        </div>
      </div>
    </Link>
  );
}

export default async function ReportsPage() {
  let reports: ScheduledAnalysis[] = [];
  try {
    reports = await api.analysisReports(50);
  } catch {
    // API unavailable
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Scheduled Analysis Reports</h1>
        <span className="text-xs text-muted-foreground">{reports.length} report(s)</span>
      </div>

      {reports.length === 0 ? (
        <div className="bg-card border border-border rounded-lg p-8 text-center space-y-3">
          <p className="text-sm text-muted-foreground">No scheduled analyses yet.</p>
          <p className="text-xs text-muted-foreground">
            Enable scheduled analysis in{" "}
            <Link href="/settings" className="text-cyan-400 hover:underline">
              Settings → RCA Schedule
            </Link>{" "}
            to start automatically analyzing your logs.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((r) => (
            <ReportCard key={r.id} r={r} />
          ))}
        </div>
      )}
    </div>
  );
}
