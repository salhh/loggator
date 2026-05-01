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

export interface EnrichmentResult {
  ioc_type: string;
  value: string;
  reputation: "clean" | "suspicious" | "malicious" | "unknown";
  confidence_score: number | null;
  source: string;
  details: Record<string, unknown>;
}

export interface AnomalyEnrichment {
  ips: EnrichmentResult[];
  hashes: string[];
  domains: string[];
}

export interface Anomaly {
  id: string;
  detected_at: string;
  log_timestamp: string | null;
  index_pattern: string;
  severity: "low" | "medium" | "high";
  summary: string;
  root_cause_hints: string[];
  mitre_tactics: string[];
  raw_logs: string[] | null;
  enrichment_context: AnomalyEnrichment | null;
  model_used: string;
  alerted: boolean;
  source: "llm" | "rule" | "ueba";
  triage_status: "new" | "acknowledged" | "suppressed" | "false_positive";
  triage_note: string | null;
  triaged_at: string | null;
}

export interface Incident {
  id: string;
  tenant_id: string;
  title: string;
  status: "open" | "investigating" | "resolved" | "false_positive";
  severity: "low" | "medium" | "high" | "critical";
  assignee_id: string | null;
  linked_anomaly_ids: string[];
  notes: string | null;
  mitre_tactics: string[];
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface IncidentComment {
  id: string;
  incident_id: string;
  author_id: string | null;
  author_label: string | null;
  body: string;
  created_at: string;
}

export interface DetectionRule {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  condition: Record<string, unknown>;
  severity: "low" | "medium" | "high" | "critical";
  mitre_tactics: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
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

// ── Platform Observability ─────────────────────────────────────────────────

export interface SystemEvent {
  id: string;
  timestamp: string;
  service: string;
  event_type: string;
  severity: "info" | "warning" | "error" | "critical";
  message: string;
  details: Record<string, unknown> | null;
  resolved_at: string | null;
}

export interface OpenError {
  service: string;
  event_type: string;
  message: string;
  timestamp: string;
}

export interface SystemEventsResponse {
  summary: {
    by_service: Record<string, number>;
    by_severity: Record<string, number>;
    open_errors: OpenError[];
  };
  events: SystemEvent[];
  total: number;
}

export interface AuditLogEntry {
  id: string;
  tenant_id: string | null;
  timestamp: string;
  request_id: string;
  method: string;
  path: string;
  status_code: number | null;
  duration_ms: number | null;
  client_ip: string | null;
  query_params: Record<string, string> | null;
  error_detail: string | null;
  actor_id: string | null;
  actor_type: string | null;
}

// ── Billing ──────────────────────────────────────────────────────────────────

export interface BillingPlan {
  id: string;
  name: string;
  slug: string;
  max_members: number | null;
  max_api_calls_per_day: number | null;
  max_log_volume_mb_per_day: number | null;
  price_usd_cents: number;
  is_active: boolean;
  created_at: string;
}

export interface TenantBilling {
  id: string;
  tenant_id: string;
  plan_id: string | null;
  plan: BillingPlan | null;
  api_calls_today: number;
  log_volume_mb_today: number;
  billing_cycle_start: string | null;
  notes: string | null;
  limits_exceeded: boolean;
  updated_at: string;
  created_at: string;
}

export interface TenantStats {
  member_count: number;
  anomaly_count: number;
  summary_count: number;
  api_key_count: number;
}

export interface TenantConnection {
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
}

export interface TenantIntegration {
  id: string;
  tenant_id: string;
  name: string;
  provider: string;
  is_primary: boolean;
  extra_config: Record<string, unknown> | null;
  opensearch_host: string | null;
  opensearch_port: number | null;
  opensearch_auth_type: string | null;
  opensearch_username: string | null;
  opensearch_use_ssl: boolean | null;
  opensearch_verify_certs: boolean | null;
  aws_region: string | null;
  opensearch_index_pattern: string | null;
  created_at: string;
  updated_at: string;
}
