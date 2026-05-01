"use client";

import { useState, useTransition } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

const STATUSES = [
  { value: "new",            label: "New",           cls: "border-zinc-600 text-zinc-300" },
  { value: "acknowledged",   label: "Acknowledged",  cls: "border-blue-700 text-blue-300" },
  { value: "suppressed",     label: "Suppressed",    cls: "border-zinc-600 text-zinc-500" },
  { value: "false_positive", label: "False Positive", cls: "border-yellow-700 text-yellow-300" },
];

interface TriagePanelProps {
  anomalyId: string;
  currentStatus: string;
  currentNote: string | null;
}

export default function TriagePanel({ anomalyId, currentStatus, currentNote }: TriagePanelProps) {
  const [status, setStatus] = useState(currentStatus);
  const [note, setNote] = useState(currentNote ?? "");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSave() {
    setError(null);
    setSuccess(false);
    startTransition(async () => {
      try {
        await api.triageAnomaly(anomalyId, status, note || undefined);
        setSuccess(true);
        router.refresh();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to save triage");
      }
    });
  }

  const changed = status !== currentStatus || note !== (currentNote ?? "");

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-3">
      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Triage
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <button
            key={s.value}
            onClick={() => setStatus(s.value)}
            className={`px-2.5 py-1 rounded border text-xs font-medium transition-all ${
              status === s.value
                ? `${s.cls} ring-1 ring-inset ring-current bg-current/10`
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note…"
        rows={2}
        className="w-full text-xs bg-background border border-border rounded px-2.5 py-1.5 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-ring"
      />

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={isPending || !changed}
          className="px-3 py-1 rounded text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {isPending ? "Saving…" : "Save"}
        </button>
        {success && <span className="text-xs text-success">Saved</span>}
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </div>
  );
}
