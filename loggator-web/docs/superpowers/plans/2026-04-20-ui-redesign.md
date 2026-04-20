# Loggator UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default shadcn/light theme with a dark data-dashboard aesthetic (Grafana/Datadog style) — cyan accent on dark gray surfaces, tinted severity cards, dual-line chart, redesigned sidebar.

**Architecture:** CSS variable overrides drive the token system; new shared components (AnomalyCard, StatCard, AnomalyChart, SidebarStatus) are composed into updated pages. The sidebar gains active-link detection via `usePathname` (client component wrapper) and a live status footer.

**Tech Stack:** Next.js 15 App Router · Tailwind CSS · shadcn/ui · Recharts 3

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Modify | `app/globals.css` | CSS variable overrides for dark palette |
| Modify | `app/layout.tsx` | Sidebar redesign — cyan branding, active nav, status footer |
| Create | `components/SidebarNav.tsx` | Client component for active-link detection |
| Create | `components/SidebarStatus.tsx` | Streaming + Ollama status footer (polls `/api/v1/status`) |
| Create | `components/AnomalyCard.tsx` | Tinted severity card (reused everywhere) |
| Create | `components/StatCard.tsx` | Single metric card with colored left border |
| Create | `components/AnomalyChart.tsx` | Recharts dual line chart |
| Modify | `app/page.tsx` | Two-column grid dashboard |
| Modify | `components/LiveFeed.tsx` | Use AnomalyCard, remove Badge style |
| Modify | `app/anomalies/page.tsx` | Use AnomalyCard component |
| Modify | `app/summaries/page.tsx` | Restyle with surface/border tokens |
| Modify | `app/alerts/page.tsx` | Restyle with new palette |
| Modify | `app/chat/ChatClient.tsx` | Dark bubbles, cyan send button |
| Modify | `app/settings/SettingsClient.tsx` | Dark inputs, cyan save button |

---

### Task 1: CSS Variables (globals.css)

**Files:** Modify `app/globals.css`

- [ ] Replace the `:root` and `.dark` blocks with dark-palette tokens. The app always uses dark mode so consolidate into `:root`:

```css
:root {
  --background: oklch(13.7% 0.017 264);   /* #111827 gray-900 */
  --foreground: oklch(98% 0 0);            /* #f9fafb */
  --card: oklch(19.8% 0.014 264);          /* #1f2937 gray-800 */
  --card-foreground: oklch(98% 0 0);
  --popover: oklch(19.8% 0.014 264);
  --popover-foreground: oklch(98% 0 0);
  --primary: oklch(83% 0.15 196);          /* #22d3ee cyan-400 */
  --primary-foreground: oklch(10% 0 0);
  --secondary: oklch(24% 0.012 264);
  --secondary-foreground: oklch(98% 0 0);
  --muted: oklch(19.8% 0.014 264);
  --muted-foreground: oklch(47% 0.01 264); /* #6b7280 */
  --accent: oklch(19.8% 0.014 264);
  --accent-foreground: oklch(83% 0.15 196);
  --destructive: oklch(59% 0.22 27);       /* #ef4444 */
  --border: oklch(24% 0.012 264);          /* #374151 */
  --input: oklch(24% 0.012 264);
  --ring: oklch(83% 0.15 196);
  --radius: 0.5rem;
  --sidebar: oklch(19.8% 0.014 264);
  --sidebar-foreground: oklch(98% 0 0);
  --sidebar-primary: oklch(83% 0.15 196);
  --sidebar-primary-foreground: oklch(10% 0 0);
  --sidebar-accent: oklch(24% 0.012 264);
  --sidebar-accent-foreground: oklch(83% 0.15 196);
  --sidebar-border: oklch(24% 0.012 264);
  --sidebar-ring: oklch(83% 0.15 196);
}
```

- [ ] Remove the separate `.dark { ... }` block (we always render dark)

---

### Task 2: AnomalyCard component

**Files:** Create `components/AnomalyCard.tsx`

