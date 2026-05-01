"use client";

import { useCallback, useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

type Member = {
  membership_id: string;
  user_id: string;
  subject: string;
  email: string;
  role: string;
  created_at: string;
};

interface Props {
  tenantId?: string;
}

export default function TenantMembersPanel({ tenantId }: Props) {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [newSubject, setNewSubject] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<"tenant_admin" | "tenant_member">("tenant_member");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setMembers(await api.tenantMembers(tenantId));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { void load(); }, [load]);

  const addMember = async () => {
    try {
      await api.addTenantMember(
        { subject: newSubject.trim(), email: newEmail.trim() || undefined, role: newRole },
        tenantId,
      );
      setNewSubject(""); setNewEmail("");
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Add failed");
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Add or remove users by OIDC <span className="font-mono">sub</span>. Tenant admins and platform admins can manage membership.
      </p>

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Subject (sub)</label>
          <Input
            value={newSubject}
            onChange={(e) => setNewSubject(e.target.value)}
            placeholder="oidc-subject"
            className="font-mono text-sm bg-card border-border"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Email (optional)</label>
          <Input
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            className="text-sm bg-card border-border"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Role</label>
          <select
            value={newRole}
            onChange={(e) => setNewRole(e.target.value as "tenant_admin" | "tenant_member")}
            className="w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
          >
            <option value="tenant_member">tenant_member</option>
            <option value="tenant_admin">tenant_admin</option>
          </select>
        </div>
      </div>
      <button
        type="button"
        disabled={loading || !newSubject.trim()}
        onClick={addMember}
        className="px-3 py-2 rounded-md bg-amber-400 text-black text-sm font-semibold disabled:opacity-40 hover:bg-amber-300 transition-colors"
      >
        Add member
      </button>

      <div className="rounded-md border border-border divide-y divide-border/50">
        {loading ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">Loading…</div>
        ) : members.length === 0 ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">No members yet.</div>
        ) : (
          members.map((m) => (
            <div key={m.membership_id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-xs">
              <div className="flex-1 min-w-[200px]">
                <div className="font-mono text-foreground">{m.subject}</div>
                <div className="text-muted-foreground">{m.email || "—"}</div>
              </div>
              <select
                value={m.role}
                onChange={async (e) => {
                  try {
                    await api.patchTenantMember(m.membership_id, { role: e.target.value }, tenantId);
                    await load();
                  } catch (err) {
                    alert(err instanceof Error ? err.message : "Update failed");
                  }
                }}
                className="rounded border border-border bg-background px-2 py-1"
              >
                <option value="tenant_member">tenant_member</option>
                <option value="tenant_admin">tenant_admin</option>
              </select>
              <button
                type="button"
                className="text-red-400 hover:underline"
                onClick={async () => {
                  if (!confirm(`Remove ${m.subject}?`)) return;
                  try {
                    await api.removeTenantMember(m.membership_id, tenantId);
                    await load();
                  } catch (err) {
                    alert(err instanceof Error ? err.message : "Remove failed");
                  }
                }}
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
