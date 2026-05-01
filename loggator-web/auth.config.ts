import type { NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";

const issuer = process.env.AUTH_ISSUER?.replace(/\/$/, "") ?? "";
const clientId = process.env.AUTH_CLIENT_ID ?? "";
const clientSecret = process.env.AUTH_CLIENT_SECRET ?? "";
const allowTokenLogin = process.env.AUTH_ALLOW_TOKEN_LOGIN === "true";

const providers: NextAuthConfig["providers"] = [];

if (issuer && clientId && clientSecret) {
  providers.push({
    id: "oidc",
    name: "SSO",
    type: "oidc",
    issuer,
    clientId,
    clientSecret,
    authorization: { params: { scope: "openid email profile" } },
    checks: ["pkce", "state"],
  });
}

if (allowTokenLogin) {
  providers.push(
    Credentials({
      id: "dev-token",
      name: "Access token",
      credentials: {
        token: { label: "JWT / access token", type: "password" },
      },
      async authorize(credentials) {
        const raw = credentials?.token;
        const token = typeof raw === "string" ? raw.trim() : "";
        if (!token) return null;
        return {
          id: "token",
          name: "Token",
          email: null,
          accessToken: token,
        };
      },
    })
  );
}

// Local `next build` / misconfiguration: avoid zero providers (NextAuth requires at least one).
if (providers.length === 0) {
  providers.push(
    Credentials({
      id: "dev-token",
      name: "Access token (configure OIDC or AUTH_ALLOW_TOKEN_LOGIN)",
      credentials: {
        token: { label: "JWT / access token", type: "password" },
      },
      async authorize(credentials) {
        const raw = credentials?.token;
        const token = typeof raw === "string" ? raw.trim() : "";
        if (!token) return null;
        return {
          id: "token",
          name: "Token",
          email: null,
          accessToken: token,
        };
      },
    })
  );
}

export const authConfig = {
  providers,
  trustHost: true,
  session: { strategy: "jwt" as const, maxAge: 60 * 60 * 24 * 7 },
  callbacks: {
    async jwt({ token, user, account }) {
      if (account?.access_token) {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
      }
      if (user?.accessToken) {
        token.accessToken = user.accessToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string | undefined;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
} satisfies NextAuthConfig;
