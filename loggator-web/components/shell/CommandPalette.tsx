"use client";

import { FileSearch, LayoutDashboard, MessageSquare, ScrollText, Settings, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Item = { href: string; label: string; keywords: string; icon: typeof LayoutDashboard };

const NAV_ITEMS: Item[] = [
  { href: "/dashboard", label: "Dashboard", keywords: "home", icon: LayoutDashboard },
  { href: "/logs", label: "Logs", keywords: "opensearch elastic", icon: ScrollText },
  { href: "/anomalies", label: "Anomalies", keywords: "alerts", icon: FileSearch },
  { href: "/incidents", label: "Incidents", keywords: "cases", icon: FileSearch },
  { href: "/chat", label: "Log assistant", keywords: "ai rag chat", icon: MessageSquare },
  { href: "/support", label: "Support", keywords: "help msp", icon: MessageSquare },
  { href: "/team", label: "Team", keywords: "members users", icon: Users },
  { href: "/settings/integrations", label: "Integrations", keywords: "siem wazuh elastic opensearch", icon: Settings },
  { href: "/settings/account", label: "Account preferences", keywords: "profile theme", icon: Settings },
  { href: "/platform", label: "Operator console", keywords: "msp admin", icon: Settings },
];

export function CommandPaletteTrigger({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return NAV_ITEMS;
    return NAV_ITEMS.filter(
      (i) =>
        i.label.toLowerCase().includes(s) ||
        i.keywords.toLowerCase().includes(s) ||
        i.href.includes(s)
    );
  }, [q]);

  const onKey = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    },
    []
  );

  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKey]);

  return (
    <>
      <Button
        type="button"
        variant="outline"
        className={
          className ??
          "hidden sm:inline-flex h-9 w-full max-w-sm justify-start text-muted-foreground font-normal"
        }
        onClick={() => setOpen(true)}
      >
        <span className="truncate">Search or jump to…</span>
        <kbd className="pointer-events-none ml-auto hidden sm:inline-flex h-5 items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100">
          ⌘K
        </kbd>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="sm:hidden size-9"
        aria-label="Search"
        onClick={() => setOpen(true)}
      >
        <FileSearch className="size-4" />
      </Button>

      {open ? (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] px-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-lg border border-border bg-popover text-popover-foreground shadow-lg overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b border-border p-2">
              <Input
                autoFocus
                placeholder="Filter pages…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="border-0 shadow-none focus-visible:ring-0"
              />
            </div>
            <ul className="max-h-[50vh] overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <li className="px-3 py-2 text-sm text-muted-foreground">No matches</li>
              ) : (
                filtered.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
                      onClick={() => {
                        setOpen(false);
                        setQ("");
                      }}
                    >
                      <item.icon className="size-4 shrink-0 text-muted-foreground" />
                      {item.label}
                    </Link>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      ) : null}
    </>
  );
}