- [ ] Create the component:

```tsx
interface AnomalyCardProps {
  severity: string;
  summary: string;
  meta?: string;
  timestamp?: string;
}

const config = {
  high: {
    bg: "bg-[#2d1b1b]", border: "border-[#7f1d1d]",
    iconBg: "bg-red-500", iconText: "text-white", letter: "H",
    titleColor: "text-red-300",
  },
  medium: {
    bg: "bg-[#292118]", border: "border-[#78350f]",
    iconBg: "bg-amber-500", iconText: "text-black", letter: "M",
    titleColor: "text-amber-300",
  },
  low: {
    bg: "bg-card", border: "border-border",
    iconBg: "bg-[#374151]", iconText: "text-gray-300", letter: "L",
    titleColor: "text-gray-300",
  },
};

export default function AnomalyCard({ severity, summary, meta, timestamp }: AnomalyCardProps) {
  const c = config[severity as keyof typeof config] ?? config.low;
  return (
    <div className={`rounded-lg border p-3 flex items-start gap-3 ${c.bg} ${c.border}`}>
      <div className={`w-7 h-7 rounded flex items-center justify-center shrink-0 font-black text-xs ${c.iconBg} ${c.iconText}`}>
        {c.letter}
      </div>
      <div className="min-w-0">
        <p className={`text-sm font-semibold truncate ${c.titleColor}`}>{summary}</p>
        {(meta || timestamp) && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {[meta, timestamp].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>
    </div>
  );
}
```

---

### Task 3: StatCard component

**Files:** Create `components/StatCard.tsx`

- [ ] Create the component:

```tsx
interface StatCardProps {
  label: string;
  value: string | number;
  borderColor: string; // Tailwind class e.g. "border-red-500"
}

export default function StatCard({ label, value, borderColor }: StatCardProps) {
  return (
    <div className={`bg-card rounded-lg border border-border border-l-4 ${borderColor} p-4`}>
      <div className="text-2xl font-bold text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}
```

---

### Task 4: AnomalyChart component

**Files:** Create `components/AnomalyChart.tsx`

- [ ] Install recharts types if missing: `npm install --save-dev @types/recharts` (skip if already in package.json)

- [ ] Create the component:

```tsx
"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

interface ChartPoint {
  hour: string;
  errors: number;
  anomalies: number;
}

interface AnomalyChartProps {
  data: ChartPoint[];
}

export default function AnomalyChart({ data }: AnomalyChartProps) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="hour" stroke="#6b7280" tick={{ fill: "#6b7280", fontSize: 11 }} />
        <YAxis stroke="#6b7280" tick={{ fill: "#6b7280", fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 6 }}
          labelStyle={{ color: "#f9fafb" }}
          itemStyle={{ color: "#f9fafb" }}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: "#6b7280" }} />
        <Line type="monotone" dataKey="errors" stroke="#ef4444" strokeWidth={1.5} dot={false} name="Errors" />
        <Line type="monotone" dataKey="anomalies" stroke="#22d3ee" strokeWidth={1.5} dot={false} name="Anomalies" />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

---

### Task 5: SidebarNav (client component for active links)

**Files:** Create `components/SidebarNav.tsx`

- [ ] Create the client component:

```tsx
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
                : "text-muted-foreground hover:text-foreground hover:bg-card"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
```

---

### Task 6: SidebarStatus component

**Files:** Create `components/SidebarStatus.tsx`

- [ ] Create the polling status footer:

```tsx
"use client";

import { useEffect, useState } from "react";

interface StatusData {
  streaming_active?: boolean;
  ollama_reachable?: boolean;
  ollama_ok?: boolean;
}

