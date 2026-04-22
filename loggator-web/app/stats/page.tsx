// loggator-web/app/stats/page.tsx
import { api } from "@/lib/api";
import type { StatsResponse } from "@/lib/types";
import StatCard from "@/components/StatCard";
import DailyActivityChart from "@/components/DailyActivityChart";
import LogVolumeChart from "@/components/LogVolumeChart";

const DAYS_OPTIONS = [7, 30] as const;

export default async function StatsPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const { days: rawDays } = await searchParams;
  const days: 7 | 30 = DAYS_OPTIONS.includes(Number(rawDays) as 7 | 30)
    ? (Number(rawDays) as 7 | 30)
    : 7;

  let stats: StatsResponse | null = null;
  try {
    stats = await api.stats(days);
  } catch {
    // API offline
  }

  if (!stats) {
    return (
      <div className="space-y-5">
        <h1 className="text-lg font-semibold">Statistics</h1>
        <p className="text-sm text-muted-foreground">
          Could not load statistics — is the API running?
        </p>
      </div>
    );
  }

  const maxErrors = Math.max(...stats.top_services.map((s) => s.error_count), 1);

  return (
    <div className="space-y-6">
      {/* Header + period toggle */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-semibold flex-1">Statistics</h1>
        <div className="flex gap-1.5">
          {DAYS_OPTIONS.map((d) => (
            <a
              key={d}
              href={`/stats?days=${d}`}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                days === d
                  ? "bg-cyan-400 text-black"
                  : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-cyan-400/60"
              }`}
            >
              {d}d
            </a>
          ))}
        </div>
      </div>

      {/* Row 1: stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Summaries"
          value={stats.totals.summaries}
          borderColor="border-l-cyan-400"
          sub={`last ${days} days`}
        />
        <StatCard
          label="Anomalies"
          value={stats.totals.anomalies}
          borderColor="border-l-amber-400"
          sub={`last ${days} days`}
        />
        <StatCard
          label="Alerts Sent"
          value={stats.totals.alerts_sent}
          borderColor="border-l-emerald-400"
          sub={`last ${days} days`}
        />
        <StatCard
          label="Alerts Failed"
          value={stats.totals.alerts_failed}
          borderColor="border-l-red-400"
          sub={`last ${days} days`}
        />
      </div>

      {/* Row 2: daily activity chart */}
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="flex items-center gap-4 mb-3 flex-wrap">
          <span className="text-sm font-medium">Daily Activity</span>
          <div className="flex gap-4 ml-auto text-xs text-muted-foreground flex-wrap">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
              Summaries
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
              Anomalies
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-400 inline-block" />
              Alerts
            </span>
          </div>
        </div>
        <DailyActivityChart data={stats.daily} />
      </div>

      {/* Row 3: log volume + top error services */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Log volume */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="flex items-center gap-4 mb-3 flex-wrap">
            <span className="text-sm font-medium">Log Volume by Day</span>
            <div className="flex gap-4 ml-auto text-xs text-muted-foreground flex-wrap">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
                Error
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                Warn
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
                Info
              </span>
            </div>
          </div>
          {stats.log_volume.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Log data unavailable
            </p>
          ) : (
            <LogVolumeChart data={stats.log_volume} />
          )}
        </div>

        {/* Top error services */}
        <div className="bg-card rounded-lg border border-border p-4">
          <span className="text-sm font-medium block mb-3">Top Error Services</span>
          {stats.top_services.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No error data</p>
          ) : (
            <div className="space-y-3">
              {stats.top_services.map((s) => (
                <div key={s.service} className="flex items-center gap-3">
                  <span className="text-xs font-mono text-muted-foreground w-36 shrink-0 truncate">
                    {s.service}
                  </span>
                  <div className="flex-1 bg-secondary rounded-full h-1.5">
                    <div
                      className="bg-red-400 h-1.5 rounded-full transition-all"
                      style={{ width: `${(s.error_count / maxErrors) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-muted-foreground w-8 text-right shrink-0">
                    {s.error_count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Row 4: anomalies by severity + alerts by channel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Anomalies by severity */}
        <div className="bg-card rounded-lg border border-border p-4">
          <span className="text-sm font-medium block mb-3">Anomalies by Severity</span>
          <div className="flex gap-3 flex-wrap">
            <span className="px-3 py-1.5 rounded-md bg-emerald-400/10 text-emerald-400 text-sm font-medium border border-emerald-400/20">
              Low — {stats.anomalies_by_severity.low}
            </span>
            <span className="px-3 py-1.5 rounded-md bg-amber-400/10 text-amber-400 text-sm font-medium border border-amber-400/20">
              Medium — {stats.anomalies_by_severity.medium}
            </span>
            <span className="px-3 py-1.5 rounded-md bg-red-400/10 text-red-400 text-sm font-medium border border-red-400/20">
              High — {stats.anomalies_by_severity.high}
            </span>
          </div>
        </div>

        {/* Alerts by channel */}
        <div className="bg-card rounded-lg border border-border p-4">
          <span className="text-sm font-medium block mb-3">Alerts by Channel</span>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(stats.alerts_by_channel).length === 0 ? (
              <p className="text-sm text-muted-foreground">No alerts dispatched yet</p>
            ) : (
              Object.entries(stats.alerts_by_channel).map(([ch, count]) => (
                <span
                  key={ch}
                  className="px-3 py-1.5 rounded-md bg-secondary text-foreground text-sm font-medium border border-border capitalize"
                >
                  {ch} — {count}
                </span>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
