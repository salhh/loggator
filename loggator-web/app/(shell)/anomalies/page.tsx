import Link from "next/link";
import { api } from "@/lib/api";
import type { Anomaly } from "@/lib/types";
import AnomalyCard from "@/components/AnomalyCard";
import MitreBadge from "@/components/MitreBadge";

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

const SEVERITY_TABS = [
  { label: "All",    value: undefined as string | undefined },
  { label: "High",   value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low",    value: "low" },
];

const TRIAGE_TABS = [
  { label: "All",              value: undefined as string | undefined },
  { label: "New",              value: "new" },
  { label: "Acknowledged",     value: "acknowledged" },
  { label: "Suppressed",       value: "suppressed" },
  { label: "False Positive",   value: "false_positive" },
];

const SOURCE_LABELS: Record<string, { label: string; cls: string }> = {
  llm:  { label: "AI",   cls: "bg-cyan-900/50 text-cyan-300 border-cyan-700" },
  rule: { label: "Rule", cls: "bg-violet-900/50 text-violet-300 border-violet-700" },
  ueba: { label: "UEBA", cls: "bg-amber-900/50 text-amber-300 border-amber-700" },
};

const TRIAGE_BADGE: Record<string, string> = {
  new:           "bg-zinc-800 text-zinc-400 border-zinc-600",
  acknowledged:  "bg-blue-900/50 text-blue-300 border-blue-700",
  suppressed:    "bg-zinc-800 text-zinc-500 border-zinc-700",
  false_positive: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
};

export default async function AnomaliesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const raw = typeof sp.severity === "string" ? sp.severity.toLowerCase() : undefined;
  const validSeverity = ["high", "medium", "low"].includes(raw ?? "") ? raw : undefined;
  const rawTriage = typeof sp.triage === "string" ? sp.triage : undefined;
  const rawTactic = typeof sp.tactic === "string" ? sp.tactic : undefined;

  let anomalies: Anomaly[] = [];
  try {
    anomalies = await api.anomalies(100, validSeverity, rawTactic, rawTriage);
  } catch {
    // API offline
  }

  function tabHref(params: Record<string, string | undefined>) {
    const qs = new URLSearchParams();
    if (params.severity) qs.set("severity", params.severity);
    if (params.triage) qs.set("triage", params.triage);
    if (params.tactic) qs.set("tactic", params.tactic);
    const s = qs.toString();
    return `/anomalies${s ? `?${s}` : ""}`;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Anomalies</h1>

      {/* Severity tabs */}
      <div className="flex items-center gap-4 border-b border-border">
        {SEVERITY_TABS.map((tab) => {
          const isActive = tab.value === validSeverity;
          return (
            <Link
              key={tab.label}
              href={tabHref({ severity: tab.value, triage: rawTriage, tactic: rawTactic })}
              className={`pb-1.5 text-sm transition-colors border-b-2 ${
                isActive
                  ? "border-cyan-400 text-cyan-300 font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
        <span className="ml-auto text-xs text-muted-foreground pb-1.5">
          {anomalies.length} anomalies
        </span>
      </div>

      {/* Triage filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-muted-foreground">Triage:</span>
        {TRIAGE_TABS.map((tab) => {
          const isActive = tab.value === rawTriage;
          return (
            <Link
              key={tab.label}
              href={tabHref({ severity: validSeverity, triage: tab.value, tactic: rawTactic })}
              className={`px-2 py-0.5 rounded text-xs border transition-colors ${
                isActive
                  ? "bg-cyan-900/50 text-cyan-300 border-cyan-700"
                  : "text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
        {rawTactic && (
          <span className="ml-2 px-2 py-0.5 rounded text-xs border bg-indigo-900/50 text-indigo-300 border-indigo-700">
            tactic: {rawTactic}
            <Link
              href={tabHref({ severity: validSeverity, triage: rawTriage })}
              className="ml-1 opacity-60 hover:opacity-100"
            >
              ×
            </Link>
          </span>
        )}
      </div>

      {anomalies.length === 0 ? (
        <p className="text-sm text-muted-foreground">No anomalies detected yet.</p>
      ) : (
        <div className="space-y-2">
          {anomalies.map((a) => (
            <Link key={a.id} href={`/anomalies/${a.id}`} className="block group">
              <div className="rounded-lg ring-0 group-hover:ring-1 group-hover:ring-cyan-400/30 transition-all">
                <AnomalyCard
                  severity={a.severity}
                  summary={a.summary}
                  meta={a.root_cause_hints.slice(0, 2).join(" · ")}
                  timestamp={fmtRelative(a.detected_at)}
                />
                {/* Badges below card */}
                {(a.source !== "llm" || a.triage_status !== "new" || (a.mitre_tactics?.length ?? 0) > 0) && (
                  <div className="flex items-center gap-2 flex-wrap px-3 pb-2 -mt-1">
                    {a.source && SOURCE_LABELS[a.source] && (
                      <span className={`px-1.5 py-0.5 text-[10px] font-medium border rounded ${SOURCE_LABELS[a.source].cls}`}>
                        {SOURCE_LABELS[a.source].label}
                      </span>
                    )}
                    {a.triage_status && a.triage_status !== "new" && (
                      <span className={`px-1.5 py-0.5 text-[10px] font-medium border rounded ${TRIAGE_BADGE[a.triage_status] ?? ""}`}>
                        {a.triage_status.replace("_", " ")}
                      </span>
                    )}
                    {a.mitre_tactics?.length > 0 && (
                      <MitreBadge tactics={a.mitre_tactics} />
                    )}
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
