"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { ScheduleStatus } from "@/lib/types";

function fmtRelative(iso: string | null) {
  if (!iso) return "—";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

function Row({ label, value, accent }: { label: string; value: string; accent?: "green" | "red" }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-border/40 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span
        className={`text-xs font-mono ${
          accent === "green"
            ? "text-emerald-400"
            : accent === "red"
            ? "text-red-400"
            : "text-foreground"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export default function ScheduleStatusWidget() {
  const [status, setStatus] = useState<ScheduleStatus | null>(null);

  useEffect(() => {
    api.scheduleStatus().then(setStatus).catch(() => {});
    const id = setInterval(
      () => api.scheduleStatus().then(setStatus).catch(() => {}),
      30_000,
    );
    return () => clearInterval(id);
  }, []);

  if (!status) return null;

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Scheduled Analysis
        </span>
        <span
          className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
            status.enabled
              ? "border-emerald-800 bg-emerald-950/40 text-emerald-400"
              : "border-border text-muted-foreground"
          }`}
        >
          {status.enabled ? "on" : "off"}
        </span>
      </div>

      <div className="space-y-0">
        <Row label="Interval" value={`${status.interval_minutes}m`} />
        <Row label="Window" value={`${status.window_minutes}m`} />
        <Row
          label="Next run"
          value={status.next_run_at ? new Date(status.next_run_at).toLocaleTimeString() : "—"}
        />
        <Row label="Last run" value={fmtRelative(status.last_run_at)} />
        {status.last_run_status && (
          <Row
            label="Status"
            value={status.last_run_status}
            accent={status.last_run_status === "success" ? "green" : "red"}
          />
        )}
      </div>
    </div>
  );
}
