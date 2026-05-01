"use client";

import { useState, useEffect, useCallback, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const LEVELS = ["INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "DEBUG"];

const levelColor: Record<string, string> = {
  ERROR:    "text-destructive bg-destructive/10 border-destructive/40",
  CRITICAL: "text-destructive bg-destructive/15 border-destructive/50",
  WARN:     "text-warning bg-warning/10 border-warning/35",
  WARNING:  "text-warning bg-warning/10 border-warning/35",
  INFO:     "text-chart-1 bg-chart-1/10 border-chart-1/30",
  DEBUG:    "text-muted-foreground bg-muted border-border",
};

const levelDot: Record<string, string> = {
  ERROR:    "bg-destructive",
  CRITICAL: "bg-destructive",
  WARN:     "bg-warning",
  WARNING:  "bg-warning",
  INFO:     "bg-chart-1",
  DEBUG:    "bg-muted-foreground",
};

interface LogEntry {
  id: string;
  index: string;
  "@timestamp"?: string;
  level?: string;
  message?: string;
  service?: string;
  host?: string;
  [key: string]: unknown;
}

type SortField = "@timestamp" | "level" | "service" | "message";

function fmt(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [q, setQ] = useState("");
  const [levelFilter, setLevelFilter] = useState<string[]>([]);
  const [serviceFilter, setServiceFilter] = useState("");
  const [indices, setIndices] = useState<string[]>([]);
  const [indexFilter, setIndexFilter] = useState("");

  // Sort
  const [sortField, setSortField] = useState<SortField>("@timestamp");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Pagination
  const [offset, setOffset] = useState(0);
  const LIMIT = 100;

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load available indices once
  useEffect(() => {
    fetch(`${API}/logs/indices`)
      .then((r) => r.json())
      .then((d) => setIndices(d.indices ?? []))
      .catch(() => {});
  }, []);

  const fetchLogs = useCallback(
    async (currentOffset = 0) => {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (levelFilter.length) params.set("level", levelFilter.join(","));
      if (serviceFilter) params.set("service", serviceFilter);
      if (indexFilter) params.set("index", indexFilter);
      params.set("sort_field", sortField);
      params.set("sort_dir", sortDir);
      params.set("limit", String(LIMIT));
      params.set("offset", String(currentOffset));

      try {
        const res = await fetch(`${API}/logs?${params}`);
        const data = await res.json();
        if (data.error) setError(data.error);
        setLogs(data.logs ?? []);
        setTotal(data.total ?? 0);
        setOffset(currentOffset);
      } catch (e) {
        setError("Failed to reach API");
      } finally {
        setLoading(false);
      }
    },
    [q, levelFilter, serviceFilter, indexFilter, sortField, sortDir]
  );

  // Debounce text search
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => fetchLogs(0), 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [fetchLogs]);

  function toggleLevel(lvl: string) {
    setLevelFilter((prev) =>
      prev.includes(lvl) ? prev.filter((l) => l !== lvl) : [...prev, lvl]
    );
  }

  function handleSort(field: SortField) {
    if (field === sortField) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="text-muted-foreground ml-1">↕</span>;
    return <span className="text-primary ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>;
  };

  const totalPages = Math.ceil(total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-card border border-border rounded-lg p-3 space-y-3">
        {/* Row 1: search + index */}
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search messages..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="flex-1 bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-colors"
          />
          <select
            value={indexFilter}
            onChange={(e) => setIndexFilter(e.target.value)}
            className="bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-primary transition-colors min-w-[160px]"
          >
            <option value="">All indices</option>
            {indices.map((idx) => (
              <option key={idx} value={idx}>{idx}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Service..."
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="w-36 bg-background border border-border rounded-md px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-colors"
          />
        </div>

        {/* Row 2: level toggles + stats */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground">Level:</span>
          {LEVELS.map((lvl) => (
            <button
              key={lvl}
              onClick={() => toggleLevel(lvl)}
              className={`px-2 py-0.5 rounded text-xs font-mono font-semibold border transition-colors ${
                levelFilter.includes(lvl)
                  ? (levelColor[lvl] ?? "text-foreground bg-card border-border")
                  : "text-muted-foreground border-border hover:border-primary/50"
              }`}
            >
              {lvl}
            </button>
          ))}
          {(levelFilter.length > 0 || q || serviceFilter || indexFilter) && (
            <button
              onClick={() => { setQ(""); setLevelFilter([]); setServiceFilter(""); setIndexFilter(""); }}
              className="ml-2 text-xs text-muted-foreground hover:text-foreground underline"
            >
              Clear filters
            </button>
          )}
          <span className="ml-auto text-xs text-muted-foreground">
            {loading ? "Loading..." : `${total.toLocaleString()} logs`}
          </span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="text-sm text-destructive bg-destructive/10 border border-destructive/40 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[130px_70px_140px_1fr_100px] gap-0 border-b border-border bg-background/50">
          {[
            { label: "Timestamp", field: "@timestamp" as SortField },
            { label: "Level",     field: "level" as SortField },
            { label: "Service",   field: "service" as SortField },
            { label: "Message",   field: "message" as SortField },
            { label: "Host",      field: null },
          ].map(({ label, field }) => (
            <button
              key={label}
              onClick={() => field && handleSort(field)}
              className={`px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground transition-colors ${
                field ? "hover:text-foreground" : "cursor-default"
              }`}
            >
              {label}
              {field && <SortIcon field={field} />}
            </button>
          ))}
        </div>

        {/* Rows */}
        <div className="divide-y divide-border/50 font-mono text-xs">
          {logs.length === 0 && !loading && (
            <div className="px-4 py-8 text-center text-muted-foreground">
              No logs found. Try adjusting your filters.
            </div>
          )}
          {logs.map((log) => {
            const lvl = (log.level ?? "INFO").toUpperCase();
            const dotClass = levelDot[lvl] ?? "bg-gray-500";
            const rowClass = lvl === "ERROR" || lvl === "CRITICAL"
              ? "hover:bg-destructive/5"
              : lvl === "WARN" || lvl === "WARNING"
              ? "hover:bg-warning/5"
              : "hover:bg-muted/40";

            return (
              <div
                key={log.id}
                className={`grid grid-cols-[130px_70px_140px_1fr_100px] gap-0 transition-colors ${rowClass}`}
              >
                <div className="px-3 py-1.5 text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis">
                  {fmt(log["@timestamp"] as string)}
                </div>
                <div className="px-3 py-1.5 flex items-center gap-1.5">
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${dotClass}`} />
                  <span className={
                    lvl === "ERROR" || lvl === "CRITICAL" ? "text-destructive"
                    : lvl === "WARN" || lvl === "WARNING" ? "text-warning"
                    : lvl === "INFO" ? "text-chart-1"
                    : "text-muted-foreground"
                  }>
                    {lvl}
                  </span>
                </div>
                <div className="px-3 py-1.5 text-muted-foreground truncate">
                  {log.service as string ?? "—"}
                </div>
                <div className="px-3 py-1.5 text-foreground truncate" title={log.message as string}>
                  {log.message as string ?? "—"}
                </div>
                <div className="px-3 py-1.5 text-muted-foreground truncate">
                  {log.host as string ?? "—"}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Page {currentPage} of {totalPages} · showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total.toLocaleString()}
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => fetchLogs(0)}
              disabled={currentPage === 1}
              className="px-2 py-1 rounded border border-border hover:border-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              «
            </button>
            <button
              onClick={() => fetchLogs(Math.max(0, offset - LIMIT))}
              disabled={currentPage === 1}
              className="px-2 py-1 rounded border border-border hover:border-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              ‹ Prev
            </button>
            <button
              onClick={() => fetchLogs(offset + LIMIT)}
              disabled={currentPage === totalPages}
              className="px-2 py-1 rounded border border-border hover:border-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next ›
            </button>
            <button
              onClick={() => fetchLogs((totalPages - 1) * LIMIT)}
              disabled={currentPage === totalPages}
              className="px-2 py-1 rounded border border-border hover:border-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              »
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
