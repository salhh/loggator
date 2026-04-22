"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { HealthCheck, HealthResponse } from "@/lib/types";

const SERVICE_LABELS: Record<string, string> = {
  database: "Database",
  opensearch: "OpenSearch",
  llm: "LLM",
  scheduler: "Scheduler",
  alerts: "Alert Channels",
};

const SERVICE_ORDER = ["database", "opensearch", "llm", "scheduler", "alerts"];

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${
        ok ? "bg-emerald-400" : "bg-red-400"
      }`}
    />
  );
}

function OverallBadge({ overall }: { overall: "ok" | "degraded" | "down" }) {
  const styles: Record<string, string> = {
    ok: "bg-emerald-400/10 text-emerald-400 border-emerald-400/30",
    degraded: "bg-amber-400/10 text-amber-400 border-amber-400/30",
    down: "bg-red-400/10 text-red-400 border-red-400/30",
  };
  const labels: Record<string, string> = {
    ok: "All Systems OK",
    degraded: "Degraded",
    down: "Down",
  };
  return (
    <span
      className={`px-2.5 py-1 rounded-md border text-xs font-semibold uppercase tracking-wide ${styles[overall]}`}
    >
      {labels[overall]}
    </span>
  );
}

function CheckCard({ name, check }: { name: string; check: HealthCheck }) {
  return (
    <div
      className={`bg-card rounded-lg border p-4 flex flex-col gap-2 ${
        check.ok ? "border-border" : "border-red-500/40"
      }`}
    >
      <div className="flex items-center gap-2">
        <StatusDot ok={check.ok} />
        <span className="text-sm font-medium text-foreground">
          {SERVICE_LABELS[name] ?? name}
        </span>
      </div>
      {check.latency_ms > 0 && (
        <span className="text-xs font-mono text-muted-foreground bg-secondary px-1.5 py-0.5 rounded self-start">
          {check.latency_ms} ms
        </span>
      )}
      <p className="text-xs text-muted-foreground leading-relaxed break-words">
        {check.detail}
      </p>
    </div>
  );
}

export default function HealthClient() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await api.health();
      setFetchError(false);
      setData(res);
      setLastChecked(Date.now());
    } catch {
      if (!data) setFetchError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(fetchHealth, 10_000);
  }, [fetchHealth]);

  const handleRefresh = useCallback(() => {
    setLoading(true);
    fetchHealth();
    startPolling();
  }, [fetchHealth, startPolling]);

  // Initial fetch + start polling
  useEffect(() => {
    fetchHealth();
    startPolling();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchHealth, startPolling]);

  // "Last checked X s ago" counter
  useEffect(() => {
    const t = setInterval(() => {
      if (lastChecked !== null) {
        setElapsed(Math.floor((Date.now() - lastChecked) / 1000));
      }
    }, 1_000);
    return () => clearInterval(t);
  }, [lastChecked]);

  const orderedChecks = data
    ? SERVICE_ORDER.filter((k) => k in data.checks).map((k) => ({
        name: k,
        check: data.checks[k],
      }))
    : [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-semibold text-foreground flex-1">System Health</h1>
        {data && <OverallBadge overall={data.overall} />}
        {lastChecked !== null && (
          <span className="text-xs text-muted-foreground">
            Last checked {elapsed}s ago
          </span>
        )}
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="px-3 py-1.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors disabled:opacity-40"
        >
          {loading ? "Checking…" : "Refresh"}
        </button>
      </div>

      {fetchError && !data && (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <p className="text-sm text-muted-foreground">Could not reach the API — is it running?</p>
        </div>
      )}

      {/* Cards — skeleton while loading before first data */}
      {loading && !data ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {SERVICE_ORDER.map((k) => (
            <div
              key={k}
              className="bg-card rounded-lg border border-border p-4 animate-pulse h-28"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {orderedChecks.map(({ name, check }) => (
            <CheckCard key={name} name={name} check={check} />
          ))}
        </div>
      )}
    </div>
  );
}
