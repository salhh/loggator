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

export interface StatusResponse {
  ok: boolean;
  streaming?: { cursor: unknown; last_seen_at: string | null };
  last_batch?: { id: string; window_end: string; error_count: number } | null;
  ollama_ok?: boolean;
  ollama_reachable?: boolean;
}
