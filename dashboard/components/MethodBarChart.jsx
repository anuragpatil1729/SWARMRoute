"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from "recharts";

const COLORS = ["#61635a", "#181a16", "#181a16", "#2e6b34", "#3d5566", "#61635a"];

export default function MethodBarChart({ data, dataKey, unit = "", height = 260 }) {
  return (
    <div className="border border-ink bg-panel p-4">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#e9e9e0" vertical={false} />
          <XAxis
            dataKey="method"
            tick={{ fill: "#61635a", fontSize: 11, fontFamily: "ui-monospace, monospace" }}
            axisLine={{ stroke: "#181a16" }}
            tickLine={false}
            interval={0}
            angle={-18}
            textAnchor="end"
            height={70}
          />
          <YAxis
            tick={{ fill: "#61635a", fontSize: 11, fontFamily: "ui-monospace, monospace" }}
            axisLine={{ stroke: "#181a16" }}
            tickLine={false}
            unit={unit}
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
            itemStyle={{ color: "#181a16" }}
            cursor={{ fill: "#e9e9e0" }}
          />
          <Bar dataKey={dataKey}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
