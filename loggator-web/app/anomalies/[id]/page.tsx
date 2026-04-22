import { notFound } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

const severityConfig = {
  high: {
    bg: "bg-[#2d1b1b]",
    border: "border-[#7f1d1d]",
    text: "text-red-300",
  },
  medium: {
    bg: "bg-[#292118]",
    border: "border-[#78350f]",
    text: "text-amber-300",
  },
  low: {
    bg: "bg-card",
    border: "border-border",
    text: "text-gray-300",
  },
} as const;

export default async function AnomalyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let anomaly;
  try {
    anomaly = await api.anomaly(id);
  } catch {
    notFound();
  }

  const c = severityConfig[anomaly.severity as keyof typeof severityConfig] ?? severityConfig.low;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link
          href="/anomalies"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
        >
          ← Anomalies
        </Link>
        <span
          className={`px-2.5 py-1 rounded border text-xs font-bold uppercase ${c.bg} ${c.border} ${c.text}`}
        >
          {anomaly.severity}
        </span>
      </div>

      {/* Body */}
      <div className="grid grid-cols-[1fr_320px] gap-6">
        {/* Left column */}
        <div className="space-y-6">
          {/* Summary */}
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Summary
            </div>
            <p className="text-sm leading-relaxed">{anomaly.summary}</p>
          </div>

          {/* Root cause hints */}
          {anomaly.root_cause_hints?.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Root cause hints
              </div>
              <ol className="space-y-1.5">
                {anomaly.root_cause_hints.map((hint, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="text-cyan-400 font-semibold shrink-0">{i + 1}.</span>
                    <span>{hint}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Raw logs */}
          {anomaly.raw_logs && anomaly.raw_logs.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Raw logs ({anomaly.raw_logs.length})
              </div>
              <div className="max-h-[400px] overflow-auto rounded-lg border border-border bg-background p-4">
                <pre className="font-mono text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {anomaly.raw_logs
                    .map((entry) =>
                      typeof entry === "string" ? entry : JSON.stringify(entry, null, 2)
                    )
                    .join("\n")}
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* Right column — metadata */}
        <div className="bg-card border border-border rounded-lg p-4 space-y-4 h-fit">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Details
          </div>

          <div className="space-y-3 text-sm">
            <div className="space-y-0.5">
              <div className="text-xs text-muted-foreground">Index pattern</div>
              <div className="font-mono text-xs">{anomaly.index_pattern}</div>
            </div>

            <div className="space-y-0.5">
              <div className="text-xs text-muted-foreground">Detected at</div>
              <div className="text-xs">{fmt(anomaly.detected_at)}</div>
            </div>

            <div className="space-y-0.5">
              <div className="text-xs text-muted-foreground">Log timestamp</div>
              <div className="text-xs">
                {anomaly.log_timestamp ? fmt(anomaly.log_timestamp) : "—"}
              </div>
            </div>

            <div className="space-y-0.5">
              <div className="text-xs text-muted-foreground">Model</div>
              <div className="font-mono text-xs">{anomaly.model_used}</div>
            </div>

            <div className="space-y-0.5">
              <div className="text-xs text-muted-foreground">Alerted</div>
              <div
                className={`text-xs font-semibold ${
                  anomaly.alerted ? "text-emerald-400" : "text-muted-foreground"
                }`}
              >
                {anomaly.alerted ? "Yes" : "No"}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
