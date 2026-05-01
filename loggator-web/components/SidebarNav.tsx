"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/platform", label: "Platform Admin", separator: false },
  // ── Detection ──
  { href: "/anomalies", label: "Anomalies" },
  { href: "/incidents", label: "Incidents" },
  { href: "/rules", label: "Detection Rules" },
  { href: "/alerts", label: "Alerts" },
  // ── Analysis ──
  { href: "/logs", label: "Logs" },
  { href: "/summaries", label: "Summaries" },
  { href: "/reports", label: "Reports" },
  { href: "/stats", label: "Statistics" },
  { href: "/chat", label: "Chat" },
  // ── Platform ──
  { href: "/health", label: "Health" },
  { href: "/settings", label: "Settings" },
];

export default function SidebarNav() {
  const pathname = usePathname();
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
