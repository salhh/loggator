"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { StatsLogVolume } from "@/lib/types";

export default function LogVolumeChart({ data }: { data: StatsLogVolume[] }) {
  const formatted = data.map((d) => ({ ...d, date: d.date.slice(5) })); // "YYYY-MM-DD" → "MM-DD"
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={formatted} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
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
          cursor={{ fill: "#1f2937" }}
        />
        <Bar dataKey="error" stackId="a" fill="#f87171" name="Error" />
        <Bar dataKey="warn" stackId="a" fill="#fbbf24" name="Warn" />
        <Bar dataKey="info" stackId="a" fill="#94a3b8" name="Info" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
