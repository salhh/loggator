import Link from "next/link";

const tiers = [
  {
    name: "Starter",
    price: "$99",
    period: "/mo",
    blurb: "Small teams getting serious about log intelligence.",
    features: ["1 tenant · up to 5 members", "Daily batch + streaming (fair use)", "Email alerts", "Community support"],
    cta: "Sign in",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$399",
    period: "/mo",
    blurb: "SOC workflows, higher volume, SSO-ready deployments.",
    features: [
      "Multiple tenants",
      "Higher ingest & API limits",
      "Slack / webhooks",
      "Priority support",
      "Audit log retention",
    ],
    cta: "Sign in",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    blurb: "Dedicated capacity, custom contracts, and deployment options.",
    features: ["Custom SLAs", "VPC / private networking", "Fine-grained controls", "Solutions engineer"],
    cta: "Contact sales",
    highlighted: false,
    sales: true,
  },
];

export function PricingTable() {
  return (
    <section id="pricing" className="px-4 py-20 scroll-mt-20">
      <div className="max-w-6xl mx-auto">
        <p className="text-[10px] font-mono uppercase tracking-widest text-cyan-400/90 mb-2">Pricing</p>
        <h2 className="text-3xl md:text-4xl font-bold text-foreground">Plans that scale with risk</h2>
        <p className="mt-3 text-sm text-muted-foreground max-w-2xl">
          Illustrative tiers for marketing. Actual limits and billing are configured per deployment (e.g. platform
          billing plans in your environment).
        </p>
        <div className="mt-12 grid md:grid-cols-3 gap-6">
          {tiers.map((t) => (
            <div
              key={t.name}
              className={`rounded-xl border p-6 flex flex-col ${
                t.highlighted
                  ? "border-cyan-400/50 bg-cyan-400/5 shadow-[0_0_40px_-16px_rgba(34,211,238,0.35)] scale-[1.02]"
                  : "border-border/80 bg-card/30 backdrop-blur-sm"
              }`}
            >
              <h3 className="text-lg font-semibold text-foreground">{t.name}</h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-3xl font-bold text-foreground">{t.price}</span>
                <span className="text-sm text-muted-foreground">{t.period}</span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{t.blurb}</p>
              <ul className="mt-6 space-y-2 flex-1">
                {t.features.map((f) => (
                  <li key={f} className="text-sm text-foreground/90 flex gap-2">
                    <span className="text-cyan-400 shrink-0">▹</span>
                    {f}
                  </li>
                ))}
              </ul>
              <div className="mt-8">
                {t.sales ? (
                  <a
                    href="mailto:sales@example.com"
                    className="block w-full text-center rounded-lg border border-cyan-400/40 py-2.5 text-sm font-medium text-cyan-200 hover:bg-cyan-400/10"
                  >
                    {t.cta}
                  </a>
                ) : (
                  <Link
                    href="/login"
                    className={`block w-full text-center rounded-lg py-2.5 text-sm font-semibold ${
                      t.highlighted
                        ? "bg-cyan-400 text-black hover:bg-cyan-300"
                        : "border border-border bg-secondary/50 hover:bg-secondary"
                    }`}
                  >
                    {t.cta}
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
