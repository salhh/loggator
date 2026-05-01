import type { Summary, Anomaly, Alert, StatusResponse, AnalysisReport, ScheduledAnalysis, ScheduleStatus, HealthResponse, StatsResponse, SystemEventsResponse, SystemEvent, AuditLogEntry, BillingPlan, TenantBilling, TenantStats, TenantConnection, TenantIntegration, Incident, IncidentComment, DetectionRule } from "./types";
import { authHeaders } from "./auth-headers";

// API_URL is only available server-side (no NEXT_PUBLIC_ prefix).
// NEXT_PUBLIC_API_URL is used by the browser. Fall back to localhost for dev.
const BASE =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

export type TenantRow = {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
  member_count: number;
  parent_tenant_id?: string | null;
  is_operator?: boolean;
};

export type AuthMeResponse = {
  user_id: string;
  email: string;
  roles: string[];
  platform_roles: string[];
  tenant_id?: string | null;
  tenant_ids?: string[];
  operator_tenant_id?: string | null;
  operator_tenant_name?: string | null;
  operator_tenant_slug?: string | null;
};

export type SupportThread = {
  id: string;
  tenant_id: string;
  operator_tenant_id: string;
  status: string;
  subject: string;
  created_at: string;
  updated_at: string;
};

export type SupportMessage = {
  id: string;
  thread_id: string;
  author_user_id: string | null;
  body: string;
  is_staff: boolean;
  created_at: string;
};

export type SupportThreadDetail = SupportThread & { messages: SupportMessage[] };

function extraHeaders(xTenantId?: string): Record<string, string> {
  return xTenantId ? { "X-Tenant-Id": xTenantId } : {};
}

