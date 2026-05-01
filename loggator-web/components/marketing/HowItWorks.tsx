const steps = [
  {
    step: "01",
    title: "Ingest",
    body: "Ship logs via API keys or pipelines into OpenSearch; isolate by tenant and index pattern.",
  },
  {
    step: "02",
    title: "Analyze",
    body: "Streaming and scheduled jobs chunk logs through LLM chains—anomalies, summaries, and RCA.",
  },
  {
    step: "03",
    title: "Respond",
    body: "WebSocket feeds, dashboards, and alerts notify your team; audit trails capture who did what.",
  },
];

export function HowItWorks() {
  return (
    <section className="px-4 py-20 border-t border-border/60">
      <div className="max-w-6xl mx-auto">
        <p className="text-[10px] font-mono uppercase tracking-widest text-violet-300/90 mb-2">Pipeline</p>
        <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-12">How it works</h2>
        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((s, i) => (
            <div key={s.step} className="relative">
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-8 left-[calc(100%+1rem)] w-[calc(100%-2rem)] h-px bg-gradient-to-r from-primary/40 to-transparent -translate-y-1/2" />
              )}
              <div className="font-mono text-4xl font-bold text-primary/20 mb-3">{s.step}</div>
              <h3 className="text-lg font-semibold text-foreground mb-2">{s.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
