import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import type { AnalysisReport } from "@/lib/types";
import AnalysisPanel from "@/components/AnalysisPanel";

function scheduledToReport(r: Awaited<ReturnType<typeof api.analysisReport>>): AnalysisReport {
  return {
    summary: r.summary,
    affected_services: r.affected_services,
    root_causes: r.root_causes,
    timeline: r.timeline,
    recommendations: r.recommendations,
    error_count: r.error_count,
    warning_count: r.warning_count,
    log_count: r.log_count,
    chunk_count: r.chunk_count,
    from_ts: r.window_start,
    to_ts: r.window_end,
  };
}

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let record: Awaited<ReturnType<typeof api.analysisReport>>;
  try {
    record = await api.analysisReport(id);
  } catch {
    notFound();
  }

  const report = scheduledToReport(record);

  return (
    <div className="space-y-4 max-w-5xl">
      {/* Back link */}
      <div className="flex items-center gap-3">
        <Link
          href="/reports"
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Reports
        </Link>
        <span
          className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
            record.status === "success"
              ? "border-success/40 bg-success/10 text-success"
              : "border-red-900 bg-red-950/40 text-red-400"
          }`}
        >
          {record.status}
        </span>
        <span className="text-xs text-muted-foreground font-mono">
          {record.index_pattern}
        </span>
      </div>

      {/* Analysis panel */}
      <AnalysisPanel report={report} />
    </div>
  );
}
