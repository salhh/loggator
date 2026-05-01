"use client";

import { useState, useEffect, useRef } from "react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { ScheduleStatus } from "@/lib/types";

interface Props {
  initial: Record<string, string>;
  envFile: string;
}

const ALERT_KEYS = new Set([
  "ALERT_SEVERITY_THRESHOLD",
  "SLACK_WEBHOOK_URL",
  "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
  "ALERT_FROM_EMAIL", "ALERT_EMAIL_TO",
  "ALERT_WEBHOOK_URL",
  "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
  "ALERT_COOLDOWN_MINUTES",
]);

const TABS = [
  { id: "alerts",   label: "Alerts" },
  { id: "schedule", label: "Schedule" },
  { id: "ingest-keys", label: "Ingest keys" },
  { id: "members", label: "Members" },
  { id: "advanced", label: "Advanced" },
] as const;
type TabId = (typeof TABS)[number]["id"];

/* ── Guide modal ────────────────────────────────────────────────────────── */

interface GuideStep { title: string; steps: (string | { text: string; code: string })[]; }

const GUIDES: Record<string, { heading: string; sections: GuideStep[] }> = {
  slack: {
    heading: "How to get a Slack Webhook URL",
    sections: [
      {
        title: "1. Create a Slack App",
        steps: [
          "Go to api.slack.com/apps and click Create New App.",
          "Choose From scratch, give it a name (e.g. Loggator) and select your workspace.",
        ],
      },
      {
        title: "2. Enable Incoming Webhooks",
        steps: [
          "In the left sidebar, click Incoming Webhooks.",
          "Toggle Activate Incoming Webhooks to ON.",
        ],
      },
      {
        title: "3. Add a webhook to a channel",
        steps: [
          "Scroll down and click Add New Webhook to Workspace.",
          "Pick the channel where alerts should appear (e.g. #alerts) and click Allow.",
        ],
      },
      {
        title: "4. Copy the URL",
        steps: [
          "Copy the URL shown — it looks like:",
          { text: "Webhook URL format", code: "https://hooks.slack.com/services/T.../B.../..." },
          "Paste it into the Webhook URL field and click Save, then Test.",
        ],
      },
    ],
  },
  telegram: {
    heading: "How to set up a Telegram Bot",
    sections: [
      {
        title: "1. Create a bot with BotFather",
        steps: [
          "Open Telegram and search for @BotFather.",
          "Send /newbot and follow the prompts to choose a name and username.",
          "BotFather will reply with your Bot Token — copy it.",
        ],
      },
      {
        title: "2. Get your Chat ID",
        steps: [
          "Send any message to your new bot in Telegram.",
          "Open this URL in your browser (replace TOKEN with your bot token):",
          { text: "getUpdates URL", code: "https://api.telegram.org/bot<TOKEN>/getUpdates" },
          'Find "chat" → "id" in the JSON response. For channels it will be a negative number like -1001234567890.',
        ],
      },
      {
        title: "3. For a channel (optional)",
        steps: [
          "Add your bot as an Administrator to the channel.",
          "Use the channel's numeric ID (starts with -100) or its @username as the Chat ID.",
        ],
      },
      {
        title: "4. Paste into Loggator",
        steps: [
          "Enter the Bot Token and Chat ID, then click Save and Test.",
        ],
      },
    ],
  },
  email: {
    heading: "How to set up Email (SMTP) alerts",
    sections: [
      {
        title: "1. Gather your SMTP settings",
        steps: [
          "You need: SMTP host, port, username, password, and a sender address.",
          "Common providers: Gmail (smtp.gmail.com:587), Outlook (smtp.office365.com:587), AWS SES (email-smtp.<region>.amazonaws.com:587).",
        ],
      },
      {
        title: "2. App passwords (Gmail / Outlook)",
        steps: [
          "If you use 2-factor authentication (recommended), create an App Password instead of your account password.",
          "Gmail: Google Account → Security → App Passwords → Mail.",
          "Outlook: Account settings → Security → Create and manage app passwords.",
        ],
      },
      {
        title: "3. Fill in the Loggator fields",
        steps: [
          "SMTP Host — your provider's SMTP address (e.g. smtp.gmail.com).",
          "SMTP Port — usually 587 (STARTTLS) or 465 (SSL).",
          "SMTP Username — your email address or SMTP user.",
          "SMTP Password — your app password or SMTP password.",
          "From email — the address alerts will appear to come from.",
          "Alert email to — one or more comma-separated recipient addresses.",
        ],
      },
      {
        title: "4. Save and Test",
        steps: [
          "Click Save, then Test. A test alert will be sent to the recipient address.",
          "Check your spam folder if it doesn't arrive within a minute.",
        ],
      },
    ],
  },
  webhook: {
    heading: "How to set up a Custom Webhook",
    sections: [
      {
        title: "1. What Loggator sends",
        steps: [
          "Loggator will POST JSON to your URL whenever an alert fires.",
          { text: "Payload structure", code: '{"severity":"high","summary":"...","detected_at":"2026-05-01T...","index_pattern":"logs-*","mitre_tactics":[],"root_cause_hints":[]}' },
        ],
      },
      {
        title: "2. Headers sent",
        steps: [
          'Content-Type: application/json',
          "No authentication header is added by default — use a secret in the URL query string if your endpoint requires it.",
        ],
      },
      {
        title: "3. Example receiver (Python)",
        steps: [
          { text: "Flask example", code: "from flask import Flask, request\napp = Flask(__name__)\n@app.post('/loggator')\ndef recv():\n    data = request.json\n    print(data['severity'], data['summary'])\n    return '', 200" },
        ],
      },
      {
        title: "4. Example receiver (Node.js)",
        steps: [
          { text: "Express example", code: "app.post('/loggator', express.json(), (req, res) => {\n  console.log(req.body.severity, req.body.summary);\n  res.sendStatus(200);\n});" },
        ],
      },
      {
        title: "5. Paste your URL and test",
        steps: [
          "Enter the full URL (including any secret query params) and click Save, then Test.",
          "Loggator expects any 2xx response — non-2xx will be logged as a delivery failure.",
        ],
      },
    ],
  },
};

