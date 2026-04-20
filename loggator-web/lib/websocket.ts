"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface WsEvent {
  type: "anomaly" | "summary" | "ping";
  [key: string]: unknown;
}

export function useWebSocket(onEvent: (event: WsEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    const url = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/live";
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect after 3 seconds
      setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      try {
        onEventRef.current(JSON.parse(e.data));
      } catch {
        // ignore malformed frames
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
