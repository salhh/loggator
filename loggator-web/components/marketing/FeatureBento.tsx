import { Activity, Bell, Bot, Database, KeyRound, Lock, Radar, Users } from "lucide-react";

const features = [
  {
    icon: Radar,
    title: "AI anomaly detection",
    tags: ["MITRE ATT&CK", "OWASP"],
    desc: "Security-enriched prompts map findings to tactics and severity—structured JSON for automation.",
    className: "md:col-span-2",
  },
  {
    icon: Activity,
    title: "Live + scheduled pipelines",
    tags: ["Streaming", "RCA"],
    desc: "Continuous ingestion, batch summaries, and root-cause reports on your log windows.",
    className: "",
  },
  {
    icon: Bot,
    title: "RAG chat on logs",
    tags: ["Context", "Ollama / cloud LLM"],
    desc: "Ask questions grounded in indexed log context and your stack.",
    className: "",
  },
  {
    icon: Database,
    title: "OpenSearch backbone",
    tags: ["Indices", "Patterns"],
    desc: "Tenant-scoped index patterns and encrypted connection secrets at rest.",
    className: "md:col-span-2",
  },
  {
    icon: Users,
    title: "Multi-tenant RBAC",
    tags: ["Members", "Roles"],
    desc: "Tenant admins, memberships, and platform operators with scoped APIs.",
    className: "",
  },
  {
    icon: KeyRound,
    title: "Ingest API keys",
    tags: ["Hashing", "Revocation"],
    desc: "Issue and revoke keys per tenant for high-volume log ingest.",
    className: "",
  },
  {
    icon: Bell,
    title: "Alerts",
    tags: ["Slack", "Email", "Webhooks"],
    desc: "Route high-severity anomalies to your channels with cooldown controls.",
    className: "",
  },
  {
    icon: Lock,
    title: "Audit & platform admin",
    tags: ["Audit log", "Billing hooks"],
    desc: "Platform views for tenants, billing plans, and observability trails.",
    className: "md:col-span-2",
  },
];

export function FeatureBento() {
  return (
    <section id="features" className="px-4 py-20 max-w-6xl mx-auto scroll-mt-20">
      <div className="mb-12 max-w-2xl">
        <p className="text-[10px] font-mono uppercase tracking-widest text-cyan-400/90 mb-2">Capabilities</p>
        <h2 className="text-3xl md:text-4xl font-bold text-foreground">Built for defenders</h2>
        <p className="mt-3 text-muted-foreground">
          Everything you need to turn raw logs into actionable security signal—without bolting on five tools.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {features.map((f) => {
          const Icon = f.icon;
          return (
            <div
              key={f.title}
              className={`group rounded-xl border border-cyan-400/15 bg-card/40 backdrop-blur-md p-5 hover:border-cyan-400/35 hover:shadow-[0_0_32px_-12px_rgba(34,211,238,0.25)] transition-all duration-300 ${f.className}`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-2 text-cyan-300">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="flex flex-wrap gap-1 justify-end">
                  {f.tags.map((t) => (
                    <span
                      key={t}
                      className="text-[9px] font-mono uppercase tracking-wide px-2 py-0.5 rounded border border-border text-muted-foreground"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
              <h3 className="text-base font-semibold text-foreground mb-2">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
