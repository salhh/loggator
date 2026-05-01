import type { Summary, Anomaly, Alert, StatusResponse, AnalysisReport, ScheduledAnalysis, ScheduleStatus, HealthResponse, StatsResponse, SystemEventsResponse, SystemEvent, AuditLogEntry } from "./types";
import { authHeaders } from "./auth-headers";

// API_URL is only available server-side (no NEXT_PUBLIC_ prefix).
// NEXT_PUBLIC_API_URL is used by the browser. Fall back to localhost for dev.
const BASE =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

export type TenantRow = { id: string; name: string; slug: string; status: string; created_at: string };

export type AuthMeResponse = {
  user_id: string;
  email: string;
  roles: string[];
  platform_roles: string[];
  tenant_id?: string | null;
  tenant_ids?: string[];
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail))
        detail = j.detail.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join("; ");
    } catch {
      /* ignore */
    }
    throw new Error(detail || `API error ${res.status}: ${path}`);
  }
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `API error ${res.status}: ${path}`);
  }
  return res.json();
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `API error ${res.status}: ${path}`);
  }
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE", headers: { ...authHeaders() } });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `API error ${res.status}: ${path}`);
  }
  return res.json();
}

export const api = {
  authMe: () => get<AuthMeResponse>("/auth/me"),
  tenants: () => get<TenantRow[]>("/tenants"),
  status: () => get<StatusResponse>("/status"),
  summaries: (limit = 20, offset = 0) =>
    get<Summary[]>(`/summaries?limit=${limit}&offset=${offset}`),
  summary: (id: string) => get<Summary>(`/summaries/${id}`),
  anomalies: (limit = 50, severity?: string) =>
    get<Anomaly[]>(`/anomalies?limit=${limit}${severity ? `&severity=${severity}` : ""}`),
  anomaly: (id: string) => get<Anomaly>(`/anomalies/${id}`),
  alerts: (limit = 50, channel?: string) =>
    get<Alert[]>(`/alerts?limit=${limit}${channel ? `&channel=${channel}` : ""}`),
  testAlert: (channel: "slack" | "email" | "telegram" | "webhook") =>
    post<{ ok: boolean; error?: string }>(`/alerts/test?channel=${channel}`, {}),
  settings: () => get<{ settings: Record<string, string>; env_file: string }>("/settings"),
  updateSettings: (updates: Record<string, string>) =>
    put<{ settings: Record<string, string>; env_file: string }>("/settings", { updates }),
  chat: (message: string, top_k = 10) =>
    post<{ answer: string; context_logs: string[] }>("/chat", { message, top_k }),
  triggerIndex: (index_pattern?: string, hours_back = 1, size = 500) =>
    post<{ message: string }>("/chat/index", { index_pattern, hours_back, size }),
  logIndices: () =>
    fetch(`${BASE.replace("/api/v1", "")}/api/v1/logs/indices`, {
      headers: { ...authHeaders() },
    }).then((r) => r.json()) as Promise<{ indices: string[] }>,
  triggerBatch: () => post<{ message: string }>("/batch/trigger", {}),
  analyzeLogs: (index_pattern?: string, hours_back = 1, size = 500) =>
    post<AnalysisReport>("/chat/analyze", { index_pattern, hours_back, size }),
  scheduleStatus: () =>
    get<ScheduleStatus>("/schedule/status"),
  updateSchedule: (body: { enabled?: boolean; interval_minutes?: number; window_minutes?: number }) =>
    put<ScheduleStatus>("/schedule", body),
  analysisReports: (limit = 50, offset = 0) =>
    get<ScheduledAnalysis[]>(`/analysis-reports?limit=${limit}&offset=${offset}`),
  analysisReport: (id: string) =>
    get<ScheduledAnalysis>(`/analysis-reports/${id}`),
  health: () =>
    get<HealthResponse>("/health"),
  stats: (days = 7) =>
    get<StatsResponse>(`/stats?days=${days}`),
  systemEvents: (params?: {
    service?: string;
    severity?: string;
    event_type?: string;
    from_ts?: string;
    to_ts?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.service) qs.set("service", params.service);
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.event_type) qs.set("event_type", params.event_type);
    if (params?.from_ts) qs.set("from_ts", params.from_ts);
    if (params?.to_ts) qs.set("to_ts", params.to_ts);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return get<SystemEventsResponse>(`/system-events${q ? `?${q}` : ""}`);
  },
  systemEvent: (id: string) => get<SystemEvent>(`/system-events/${id}`),
  auditLog: (params?: {
    path?: string;
    method?: string;
    status?: string;
    from_ts?: string;
    to_ts?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.path) qs.set("path", params.path);
    if (params?.method) qs.set("method", params.method);
    if (params?.status) qs.set("status", params.status);
    if (params?.from_ts) qs.set("from_ts", params.from_ts);
    if (params?.to_ts) qs.set("to_ts", params.to_ts);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return get<AuditLogEntry[]>(`/audit-log${q ? `?${q}` : ""}`);
  },
  createTenantApiKey: (name: string) =>
    post<{
      id: string;
      name: string;
      key_prefix: string;
      key: string;
      scopes: string[];
      created_at: string;
    }>("/tenant-api-keys", { name, scopes: ["ingest"] }),
  listTenantApiKeys: () =>
    get<
      Array<{
        id: string;
        name: string;
        key_prefix: string;
        scopes: string[];
        created_at: string;
        last_used_at: string | null;
        revoked_at: string | null;
      }>
    >("/tenant-api-keys"),
  revokeTenantApiKey: (id: string) => post<{ ok: boolean }>(`/tenant-api-keys/${id}/revoke`, {}),

  platformTenants: () => get<TenantRow[]>("/platform/tenants"),
  platformTenant: (id: string) => get<TenantRow>(`/platform/tenants/${id}`),
  platformCreateTenant: (body: {
    name: string;
    slug: string;
    admin_subject?: string | null;
    admin_email?: string | null;
  }) => post<TenantRow>("/platform/tenants", body),
  platformPatchTenant: (id: string, body: { name?: string; slug?: string; status?: string }) =>
    patch<TenantRow>(`/platform/tenants/${id}`, body),
  platformUsers: (search?: string) =>
    get<Array<{ id: string; subject: string; email: string; created_at: string }>>(
      `/platform/users${search ? `?search=${encodeURIComponent(search)}` : ""}`
    ),

  tenantMembers: () =>
    get<
      Array<{
        membership_id: string;
        user_id: string;
        subject: string;
        email: string;
        role: string;
        created_at: string;
      }>
    >("/tenant/members"),
  addTenantMember: (body: { subject: string; email?: string; role?: string }) =>
    post<{
      membership_id: string;
      user_id: string;
      subject: string;
      email: string;
      role: string;
      created_at: string;
    }>("/tenant/members", body),
  patchTenantMember: (membershipId: string, body: { role: string }) =>
    patch<{
      membership_id: string;
      user_id: string;
      subject: string;
      email: string;
      role: string;
      created_at: string;
    }>(`/tenant/members/${membershipId}`, body),
  removeTenantMember: (membershipId: string) => del<{ ok: boolean }>(`/tenant/members/${membershipId}`),
};
