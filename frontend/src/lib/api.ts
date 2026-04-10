const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export interface RegimeSignal {
  date: string;
  regime: "risk_on" | "transition" | "risk_off";
  confidence: number;
  risk_on_prob: number;
  risk_off_prob: number;
  transition_prob: number;
}

export interface LatestSignal {
  date: string;
  regime: "risk_on" | "transition" | "risk_off";
  confidence: number;
  probabilities: Record<string, number>;
  source_counts: Record<string, number>;
}

export interface DailySentiment {
  date: string;
  cross_composite: number;
  cross_positive: number;
  cross_negative: number;
  cross_count: number;
}

export interface GeopoliticalDay {
  date: string;
  mean_goldstein: number;
  geopolitical_risk_score: number;
  conflict_ratio: number;
  total_events: number;
}

export interface TopicDay {
  date: string;
  [topic: string]: string | number;
}

export interface TopicSummary {
  dominant_topics: Record<string, number>;
}

export interface BacktestRequest {
  signal_source: "sentiment" | "geopolitical" | "composite";
  lookback_days: number;
  entry_threshold: number;
  exit_threshold: number;
  direction: "long" | "short" | "both";
  fees: number;
}

export interface BacktestResult {
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  n_trades: number;
  calmar_ratio: number;
  sortino_ratio: number;
  equity_curve: Array<{ date: string; value: number }>;
  signal_series: Array<{ date: string; value: number }>;
  summary: string;
}

export interface ShapFeature {
  feature: string;
  mean_shap: number;
}

/* ---------- synthetic fallback helpers ---------- */

function isoDate(daysAgo: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

// Deterministic pseudo-random based on seed (keeps data stable across renders)
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return s / 2147483647;
  };
}

function syntheticSignalHistory(days: number): RegimeSignal[] {
  const regimes: Array<"risk_on" | "transition" | "risk_off"> = [
    "risk_on",
    "transition",
    "risk_off",
  ];
  const rand = seededRandom(42);
  let regime = regimes[1]; // start at transition
  const out: RegimeSignal[] = [];
  for (let i = days - 1; i >= 0; i--) {
    if (rand() < 0.1) regime = regimes[Math.floor(rand() * 3)];
    const risk_on_prob = +(0.05 + rand() * 0.85).toFixed(3);
    const risk_off_prob = +(0.05 + rand() * (1 - risk_on_prob - 0.05)).toFixed(3);
    const transition_prob = +(1 - risk_on_prob - risk_off_prob).toFixed(3);
    out.push({
      date: isoDate(i),
      regime,
      confidence: +(0.55 + rand() * 0.37).toFixed(3),
      risk_on_prob,
      risk_off_prob,
      transition_prob,
    });
  }
  return out;
}

function syntheticLatest(): LatestSignal {
  return {
    date: isoDate(0),
    regime: "transition",
    confidence: 0.64,
    probabilities: { risk_on: 0.28, transition: 0.64, risk_off: 0.08 },
    source_counts: { reddit: 0, gdelt: 0, fred: 0, edgar: 0, wikipedia: 0 },
  };
}

function syntheticSentiment(days: number): DailySentiment[] {
  const rand = seededRandom(99);
  const out: DailySentiment[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const base = +((rand() - 0.5) * 0.3 + 0.05).toFixed(4);
    out.push({
      date: isoDate(i),
      cross_composite: base,
      cross_positive: +(0.35 + base * 0.3).toFixed(4),
      cross_negative: +(0.3 - base * 0.3).toFixed(4),
      cross_count: Math.floor(80 + rand() * 320),
    });
  }
  return out;
}

function syntheticGeo(days: number): GeopoliticalDay[] {
  const rand = seededRandom(77);
  let risk = 0.3;
  const out: GeopoliticalDay[] = [];
  for (let i = days - 1; i >= 0; i--) {
    risk = Math.max(-1, Math.min(1, risk + (rand() - 0.5) * 0.08));
    out.push({
      date: isoDate(i),
      mean_goldstein: +(-risk * 6 + (rand() - 0.5) * 1.0).toFixed(4),
      geopolitical_risk_score: +risk.toFixed(4),
      conflict_ratio: +Math.max(0, 0.3 + risk * 0.4 + (rand() - 0.5) * 0.1).toFixed(4),
      total_events: Math.floor(40 + rand() * 260),
    });
  }
  return out;
}

