import { api } from "@/lib/api";
import type { Anomaly } from "@/lib/types";
import AnomalyCard from "@/components/AnomalyCard";

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

export default async function AnomaliesPage() {
  let anomalies: Anomaly[] = [];
  try {
    anomalies = await api.anomalies(100);
  } catch {
    // API offline
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Anomalies</h1>
      {anomalies.length === 0 ? (
        <p className="text-sm text-muted-foreground">No anomalies detected yet.</p>
      ) : (
        <div className="space-y-2">
          {anomalies.map((a) => (
            <AnomalyCard
              key={a.id}
              severity={a.severity}
              summary={a.summary}
              meta={a.root_cause_hints.slice(0, 2).join(" · ")}
              timestamp={fmtRelative(a.detected_at)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