function GuideModal({ guide, onClose }: { guide: string; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const g = GUIDES[guide];
  if (!g) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        ref={ref}
        className="relative z-10 bg-card border border-border rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border sticky top-0 bg-card z-10">
          <h2 className="text-sm font-semibold text-foreground">{g.heading}</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors text-lg leading-none">✕</button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-5">
          {g.sections.map((section) => (
            <div key={section.title} className="space-y-2">
              <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">{section.title}</div>
              <ul className="space-y-2">
                {section.steps.map((step, i) =>
                  typeof step === "string" ? (
                    <li key={i} className="text-sm text-muted-foreground leading-relaxed flex gap-2">
                      <span className="text-border mt-0.5">›</span>
                      <span>{step}</span>
                    </li>
                  ) : (
                    <li key={i}>
                      <code className="block w-full bg-background border border-border rounded-md px-3 py-2 text-xs font-mono text-cyan-300 break-all">
                        {step.code}
                      </code>
                    </li>
                  )
                )}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function GuideButton({ guide, onOpen }: { guide: string; onOpen: (g: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(guide)}
      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-cyan-400 transition-colors border border-border hover:border-cyan-400/60 rounded-md px-2 py-1"
      title="How to get this"
    >
      <span className="text-[11px]">?</span> How to get this
    </button>
  );
}

/* ── Primitives ─────────────────────────────────────────────────────────── */

function SecretInput({ value, onChange, isDirty }: { value: string; onChange: (v: string) => void; isDirty: boolean }) {
  const [show, setShow] = useState(false);
  return (
    <div className="flex gap-2">
      <Input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`font-mono text-sm bg-card border-border flex-1 ${isDirty ? "border-cyan-400" : ""}`}
      />
      <button type="button" onClick={() => setShow((v) => !v)}
        className="px-2.5 py-1.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors shrink-0">
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}

function Field({ label, helper, children }: { label: string; helper?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{label}</label>
      {children}
      {helper && <p className="text-xs text-muted-foreground">{helper}</p>}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-4">
      <div className="text-sm font-semibold text-foreground">{title}</div>
      {children}
    </div>
  );
}

function TestBtn({ channel, loading, result, onTest }: {
  channel: string; loading: boolean; result: string; onTest: () => void;
}) {
  return (
    <div className="flex items-center gap-2 pt-1">
      <button type="button" onClick={onTest} disabled={loading}
        className="px-3 py-1.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors disabled:opacity-40">
        {loading ? "Sending…" : "Send test"}
      </button>
      {result && (
        <span className={`text-xs ${result.startsWith("✓") ? "text-emerald-400" : "text-red-400"}`}>{result}</span>
      )}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────────── */

export default function SettingsClient({ initial, envFile }: Props) {
  const [tab, setTab] = useState<TabId>("alerts");
  const [values, setValues] = useState<Record<string, string>>(initial);
  const [dirty, setDirty] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [scheduleStatus, setScheduleStatus] = useState<ScheduleStatus | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [intervalInput, setIntervalInput] = useState("");
  const [windowInput, setWindowInput] = useState("");
  const [testResults, setTestResults] = useState<Record<string, string>>({});
  const [testLoading, setTestLoading] = useState<Record<string, boolean>>({});
  const [openGuide, setOpenGuide] = useState<string | null>(null);
  const [ingestKeys, setIngestKeys] = useState<
    Awaited<ReturnType<typeof api.listTenantApiKeys>>
  >([]);
  const [ingestKeysLoading, setIngestKeysLoading] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [justCreatedKey, setJustCreatedKey] = useState<string | null>(null);
  const [members, setMembers] = useState<Awaited<ReturnType<typeof api.tenantMembers>>>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [newMemberSubject, setNewMemberSubject] = useState("");
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<"tenant_admin" | "tenant_member">("tenant_member");

  useEffect(() => {
    api.scheduleStatus().then(setScheduleStatus).catch(() => {});
  }, []);

  async function loadIngestKeys() {
    setIngestKeysLoading(true);
    try {
      setIngestKeys(await api.listTenantApiKeys());
    } catch {
      setIngestKeys([]);
    } finally {
      setIngestKeysLoading(false);
    }
  }

  useEffect(() => {
    if (tab === "ingest-keys") void loadIngestKeys();
  }, [tab]);

  async function loadMembers() {
    setMembersLoading(true);
    try {
      setMembers(await api.tenantMembers());
    } catch {
      setMembers([]);
    } finally {
      setMembersLoading(false);
    }
  }

  useEffect(() => {
    if (tab === "members") void loadMembers();
  }, [tab]);

  useEffect(() => {
    if (!scheduleStatus) return;
    setIntervalInput(String(scheduleStatus.interval_minutes));
    setWindowInput(String(scheduleStatus.window_minutes));
  }, [scheduleStatus]);

  function onChange(key: string, value: string) {
    setValues((p) => ({ ...p, [key]: value }));
    setDirty((p) => ({ ...p, [key]: value }));
    setSaved(false);
  }

  const val = (key: string) => dirty[key] ?? values[key] ?? "";
  const isDirty = (key: string) => dirty[key] !== undefined;

  async function updateSchedule(patch: Parameters<typeof api.updateSchedule>[0]) {
    setScheduleLoading(true);
    try {
      setScheduleStatus(await api.updateSchedule(patch));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to update schedule.";
      alert(msg);
    } finally {
      setScheduleLoading(false);
    }
  }

  async function testChannel(channel: "slack" | "email" | "telegram" | "webhook") {
    setTestLoading((p) => ({ ...p, [channel]: true }));
    setTestResults((p) => ({ ...p, [channel]: "" }));
    try {
      const res = await api.testAlert(channel);
      setTestResults((p) => ({ ...p, [channel]: res.ok ? "✓ Test sent" : `✗ ${res.error ?? "unknown error"}` }));
    } catch {
      setTestResults((p) => ({ ...p, [channel]: "✗ Request failed" }));
    } finally {
      setTestLoading((p) => ({ ...p, [channel]: false }));
    }
  }

  async function save() {
    if (Object.keys(dirty).length === 0) return;
    setSaving(true);
    try {
      const res = await api.updateSettings(dirty);
      setValues(res.settings);
      setDirty({});
      setSaved(true);
    } catch { alert("Failed to save settings."); }
    finally { setSaving(false); }
  }

  const dirtyCount = Object.keys(dirty).length;

  return (
    <div className="space-y-5">
      {openGuide && <GuideModal guide={openGuide} onClose={() => setOpenGuide(null)} />}

      {/* ── Tab bar ───────────────────────────────────────────────────────── */}
      <div className="flex border-b border-border">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              tab === id
                ? "text-cyan-400 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-cyan-400"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
        {/* Unsaved indicator lives in the tab bar, always visible */}
        {dirtyCount > 0 && (
          <span className="ml-auto self-center text-xs text-amber-400 pr-1">
            {dirtyCount} unsaved change{dirtyCount !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* ── Alerts tab ───────────────────────────────────────────────────── */}
      {tab === "alerts" && (
        <div className="space-y-4">
          {/* General */}
          <Card title="General">
            <Field label="Severity threshold" helper="Only anomalies at or above this level trigger alerts.">
              <select
                value={val("ALERT_SEVERITY_THRESHOLD") || "medium"}
                onChange={(e) => onChange("ALERT_SEVERITY_THRESHOLD", e.target.value)}
                className={`w-full bg-background border rounded-md px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-cyan-400 transition-colors ${
                  isDirty("ALERT_SEVERITY_THRESHOLD") ? "border-cyan-400" : "border-border"
                }`}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
            <Field label="Cooldown (minutes)" helper="Minimum gap between alerts for the same index + severity.">
              <Input type="number" min={0} value={val("ALERT_COOLDOWN_MINUTES") || "5"}
                onChange={(e) => onChange("ALERT_COOLDOWN_MINUTES", e.target.value)}
                className={`font-mono text-sm bg-card border-border w-28 ${isDirty("ALERT_COOLDOWN_MINUTES") ? "border-cyan-400" : ""}`}
              />
            </Field>
          </Card>

          {/* Slack */}
          <Card title="Slack">
            <div className="flex items-center justify-between -mt-1 mb-1">
              <span className="text-xs text-muted-foreground">Incoming Webhooks</span>
              <GuideButton guide="slack" onOpen={setOpenGuide} />
            </div>
            <Field label="Webhook URL">
              <div className="flex gap-2">
                <div className="flex-1">
                  <SecretInput value={val("SLACK_WEBHOOK_URL")} onChange={(v) => onChange("SLACK_WEBHOOK_URL", v)} isDirty={isDirty("SLACK_WEBHOOK_URL")} />
                </div>
              </div>
            </Field>
            <TestBtn channel="slack" loading={!!testLoading["slack"]} result={testResults["slack"] ?? ""} onTest={() => testChannel("slack")} />
          </Card>

          {/* Telegram */}
          <Card title="Telegram">
            <div className="flex items-center justify-between -mt-1 mb-1">
              <span className="text-xs text-muted-foreground">Bot API</span>
              <GuideButton guide="telegram" onOpen={setOpenGuide} />
            </div>
            <Field label="Bot Token">
              <SecretInput value={val("TELEGRAM_BOT_TOKEN")} onChange={(v) => onChange("TELEGRAM_BOT_TOKEN", v)} isDirty={isDirty("TELEGRAM_BOT_TOKEN")} />
            </Field>
            <Field label="Chat ID" helper="Numeric chat ID (e.g. -1001234567890) or @channelname">
              <Input value={val("TELEGRAM_CHAT_ID")} onChange={(e) => onChange("TELEGRAM_CHAT_ID", e.target.value)}
                className={`font-mono text-sm bg-card border-border ${isDirty("TELEGRAM_CHAT_ID") ? "border-cyan-400" : ""}`}
              />
            </Field>
            <TestBtn channel="telegram" loading={!!testLoading["telegram"]} result={testResults["telegram"] ?? ""} onTest={() => testChannel("telegram")} />
          </Card>

          {/* Email */}
          <Card title="Email (SMTP)">
            <div className="flex items-center justify-between -mt-1 mb-1">
              <span className="text-xs text-muted-foreground">SMTP delivery</span>
              <GuideButton guide="email" onOpen={setOpenGuide} />
            </div>
            <div className="grid grid-cols-[1fr_100px] gap-3">
              <Field label="SMTP Host">
                <Input value={val("SMTP_HOST")} onChange={(e) => onChange("SMTP_HOST", e.target.value)}
                  className={`font-mono text-sm bg-card border-border ${isDirty("SMTP_HOST") ? "border-cyan-400" : ""}`}
                />
              </Field>
              <Field label="Port">
                <Input value={val("SMTP_PORT")} onChange={(e) => onChange("SMTP_PORT", e.target.value)}
                  className={`font-mono text-sm bg-card border-border ${isDirty("SMTP_PORT") ? "border-cyan-400" : ""}`}
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Username">
                <Input value={val("SMTP_USERNAME")} onChange={(e) => onChange("SMTP_USERNAME", e.target.value)}
                  className={`font-mono text-sm bg-card border-border ${isDirty("SMTP_USERNAME") ? "border-cyan-400" : ""}`}
                />
              </Field>
              <Field label="Password">
                <SecretInput value={val("SMTP_PASSWORD")} onChange={(v) => onChange("SMTP_PASSWORD", v)} isDirty={isDirty("SMTP_PASSWORD")} />
              </Field>
            </div>
            <Field label="From address">
              <Input value={val("ALERT_FROM_EMAIL")} onChange={(e) => onChange("ALERT_FROM_EMAIL", e.target.value)}
                className={`font-mono text-sm bg-card border-border ${isDirty("ALERT_FROM_EMAIL") ? "border-cyan-400" : ""}`}
              />
            </Field>
            <Field label="Recipients" helper="Comma-separated email addresses">
              <Input value={val("ALERT_EMAIL_TO")} onChange={(e) => onChange("ALERT_EMAIL_TO", e.target.value)}
                className={`font-mono text-sm bg-card border-border ${isDirty("ALERT_EMAIL_TO") ? "border-cyan-400" : ""}`}
              />
            </Field>
            <TestBtn channel="email" loading={!!testLoading["email"]} result={testResults["email"] ?? ""} onTest={() => testChannel("email")} />
          </Card>

          {/* Webhook */}
          <Card title="Custom Webhook">
            <div className="flex items-center justify-between -mt-1 mb-1">
              <span className="text-xs text-muted-foreground">POST JSON to any URL</span>
              <GuideButton guide="webhook" onOpen={setOpenGuide} />
            </div>
            <Field label="Webhook URL">
              <div className="flex gap-2">
                <div className="flex-1">
                  <Input value={val("ALERT_WEBHOOK_URL")} onChange={(e) => onChange("ALERT_WEBHOOK_URL", e.target.value)}
                    className={`font-mono text-sm bg-card border-border ${isDirty("ALERT_WEBHOOK_URL") ? "border-cyan-400" : ""}`}
                  />
                </div>
              </div>
            </Field>
            <TestBtn channel="webhook" loading={!!testLoading["webhook"]} result={testResults["webhook"] ?? ""} onTest={() => testChannel("webhook")} />
          </Card>
        </div>
      )}

      {/* ── Schedule tab ─────────────────────────────────────────────────── */}
      {tab === "schedule" && (
        <div className="space-y-4">
          <Card title="RCA Schedule">
            <Field label="Scheduled analysis" helper="When enabled, a full RCA runs automatically on the configured interval.">
              <div className="flex items-center gap-3">
                <button type="button"
                  onClick={() => scheduleStatus && updateSchedule({ enabled: !scheduleStatus.enabled })}
                  disabled={scheduleLoading || !scheduleStatus}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-40 ${
                    scheduleStatus?.enabled ? "bg-cyan-400" : "bg-border"
                  }`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    scheduleStatus?.enabled ? "translate-x-4" : "translate-x-0"
                  }`} />
                </button>
                <span className="text-sm text-muted-foreground">
                  {scheduleStatus ? (scheduleStatus.enabled ? "Enabled" : "Disabled") : "Loading…"}
                </span>
              </div>
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Interval (minutes)" helper="How often the scheduled RCA job runs (not the batch summarizer — that uses BATCH_INTERVAL_MINUTES in Advanced).">
                <Input type="number" min={1} max={1440}
                  value={intervalInput}
                  onChange={(e) => setIntervalInput(e.target.value)}
                  disabled={scheduleLoading || !scheduleStatus}
                  className="font-mono text-sm bg-card border-border"
                />
              </Field>
              <Field label="Window (minutes)" helper="How far back each RCA run looks in OpenSearch">
                <Input type="number" min={1} max={1440}
                  value={windowInput}
                  onChange={(e) => setWindowInput(e.target.value)}
                  disabled={scheduleLoading || !scheduleStatus}
                  className="font-mono text-sm bg-card border-border"
                />
              </Field>
            </div>
            <button
              type="button"
              disabled={scheduleLoading || !scheduleStatus}
              onClick={() => {
                const iv = parseInt(intervalInput, 10);
                const wv = parseInt(windowInput, 10);
                if (isNaN(iv) || iv < 1 || iv > 1440) {
                  alert("Interval must be between 1 and 1440.");
                  return;
                }
                if (isNaN(wv) || wv < 1 || wv > 1440) {
                  alert("Window must be between 1 and 1440.");
                  return;
                }
                void updateSchedule({ interval_minutes: iv, window_minutes: wv });
              }}
              className="px-4 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {scheduleLoading ? "Saving…" : "Apply interval & window"}
            </button>

            {scheduleStatus && (
              <div className="rounded-md bg-background border border-border divide-y divide-border/50">
                {[
                  { label: "Next run", value: scheduleStatus.next_run_at ? new Date(scheduleStatus.next_run_at).toLocaleString() : "—" },
                  { label: "Last run", value: scheduleStatus.last_run_at ? new Date(scheduleStatus.last_run_at).toLocaleString() : "—" },
                  ...(scheduleStatus.last_run_status ? [{ label: "Last status", value: scheduleStatus.last_run_status, accent: scheduleStatus.last_run_status }] : []),
                ].map(({ label, value, accent }) => (
                  <div key={label} className="flex items-center justify-between px-3 py-2 text-xs">
                    <span className="text-muted-foreground">{label}</span>
                    <span className={accent === "success" ? "text-emerald-400" : accent === "failed" ? "text-red-400" : "text-foreground font-mono"}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Ingest API keys ─────────────────────────────────────────────── */}
      {tab === "ingest-keys" && (
        <div className="space-y-4">
          <Card title="HTTP ingest (lgk_ keys)">
            <p className="text-xs text-muted-foreground mb-3">
              Requires a JWT with <span className="font-mono">tenant_admin</span> or{" "}
              <span className="font-mono">platform_admin</span> (or auth disabled in dev). Use{" "}
              <span className="font-mono">Authorization: Bearer lgk_…</span> or{" "}
              <span className="font-mono">X-API-Key</span> on <span className="font-mono">POST /api/v1/ingest/logs</span>.
            </p>
            <div className="flex gap-2 items-end">
              <Field label="Name">
                <Input
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g. fluent-bit-prod"
                  className="font-mono text-sm bg-card border-border"
                />
              </Field>
              <button
                type="button"
                disabled={ingestKeysLoading || !newKeyName.trim()}
                onClick={async () => {
                  try {
                    const res = await api.createTenantApiKey(newKeyName.trim());
                    setJustCreatedKey(res.key);
                    setNewKeyName("");
                    await loadIngestKeys();
                  } catch (e) {
                    alert(e instanceof Error ? e.message : "Failed to create key");
                  }
                }}
                className="px-3 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40"
              >
                Create key
              </button>
            </div>
            {justCreatedKey && (
              <div className="mt-3 rounded-md border border-amber-500/50 bg-amber-950/30 px-3 py-2 text-xs">
                <p className="text-amber-200 font-medium mb-1">Copy this secret now — it will not be shown again.</p>
                <code className="break-all text-foreground select-all">{justCreatedKey}</code>
                <button
                  type="button"
                  className="block mt-2 text-cyan-400 hover:underline"
                  onClick={() => setJustCreatedKey(null)}
                >
                  Dismiss
                </button>
              </div>
            )}
            <div className="mt-4 rounded-md border border-border divide-y divide-border/50">
              {ingestKeysLoading ? (
                <div className="px-3 py-2 text-xs text-muted-foreground">Loading…</div>
              ) : ingestKeys.length === 0 ? (
                <div className="px-3 py-2 text-xs text-muted-foreground">No keys yet.</div>
              ) : (
                ingestKeys.map((k) => {
                  const now = Date.now();
                  const expiresAt = k.expires_at ? new Date(k.expires_at).getTime() : null;
                  const isExpired = expiresAt !== null && expiresAt < now;
                  const expiresSoon = expiresAt !== null && !isExpired && expiresAt - now < 5 * 24 * 60 * 60 * 1000;
                  const expiryLabel = isExpired
                    ? <span className="ml-1 px-1 py-0.5 rounded text-[10px] border border-red-700 bg-red-900/40 text-red-300">Expired</span>
                    : expiresSoon
                    ? <span className="ml-1 px-1 py-0.5 rounded text-[10px] border border-amber-700 bg-amber-900/40 text-amber-300">Expires soon</span>
                    : expiresAt
                    ? <span className="ml-1 text-muted-foreground">· expires {new Date(expiresAt).toLocaleDateString()}</span>
                    : null;

                  return (
                    <div key={k.id} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                      <div className="min-w-0">
                        <div className="font-medium text-foreground truncate">{k.name}</div>
                        <div className="font-mono text-muted-foreground flex items-center flex-wrap gap-x-1">
                          {k.key_prefix}… · {k.revoked_at ? "revoked" : "active"}
                          {expiryLabel}
                        </div>
                      </div>
                      {!k.revoked_at && (
                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            className="text-amber-400 hover:underline"
                            onClick={async () => {
                              if (!confirm(`Rotate key "${k.name}"? The old key will stop working immediately.`)) return;
                              try {
                                const res = await api.rotateTenantApiKey(k.id);
                                setJustCreatedKey(res.key);
                                await loadIngestKeys();
                              } catch (e) {
                                alert(e instanceof Error ? e.message : "Rotate failed");
                              }
                            }}
                          >
                            Rotate
                          </button>
                          <button
                            type="button"
                            className="text-red-400 hover:underline"
                            onClick={async () => {
                              if (!confirm(`Revoke key "${k.name}"?`)) return;
                              try {
                                await api.revokeTenantApiKey(k.id);
                                await loadIngestKeys();
                              } catch (e) {
                                alert(e instanceof Error ? e.message : "Revoke failed");
                              }
                            }}
                          >
                            Revoke
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      )}

      {/* ── Members tab ─────────────────────────────────────────────────── */}
      {tab === "members" && (
        <div className="space-y-4">
          <Card title="Tenant members">
            <p className="text-xs text-muted-foreground mb-3">
              List and invite users by OIDC <span className="font-mono">sub</span>. Tenant admins and platform admins
              can add or remove members. Members can view this list.
            </p>
            <div className="grid gap-2 sm:grid-cols-3 mb-3">
              <Field label="Subject (sub)">
                <Input
                  value={newMemberSubject}
                  onChange={(e) => setNewMemberSubject(e.target.value)}
                  placeholder="oidc-subject"
                  className="font-mono text-sm bg-card border-border"
                />
              </Field>
              <Field label="Email (optional)">
                <Input
                  value={newMemberEmail}
                  onChange={(e) => setNewMemberEmail(e.target.value)}
                  className="text-sm bg-card border-border"
                />
              </Field>
              <Field label="Role">
                <select
                  value={newMemberRole}
                  onChange={(e) => setNewMemberRole(e.target.value as "tenant_admin" | "tenant_member")}
                  className="w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
                >
                  <option value="tenant_member">tenant_member</option>
                  <option value="tenant_admin">tenant_admin</option>
                </select>
              </Field>
            </div>
            <button
              type="button"
              disabled={membersLoading || !newMemberSubject.trim()}
              onClick={async () => {
                try {
                  await api.addTenantMember({
                    subject: newMemberSubject.trim(),
                    email: newMemberEmail.trim() || undefined,
                    role: newMemberRole,
                  });
                  setNewMemberSubject("");
                  setNewMemberEmail("");
                  await loadMembers();
                } catch (e) {
                  alert(e instanceof Error ? e.message : "Add failed");
                }
              }}
              className="px-3 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold disabled:opacity-40"
            >
              Add member
            </button>

            <div className="mt-4 rounded-md border border-border divide-y divide-border/50">
              {membersLoading ? (
                <div className="px-3 py-2 text-xs text-muted-foreground">Loading…</div>
              ) : members.length === 0 ? (
                <div className="px-3 py-2 text-xs text-muted-foreground">No members.</div>
              ) : (
                members.map((m) => (
                  <div key={m.membership_id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-xs">
                    <div className="flex-1 min-w-[200px]">
                      <div className="font-mono text-foreground">{m.subject}</div>
                      <div className="text-muted-foreground">{m.email || "—"}</div>
                    </div>
                    <select
                      value={m.role}
                      onChange={async (e) => {
                        try {
                          await api.patchTenantMember(m.membership_id, { role: e.target.value });
                          await loadMembers();
                        } catch (err) {
                          alert(err instanceof Error ? err.message : "Update failed");
                        }
                      }}
                      className="rounded border border-border bg-background px-2 py-1"
                    >
                      <option value="tenant_member">tenant_member</option>
                      <option value="tenant_admin">tenant_admin</option>
                    </select>
                    <button
                      type="button"
                      className="text-red-400 hover:underline"
                      onClick={async () => {
                        if (!confirm(`Remove ${m.subject}?`)) return;
                        try {
                          await api.removeTenantMember(m.membership_id);
                          await loadMembers();
                        } catch (err) {
                          alert(err instanceof Error ? err.message : "Remove failed");
                        }
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      )}

      {/* ── Advanced tab ─────────────────────────────────────────────────── */}
      {tab === "advanced" && (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Raw key-value editor for <span className="font-mono text-foreground">{envFile}</span>.{" "}
            Alert and schedule keys are managed in their respective tabs.
          </p>
          <div className="space-y-2">
            {Object.entries(values)
              .filter(([key]) => !ALERT_KEYS.has(key))
              .map(([key, value]) => (
                <div key={key} className="grid grid-cols-[240px_1fr] gap-3 items-center">
                  <label className="text-xs font-mono text-muted-foreground truncate">{key}</label>
                  <Input
                    value={dirty[key] ?? value}
                    onChange={(e) => onChange(key, e.target.value)}
                    className={`font-mono text-sm bg-card border-border ${dirty[key] !== undefined ? "border-cyan-400" : ""}`}
                  />
                </div>
              ))}
          </div>
        </div>
      )}

      {/* ── Save bar ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 pt-2 border-t border-border">
        <button
          onClick={save}
          disabled={saving || dirtyCount === 0}
          className="px-4 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
        {saved && <span className="text-sm text-emerald-400">✓ Saved</span>}
      </div>
    </div>
  );
}
