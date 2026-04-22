interface StatCardProps {
  label: string;
  value: string | number;
  borderColor: string;
  sub?: string;
}

export default function StatCard({ label, value, borderColor, sub }: StatCardProps) {
  return (
    <div className={`bg-card rounded-lg border border-border border-l-2 ${borderColor} px-4 py-3 flex flex-col gap-1`}>
      <div className="text-xs text-muted-foreground uppercase tracking-wider font-medium">{label}</div>
      <div className="text-3xl font-bold text-foreground leading-none">{value}</div>
      {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}