export default function SidebarStatus() {
  const [status, setStatus] = useState<StatusData | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
    const fetchStatus = () =>
      fetch(`${apiUrl}/status`).then((r) => r.json()).then(setStatus).catch(() => {});
    fetchStatus();
    const id = setInterval(fetchStatus, 30_000);
    return () => clearInterval(id);
  }, []);

  const streaming = status?.streaming_active ?? false;
  const ollama = status?.ollama_reachable ?? status?.ollama_ok ?? false;

  return (
    <div className="flex flex-col gap-2 px-3 py-3 border-t border-border text-xs text-muted-foreground">
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${streaming ? "bg-emerald-500" : "bg-red-500"}`} />
        Streaming
      </div>
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${ollama ? "bg-emerald-500" : "bg-red-500"}`} />
        Ollama
      </div>
    </div>
  );
}
```

---

### Task 7: Redesign layout.tsx

**Files:** Modify `app/layout.tsx`

- [ ] Replace sidebar with new design using SidebarNav + SidebarStatus:

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import SidebarNav from "@/components/SidebarNav";
import SidebarStatus from "@/components/SidebarStatus";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Loggator",
  description: "AI-powered log analysis dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex bg-background text-foreground">
        <aside className="w-[180px] shrink-0 flex flex-col border-r border-border bg-card">
          <div className="px-4 py-5">
            <div className="text-sm font-bold tracking-widest text-cyan-400 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-cyan-400 inline-block" />
              LOGGATOR
            </div>
          </div>
          <div className="flex-1 px-2">
            <SidebarNav />
          </div>
          <SidebarStatus />
        </aside>
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </body>
    </html>
  );
}
```

---

### Task 8: Rewrite app/page.tsx (Dashboard)

**Files:** Modify `app/page.tsx`

- [ ] Aggregate chart data from anomalies list (client-side by hour), render two-column grid:

```tsx
import { api } from "@/lib/api";
import type { Anomaly, Summary } from "@/lib/types";
import StatCard from "@/components/StatCard";
import AnomalyChart from "@/components/AnomalyChart";
import AnomalyCard from "@/components/AnomalyCard";
import LiveFeed from "@/components/LiveFeed";
import Link from "next/link";

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

function buildChartData(anomalies: Anomaly[]) {
  const buckets: Record<string, { errors: number; anomalies: number }> = {};
  for (const a of anomalies) {
    const hour = new Date(a.detected_at).toISOString().slice(11, 13) + ":00";
    if (!buckets[hour]) buckets[hour] = { errors: 0, anomalies: 0 };
    buckets[hour].anomalies++;
    if (a.severity === "high") buckets[hour].errors++;
  }
  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, v]) => ({ hour, ...v }));
}

export default async function Dashboard() {
  const [statusRes, summariesRes, anomaliesRes] = await Promise.allSettled([
    api.status(),
    api.summaries(5),
    api.anomalies(100),
  ]);

  const s = statusRes.status === "fulfilled" ? statusRes.value : null;
  const latestSummary =
    summariesRes.status === "fulfilled" && summariesRes.value.length > 0
      ? summariesRes.value[0]
      : null;
  const allAnomalies = anomaliesRes.status === "fulfilled" ? anomaliesRes.value : [];
  const recentAnomalies = allAnomalies.slice(0, 8);
  const chartData = buildChartData(allAnomalies);

  const highCount = allAnomalies.filter((a) => a.severity === "high").length;
  const medCount = allAnomalies.filter((a) => a.severity === "medium").length;

  return (
    <div className="grid grid-cols-[2fr_1fr] gap-6 h-full">
      {/* Left column */}
      <div className="space-y-6">
        {/* Stat row */}
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="High anomalies" value={highCount} borderColor="border-l-red-500" />
          <StatCard label="Total anomalies" value={allAnomalies.length} borderColor="border-l-cyan-400" />
          <StatCard
            label="Ollama"
            value={(s?.ollama_ok || s?.ollama_reachable) ? "OK" : "Offline"}
            borderColor="border-l-emerald-500"
          />
          <StatCard label="Medium alerts" value={medCount} borderColor="border-l-amber-500" />
        </div>

        {/* Chart */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-4">
            Errors + Anomalies · last 24h
          </div>
          <AnomalyChart data={chartData} />
        </div>
      </div>

      {/* Right column */}
      <div className="space-y-6">
        {/* Live feed */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Live anomaly feed</div>
          <LiveFeed />
        </div>

        {/* Latest summary */}
        {latestSummary && (
          <div className="bg-card rounded-lg border border-border p-4 space-y-2">
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Latest summary</div>
            <p className="text-xs text-muted-foreground">
              {fmt(latestSummary.window_start)} → {fmt(latestSummary.window_end)}
            </p>
            <p className="text-sm">{latestSummary.summary}</p>
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>Errors: <strong className="text-foreground">{latestSummary.error_count}</strong></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### Task 9: Update LiveFeed.tsx

**Files:** Modify `components/LiveFeed.tsx`

- [ ] Replace Badge cards with AnomalyCard:

```tsx
"use client";

