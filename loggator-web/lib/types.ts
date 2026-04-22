export interface Summary {
  id: string;
  created_at: string;
  window_start: string;
  window_end: string;
  index_pattern: string;
  summary: string;
  top_issues: string[];
  error_count: number;
  recommendation: string | null;
  model_used: string;
  tokens_used: number | null;
}

export interface Anomaly {
  id: string;
  detected_at: string;
  log_timestamp: string | null;
  index_pattern: string;
  severity: "low" | "medium" | "high";
  summary: string;
  root_cause_hints: string[];
  raw_logs: string[] | null;
  model_used: string;
  alerted: boolean;
}

export interface Alert {
  id: string;
  created_at: string;
  anomaly_id: string;
  channel: string;
  destination: string;
  status: string;
  error: string | null;
}

export interface RootCause {
  title: string;
  description: string;
  services: string[];
  severity: "low" | "medium" | "high" | "critical";
}

export interface Recommendation {
  priority: "immediate" | "short-term" | "long-term";
  action: string;
  rationale: string;
}

export interface AnalysisReport {
  summary: string;
  affected_services: string[];
  root_causes: RootCause[];
  timeline: string[];
  recommendations: Recommendation[];
  error_count: number;
  warning_count: number;
  log_count: number;
  chunk_count?: number;
  from_ts: string;
  to_ts: string;
}

export interface ScheduledAnalysis {
  id: string;
  created_at: string;
  window_start: string;
  window_end: string;
  index_pattern: string;
  summary: string;
  affected_services: string[];
  root_causes: RootCause[];
  timeline: string[];
  recommendations: Recommendation[];
  error_count: number;
  warning_count: number;
  log_count: number;
  chunk_count: number;
  model_used: string;
  status: "success" | "failed";
}

export interface AlertChannel {
  id: string;
  label: string;
  type: "slack" | "telegram" | "email" | "webhook";
  config: Record<string, string>;
  enabled: boolean;
  updated_at: string | null;
}

export interface LLMConfig {
  id: string;
  label: string;
  provider: "ollama" | "anthropic" | "openai";
  model: string;
  base_url: string;
  api_key: string;   // masked
  is_default: boolean;
  updated_at: string | null;
}

export interface ScheduleStatus {
  enabled: boolean;
  interval_minutes: number;
  window_minutes: number;
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_status: "success" | "failed" | null;
}

export interface StatusResponse {
  ok: boolean;
  streaming?: { cursor: unknown; last_seen_at: string | null };
  last_batch?: { id: string; window_end: string; error_count: number } | null;
  ollama_ok?: boolean;
  ollama_reachable?: boolean;
}

export interface HealthCheck {
  ok: boolean;
  latency_ms: number;
  detail: string;
}

export interface HealthResponse {
  checks: Record<string, HealthCheck>;
  overall: "ok" | "degraded" | "down";
}

export interface StatsDaily {
  date: string;
  summaries: number;
  anomalies: number;
  alerts: number;
}

export interface StatsLogVolume {
  date: string;
  error: number;
  warn: number;
  info: number;
}

export interface StatsTopService {
  service: string;
  error_count: number;
}

export interface StatsResponse {
  period_days: number;
  totals: {
    summaries: number;
    anomalies: number;
    alerts_sent: number;
    alerts_failed: number;
  };
  daily: StatsDaily[];
  anomalies_by_severity: { low: number; medium: number; high: number };
  alerts_by_channel: Record<string, number>;
  log_volume: StatsLogVolume[];
  top_services: StatsTopService[];
}
