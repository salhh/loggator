import { api } from "@/lib/api";
import type { DetectionRule } from "@/lib/types";
import MitreBadge from "@/components/MitreBadge";
import RulesClient from "./RulesClient";

const SEVERITY_CLS: Record<string, string> = {
  critical: "text-red-300",
  high:     "text-orange-300",
  medium:   "text-warning",
  low:      "text-zinc-400",
};

export default async function RulesPage() {
  let rules: DetectionRule[] = [];
  try {
    rules = await api.detectionRules();
  } catch {
    // API offline
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Detection Rules</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Deterministic rules evaluated against every log batch. Supplement AI detection with exact matches.
          </p>
        </div>
        <RulesClient rules={rules} />
      </div>

      {rules.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <p className="text-sm text-muted-foreground">No rules yet. Create your first rule to start deterministic detection.</p>
        </div>
      ) : (
        <div className="rounded-lg border border-border divide-y divide-border/50">
          {rules.map((rule) => (
            <div key={rule.id} className="px-4 py-3 space-y-1.5">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${rule.enabled ? "bg-success" : "bg-muted-foreground"}`} />
                    <span className="text-sm font-medium text-foreground">{rule.name}</span>
                    <span className={`text-xs font-semibold uppercase ${SEVERITY_CLS[rule.severity] ?? ""}`}>
                      {rule.severity}
                    </span>
                  </div>
                  {rule.description && (
                    <p className="text-xs text-muted-foreground pl-3.5">{rule.description}</p>
                  )}
                  <div className="pl-3.5 font-mono text-xs text-muted-foreground">
                    <span className="text-zinc-500">
                      {rule.condition.type != null ? String(rule.condition.type) : ""}
                    </span>
                    {" · "}
                    {rule.condition.field as string}
                    {rule.condition.op ? ` ${rule.condition.op as string}` : ""}
                    {rule.condition.value !== undefined ? ` "${rule.condition.value as string}"` : ""}
                    {rule.condition.pattern ? ` /${rule.condition.pattern as string}/` : ""}
                    {rule.condition.count ? ` ≥${rule.condition.count as number} in ${rule.condition.window_seconds as number}s` : ""}
                  </div>
                </div>
                <MitreBadge tactics={rule.mitre_tactics} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
