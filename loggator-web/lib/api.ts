import type { Summary, Anomaly, Alert, StatusResponse, AnalysisReport, ScheduledAnalysis, ScheduleStatus, HealthResponse, StatsResponse, LLMConfig, AlertChannel } from "./types";

// API_URL is only available server-side (no NEXT_PUBLIC_ prefix).
// NEXT_PUBLIC_API_URL is used by the browser. Fall back to localhost for dev.
const BASE =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
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
  chat: (message: string, top_k = 10, model_id?: string) =>
    post<{ answer: string; context_logs: string[] }>("/chat", { message, top_k, model_id }),
  triggerIndex: (index_pattern?: string, hours_back = 1, size = 500) =>
    post<{ message: string }>("/chat/index", { index_pattern, hours_back, size }),
  logIndices: () =>
    fetch(`${BASE.replace("/api/v1", "")}/api/v1/logs/indices`).then((r) => r.json()) as Promise<{ indices: string[] }>,
  triggerBatch: () => post<{ message: string }>("/batch/trigger", {}),
  analyzeLogs: (index_pattern?: string, hours_back = 1, size = 500, model_id?: string) =>
    post<AnalysisReport>("/chat/analyze", { index_pattern, hours_back, size, model_id }),
  llms: () => get<LLMConfig[]>("/llms"),
  createLlm: (data: Omit<LLMConfig, "id" | "updated_at">) =>
    post<LLMConfig>("/llms", data),
  updateLlm: (id: string, data: Omit<LLMConfig, "id" | "updated_at">) =>
    put<LLMConfig>(`/llms/${id}`, data),
  deleteLlm: (id: string) =>
    fetch(`${BASE}/llms/${id}`, { method: "DELETE" }),
  testLlm: (id: string) =>
    post<{ ok: boolean; response?: string; error?: string }>(`/llms/${id}/test`, {}),
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
  alertChannels: () =>
    get<AlertChannel[]>("/alert-channels"),
  createAlertChannel: (data: Omit<AlertChannel, "id" | "updated_at">) =>
    post<AlertChannel>("/alert-channels", data),
  updateAlertChannel: (id: string, data: Omit<AlertChannel, "id" | "updated_at">) =>
    put<AlertChannel>(`/alert-channels/${id}`, data),
  deleteAlertChannel: (id: string) =>
    fetch(`${BASE}/alert-channels/${id}`, { method: "DELETE" }),
  testAlertChannel: (id: string) =>
    post<{ ok: boolean; error?: string | null }>(`/alert-channels/${id}/test`, {}),
};
