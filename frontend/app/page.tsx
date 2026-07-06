import Link from "next/link";
import { Header } from "@/components/Header";
import { MetricCard } from "@/components/MetricCard";
import { RefreshCadence } from "@/components/RefreshCadence";
import { WatchlistTable } from "@/components/WatchlistTable";
import { getAssets, getPaperTrades, getPaperTradingSummary, getSchedulerStatus } from "@/lib/api";
import { formatCompactCurrency, formatCurrency } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [assets, paperSummary, paperTrades, schedulerStatus] = await Promise.all([getAssets(), getPaperTradingSummary(), getPaperTrades(), getSchedulerStatus()]);
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
  const availableMargin = paperSummary.available_margin ?? paperSummary.account_balance - paperSummary.used_margin;
  const marginUsagePercent = paperSummary.account_balance > 0 ? (paperSummary.used_margin / paperSummary.account_balance) * 100 : 0;
  const notionalExposureRatio = paperSummary.account_balance > 0 ? (paperSummary.open_notional / paperSummary.account_balance) * 100 : 0;
  const perTradeNotional = paperSummary.margin_per_trade * paperSummary.leverage;
  const feeRatePercent = (paperSummary.fee_rate * 100).toFixed(2);
  const latestRefresh = formatLatestRefresh(assets.map((asset) => asset.refreshed_at).filter(Boolean) as string[]);
  const universeLabel = schedulerStatus.market_universe_source === "binance_futures"
    ? `币安 U 本位永续合约 24h 成交额前 ${schedulerStatus.tracked_asset_count} 个交易对`
    : `CoinGecko 市值前 ${schedulerStatus.tracked_asset_count} 个标的`;

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
            短线精灵默认扫描{universeLabel}，首页机会使用 v6.4 1H主导指标策略：15m 执行开单，1H 决定主方向，4H/日线作为背景加减分，趋势单按参考目标和移动止损回测，区间单按固定止盈止损。
          </p>
          <p className="mt-2 text-xs text-ink/45">首页最后刷新：{latestRefresh}</p>
        </section>

        <section className={`mb-6 rounded border p-4 sm:p-5 lg:p-6 ${paperSummary.unrealized_pnl >= 0 ? "border-mint/25 bg-mint/10" : "border-coral/25 bg-coral/10"}`}>
          <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-end">
            <div className="min-w-0">
              <p className="text-sm font-semibold uppercase tracking-wide text-ink/55">当前模拟持仓盈亏</p>
              <p className={`mt-3 break-words text-5xl font-semibold leading-none tabular-nums sm:text-6xl ${paperSummary.unrealized_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {formatCurrency(paperSummary.unrealized_pnl)}
              </p>
              <p className={`mt-2 text-lg font-semibold tabular-nums ${paperSummary.unrealized_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {floatingPnlPercent >= 0 ? "+" : ""}{floatingPnlPercent.toFixed(2)}% / 按已用保证金计算
              </p>
              <p className="mt-3 text-sm leading-6 text-ink/65">
                规则：先同步最新 15m/1H/4H K 线，再按 v6.4 1H主导指标策略筛选；方向为做多/做空、1H 与开仓方向一致、15m确认K线成立、计划盈亏比 &gt;= 1.3:1 且有止盈止损时自动进入模拟开单。每单保证金 {formatCurrency(paperSummary.margin_per_trade)}，{paperSummary.leverage} 倍杠杆；止盈止损平仓后会滚动更新当前本金，盈亏已扣 {feeRatePercent}% 手续费磨损。
              </p>
              {marginUsagePercent > 100 ? (
                <p className="mt-2 text-sm leading-6 text-coral">
                  当前已用保证金超过当前本金，说明现有未平仓模拟持仓已经超额占用资金；这里仅展示持仓现状，不会自动清仓或改动持仓数据。
                </p>
              ) : null}
            </div>
            <div className="grid min-w-0 grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
              <HomePnlStat label="初始本金" value={formatCurrency(paperSummary.initial_balance ?? 10000)} hint="模拟起始本金" />
              <HomePnlStat label="当前本金" value={formatCurrency(paperSummary.account_balance)} hint="初始本金 + 已实现盈亏" tone={paperSummary.realized_pnl >= 0 ? "mint" : "coral"} />
              <HomePnlStat label="当前权益" value={formatCurrency(paperSummary.equity ?? paperSummary.account_balance + paperSummary.unrealized_pnl)} hint="当前本金 + 未实现盈亏" tone={(paperSummary.equity ?? paperSummary.account_balance + paperSummary.unrealized_pnl) >= (paperSummary.initial_balance ?? 10000) ? "mint" : "coral"} />
              <HomePnlStat label="可用保证金" value={formatCurrency(availableMargin)} hint="当前本金 - 已用保证金" tone={availableMargin >= 0 ? "mint" : "coral"} />
              <HomePnlStat label="已用保证金" value={formatCurrency(paperSummary.used_margin)} hint="真实占用本金" />
              <HomePnlStat label="保证金使用率" value={`${marginUsagePercent.toFixed(2)}%`} hint="已用保证金 / 当前本金" />
              <HomePnlStat label="名义仓位" value={formatCurrency(paperSummary.open_notional)} hint="保证金 × 杠杆后的敞口" />
              <HomePnlStat label="名义仓位 / 本金" value={`${notionalExposureRatio.toFixed(2)}%`} hint="敞口大小，不是本金占用" />
              <HomePnlStat label="当前浮盈亏" value={formatCurrency(paperSummary.unrealized_pnl)} hint="未平仓持仓盈亏" tone={paperSummary.unrealized_pnl >= 0 ? "mint" : "coral"} />
              <HomePnlStat label="持仓笔数" value={`${paperSummary.open_trades} 笔`} hint={`每笔名义 ${formatCurrency(perTradeNotional)}`} />
              <HomePnlStat label="已实现盈亏" value={formatCurrency(paperSummary.realized_pnl)} hint="已平仓止盈/止损/到期" tone={paperSummary.realized_pnl >= 0 ? "mint" : "coral"} />
              <HomePnlStat label="累计盈亏" value={formatCurrency(paperSummary.total_pnl)} hint="已实现 + 未实现" tone={paperSummary.total_pnl >= 0 ? "mint" : "coral"} />
              <HomePnlStat label="手续费磨损" value={formatCurrency(paperSummary.total_fees)} hint={`${feeRatePercent}% × 每笔名义仓位`} tone="coral" />
              <HomePnlStat label="累计收益率" value={`${paperSummary.total_pnl_percent >= 0 ? "+" : ""}${paperSummary.total_pnl_percent}%`} hint="累计盈亏 / 初始本金" tone={paperSummary.total_pnl >= 0 ? "mint" : "coral"} />
              <Link href="/paper" className="rounded border border-ink/10 bg-white/80 p-3 hover:bg-white sm:p-4">
                <p className="text-xs font-medium text-ink/50">模拟详情</p>
                <p className="mt-2 text-xl font-semibold text-ink sm:text-2xl">查看</p>
                <p className="mt-1 text-[11px] leading-4 text-ink/45">查看每日、7日、30日表现</p>
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
                      <p>
                        开仓盈亏比：{formatRiskReward(calculateTradeRiskReward(trade.side, trade.entry_price, trade.take_profit, trade.stop_loss))}
                        <span className="mx-1 text-ink/35">/</span>
                        当前剩余盈亏比：{formatRiskReward(calculateRemainingRiskReward(trade.side, trade.current_price, trade.take_profit, trade.stop_loss))}
                      </p>
                      <div className="grid grid-cols-2 gap-2 py-1">
                        <TradePriceStat label="开仓价" value={formatCurrency(trade.entry_price)} />
                        <TradePriceStat label="现价" value={formatCurrency(trade.current_price)} />
                        <TradePriceStat
                          label="参考止盈"
                          value={trade.take_profit ? formatCurrency(trade.take_profit) : "暂无"}
                          subValue={trade.take_profit ? formatSignedCurrency(calculateProjectedPnl(trade.side, trade.entry_price, trade.take_profit, trade.notional_usdt)) : undefined}
                          tone="mint"
                        />
                        <TradePriceStat
                          label="止损价"
                          value={trade.stop_loss ? formatCurrency(trade.stop_loss) : "暂无"}
                          subValue={trade.stop_loss ? formatSignedCurrency(calculateProjectedPnl(trade.side, trade.entry_price, trade.stop_loss, trade.notional_usdt)) : undefined}
                          tone="coral"
                        />
                      </div>
                      <p>保证金：{formatCurrency(trade.margin_usdt)} · 名义仓位：{formatCurrency(trade.notional_usdt)}</p>
                      <p className={trade.pnl_usdt >= 0 ? "font-semibold text-mint" : "font-semibold text-coral"}>
                        净盈亏：{formatCurrency(trade.pnl_usdt)} / {trade.pnl_percent}%
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink/60">
                当前没有模拟持仓。下一次刷新后，满足 v6.4 1H主导指标策略、15m确认K线成立且计划盈亏比 &gt;= 1.3:1 的标的会自动进入模拟开单。
              </p>
            )}
          </div>
        </section>

        <div className="mb-6">
          <RefreshCadence status={schedulerStatus} />
        </div>

        <section className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          <MetricCard label="追踪资产" value={assets.length} />
          <MetricCard label="可关注机会" value={highPriorityCount} accent="mint" />
          <MetricCard label="最高机会分" value={leader ? `${leader.symbol} ${leader.opportunity_score}/100` : "需要刷新"} accent="gold" />
          <MetricCard label="24 小时成交量" value={formatCompactCurrency(totalVolume)} accent="mint" />
        </section>

        <section className="mt-8">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">v6 市场机会列表</h2>
            {leader ? <p className="text-sm text-ink/55">当前首选 {leader.symbol}，v6机会分 {leader.opportunity_score}/100，价格 {formatCurrency(leader.current_price)}</p> : null}
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

