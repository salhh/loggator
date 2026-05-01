"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type AuthMeResponse } from "@/lib/api";

type NavItem = { href: string; label: string; operatorOnly?: boolean };

const baseNav: NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/platform", label: "Operator console", operatorOnly: true },
  { href: "/anomalies", label: "Anomalies" },
  { href: "/incidents", label: "Incidents" },
  { href: "/rules", label: "Detection Rules" },
  { href: "/alerts", label: "Alerts" },
  { href: "/logs", label: "Logs" },
  { href: "/summaries", label: "Summaries" },
  { href: "/reports", label: "Reports" },
  { href: "/stats", label: "Statistics" },
  { href: "/chat", label: "Log assistant" },
  { href: "/support", label: "Support" },
  { href: "/health", label: "Health" },
  { href: "/settings", label: "Settings" },
];

function isOperator(me: AuthMeResponse | null) {
  if (!me) return false;
  return (
    me.platform_roles.includes("platform_admin") || me.platform_roles.includes("msp_admin")
  );
}

export default function SidebarNav() {
  const pathname = usePathname();
  const [me, setMe] = useState<AuthMeResponse | null>(null);

  useEffect(() => {
    void api
      .authMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  const op = isOperator(me);
  const nav = baseNav.filter((item) => !item.operatorOnly || op);

  return (
    <nav className="flex flex-col gap-0.5">
      {nav.map(({ href, label }) => {
        const active =
          href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`px-3 py-2 rounded-md text-sm transition-colors ${
              active
                ? "border-l-2 border-cyan-400 bg-cyan-950/40 text-cyan-300 pl-[10px]"
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
