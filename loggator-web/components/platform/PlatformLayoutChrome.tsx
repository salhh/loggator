"use client";

import { useEffect, useState } from "react";
import { api, type AuthMeResponse } from "@/lib/api";

/** Header strip for the operator sidebar (super-admin vs MSP label). */
export default function PlatformLayoutChrome() {
  const [me, setMe] = useState<AuthMeResponse | null>(null);

  useEffect(() => {
    void api
      .authMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  const isSuper = me?.platform_roles.includes("platform_admin");
  const mspLabel =
    me?.operator_tenant_name || me?.operator_tenant_slug || me?.operator_tenant_id || "MSP";

  return (
    <div className="px-4 py-4 border-b border-border shrink-0">
      {isSuper ? (
        <div className="text-xs font-bold tracking-widest text-amber-400 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-amber-400 inline-block" />
          SUPER ADMIN
        </div>
      ) : (
        <div className="space-y-0.5">
          <div className="text-xs font-bold tracking-widest text-amber-400 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-amber-400 inline-block" />
            Operator console
          </div>
          <p className="text-[11px] text-muted-foreground truncate" title={mspLabel}>
            {mspLabel}
          </p>
        </div>
      )}
    </div>
  );
}
