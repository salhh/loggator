interface StatCardProps {
  label: string;
  value: string | number;
  borderColor: string;
}

export default function StatCard({ label, value, borderColor }: StatCardProps) {
  return (
    <div className={`bg-card rounded-lg border border-border border-l-4 ${borderColor} p-4`}>
      <div className="text-2xl font-bold text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}
