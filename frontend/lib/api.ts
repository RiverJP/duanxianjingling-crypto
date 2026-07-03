import { Asset, EquityCurvePoint, OhlcCandle, PaperTrade, PaperTradingSummary } from "@/types/asset";

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
