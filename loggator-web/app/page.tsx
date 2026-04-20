import { api } from "@/lib/api";
import type { Anomaly } from "@/lib/types";
import StatCard from "@/components/StatCard";
import AnomalyChart, { type ChartPoint } from "@/components/AnomalyChart";
import AnomalyCard from "@/components/AnomalyCard";
import LiveFeed from "@/components/LiveFeed";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

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
  const recentAnomalies = allAnomalies.slice(0, 8);
  const chartData = buildChartData(allAnomalies);

  const highCount = allAnomalies.filter((a) => a.severity === "high").length;
  const medCount = allAnomalies.filter((a) => a.severity === "medium").length;

  return (
    <div className="grid grid-cols-[2fr_1fr] gap-6 min-h-full">
      {/* Left column */}
      <div className="space-y-6">
        {/* Stat row */}
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="High anomalies" value={highCount} borderColor="border-l-red-500" />
          <StatCard label="Total anomalies" value={allAnomalies.length} borderColor="border-l-cyan-400" />
          <StatCard
            label="Ollama"
            value={(s?.ollama_ok || s?.ollama_reachable) ? "OK" : "Offline"}
            borderColor="border-l-emerald-500"
          />
          <StatCard label="Medium alerts" value={medCount} borderColor="border-l-amber-500" />
        </div>

        {/* Chart */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-4">
            Errors + Anomalies · last 24h
          </div>
          {chartData.length > 0 ? (
            <AnomalyChart data={chartData} />
          ) : (
            <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">
              No data yet
            </div>
          )}
        </div>
      </div>

      {/* Right column */}
      <div className="space-y-6">
        {/* Live feed */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">
            Live anomaly feed
          </div>
          <LiveFeed />
        </div>

        {/* Latest summary */}
        {latestSummary && (
          <div className="bg-card rounded-lg border border-border p-4 space-y-2">
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Latest summary
            </div>
            <p className="text-xs text-muted-foreground">
              {fmt(latestSummary.window_start)} → {fmt(latestSummary.window_end)}
            </p>
            <p className="text-sm leading-relaxed">{latestSummary.summary}</p>
            {latestSummary.recommendation && (
              <p className="text-xs border-l-2 border-cyan-400 pl-3 text-muted-foreground">
                {latestSummary.recommendation}
              </p>
            )}
            <div className="text-xs text-muted-foreground">
              Errors: <strong className="text-foreground">{latestSummary.error_count}</strong>
            </div>
          </div>
        )}

        {/* Recent anomalies (static) */}
        {recentAnomalies.length > 0 && (
          <div className="bg-card rounded-lg border border-border p-4">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">
              Recent anomalies
            </div>
            <div className="space-y-2">
              {recentAnomalies.map((a) => (
                <AnomalyCard
                  key={a.id}
                  severity={a.severity}
                  summary={a.summary}
                  meta={a.index_pattern}
                  timestamp={fmtRelative(a.detected_at)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
