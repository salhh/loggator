"use client";

import type { AnomalyEnrichment, EnrichmentResult } from "@/lib/types";

const REPUTATION_CONFIG = {
  clean:      { cls: "bg-success/12 text-success border-success/35", label: "Clean" },
  suspicious: { cls: "bg-warning/12 text-warning border-warning/35",       label: "Suspicious" },
  malicious:  { cls: "bg-red-900/50 text-red-300 border-red-700",             label: "Malicious" },
  unknown:    { cls: "bg-zinc-800 text-zinc-400 border-zinc-600",              label: "Unknown" },
};

function IPRow({ result }: { result: EnrichmentResult }) {
  const rep = REPUTATION_CONFIG[result.reputation] ?? REPUTATION_CONFIG.unknown;
  const details = result.details ?? {};
  return (
    <div className="flex items-start gap-3 py-1.5 border-b border-border last:border-0">
      <div className="font-mono text-xs text-foreground min-w-[120px]">{result.value}</div>
      <span className={`px-1.5 py-0.5 text-[10px] font-medium border rounded shrink-0 ${rep.cls}`}>
        {rep.label}
      </span>
      <div className="text-xs text-muted-foreground space-y-0.5 min-w-0">
        {result.confidence_score !== null && (
          <div>Score: {result.confidence_score}/100 via {result.source}</div>
        )}
        {details.country_code != null && String(details.country_code) !== "" ? (
          <div>Country: {String(details.country_code)}</div>
        ) : null}
        {details.isp != null && String(details.isp) !== "" ? <div>ISP: {String(details.isp)}</div> : null}
        {details.classification != null && String(details.classification) !== "" ? (
          <div>Class: {String(details.classification)}</div>
        ) : null}
      </div>
    </div>
  );
}

interface EnrichmentPanelProps {
  enrichment: AnomalyEnrichment;
}

export default function EnrichmentPanel({ enrichment }: EnrichmentPanelProps) {
  const hasIPs = enrichment.ips?.length > 0;
  const hasHashes = enrichment.hashes?.length > 0;
  const hasDomains = enrichment.domains?.length > 0;

  if (!hasIPs && !hasHashes && !hasDomains) return null;

  return (
    <div className="space-y-1.5">
      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Threat Intelligence
      </div>
      <div className="rounded-lg border border-border bg-background p-3 space-y-3">
        {hasIPs && (
          <div>
            <div className="text-xs text-muted-foreground mb-1.5">IP Reputation</div>
            <div className="divide-y divide-border">
              {enrichment.ips.map((r) => (
                <IPRow key={r.value} result={r} />
              ))}
            </div>
          </div>
        )}

        {hasDomains && (
          <div>
            <div className="text-xs text-muted-foreground mb-1">Domains</div>
            <div className="flex flex-wrap gap-1">
              {enrichment.domains.map((d) => (
                <span key={d} className="px-1.5 py-0.5 rounded border border-border text-xs font-mono text-muted-foreground">
                  {d}
                </span>
              ))}
            </div>
          </div>
        )}

        {hasHashes && (
          <div>
            <div className="text-xs text-muted-foreground mb-1">File Hashes</div>
            <div className="space-y-0.5">
              {enrichment.hashes.map((h) => (
                <div key={h} className="font-mono text-xs text-muted-foreground break-all">{h}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
