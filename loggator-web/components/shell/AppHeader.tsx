"use client";

import Link from "next/link";
import { CommandPaletteTrigger } from "./CommandPalette";
import { HeaderTenantSelect } from "./HeaderTenantSelect";
import { ProfileMenu } from "./ProfileMenu";
import { ThemeToggle } from "./ThemeToggle";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-3 border-b border-header-border bg-header/95 px-4 shadow-sm supports-[backdrop-filter]:backdrop-blur-md dark:bg-header">
      <Link
        href="/dashboard"
        className="hidden sm:flex items-center gap-2 text-sm font-semibold tracking-tight text-foreground shrink-0"
      >
        <span className="size-2 rounded-full bg-primary" aria-hidden />
        Loggator
      </Link>
      <div className="flex items-center gap-2 shrink-0">
        <HeaderTenantSelect />
      </div>
      <div className="flex-1 flex justify-center min-w-0 px-2">
        <CommandPaletteTrigger />
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <ThemeToggle />
        <ProfileMenu />
      </div>
    </header>
  );
}
