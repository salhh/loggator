"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type SupportThread, type SupportThreadDetail } from "@/lib/api";
import { Input } from "@/components/ui/input";

export default function PlatformSupportPage() {
  const [threads, setThreads] = useState<SupportThread[]>([]);
  const [selected, setSelected] = useState<SupportThreadDetail | null>(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");

  const loadThreads = useCallback(async () => {
    try {
      const list = await api.platformSupportThreads();
      setThreads(list);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inbox");
    }
  }, []);

  const openThread = async (id: string) => {
    try {
      const t = await api.platformSupportThread(id);
      setSelected(t);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to open thread");
    }
  };

  useEffect(() => {
    void loadThreads();
    const id = setInterval(() => void loadThreads(), 8000);
    return () => clearInterval(id);
  }, [loadThreads]);

  const sendReply = async () => {
    if (!selected || !reply.trim()) return;
    try {
      await api.platformPostSupportMessage(selected.id, reply.trim());
      setReply("");
      await openThread(selected.id);
      await loadThreads();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    }
  };

  const setStatus = async (status: string) => {
    if (!selected) return;
    try {
      await api.platformPatchSupportThread(selected.id, { status });
      await openThread(selected.id);
      await loadThreads();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Support inbox</h1>
        <p className="text-sm text-muted-foreground mt-1">Threads from tenants in your organization.</p>
      </div>
      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4">
          <ul className="space-y-1 max-h-[480px] overflow-y-auto text-sm">
            {threads.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => void openThread(t.id)}
                  className={`w-full text-left px-2 py-1.5 rounded hover:bg-secondary ${
                    selected?.id === t.id ? "bg-amber-950/40 text-amber-200" : "text-muted-foreground"
                  }`}
                >
                  <span className="block truncate font-medium text-foreground">{t.subject || "(no subject)"}</span>
                  <span className="text-[10px] uppercase tracking-wide">{t.status}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 flex flex-col min-h-[320px]">
          {selected ? (
            <>
              <div className="flex flex-wrap gap-2 mb-2">
                {(["open", "pending", "resolved", "closed"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => void setStatus(s)}
                    className="text-[11px] uppercase px-2 py-1 rounded border border-border hover:bg-secondary"
                  >
                    {s}
                  </button>
                ))}
              </div>
              <h2 className="text-sm font-medium text-foreground mb-2 truncate">{selected.subject}</h2>
              <div className="flex-1 overflow-y-auto space-y-2 text-sm mb-3 border border-border rounded-md p-2 bg-background/50">
                {selected.messages.map((m) => (
                  <div
                    key={m.id}
                    className={`rounded px-2 py-1.5 ${
                      m.is_staff ? "bg-amber-950/30 text-amber-100 ml-4" : "bg-secondary mr-4"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{m.body}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      {m.is_staff ? "Staff" : "Customer"} · {new Date(m.created_at).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  placeholder="Reply as staff…"
                  className="bg-background flex-1"
                />
                <button
                  type="button"
                  onClick={() => void sendReply()}
                  disabled={!reply.trim()}
                  className="rounded-md bg-amber-400 text-black px-3 py-2 text-sm font-semibold disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Select a thread.</p>
          )}
        </div>
      </div>
    </div>
  );
}
