"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type TenantRow } from "@/lib/api";
import { Input } from "@/components/ui/input";

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
        status === "active"
          ? "bg-green-950/40 text-green-300"
          : "bg-red-950/40 text-red-300"
      }`}
    >
      {status}
    </span>
  );
}

function CreateTenantDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [adminSubject, setAdminSubject] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    try {
      await api.platformCreateTenant({
        name: name.trim(),
        slug: slug.trim(),
        admin_subject: adminSubject.trim() || null,
        admin_email: adminEmail.trim() || null,
      });
      setName(""); setSlug(""); setAdminSubject(""); setAdminEmail("");
      setOpen(false);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-3 py-2 rounded-md bg-amber-400 text-black text-sm font-semibold hover:bg-amber-300 transition-colors"
      >
        + New Tenant
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="rounded-lg border border-border bg-card p-6 w-full max-w-md space-y-4 shadow-xl">
        <h2 className="text-sm font-semibold text-foreground">Create Tenant</h2>
        {error && (
          <div className="rounded border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-muted-foreground col-span-2 sm:col-span-1">
            Name
            <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 bg-background" />
          </label>
          <label className="text-xs text-muted-foreground col-span-2 sm:col-span-1">
            Slug
            <Input value={slug} onChange={(e) => setSlug(e.target.value)} className="mt-1 bg-background font-mono text-sm" />
          </label>
          <label className="text-xs text-muted-foreground col-span-2 sm:col-span-1">
            Admin OIDC subject (optional)
            <Input value={adminSubject} onChange={(e) => setAdminSubject(e.target.value)} className="mt-1 bg-background font-mono text-sm" />
          </label>
          <label className="text-xs text-muted-foreground col-span-2 sm:col-span-1">
            Admin email (optional)
            <Input value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} className="mt-1 bg-background" />
          </label>
        </div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => setOpen(false)}
            className="px-3 py-1.5 rounded border border-border text-sm text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          <button
            disabled={!name.trim() || !slug.trim()}
            onClick={submit}
            className="px-3 py-1.5 rounded bg-amber-400 text-black text-sm font-semibold disabled:opacity-40 hover:bg-amber-300 transition-colors"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PlatformTenantsPage() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refresh = useCallback(async () => {
    setError("");
    try {
      setTenants(await api.platformTenants());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tenants");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Tenants</h1>
          <p className="text-sm text-muted-foreground mt-0.5">All platform tenants — click a row for details.</p>
        </div>
        <CreateTenantDialog onCreated={refresh} />
      </div>

      {error && (
        <div className="rounded border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
      )}

      <section className="rounded-lg border border-border bg-card overflow-hidden">
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground animate-pulse">Loading…</p>
        ) : tenants.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">No tenants yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="p-3 font-medium">Name</th>
                <th className="p-3 font-medium">Slug</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium text-right">Members</th>
                <th className="p-3 font-medium">Created</th>
                <th className="p-3 font-medium w-[130px]">Change Status</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-border/60 hover:bg-secondary/40 cursor-pointer transition-colors"
                  onClick={() => router.push(`/platform/tenants/${t.id}`)}
                >
                  <td className="p-3 font-medium">{t.name}</td>
                  <td className="p-3 font-mono text-xs text-muted-foreground">{t.slug}</td>
                  <td className="p-3"><StatusBadge status={t.status} /></td>
                  <td className="p-3 text-right text-muted-foreground">{t.member_count ?? 0}</td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                  <td className="p-3" onClick={(e) => e.stopPropagation()}>
                    <select
                      value={t.status}
                      onChange={async (e) => {
                        try {
                          await api.platformPatchTenant(t.id, { status: e.target.value });
                          await refresh();
                        } catch (err) {
                          alert(err instanceof Error ? err.message : "Update failed");
                        }
                      }}
                      className="rounded border border-border bg-background px-2 py-1 text-xs"
                    >
                      <option value="active">active</option>
                      <option value="suspended">suspended</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
