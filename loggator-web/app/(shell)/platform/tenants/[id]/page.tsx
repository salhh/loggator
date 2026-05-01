"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type TenantRow } from "@/lib/api";
import type { TenantBilling, TenantStats, TenantConnection, BillingPlan } from "@/lib/types";
import { Input } from "@/components/ui/input";
import StatCard from "@/components/StatCard";
import TenantMembersPanel from "@/components/platform/TenantMembersPanel";

const TABS = ["Overview", "Connection", "Members", "Billing", "Stats"] as const;
type Tab = (typeof TABS)[number];

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
        status === "active" ? "bg-green-950/40 text-green-300" : "bg-red-950/40 text-red-300"
      }`}
    >
      {status}
    </span>
  );
}

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("Overview");

  const [tenant, setTenant] = useState<TenantRow | null>(null);
  const [editName, setEditName] = useState("");
  const [editSlug, setEditSlug] = useState("");
  const [saving, setSaving] = useState(false);

  const [conn, setConn] = useState<TenantConnection | null>(null);
  const [connForm, setConnForm] = useState<Partial<TenantConnection>>({});
  const [connSaving, setConnSaving] = useState(false);

  const [billing, setBilling] = useState<TenantBilling | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [billingSaving, setBillingSaving] = useState(false);

  const [stats, setStats] = useState<TenantStats | null>(null);

  const loadTenant = useCallback(async () => {
    const t = await api.platformTenant(id);
    setTenant(t);
    setEditName(t.name);
    setEditSlug(t.slug);
  }, [id]);

  useEffect(() => { void loadTenant(); }, [loadTenant]);

  useEffect(() => {
    if (tab === "Connection" && !conn) {
      api.platformTenantConnection(id).then((c) => {
        setConn(c);
        setConnForm(c ?? {});
      }).catch(() => {});
    }
    if (tab === "Billing" && !billing) {
      Promise.all([api.platformTenantBilling(id), api.platformBillingPlans()]).then(([b, p]) => {
        setBilling(b);
        setPlans(p);
        setSelectedPlanId(b.plan_id ?? "");
      }).catch(() => {});
    }
    if (tab === "Stats" && !stats) {
      api.platformTenantStats(id).then(setStats).catch(() => {});
    }
  }, [tab, id, conn, billing, stats]);

  if (!tenant) {
    return <p className="text-sm text-muted-foreground animate-pulse p-4">Loading…</p>;
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">{tenant.name}</h1>
        <p className="text-xs text-muted-foreground mt-0.5 font-mono">{tenant.slug} · <StatusBadge status={tenant.status} /></p>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              tab === t
                ? "text-amber-400 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-amber-400"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Overview ─────────────────────────────────────────────────────── */}
      {tab === "Overview" && (
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h2 className="text-sm font-medium">Edit Details</h2>
            <label className="text-xs text-muted-foreground block">
              Name
              <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="mt-1 bg-background" />
            </label>
            <label className="text-xs text-muted-foreground block">
              Slug
              <Input value={editSlug} onChange={(e) => setEditSlug(e.target.value)} className="mt-1 bg-background font-mono text-sm" />
            </label>
            <div className="flex gap-2">
              <button
                disabled={saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    const t = await api.platformPatchTenant(id, { name: editName.trim(), slug: editSlug.trim() });
                    setTenant(t);
                  } catch (e) { alert(e instanceof Error ? e.message : "Save failed"); }
                  finally { setSaving(false); }
                }}
                className="px-3 py-1.5 rounded bg-amber-400 text-black text-sm font-semibold hover:bg-amber-300 disabled:opacity-40 transition-colors"
              >
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                onClick={async () => {
                  const next = tenant.status === "active" ? "suspended" : "active";
                  if (!confirm(`${next === "suspended" ? "Suspend" : "Activate"} this tenant?`)) return;
                  try {
                    const t = await api.platformPatchTenant(id, { status: next });
                    setTenant(t);
                  } catch (e) { alert(e instanceof Error ? e.message : "Failed"); }
                }}
                className={`px-3 py-1.5 rounded border text-sm font-medium transition-colors ${
                  tenant.status === "active"
                    ? "border-red-500/50 text-red-300 hover:bg-red-950/30"
                    : "border-green-500/50 text-green-300 hover:bg-green-950/30"
                }`}
              >
                {tenant.status === "active" ? "Suspend" : "Activate"}
              </button>
            </div>
          </div>
          <div className="rounded-md border border-border divide-y divide-border/50 text-xs">
            {[
              { label: "ID", value: tenant.id },
              { label: "Created", value: new Date(tenant.created_at).toLocaleString() },
              { label: "Status", value: <StatusBadge status={tenant.status} /> },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center gap-3 px-3 py-2">
                <span className="text-muted-foreground w-20">{label}</span>
                <span className="font-mono text-foreground flex-1">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Connection ───────────────────────────────────────────────────── */}
      {tab === "Connection" && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-sm font-medium">OpenSearch Connection</h2>
          <p className="text-xs text-muted-foreground">Leave blank to inherit global settings.</p>
          {(["opensearch_host", "opensearch_port", "opensearch_auth_type", "opensearch_username", "opensearch_password", "opensearch_api_key", "aws_region", "opensearch_index_pattern"] as const).map((field) => (
            <label key={field} className="text-xs text-muted-foreground block">
              {field.replace(/_/g, " ")}
              <Input
                value={String(connForm[field] ?? "")}
                onChange={(e) => setConnForm((p) => ({ ...p, [field]: e.target.value || null }))}
                className="mt-1 bg-background font-mono text-sm"
                type={field.includes("password") || field.includes("api_key") ? "password" : "text"}
              />
            </label>
          ))}
          <div className="flex gap-3 items-center">
            {(["opensearch_use_ssl", "opensearch_verify_certs"] as const).map((f) => (
              <label key={f} className="text-xs text-muted-foreground flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={!!connForm[f]}
                  onChange={(e) => setConnForm((p) => ({ ...p, [f]: e.target.checked }))}
                />
                {f.replace("opensearch_", "").replace(/_/g, " ")}
              </label>
            ))}
          </div>
          <button
            disabled={connSaving}
            onClick={async () => {
              setConnSaving(true);
              try {
                await api.platformPutTenantConnection(id, connForm);
              } catch (e) { alert(e instanceof Error ? e.message : "Save failed"); }
              finally { setConnSaving(false); }
            }}
            className="px-3 py-1.5 rounded bg-amber-400 text-black text-sm font-semibold hover:bg-amber-300 disabled:opacity-40 transition-colors"
          >
            {connSaving ? "Saving…" : "Save Connection"}
          </button>
        </div>
      )}

      {/* ── Members ──────────────────────────────────────────────────────── */}
      {tab === "Members" && (
        <TenantMembersPanel tenantId={id} />
      )}

      {/* ── Billing ──────────────────────────────────────────────────────── */}
      {tab === "Billing" && billing && (
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h2 className="text-sm font-medium">Plan Assignment</h2>
            <label className="text-xs text-muted-foreground block">
              Billing Plan
              <select
                value={selectedPlanId}
                onChange={(e) => setSelectedPlanId(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
              >
                <option value="">— Unassigned —</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} {p.price_usd_cents > 0 ? `($${(p.price_usd_cents / 100).toFixed(2)}/mo)` : "(free)"}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={billingSaving}
              onClick={async () => {
                setBillingSaving(true);
                try {
                  const b = await api.platformPutTenantBilling(id, { plan_id: selectedPlanId || null });
                  setBilling(b);
                } catch (e) { alert(e instanceof Error ? e.message : "Save failed"); }
                finally { setBillingSaving(false); }
              }}
              className="px-3 py-1.5 rounded bg-amber-400 text-black text-sm font-semibold hover:bg-amber-300 disabled:opacity-40 transition-colors"
            >
              {billingSaving ? "Saving…" : "Save Plan"}
            </button>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 space-y-2">
            <h2 className="text-sm font-medium mb-2">Today&apos;s Usage</h2>
            {billing.limits_exceeded && (
              <div className="rounded border border-red-500/40 bg-red-950/30 px-3 py-1.5 text-xs text-red-200 mb-2">
                Limits exceeded
              </div>
            )}
            <div className="rounded-md border border-border divide-y divide-border/50 text-xs">
              {[
                { label: "API calls today", value: billing.api_calls_today, limit: billing.plan?.max_api_calls_per_day },
                { label: "Log volume MB today", value: billing.log_volume_mb_today, limit: billing.plan?.max_log_volume_mb_per_day },
              ].map(({ label, value, limit }) => (
                <div key={label} className="flex items-center justify-between px-3 py-2">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-mono">{value}{limit != null ? ` / ${limit}` : ""}</span>
                </div>
              ))}
            </div>
            <button
              onClick={async () => {
                if (!confirm("Reset today's usage counters to zero?")) return;
                try {
                  await api.platformResetBillingCounters(id);
                  const b = await api.platformTenantBilling(id);
                  setBilling(b);
                } catch (e) { alert(e instanceof Error ? e.message : "Reset failed"); }
              }}
              className="text-xs text-amber-400 hover:underline mt-1"
            >
              Reset counters
            </button>
          </div>
        </div>
      )}

      {/* ── Stats ────────────────────────────────────────────────────────── */}
      {tab === "Stats" && (
        stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Members" value={stats.member_count} borderColor="border-l-amber-400" />
            <StatCard label="Anomalies" value={stats.anomaly_count} borderColor="border-l-red-500" />
            <StatCard label="Summaries" value={stats.summary_count} borderColor="border-l-cyan-400" />
            <StatCard label="API Keys" value={stats.api_key_count} borderColor="border-l-green-500" />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground animate-pulse">Loading stats…</p>
        )
      )}
    </div>
  );
}
