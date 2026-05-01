import Link from "next/link";
import { Shield, Zap } from "lucide-react";

export function MarketingHero() {
  return (
    <section className="relative px-4 pt-16 pb-20 md:pt-24 md:pb-28 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-[11px] font-mono uppercase tracking-wider text-primary">
          <Shield className="h-3.5 w-3.5" />
          SecOps-grade telemetry
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-400/25 bg-violet-500/5 px-3 py-1 text-[11px] font-mono uppercase tracking-wider text-violet-200/80">
          <Zap className="h-3.5 w-3.5" />
          AI-native analysis
        </span>
      </div>
      <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-foreground max-w-4xl leading-[1.1]">
        Detect threats in your logs
        <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-violet-500">
          {" "}
          before they spread
        </span>
      </h1>
      <p className="mt-6 text-lg md:text-xl text-muted-foreground max-w-2xl leading-relaxed">
        Loggator ingests OpenSearch streams, applies MITRE-aware AI models, and surfaces anomalies,
        RCA, and alerts—multi-tenant, audit-ready, built for security teams.
      </p>
      <div className="mt-10 flex flex-wrap gap-4">
        <Link
          href="/login"
          className="inline-flex items-center justify-center rounded-lg bg-primary text-primary-foreground px-8 py-3 text-sm font-semibold hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20"
        >
          Sign in
        </Link>
        <a
          href="#features"
          className="inline-flex items-center justify-center rounded-lg border border-primary/40 bg-primary/5 px-8 py-3 text-sm font-medium text-primary hover:bg-primary/10 transition-colors"
        >
          Explore capabilities
        </a>
      </div>
    </section>
  );
}
