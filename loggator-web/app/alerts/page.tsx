import { api } from "@/lib/api";
import type { Alert } from "@/lib/types";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

const statusColor: Record<string, string> = {
  sent: "text-emerald-400",
  failed: "text-red-400",
  pending: "text-amber-400",
};

const channelIcon: Record<string, string> = {
  slack: "S",
  email: "E",
  telegram: "T",
  webhook: "W",
};

const CHANNELS = ["all", "slack", "email", "telegram", "webhook"] as const;
type Channel = (typeof CHANNELS)[number];

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{ channel?: string }>;
}) {
  const { channel: rawChannel } = await searchParams;
  const channel: Channel = CHANNELS.includes(rawChannel as Channel)
    ? (rawChannel as Channel)
    : "all";

  let alerts: Alert[] = [];
  try {
    alerts = await api.alerts(100, channel === "all" ? undefined : channel);
  } catch {
    // API offline
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Alerts</h1>
        <span className="text-xs text-muted-foreground">{alerts.length} record(s)</span>
      </div>

      {/* Channel filter tabs */}
      <div className="flex gap-1.5 flex-wrap">
        {CHANNELS.map((ch) => (
          <a
            key={ch}
            href={ch === "all" ? "/alerts" : `/alerts?channel=${ch}`}
            className={`px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-colors ${
              channel === ch
                ? "bg-cyan-400 text-black"
                : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-cyan-400/60"
            }`}
          >
            {ch}
          </a>
        ))}
      </div>

      {alerts.length === 0 ? (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <p className="text-sm text-muted-foreground">No alerts dispatched yet.</p>
          <p className="text-xs text-muted-foreground mt-1">
            Configure alert channels in Settings to start receiving notifications.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => (
            <div
              key={a.id}
              className="bg-card rounded-lg border border-border px-4 py-3 flex items-start gap-4"
            >
              <div className="shrink-0 w-7 h-7 rounded bg-secondary flex items-center justify-center text-[10px] font-bold text-muted-foreground uppercase">
                {channelIcon[a.channel] ?? a.channel[0]}
              </div>
              <div className="flex-1 min-w-0 space-y-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-semibold uppercase ${statusColor[a.status] ?? "text-muted-foreground"}`}>
                    {a.status}
                  </span>
                  <span className="text-sm font-medium text-foreground capitalize">{a.channel}</span>
                  <span className="text-xs text-muted-foreground font-mono truncate max-w-xs">{a.destination}</span>
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
