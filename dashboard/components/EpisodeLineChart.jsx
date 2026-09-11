"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";

export default function EpisodeLineChart({ data, lines, height = 260 }) {
  return (
    <div className="border border-ink bg-panel p-4">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#e9e9e0" vertical={false} />
          <XAxis
            dataKey="episode"
            tick={{ fill: "#61635a", fontSize: 11, fontFamily: "ui-monospace, monospace" }}
            axisLine={{ stroke: "#181a16" }}
            tickLine={false}
            label={{ value: "episode", position: "insideBottom", offset: -4, fill: "#61635a", fontSize: 11 }}
          />
          <YAxis
            tick={{ fill: "#61635a", fontSize: 11, fontFamily: "ui-monospace, monospace" }}
            axisLine={{ stroke: "#181a16" }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "#fbfbf8",
              border: "1px solid #181a16",
              borderRadius: 0,
              fontSize: 12,
              fontFamily: "ui-monospace, monospace",
            }}
            labelStyle={{ color: "#181a16" }}
          />
          {lines.length > 1 && (
            <Legend
              wrapperStyle={{ fontSize: 12, fontFamily: "ui-monospace, monospace" }}
            />
          )}
          {lines.map((l) => (
            <Line
              key={l.dataKey}
              type="monotone"
              dataKey={l.dataKey}
              stroke={l.color}
              strokeWidth={1.75}
              dot={{ r: 3, fill: l.color, strokeWidth: 0 }}
              name={l.name}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
