"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api, type SupportThread, type SupportThreadDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** MSP / platform operators must use /platform/support/*; customer GET /support/threads returns 400 for them. */
function isOperatorSupportInbox(platformRoles: string[] | undefined): boolean {
  const pr = platformRoles ?? [];
  return pr.includes("msp_admin") || pr.includes("platform_admin");
}

export default function SupportPage() {
  const { tenantId, authStatus } = useAuth();
  /** Avoid calling customer /support/threads before authMe resolves (MSP would get 400). */
  const [inboxMode, setInboxMode] = useState<"pending" | "customer" | "operator">("pending");
  const [threads, setThreads] = useState<SupportThread[]>([]);
  const [selected, setSelected] = useState<SupportThreadDetail | null>(null);
  const [subject, setSubject] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (authStatus !== "authenticated") {
      setInboxMode("pending");
      return;
    }
    let cancelled = false;
    setInboxMode("pending");
    void api
      .authMe()
      .then((me) => {
        if (!cancelled) {
          setInboxMode(isOperatorSupportInbox(me.platform_roles) ? "operator" : "customer");
        }
      })
      .catch(() => {
        if (!cancelled) setInboxMode("customer");
      });
    return () => {
      cancelled = true;
    };
  }, [authStatus]);

  const loadThreads = useCallback(async () => {
    if (!tenantId || inboxMode === "pending") return;
    try {
      const list =
        inboxMode === "operator"
          ? await api.platformSupportThreads({ tenant_id: tenantId })
          : await api.supportThreads(tenantId);
      setThreads(list);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load threads");
    }
  }, [tenantId, inboxMode]);

  const openThread = async (id: string) => {
    if (!tenantId || inboxMode === "pending") return;
    try {
      const t =
        inboxMode === "operator"
          ? await api.platformSupportThread(id)
          : await api.supportThread(id, tenantId);
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
    if (!tenantId || !selected || !reply.trim() || inboxMode === "pending") return;
    try {
      if (inboxMode === "operator") {
        await api.platformPostSupportMessage(selected.id, reply.trim());
      } else {
        await api.postSupportMessage(selected.id, reply.trim(), tenantId);
      }
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
      {inboxMode === "pending" && tenantId ? (
        <p className="text-sm text-muted-foreground">Loading support inbox…</p>
      ) : null}
      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
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
          <Button type="button" onClick={() => void create()} disabled={!subject.trim()}>
            Start thread
          </Button>
          <ul className="space-y-1 max-h-64 overflow-y-auto text-sm border-t border-border pt-3 mt-3">
            {threads.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => void openThread(t.id)}
                  className={`w-full text-left px-2 py-1.5 rounded hover:bg-secondary ${
                    selected?.id === t.id ? "bg-accent text-accent-foreground" : "text-muted-foreground"
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
                      m.is_staff ? "bg-chart-3/15 text-chart-3 border border-chart-3/25 ml-4" : "bg-secondary mr-4"
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
