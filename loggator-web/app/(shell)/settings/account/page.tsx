"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function AccountPreferencesPage() {
  const { theme, setTheme } = useTheme();
  const { tenants, tenantId, setTenantId, authStatus } = useAuth();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Account preferences</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Appearance and workspace defaults for this browser.
        </p>
      </div>

      <Card className="p-4 space-y-4">
        <div>
          <h2 className="text-sm font-medium text-foreground">Theme</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Choose light, dark, or match your system.
          </p>
          <div className="flex flex-wrap gap-2 mt-3">
            {(["light", "dark", "system"] as const).map((t) => (
              <Button
                key={t}
                type="button"
                variant={mounted && theme === t ? "default" : "outline"}
                size="sm"
                className="capitalize"
                onClick={() => setTheme(t)}
              >
                {t}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      {authStatus === "authenticated" && tenants.length > 1 ? (
        <Card className="p-4 space-y-3">
          <h2 className="text-sm font-medium text-foreground">Default tenant</h2>
          <p className="text-xs text-muted-foreground">
            Pre-select a tenant when you open the app (stored in this browser).
          </p>
          <select
            value={tenantId ?? ""}
            onChange={(e) => setTenantId(e.target.value || null)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">Last used / prompt</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </Card>
      ) : null}

      <Card className="p-4 space-y-2">
        <h2 className="text-sm font-medium text-foreground">Notifications</h2>
        <p className="text-xs text-muted-foreground">
          Notification preferences will be available in a future release.
        </p>
      </Card>
    </div>
  );
}
