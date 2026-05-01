"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SystemEvent, SystemEventsResponse } from "@/lib/types";

const SERVICES = ["llm", "opensearch", "postgres", "scheduler", "alerts", "streaming"];
const SEVERITIES = ["info", "warning", "error", "critical"];

const SEVERITY_BADGE: Record<string, string> = {
  info: "bg-chart-5/10 text-chart-5 border border-chart-5/25",
  warning: "bg-amber-400/10 text-amber-400 border border-amber-400/20",
  error: "bg-red-400/10 text-red-400 border border-red-400/20",
  critical: "bg-purple-400/10 text-purple-400 border border-purple-400/20",
};

function EventRow({ event }: { event: SystemEvent }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-b border-border last:border-0 py-2.5 px-1">
      <div
        className="flex items-start gap-3 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="text-xs font-mono text-muted-foreground shrink-0 w-36">
          {new Date(event.timestamp).toLocaleString()}
        </span>
        <span
          className={`text-[11px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
            SEVERITY_BADGE[event.severity] ?? ""
          }`}
        >
          {event.severity}
        </span>
        <span className="text-xs text-primary bg-primary/10 px-1.5 py-0.5 rounded shrink-0">
          {event.service}
        </span>
        <span className="text-sm text-foreground leading-snug flex-1 min-w-0">
          {event.message}
        </span>
      </div>
      {expanded && event.details && (
        <pre className="mt-2 ml-4 p-3 bg-secondary rounded text-xs font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(event.details, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function SystemEventFeed({
  onDataUpdate,
}: {
  onDataUpdate?: (data: SystemEventsResponse) => void;
}) {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterService, setFilterService] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchEvents = useCallback(async () => {
    try {
      const data = await api.systemEvents({
        service: filterService || undefined,
        severity: filterSeverity || undefined,
        limit: 100,
      });
      setEvents(data.events);
      onDataUpdate?.(data);
    } catch {
      // keep stale data on error
    } finally {
      setLoading(false);
    }
  }, [filterService, filterSeverity, onDataUpdate]);

  useEffect(() => {
    setLoading(true);
    fetchEvents();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(fetchEvents, 30_000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchEvents]);

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select
          value={filterService}
          onChange={(e) => setFilterService(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All services</option>
          {SERVICES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground self-center ml-auto">
          Auto-refresh every 30s
        </span>
      </div>

      {/* Event list */}
      <div className="bg-card border border-border rounded-lg px-3 py-1">
        {loading && events.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">Loading…</div>
        ) : events.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No events in the last 24 hours
          </div>
        ) : (
          events.map((e) => <EventRow key={e.id} event={e} />)
        )}
      </div>
    </div>
  );
}
