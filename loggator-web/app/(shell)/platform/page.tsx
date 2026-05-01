"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type TenantRow } from "@/lib/api";
import StatCard from "@/components/StatCard";
import type { SystemEventsResponse } from "@/lib/types";

export default function PlatformOverviewPage() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [events, setEvents] = useState<SystemEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [t, e] = await Promise.allSettled([
      api.platformTenants(),
      api.systemEvents({ limit: 5 }),
    ]);
    if (t.status === "fulfilled") setTenants(t.value);
    if (e.status === "fulfilled") setEvents(e.value);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const total = tenants.length;
  const active = tenants.filter((t) => t.status === "active").length;
  const suspended = tenants.filter((t) => t.status === "suspended").length;
  const totalMembers = tenants.reduce((sum, t) => sum + (t.member_count ?? 0), 0);

  const sections = [
    { href: "/platform/tenants", label: "Tenants", desc: "Manage all tenants, members, and connections" },
    { href: "/platform/billing", label: "Billing", desc: "Assign plans, track usage and limits" },
    { href: "/platform/audit-log", label: "Audit Log", desc: "Cross-tenant request history and actor tracking" },
    { href: "/platform/settings", label: "Platform Settings", desc: "Configure global platform environment" },
  ];

  return (
    <div className="max-w-5xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Platform Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">Super admin view — platform-wide metrics and quick access.</p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground animate-pulse">Loading…</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Total Tenants" value={total} borderColor="border-l-warning" />
          <StatCard label="Active" value={active} borderColor="border-l-success" />
          <StatCard label="Suspended" value={suspended} borderColor="border-l-destructive" />
          <StatCard label="Total Members" value={totalMembers} borderColor="border-l-primary" />
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {sections.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="rounded-lg border border-border bg-card p-4 hover:border-primary/45 hover:bg-primary/5 transition-colors group"
          >
            <div className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{s.label}</div>
            <div className="text-xs text-muted-foreground mt-1">{s.desc}</div>
          </Link>
        ))}
      </div>

      {events && events.events.length > 0 && (
        <section className="rounded-lg border border-border bg-card overflow-hidden">
          <h2 className="text-sm font-medium text-foreground p-4 border-b border-border">Recent System Events</h2>
          <table className="w-full text-sm">
            <tbody>
              {events.events.map((ev) => (
                <tr key={ev.id} className="border-b border-border/60 last:border-0">
                  <td className="p-3 text-xs text-muted-foreground w-[140px]">
                    {new Date(ev.timestamp).toLocaleString()}
                  </td>
                  <td className="p-3 font-mono text-xs text-muted-foreground w-[100px]">{ev.service}</td>
                  <td className="p-3">
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-medium mr-2 ${
                        ev.severity === "error" || ev.severity === "critical"
                          ? "bg-destructive/12 text-destructive"
                          : ev.severity === "warning"
                          ? "bg-warning/12 text-warning"
                          : "bg-primary/12 text-primary"
                      }`}
                    >
                      {ev.severity}
                    </span>
                    {ev.message}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
