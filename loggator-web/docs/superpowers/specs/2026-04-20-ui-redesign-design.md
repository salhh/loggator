# Loggator UI Redesign — Design Spec

**Date:** 2026-04-20  
**Status:** Approved

---

## Overview

Full visual redesign of the Loggator Next.js dashboard. Direction: **Dark Data Dashboard** — Grafana/Datadog aesthetic. Dense, information-rich, professional. Cyan accent on dark gray surfaces.

---

## Color Palette

| Token | Value | Usage |
|---|---|---|
| Background | `#111827` (gray-900) | Page body |
| Surface | `#1f2937` (gray-800) | Cards, sidebar, inputs |
| Border | `#374151` (gray-700) | Dividers, card borders |
| Accent (cyan) | `#22d3ee` (cyan-400) | Active nav, buttons, primary actions, anomaly chart line |
| Error (red) | `#ef4444` (red-500) | HIGH severity, error chart line |
| Warning (amber) | `#f59e0b` (amber-500) | MEDIUM severity |
| Low (gray) | `#374151` (gray-700) | LOW severity |
| Success (green) | `#10b981` (emerald-500) | Status OK, streaming active |
| Text primary | `#f9fafb` (gray-50) | Headings, primary content |
| Text muted | `#6b7280` (gray-500) | Timestamps, labels, secondary info |

### Severity Card Tints
- HIGH: background `#2d1b1b`, border `#7f1d1d`
- MEDIUM: background `#292118`, border `#78350f`
- LOW: background `#1f2937`, border `#374151`

---

## CSS Variable Changes

Update `globals.css` to align shadcn CSS variables with the design palette:

```css
:root {
  --background: 217 33% 8%;       /* #111827 */
  --foreground: 210 40% 98%;      /* #f9fafb */
  --card: 215 28% 17%;            /* #1f2937 */
  --card-foreground: 210 40% 98%;
  --border: 215 20% 27%;          /* #374151 */
  --primary: 189 94% 53%;         /* #22d3ee cyan */
  --primary-foreground: 0 0% 7%;
  --muted: 215 28% 17%;
  --muted-foreground: 215 14% 47%; /* #6b7280 */
  --accent: 215 28% 17%;
  --accent-foreground: 189 94% 53%;
  --destructive: 0 84% 60%;       /* #ef4444 */
}
```

---

## Layout

### Sidebar (180px, fixed)
- Logo "LOGGATOR" in cyan at top with small dot indicator
- Nav links — plain text when inactive, cyan left border + subtle tinted background when active
- Bottom section: streaming status (green dot = active) + Ollama status (green/red dot)

### Main content area
- **Dashboard page**: two-column grid `2fr 1fr`
  - Left: 4-stat row → dual line chart (full width)
  - Right: live anomaly feed → last AI summary card
- **All other pages**: single full-width column with page title + content

---

## Components

### AnomalyCard
Tinted background severity card used on the anomalies page, dashboard, and live feed:

```
┌─────────────────────────────────────────┐  ← border color by severity
│ [H]  OOM killer invoked on auth-service │  ← icon block + title
│      Memory limit exceeded · 2m ago     │  ← meta row
└─────────────────────────────────────────┘
```

- Icon block: `28×28px` square, severity color background, bold letter (H/M/L) in white/black
- Title: `text-sm font-semibold`, severity-tinted color (`#fca5a5` for HIGH, `#fcd34d` for MED, `#d1d5db` for LOW)
- Meta row: root cause hints joined · timestamp · index pattern — all in `text-muted-foreground`
- Whole card: tinted background + colored border, `rounded-lg`

### AnomalyChart (Recharts)
Dual `LineChart` — two lines, shared X axis (time buckets):
- Red line (`#ef4444`): error count per bucket
- Cyan line (`#22d3ee`): anomaly count per bucket
- Dashed grid lines (`#374151`)
- No fill / no area — clean lines only
- Tooltip showing both values on hover
- X axis: time labels (HH:mm), Y axis: count
- Data sourced from `GET /api/v1/anomalies` + `GET /api/v1/summaries` (aggregated client-side by hour)

### StatCard
4-up row at top of dashboard:
- Background: surface (`#1f2937`)
- Left border: color by metric (red=errors, cyan=anomalies, green=status, amber=alerts)
- Large number + small label
- Used only on dashboard

### Sidebar Status Footer
Two small rows at the bottom of the sidebar:
- `● Streaming` — green if active, red if down
- `● Ollama` — green if reachable, red if not
- Data from `GET /api/v1/status` polled every 30s

---

## Pages Affected

| Page | Changes |
|---|---|
| `layout.tsx` | Full sidebar redesign — active state, status footer, cyan branding |
| `app/page.tsx` | Two-column grid, StatCards, AnomalyChart, redesigned live feed |
| `app/anomalies/page.tsx` | Replace current cards with AnomalyCard component |
| `app/summaries/page.tsx` | Restyled cards matching surface/border tokens |
| `app/alerts/page.tsx` | Restyled with new palette |
| `app/chat/ChatClient.tsx` | Dark chat bubbles, cyan send button |
| `app/settings/SettingsClient.tsx` | Dark inputs, cyan save button |
| `globals.css` | CSS variable overrides for full palette |
| `components/LiveFeed.tsx` | Use AnomalyCard, remove old Badge style |

---

## New Files

| File | Purpose |
|---|---|
| `components/AnomalyCard.tsx` | Reusable severity card component |
| `components/AnomalyChart.tsx` | Recharts dual line chart |
| `components/StatCard.tsx` | Single metric card with colored left border |
| `components/SidebarStatus.tsx` | Streaming + Ollama status footer |

---

## Out of Scope

- Mobile/responsive layout (desktop-first for now)
- Light mode toggle
- Animation/transitions beyond Tailwind defaults
- Chart time-range picker (static 24h window for now)
