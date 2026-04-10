"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

interface RollingICRow {
  date: string;
  ticker: string;
  rolling_ic: number;
}

const TICKER_COLORS: Record<string, string> = {
  SPY: "#f59e0b",   // amber
  TLT: "#3b82f6",   // blue
  GLD: "#22c55e",   // green
  "DX-Y.NYB": "#a1a1aa", // zinc
};

export function ICChart({ data }: { data: RollingICRow[] }) {
  if (!data.length) {
    return <p className="text-xs text-zinc-600 font-mono">No rolling IC data available.</p>;
  }

  // Pivot: one row per date, columns = ticker rolling_ic values
  const dateMap = new Map<string, Record<string, number | string>>();
  for (const row of data) {
    if (!dateMap.has(row.date)) {
      dateMap.set(row.date, { date: row.date });
    }
    dateMap.get(row.date)![row.ticker] = row.rolling_ic;
  }
  const chartData = Array.from(dateMap.values()).sort(
    (a, b) => String(a.date).localeCompare(String(b.date))
  );

  const tickers = Array.from(new Set(data.map((d) => d.ticker)));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#71717a", fontFamily: "var(--font-jetbrains)" }}
          tickFormatter={(v: string) => v.slice(5, 10)}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#71717a", fontFamily: "var(--font-jetbrains)" }}
          domain={[-0.4, 0.4]}
          tickFormatter={(v: number) => v.toFixed(2)}
        />
        <Tooltip
          contentStyle={{
            background: "#18181b",
            border: "1px solid #27272a",
            borderRadius: 6,
            fontSize: 11,
            fontFamily: "var(--font-jetbrains)",
          }}
          labelStyle={{ color: "#a1a1aa" }}
        />
        <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="4 4" />
        {tickers.map((t) => (
          <Line
            key={t}
            type="monotone"
            dataKey={t}
            stroke={TICKER_COLORS[t] ?? "#71717a"}
            dot={false}
            strokeWidth={1.5}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
