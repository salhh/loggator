"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { decodeJwtExpiry } from "@/lib/auth-headers";
import { useAuth } from "./AuthProvider";

function useTokenExpiry(token: string | null) {
  const [label, setLabel] = useState<{ text: string; color: string } | null>(null);
  useEffect(() => {
    if (!token) {
      setLabel(null);
      return;
    }
    const exp = decodeJwtExpiry(token);
    if (exp === null) {
      setLabel(null);
      return;
    }
    function refresh() {
      const remaining = exp! - Math.floor(Date.now() / 1000);
      if (remaining <= 0) setLabel({ text: "Expired", color: "text-destructive" });
      else if (remaining <= 300) setLabel({ text: "Expires soon", color: "text-warning" });
      else setLabel({ text: `Expires in ${Math.floor(remaining / 60)}m`, color: "text-success" });
    }
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [token]);
  return label;
}

export default function TenantBar() {
  const { accessToken, tenantId, setTenantId, tenants, tenantsError, authStatus } = useAuth();
  const hasSession = authStatus === "authenticated" && !!accessToken;
  const expiryLabel = useTokenExpiry(accessToken);

  return (
    <div className="px-3 py-3 space-y-2 border-b border-sidebar-border text-xs">
      {authStatus === "loading" ? (
        <p className="text-muted-foreground">Session…</p>
      ) : hasSession ? (
        <div className="space-y-2">
          {expiryLabel && (
            <p className={`text-[10px] font-medium ${expiryLabel.color}`}>{expiryLabel.text}</p>
          )}
          <p className="text-[10px] text-muted-foreground">
            Tenant and profile controls are in the top bar.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <Link
            href="/login"
            className="block w-full text-center rounded-md bg-primary text-primary-foreground py-1.5 text-xs font-semibold hover:opacity-90"
          >
            Log in
          </Link>
          <p className="text-[10px] text-muted-foreground">
            SSO or dev token on the login page.
          </p>
        </div>
      )}

      {tenants.length > 1 ? (
        <>
          <label className="block text-muted-foreground pt-1">Tenant (sidebar)</label>
          <select
            value={tenantId ?? ""}
            onChange={(e) => setTenantId(e.target.value || null)}
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-foreground text-xs focus-visible:ring-2 focus-visible:ring-ring/80 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <option value="">Select tenant…</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.slug})
              </option>
            ))}
          </select>
        </>
      ) : tenants.length === 1 ? (
        <p className="text-muted-foreground pt-1 truncate text-[11px]" title={tenants[0].name}>
          {tenants[0].name}
        </p>
      ) : hasSession ? (
        <p className="text-muted-foreground pt-1 text-[11px]">
          {tenantsError ?? "No tenants visible."}
        </p>
      ) : null}
    </div>
  );
}
