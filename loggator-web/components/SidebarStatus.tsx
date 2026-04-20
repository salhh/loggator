"use client";

import { useEffect, useState } from "react";

interface StatusData {
  streaming_active?: boolean;
  ollama_reachable?: boolean;
  ollama_ok?: boolean;
}

export default function SidebarStatus() {
  const [status, setStatus] = useState<StatusData | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
    const fetchStatus = () =>
      fetch(`${apiUrl}/status`)
        .then((r) => r.json())
        .then(setStatus)
        .catch(() => {});
    fetchStatus();
    const id = setInterval(fetchStatus, 30_000);
    return () => clearInterval(id);
  }, []);

  const streaming = status?.streaming_active ?? false;
  const ollama = status?.ollama_reachable ?? status?.ollama_ok ?? false;

  return (
    <div className="flex flex-col gap-2 px-3 py-3 border-t border-border text-xs text-muted-foreground">
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${streaming ? "bg-emerald-500" : "bg-red-500"}`} />
        Streaming
      </div>
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${ollama ? "bg-emerald-500" : "bg-red-500"}`} />
        Ollama
      </div>
    </div>
  );
}
