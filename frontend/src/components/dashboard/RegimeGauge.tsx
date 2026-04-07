"use client";

import { useLiveSignal } from "@/hooks/useLiveSignal";
import { RegimeBadge, Spinner } from "@/components/ui";

const RADIUS = 70;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function Arc({
  value,
  color,
  offset,
  total,
}: {
  value: number;
  color: string;
  offset: number;
  total: number;
}) {
  const dash = (value / total) * CIRCUMFERENCE;
  const gap = CIRCUMFERENCE - dash;
  const rotation = (offset / total) * 360 - 90;

  return (
    <circle
      cx="90"
      cy="90"
      r={RADIUS}
      fill="none"
      stroke={color}
      strokeWidth="14"
      strokeDasharray={`${dash} ${gap}`}
      strokeLinecap="butt"
      transform={`rotate(${rotation} 90 90)`}
      style={{ transition: "stroke-dasharray 0.8s ease" }}
    />
  );
}

export function RegimeGauge() {
  const { signal, connected } = useLiveSignal();

  const probs = signal?.probabilities ?? {
    risk_on: 0.33,
    transition: 0.34,
    risk_off: 0.33,
  };

  const total = Object.values(probs).reduce((a, b) => a + b, 0) || 1;
  const ro = (probs.risk_on ?? 0) / total;
  const tr = (probs.transition ?? 0) / total;
  const rf = (probs.risk_off ?? 0) / total;

  const regime = signal?.regime ?? "transition";
  const confidence = signal?.confidence ?? 0;

  const dominantColor =
    regime === "risk_on"
      ? "var(--color-risk-on)"
      : regime === "risk_off"
      ? "var(--color-risk-off)"
      : "var(--color-transition)";

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        <svg width="180" height="180" viewBox="0 0 180 180">
          <circle
            cx="90" cy="90" r={RADIUS}
            fill="none"
            stroke="#27272a"
            strokeWidth="14"
          />
          <Arc value={ro} color="var(--color-risk-on)" offset={0} total={1} />
          <Arc value={tr} color="var(--color-transition)" offset={ro} total={1} />
          <Arc value={rf} color="var(--color-risk-off)" offset={ro + tr} total={1} />

          <text
            x="90" y="84"
            textAnchor="middle"
            fill={dominantColor}
            fontSize="11"
            fontFamily="var(--font-jetbrains), monospace"
            fontWeight="500"
            letterSpacing="0.08em"
          >
            {regime.replace("_", " ").toUpperCase()}
          </text>
          <text
            x="90" y="104"
            textAnchor="middle"
            fill="#a1a1aa"
            fontSize="22"
            fontFamily="var(--font-jetbrains), monospace"
            fontWeight="500"
          >
            {(confidence * 100).toFixed(0)}%
          </text>
          <text
            x="90" y="120"
            textAnchor="middle"
            fill="#71717a"
            fontSize="10"
            fontFamily="var(--font-jetbrains), monospace"
          >
            confidence
          </text>
        </svg>

        <div
          className="absolute top-1 right-1 w-2 h-2 rounded-full"
          style={{
            background: connected ? "var(--color-risk-on)" : "#71717a",
            boxShadow: connected ? "0 0 6px var(--color-risk-on)" : "none",
          }}
          title={connected ? "Live" : "Disconnected"}
        />
      </div>

      <div className="w-full space-y-2">
        {([
          ["risk_on", ro, "var(--color-risk-on)", "Risk On"],
          ["transition", tr, "var(--color-transition)", "Transition"],
          ["risk_off", rf, "var(--color-risk-off)", "Risk Off"],
        ] as const).map(([key, val, color, label]) => (
          <div key={key} className="flex items-center gap-2">
            <span className="text-xs text-zinc-400 w-20 font-mono">{label}</span>
            <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(val * 100).toFixed(1)}%`,
                  background: color,
                  transition: "width 0.8s ease",
                }}
              />
            </div>
            <span className="text-xs font-mono text-zinc-400 w-10 text-right">
              {(val * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <RegimeBadge regime={regime} />
        {!connected && (
          <span className="text-xs text-zinc-600 font-mono">disconnected</span>
        )}
        {connected && (
          <span className="text-xs text-zinc-600 font-mono">
            {signal?.date ?? "—"}
          </span>
        )}
      </div>
    </div>
  );
}