function formatLatestRefresh(values: string[]): string {
  if (!values.length) {
    return "暂无";
  }
  const latest = values
    .map((value) => new Date(value))
    .filter((value) => !Number.isNaN(value.getTime()))
    .sort((a, b) => b.getTime() - a.getTime())[0];
  return latest ? latest.toLocaleString("zh-CN") : "暂无";
}

function HomePnlStat({ label, value, hint, tone = "ink" }: { label: string; value: string; hint?: string; tone?: "ink" | "mint" | "coral" }) {
  const color = tone === "mint" ? "text-mint" : tone === "coral" ? "text-coral" : "text-ink";
  return (
    <div className="min-w-0 rounded border border-ink/10 bg-white/80 p-3 sm:p-4">
      <p className="text-xs font-medium text-ink/50">{label}</p>
      <p className={`mt-2 break-words text-xl font-semibold tabular-nums sm:text-2xl ${color}`}>{value}</p>
      {hint ? <p className="mt-1 text-[11px] leading-4 text-ink/45">{hint}</p> : null}
    </div>
  );
}

function TradePriceStat({ label, value, subValue, tone = "ink" }: { label: string; value: string; subValue?: string; tone?: "ink" | "mint" | "coral" }) {
  const color = tone === "mint" ? "text-mint" : tone === "coral" ? "text-coral" : "text-ink";
  return (
    <div className="min-w-0 rounded bg-panel p-2">
      <p className="text-[11px] text-ink/45">{label}</p>
      <p className={`mt-1 break-words text-xs font-semibold tabular-nums ${color}`}>{value}</p>
      {subValue ? <p className={`mt-0.5 break-words text-[11px] font-semibold tabular-nums ${color}`}>{subValue}</p> : null}
    </div>
  );
}

