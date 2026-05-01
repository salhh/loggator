import { Suspense } from "react";
import { LoginClient } from "./LoginClient";

/** Read OIDC / auth flags from the container at request time (not at `next build`). */
export const dynamic = "force-dynamic";

function loginUiFlags(): { showSso: boolean; showPassword: boolean; showToken: boolean } {
  const issuer = process.env.AUTH_ISSUER?.replace(/\/$/, "").trim() ?? "";
  const clientId = process.env.AUTH_CLIENT_ID?.trim() ?? "";
  const clientSecret = process.env.AUTH_CLIENT_SECRET?.trim() ?? "";
  const oidcReady = Boolean(issuer && clientId && clientSecret);
  const allowTokenLogin = process.env.AUTH_ALLOW_TOKEN_LOGIN === "true";
  const allowPasswordLogin = process.env.AUTH_ALLOW_PASSWORD_LOGIN !== "false";
  const ssoEnabled = process.env.AUTH_SSO_ENABLED !== "false";

  const showSso = oidcReady && ssoEnabled;
  const showPassword = allowPasswordLogin;
  const showToken = allowTokenLogin;

  return { showSso, showPassword, showToken };
}

export default function LoginPage() {
  const flags = loginUiFlags();
  return (
    <Suspense
      fallback={
        <div className="min-h-[40vh] flex items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      }
    >
      <LoginClient showSso={flags.showSso} showPassword={flags.showPassword} showToken={flags.showToken} />
    </Suspense>
  );
}
