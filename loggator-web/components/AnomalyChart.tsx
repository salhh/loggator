"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

export interface ChartPoint {
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
          contentStyle={{
            background: "#1f2937",
            border: "1px solid #374151",
            borderRadius: 6,
          }}
          labelStyle={{ color: "#f9fafb" }}
          itemStyle={{ color: "#f9fafb" }}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: "#6b7280" }} />
        <Line
          type="monotone"
          dataKey="errors"
          stroke="#ef4444"
          strokeWidth={1.5}
          dot={false}
          name="Errors"
        />
        <Line
          type="monotone"
          dataKey="anomalies"
          stroke="#22d3ee"
          strokeWidth={1.5}
          dot={false}
          name="Anomalies"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
