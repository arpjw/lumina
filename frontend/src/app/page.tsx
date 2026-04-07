"use client";

import { useState } from "react";
import { RegimeGauge } from "@/components/dashboard/RegimeGauge";
import { SentimentChart } from "@/components/dashboard/SentimentChart";
import { GeopoliticalChart, TopicBars } from "@/components/dashboard/Charts";
import { BacktestPanel } from "@/components/notebook/BacktestPanel";
import { ShapChart, ConfusionMatrix } from "@/components/inspector";
import { Card } from "@/components/ui";
import { useLiveSignal } from "@/hooks/useLiveSignal";

type View = "dashboard" | "notebook" | "inspector";

const NAV_ITEMS: { id: View; label: string; icon: string }[] = [
  { id: "dashboard", label: "Signal Dashboard", icon: "◈" },
  { id: "notebook", label: "Research Notebook", icon: "⌘" },
  { id: "inspector", label: "Model Inspector", icon: "◉" },
];

function Sidebar({
  view,
  onSelect,
  connected,
}: {
  view: View;
  onSelect: (v: View) => void;
  connected: boolean;
}) {
  return (
    <aside className="w-52 shrink-0 border-r border-zinc-800 flex flex-col h-screen sticky top-0">
      <div className="px-5 py-5 border-b border-zinc-800">
        <p className="text-xs font-mono font-semibold text-amber-400 tracking-widest uppercase">
          Lumina
        </p>
        <p className="text-xs text-zinc-600 font-mono mt-0.5">alt data research</p>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-mono transition-colors text-left ${
              view === item.id
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900"
            }`}
          >
            <span className="text-base leading-none opacity-70">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-zinc-800 space-y-2">
        <div className="flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: connected ? "var(--color-risk-on)" : "#52525b",
              boxShadow: connected ? "0 0 4px var(--color-risk-on)" : "none",
            }}
          />
          <span className="text-xs font-mono text-zinc-600">
            {connected ? "live stream" : "connecting..."}
          </span>
        </div>
        <p className="text-xs text-zinc-700 font-mono">
          Polaris Research Group
        </p>
      </div>
    </aside>
  );
}

function DashboardView() {
  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-3">
        <Card title="Macro Regime" subtitle="Live signal via WebSocket">
          <RegimeGauge />
        </Card>
      </div>

      <div className="col-span-9 space-y-4">
        <Card title="Cross-source sentiment" subtitle="FinBERT composite score · 60-day window">
          <SentimentChart days={60} />
        </Card>

        <div className="grid grid-cols-2 gap-4">
          <Card title="Geopolitical risk" subtitle="GDELT Goldstein scale · conflict ratio">
            <GeopoliticalChart days={60} />
          </Card>
          <Card title="Dominant macro topics" subtitle="BERTopic daily counts">
            <TopicBars />
          </Card>
        </div>
      </div>

      <div className="col-span-12">
        <Card title="Source activity" subtitle="Ingested records by source · last 30 days">
          <SourceGrid />
        </Card>
      </div>
    </div>
  );
}

function SourceGrid() {
  const sources = [
    { name: "reddit", color: "#f97316", desc: "r/investing · r/MacroEconomics · r/wallstreetbets" },
    { name: "gdelt", color: "#38bdf8", desc: "Global news event stream · CAMEO codes" },
    { name: "edgar", color: "#a78bfa", desc: "SEC 8-K · 10-K filings" },
    { name: "fred", color: "#34d399", desc: "40+ macro indicator series" },
    { name: "wikipedia", color: "#fbbf24", desc: "Breaking event stream · edit delta" },
  ];

  return (
    <div className="grid grid-cols-5 gap-3">
      {sources.map((s) => (
        <div key={s.name} className="bg-zinc-900 rounded p-3 border border-zinc-800">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: s.color }} />
            <span className="text-xs font-mono font-semibold text-zinc-200">{s.name}</span>
          </div>
          <p className="text-xs text-zinc-600 font-mono leading-relaxed">{s.desc}</p>
        </div>
      ))}
    </div>
  );
}

function NotebookView() {
  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-sm font-mono font-semibold text-zinc-200 mb-1">Signal backtest</h2>
        <p className="text-xs text-zinc-500 font-mono">
          Run a long/short strategy on any signal layer with configurable entry/exit thresholds.
          Equity curve, Sharpe, max drawdown, and Calmar ratio computed in-process.
        </p>
      </div>
      <Card>
        <BacktestPanel />
      </Card>

      <Card title="Pipeline architecture" subtitle="Signal fusion flow">
        <div className="space-y-3 text-xs font-mono text-zinc-400 leading-relaxed">
          <div className="flex items-start gap-3">
            <span className="text-amber-500 shrink-0">01</span>
            <div>
              <span className="text-zinc-200">FinBERT sentiment layer</span>
              <span className="text-zinc-600 ml-2">— ProsusAI/finbert, batch=32, max_length=512</span>
              <p className="text-zinc-600 mt-0.5">Cross-source daily composite score. Weighted by source reliability and recency.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-amber-500 shrink-0">02</span>
            <div>
              <span className="text-zinc-200">BERTopic topic layer</span>
              <span className="text-zinc-600 ml-2">— all-MiniLM-L6-v2 embeddings, nr_topics=auto</span>
              <p className="text-zinc-600 mt-0.5">Dominant macro theme identification. 8 labeled categories mapped via CAMEO keyword matching.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-amber-500 shrink-0">03</span>
            <div>
              <span className="text-zinc-200">GDELT geopolitical layer</span>
              <span className="text-zinc-600 ml-2">— Goldstein scale → conflict/cooperation scalar</span>
              <p className="text-zinc-600 mt-0.5">Geopolitical risk score = -0.6 × mean_goldstein + 0.4 × conflict_ratio. Range [-1, 1].</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-amber-500 shrink-0">04</span>
            <div>
              <span className="text-zinc-200">XGBoost regime classifier</span>
              <span className="text-zinc-600 ml-2">— 3-fold TimeSeriesSplit CV, MLflow tracking</span>
              <p className="text-zinc-600 mt-0.5">Fuses all three layers into &#123;risk_on, transition, risk_off&#125; daily label. VIX-based ground truth labeling.</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function InspectorView() {
  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-sm font-mono font-semibold text-zinc-200 mb-1">Model inspector</h2>
        <p className="text-xs text-zinc-500 font-mono">
          SHAP feature attribution and cross-validated confusion matrix for the XGBoost regime classifier.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card title="Feature importance" subtitle="Mean |SHAP| — XGBoost regime classifier">
          <ShapChart />
        </Card>
        <Card title="Confusion matrix" subtitle="3-fold time-series CV · actual vs predicted">
          <ConfusionMatrix />
        </Card>
      </div>

      <Card title="Model config" subtitle="Hyperparameters and training setup">
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs font-mono">
          {[
            ["Model", "XGBClassifier"],
            ["n_estimators", "200"],
            ["max_depth", "4"],
            ["learning_rate", "0.05"],
            ["subsample", "0.8"],
            ["colsample_bytree", "0.8"],
            ["eval_metric", "mlogloss"],
            ["CV strategy", "TimeSeriesSplit(n_splits=3)"],
            ["Label source", "VIX-based (VIXCLS < 15 = risk_on)"],
            ["Explainability", "SHAP TreeExplainer"],
            ["Tracking", "MLflow (port 5001)"],
            ["Artifact store", "models/registry/"],
          ].map(([k, v]) => (
            <div key={k} className="flex gap-2 py-1 border-b border-zinc-800">
              <span className="text-zinc-600 w-36 shrink-0">{k}</span>
              <span className="text-zinc-300">{v}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default function Page() {
  const [view, setView] = useState<View>("dashboard");
  const { connected } = useLiveSignal();

  return (
    <div className="flex min-h-screen">
      <Sidebar view={view} onSelect={setView} connected={connected} />
      <main className="flex-1 overflow-auto">
        <header className="border-b border-zinc-800 px-8 py-4 flex items-center justify-between sticky top-0 bg-zinc-950/90 backdrop-blur-sm z-10">
          <div>
            <h1 className="text-sm font-mono font-semibold text-zinc-200">
              {NAV_ITEMS.find((n) => n.id === view)?.label}
            </h1>
            <p className="text-xs text-zinc-600 font-mono mt-0.5">
              lumina · alternative data signal research platform
            </p>
          </div>
          <a
            href="http://localhost:5001"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-mono text-zinc-500 hover:text-amber-400 transition-colors border border-zinc-800 rounded px-3 py-1.5"
          >
            MLflow UI →
          </a>
        </header>

        <div className="p-8">
          {view === "dashboard" && <DashboardView />}
          {view === "notebook" && <NotebookView />}
          {view === "inspector" && <InspectorView />}
        </div>
      </main>
    </div>
  );
}
