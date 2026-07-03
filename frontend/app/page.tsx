import Link from "next/link";
import { Header } from "@/components/Header";
import { MetricCard } from "@/components/MetricCard";
import { WatchlistTable } from "@/components/WatchlistTable";
import { getAssets, getPaperTrades, getPaperTradingSummary } from "@/lib/api";
import { formatCompactCurrency, formatCurrency } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [assets, paperSummary, paperTrades] = await Promise.all([getAssets(), getPaperTradingSummary(), getPaperTrades()]);
  const openTrades = paperTrades.filter((trade) => trade.status === "open");
  const leader = assets.reduce<typeof assets[number] | null>((best, asset) => {
    if (!best) {
      return asset;
    }
    return asset.opportunity_score > best.opportunity_score ? asset : best;
  }, null);
  const highPriorityCount = assets.filter((asset) => asset.opportunity_status === "高优先级" || asset.opportunity_status === "可关注").length;
  const totalVolume = assets.reduce((sum, asset) => sum + asset.volume_24h, 0);
  const floatingPnlPercent = paperSummary.used_margin > 0 ? (paperSummary.unrealized_pnl / paperSummary.used_margin) * 100 : 0;
  const availableMargin = paperSummary.account_balance + paperSummary.total_pnl - paperSummary.used_margin;
  const marginUsagePercent = paperSummary.account_balance > 0 ? (paperSummary.used_margin / paperSummary.account_balance) * 100 : 0;
  const positionRatio = paperSummary.account_balance > 0 ? (paperSummary.open_notional / paperSummary.account_balance) * 100 : 0;

  return (
    <>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8">
        <section className="mb-6 sm:mb-8">
          <p className="text-sm font-medium uppercase tracking-wide text-ink/50">短线精灵</p>
          <h1 className="mt-2 max-w-4xl text-3xl font-semibold leading-tight sm:text-4xl lg:text-5xl">
            从市场前排标的里自动发现短线机会
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-ink/60">
            短线精灵默认扫描 CoinGecko 市值前 100 个标的，按机会分、趋势、流动性和风险排序；完整 K 线、技术指标和模拟做单效果可进入详情页与模拟观察页查看。
          </p>
        </section>

        <section className={`mb-6 rounded border p-4 sm:p-5 lg:p-6 ${paperSummary.unrealized_pnl >= 0 ? "border-mint/25 bg-mint/10" : "border-coral/25 bg-coral/10"}`}>
          <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-end">
            <div className="min-w-0">
              <p className="text-sm font-semibold uppercase tracking-wide text-ink/55">当前模拟持仓盈利</p>
              <p className={`mt-3 break-words text-5xl font-semibold leading-none tabular-nums sm:text-6xl ${paperSummary.unrealized_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {formatCurrency(paperSummary.unrealized_pnl)}
              </p>
              <p className={`mt-2 text-lg font-semibold tabular-nums ${paperSummary.unrealized_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {floatingPnlPercent >= 0 ? "+" : ""}{floatingPnlPercent.toFixed(2)}% / 已用保证金
              </p>
              <p className="mt-3 text-sm leading-6 text-ink/65">
                规则：机会分 &gt;= {paperSummary.min_opportunity_score} 且方向为做多/做空时自动进入模拟开单；每单保证金 {formatCurrency(paperSummary.margin_per_trade)}，{paperSummary.leverage} 倍杠杆，名义仓位 {formatCurrency(paperSummary.margin_per_trade * paperSummary.leverage)}。
              </p>
            </div>
            <div className="grid min-w-0 grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
              <HomePnlStat label="总资金" value={formatCurrency(paperSummary.account_balance)} />
              <HomePnlStat label="持仓" value={`${paperSummary.open_trades} 笔`} />
              <HomePnlStat label="总仓位" value={formatCurrency(paperSummary.open_notional)} />
              <HomePnlStat label="仓位占本金" value={`${positionRatio.toFixed(2)}%`} />
              <HomePnlStat label="已用保证金" value={formatCurrency(paperSummary.used_margin)} />
              <HomePnlStat label="保证金使用率" value={`${marginUsagePercent.toFixed(2)}%`} />
              <HomePnlStat label="剩余可用" value={formatCurrency(availableMargin)} tone={availableMargin >= 0 ? "mint" : "coral"} />
              <HomePnlStat label="总盈亏" value={formatCurrency(paperSummary.total_pnl)} tone={paperSummary.total_pnl >= 0 ? "mint" : "coral"} />
              <HomePnlStat label="占总资金" value={`${paperSummary.total_pnl_percent >= 0 ? "+" : ""}${paperSummary.total_pnl_percent}%`} tone={paperSummary.total_pnl >= 0 ? "mint" : "coral"} />
              <Link href="/paper" className="rounded border border-ink/10 bg-white/80 p-3 hover:bg-white sm:p-4">
                <p className="text-xs font-medium text-ink/50">模拟详情</p>
                <p className="mt-2 text-xl font-semibold text-ink sm:text-2xl">查看</p>
              </Link>
            </div>
          </div>
          <div className="rounded border border-ink/10 bg-white/75 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink">当前持仓标的</h2>
              <Link href="/paper" className="text-sm font-medium text-ink/60 hover:text-ink">
                查看详情
              </Link>
            </div>
            {openTrades.length ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {openTrades.map((trade) => (
                  <Link key={trade.id} href={`/asset/${trade.symbol.toLowerCase()}`} className="rounded border border-ink/10 bg-white p-3 hover:border-mint/40">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold text-ink">{trade.symbol}</p>
                        <p className="text-xs text-ink/45">{trade.name}</p>
                      </div>
                      <span className={`rounded px-2 py-1 text-xs font-medium ${trade.side === "做多" ? "bg-mint/15 text-mint" : "bg-coral/15 text-coral"}`}>
                        {trade.side}
                      </span>
                    </div>
                    <div className="space-y-1 text-xs leading-5 text-ink/65">
                      <p>机会分：{trade.opportunity_score}/100</p>
                      <p>保证金：{formatCurrency(trade.margin_usdt)}</p>
                      <p>名义仓位：{formatCurrency(trade.notional_usdt)}</p>
                      <p className={trade.pnl_usdt >= 0 ? "font-semibold text-mint" : "font-semibold text-coral"}>
                        盈亏：{formatCurrency(trade.pnl_usdt)} / {trade.pnl_percent}%
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink/60">
                当前没有模拟持仓。下一次刷新后，机会分 &gt;= {paperSummary.min_opportunity_score} 的做多/做空标的会自动进入模拟开单。
              </p>
            )}
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          <MetricCard label="追踪资产" value={assets.length} />
          <MetricCard label="可关注机会" value={highPriorityCount} accent="mint" />
          <MetricCard label="最高机会分" value={leader ? `${leader.symbol} ${leader.opportunity_score}/100` : "需要刷新"} accent="gold" />
          <MetricCard label="24 小时成交量" value={formatCompactCurrency(totalVolume)} accent="mint" />
        </section>

        <section className="mt-8">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">市场机会列表</h2>
            {leader ? <p className="text-sm text-ink/55">当前首选 {leader.symbol}，机会分 {leader.opportunity_score}/100，价格 {formatCurrency(leader.current_price)}</p> : null}
          </div>
          {assets.length ? (
            <div className="overflow-x-auto">
              <WatchlistTable assets={assets} />
            </div>
          ) : (
            <div className="rounded border border-ink/10 bg-white p-8 text-ink/60">
              暂无资产数据。请运行后端刷新接口加载市场扫描列表。
            </div>
          )}
        </section>
      </main>
    </>
  );
}

function HomePnlStat({ label, value, tone = "ink" }: { label: string; value: string; tone?: "ink" | "mint" | "coral" }) {
  const color = tone === "mint" ? "text-mint" : tone === "coral" ? "text-coral" : "text-ink";
  return (
    <div className="min-w-0 rounded border border-ink/10 bg-white/80 p-3 sm:p-4">
      <p className="text-xs font-medium text-ink/50">{label}</p>
      <p className={`mt-2 break-words text-xl font-semibold tabular-nums sm:text-2xl ${color}`}>{value}</p>
    </div>
  );
}
