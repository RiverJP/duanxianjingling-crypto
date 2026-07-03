import { AssetDetail } from "@/components/AssetDetail";
import { getAsset, getAssetOhlc } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AssetPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: routeSymbol } = await params;
  const symbol = routeSymbol.toUpperCase();
  const [asset, candles] = await Promise.all([getAsset(symbol), getAssetOhlc(symbol)]);
  return <AssetDetail asset={asset} candles={candles} />;
}
