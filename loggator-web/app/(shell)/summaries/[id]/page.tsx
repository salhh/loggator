import { notFound } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

export default async function SummaryDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let summary;
  try {
    summary = await api.summary(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link
          href="/summaries"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Summaries
        </Link>
        <span className="text-xs text-muted-foreground">
          {fmt(summary.window_start)} → {fmt(summary.window_end)}
        </span>
      </div>

      {/* Main card */}
      <div className="bg-card border border-border rounded-lg p-6 space-y-6">
        {/* Summary */}
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Summary
          </div>
          <p className="text-sm leading-relaxed">{summary.summary}</p>
        </div>

        {/* Top issues */}
        {summary.top_issues?.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Top issues
            </div>
            <ol className="space-y-2">
              {summary.top_issues.map((issue, i) => (
                <li key={i} className="flex gap-2 text-sm">
                  <span className="text-primary font-semibold shrink-0">{i + 1}.</span>
                  <span className="text-muted-foreground">{issue}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Recommendation */}
        {summary.recommendation && (
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Recommendation
            </div>
            <p className="border-l-2 border-primary pl-4 py-1 text-sm text-muted-foreground leading-relaxed">
              {summary.recommendation}
            </p>
          </div>
        )}

        {/* Metadata footer */}
        <div className="flex gap-6 pt-4 border-t border-border text-xs text-muted-foreground">
          <span>
            Errors: <strong className="text-foreground">{summary.error_count}</strong>
          </span>
          <span>Model: <span className="font-mono">{summary.model_used}</span></span>
          {summary.tokens_used && (
            <span>Tokens: <strong className="text-foreground">{summary.tokens_used}</strong></span>
          )}
        </div>
      </div>
    </div>
  );
}
