"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  BarChart,
  Bar,
  Cell,
  LabelList,
} from "recharts";
import { useFetch } from "@/hooks/useFetch";
import type { GeopoliticalDay, TopicSummary } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { format, parseISO } from "date-fns";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function GeoTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-xs font-mono">
      <p className="text-zinc-400 mb-1">{label}</p>
      <p className="text-amber-400">
        risk score: {payload[0]?.value?.toFixed(3)}
      </p>
      <p className="text-zinc-400">
        goldstein: {payload[1]?.value?.toFixed(3)}
      </p>
    </div>
  );
}

export function GeopoliticalChart({ days = 60 }: { days?: number }) {
  const { data, isLoading } = useFetch<GeopoliticalDay[]>(
    `${BASE}/geopolitical/daily?days=${days}`
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
    <ResponsiveContainer width="100%" height={160}>
      <LineChart data={sorted} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
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
          domain={[-1, 1]}
        />
        <Tooltip content={<GeoTooltip />} />
        <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
        <Line
          type="monotone"
          dataKey="geopolitical_risk_score"
          stroke="#f87171"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, fill: "#f87171" }}
        />
        <Line
          type="monotone"
          dataKey="mean_goldstein"
          stroke="#71717a"
          strokeWidth={1}
          dot={false}
          strokeDasharray="3 3"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

const TOPIC_COLORS: Record<string, string> = {
  monetary_policy: "#fbbf24",
  inflation: "#fb923c",
  geopolitics: "#f87171",
  equity: "#34d399",
  recession: "#f87171",
  credit: "#a78bfa",
  labor: "#38bdf8",
  energy: "#facc15",
  other: "#52525b",
};

export function TopicBars() {
  const { data, isLoading } = useFetch<TopicSummary>(`${BASE}/topics/summary`);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Spinner size={20} />
      </div>
    );
  }

  const topics = data?.dominant_topics ?? {};
  const entries = Object.entries(topics)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, count]) => ({ name, count }));

  const max = Math.max(...entries.map((e) => e.count), 1);

  return (
    <div className="space-y-2">
      {entries.map(({ name, count }) => (
        <div key={name} className="flex items-center gap-3">
          <span className="text-xs font-mono text-zinc-400 w-28 truncate">{name.replace("_", " ")}</span>
          <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${(count / max) * 100}%`,
                background: TOPIC_COLORS[name] ?? TOPIC_COLORS.other,
              }}
            />
          </div>
          <span className="text-xs font-mono text-zinc-500 w-8 text-right">{count}</span>
        </div>
      ))}
    </div>
  );
}
