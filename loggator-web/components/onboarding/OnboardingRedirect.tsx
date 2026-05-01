"use client";

import { useSession } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api, type AuthMeResponse } from "@/lib/api";
import { isOnboardingComplete } from "@/lib/onboarding-storage";

/**
 * Sends eligible users to /onboarding until they finish or skip (shell routes only).
 */
export function OnboardingRedirect({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, status: sessionStatus } = useSession();
  const { authStatus } = useAuth();
  const [me, setMe] = useState<AuthMeResponse | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (sessionStatus === "loading" || authStatus === "loading") return;
    if (authStatus !== "authenticated") {
      setChecked(true);
      return;
    }
    void api
      .authMe()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setChecked(true));
  }, [sessionStatus, authStatus]);

  useEffect(() => {
    if (!checked || !me) return;
    if (pathname.startsWith("/onboarding")) return;
    if (pathname.startsWith("/login") || pathname.startsWith("/logout")) return;

    const sub = me.user_id || session?.user?.email || "";
    if (!sub) return;

    const tenantAdmin = (me.roles || []).includes("tenant_admin");
    const operator = me.platform_roles.includes("msp_admin") || me.platform_roles.includes("platform_admin");
    if (!tenantAdmin && !operator) return;

    if (isOnboardingComplete(sub)) return;

    router.replace("/onboarding");
  }, [checked, me, pathname, router, session?.user?.email]);

  return <>{children}</>;
}
