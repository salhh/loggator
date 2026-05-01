import TenantMembersPanel from "@/components/platform/TenantMembersPanel";

export default function TenantMembersPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">Team Members</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Add or remove members from your tenant. Requires tenant admin or platform admin role.
        </p>
      </div>
      <TenantMembersPanel />
    </div>
  );
}
