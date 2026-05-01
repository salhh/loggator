"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type TenantRow } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";

function StatusBadge({ code }: { code: number | null }) {
  if (code === null) return <span className="text-muted-foreground">—</span>;
  const cls =
    code >= 500 ? "bg-red-950/40 text-red-300"
    : code >= 400 ? "bg-amber-950/40 text-amber-300"
    : "bg-green-950/40 text-green-300";
  return <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-mono font-medium ${cls}`}>{code}</span>;
}

function MethodBadge({ method }: { method: string }) {
  const colors: Record<string, string> = {
    GET: "text-cyan-300", POST: "text-green-300", PATCH: "text-amber-300",
    PUT: "text-blue-300", DELETE: "text-red-300",
  };
  return <span className={`font-mono text-xs font-medium ${colors[method] ?? "text-muted-foreground"}`}>{method}</span>;
}

function exportCsv(rows: AuditLogEntry[]) {
  const headers = ["id", "tenant_id", "timestamp", "method", "path", "status_code", "duration_ms", "actor_id", "client_ip"];
  const lines = [
    headers.join(","),
    ...rows.map((r) =>
      headers.map((h) => {
        const v = r[h as keyof AuditLogEntry];
        const s = v == null ? "" : String(v);
        return s.includes(",") || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(",")
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `audit-log-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const LIMIT = 100;

export default function PlatformAuditLogViewer() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [rows, setRows] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Filters
  const [filterTenant, setFilterTenant] = useState("");
  const [filterPath, setFilterPath] = useState("");
  const [filterMethod, setFilterMethod] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterActor, setFilterActor] = useState("");
  const [filterFrom, setFilterFrom] = useState("");
  const [filterTo, setFilterTo] = useState("");

  useEffect(() => {
    api.platformTenants().then(setTenants).catch(() => {});
  }, []);

  const fetch = useCallback(async (off = 0) => {
    setLoading(true);
    try {
      const data = await api.platformAuditLog({
        tenant_id: filterTenant || undefined,
        path: filterPath || undefined,
        method: filterMethod || undefined,
        status: filterStatus || undefined,
        actor_id: filterActor || undefined,
        from_ts: filterFrom || undefined,
        to_ts: filterTo || undefined,
        limit: LIMIT,
        offset: off,
      });
      setRows(data);
      setOffset(off);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [filterTenant, filterPath, filterMethod, filterStatus, filterActor, filterFrom, filterTo]);

  useEffect(() => { void fetch(0); }, [fetch]);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (autoRefresh) {
      timerRef.current = setInterval(() => void fetch(0), 30_000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [autoRefresh, fetch]);

  const tenantName = (id: string | null) => {
    if (!id) return "—";
    return tenants.find((t) => t.id === id)?.name ?? id.slice(0, 8) + "…";
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Tenant</label>
          <select
            value={filterTenant}
            onChange={(e) => setFilterTenant(e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          >
            <option value="">All tenants</option>
            {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Method</label>
          <select
            value={filterMethod}
            onChange={(e) => setFilterMethod(e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          >
            <option value="">Any</option>
            {["GET", "POST", "PATCH", "PUT", "DELETE"].map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Status</label>
          <input
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            placeholder="e.g. 200 or 5"
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm font-mono"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Path prefix</label>
          <input
            value={filterPath}
            onChange={(e) => setFilterPath(e.target.value)}
            placeholder="/api/v1/…"
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm font-mono"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Actor ID</label>
          <input
            value={filterActor}
            onChange={(e) => setFilterActor(e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm font-mono"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">From</label>
          <input
            type="datetime-local"
            value={filterFrom}
            onChange={(e) => setFilterFrom(e.target.value ? new Date(e.target.value).toISOString() : "")}
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">To</label>
          <input
            type="datetime-local"
            value={filterTo}
            onChange={(e) => setFilterTo(e.target.value ? new Date(e.target.value).toISOString() : "")}
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => void fetch(0)}
          disabled={loading}
          className="px-3 py-1.5 rounded bg-amber-400 text-black text-sm font-semibold hover:bg-amber-300 disabled:opacity-40 transition-colors"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
        <button
          onClick={() => exportCsv(rows)}
          disabled={rows.length === 0}
          className="px-3 py-1.5 rounded border border-border text-sm text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
        >
          Export CSV
        </button>
        <label className="text-xs text-muted-foreground flex items-center gap-1.5 ml-auto">
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
          Auto-refresh (30s)
        </label>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="p-3 font-medium w-[150px]">Timestamp</th>
              <th className="p-3 font-medium">Tenant</th>
              <th className="p-3 font-medium w-[70px]">Method</th>
              <th className="p-3 font-medium">Path</th>
              <th className="p-3 font-medium w-[60px]">Status</th>
              <th className="p-3 font-medium w-[80px] text-right">ms</th>
              <th className="p-3 font-medium">Actor</th>
              <th className="p-3 font-medium">IP</th>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr><td colSpan={8} className="p-4 text-center text-muted-foreground animate-pulse">Loading…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={8} className="p-4 text-center text-muted-foreground">No results.</td></tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} className="border-b border-border/60 hover:bg-secondary/30">
                  <td className="p-3 font-mono text-muted-foreground">{new Date(r.timestamp).toLocaleString()}</td>
                  <td className="p-3">
                    {r.tenant_id ? (
                      <a href={`/platform/tenants/${r.tenant_id}`} className="text-amber-400 hover:underline" onClick={(e) => e.stopPropagation()}>
                        {tenantName(r.tenant_id)}
                      </a>
                    ) : <span className="text-muted-foreground">platform</span>}
                  </td>
                  <td className="p-3"><MethodBadge method={r.method} /></td>
                  <td className="p-3 font-mono text-muted-foreground max-w-[200px] truncate" title={r.path}>{r.path}</td>
                  <td className="p-3"><StatusBadge code={r.status_code} /></td>
                  <td className="p-3 text-right font-mono text-muted-foreground">{r.duration_ms ?? "—"}</td>
                  <td className="p-3 font-mono text-muted-foreground truncate max-w-[100px]" title={r.actor_id ?? ""}>{r.actor_id ?? "—"}</td>
                  <td className="p-3 font-mono text-muted-foreground">{r.client_ip ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center gap-3 text-sm">
        <button
          disabled={offset === 0}
          onClick={() => void fetch(Math.max(0, offset - LIMIT))}
          className="px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground disabled:opacity-40"
        >
          Previous
        </button>
        <span className="text-muted-foreground text-xs">Showing {offset + 1}–{offset + rows.length}</span>
        <button
          disabled={rows.length < LIMIT}
          onClick={() => void fetch(offset + LIMIT)}
          className="px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
