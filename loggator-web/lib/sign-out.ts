"use client";

import { signOut } from "next-auth/react";
import {
  setSessionAccessToken,
  setStoredAccessToken,
  setStoredTenantId,
} from "@/lib/auth-headers";

/** Clear tokens and redirect to logout (session) or login (legacy token). */
export async function signOutEverywhere(session: boolean): Promise<void> {
  setStoredAccessToken(null);
  setStoredTenantId(null);
  setSessionAccessToken(null);
  if (typeof window === "undefined") return;
  if (session) {
    window.location.href = "/logout";
  } else {
    window.location.href = "/login";
  }
}

/** NextAuth signOut when session exists; otherwise legacy redirect. */
export async function signOutWithNextAuth(hasNextAuthSession: boolean): Promise<void> {
  if (hasNextAuthSession) {
    await signOut({ redirect: false });
  }
  await signOutEverywhere(hasNextAuthSession);
}