function calculateProjectedPnl(side: string, entryPrice: number, targetPrice: number, notional: number): number {
  if (entryPrice <= 0) {
    return 0;
  }
  const ratio = side === "做空" ? (entryPrice - targetPrice) / entryPrice : (targetPrice - entryPrice) / entryPrice;
  return ratio * notional;
}

function formatSignedCurrency(value: number): string {
  const formatted = formatCurrency(Math.abs(value));
  return `${value >= 0 ? "+" : "-"}${formatted}`;
}

function calculateTradeRiskReward(side: string, entryPrice: number, takeProfit: number | null, stopLoss: number | null): number | null {
  if (entryPrice <= 0 || !takeProfit || !stopLoss) {
    return null;
  }
  const reward = Math.abs(calculateProjectedPnl(side, entryPrice, takeProfit, 1));
  const risk = Math.abs(calculateProjectedPnl(side, entryPrice, stopLoss, 1));
  if (risk <= 0) {
    return null;
  }
  return reward / risk;
}

function calculateRemainingRiskReward(side: string, currentPrice: number, takeProfit: number | null, stopLoss: number | null): number | null {
  if (currentPrice <= 0 || !takeProfit || !stopLoss) {
    return null;
  }
  const reward = Math.abs(calculateProjectedPnl(side, currentPrice, takeProfit, 1));
  const risk = Math.abs(calculateProjectedPnl(side, currentPrice, stopLoss, 1));
  if (risk <= 0) {
    return null;
  }
  if (side === "做多" && (currentPrice >= takeProfit || currentPrice <= stopLoss)) {
    return null;
  }
  if (side === "做空" && (currentPrice <= takeProfit || currentPrice >= stopLoss)) {
    return null;
  }
  return reward / risk;
}

function formatRiskReward(value: number | null): string {
  return value ? `${value.toFixed(2)}:1` : "暂无";
}
