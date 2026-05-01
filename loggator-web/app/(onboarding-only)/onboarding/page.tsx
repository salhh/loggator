"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type AuthMeResponse } from "@/lib/api";
import {
  getOnboardingStep,
  setOnboardingComplete,
  setOnboardingStep,
} from "@/lib/onboarding-storage";

const STEPS = [
  { title: "Welcome", body: "Loggator helps you search logs, detect anomalies, and collaborate with your MSP." },
  { title: "Organization", body: "Your active tenant scopes all data. Switch tenants from the top bar when you have access to more than one." },
  { title: "Log sources", body: "Connect OpenSearch, Elasticsearch, or a Wazuh indexer under Settings → Integrations." },
  { title: "Invite your team", body: "Add colleagues from Team → Members with appropriate roles." },
  { title: "You are set", body: "Open the dashboard to start exploring. You can revisit integrations anytime." },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { data: session } = useSession();
  const { tenants, tenantId } = useAuth();
  const [me, setMe] = useState<AuthMeResponse | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    void api.authMe().then((m) => {
      setMe(m);
      const sub = m.user_id || session?.user?.email || "";
      if (sub) setStep(getOnboardingStep(sub));
    });
  }, [session?.user?.email]);

  const sub = me?.user_id || session?.user?.email || "";
  const tenantLabel =
    tenants.find((t) => t.id === tenantId)?.name ||
    (tenants.length === 1 ? tenants[0].name : null) ||
    "your organization";

  function persistStep(n: number) {
    setStep(n);
    if (sub) setOnboardingStep(sub, n);
  }

  function finish() {
    if (sub) setOnboardingComplete(sub);
    router.replace("/dashboard");
  }

  function skip() {
    if (sub) setOnboardingComplete(sub);
    router.replace("/dashboard");
  }

  const isLast = step >= STEPS.length - 1;
  const s = STEPS[step] ?? STEPS[0];

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex items-center justify-end gap-2 px-4 py-3 border-b border-border">
        <ThemeToggle />
        <Button type="button" variant="ghost" size="sm" onClick={skip}>
          Skip for now
        </Button>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
        <Card className="w-full max-w-lg p-8 space-y-6 shadow-lg">
          <div className="flex gap-1">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full ${i <= step ? "bg-primary" : "bg-muted"}`}
              />
            ))}
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Step {step + 1} of {STEPS.length}
            </p>
            <h1 className="text-xl font-semibold mt-1">{s.title}</h1>
            <p className="text-sm text-muted-foreground mt-2">{s.body}</p>
            {step === 1 ? (
              <p className="text-sm mt-3 rounded-md border border-border bg-muted/40 px-3 py-2">
                Current workspace: <span className="font-medium text-foreground">{tenantLabel}</span>
              </p>
            ) : null}
            {step === 2 ? (
              <Link
                href="/settings/integrations"
                className="inline-block mt-3 text-sm font-medium text-primary hover:underline"
              >
                Open integrations
              </Link>
            ) : null}
            {step === 3 ? (
              <Link
                href="/team"
                className="inline-block mt-3 text-sm font-medium text-primary hover:underline"
              >
                Open team management
              </Link>
            ) : null}
          </div>
          <div className="flex justify-between gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={step === 0}
              onClick={() => persistStep(Math.max(0, step - 1))}
            >
              Back
            </Button>
            {isLast ? (
              <Button type="button" onClick={finish}>
                Go to dashboard
              </Button>
            ) : (
              <Button type="button" onClick={() => persistStep(step + 1)}>
                Continue
              </Button>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
