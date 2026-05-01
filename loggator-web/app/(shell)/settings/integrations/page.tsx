"use client";

import { useAuth } from "@/components/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { TenantIntegration } from "@/lib/types";
import { useCallback, useEffect, useState } from "react";

const PROVIDERS = [
  { id: "opensearch", label: "OpenSearch" },
  { id: "elasticsearch", label: "Elasticsearch" },
  { id: "wazuh_indexer", label: "Wazuh Indexer (OpenSearch-compatible)" },
  { id: "wazuh_api", label: "Wazuh manager API" },
] as const;

type ProviderId = (typeof PROVIDERS)[number]["id"];

export default function IntegrationsSettingsPage() {
  const { tenantId, authStatus } = useAuth();
  const [rows, setRows] = useState<TenantIntegration[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [testMsg, setTestMsg] = useState<Record<string, string>>({});

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [provider, setProvider] = useState<ProviderId>("opensearch");
  const [isPrimary, setIsPrimary] = useState(false);
  const [host, setHost] = useState("");
  const [port, setPort] = useState("");
  const [authType, setAuthType] = useState("none");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [useSsl, setUseSsl] = useState(true);
  const [verifyCerts, setVerifyCerts] = useState(false);
  const [indexPattern, setIndexPattern] = useState("");
  const [awsRegion, setAwsRegion] = useState("");
  const [wazuhBaseUrl, setWazuhBaseUrl] = useState("https://wazuh.example:55000");

  const xt = tenantId ?? undefined;

  const refresh = useCallback(async () => {
    if (!xt) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const list = await api.listTenantIntegrations(xt);
      setRows(list);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  }, [xt]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!xt) return;
    setErr(null);
    setBusyId("__create__");
    try {
      const body =
        provider === "wazuh_api"
          ? {
              name: name.trim(),
              provider,
              is_primary: isPrimary,
              extra_config: { base_url: wazuhBaseUrl.trim() },
            }
          : {
              name: name.trim(),
              provider,
              is_primary: isPrimary,
              opensearch_host: host.trim() || null,
              opensearch_port: port ? parseInt(port, 10) : null,
              opensearch_auth_type: authType,
              opensearch_username: username.trim() || null,
              opensearch_password: password || null,
              opensearch_api_key: apiKey || null,
              opensearch_use_ssl: useSsl,
              opensearch_verify_certs: verifyCerts,
              opensearch_index_pattern: indexPattern.trim() || null,
              aws_region: awsRegion.trim() || null,
            };
      await api.createTenantIntegration(body, xt);
      setShowForm(false);
      setName("");
      setIsPrimary(false);
      setHost("");
      setPort("");
      setPassword("");
      setApiKey("");
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Create failed");
    } finally {
      setBusyId(null);
    }
  }

  async function setPrimary(id: string) {
    if (!xt) return;
    setBusyId(id);
    setErr(null);
    try {
      await api.patchTenantIntegration(id, { is_primary: true }, xt);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(id: string) {
    if (!xt || !confirm("Delete this integration? Log search will fall back if another is configured.")) return;
    setBusyId(id);
    setErr(null);
    try {
      await api.deleteTenantIntegration(id, xt);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  async function test(id: string) {
    if (!xt) return;
    setBusyId(id);
    setErr(null);
    setTestMsg((m) => ({ ...m, [id]: "" }));
    try {
      const r = await api.testTenantIntegration(id, xt);
      setTestMsg((m) => ({
        ...m,
        [id]: r.ok === false ? JSON.stringify(r) : `OK — ${JSON.stringify(r)}`,
      }));
    } catch (e) {
      setTestMsg((m) => ({ ...m, [id]: e instanceof Error ? e.message : "Test failed" }));
    } finally {
      setBusyId(null);
    }
  }

  if (authStatus !== "authenticated") {
    return (
      <div className="text-sm text-muted-foreground">
        Sign in to manage integrations.
      </div>
    );
  }

  if (!tenantId) {
    return (
      <div className="space-y-2 max-w-xl">
        <h1 className="text-xl font-semibold text-foreground">Integrations</h1>
        <p className="text-sm text-muted-foreground">
          Select a tenant in the header to configure log backends and SIEM connections.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Integrations</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Connect OpenSearch, Elasticsearch, Wazuh Indexer, or the Wazuh manager API. The{" "}
          <strong className="font-medium text-foreground">primary</strong> search integration drives log views and
          analysis.
        </p>
      </div>

      {err ? (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {err}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button type="button" variant={showForm ? "secondary" : "default"} onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "Add integration"}
        </Button>
      </div>

      {showForm ? (
        <Card className="p-4 space-y-4">
          <h2 className="text-sm font-medium text-foreground">New integration</h2>
          <form onSubmit={onCreate} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Production cluster" required />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as ProviderId)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={isPrimary} onChange={(e) => setIsPrimary(e.target.checked)} />
              Set as primary (used for log search and summaries)
            </label>

            {provider === "wazuh_api" ? (
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Base URL</label>
                <Input
                  value={wazuhBaseUrl}
                  onChange={(e) => setWazuhBaseUrl(e.target.value)}
                  placeholder="https://wazuh-manager:55000"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  Reachability check only; agents and rules UI will expand in a later release.
                </p>
              </div>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">Host</label>
                    <Input value={host} onChange={(e) => setHost(e.target.value)} placeholder="search.example.com" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">Port</label>
                    <Input value={port} onChange={(e) => setPort(e.target.value)} placeholder="9200" />
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">Auth type</label>
                    <select
                      value={authType}
                      onChange={(e) => setAuthType(e.target.value)}
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                    >
                      {["none", "basic", "api_key", "aws_iam"].map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">Index pattern</label>
                    <Input
                      value={indexPattern}
                      onChange={(e) => setIndexPattern(e.target.value)}
                      placeholder="logs-*"
                    />
                  </div>
                </div>
                {(authType === "basic" || authType === "api_key") && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {authType === "basic" ? (
                      <>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-muted-foreground">Username</label>
                          <Input value={username} onChange={(e) => setUsername(e.target.value)} />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-muted-foreground">Password</label>
                          <Input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            autoComplete="new-password"
                          />
                        </div>
                      </>
                    ) : (
                      <div className="space-y-1 sm:col-span-2">
                        <label className="text-xs font-medium text-muted-foreground">API key</label>
                        <Textarea value={apiKey} onChange={(e) => setApiKey(e.target.value)} rows={2} />
                      </div>
                    )}
                  </div>
                )}
                {authType === "aws_iam" && (
                  <div className="space-y-1 max-w-sm">
                    <label className="text-xs font-medium text-muted-foreground">AWS region</label>
                    <Input value={awsRegion} onChange={(e) => setAwsRegion(e.target.value)} placeholder="us-east-1" />
                  </div>
                )}
                <div className="flex flex-wrap gap-4 text-sm">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={useSsl} onChange={(e) => setUseSsl(e.target.checked)} />
                    Use TLS
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={verifyCerts} onChange={(e) => setVerifyCerts(e.target.checked)} />
                    Verify certificates
                  </label>
                </div>
              </>
            )}

            <Button type="submit" disabled={busyId === "__create__" || !name.trim()}>
              {busyId === "__create__" ? "Saving…" : "Create"}
            </Button>
          </form>
        </Card>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <Card className="p-6 text-sm text-muted-foreground">No integrations yet. Add one to connect your log cluster.</Card>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.id}>
              <Card className="p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-foreground">{r.name}</span>
                      {r.is_primary ? (
                        <Badge variant="default" className="text-xs">
                          Primary
                        </Badge>
                      ) : null}
                      <Badge variant="outline" className="text-xs capitalize">
                        {r.provider.replace(/_/g, " ")}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 font-mono break-all">
                      {r.provider === "wazuh_api"
                        ? String((r.extra_config as { base_url?: string } | null)?.base_url ?? "—")
                        : r.opensearch_host ?? "—"}
                      {r.opensearch_index_pattern ? ` · pattern: ${r.opensearch_index_pattern}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!r.is_primary ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busyId === r.id}
                        onClick={() => void setPrimary(r.id)}
                      >
                        Set primary
                      </Button>
                    ) : null}
                    <Button type="button" variant="outline" size="sm" disabled={busyId === r.id} onClick={() => void test(r.id)}>
                      Test
                    </Button>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={busyId === r.id}
                      onClick={() => void remove(r.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
                {testMsg[r.id] ? (
                  <p className="text-xs text-muted-foreground whitespace-pre-wrap border-t border-border pt-2">
                    {testMsg[r.id]}
                  </p>
                ) : null}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
