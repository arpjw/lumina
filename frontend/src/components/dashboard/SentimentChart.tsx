"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useFetch } from "@/hooks/useFetch";
import type { DailySentiment } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { format, parseISO } from "date-fns";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const v = payload[0]?.value as number;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs font-mono">
      <p className="text-zinc-400 mb-1">{label}</p>
      <p style={{ color: v >= 0 ? "var(--color-risk-on)" : "var(--color-risk-off)" }}>
        composite: {v?.toFixed(4)}
      </p>
      {payload[1] && (
        <p className="text-emerald-400">positive: {payload[1]?.value?.toFixed(4)}</p>
      )}
      {payload[2] && (
        <p className="text-red-400">negative: {payload[2]?.value?.toFixed(4)}</p>
      )}
    </div>
  );
}

export function SentimentChart({ days = 60 }: { days?: number }) {
  const { data, isLoading } = useFetch<DailySentiment[]>(
    `${BASE}/sentiment/daily?days=${days}`
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40">
        <Spinner size={20} />
      </div>
    );
  }

  const sorted = [...(data ?? [])].reverse().map((d) => ({
    ...d,
    dateLabel: (() => {
      try { return format(parseISO(d.date), "MMM d"); } catch { return d.date; }
    })(),
  }));

  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={sorted} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <defs>
          <linearGradient id="sentPos" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#34d399" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#34d399" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="sentNeg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f87171" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#f87171" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="dateLabel"
          tick={{ fill: "#52525b", fontSize: 10, fontFamily: "var(--font-jetbrains)" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: "#52525b", fontSize: 10, fontFamily: "var(--font-jetbrains)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => v.toFixed(2)}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
        <Area
          type="monotone"
          dataKey="cross_composite"
          stroke="#fbbf24"
          strokeWidth={1.5}
          fill="url(#sentPos)"
          dot={false}
          activeDot={{ r: 3, fill: "#fbbf24" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
