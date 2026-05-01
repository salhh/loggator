"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type TenantRow } from "@/lib/api";
import { Input } from "@/components/ui/input";

export default function PlatformTenantsPage() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [adminSubject, setAdminSubject] = useState("");
  const [adminEmail, setAdminEmail] = useState("");

  const refresh = useCallback(async () => {
    setError("");
    try {
      setTenants(await api.platformTenants());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tenants");
      setTenants([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Platform — tenants</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Requires a JWT with <code className="text-xs">platform_admin</code>. Use the sidebar access token.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
      )}

      <section className="rounded-lg border border-border bg-card p-4 space-y-3">
        <h2 className="text-sm font-medium text-foreground">Create tenant</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-muted-foreground">
            Name
            <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 bg-background" />
          </label>
          <label className="text-xs text-muted-foreground">
            Slug
            <Input value={slug} onChange={(e) => setSlug(e.target.value)} className="mt-1 bg-background font-mono text-sm" />
          </label>
          <label className="text-xs text-muted-foreground">
            Admin OIDC subject (optional)
            <Input
              value={adminSubject}
              onChange={(e) => setAdminSubject(e.target.value)}
              className="mt-1 bg-background font-mono text-sm"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Admin email (optional)
            <Input value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} className="mt-1 bg-background" />
          </label>
        </div>
        <button
          type="button"
          disabled={!name.trim() || !slug.trim()}
          onClick={async () => {
            try {
              await api.platformCreateTenant({
                name: name.trim(),
                slug: slug.trim(),
                admin_subject: adminSubject.trim() || null,
                admin_email: adminEmail.trim() || null,
              });
              setName("");
              setSlug("");
              setAdminSubject("");
              setAdminEmail("");
              await refresh();
            } catch (e) {
              alert(e instanceof Error ? e.message : "Create failed");
            }
          }}
          className="px-3 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold disabled:opacity-40"
        >
          Create
        </button>
      </section>

      <section className="rounded-lg border border-border bg-card overflow-hidden">
        <h2 className="text-sm font-medium text-foreground p-4 border-b border-border">All tenants</h2>
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground">Loading…</p>
        ) : tenants.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">No tenants.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="p-3 font-medium">Name</th>
                <th className="p-3 font-medium">Slug</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium w-[140px]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} className="border-b border-border/60">
                  <td className="p-3">{t.name}</td>
                  <td className="p-3 font-mono text-xs">{t.slug}</td>
                  <td className="p-3">{t.status}</td>
                  <td className="p-3">
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
