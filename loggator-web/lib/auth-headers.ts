const TOKEN_KEY = "loggator_access_token";
const TENANT_KEY = "loggator_tenant_id";

/** Set by AuthProvider from NextAuth session (takes precedence over localStorage). */
let sessionAccessToken: string | null = null;

export function setSessionAccessToken(token: string | null): void {
  sessionAccessToken = token;
}

export function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredAccessToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getStoredTenantId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TENANT_KEY);
}

export function setStoredTenantId(id: string | null): void {
  if (typeof window === "undefined") return;
  if (id) localStorage.setItem(TENANT_KEY, id);
  else localStorage.removeItem(TENANT_KEY);
}

/** Decode JWT `exp` (seconds since epoch), or null if missing / not a JWT. */
export function decodeJwtExpiry(jwt: string): number | null {
  const parts = jwt.split(".");
  if (parts.length < 2) return null;
  try {
    const payload = parts[1];
    const json = JSON.parse(
      atob(payload.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(payload.length / 4) * 4, "="))
    ) as { exp?: unknown };
    return typeof json.exp === "number" ? json.exp : null;
  } catch {
    return null;
  }
}

/** Bearer token for browser: session (OIDC) or pasted localStorage token. */
export function getBrowserAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionAccessToken ?? getStoredAccessToken();
}

/** Headers for browser calls to the API (Bearer + optional X-Tenant-Id). */
export function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  const token = getBrowserAccessToken();
  const tid = getStoredTenantId();
  if (token) h.Authorization = `Bearer ${token}`;
  if (tid) h["X-Tenant-Id"] = tid;
  return h;
}
