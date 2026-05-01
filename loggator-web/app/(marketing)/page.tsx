import type { Metadata } from "next";
import { FeatureBento } from "@/components/marketing/FeatureBento";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { MarketingHero } from "@/components/marketing/MarketingHero";
import { MarketingStats } from "@/components/marketing/MarketingStats";
import { PricingTable } from "@/components/marketing/PricingTable";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Loggator — AI log security & operations",
  description:
    "Multi-tenant log intelligence: MITRE-aware anomaly detection, OpenSearch-native ingest, live feeds, alerts, and RBAC for security teams.",
};

export default function MarketingHomePage() {
  return (
    <>
      <header className="sticky top-0 z-20 border-b border-primary/15 bg-background/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link href="/" className="text-sm font-bold tracking-widest text-primary flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary inline-block" />
            LOGGATOR
          </Link>
          <div className="flex items-center gap-4">
            <a href="#pricing" className="text-xs text-muted-foreground hover:text-primary transition-colors">
              Pricing
            </a>
            <Link
              href="/login"
              className="text-xs font-semibold rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90"
            >
              Sign in
            </Link>
          </div>
        </div>
      </header>
      <main>
        <MarketingHero />
        <MarketingStats />
        <FeatureBento />
        <HowItWorks />
        <PricingTable />
      </main>
      <MarketingFooter />
    </>
  );
}
