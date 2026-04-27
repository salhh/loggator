"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SystemEventsResponse } from "@/lib/types";
import StatusBoard from "@/components/health/StatusBoard";
import SystemEventFeed from "@/components/health/SystemEventFeed";
import AuditLogTable from "@/components/health/AuditLogTable";

type Tab = "events" | "audit";

export default function HealthClient() {
  const [tab, setTab] = useState<Tab>("events");
  const [data, setData] = useState<SystemEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.systemEvents({ limit: 50 });
      setData(res);
      setLastChecked(Date.now());
    } catch {
      // keep stale data
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    pollRef.current = setInterval(fetchData, 30_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchData]);

  // Elapsed counter
  useEffect(() => {
    const t = setInterval(() => {
      if (lastChecked !== null) setElapsed(Math.floor((Date.now() - lastChecked) / 1000));
    }, 1_000);
    return () => clearInterval(t);
  }, [lastChecked]);

  const tabClass = (t: Tab) =>
    `px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
      tab === t
        ? "border-cyan-400 text-foreground"
        : "border-transparent text-muted-foreground hover:text-foreground"
    }`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-semibold text-foreground flex-1">Platform Health</h1>
        {lastChecked !== null && (
          <span className="text-xs text-muted-foreground">Updated {elapsed}s ago</span>
        )}
        <button
          onClick={() => {
            setLoading(true);
            fetchData();
          }}
          disabled={loading}
          className="px-3 py-1.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors disabled:opacity-40"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* Status board skeleton or board */}
      {loading && !data ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="bg-card rounded-lg border border-border p-4 animate-pulse h-20"
            />
          ))}
        </div>
      ) : data ? (
        <StatusBoard data={data} />
      ) : null}

      {/* Tabs */}
      <div>
        <div className="flex border-b border-border mb-4">
          <button className={tabClass("events")} onClick={() => setTab("events")}>
            System Events
          </button>
          <button className={tabClass("audit")} onClick={() => setTab("audit")}>
            Audit Log
          </button>
        </div>

        {tab === "events" && <SystemEventFeed onDataUpdate={(d) => setData(d)} />}
        {tab === "audit" && <AuditLogTable />}
      </div>
    </div>
  );
}
