"use client";

import { useState } from "react";
import { useWebSocket, type WsEvent } from "@/lib/websocket";
import AnomalyCard from "@/components/AnomalyCard";
import { useAuth } from "@/components/AuthProvider";

interface LiveAnomaly {
  anomaly_id: string;
  severity: string;
  summary: string;
  detected_at: string;
  index_pattern: string;
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString();
}

export default function LiveFeed() {
  const { accessToken, tenantId } = useAuth();
  const [events, setEvents] = useState<LiveAnomaly[]>([]);
  const { connected, permanentlyOffline, reconnect } = useWebSocket(
    (event: WsEvent) => {
      if (event.type === "anomaly") {
        setEvents((prev) => [event as unknown as LiveAnomaly, ...prev].slice(0, 20));
      }
    },
    accessToken,
    tenantId
  );

  return (
    <div className="space-y-2">
      {permanentlyOffline ? (
        <div className="flex items-center gap-2 mb-2">
          <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
          <span className="text-xs text-destructive flex-1">Live feed disconnected</span>
          <button
            type="button"
            onClick={reconnect}
            className="text-xs text-primary hover:underline shrink-0"
          >
            Reconnect
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2 mb-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-success" : "bg-muted-foreground"}`}
          />
          <span className="text-xs text-muted-foreground">
            {connected ? "connected" : "connecting..."}
          </span>
        </div>
      )}
      {events.length === 0 ? (
        <p className="text-xs text-muted-foreground">Waiting for anomalies...</p>
      ) : (
        <div className="space-y-2">
          {events.map((e) => (
            <AnomalyCard
              key={e.anomaly_id}
              severity={e.severity}
              summary={e.summary}
              meta={e.index_pattern}
              timestamp={fmtTime(e.detected_at)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
