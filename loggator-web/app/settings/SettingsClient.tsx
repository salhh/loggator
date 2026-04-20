"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

interface Props {
  initial: Record<string, string>;
  envFile: string;
}

export default function SettingsClient({ initial, envFile }: Props) {
  const [values, setValues] = useState<Record<string, string>>(initial);
  const [dirty, setDirty] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  function onChange(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
    setDirty((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  async function save() {
    if (Object.keys(dirty).length === 0) return;
    setSaving(true);
    try {
      const res = await api.updateSettings(dirty);
      setValues(res.settings);
      setDirty({});
      setSaved(true);
    } catch {
      alert("Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">Editing: {envFile}</p>

      <div className="space-y-2">
        {Object.entries(values).map(([key, value]) => (
          <div key={key} className="grid grid-cols-[280px_1fr] gap-3 items-center">
            <label className="text-sm font-mono text-muted-foreground">{key}</label>
            <Input
              value={dirty[key] ?? value}
              onChange={(e) => onChange(key, e.target.value)}
              className={`font-mono text-sm bg-card border-border ${
                dirty[key] !== undefined ? "border-cyan-400" : ""
              }`}
            />
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving || Object.keys(dirty).length === 0}
          className="px-4 py-2 rounded-md bg-cyan-400 text-black text-sm font-semibold hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? "Saving..." : "Save changes"}
        </button>
        {saved && <span className="text-sm text-emerald-400">Saved</span>}
        {Object.keys(dirty).length > 0 && !saving && (
          <span className="text-sm text-muted-foreground">
            {Object.keys(dirty).length} unsaved change(s)
          </span>
        )}
      </div>
    </div>
  );
}
