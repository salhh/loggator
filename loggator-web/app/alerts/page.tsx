import { api } from "@/lib/api";
import type { Alert } from "@/lib/types";

const statusColor: Record<string, string> = {
  sent: "text-emerald-400",
  failed: "text-red-400",
  pending: "text-amber-400",
};

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

export default async function AlertsPage() {
  let alerts: Alert[] = [];
  try {
    alerts = await api.alerts(100);
  } catch {
    // API offline
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Alerts</h1>
      {alerts.length === 0 ? (
        <p className="text-sm text-muted-foreground">No alerts dispatched yet.</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => (
            <div
              key={a.id}
              className="bg-card rounded-lg border border-border p-3 flex items-start justify-between gap-4"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold uppercase ${statusColor[a.status] ?? "text-muted-foreground"}`}>
                    {a.status}
                  </span>
                  <span className="text-sm font-medium text-foreground">{a.channel}</span>
                  <span className="text-xs text-muted-foreground truncate">{a.destination}</span>
                </div>
                {a.error && <p className="text-xs text-red-400">{a.error}</p>}
              </div>
              <span className="text-xs text-muted-foreground shrink-0">{fmt(a.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
