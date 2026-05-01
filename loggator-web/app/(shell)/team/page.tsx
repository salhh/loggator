"use client";

import TenantMembersPanel from "@/components/platform/TenantMembersPanel";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ROLES = [
  { role: "tenant_admin", desc: "Manage members, keys, and tenant settings." },
  { role: "tenant_member", desc: "View logs, anomalies, and dashboards." },
];

export default function TeamPage() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Team</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage people and roles for the active tenant. Requires tenant admin, MSP, or platform
          access.
        </p>
      </div>

      <Tabs defaultValue="members" className="gap-4">
        <TabsList variant="line" className="w-full justify-start">
          <TabsTrigger value="members">Members</TabsTrigger>
          <TabsTrigger value="invitations">Invitations</TabsTrigger>
          <TabsTrigger value="roles">Roles</TabsTrigger>
        </TabsList>
        <TabsContent value="members">
          <TenantMembersPanel />
        </TabsContent>
        <TabsContent value="invitations">
          <Card className="p-6 text-sm text-muted-foreground">
            Invitations and SSO directory sync will appear here in a future release.
          </Card>
        </TabsContent>
        <TabsContent value="roles">
          <Card className="p-6 space-y-4">
            <p className="text-sm text-muted-foreground">
              Role capabilities for this tenant (read-only).
            </p>
            <ul className="space-y-3">
              {ROLES.map((r) => (
                <li key={r.role} className="rounded-md border border-border p-3">
                  <p className="text-sm font-medium font-mono">{r.role}</p>
                  <p className="text-xs text-muted-foreground mt-1">{r.desc}</p>
                </li>
              ))}
            </ul>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
