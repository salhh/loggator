import type { OpenError, SystemEventsResponse } from "@/lib/types";

const SERVICES = ["llm", "opensearch", "postgres", "scheduler", "alerts", "streaming"] as const;
const SERVICE_LABELS: Record<string, string> = {
  llm: "LLM",
  opensearch: "OpenSearch",
  postgres: "PostgreSQL",
  scheduler: "Scheduler",
  alerts: "Alerts",
  streaming: "Streaming",
};

type Dot = "healthy" | "degraded" | "error";

function getDot(service: string, openErrors: OpenError[]): Dot {
  if (openErrors.some((e) => e.service === service)) return "error";
  return "healthy";
}

function getLastEvent(
  service: string,
  openErrors: OpenError[],
  events: SystemEventsResponse["events"]
) {
  const err = openErrors.find((e) => e.service === service);
  if (err) return { message: err.message, timestamp: err.timestamp };
  const ev = events.find((e) => e.service === service);
  if (ev) return { message: ev.message, timestamp: ev.timestamp };
  return null;
}

function relativeTime(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function ServiceCard({
  service,
  dot,
  last,
}: {
  service: string;
  dot: Dot;
  last: { message: string; timestamp: string } | null;
}) {
  const dotColor =
    dot === "error"
      ? "bg-red-400"
      : dot === "degraded"
      ? "bg-amber-400"
      : "bg-emerald-400";
  const borderColor =
    dot === "error"
      ? "border-red-500/40"
      : dot === "degraded"
      ? "border-amber-400/30"
      : "border-border";

  return (
    <div
      className={`bg-card rounded-lg border ${borderColor} p-4 flex flex-col gap-2`}
    >
      <div className="flex items-center gap-2">
        <span className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${dotColor}`} />
        <span className="text-sm font-medium text-foreground">
          {SERVICE_LABELS[service] ?? service}
        </span>
      </div>
      {last ? (
        <p className="text-xs text-muted-foreground leading-relaxed break-words line-clamp-2">
          {last.message}
          <span className="ml-1 text-muted-foreground/60">
            · {relativeTime(last.timestamp)}
          </span>
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">No recent events</p>
      )}
    </div>
  );
}

export default function StatusBoard({ data }: { data: SystemEventsResponse }) {
  const { open_errors } = data.summary;
  const { events } = data;

  return (
    <div>
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Service Status
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {SERVICES.map((svc) => (
          <ServiceCard
            key={svc}
            service={svc}
            dot={getDot(svc, open_errors)}
            last={getLastEvent(svc, open_errors, events)}
          />
        ))}
      </div>
    </div>
  );
}
