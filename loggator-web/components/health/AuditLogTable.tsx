"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";

const METHOD_COLOR: Record<string, string> = {
  GET: "text-emerald-400",
  POST: "text-sky-400",
  PUT: "text-amber-400",
  DELETE: "text-red-400",
  PATCH: "text-purple-400",
};

function statusColor(code: number | null): string {
  if (!code) return "text-muted-foreground";
  if (code < 300) return "text-emerald-400";
  if (code < 400) return "text-sky-400";
  if (code < 500) return "text-amber-400";
  return "text-red-400";
}

export default function AuditLogTable() {
  const [rows, setRows] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterPath, setFilterPath] = useState("");
  const [filterMethod, setFilterMethod] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [fetched, setFetched] = useState(false);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.auditLog({
        path: filterPath || undefined,
        method: filterMethod || undefined,
        status: filterStatus || undefined,
        limit: 100,
      });
      setRows(data);
      setFetched(true);
    } catch {
      // keep stale data
    } finally {
      setLoading(false);
    }
  }, [filterPath, filterMethod, filterStatus]);

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="/api/v1/..."
          value={filterPath}
          onChange={(e) => setFilterPath(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground placeholder:text-muted-foreground w-44"
        />
        <select
          value={filterMethod}
          onChange={(e) => setFilterMethod(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All methods</option>
          {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All statuses</option>
          <option value="2">2xx</option>
          <option value="3">3xx</option>
          <option value="4">4xx</option>
          <option value="5">5xx</option>
        </select>
        <button
          onClick={fetchRows}
          disabled={loading}
          className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors disabled:opacity-40"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-lg overflow-x-auto">
        {!fetched ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            Click Refresh to load audit logs
          </div>
        ) : rows.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No entries</div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left px-3 py-2 font-medium">Time</th>
                <th className="text-left px-3 py-2 font-medium">Method · Path</th>
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-left px-3 py-2 font-medium">Duration</th>
                <th className="text-left px-3 py-2 font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-border last:border-0 hover:bg-secondary/40"
                >
                  <td className="px-3 py-2 font-mono text-muted-foreground whitespace-nowrap">
                    {new Date(r.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="px-3 py-2 font-mono">
                    <span className={`${METHOD_COLOR[r.method] ?? ""} mr-1.5`}>{r.method}</span>
                    <span className="text-foreground">{r.path}</span>
                  </td>
                  <td className={`px-3 py-2 font-mono font-semibold ${statusColor(r.status_code)}`}>
                    {r.status_code ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {r.duration_ms != null ? `${r.duration_ms}ms` : "—"}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground font-mono">
                    {r.client_ip ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
