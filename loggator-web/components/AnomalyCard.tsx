interface AnomalyCardProps {
  severity: string;
  summary: string;
  meta?: string;
  timestamp?: string;
}

const config = {
  high: {
    bg: "bg-red-950/30",
    border: "border-red-900/60",
    iconBg: "bg-red-500",
    iconText: "text-white",
    letter: "H",
    titleColor: "text-red-300",
    dot: "bg-red-500",
  },
  medium: {
    bg: "bg-amber-950/20",
    border: "border-amber-900/50",
    iconBg: "bg-amber-500",
    iconText: "text-black",
    letter: "M",
    titleColor: "text-amber-300",
    dot: "bg-amber-500",
  },
  low: {
    bg: "bg-card",
    border: "border-border",
    iconBg: "bg-secondary",
    iconText: "text-muted-foreground",
    letter: "L",
    titleColor: "text-foreground",
    dot: "bg-border",
  },
};

export default function AnomalyCard({ severity, summary, meta, timestamp }: AnomalyCardProps) {
  const c = config[severity as keyof typeof config] ?? config.low;
  return (
    <div className={`rounded-md border px-3 py-2.5 flex items-start gap-2.5 ${c.bg} ${c.border}`}>
      <span className={`mt-0.5 h-2 w-2 rounded-full shrink-0 ${c.dot}`} />
      <div className="min-w-0 space-y-0.5">
        <p className={`text-sm leading-snug line-clamp-2 ${c.titleColor}`}>{summary}</p>
        {(meta || timestamp) && (
          <p className="text-[11px] text-muted-foreground">
            {[meta, timestamp].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>
    </div>
  );
}
