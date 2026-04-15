const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

// Universe
export const getUniverse = (params?: string) =>
  fetchApi<Company[]>(`/api/universe${params ? `?${params}` : ""}`);
export const getCompany = (ticker: string) =>
  fetchApi<CompanyDetail>(`/api/universe/${ticker}`);
export const addCompany = (data: { ticker: string; name?: string; sector?: string }) =>
  fetchApi<Company>("/api/universe/add", { method: "POST", body: JSON.stringify(data) });
export const removeCompany = (ticker: string) =>
  fetchApi(`/api/universe/${ticker}`, { method: "DELETE" });

// Signals
export const getSignals = (ticker: string) =>
  fetchApi<Signal[]>(`/api/signals/${ticker}`);
export const getSignalHistory = (ticker: string, type?: string) =>
  fetchApi<Signal[]>(`/api/signals/${ticker}/history${type ? `?signal_type=${type}` : ""}`);
export const refreshSignals = (ticker: string) =>
  fetchApi(`/api/signals/refresh/${ticker}`, { method: "POST" });

// Nadir
export const getWatchlist = () => fetchApi<Company[]>("/api/nadir/watchlist");
export const getNadirComplete = () => fetchApi<Company[]>("/api/nadir/complete");
export const validateCompany = (ticker: string) =>
  fetchApi(`/api/nadir/${ticker}/validate`);
export const getThesis = (ticker: string) =>
  fetchApi(`/api/nadir/${ticker}/thesis`);

// Beliefs
export const getBeliefs = (ticker: string) =>
  fetchApi<BeliefLayer[]>(`/api/beliefs/${ticker}`);
export const refreshBeliefs = (ticker: string) =>
  fetchApi<BeliefLayer[]>(`/api/beliefs/${ticker}/refresh`, { method: "POST" });

// Positions
export const getPositions = (status?: string) =>
  fetchApi<Position[]>(`/api/positions${status ? `?status=${status}` : ""}`);
export const getPositionHistory = () =>
  fetchApi<Position[]>("/api/positions/history");
export const approvePosition = (ticker: string) =>
  fetchApi<Position>(`/api/positions/${ticker}/approve`, { method: "POST" });
export const exitPosition = (ticker: string, reason: string) =>
  fetchApi<Position>(`/api/positions/${ticker}/exit`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });

// Predictions
export const getPredictions = (activeOnly = false) =>
  fetchApi<Prediction[]>(`/api/predictions?active_only=${activeOnly}`);
export const createPrediction = (data: PredictionCreate) =>
  fetchApi<Prediction>("/api/predictions", { method: "POST", body: JSON.stringify(data) });
export const resolvePrediction = (id: string, data: PredictionResolve) =>
  fetchApi<Prediction>(`/api/predictions/${id}/resolve`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
export const getAccuracyStats = () => fetchApi("/api/predictions/accuracy");

// Alerts
export const getAlerts = (reviewed = false) =>
  fetchApi<Alert[]>(`/api/alerts?reviewed=${reviewed}`);
export const reviewAlert = (id: string, actionTaken: string) =>
  fetchApi<Alert>(`/api/alerts/${id}/review`, {
    method: "PUT",
    body: JSON.stringify({ action_taken: actionTaken }),
  });

// Analytics
export const getPerformance = () => fetchApi("/api/analytics/performance");
export const getSignalAccuracy = () => fetchApi("/api/analytics/signals");
export const getKellyCalibration = () => fetchApi("/api/analytics/kelly");

// Health
export const getHealth = () => fetchApi<{ status: string; mode: string }>("/api/health");

// Types
export interface Company {
  id: string;
  ticker: string;
  name: string;
  sector: string;
  market_cap: number | null;
  current_price: number | null;
  system_state: string;
  conditions_met: number;
  last_scanned: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyDetail extends Company {
  signals: Signal[];
  belief_layers: BeliefLayer[];
  positions: Position[];
  alerts: Alert[];
}

export interface Signal {
  id: string;
  company_id: string;
  signal_type: string;
  current_value: number | null;
  previous_value: number | null;
  threshold: number | null;
  condition_met: boolean;
  raw_data: Record<string, any> | null;
  source: string | null;
  last_updated: string;
}

export interface BeliefLayer {
  id: string;
  company_id: string;
  layer: string;
  assumption_text: string;
  market_implied_value: string;
  variant_value: string;
  confidence_pct: number | null;
  confirming_signals: number;
  contradicting_signals: number;
  net_direction: string;
  last_updated: string;
}

export interface Position {
  id: string;
  company_id: string;
  ticker: string;
  entry_date: string;
  entry_price: number;
  shares: number;
  dollar_amount: number;
  position_pct: number;
  p_win: number | null;
  kelly_fraction: number | null;
  thesis: Record<string, any> | null;
  validation_result: Record<string, any> | null;
  falsification_conditions: Record<string, any> | null;
  time_horizon_days: number;
  status: string;
  exit_date: string | null;
  exit_price: number | null;
  return_pct: number | null;
  exit_reason: string | null;
  pending_approval: boolean;
  created_at: string;
}

export interface Prediction {
  id: string;
  company_id: string;
  claim_text: string;
  observable_outcome: string;
  resolution_date: string;
  confidence_pct: number;
  actual_outcome: string | null;
  outcome_direction: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface PredictionCreate {
  company_id: string;
  claim_text: string;
  observable_outcome: string;
  resolution_date: string;
  confidence_pct: number;
  belief_stack_id?: string;
}

export interface PredictionResolve {
  actual_outcome: string;
  outcome_direction: string;
  notes?: string;
}

export interface Alert {
  id: string;
  company_id: string;
  alert_type: string;
  alert_text: string;
  priority: string;
  reviewed: boolean;
  action_taken: string | null;
  created_at: string;
}
