/** Minimal chrome for the onboarding wizard (no app sidebar). */
export default function OnboardingOnlyLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-background text-foreground">{children}</div>;
}
