"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { StatsDaily } from "@/lib/types";

export default function DailyActivityChart({ data }: { data: StatsDaily[] }) {
  const formatted = data.map((d) => ({ ...d, date: d.date.slice(5) })); // "YYYY-MM-DD" → "MM-DD"
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={formatted} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="gSummaries" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gAnomalies" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gAlerts" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#fb7185" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#fb7185" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis
          dataKey="date"
          stroke="transparent"
          tick={{ fill: "#4b5563", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="transparent"
          tick={{ fill: "#4b5563", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: "#9ca3af", marginBottom: 4 }}
          itemStyle={{ color: "#f3f4f6", padding: "1px 0" }}
          cursor={{ stroke: "#374151", strokeWidth: 1 }}
        />
        <Area type="monotone" dataKey="summaries" stroke="#22d3ee" strokeWidth={1.5} fill="url(#gSummaries)" dot={false} name="Summaries" />
        <Area type="monotone" dataKey="anomalies" stroke="#fbbf24" strokeWidth={1.5} fill="url(#gAnomalies)" dot={false} name="Anomalies" />
        <Area type="monotone" dataKey="alerts" stroke="#fb7185" strokeWidth={1.5} fill="url(#gAlerts)" dot={false} name="Alerts" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
