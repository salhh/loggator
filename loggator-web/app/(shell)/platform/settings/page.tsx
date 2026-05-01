import SettingsClient from "@/app/(shell)/settings/SettingsClient";
import { api } from "@/lib/api";

export default async function PlatformSettingsPage() {
  let settings: Record<string, string> = {};
  let envFile = "";

  try {
    const res = await api.settings();
    settings = res.settings;
    envFile = res.env_file;
  } catch {
    // API offline
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">Platform Configuration</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Global environment settings — changes apply platform-wide.
        </p>
      </div>
      {envFile ? (
        <SettingsClient initial={settings} envFile={envFile} />
      ) : (
        <p className="text-muted-foreground text-sm">Could not load settings — is the API running?</p>
      )}
    </div>
  );
}
