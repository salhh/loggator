"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const STATUSES = [
  { value: "open",           label: "Open",           cls: "border-red-700 text-red-300" },
  { value: "investigating",  label: "Investigating",  cls: "border-amber-700 text-amber-300" },
  { value: "resolved",       label: "Resolved",       cls: "border-emerald-700 text-emerald-300" },
  { value: "false_positive", label: "False Positive", cls: "border-zinc-600 text-zinc-400" },
];

interface IncidentActionsProps {
  incidentId: string;
  currentStatus: string;
}

export default function IncidentActions({ incidentId, currentStatus }: IncidentActionsProps) {
  const [status, setStatus] = useState(currentStatus);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSave() {
    setError(null);
    setSuccess(false);
    startTransition(async () => {
      try {
        const ops: Promise<unknown>[] = [];
        if (status !== currentStatus) {
          ops.push(api.patchIncident(incidentId, { status }));
        }
        if (comment.trim()) {
          ops.push(api.addIncidentComment(incidentId, comment.trim()));
        }
        await Promise.all(ops);
        setSuccess(true);
        setComment("");
        router.refresh();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to save");
      }
    });
  }

  const changed = status !== currentStatus || comment.trim() !== "";

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-3">
      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Update
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
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Add a comment…"
        rows={3}
        className="w-full text-xs bg-background border border-border rounded px-2.5 py-1.5 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-cyan-500"
      />

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={isPending || !changed}
          className="px-3 py-1 rounded text-xs font-medium bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
        >
          {isPending ? "Saving…" : "Save"}
        </button>
        {success && <span className="text-xs text-emerald-400">Saved</span>}
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </div>
  );
}
