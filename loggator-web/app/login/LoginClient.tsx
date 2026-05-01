"use client";

import { signIn, useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function LoginClient({
  showSso,
  showPassword,
  showToken,
}: {
  showSso: boolean;
  showPassword: boolean;
  showToken: boolean;
}) {
  const { status } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") || "/dashboard";
  const error = params.get("error");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status !== "authenticated") return;
    void (async () => {
      try {
        const me = await api.authMe();
        const roles = me.platform_roles ?? [];
        const operator = roles.includes("platform_admin") || roles.includes("msp_admin");
        const dest = operator && callbackUrl === "/dashboard" ? "/platform" : callbackUrl;
        router.replace(dest);
      } catch {
        router.replace(callbackUrl);
      }
    })();
  }, [status, router, callbackUrl]);

  if (status === "loading" || status === "authenticated") {
    return (
      <div className="min-h-[40vh] flex items-center justify-center text-sm text-muted-foreground">
        Redirecting…
      </div>
    );
  }

  const nothingConfigured = !showSso && !showPassword && !showToken;

  return (
    <div className="max-w-md mx-auto space-y-6 py-12 px-4">
      <div>
        <Link
          href="/"
          className="text-[11px] font-mono text-primary hover:text-primary/80 mb-3 inline-block"
        >
          ← Back to product
        </Link>
        <h1 className="text-xl font-semibold text-foreground">Log in</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Sign in with your email and password, organization SSO, or (optional) a development access token.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Sign-in error: {error}
        </div>
      )}

      {showPassword && (
        <form
          className="space-y-3 rounded-lg border border-border bg-card p-4"
          onSubmit={(e) => {
            e.preventDefault();
            setBusy(true);
            void signIn("password", { username, password, callbackUrl, redirect: true }).finally(() =>
              setBusy(false)
            );
          }}
        >
          <label className="block text-xs text-muted-foreground">Email or username</label>
          <input
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="you@company.com"
          />
          <label className="block text-xs text-muted-foreground">Password</label>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={busy || !username.trim() || !password}
            className="w-full rounded-md bg-primary text-primary-foreground py-2.5 text-sm font-semibold hover:bg-primary/90 disabled:opacity-50"
          >
            Continue
          </button>
          <p className="text-[11px] text-muted-foreground">
            The API signs you in and returns a session token (Bearer JWT). Use{" "}
            <code className="text-[10px]">DEV_JWT_SECRET</code> and bootstrap admin env vars for local stacks.
          </p>
        </form>
      )}

      {showSso && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void signIn("oidc", { callbackUrl });
          }}
          className="w-full rounded-md border border-border py-2.5 text-sm font-semibold hover:bg-secondary disabled:opacity-50"
        >
          Continue with SSO
        </button>
      )}

      {showToken && (
        <form
          className="space-y-3 rounded-lg border border-border bg-card p-4"
          onSubmit={(e) => {
            e.preventDefault();
            setBusy(true);
            void signIn("dev-token", { token, callbackUrl, redirect: true }).finally(() => setBusy(false));
          }}
        >
          <label className="block text-xs text-muted-foreground">Access token (JWT)</label>
          <input
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
            placeholder="Paste bearer token"
          />
          <button
            type="submit"
            disabled={busy || !token.trim()}
            className="w-full rounded-md border border-border py-2 text-sm hover:bg-secondary disabled:opacity-50"
          >
            Continue with token
          </button>
        </form>
      )}

      {nothingConfigured && (
        <p className="text-sm text-warning">
          Web auth is not configured. Enable password login with{" "}
          <code className="text-xs">AUTH_ALLOW_PASSWORD_LOGIN=true</code> and set{" "}
          <code className="text-xs">DEV_JWT_SECRET</code> on the API, or configure SSO (
          <code className="text-xs">AUTH_ISSUER</code>, <code className="text-xs">AUTH_CLIENT_ID</code>,{" "}
          <code className="text-xs">AUTH_CLIENT_SECRET</code>), or opt in to token login with{" "}
          <code className="text-xs">AUTH_ALLOW_TOKEN_LOGIN=true</code>.
        </p>
      )}
    </div>
  );
}
