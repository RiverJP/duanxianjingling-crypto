import Link from "next/link";
import { Target } from "lucide-react";
import { Asset } from "@/types/asset";
import { formatCompactCurrency, formatCurrency, formatPercent } from "@/lib/format";

export function WatchlistTable({ assets }: { assets: Asset[] }) {
  return (
    <div>
      <div className="space-y-3 md:hidden">
        {assets.map((asset) => (
          <Link key={asset.symbol} href={`/asset/${asset.symbol.toLowerCase()}`} className="block overflow-hidden rounded border border-ink/10 bg-white hover:border-mint/40">
            <div className={`flex items-center justify-between gap-2 px-4 py-3 ${mobileStatusClass(asset.opportunity_status)}`}>
              <span className="inline-flex min-w-0 items-center gap-2 text-sm font-semibold">
                <Target size={16} className="shrink-0" />
                <span className="truncate">{asset.opportunity_status}</span>
              </span>
              <span className="shrink-0 rounded bg-white/70 px-2 py-1 text-xs font-semibold tabular-nums text-ink">
                {asset.opportunity_score}/100
              </span>
            </div>
            <div className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                {asset.image_url ? <img src={asset.image_url} alt="" className="h-8 w-8 shrink-0 rounded-full" /> : null}
                <div className="min-w-0">
                  <p className="truncate font-semibold text-ink">{asset.name}</p>
                  <p className="text-xs text-ink/45">{asset.symbol}</p>
                </div>
              </div>
              <span className={`shrink-0 rounded px-2 py-1 text-xs font-medium ${signalClass(asset.trade_signal)}`}>
                {asset.trade_signal}
              </span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <MobileStat label="机会分" value={`${asset.opportunity_score}/100`} strong />
              <MobileStat label="v3计划盈亏比" value={formatRiskReward(asset.risk_reward_ratio)} strong tone={asset.risk_reward_ratio && asset.risk_reward_ratio >= 1 ? "mint" : "ink"} />
              <MobileStat label="价格" value={formatCurrency(asset.current_price)} />
              <MobileStat label="24小时" value={formatPercent(asset.change_24h)} tone={asset.change_24h >= 0 ? "mint" : "coral"} />
              <MobileStat label="成交量" value={formatCompactCurrency(asset.volume_24h)} />
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="rounded bg-panel px-2 py-1 text-xs text-ink/60">
                触发 {asset.trigger_price ? formatCurrency(asset.trigger_price) : "等待"}
              </span>
              <span className="rounded bg-panel px-2 py-1 text-xs text-ink/60">
                止盈 {asset.take_profit ? formatCurrency(asset.take_profit) : "暂无"}
              </span>
              <span className="rounded bg-panel px-2 py-1 text-xs text-ink/60">
                止损 {asset.stop_loss ? formatCurrency(asset.stop_loss) : "暂无"}
              </span>
            </div>
            </div>
          </Link>
        ))}
      </div>

      <div className="hidden overflow-hidden rounded border border-ink/10 bg-white md:block">
        <table className="w-full min-w-[1320px] text-left text-sm">
        <thead className="bg-panel text-xs uppercase tracking-wide text-ink/55">
          <tr>
            <th className="px-4 py-3">资产</th>
            <th className="px-4 py-3">v3机会</th>
            <th className="px-4 py-3">机会分</th>
            <th className="px-4 py-3">v3计划盈亏比</th>
            <th className="px-4 py-3">价格</th>
            <th className="px-4 py-3">24 小时</th>
            <th className="px-4 py-3">方向</th>
            <th className="px-4 py-3">触发 / 失效</th>
            <th className="px-4 py-3">止盈 / 止损</th>
            <th className="px-4 py-3">市值</th>
            <th className="px-4 py-3">成交量</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-ink/10">
          {assets.map((asset) => (
            <tr key={asset.symbol}>
              <td className="px-4 py-4 font-medium">
                <div className="flex items-center gap-2">
                  {asset.image_url ? <img src={asset.image_url} alt="" className="h-6 w-6 rounded-full" /> : null}
                  <div>
                    <Link href={`/asset/${asset.symbol.toLowerCase()}`} className="hover:text-mint">
                      {asset.name}
                    </Link>
                    <div className="text-xs text-ink/45">{asset.symbol}</div>
                  </div>
                  <Link
                    href={`/asset/${asset.symbol.toLowerCase()}`}
                    className="ml-2 rounded border border-ink/10 px-2 py-1 text-xs font-medium text-ink/60 hover:bg-panel hover:text-ink"
                  >
                    详情
                  </Link>
                </div>
              </td>
              <td className="px-4 py-4">
                <span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium ${statusClass(asset.opportunity_status)}`}>
                  <Target size={13} />
                  {asset.opportunity_status}
                </span>
              </td>
              <td className="px-4 py-4 tabular-nums">
                <span className="font-semibold">{asset.opportunity_score}</span>
                <span className="text-ink/40">/100</span>
              </td>
              <td className={`px-4 py-4 tabular-nums ${asset.risk_reward_ratio && asset.risk_reward_ratio >= 1 ? "font-semibold text-mint" : "text-ink/60"}`}>
                {formatRiskReward(asset.risk_reward_ratio)}
              </td>
              <td className="px-4 py-4 tabular-nums">{formatCurrency(asset.current_price)}</td>
              <td className={`px-4 py-4 tabular-nums ${asset.change_24h >= 0 ? "text-mint" : "text-coral"}`}>
                {formatPercent(asset.change_24h)}
              </td>
              <td className="px-4 py-4">
                <span className={`rounded px-2 py-1 text-xs font-medium ${signalClass(asset.trade_signal)}`}>
                  {asset.trade_signal}
                </span>
              </td>
              <td className="px-4 py-4 text-xs tabular-nums text-ink/70">
                {asset.trigger_price && asset.invalid_price ? (
                  <span>{formatCurrency(asset.trigger_price)} / {formatCurrency(asset.invalid_price)}</span>
                ) : (
                  <span>等待</span>
                )}
              </td>
              <td className="px-4 py-4 text-xs tabular-nums text-ink/70">
                {asset.take_profit && asset.stop_loss ? (
                  <span>{formatCurrency(asset.take_profit)} / {formatCurrency(asset.stop_loss)}</span>
                ) : (
                  <span>暂无</span>
                )}
              </td>
              <td className="px-4 py-4 tabular-nums">{formatCompactCurrency(asset.market_cap)}</td>
              <td className="px-4 py-4 tabular-nums">{formatCompactCurrency(asset.volume_24h)}</td>
              <td className="px-4 py-4 text-right" />
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </div>
  );
}

function MobileStat({ label, value, strong = false, tone = "ink" }: { label: string; value: string; strong?: boolean; tone?: "ink" | "mint" | "coral" }) {
  const color = tone === "mint" ? "text-mint" : tone === "coral" ? "text-coral" : "text-ink";
  return (
    <div className="min-w-0 rounded bg-panel p-3">
      <p className="text-xs text-ink/45">{label}</p>
      <p className={`mt-1 break-words tabular-nums ${strong ? "font-semibold" : "font-medium"} ${color}`}>{value}</p>
    </div>
  );
}

function statusClass(status: string): string {
  if (status === "高优先级") {
    return "bg-gold/20 text-ink";
  }
  if (status === "可关注") {
    return "bg-mint/15 text-mint";
  }
  if (status === "等待触发") {
    return "bg-ink/10 text-ink/65";
  }
  return "bg-panel text-ink/55";
}

function mobileStatusClass(status: string): string {
  if (status === "高优先级") {
    return "bg-gold/35 text-ink";
  }
  if (status === "可关注") {
    return "bg-mint/20 text-mint";
  }
  if (status === "等待触发") {
    return "bg-ink/10 text-ink/70";
  }
  return "bg-panel text-ink/60";
}

function signalClass(signal: string): string {
  if (signal === "做多") {
    return "bg-mint/15 text-mint";
  }
  if (signal === "做空") {
    return "bg-coral/15 text-coral";
  }
  return "bg-ink/10 text-ink/65";
}

function formatRiskReward(value: number | null): string {
  return value ? `${value.toFixed(2)}:1` : "暂无";
}
