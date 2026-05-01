"use client";

// Color mapping for common MITRE ATT&CK tactics
const TACTIC_COLORS: Record<string, string> = {
  "initial access": "bg-red-900/60 text-red-300 border-red-700",
  "execution": "bg-orange-900/60 text-orange-300 border-orange-700",
  "persistence": "bg-yellow-900/60 text-yellow-300 border-yellow-700",
  "privilege escalation": "bg-amber-900/60 text-amber-300 border-amber-700",
  "defense evasion": "bg-purple-900/60 text-purple-300 border-purple-700",
  "credential access": "bg-pink-900/60 text-pink-300 border-pink-700",
  "discovery": "bg-blue-900/60 text-blue-300 border-blue-700",
  "lateral movement": "bg-chart-1/18 text-chart-1 border-chart-1/35",
  "collection": "bg-chart-4/18 text-chart-4 border-chart-4/35",
  "command and control": "bg-indigo-900/60 text-indigo-300 border-indigo-700",
  "exfiltration": "bg-rose-900/60 text-rose-300 border-rose-700",
  "impact": "bg-red-950/80 text-red-200 border-red-600",
  "reconnaissance": "bg-chart-5/18 text-chart-5 border-chart-5/35",
  "resource development": "bg-violet-900/60 text-violet-300 border-violet-700",
};

function tacticColor(tactic: string): string {
  return TACTIC_COLORS[tactic.toLowerCase()] ?? "bg-zinc-800 text-zinc-300 border-zinc-600";
}

function tacticUrl(tactic: string): string {
  const slug = tactic.toLowerCase().replace(/\s+/g, "-");
  return `https://attack.mitre.org/tactics/TA${slug}/`;
}

interface MitreBadgeProps {
  tactics: string[];
  linkable?: boolean;
  size?: "sm" | "xs";
}

export default function MitreBadge({ tactics, linkable = false, size = "xs" }: MitreBadgeProps) {
  if (!tactics || tactics.length === 0) return null;

  const cls = size === "xs"
    ? "px-1.5 py-0.5 text-[10px] font-medium border rounded"
    : "px-2 py-1 text-xs font-medium border rounded";

  return (
    <div className="flex flex-wrap gap-1">
      {tactics.map((t) => {
        const colorCls = `${cls} ${tacticColor(t)}`;
        if (linkable) {
          return (
            <a
              key={t}
              href={tacticUrl(t)}
              target="_blank"
              rel="noopener noreferrer"
              title={`View ${t} on MITRE ATT&CK`}
              className={`${colorCls} hover:brightness-125 transition-all cursor-pointer`}
            >
              {t}
            </a>
          );
        }
        return (
          <span key={t} className={colorCls}>
            {t}
          </span>
        );
      })}
    </div>
  );
}
