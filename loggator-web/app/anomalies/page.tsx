import Link from "next/link";
import { api } from "@/lib/api";
import type { Anomaly } from "@/lib/types";
import AnomalyCard from "@/components/AnomalyCard";

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

const TABS = [
  { label: "All",    href: "/anomalies",                 value: undefined as string | undefined },
  { label: "High",   href: "/anomalies?severity=high",   value: "high" },
  { label: "Medium", href: "/anomalies?severity=medium", value: "medium" },
  { label: "Low",    href: "/anomalies?severity=low",    value: "low" },
];

export default async function AnomaliesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { severity } = await searchParams;
  const raw = typeof severity === "string" ? severity.toLowerCase() : undefined;
  const validSeverity = ["high", "medium", "low"].includes(raw ?? "") ? raw : undefined;

  let anomalies: Anomaly[] = [];
  try {
    anomalies = await api.anomalies(100, validSeverity);
  } catch {
    // API offline
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Anomalies</h1>

      {/* Filter tabs */}
      <div className="flex items-center gap-4 border-b border-border">
        {TABS.map((tab) => {
          const isActive = tab.value === validSeverity;
          return (
            <Link
              key={tab.label}
              href={tab.href}
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
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
