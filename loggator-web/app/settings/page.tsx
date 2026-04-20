import SettingsClient from "./SettingsClient";
import { api } from "@/lib/api";

export default async function SettingsPage() {
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
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Edit your environment configuration. Changes are written to the .env file immediately.
        </p>
      </div>
      {envFile ? (
        <SettingsClient initial={settings} envFile={envFile} />
      ) : (
        <p className="text-muted-foreground">Could not load settings — is the API running?</p>
      )}
    </div>
  );
}
