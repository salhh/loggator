"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useSession } from "next-auth/react";
import {
  getStoredTenantId,
  setSessionAccessToken,
  setStoredAccessToken,
  setStoredTenantId,
} from "@/lib/auth-headers";
import { api, type TenantRow } from "@/lib/api";

type AuthContextValue = {
  /** Resolved bearer token: NextAuth session or legacy localStorage (dev). */
  accessToken: string | null;
  setAccessToken: (t: string | null) => void;
  tenantId: string | null;
  setTenantId: (id: string | null) => void;
  tenants: TenantRow[];
  tenantsError: string | null;
  refreshTenants: () => Promise<void>;
  authStatus: "loading" | "authenticated" | "unauthenticated";
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const [legacyToken, setLegacyToken] = useState<string | null>(null);
  const [tenantId, setTenantIdState] = useState<string | null>(null);
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [tenantsError, setTenantsError] = useState<string | null>(null);

  const sessionToken = session?.accessToken ?? null;
  const accessToken = sessionToken ?? legacyToken;

  useEffect(() => {
    setSessionAccessToken(sessionToken);
  }, [sessionToken]);

  useEffect(() => {
    setLegacyToken(null);
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("loggator_access_token");
      if (stored && !sessionToken) setLegacyToken(stored);
    }
    setTenantIdState(getStoredTenantId());
  }, [sessionToken]);

  const setAccessToken = useCallback(
    (t: string | null) => {
      if (t) {
        setStoredAccessToken(t);
        setLegacyToken(t);
        setSessionAccessToken(sessionToken ?? t);
        return;
      }
      setStoredAccessToken(null);
      setLegacyToken(null);
      if (!sessionToken) {
        setStoredTenantId(null);
        setTenantIdState(null);
        setTenants([]);
        setTenantsError(null);
      }
      setSessionAccessToken(sessionToken ?? null);
    },
    [sessionToken]
  );

  const setTenantId = useCallback((id: string | null) => {
    setStoredTenantId(id);
    setTenantIdState(id);
  }, []);

  const refreshTenants = useCallback(async () => {
    try {
      const list = await api.tenants();
      setTenants(list);
      setTenantsError(null);
      const stored = getStoredTenantId();
      if (list.length === 1) {
        const only = list[0].id;
        if (stored !== only) {
          setStoredTenantId(only);
          setTenantIdState(only);
        }
      }
    } catch (err) {
      setTenants([]);
      setTenantsError(err instanceof Error ? err.message : "Failed to load tenants");
    }
  }, []);

  useEffect(() => {
    if (status === "loading") return;
    void refreshTenants();
  }, [status, accessToken, refreshTenants]);

  const authStatus: "loading" | "authenticated" | "unauthenticated" =
    status === "loading"
      ? "loading"
      : session || legacyToken
        ? "authenticated"
        : "unauthenticated";

  const value = useMemo(
    () => ({
      accessToken,
      setAccessToken,
      tenantId,
      setTenantId,
      tenants,
      tenantsError,
      refreshTenants,
      authStatus,
    }),
    [accessToken, setAccessToken, tenantId, setTenantId, tenants, tenantsError, refreshTenants, authStatus]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
