"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  contextLogs?: string[];
}

export default function ChatClient() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);

  async function send() {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    try {
      const res = await api.chat(userMsg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, contextLogs: res.context_logs },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: could not reach the API." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function triggerIndex() {
    setIndexing(true);
    try {
      await api.triggerIndex(undefined, 1);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Log indexing started. Ask questions once it completes (a few seconds).",
        },
      ]);
    } finally {
      setIndexing(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <button
          onClick={triggerIndex}
          disabled={indexing}
          className="px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-card text-foreground hover:bg-secondary disabled:opacity-50 transition-colors"
        >
          {indexing ? "Indexing..." : "Index recent logs"}
        </button>
        <span className="text-xs text-muted-foreground">
          Run this first to let the AI search your logs
        </span>
      </div>

      <div className="space-y-3 min-h-[300px]">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div
              className={`max-w-2xl rounded-lg border p-3 space-y-2 ${
                m.role === "user"
                  ? "bg-card border-cyan-400/40 text-foreground"
                  : "bg-card border-border"
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              {m.contextLogs && m.contextLogs.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground">
                    {m.contextLogs.length} log lines used as context
                  </summary>
                  <ul className="mt-1 space-y-0.5 font-mono text-[10px] text-muted-foreground">
                    {m.contextLogs.map((l, j) => (
                      <li key={j} className="truncate">
                        {l}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="max-w-2xl rounded-lg border border-border bg-card p-3">
            <p className="text-sm text-muted-foreground animate-pulse">Thinking...</p>
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <Textarea
          className="resize-none bg-card border-border"
          rows={2}
          placeholder="Ask about your logs..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="px-4 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
