import { Asset, BacktestResult, BacktestRun, EquityCurvePoint, OhlcCandle, PaperTrade, PaperTradingSummary, SchedulerStatus } from "@/types/asset";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function getAssets(): Promise<Asset[]> {
  const response = await fetch(`${API_BASE_URL}/assets`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error("Unable to load assets");
  }
  return response.json();
}

export async function getAsset(symbol: string): Promise<Asset> {
  const response = await fetch(`${API_BASE_URL}/assets/${symbol}`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error(`Unable to load ${symbol}`);
  }
  return response.json();
}

export async function getAssetOhlc(symbol: string): Promise<OhlcCandle[]> {
  const response = await fetch(`${API_BASE_URL}/assets/${symbol}/ohlc`, { next: { revalidate: 300 } });
  if (!response.ok) {
    return [];
  }
  return response.json();
}

export async function getPaperTradingSummary(): Promise<PaperTradingSummary> {
  const response = await fetch(`${API_BASE_URL}/paper-trading/summary`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error("Unable to load paper trading summary");
  }
  return response.json();
}

export async function getPaperTrades(): Promise<PaperTrade[]> {
  const response = await fetch(`${API_BASE_URL}/paper-trading/trades`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error("Unable to load paper trades");
  }
  return response.json();
}

export async function getEquityCurve(days = 30): Promise<EquityCurvePoint[]> {
  const response = await fetch(`${API_BASE_URL}/paper-trading/equity-curve?days=${days}`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error("Unable to load equity curve");
  }
  return response.json();
}

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  const response = await fetch(`${API_BASE_URL}/scheduler/status`, { next: { revalidate: 60 } });
  if (!response.ok) {
    throw new Error("Unable to load scheduler status");
  }
  return response.json();
}

export async function getBacktestResult(days = 30, limit = 100, interval = "1h", mode = "indicator"): Promise<BacktestResult> {
  const response = await fetch(`${API_BASE_URL}/backtest/month?days=${days}&limit=${limit}&interval=${interval}&mode=${mode}`, { next: { revalidate: 300 } });
  if (!response.ok) {
    throw new Error("Unable to load backtest result");
  }
  return response.json();
}

export async function getBacktestRuns(limit = 8): Promise<BacktestRun[]> {
  const response = await fetch(`${API_BASE_URL}/backtest/runs?limit=${limit}`, { next: { revalidate: 30 } });
  if (!response.ok) {
    return [];
  }
  return response.json();
}

export async function getBacktestRunResult(runKey: string): Promise<BacktestResult> {
  const response = await fetch(`${API_BASE_URL}/backtest/runs/${runKey}`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error("Unable to load saved backtest result");
  }
  return response.json();
}

export async function getSavedBacktestResult(days = 30, interval = "15m", mode = "indicator", tradeLimit?: number, version?: string): Promise<BacktestResult> {
  const params = new URLSearchParams({
    days: String(days),
    interval,
    mode,
  });
  if (version) {
    params.set("version", version);
  }
  if (tradeLimit !== undefined) {
    params.set("trade_limit", String(tradeLimit));
  }
  const response = await fetch(`${API_BASE_URL}/backtest/saved-result?${params.toString()}`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error("Unable to load saved backtest result");
  }
  return response.json();
}
