"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type AuthMeResponse } from "@/lib/api";

const allNav = [
  { href: "/platform", label: "Overview" },
  { href: "/platform/tenants", label: "Tenants" },
  { href: "/platform/billing", label: "Billing" },
  { href: "/platform/support", label: "Support" },
  { href: "/platform/audit-log", label: "Audit Log" },
  { href: "/platform/settings", label: "Platform Settings", superOnly: true },
] as const;

export default function PlatformSidebarNav() {
  const pathname = usePathname();
  const [me, setMe] = useState<AuthMeResponse | null>(null);

  useEffect(() => {
    void api
      .authMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  const superOnlyHidden = Boolean(
    me &&
      !me.platform_roles.includes("platform_admin") &&
      me.platform_roles.includes("msp_admin")
  );

  const nav = allNav.filter((item) => {
    if ("superOnly" in item && item.superOnly && superOnlyHidden) return false;
    return true;
  });

  return (
    <nav className="flex flex-col gap-0.5">
      {nav.map(({ href, label }) => {
        const active =
          href === "/platform" ? pathname === "/platform" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`px-3 py-2 rounded-md text-sm transition-colors ${
              active
                ? "border-l-2 border-amber-400 bg-amber-950/40 text-amber-300 pl-[10px]"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
