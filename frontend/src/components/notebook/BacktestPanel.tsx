"use client";

import { useState } from "react";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { api, type BacktestRequest, type BacktestResult } from "@/lib/api";
import { Card, StatBlock, Spinner, RegimeBadge } from "@/components/ui";

const DEFAULTS: BacktestRequest = {
  signal_source: "composite",
  lookback_days: 252,
  entry_threshold: 0.2,
  exit_threshold: -0.1,
  direction: "long",
  fees: 0.001,
};

function TearsheetStats({ result }: { result: BacktestResult }) {
  const stats = [
    { label: "Total Return", value: `${(result.total_return * 100).toFixed(2)}%`, color: result.total_return >= 0 ? "var(--color-risk-on)" : "var(--color-risk-off)" },
    { label: "Ann. Return", value: `${(result.annualized_return * 100).toFixed(2)}%`, color: result.annualized_return >= 0 ? "var(--color-risk-on)" : "var(--color-risk-off)" },
    { label: "Sharpe", value: result.sharpe_ratio.toFixed(2), color: result.sharpe_ratio >= 1 ? "var(--color-risk-on)" : result.sharpe_ratio >= 0 ? "var(--color-transition)" : "var(--color-risk-off)" },
    { label: "Max DD", value: `${(result.max_drawdown * 100).toFixed(2)}%`, color: "var(--color-risk-off)" },
    { label: "Win Rate", value: `${(result.win_rate * 100).toFixed(1)}%` },
    { label: "Calmar", value: result.calmar_ratio.toFixed(2) },
    { label: "Sortino", value: result.sortino_ratio.toFixed(2) },
    { label: "Trades", value: result.n_trades.toString() },
  ];

  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      {stats.map((s) => (
        <StatBlock key={s.label} label={s.label} value={s.value} color={s.color} />
      ))}
    </div>
  );
}

export function BacktestPanel() {
  const [form, setForm] = useState<BacktestRequest>(DEFAULTS);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runBacktest() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.backtest.run(form);
      setResult(res);
    } catch (e: any) {
      setError(e.message ?? "Backtest failed");
    } finally {
      setLoading(false);
    }
  }

  const inputCls = "w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-amber-500 transition-colors";
  const labelCls = "text-xs font-mono text-zinc-500 mb-1 block uppercase tracking-wider";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className={labelCls}>Signal source</label>
          <select
            className={inputCls}
            value={form.signal_source}
            onChange={(e) => setForm((f) => ({ ...f, signal_source: e.target.value as any }))}
          >
            <option value="composite">Composite</option>
            <option value="sentiment">Sentiment</option>
            <option value="geopolitical">Geopolitical</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Lookback (days)</label>
          <input
            type="number"
            className={inputCls}
            value={form.lookback_days}
            min={30}
            max={1260}
            onChange={(e) => setForm((f) => ({ ...f, lookback_days: parseInt(e.target.value) }))}
          />
        </div>
        <div>
          <label className={labelCls}>Direction</label>
          <select
            className={inputCls}
            value={form.direction}
            onChange={(e) => setForm((f) => ({ ...f, direction: e.target.value as any }))}
          >
            <option value="long">Long</option>
            <option value="short">Short</option>
            <option value="both">Both</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Entry threshold</label>
          <input
            type="number"
            className={inputCls}
            value={form.entry_threshold}
            step={0.05}
            min={-1}
            max={1}
            onChange={(e) => setForm((f) => ({ ...f, entry_threshold: parseFloat(e.target.value) }))}
          />
        </div>
        <div>
          <label className={labelCls}>Exit threshold</label>
          <input
            type="number"
            className={inputCls}
            value={form.exit_threshold}
            step={0.05}
            min={-1}
            max={1}
            onChange={(e) => setForm((f) => ({ ...f, exit_threshold: parseFloat(e.target.value) }))}
          />
        </div>
        <div>
          <label className={labelCls}>Fees (bps)</label>
          <input
            type="number"
            className={inputCls}
            value={form.fees * 10000}
            step={1}
            min={0}
            max={100}
            onChange={(e) => setForm((f) => ({ ...f, fees: parseFloat(e.target.value) / 10000 }))}
          />
        </div>
      </div>

      <button
        onClick={runBacktest}
        disabled={loading}
        className="flex items-center gap-2 px-5 py-2 bg-amber-500 text-zinc-950 rounded text-sm font-mono font-semibold hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading && <Spinner size={14} />}
        {loading ? "Running..." : "Run Backtest"}
      </button>

      {error && (
        <p className="text-red-400 text-xs font-mono border border-red-900 bg-red-950/30 rounded px-3 py-2">
          {error}
        </p>
      )}

      {result && (
        <div className="space-y-6 animate-fade-in">
          <TearsheetStats result={result} />

          <div>
            <p className="label mb-3">Equity curve</p>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={result.equity_curve} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: "#52525b", fontSize: 10, fontFamily: "var(--font-jetbrains)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fill: "#52525b", fontSize: 10, fontFamily: "var(--font-jetbrains)" }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 6, fontFamily: "var(--font-jetbrains)", fontSize: 11 }} />
                <ReferenceLine y={1} stroke="#3f3f46" strokeDasharray="3 3" />
                <Area type="monotone" dataKey="value" stroke="#fbbf24" strokeWidth={1.5} fill="url(#eqGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div>
            <p className="label mb-3">Signal series</p>
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={result.signal_series} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <XAxis dataKey="date" tick={{ fill: "#52525b", fontSize: 10, fontFamily: "var(--font-jetbrains)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fill: "#52525b", fontSize: 10, fontFamily: "var(--font-jetbrains)" }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 6, fontFamily: "var(--font-jetbrains)", fontSize: 11 }} />
                <ReferenceLine y={form.entry_threshold} stroke="#34d399" strokeDasharray="2 2" strokeWidth={0.8} />
                <ReferenceLine y={form.exit_threshold} stroke="#f87171" strokeDasharray="2 2" strokeWidth={0.8} />
                <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="value" stroke="#a78bfa" strokeWidth={1.2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <p className="text-xs text-zinc-500 font-mono border-l-2 border-zinc-700 pl-3 italic">
            {result.summary}
          </p>
        </div>
      )}
    </div>
  );
}
