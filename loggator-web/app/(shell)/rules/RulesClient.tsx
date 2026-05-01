"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { DetectionRule } from "@/lib/types";

type RuleType = "field_match" | "regex" | "threshold";

const FIELD_OPS = ["eq", "neq", "contains", "startswith", "endswith"];

interface RulesClientProps {
  rules: DetectionRule[];
}

export default function RulesClient({ rules }: RulesClientProps) {
  const [open, setOpen] = useState(false);
  const [ruleType, setRuleType] = useState<RuleType>("field_match");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [field, setField] = useState("level");
  const [op, setOp] = useState("eq");
  const [value, setValue] = useState("ERROR");
  const [pattern, setPattern] = useState("");
  const [count, setCount] = useState("10");
  const [windowSec, setWindowSec] = useState("300");
  const [mitreTactics, setMitreTactics] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function buildCondition(): Record<string, unknown> {
    if (ruleType === "field_match") {
      return { type: "field_match", field, op, value };
    }
    if (ruleType === "regex") {
      return { type: "regex", field, pattern };
    }
    return { type: "threshold", field, op: "eq", value, count: parseInt(count), window_seconds: parseInt(windowSec) };
  }

  function handleCreate() {
    if (!name.trim()) return;
    setError(null);
    startTransition(async () => {
      try {
        await api.createDetectionRule({
          name: name.trim(),
          description: description.trim() || undefined,
          condition: buildCondition(),
          severity,
          mitre_tactics: mitreTactics.split(",").map((t) => t.trim()).filter(Boolean),
          enabled,
        });
        setOpen(false);
        setName("");
        setDescription("");
        router.refresh();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to create rule");
      }
    });
  }

  async function toggleRule(rule: DetectionRule) {
    try {
      await api.patchDetectionRule(rule.id, { enabled: !rule.enabled });
      router.refresh();
    } catch {
      // ignore
    }
  }

  async function deleteRule(rule: DetectionRule) {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    try {
      await api.deleteDetectionRule(rule.id);
      router.refresh();
    } catch {
      // ignore
    }
  }

  return (
    <>
      {/* Per-rule toggle/delete buttons — rendered inline via data attributes for simplicity */}
      <div className="hidden" data-rules-manager>
        {rules.map((rule) => (
          <span key={rule.id} />
        ))}
      </div>

      <button
        onClick={() => setOpen(true)}
        className="px-3 py-1.5 rounded-md bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
      >
        + New Rule
      </button>

      {/* Per-row actions rendered as a separate overlay isn't needed — we handle inline */}
      {/* Quick action buttons on each rule row */}
      <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-10">
        {rules.filter((r) => !r.enabled).map((r) => (
          <button
            key={r.id}
            onClick={() => toggleRule(r)}
            className="hidden"
          />
        ))}
      </div>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative z-10 bg-card border border-border rounded-xl shadow-2xl w-full max-w-lg p-6 space-y-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-sm font-semibold">New Detection Rule</h2>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5 col-span-2">
                <label className="text-xs text-muted-foreground">Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Auth failure spike"
                  className="w-full text-sm bg-background border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                />
              </div>

              <div className="space-y-1.5 col-span-2">
                <label className="text-xs text-muted-foreground">Description (optional)</label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full text-sm bg-background border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="w-full text-sm bg-background border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Rule type</label>
                <select
                  value={ruleType}
                  onChange={(e) => setRuleType(e.target.value as RuleType)}
                  className="w-full text-sm bg-background border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                >
                  <option value="field_match">Field match</option>
                  <option value="regex">Regex</option>
                  <option value="threshold">Threshold</option>
                </select>
              </div>
            </div>

            {/* Condition builder */}
            <div className="rounded-lg border border-border bg-background p-3 space-y-3">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Condition</div>

              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Field</label>
                <input
                  value={field}
                  onChange={(e) => setField(e.target.value)}
                  placeholder="level"
                  className="w-full text-sm font-mono bg-card border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                />
                <p className="text-[10px] text-muted-foreground">Use dot notation for nested fields: fields.src_ip</p>
              </div>

              {ruleType === "field_match" && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Operator</label>
                    <select
                      value={op}
                      onChange={(e) => setOp(e.target.value)}
                      className="w-full text-sm bg-card border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                    >
                      {FIELD_OPS.map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Value</label>
                    <input
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      className="w-full text-sm font-mono bg-card border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                    />
                  </div>
                </div>
              )}

              {ruleType === "regex" && (
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">Pattern (regex)</label>
                  <input
                    value={pattern}
                    onChange={(e) => setPattern(e.target.value)}
                    placeholder="(?i)failed (login|auth)"
                    className="w-full text-sm font-mono bg-card border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
              )}

              {ruleType === "threshold" && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Value to match</label>
                    <input
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      className="w-full text-sm font-mono bg-card border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Min count</label>
                    <input
                      type="number"
                      value={count}
                      onChange={(e) => setCount(e.target.value)}
                      className="w-full text-sm bg-card border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                    />
                  </div>
                  <div className="space-y-1.5 col-span-2">
                    <label className="text-xs text-muted-foreground">Window (seconds)</label>
                    <input
                      type="number"
                      value={windowSec}
                      onChange={(e) => setWindowSec(e.target.value)}
                      className="w-full text-sm bg-card border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">MITRE tactics (comma-separated, optional)</label>
              <input
                value={mitreTactics}
                onChange={(e) => setMitreTactics(e.target.value)}
                placeholder="Initial Access, Credential Access"
                className="w-full text-sm bg-background border border-border rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                id="rule-enabled"
                className="rounded"
              />
              <label htmlFor="rule-enabled" className="text-xs text-muted-foreground">Enable immediately</label>
            </div>

            {error && <p className="text-xs text-red-400">{error}</p>}

            <div className="flex items-center gap-3 justify-end">
              <button
                onClick={() => setOpen(false)}
                className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={isPending || !name.trim()}
                className="px-4 py-1.5 rounded-md bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm font-medium transition-colors"
              >
                {isPending ? "Creating…" : "Create Rule"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
