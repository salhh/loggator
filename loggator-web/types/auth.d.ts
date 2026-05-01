import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    user: DefaultSession["user"] & { id?: string };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    expiresAt?: number;
  }
}

declare module "next-auth" {
  interface User {
    accessToken?: string;
  }
}
