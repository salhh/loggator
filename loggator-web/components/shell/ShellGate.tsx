"use client";

import type { ReactNode } from "react";
import { OnboardingRedirect } from "@/components/onboarding/OnboardingRedirect";

export function ShellGate({ children }: { children: ReactNode }) {
  return <OnboardingRedirect>{children}</OnboardingRedirect>;
}
