import { AssetDetail } from "@/components/AssetDetail";
import { Header } from "@/components/Header";
import { getAsset, getAssetOhlc } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function EthPage() {
  const [asset, candles] = await Promise.all([getAsset("ETH"), getAssetOhlc("ETH")]);
  return (
    <>
      <Header />
      <AssetDetail asset={asset} candles={candles} />
    </>
  );
}
