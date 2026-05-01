"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api, type SupportThread, type SupportThreadDetail } from "@/lib/api";
import { Input } from "@/components/ui/input";

export default function SupportPage() {
  const { tenantId, authStatus } = useAuth();
  const [threads, setThreads] = useState<SupportThread[]>([]);
  const [selected, setSelected] = useState<SupportThreadDetail | null>(null);
  const [subject, setSubject] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");

  const loadThreads = useCallback(async () => {
    if (!tenantId) return;
    try {
      const list = await api.supportThreads(tenantId ?? undefined);
      setThreads(list);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load threads");
    }
  }, [tenantId]);

  const openThread = async (id: string) => {
    if (!tenantId) return;
    try {
      const t = await api.supportThread(id, tenantId ?? undefined);
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

  const create = async () => {
    if (!tenantId || !subject.trim()) return;
    try {
      await api.createSupportThread(subject.trim(), tenantId);
      setSubject("");
      await loadThreads();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    }
  };

  const sendReply = async () => {
    if (!tenantId || !selected || !reply.trim()) return;
    try {
      await api.postSupportMessage(selected.id, reply.trim(), tenantId);
      setReply("");
      await openThread(selected.id);
      await loadThreads();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    }
  };

  if (authStatus !== "authenticated") {
    return <p className="text-sm text-muted-foreground">Sign in to use support.</p>;
  }

  if (!tenantId) {
    return <p className="text-sm text-muted-foreground">Select a tenant above to open or create support threads.</p>;
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Support</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Message your MSP about this tenant. This is separate from the log assistant.
        </p>
      </div>
      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-sm font-medium text-foreground">New thread</h2>
          <Input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject"
            className="bg-background"
          />
          <button
            type="button"
            onClick={() => void create()}
            disabled={!subject.trim()}
            className="rounded-md bg-cyan-400 text-black px-3 py-2 text-sm font-semibold disabled:opacity-50"
          >
            Start thread
          </button>
          <ul className="space-y-1 max-h-64 overflow-y-auto text-sm border-t border-border pt-3 mt-3">
            {threads.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => void openThread(t.id)}
                  className={`w-full text-left px-2 py-1.5 rounded hover:bg-secondary ${
                    selected?.id === t.id ? "bg-cyan-950/40 text-cyan-200" : "text-muted-foreground"
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
                      {m.is_staff ? "Staff" : "You"} · {new Date(m.created_at).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  placeholder="Reply…"
                  className="bg-background flex-1"
                />
                <button
                  type="button"
                  onClick={() => void sendReply()}
                  disabled={!reply.trim()}
                  className="rounded-md border border-border px-3 py-2 text-sm hover:bg-secondary disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Select a thread or start a new one.</p>
          )}
        </div>
      </div>
    </div>
  );
}
