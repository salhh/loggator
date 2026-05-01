"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type TenantRow } from "@/lib/api";
import type { BillingPlan, TenantBilling } from "@/lib/types";
import { Input } from "@/components/ui/input";
import PlanBadge from "@/components/platform/PlanBadge";

function EditPlanModal({
  plan,
  onClose,
  onSaved,
}: {
  plan: BillingPlan;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(plan.name);
  const [maxMembers, setMaxMembers] = useState(String(plan.max_members ?? ""));
  const [maxCalls, setMaxCalls] = useState(String(plan.max_api_calls_per_day ?? ""));
  const [maxVolume, setMaxVolume] = useState(String(plan.max_log_volume_mb_per_day ?? ""));
  const [price, setPrice] = useState(String(plan.price_usd_cents));
  const [isActive, setIsActive] = useState(plan.is_active);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.platformPatchBillingPlan(plan.id, {
        name: name.trim(),
        max_members: maxMembers ? Number(maxMembers) : null,
        max_api_calls_per_day: maxCalls ? Number(maxCalls) : null,
        max_log_volume_mb_per_day: maxVolume ? Number(maxVolume) : null,
        price_usd_cents: Number(price) || 0,
        is_active: isActive,
      });
      onSaved();
      onClose();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="rounded-lg border border-border bg-card p-6 w-full max-w-md space-y-4 shadow-xl">
        <h2 className="text-sm font-semibold text-foreground">Edit Plan: {plan.slug}</h2>
        <label className="text-xs text-muted-foreground block">
          Name
          <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 bg-background" />
        </label>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Max members (blank = unlimited)", val: maxMembers, set: setMaxMembers },
            { label: "Max API calls/day (blank = unlimited)", val: maxCalls, set: setMaxCalls },
            { label: "Max log volume MB/day (blank = unlimited)", val: maxVolume, set: setMaxVolume },
            { label: "Price (USD cents)", val: price, set: setPrice },
          ].map(({ label, val, set }) => (
            <label key={label} className="text-xs text-muted-foreground col-span-2 sm:col-span-1 block">
              {label}
              <Input type="number" min={0} value={val} onChange={(e) => set(e.target.value)} className="mt-1 bg-background font-mono text-sm" />
            </label>
          ))}
        </div>
        <label className="text-xs text-muted-foreground flex items-center gap-2">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Active
        </label>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 rounded border border-border text-sm text-muted-foreground hover:text-foreground">
            Cancel
          </button>
          <button disabled={saving} onClick={save} className="px-3 py-1.5 rounded bg-amber-400 text-black text-sm font-semibold disabled:opacity-40 hover:bg-amber-300 transition-colors">
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PlatformBillingPage() {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [billings, setBillings] = useState<Record<string, TenantBilling>>({});
  const [editingPlan, setEditingPlan] = useState<BillingPlan | null>(null);
  const [loading, setLoading] = useState(true);

  const loadPlans = useCallback(async () => {
    const p = await api.platformBillingPlans();
    setPlans(p);
    return p;
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, t] = await Promise.all([api.platformBillingPlans(), api.platformTenants()]);
      setPlans(p);
      setTenants(t);
      const billEntries = await Promise.allSettled(t.map((t) => api.platformTenantBilling(t.id)));
      const map: Record<string, TenantBilling> = {};
      billEntries.forEach((res, i) => {
        if (res.status === "fulfilled") map[t[i].id] = res.value;
      });
      setBillings(map);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="max-w-5xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Billing</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Manage plans and per-tenant assignments.</p>
      </div>

      {editingPlan && (
        <EditPlanModal plan={editingPlan} onClose={() => setEditingPlan(null)} onSaved={loadPlans} />
      )}

      {/* Plans table */}
      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <h2 className="text-sm font-medium text-foreground p-4 border-b border-border">Billing Plans</h2>
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground animate-pulse">Loading…</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="p-3 font-medium">Name</th>
                <th className="p-3 font-medium">Slug</th>
                <th className="p-3 font-medium">Max Members</th>
                <th className="p-3 font-medium">Max API Calls/Day</th>
                <th className="p-3 font-medium">Max Vol MB/Day</th>
                <th className="p-3 font-medium">Price</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium w-[80px]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.id} className="border-b border-border/60">
                  <td className="p-3 font-medium"><PlanBadge plan={p} /></td>
                  <td className="p-3 font-mono text-xs text-muted-foreground">{p.slug}</td>
                  <td className="p-3 text-muted-foreground">{p.max_members ?? "∞"}</td>
                  <td className="p-3 text-muted-foreground">{p.max_api_calls_per_day?.toLocaleString() ?? "∞"}</td>
                  <td className="p-3 text-muted-foreground">{p.max_log_volume_mb_per_day?.toLocaleString() ?? "∞"}</td>
                  <td className="p-3 text-muted-foreground">
                    {p.price_usd_cents > 0 ? `$${(p.price_usd_cents / 100).toFixed(2)}` : "Free"}
                  </td>
                  <td className="p-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${p.is_active ? "bg-green-950/40 text-green-300" : "bg-secondary text-muted-foreground"}`}>
                      {p.is_active ? "active" : "inactive"}
                    </span>
                  </td>
                  <td className="p-3">
                    <button onClick={() => setEditingPlan(p)} className="text-xs text-amber-400 hover:underline">Edit</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Tenant assignments */}
      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <h2 className="text-sm font-medium text-foreground p-4 border-b border-border">Tenant Assignments</h2>
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground animate-pulse">Loading…</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="p-3 font-medium">Tenant</th>
                <th className="p-3 font-medium">Plan</th>
                <th className="p-3 font-medium text-right">API Calls Today</th>
                <th className="p-3 font-medium text-right">Log Vol MB Today</th>
                <th className="p-3 font-medium">Limits</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => {
                const b = billings[t.id];
                return (
                  <tr key={t.id} className="border-b border-border/60">
                    <td className="p-3 font-medium">{t.name}</td>
                    <td className="p-3"><PlanBadge plan={b?.plan ?? null} /></td>
                    <td className="p-3 text-right font-mono text-xs">{b?.api_calls_today ?? 0}</td>
                    <td className="p-3 text-right font-mono text-xs">{b?.log_volume_mb_today ?? 0}</td>
                    <td className="p-3">
                      {b?.limits_exceeded ? (
                        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-red-950/40 text-red-300">Exceeded</span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-green-950/40 text-green-300">OK</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
