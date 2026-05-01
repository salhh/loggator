"use client";

import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";

export default function PlatformGuard({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "allowed" | "forbidden">("loading");

  useEffect(() => {
    api
      .authMe()
      .then((me) => {
        const ok =
          me.platform_roles.includes("platform_admin") || me.platform_roles.includes("msp_admin");
        setState(ok ? "allowed" : "forbidden");
      })
      .catch(() => setState("forbidden"));
  }, []);

  if (state === "loading") {
    return (
      <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
        <span className="animate-pulse">Checking access…</span>
      </div>
    );
  }

  if (state === "forbidden") {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-2">
        <p className="text-amber-400 font-semibold">Access denied</p>
        <p className="text-sm text-muted-foreground">
          This area requires a <code className="text-xs">platform_admin</code> or{" "}
          <code className="text-xs">msp_admin</code> role.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
