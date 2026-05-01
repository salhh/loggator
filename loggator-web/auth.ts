import NextAuth from "next-auth";
import { authConfig } from "./auth.config";

if (authConfig.providers.length === 0) {
  console.warn("[auth] No providers — this should not happen (fallback dev-token is registered).");
}

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
