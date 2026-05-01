"use client";

import { ChevronDown, LogOut, User } from "lucide-react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { signOutEverywhere } from "@/lib/sign-out";
import { Button } from "@/components/ui/button";

export function ProfileMenu() {
  const { data: session } = useSession();
  const { authStatus } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const label =
    session?.user?.email ||
    session?.user?.name ||
    (authStatus === "authenticated" ? "Signed in" : "Account");

  return (
    <div className="relative" ref={ref}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="gap-1 max-w-[200px]"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <User className="size-4 shrink-0" />
        <span className="truncate">{label}</span>
        <ChevronDown className="size-3 shrink-0 opacity-60" />
      </Button>
      {open ? (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[200px] rounded-md border border-border bg-popover py-1 shadow-lg ring-1 ring-foreground/5">
          <Link
            href="/settings/account"
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
            onClick={() => setOpen(false)}
          >
            <User className="size-4" />
            Account preferences
          </Link>
          <button
            type="button"
            className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent text-left"
            onClick={() => void signOutEverywhere(!!session)}
          >
            <LogOut className="size-4" />
            Log out
          </button>
        </div>
      ) : null}
    </div>
  );
}
