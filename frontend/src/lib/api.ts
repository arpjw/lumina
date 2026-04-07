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

export const api = {
  signals: {
    history: (days = 90) => get<RegimeSignal[]>(`/signals/history?days=${days}`),
    latest: () => get<LatestSignal>("/signals/latest"),
  },
  sentiment: {
    daily: (days = 60) => get<DailySentiment[]>(`/sentiment/daily?days=${days}`),
  },
  geopolitical: {
    daily: (days = 60) => get<GeopoliticalDay[]>(`/geopolitical/daily?days=${days}`),
  },
  topics: {
    daily: (days = 30) => get<TopicDay[]>(`/topics/daily?days=${days}`),
    summary: () => get<TopicSummary>("/topics/summary"),
  },
  backtest: {
    run: (req: BacktestRequest) => post<BacktestResult>("/backtest/run", req),
  },
};

export const WS_URL = `${WS_BASE}/ws/live`;
