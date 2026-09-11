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

const COLORS = ["#5b6779", "#818cf8", "#4dd9c4", "#f5a623", "#4dd9c4", "#5b6779"];

export default function MethodBarChart({ data, dataKey, unit = "", height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke="#1c2530" vertical={false} />
        <XAxis
          dataKey="method"
          tick={{ fill: "#8b93a7", fontSize: 11 }}
          axisLine={{ stroke: "#232834" }}
          tickLine={false}
          interval={0}
          angle={-18}
          textAnchor="end"
          height={70}
        />
        <YAxis
          tick={{ fill: "#8b93a7", fontSize: 11 }}
          axisLine={{ stroke: "#232834" }}
          tickLine={false}
          unit={unit}
        />
        <Tooltip
          contentStyle={{
            background: "#12151c",
            border: "1px solid #232834",
            borderRadius: 0,
            fontSize: 12,
          }}
          labelStyle={{ color: "#e6eaf0" }}
          itemStyle={{ color: "#4dd9c4" }}
          cursor={{ fill: "#171b24" }}
        />
        <Bar dataKey={dataKey} radius={[2, 2, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
