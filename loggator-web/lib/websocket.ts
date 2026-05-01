"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getBrowserAccessToken, getStoredTenantId } from "./auth-headers";

export interface WsEvent {
  type: "anomaly" | "summary" | "ping" | "scheduled_analysis";
  tenant_id?: string;
  [key: string]: unknown;
}

const MAX_ATTEMPTS = 8;
// Exponential backoff: 2s → 4s → 8s → 16s → 30s (capped)
function backoffMs(attempt: number): number {
  return Math.min(2000 * Math.pow(2, attempt), 30_000);
}

function buildWebSocketUrl(): string {
  const base = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/live";
  const params = new URLSearchParams();
  const token = getBrowserAccessToken();
  const tid = getStoredTenantId();
  if (token) params.set("access_token", token);
  if (tid) params.set("tenant_id", tid);
  const q = params.toString();
  return q ? `${base}?${q}` : base;
}

export function useWebSocket(
  onEvent: (event: WsEvent) => void,
  reconnectToken: string | null,
  reconnectTenantId: string | null
) {
  const [connected, setConnected] = useState(false);
  const [permanentlyOffline, setPermanentlyOffline] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const attemptRef = useRef(0);
  const connectRef = useRef<() => void>(() => {});

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    attemptRef.current = 0;
    setPermanentlyOffline(false);

    const connect = () => {
      if (cancelled) return;
      const url = buildWebSocketUrl();
      ws = new WebSocket(url);

      ws.onopen = () => {
        attemptRef.current = 0;
        setConnected(true);
        setPermanentlyOffline(false);
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          if (attemptRef.current >= MAX_ATTEMPTS) {
            setPermanentlyOffline(true);
            return;
          }
          const delay = backoffMs(attemptRef.current);
          attemptRef.current += 1;
          reconnectTimer = setTimeout(connect, delay);
        }
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (e) => {
        try {
          onEventRef.current(JSON.parse(e.data));
        } catch {
          /* ignore */
        }
      };
    };

    connectRef.current = connect;
    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [reconnectToken, reconnectTenantId]);

  const reconnect = useCallback(() => {
    attemptRef.current = 0;
    setPermanentlyOffline(false);
    connectRef.current();
  }, []);

  return { connected, permanentlyOffline, reconnect };
}