async function get<T>(path: string, xTenantId?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: { ...authHeaders(), ...extraHeaders(xTenantId) },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

async function post<T>(path: string, body: unknown, xTenantId?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(), ...extraHeaders(xTenantId) },
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

async function put<T>(path: string, body: unknown, xTenantId?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders(), ...extraHeaders(xTenantId) },
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

async function patch<T>(path: string, body: unknown, xTenantId?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders(), ...extraHeaders(xTenantId) },
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

async function del<T>(path: string, xTenantId?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE", headers: { ...authHeaders(), ...extraHeaders(xTenantId) } });
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
  anomalies: (limit = 50, severity?: string, tactic?: string, triage_status?: string) => {
    const qs = new URLSearchParams();
    qs.set("limit", String(limit));
    if (severity) qs.set("severity", severity);
    if (tactic) qs.set("tactic", tactic);
    if (triage_status) qs.set("triage_status", triage_status);
    return get<Anomaly[]>(`/anomalies?${qs.toString()}`);
  },
  anomaly: (id: string) => get<Anomaly>(`/anomalies/${id}`),
  triageAnomaly: (id: string, status: string, note?: string) =>
    patch<Anomaly>(`/anomalies/${id}/triage`, { status, note }),
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
  createTenantApiKey: (name: string, expires_at?: string) =>
    post<{
      id: string;
      name: string;
      key_prefix: string;
      key: string;
      scopes: string[];
      created_at: string;
      expires_at: string | null;
    }>("/tenant-api-keys", { name, scopes: ["ingest"], expires_at: expires_at ?? null }),
  listTenantApiKeys: () =>
    get<
      Array<{
        id: string;
        name: string;
        key_prefix: string;
        scopes: string[];
        created_at: string;
        last_used_at: string | null;
        expires_at: string | null;
        revoked_at: string | null;
      }>
    >("/tenant-api-keys"),
  revokeTenantApiKey: (id: string) => post<{ ok: boolean }>(`/tenant-api-keys/${id}/revoke`, {}),
  rotateTenantApiKey: (id: string) =>
    post<{ id: string; name: string; key_prefix: string; key: string; scopes: string[]; created_at: string; expires_at: string | null }>(
      `/tenant-api-keys/${id}/rotate`,
      {}
    ),

  // Incidents
  incidents: (status?: string, severity?: string, limit = 50) => {
    const qs = new URLSearchParams();
    qs.set("limit", String(limit));
    if (status) qs.set("status", status);
    if (severity) qs.set("severity", severity);
    return get<Incident[]>(`/incidents?${qs.toString()}`);
  },
  incident: (id: string) => get<Incident>(`/incidents/${id}`),
  createIncident: (body: { title: string; severity?: string; notes?: string; linked_anomaly_ids?: string[]; mitre_tactics?: string[] }) =>
    post<Incident>("/incidents", body),
  patchIncident: (id: string, body: Partial<{ title: string; status: string; severity: string; notes: string; assignee_subject: string; linked_anomaly_ids: string[]; mitre_tactics: string[] }>) =>
    patch<Incident>(`/incidents/${id}`, body),
  deleteIncident: (id: string) => del<void>(`/incidents/${id}`),
  incidentComments: (id: string) => get<IncidentComment[]>(`/incidents/${id}/comments`),
  addIncidentComment: (id: string, body: string) =>
    post<IncidentComment>(`/incidents/${id}/comments`, { body }),

  // Detection rules
  detectionRules: (enabled?: boolean) => {
    const qs = new URLSearchParams();
    if (enabled !== undefined) qs.set("enabled", String(enabled));
    return get<DetectionRule[]>(`/detection-rules?${qs.toString()}`);
  },
  detectionRule: (id: string) => get<DetectionRule>(`/detection-rules/${id}`),
  createDetectionRule: (body: { name: string; description?: string; condition: Record<string, unknown>; severity?: string; mitre_tactics?: string[]; enabled?: boolean }) =>
    post<DetectionRule>("/detection-rules", body),
  patchDetectionRule: (id: string, body: Partial<{ name: string; description: string; condition: Record<string, unknown>; severity: string; mitre_tactics: string[]; enabled: boolean }>) =>
    patch<DetectionRule>(`/detection-rules/${id}`, body),
  deleteDetectionRule: (id: string) => del<void>(`/detection-rules/${id}`),

  platformTenants: () => get<TenantRow[]>("/platform/tenants"),
  platformTenant: (id: string) => get<TenantRow>(`/platform/tenants/${id}`),
  platformCreateTenant: (body: {
    name: string;
    slug: string;
    admin_subject?: string | null;
    admin_email?: string | null;
    parent_tenant_id?: string | null;
    is_operator?: boolean;
  }) => post<TenantRow>("/platform/tenants", body),
  platformPatchTenant: (id: string, body: { name?: string; slug?: string; status?: string }) =>
    patch<TenantRow>(`/platform/tenants/${id}`, body),
  platformArchiveTenant: (id: string) => del<{ ok: boolean; tenant_id: string }>(`/platform/tenants/${id}`),

  supportThreads: (xTenantId?: string) => get<SupportThread[]>("/support/threads", xTenantId),
  supportThread: (id: string, xTenantId?: string) =>
    get<SupportThreadDetail>(`/support/threads/${id}`, xTenantId),
  createSupportThread: (subject: string, xTenantId?: string) =>
    post<SupportThread>("/support/threads", { subject }, xTenantId),
  postSupportMessage: (threadId: string, body: string, xTenantId?: string) =>
    post<SupportMessage>(`/support/threads/${threadId}/messages`, { body }, xTenantId),

  platformSupportThreads: (params?: { status?: string; tenant_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.tenant_id) qs.set("tenant_id", params.tenant_id);
    const q = qs.toString();
    return get<SupportThread[]>(`/platform/support/threads${q ? `?${q}` : ""}`);
  },
  platformSupportThread: (id: string) => get<SupportThreadDetail>(`/platform/support/threads/${id}`),
  platformPostSupportMessage: (threadId: string, body: string) =>
    post<SupportMessage>(`/platform/support/threads/${threadId}/messages`, { body }),
  platformPatchSupportThread: (
    threadId: string,
    body: { status?: string; assigned_to_user_id?: string | null }
  ) => patch<SupportThread>(`/platform/support/threads/${threadId}`, body),
  platformUsers: (search?: string) =>
    get<Array<{ id: string; subject: string; email: string; created_at: string }>>(
      `/platform/users${search ? `?search=${encodeURIComponent(search)}` : ""}`
    ),

  tenantMembers: (xTenantId?: string) =>
    get<
      Array<{
        membership_id: string;
        user_id: string;
        subject: string;
        email: string;
        role: string;
        created_at: string;
      }>
    >("/tenant/members", xTenantId),
  addTenantMember: (body: { subject: string; email?: string; role?: string }, xTenantId?: string) =>
    post<{
      membership_id: string;
      user_id: string;
      subject: string;
      email: string;
      role: string;
      created_at: string;
    }>("/tenant/members", body, xTenantId),
  patchTenantMember: (membershipId: string, body: { role: string }, xTenantId?: string) =>
    patch<{
      membership_id: string;
      user_id: string;
      subject: string;
      email: string;
      role: string;
      created_at: string;
    }>(`/tenant/members/${membershipId}`, body, xTenantId),
  removeTenantMember: (membershipId: string, xTenantId?: string) =>
    del<{ ok: boolean }>(`/tenant/members/${membershipId}`, xTenantId),

  listTenantIntegrations: (xTenantId?: string) => get<TenantIntegration[]>("/tenant/integrations", xTenantId),
  createTenantIntegration: (
    body: {
      name: string;
      provider: "opensearch" | "elasticsearch" | "wazuh_indexer" | "wazuh_api";
      is_primary?: boolean;
      extra_config?: Record<string, unknown> | null;
      opensearch_host?: string | null;
      opensearch_port?: number | null;
      opensearch_auth_type?: string | null;
      opensearch_username?: string | null;
      opensearch_password?: string | null;
      opensearch_api_key?: string | null;
      opensearch_use_ssl?: boolean | null;
      opensearch_verify_certs?: boolean | null;
      opensearch_ca_certs?: string | null;
      aws_region?: string | null;
      opensearch_index_pattern?: string | null;
    },
    xTenantId?: string
  ) => post<TenantIntegration>("/tenant/integrations", body, xTenantId),
  patchTenantIntegration: (
    id: string,
    body: Partial<{
      name: string;
      is_primary: boolean;
      extra_config: Record<string, unknown> | null;
      opensearch_host: string | null;
      opensearch_port: number | null;
      opensearch_auth_type: string | null;
      opensearch_username: string | null;
      opensearch_password: string | null;
      opensearch_api_key: string | null;
      opensearch_use_ssl: boolean | null;
      opensearch_verify_certs: boolean | null;
      opensearch_ca_certs: string | null;
      aws_region: string | null;
      opensearch_index_pattern: string | null;
    }>,
    xTenantId?: string
  ) => patch<TenantIntegration>(`/tenant/integrations/${id}`, body, xTenantId),
  deleteTenantIntegration: (id: string, xTenantId?: string) =>
    del<{ ok: boolean }>(`/tenant/integrations/${id}`, xTenantId),
  testTenantIntegration: (id: string, xTenantId?: string) =>
    post<Record<string, unknown>>(`/tenant/integrations/${id}/test`, {}, xTenantId),

  // Billing plans
  platformBillingPlans: () => get<BillingPlan[]>("/platform/billing/plans"),
  platformCreateBillingPlan: (body: {
    name: string;
    slug: string;
    max_members?: number | null;
    max_api_calls_per_day?: number | null;
    max_log_volume_mb_per_day?: number | null;
    price_usd_cents?: number;
  }) => post<BillingPlan>("/platform/billing/plans", body),
  platformPatchBillingPlan: (id: string, body: Partial<{
    name: string;
    max_members: number | null;
    max_api_calls_per_day: number | null;
    max_log_volume_mb_per_day: number | null;
    price_usd_cents: number;
    is_active: boolean;
  }>) => patch<BillingPlan>(`/platform/billing/plans/${id}`, body),

  // Tenant billing
  platformTenantBilling: (tenantId: string) =>
    get<TenantBilling>(`/platform/billing/tenants/${tenantId}`),
  platformPutTenantBilling: (tenantId: string, body: { plan_id: string | null; notes?: string | null }) =>
    put<TenantBilling>(`/platform/billing/tenants/${tenantId}`, body),
  platformResetBillingCounters: (tenantId: string) =>
    post<{ ok: boolean }>(`/platform/billing/tenants/${tenantId}/reset-counters`, {}),

  // Tenant stats and connection
  platformTenantStats: (tenantId: string) =>
    get<TenantStats>(`/platform/tenants/${tenantId}/stats`),
  platformTenantConnection: (tenantId: string) =>
    get<TenantConnection | null>(`/platform/tenants/${tenantId}/connection`),
  platformPutTenantConnection: (tenantId: string, body: Partial<TenantConnection>) =>
    put<{ ok: boolean }>(`/platform/tenants/${tenantId}/connection`, body),

  // Platform-wide audit log
  platformAuditLog: (params?: {
    tenant_id?: string;
    path?: string;
    method?: string;
    status?: string;
    actor_id?: string;
    from_ts?: string;
    to_ts?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.tenant_id) qs.set("tenant_id", params.tenant_id);
    if (params?.path) qs.set("path", params.path);
    if (params?.method) qs.set("method", params.method);
    if (params?.status) qs.set("status", params.status);
    if (params?.actor_id) qs.set("actor_id", params.actor_id);
    if (params?.from_ts) qs.set("from_ts", params.from_ts);
    if (params?.to_ts) qs.set("to_ts", params.to_ts);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return get<AuditLogEntry[]>(`/platform/audit-log${q ? `?${q}` : ""}`);
  },
};
