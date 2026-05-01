const stats = [
  { label: "Analysis", value: "Streaming + batch", hint: "Near-real-time and scheduled windows" },
  { label: "Tenancy", value: "Isolated", hint: "Per-tenant data and RBAC" },
  { label: "Signals", value: "MITRE-aligned", hint: "Structured anomaly output" },
  { label: "Integrations", value: "OpenSearch-native", hint: "Ingest, WebSockets, API keys" },
];

export function MarketingStats() {
  return (
    <section className="px-4 py-12 border-y border-border/60 bg-card/30 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-8">
        {stats.map((s) => (
          <div key={s.label} className="space-y-1">
            <p className="text-[10px] font-mono uppercase tracking-widest text-primary/80">{s.label}</p>
            <p className="text-lg font-semibold text-foreground">{s.value}</p>
            <p className="text-xs text-muted-foreground leading-snug">{s.hint}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