import { useState } from "react";
import { useWebSocket, type WsEvent } from "@/lib/websocket";
import AnomalyCard from "@/components/AnomalyCard";

interface LiveAnomaly {
  anomaly_id: string;
  severity: string;
  summary: string;
  detected_at: string;
  index_pattern: string;
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString();
}

export default function LiveFeed() {
  const [events, setEvents] = useState<LiveAnomaly[]>([]);
  const { connected } = useWebSocket((event: WsEvent) => {
    if (event.type === "anomaly") {
      setEvents((prev) => [event as unknown as LiveAnomaly, ...prev].slice(0, 20));
    }
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-2">
        <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-muted-foreground"}`} />
        <span className="text-xs text-muted-foreground">{connected ? "connected" : "connecting..."}</span>
      </div>
      {events.length === 0 ? (
        <p className="text-xs text-muted-foreground">Waiting for anomalies...</p>
      ) : (
        <div className="space-y-2">
          {events.map((e) => (
            <AnomalyCard
              key={e.anomaly_id}
              severity={e.severity}
              summary={e.summary}
              meta={e.index_pattern}
              timestamp={fmtTime(e.detected_at)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

---

### Task 10: Update anomalies/page.tsx

**Files:** Modify `app/anomalies/page.tsx`

- [ ] Replace Card/Badge with AnomalyCard:

```tsx
import { api } from "@/lib/api";
import type { Anomaly } from "@/lib/types";
import AnomalyCard from "@/components/AnomalyCard";

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

export default async function AnomaliesPage() {
  let anomalies: Anomaly[] = [];
  try { anomalies = await api.anomalies(100); } catch {}

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Anomalies</h1>
      {anomalies.length === 0 ? (
        <p className="text-sm text-muted-foreground">No anomalies detected yet.</p>
      ) : (
        <div className="space-y-2">
          {anomalies.map((a) => (
            <AnomalyCard
              key={a.id}
              severity={a.severity}
              summary={a.summary}
              meta={a.root_cause_hints.slice(0, 2).join(" · ")}
              timestamp={fmtRelative(a.detected_at)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

---

### Task 11: Restyle summaries, alerts, chat, settings

**Files:** Modify `app/summaries/page.tsx`, `app/alerts/page.tsx`, `app/chat/ChatClient.tsx`, `app/settings/SettingsClient.tsx`

These use the same surface tokens so they update automatically from globals.css. Changes are targeted:

**summaries/page.tsx:** Replace `<Card>` border with explicit `border-border bg-card` classes — no structural change needed since tokens now map to dark palette.

**alerts/page.tsx:** Same token-based approach — status badge colors update from `--destructive`.

**chat/ChatClient.tsx:** Add `bg-cyan-400 text-black` to the send button; user message bubbles get `bg-card`.

**settings/SettingsClient.tsx:** Add `bg-cyan-400 text-black` to the save button.

---

### Task 12: Build verification

- [ ] Run `npm run build` in `loggator-web/`
- [ ] Fix any TypeScript errors
- [ ] Start dev server and visually verify: sidebar active state, stat cards, chart renders, AnomalyCard tints
