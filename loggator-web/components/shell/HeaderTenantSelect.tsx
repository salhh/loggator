"use client";

import { useAuth } from "@/components/AuthProvider";

/** Compact tenant switcher for the app header. */
export function HeaderTenantSelect() {
  const { tenantId, setTenantId, tenants, authStatus } = useAuth();
  const hasSession = authStatus === "authenticated";

  if (!hasSession || tenants.length === 0) return null;

  if (tenants.length === 1) {
    return (
      <span
        className="hidden md:inline text-xs text-muted-foreground truncate max-w-[140px]"
        title={tenants[0].name}
      >
        {tenants[0].name}
      </span>
    );
  }

  return (
    <select
      value={tenantId ?? ""}
      onChange={(e) => setTenantId(e.target.value || null)}
      className="h-8 max-w-[160px] md:max-w-[220px] rounded-md border border-input bg-background px-2 text-xs text-foreground focus-visible:ring-2 focus-visible:ring-ring/80 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      aria-label="Active tenant"
    >
      <option value="">Tenant…</option>
      {tenants.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}
