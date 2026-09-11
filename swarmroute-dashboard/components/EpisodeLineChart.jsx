"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

export default function EpisodeLineChart({ data, lines, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid stroke="#1c2530" vertical={false} />
        <XAxis
          dataKey="episode"
          tick={{ fill: "#8b93a7", fontSize: 11 }}
          axisLine={{ stroke: "#232834" }}
          tickLine={false}
          label={{ value: "episode", position: "insideBottom", offset: -4, fill: "#8b93a7", fontSize: 11 }}
        />
        <YAxis
          tick={{ fill: "#8b93a7", fontSize: 11 }}
          axisLine={{ stroke: "#232834" }}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "#12151c",
            border: "1px solid #232834",
            borderRadius: 0,
            fontSize: 12,
          }}
          labelStyle={{ color: "#e6eaf0" }}
        />
        {lines.map((l) => (
          <Line
            key={l.dataKey}
            type="monotone"
            dataKey={l.dataKey}
            stroke={l.color}
            strokeWidth={2}
            dot={{ r: 3, fill: l.color, strokeWidth: 0 }}
            name={l.name}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
