"use client";

import { useEffect, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import {
  decodeJwtExpiry,
  setSessionAccessToken,
  setStoredAccessToken,
  setStoredTenantId,
} from "@/lib/auth-headers";
import { useAuth } from "./AuthProvider";

function useTokenExpiry(token: string | null) {
  const [label, setLabel] = useState<{ text: string; color: string } | null>(null);
  useEffect(() => {
    if (!token) { setLabel(null); return; }
    const exp = decodeJwtExpiry(token);
    if (exp === null) { setLabel(null); return; }
    function refresh() {
      const remaining = exp! - Math.floor(Date.now() / 1000);
      if (remaining <= 0) setLabel({ text: "Expired", color: "text-red-500" });
      else if (remaining <= 300) setLabel({ text: "Expires soon", color: "text-amber-500" });
      else setLabel({ text: `Expires in ${Math.floor(remaining / 60)}m`, color: "text-green-500" });
    }
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [token]);
  return label;
}

export default function TenantBar() {
  const { data: session } = useSession();
  const { accessToken, tenantId, setTenantId, tenants, tenantsError, authStatus, setAccessToken } =
    useAuth();
  const hasSession = authStatus === "authenticated" && !!accessToken;
  const expiryLabel = useTokenExpiry(accessToken);

  async function handleLogout() {
    setStoredAccessToken(null);
    setStoredTenantId(null);
    setSessionAccessToken(null);
    if (session) await signOut({ callbackUrl: "/login" });
    else {
      setAccessToken(null);
      if (typeof window !== "undefined") window.location.href = "/login";
    }
  }

  return (
    <div className="px-3 py-3 space-y-2 border-b border-border text-xs">
      {authStatus === "loading" ? (
        <p className="text-muted-foreground">Session…</p>
      ) : hasSession ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span
              className="text-muted-foreground truncate"
              title={session?.user?.email ?? session?.user?.name ?? "Signed in"}
            >
              {session?.user?.email || session?.user?.name || "Signed in"}
            </span>
            <button
              type="button"
              onClick={() => void handleLogout()}
              className="shrink-0 text-cyan-400 hover:underline"
            >
              Log out
            </button>
          </div>
          {expiryLabel && (
            <p className={`text-[10px] font-medium ${expiryLabel.color}`}>{expiryLabel.text}</p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <a
            href="/login"
            className="block w-full text-center rounded-md bg-cyan-400 text-black py-1.5 text-xs font-semibold hover:bg-cyan-300"
          >
            Log in
          </a>
          <p className="text-[10px] text-muted-foreground">
            Use SSO or a dev token on the login page (session required to browse the app).
          </p>
        </div>
      )}

      {tenants.length > 1 ? (
        <>
          <label className="block text-muted-foreground pt-1">Tenant</label>
          <select
            value={tenantId ?? ""}
            onChange={(e) => setTenantId(e.target.value || null)}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-foreground"
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
        <p className="text-muted-foreground pt-1 truncate" title={tenants[0].name}>
          Tenant: {tenants[0].name}
        </p>
      ) : hasSession ? (
        <p className="text-muted-foreground pt-1">
          {tenantsError ?? "No tenants visible — check membership or token."}
        </p>
      ) : null}
    </div>
  );
}
