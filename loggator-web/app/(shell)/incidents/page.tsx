import Link from "next/link";
import { api } from "@/lib/api";
import type { Incident } from "@/lib/types";
import MitreBadge from "@/components/MitreBadge";
import NewIncidentButton from "@/components/NewIncidentButton";

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const STATUS_CONFIG: Record<string, { cls: string; label: string }> = {
  open:           { cls: "bg-destructive/12 text-destructive border-destructive/35", label: "Open" },
  investigating:  { cls: "bg-warning/12 text-warning border-warning/35", label: "Investigating" },
  resolved:       { cls: "bg-success/12 text-success border-success/35", label: "Resolved" },
  false_positive: { cls: "bg-muted text-muted-foreground border-border", label: "False Positive" },
};

const SEVERITY_CONFIG: Record<string, string> = {
  critical: "text-destructive",
  high:     "text-chart-2",
  medium:   "text-warning",
  low:      "text-muted-foreground",
};

const STATUS_TABS = [
  { label: "All",           value: undefined as string | undefined },
  { label: "Open",          value: "open" },
  { label: "Investigating", value: "investigating" },
  { label: "Resolved",      value: "resolved" },
];

export default async function IncidentsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const rawStatus = typeof sp.status === "string" ? sp.status : undefined;

  let incidents: Incident[] = [];
  try {
    incidents = await api.incidents(rawStatus);
  } catch {
    // API offline
  }

  function tabHref(status: string | undefined) {
    return `/incidents${status ? `?status=${status}` : ""}`;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Incidents</h1>
        <NewIncidentButton />
      </div>

      {/* Status tabs */}
      <div className="flex items-center gap-4 border-b border-border">
        {STATUS_TABS.map((tab) => {
          const isActive = tab.value === rawStatus;
          return (
            <Link
              key={tab.label}
              href={tabHref(tab.value)}
              className={`pb-1.5 text-sm transition-colors border-b-2 ${
                isActive
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
        <span className="ml-auto text-xs text-muted-foreground pb-1.5">
          {incidents.length} incidents
        </span>
      </div>

      {incidents.length === 0 ? (
        <p className="text-sm text-muted-foreground">No incidents yet.</p>
      ) : (
        <div className="space-y-2">
          {incidents.map((inc) => {
            const s = STATUS_CONFIG[inc.status] ?? STATUS_CONFIG.open;
            const sevCls = SEVERITY_CONFIG[inc.severity] ?? "";
            return (
              <Link key={inc.id} href={`/incidents/${inc.id}`} className="block group">
                <div className="rounded-lg border border-border bg-card px-4 py-3 group-hover:ring-1 group-hover:ring-ring/25 transition-all space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-0.5 min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">{inc.title}</div>
                      <div className={`text-xs font-semibold uppercase ${sevCls}`}>{inc.severity}</div>
                    </div>
                    <span className={`px-2 py-0.5 rounded border text-xs font-medium shrink-0 ${s.cls}`}>
                      {s.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span>{fmtRelative(inc.created_at)}</span>
                    {inc.linked_anomaly_ids.length > 0 && (
                      <span>{inc.linked_anomaly_ids.length} anomal{inc.linked_anomaly_ids.length === 1 ? "y" : "ies"}</span>
                    )}
                  </div>
                  {inc.mitre_tactics.length > 0 && (
                    <MitreBadge tactics={inc.mitre_tactics} />
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
