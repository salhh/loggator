import type { Summary, Anomaly, Alert, StatusResponse } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

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
  alerts: (limit = 50) => get<Alert[]>(`/alerts?limit=${limit}`),
  settings: () => get<{ settings: Record<string, string>; env_file: string }>("/settings"),
  updateSettings: (updates: Record<string, string>) =>
    put<{ settings: Record<string, string>; env_file: string }>("/settings", { updates }),
  chat: (message: string, top_k = 10) =>
    post<{ answer: string; context_logs: string[] }>("/chat", { message, top_k }),
  triggerIndex: (index_pattern?: string, hours_back = 1) =>
    post<{ message: string }>("/chat/index", { index_pattern, hours_back }),
  triggerBatch: () => post<{ message: string }>("/batch/trigger", {}),
};
