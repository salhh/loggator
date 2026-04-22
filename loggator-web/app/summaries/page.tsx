import Link from "next/link";
import { api } from "@/lib/api";
import type { Summary } from "@/lib/types";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

export default async function SummariesPage() {
  let summaries: Summary[] = [];
  try {
    summaries = await api.summaries(50);
  } catch {
    // API offline
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Summaries</h1>
      {summaries.length === 0 ? (
        <p className="text-sm text-muted-foreground">No summaries yet. Run a batch to generate one.</p>
      ) : (
        <div className="space-y-3">
          {summaries.map((s) => (
            <Link key={s.id} href={`/summaries/${s.id}`} className="block">
              <div className="bg-card rounded-lg border border-border p-4 space-y-3 hover:border-cyan-400/40 transition-colors cursor-pointer">
                <div className="text-xs text-muted-foreground">
                  {fmt(s.window_start)} → {fmt(s.window_end)}
                </div>
                <p className="text-sm leading-relaxed">{s.summary}</p>
                {s.top_issues.length > 0 && (
                  <ul className="list-disc list-inside text-xs text-muted-foreground space-y-1">
                    {s.top_issues.map((issue, i) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                )}
                {s.recommendation && (
                  <p className="text-xs border-l-2 border-cyan-400 pl-3 text-muted-foreground">
                    {s.recommendation}
                  </p>
                )}
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>
                    Errors: <strong className="text-foreground">{s.error_count}</strong>
                  </span>
                  <span>Model: {s.model_used}</span>
                  {s.tokens_used && <span>Tokens: {s.tokens_used}</span>}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