function syntheticTopics(days: number): TopicDay[] {
  const topics = [
    "inflation",
    "monetary_policy",
    "recession",
    "credit",
    "geopolitics",
    "labor",
    "energy",
    "equity",
  ];
  const rand = seededRandom(55);
  const out: TopicDay[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const row: TopicDay = { date: isoDate(i) };
    for (const t of topics) row[t] = Math.floor(rand() * 40);
    out.push(row);
  }
  return out;
}

function syntheticTopicSummary(): TopicSummary {
  return {
    dominant_topics: {
      monetary_policy: 342,
      inflation: 289,
      equity: 201,
      geopolitics: 178,
      recession: 134,
      credit: 98,
      labor: 87,
      energy: 62,
    },
  };
}

function syntheticBacktest(req: BacktestRequest): BacktestResult {
  const rand = seededRandom(123);
  const n = req.lookback_days || 90;
  let v = 0;
  const signal_series: Array<{ date: string; value: number }> = [];
  const equity_curve: Array<{ date: string; value: number }> = [];
  let equity = 100;
  for (let i = n - 1; i >= 0; i--) {
    v = v * 0.95 + (rand() - 0.5) * 0.16;
    signal_series.push({ date: isoDate(i), value: +v.toFixed(4) });
    const ret = v * 0.003 + (rand() - 0.5) * 0.02;
    equity *= 1 + ret;
    equity_curve.push({ date: isoDate(i), value: +equity.toFixed(2) });
  }
  return {
    total_return: +((equity / 100 - 1) * 100).toFixed(2),
    annualized_return: +(((equity / 100 - 1) / n) * 252 * 100).toFixed(2),
    sharpe_ratio: +(0.4 + rand() * 1.2).toFixed(2),
    max_drawdown: +(-0.02 - rand() * 0.08).toFixed(4),
    win_rate: +(0.48 + rand() * 0.12).toFixed(2),
    n_trades: Math.floor(10 + rand() * 30),
    calmar_ratio: +(0.5 + rand() * 2).toFixed(2),
    sortino_ratio: +(0.5 + rand() * 1.5).toFixed(2),
    equity_curve,
    signal_series,
    summary: "Synthetic backtest — no live backend connected.",
  };
}

/* ---------- public API with fallback ---------- */

export const api = {
  signals: {
    history: async (days = 90) => {
      try {
        return await get<RegimeSignal[]>(`/signals/history?days=${days}`);
      } catch {
        return syntheticSignalHistory(days);
      }
    },
    latest: async () => {
      try {
        return await get<LatestSignal>("/signals/latest");
      } catch {
        return syntheticLatest();
      }
    },
  },
  sentiment: {
    daily: async (days = 60) => {
      try {
        return await get<DailySentiment[]>(`/sentiment/daily?days=${days}`);
      } catch {
        return syntheticSentiment(days);
      }
    },
  },
  geopolitical: {
    daily: async (days = 60) => {
      try {
        return await get<GeopoliticalDay[]>(`/geopolitical/daily?days=${days}`);
      } catch {
        return syntheticGeo(days);
      }
    },
  },
  topics: {
    daily: async (days = 30) => {
      try {
        return await get<TopicDay[]>(`/topics/daily?days=${days}`);
      } catch {
        return syntheticTopics(days);
      }
    },
    summary: async () => {
      try {
        return await get<TopicSummary>("/topics/summary");
      } catch {
        return syntheticTopicSummary();
      }
    },
  },
  backtest: {
    run: async (req: BacktestRequest) => {
      try {
        return await post<BacktestResult>("/backtest/run", req);
      } catch {
        return syntheticBacktest(req);
      }
    },
  },
};

export const WS_URL = `${WS_BASE}/ws/live`;
