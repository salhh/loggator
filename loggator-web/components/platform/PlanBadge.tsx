import type { BillingPlan } from "@/lib/types";

interface Props {
  plan: BillingPlan | null | undefined;
}

export default function PlanBadge({ plan }: Props) {
  if (!plan) {
    return <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-secondary text-muted-foreground">Unassigned</span>;
  }
  const colors: Record<string, string> = {
    free: "bg-secondary text-muted-foreground",
    pro: "bg-blue-950/40 text-blue-300",
    enterprise: "bg-amber-950/40 text-amber-300",
  };
  const cls = colors[plan.slug] ?? "bg-secondary text-foreground";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${cls}`}>{plan.name}</span>
  );
}
