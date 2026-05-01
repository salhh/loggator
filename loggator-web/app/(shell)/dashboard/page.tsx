import { api } from "@/lib/api";
import type { Anomaly } from "@/lib/types";
import StatCard from "@/components/StatCard";
import AnomalyChart, { type ChartPoint } from "@/components/AnomalyChart";
import AnomalyCard from "@/components/AnomalyCard";
import LiveFeed from "@/components/LiveFeed";
import DashboardAnalysis from "@/components/DashboardAnalysis";
import ScheduleStatusWidget from "@/components/ScheduleStatus";
import Link from "next/link";

function buildChartData(anomalies: Anomaly[]): ChartPoint[] {
  const buckets: Record<string, { errors: number; anomalies: number }> = {};
  for (const a of anomalies) {
    const hour = new Date(a.detected_at).toISOString().slice(11, 13) + ":00";
    if (!buckets[hour]) buckets[hour] = { errors: 0, anomalies: 0 };
    buckets[hour].anomalies++;
    if (a.severity === "high") buckets[hour].errors++;
  }
  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, v]) => ({ hour, ...v }));
}

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">
      {children}
    </div>
  );
}

export default async function Dashboard() {
  const [statusRes, summariesRes, anomaliesRes] = await Promise.allSettled([
    api.status(),
    api.summaries(5),
    api.anomalies(100),
  ]);

  const s = statusRes.status === "fulfilled" ? statusRes.value : null;
  const latestSummary =
    summariesRes.status === "fulfilled" && summariesRes.value.length > 0
      ? summariesRes.value[0]
      : null;
  const allAnomalies = anomaliesRes.status === "fulfilled" ? anomaliesRes.value : [];
  const recentAnomalies = allAnomalies.slice(0, 6);
  const chartData = buildChartData(allAnomalies);

  const highCount = allAnomalies.filter((a) => a.severity === "high").length;
  const medCount = allAnomalies.filter((a) => a.severity === "medium").length;
  const ollamaOk = s?.ollama_ok || s?.ollama_reachable;

  return (
    <div className="space-y-6">

      {/* ── Stat row ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="High severity"
          value={highCount}
          borderColor="border-l-destructive"
          sub="anomalies"
        />
        <StatCard
          label="Medium severity"
          value={medCount}
          borderColor="border-l-warning"
          sub="anomalies"
        />
        <StatCard
          label="Total anomalies"
          value={allAnomalies.length}
          borderColor="border-l-primary"
          sub="last 100 fetched"
        />
        <StatCard
          label="Ollama"
          value={ollamaOk ? "Online" : "Offline"}
          borderColor={ollamaOk ? "border-l-success" : "border-l-destructive"}
          sub="AI model"
        />
      </div>

      {/* ── Main grid ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-[1fr_300px] gap-5">

        {/* Left column */}
        <div className="space-y-5">

          {/* Chart */}
          <div className="bg-card rounded-lg border border-border p-4">
            <div className="flex items-center justify-between mb-4">
              <SectionLabel>Anomaly activity · last 24 h</SectionLabel>
              <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-4 rounded-sm bg-primary/70 inline-block" />
                  Anomalies
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-4 rounded-sm bg-red-500/70 inline-block" />
                  Errors
                </span>
              </div>
            </div>
            {chartData.length > 0 ? (
              <AnomalyChart data={chartData} />
            ) : (
              <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground">
                No data yet
              </div>
            )}
          </div>

          {/* Latest summary */}
          {latestSummary && (
            <div className="bg-card rounded-lg border border-border p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <SectionLabel>Latest batch summary</SectionLabel>
                <span className="text-[10px] text-muted-foreground shrink-0">
                  {fmt(latestSummary.window_start)} → {fmt(latestSummary.window_end)}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-foreground/90">{latestSummary.summary}</p>
              {latestSummary.recommendation && (
                <p className="text-xs border-l-2 border-primary pl-3 text-muted-foreground leading-relaxed">
                  {latestSummary.recommendation}
                </p>
              )}
              <div className="flex gap-4 pt-1 border-t border-border text-xs text-muted-foreground">
                <span>Errors: <strong className="text-foreground">{latestSummary.error_count}</strong></span>
                <span>Model: <strong className="text-foreground">{latestSummary.model_used}</strong></span>
              </div>
            </div>
          )}

          {/* Recent anomalies */}
          {recentAnomalies.length > 0 && (
            <div className="bg-card rounded-lg border border-border p-4">
              <div className="flex items-center justify-between mb-3">
                <SectionLabel>Recent anomalies</SectionLabel>
                <Link
                  href="/anomalies"
                  className="text-[11px] text-muted-foreground hover:text-primary transition-colors"
                >
                  View all →
                </Link>
              </div>
              <div className="space-y-1.5">
                {recentAnomalies.map((a) => (
                  <Link key={a.id} href={`/anomalies/${a.id}`} className="block">
                    <AnomalyCard
                      severity={a.severity}
                      summary={a.summary}
                      meta={a.index_pattern}
                      timestamp={fmtRelative(a.detected_at)}
                    />
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">

          {/* Schedule status */}
          <ScheduleStatusWidget />

          {/* Live feed */}
          <div className="bg-card rounded-lg border border-border p-4">
            <SectionLabel>Live anomaly feed</SectionLabel>
            <LiveFeed />
          </div>
        </div>
      </div>

      {/* ── Full-width RCA ──────────────────────────────────────────────────── */}
      <DashboardAnalysis />
    </div>
  );
}
