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

export interface ChartPoint {
  hour: string;
  errors: number;
  anomalies: number;
}

export default function AnomalyChart({ data }: { data: ChartPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="gErrors" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gAnomalies" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis
          dataKey="hour"
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
          contentStyle={{
            background: "#111827",
            border: "1px solid #1f2937",
            borderRadius: 6,
            fontSize: 12,
          }}
          labelStyle={{ color: "#9ca3af", marginBottom: 4 }}
          itemStyle={{ color: "#f3f4f6", padding: "1px 0" }}
          cursor={{ stroke: "#374151", strokeWidth: 1 }}
        />
        <Area
          type="monotone"
          dataKey="anomalies"
          stroke="#22d3ee"
          strokeWidth={1.5}
          fill="url(#gAnomalies)"
          dot={false}
          name="Anomalies"
        />
        <Area
          type="monotone"
          dataKey="errors"
          stroke="#ef4444"
          strokeWidth={1.5}
          fill="url(#gErrors)"
          dot={false}
          name="Errors"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
