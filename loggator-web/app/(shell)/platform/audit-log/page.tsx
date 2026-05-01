import PlatformAuditLogViewer from "@/components/platform/PlatformAuditLogViewer";

export default function PlatformAuditLogPage() {
  return (
    <div className="max-w-7xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Audit Log</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Cross-tenant request history — all actors, all tenants.</p>
      </div>
      <PlatformAuditLogViewer />
    </div>
  );
}
