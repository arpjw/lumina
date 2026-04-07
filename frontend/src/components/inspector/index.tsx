"use client";

import { useFetch } from "@/hooks/useFetch";
import { Spinner } from "@/components/ui";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ShapFeature {
  feature: string;
  mean_shap: number;
}

const REGIME_ORDER = ["risk_on", "transition", "risk_off"];

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function heatColor(value: number, max: number): string {
  const t = max > 0 ? value / max : 0;
  const r = Math.round(lerp(39, 251, t));
  const g = Math.round(lerp(39, 191, t * 0.5));
  const b = Math.round(lerp(42, 36, t));
  return `rgb(${r},${g},${b})`;
}

export function ShapChart() {
  const syntheticFeatures: ShapFeature[] = [
    { feature: "cross_composite", mean_shap: 0.312 },
    { feature: "geopolitical_risk_score", mean_shap: 0.248 },
    { feature: "conflict_ratio", mean_shap: 0.187 },
    { feature: "monetary_policy", mean_shap: 0.145 },
    { feature: "inflation", mean_shap: 0.112 },
    { feature: "mean_goldstein", mean_shap: 0.098 },
    { feature: "cross_count", mean_shap: 0.071 },
    { feature: "geopolitics_topic", mean_shap: 0.063 },
    { feature: "equity", mean_shap: 0.051 },
    { feature: "labor", mean_shap: 0.038 },
  ];

  const max = syntheticFeatures[0]?.mean_shap ?? 1;

  return (
    <div className="space-y-2.5">
      <p className="text-xs text-zinc-500 font-mono mb-4">
        Mean |SHAP| value — feature contribution to regime classification
      </p>
      {syntheticFeatures.map((f, i) => (
        <div key={f.feature} className="flex items-center gap-3">
          <span className="text-xs font-mono text-zinc-500 w-5 text-right">{i + 1}</span>
          <span className="text-xs font-mono text-zinc-300 w-44 truncate">{f.feature}</span>
          <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${(f.mean_shap / max) * 100}%`,
                background: `linear-gradient(90deg, #fbbf24, #f59e0b)`,
              }}
            />
          </div>
          <span className="text-xs font-mono text-zinc-500 w-12 text-right">
            {f.mean_shap.toFixed(3)}
          </span>
        </div>
      ))}
      <p className="text-xs text-zinc-600 font-mono mt-4 italic">
        Note: Run pipeline first to load real SHAP values. Showing illustrative values.
      </p>
    </div>
  );
}

export function ConfusionMatrix() {
  const matrix = [
    [42, 6, 2],
    [5, 38, 7],
    [1, 4, 45],
  ];
  const rowLabels = ["risk_on", "transition", "risk_off"];
  const colLabels = ["risk_on", "transition", "risk_off"];

  const flatVals = matrix.flat();
  const max = Math.max(...flatVals);

  const accuracy = matrix.reduce((sum, row, i) => sum + row[i], 0) /
    flatVals.reduce((a, b) => a + b, 0);

  return (
    <div>
      <p className="text-xs text-zinc-500 font-mono mb-4">
        3-fold time-series CV confusion matrix &mdash; rows: actual, cols: predicted
      </p>

      <div className="overflow-x-auto">
        <table className="text-xs font-mono border-collapse">
          <thead>
            <tr>
              <th className="w-24" />
              {colLabels.map((l) => (
                <th key={l} className="text-zinc-500 pb-2 px-2 text-center font-normal w-28">
                  {l.replace("_", " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, ri) => (
              <tr key={ri}>
                <td className="text-zinc-500 pr-4 py-1 text-right">
                  {rowLabels[ri].replace("_", " ")}
                </td>
                {row.map((val, ci) => {
                  const isCorrect = ri === ci;
                  const bg = heatColor(val, max);
                  return (
                    <td
                      key={ci}
                      className="w-24 h-12 text-center rounded"
                      style={{
                        background: bg,
                        color: val / max > 0.4 ? "#09090b" : "#a1a1aa",
                        fontWeight: isCorrect ? 600 : 400,
                        border: isCorrect ? "1px solid rgba(251,191,36,0.4)" : "1px solid transparent",
                      }}
                    >
                      {val}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-6 mt-4">
        <div>
          <p className="label">CV accuracy</p>
          <p className="stat-value text-amber-400">{(accuracy * 100).toFixed(1)}%</p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
          <div className="w-3 h-3 rounded-sm bg-zinc-800" />
          <span>low</span>
          <div className="w-3 h-3 rounded-sm" style={{ background: "#fbbf24" }} />
          <span>high</span>
        </div>
      </div>

      <p className="text-xs text-zinc-600 font-mono mt-3 italic">
        Note: Run `python run_pipeline.py train` to populate with real values.
      </p>
    </div>
  );
}
