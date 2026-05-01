import { notFound } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { IncidentComment } from "@/lib/types";
import MitreBadge from "@/components/MitreBadge";
import IncidentActions from "@/components/IncidentActions";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

const STATUS_CONFIG: Record<string, { cls: string; label: string }> = {
  open:           { cls: "bg-red-900/50 text-red-300 border-red-700",         label: "Open" },
  investigating:  { cls: "bg-amber-900/50 text-amber-300 border-amber-700",   label: "Investigating" },
  resolved:       { cls: "bg-emerald-900/50 text-emerald-300 border-emerald-700", label: "Resolved" },
  false_positive: { cls: "bg-zinc-800 text-zinc-400 border-zinc-600",         label: "False Positive" },
};

export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let incident;
  let comments: IncidentComment[] = [];
  try {
    [incident, comments] = await Promise.all([
      api.incident(id),
      api.incidentComments(id),
    ]);
  } catch {
    notFound();
  }

  const s = STATUS_CONFIG[incident.status] ?? STATUS_CONFIG.open;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <Link
            href="/incidents"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            ← Incidents
          </Link>
          <h1 className="text-lg font-semibold text-foreground">{incident.title}</h1>
        </div>
        <span className={`px-2.5 py-1 rounded border text-xs font-bold uppercase shrink-0 ${s.cls}`}>
          {s.label}
        </span>
      </div>

      {/* MITRE tactics */}
      {incident.mitre_tactics.length > 0 && (
        <MitreBadge tactics={incident.mitre_tactics} linkable size="sm" />
      )}

      <div className="grid grid-cols-[1fr_300px] gap-6">
        {/* Left: notes + comments */}
        <div className="space-y-6">
          {incident.notes && (
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Notes
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{incident.notes}</p>
            </div>
          )}

          {/* Linked anomalies */}
          {incident.linked_anomaly_ids.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Linked anomalies
              </div>
              <div className="space-y-1">
                {incident.linked_anomaly_ids.map((aid) => (
                  <Link
                    key={aid}
                    href={`/anomalies/${aid}`}
                    className="block font-mono text-xs text-cyan-400 hover:underline"
                  >
                    {aid}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Comments */}
          <div className="space-y-3">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Comments ({comments.length})
            </div>
            {comments.map((c) => (
              <div key={c.id} className="rounded-lg border border-border bg-card px-3 py-2.5 space-y-1">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{c.author_label ?? "Unknown"}</span>
                  <span>·</span>
                  <span>{fmt(c.created_at)}</span>
                </div>
                <p className="text-sm whitespace-pre-wrap">{c.body}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right: details + actions */}
        <div className="space-y-4">
          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Details
            </div>
            <div className="space-y-2 text-xs">
              <div>
                <div className="text-muted-foreground">Severity</div>
                <div className="font-semibold uppercase">{incident.severity}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Created</div>
                <div>{fmt(incident.created_at)}</div>
              </div>
              {incident.resolved_at && (
                <div>
                  <div className="text-muted-foreground">Resolved</div>
                  <div>{fmt(incident.resolved_at)}</div>
                </div>
              )}
            </div>
          </div>

          <IncidentActions incidentId={incident.id} currentStatus={incident.status} />
        </div>
      </div>
    </div>
  );
}
