interface AnomalyCardProps {
  severity: string;
  summary: string;
  meta?: string;
  timestamp?: string;
}

const config = {
  high: {
    bg: "bg-[#2d1b1b]",
    border: "border-[#7f1d1d]",
    iconBg: "bg-red-500",
    iconText: "text-white",
    letter: "H",
    titleColor: "text-red-300",
  },
  medium: {
    bg: "bg-[#292118]",
    border: "border-[#78350f]",
    iconBg: "bg-amber-500",
    iconText: "text-black",
    letter: "M",
    titleColor: "text-amber-300",
  },
  low: {
    bg: "bg-card",
    border: "border-border",
    iconBg: "bg-[#374151]",
    iconText: "text-gray-300",
    letter: "L",
    titleColor: "text-gray-300",
  },
};

export default function AnomalyCard({ severity, summary, meta, timestamp }: AnomalyCardProps) {
  const c = config[severity as keyof typeof config] ?? config.low;
  return (
    <div className={`rounded-lg border p-3 flex items-start gap-3 ${c.bg} ${c.border}`}>
      <div
        className={`w-7 h-7 rounded flex items-center justify-center shrink-0 font-black text-xs ${c.iconBg} ${c.iconText}`}
      >
        {c.letter}
      </div>
      <div className="min-w-0">
        <p className={`text-sm font-semibold truncate ${c.titleColor}`}>{summary}</p>
        {(meta || timestamp) && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {[meta, timestamp].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>
    </div>
  );
}
