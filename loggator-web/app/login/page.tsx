"use client";

import { signIn, useSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function LoginInner() {
  const { status } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") || "/";
  const error = params.get("error");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const showSso = process.env.NEXT_PUBLIC_AUTH_SSO_ENABLED === "true";
  const showToken = process.env.NEXT_PUBLIC_AUTH_ALLOW_TOKEN === "true";

  useEffect(() => {
    if (status === "authenticated") router.replace(callbackUrl);
  }, [status, router, callbackUrl]);

  if (status === "loading" || status === "authenticated") {
    return (
      <div className="min-h-[40vh] flex items-center justify-center text-sm text-muted-foreground">
        Redirecting…
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-6 py-12 px-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Log in</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Sign in with your organization SSO or a development access token.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          Sign-in error: {error}
        </div>
      )}

      {showSso && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void signIn("oidc", { callbackUrl });
          }}
          className="w-full rounded-md bg-cyan-400 text-black py-2.5 text-sm font-semibold hover:bg-cyan-300 disabled:opacity-50"
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
            void signIn("dev-token", { token, callbackUrl, redirect: true }).finally(() =>
              setBusy(false)
            );
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

      {!showSso && !showToken && (
        <p className="text-sm text-amber-200/90">
          Web auth is not configured. Set{" "}
          <code className="text-xs">AUTH_ISSUER</code>, <code className="text-xs">AUTH_CLIENT_ID</code>,{" "}
          <code className="text-xs">AUTH_CLIENT_SECRET</code>, and{" "}
          <code className="text-xs">NEXT_PUBLIC_AUTH_SSO_ENABLED=true</code>, or enable token login with{" "}
          <code className="text-xs">AUTH_ALLOW_TOKEN_LOGIN</code> and{" "}
          <code className="text-xs">NEXT_PUBLIC_AUTH_ALLOW_TOKEN=true</code>.
        </p>
      )}
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[40vh] flex items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      }
    >
      <LoginInner />
    </Suspense>
  );
}
