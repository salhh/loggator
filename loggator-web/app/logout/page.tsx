"use client";

import { signOut, useSession } from "next-auth/react";
import { useEffect } from "react";

function buildEndSessionUrl(endSessionUrl: string, opts: { idToken?: string; postLogoutRedirectUri: string }) {
  const u = new URL(endSessionUrl);
  // Standard-ish params (supported by many OIDC providers)
  u.searchParams.set("post_logout_redirect_uri", opts.postLogoutRedirectUri);
  if (opts.idToken) u.searchParams.set("id_token_hint", opts.idToken);
  return u.toString();
}

export default function LogoutPage() {
  const { data: session, status } = useSession();

  useEffect(() => {
    const endSession = process.env.NEXT_PUBLIC_AUTH_END_SESSION_URL ?? "";
    const postLogout =
      process.env.NEXT_PUBLIC_AUTH_POST_LOGOUT_REDIRECT_URI ??
      (typeof window !== "undefined" ? `${window.location.origin}/login` : "/login");

    async function run() {
      // Clear NextAuth session cookie first.
      await signOut({ redirect: false });

      if (endSession) {
        window.location.href = buildEndSessionUrl(endSession, {
          idToken: session?.idToken,
          postLogoutRedirectUri: postLogout,
        });
        return;
      }
      window.location.href = "/login";
    }

    if (status !== "loading") void run();
  }, [session?.idToken, status]);

  return (
    <div className="min-h-[40vh] flex items-center justify-center text-sm text-muted-foreground">
      Signing out…
    </div>
  );
}

