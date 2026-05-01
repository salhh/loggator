import type { NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";

const issuer = process.env.AUTH_ISSUER?.replace(/\/$/, "") ?? "";
const clientId = process.env.AUTH_CLIENT_ID ?? "";
const clientSecret = process.env.AUTH_CLIENT_SECRET ?? "";
const allowTokenLogin = process.env.AUTH_ALLOW_TOKEN_LOGIN === "true";
const allowPasswordLogin = process.env.AUTH_ALLOW_PASSWORD_LOGIN !== "false";

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

function apiV1Base(): string {
  const raw =
    process.env.API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://localhost:8000/api/v1";
  return raw.replace(/\/$/, "");
}

if (allowPasswordLogin) {
  providers.push(
    Credentials({
      id: "password",
      name: "Email and password",
      credentials: {
        username: { label: "Email or username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const username = typeof credentials?.username === "string" ? credentials.username.trim() : "";
        const password = typeof credentials?.password === "string" ? credentials.password : "";
        if (!username || !password) return null;
        try {
          const res = await fetch(`${apiV1Base()}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
          });
          if (!res.ok) return null;
          const data = (await res.json()) as { access_token?: string };
          if (!data.access_token) return null;
          return {
            id: username,
            name: username,
            email: "",
            accessToken: data.access_token,
          };
        } catch {
          return null;
        }
      },
    })
  );
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

// `next build` / no providers configured: keep token fallback so NextAuth still initializes.
if (providers.length === 0) {
  providers.push(
    Credentials({
      id: "dev-token",
      name: "Access token (configure OIDC or password login)",
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
      if (account?.id_token) {
        token.idToken = account.id_token;
      }
      if (user?.accessToken) {
        token.accessToken = user.accessToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string | undefined;
      session.idToken = token.idToken as string | undefined;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
} satisfies NextAuthConfig;
