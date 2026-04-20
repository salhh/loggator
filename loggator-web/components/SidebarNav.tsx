"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/", label: "Dashboard" },
  { href: "/summaries", label: "Summaries" },
  { href: "/anomalies", label: "Anomalies" },
  { href: "/alerts", label: "Alerts" },
  { href: "/chat", label: "Chat" },
  { href: "/settings", label: "Settings" },
];

export default function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-0.5">
      {nav.map(({ href, label }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
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
