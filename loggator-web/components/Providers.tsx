"use client";

import { SessionProvider } from "next-auth/react";
import type { ReactNode } from "react";
import { AuthProvider } from "./AuthProvider";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <AuthProvider>{children}</AuthProvider>
    </SessionProvider>
  );
}
