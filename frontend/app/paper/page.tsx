import Link from "next/link";
import { Header } from "@/components/Header";
import { MetricCard } from "@/components/MetricCard";
import { RefreshCadence } from "@/components/RefreshCadence";
import { getEquityCurve, getPaperTrades, getPaperTradingSummary, getSchedulerStatus } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { EquityCurvePoint } from "@/types/asset";

export const dynamic = "force-dynamic";

export default async function PaperTradingPage() {
  const [summary, trades, equityCurve, schedulerStatus] = await Promise.all([getPaperTradingSummary(), getPaperTrades(), getEquityCurve(30), getSchedulerStatus()]);
  const openTrades = trades.filter((trade) => trade.status === "open");
  const floatingPnlPercent = summary.used_margin > 0 ? (summary.unrealized_pnl / summary.used_margin) * 100 : 0;
  const availableMargin = summary.account_balance - summary.used_margin;
  const marginUsagePercent = summary.account_balance > 0 ? (summary.used_margin / summary.account_balance) * 100 : 0;
  const positionRatio = summary.account_balance > 0 ? (summary.open_notional / summary.account_balance) * 100 : 0;
  const feeRatePercent = (summary.fee_rate * 100).toFixed(2);

  return (
    <>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8">
        <section className="mb-6 sm:mb-8">
          <p className="text-sm font-medium uppercase tracking-wide text-ink/50">模拟观察</p>
          <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">10000U 模拟仓位验证</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/60">
            模拟开仓按 v3 指标策略执行：先更新 15m/1H/4H K 线，再用 1H/4H 方向过滤、日线结构和计划盈亏比筛选。机会分达到 {summary.min_opportunity_score} 且计划盈亏比 &gt;= 1:1 时才开模拟单。每单保证金 {formatCurrency(summary.margin_per_trade)}，{summary.leverage} 倍杠杆；总保证金不超过模拟本金，盈亏已扣 {feeRatePercent}% 手续费磨损。
          </p>
        </section>

        <section className={`mb-6 rounded border p-4 sm:p-5 lg:p-6 ${summary.unrealized_pnl >= 0 ? "border-mint/25 bg-mint/10" : "border-coral/25 bg-coral/10"}`}>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-end">
            <div className="min-w-0">
              <p className="text-sm font-semibold uppercase tracking-wide text-ink/55">当前持仓盈亏</p>
              <p className={`mt-3 break-words text-5xl font-semibold leading-none tabular-nums sm:text-6xl ${summary.unrealized_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {formatCurrency(summary.unrealized_pnl)}
              </p>
              <p className={`mt-3 text-xl font-semibold tabular-nums ${summary.unrealized_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {floatingPnlPercent >= 0 ? "+" : ""}{floatingPnlPercent.toFixed(2)}% / 已用保证金
              </p>
            </div>
            <div className="grid min-w-0 grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
              <HighlightStat label="总资金" value={formatCurrency(summary.account_balance)} />
              <HighlightStat label="当前持仓" value={`${summary.open_trades} 笔`} />
              <HighlightStat label="总仓位" value={formatCurrency(summary.open_notional)} />
              <HighlightStat label="仓位占本金" value={`${positionRatio.toFixed(2)}%`} />
              <HighlightStat label="保证金使用率" value={`${marginUsagePercent.toFixed(2)}%`} />
              <HighlightStat label="剩余可用" value={formatCurrency(availableMargin)} tone={availableMargin >= 0 ? "mint" : "coral"} />
              <HighlightStat label="累计盈亏" value={formatCurrency(summary.total_pnl)} tone={summary.total_pnl >= 0 ? "mint" : "coral"} />
              <HighlightStat label="占总资金" value={`${summary.total_pnl_percent >= 0 ? "+" : ""}${summary.total_pnl_percent}%`} tone={summary.total_pnl >= 0 ? "mint" : "coral"} />
              <HighlightStat label="已用保证金" value={formatCurrency(summary.used_margin)} />
              <HighlightStat label="手续费磨损" value={formatCurrency(summary.total_fees)} tone="coral" />
            </div>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          <MetricCard label="模拟本金" value={formatCurrency(summary.account_balance)} />
          <MetricCard label="已用保证金" value={formatCurrency(summary.used_margin)} />
          <MetricCard label="总名义仓位" value={formatCurrency(summary.open_notional)} accent="gold" />
          <MetricCard label="仓位占本金" value={`${positionRatio.toFixed(2)}%`} />
        </section>

        <section className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          <MetricCard label="剩余可用" value={formatCurrency(availableMargin)} accent={availableMargin >= 0 ? "mint" : "coral"} />
          <MetricCard label="保证金使用率" value={`${marginUsagePercent.toFixed(2)}%`} />
          <MetricCard label="当前持仓" value={summary.open_trades} accent="gold" />
          <MetricCard label="胜率" value={`${summary.win_rate}%`} accent="mint" />
          <MetricCard label="手续费磨损" value={formatCurrency(summary.total_fees)} accent="coral" />
        </section>

        <section className="mt-6 grid gap-4 md:grid-cols-4">
          <PnlCard label="当日盈亏" value={summary.daily_pnl} />
          <PnlCard label="7日盈亏" value={summary.seven_day_pnl} />
          <PnlCard label="30日盈亏" value={summary.thirty_day_pnl} />
          <PnlCard label="总盈亏" value={summary.total_pnl} />
        </section>

        <section className="mt-8 rounded border border-ink/10 bg-white p-5">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">资金曲线</h2>
              <p className="mt-1 text-sm text-ink/55">近 30 天权益变化，包含已平仓收益和当前浮动盈亏。</p>
            </div>
            <p className={`text-sm font-semibold ${summary.total_pnl >= 0 ? "text-mint" : "text-coral"}`}>
              当前权益 {formatCurrency(summary.account_balance + summary.total_pnl)}
            </p>
          </div>
          <EquityCurveChart points={equityCurve} />
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="rounded border border-ink/10 bg-white p-5">
            <h2 className="mb-4 text-lg font-semibold">当前持仓</h2>
            {openTrades.length ? (
              <div className="space-y-3">
                {openTrades.map((trade) => (
                  <div key={trade.id} className="rounded border border-ink/10 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <Link href={`/asset/${trade.symbol.toLowerCase()}`} className="font-semibold hover:text-mint">
                          {trade.symbol}
                        </Link>
                        <span className="ml-2 text-sm text-ink/45">{trade.name}</span>
                      </div>
                      <span className={`rounded px-2 py-1 text-xs font-medium ${trade.side === "做多" ? "bg-mint/15 text-mint" : "bg-coral/15 text-coral"}`}>
                        {trade.side}
                      </span>
                    </div>
                    <div className="mb-4 rounded bg-panel p-4">
                      <p className="text-xs font-medium text-ink/50">单笔持仓盈亏</p>
                      <p className={`mt-2 text-3xl font-semibold tabular-nums ${trade.pnl_usdt >= 0 ? "text-mint" : "text-coral"}`}>
                        {formatCurrency(trade.pnl_usdt)}
                      </p>
                      <p className={`mt-1 text-sm font-semibold tabular-nums ${trade.pnl_usdt >= 0 ? "text-mint" : "text-coral"}`}>
                        {trade.pnl_percent >= 0 ? "+" : ""}{trade.pnl_percent}%
                      </p>
                    </div>
                    <div className="grid gap-2 text-sm text-ink/70 md:grid-cols-2">
                      <p>入场：{formatCurrency(trade.entry_price)}</p>
                      <p>现价：{formatCurrency(trade.current_price)}</p>
                      <p>止盈：{trade.take_profit ? formatCurrency(trade.take_profit) : "暂无"}</p>
                      <p>止损：{trade.stop_loss ? formatCurrency(trade.stop_loss) : "暂无"}</p>
                      <p>机会分：{trade.opportunity_score}/100</p>
                      <p>名义仓位：{formatCurrency(trade.notional_usdt)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded border border-ink/10 bg-panel p-6 text-sm text-ink/60">
                当前没有模拟持仓。等下一次刷新后，机会分达到 {summary.min_opportunity_score} 的标的会自动进入模拟观察。
              </div>
            )}
          </div>

          <div className="rounded border border-ink/10 bg-white p-5">
            <h2 className="mb-4 text-lg font-semibold">规则说明</h2>
            <div className="space-y-3 text-sm leading-6 text-ink/70">
              <p>开单条件：v3 指标策略触发做多/做空，机会分达到 {summary.min_opportunity_score}，计划盈亏比 &gt;= 1:1，并且系统已经给出止盈止损。</p>
              <p>开单资金：模拟账户 {formatCurrency(summary.account_balance)}，每次使用 {formatCurrency(summary.margin_per_trade)} 保证金，{summary.leverage} 倍杠杆；总保证金最多用满本金，不会超开。</p>
              <p>手续费：每笔按名义仓位 {feeRatePercent}% 估算磨损，当前页面的单笔和汇总盈亏均为扣费后净值。</p>
              <p>平仓条件：刷新时如果价格触达止盈或止损，则按当前刷新价格模拟平仓；15m 单最长持仓 7 天，到期仍未触发则到期平仓。</p>
              <p>用途：这个页面用于观察评分策略效果，不连接真实交易所，也不会真实下单。</p>
            </div>
            <div className="mt-5">
              <RefreshCadence status={schedulerStatus} compact />
            </div>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="mb-4 text-xl font-semibold">交易记录</h2>
          <div className="overflow-x-auto rounded border border-ink/10 bg-white">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-panel text-xs uppercase tracking-wide text-ink/55">
                <tr>
                  <th className="px-4 py-3">标的</th>
                  <th className="px-4 py-3">方向</th>
                  <th className="px-4 py-3">状态</th>
                  <th className="px-4 py-3">入场 / 当前</th>
                  <th className="px-4 py-3">止盈 / 止损</th>
                  <th className="px-4 py-3">机会分</th>
                  <th className="px-4 py-3">净盈亏</th>
                  <th className="px-4 py-3">开仓时间</th>
                  <th className="px-4 py-3">平仓</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink/10">
                {trades.map((trade) => (
                  <tr key={trade.id}>
                    <td className="px-4 py-4 font-medium">
                      <Link href={`/asset/${trade.symbol.toLowerCase()}`} className="hover:text-mint">
                        {trade.symbol}
                      </Link>
                      <div className="text-xs text-ink/45">{trade.name}</div>
                    </td>
                    <td className="px-4 py-4">{trade.side}</td>
                    <td className="px-4 py-4">{trade.status === "open" ? "持仓中" : "已平仓"}</td>
                    <td className="px-4 py-4 tabular-nums">{formatCurrency(trade.entry_price)} / {formatCurrency(trade.current_price)}</td>
                    <td className="px-4 py-4 tabular-nums">{trade.take_profit ? formatCurrency(trade.take_profit) : "暂无"} / {trade.stop_loss ? formatCurrency(trade.stop_loss) : "暂无"}</td>
                    <td className="px-4 py-4 tabular-nums">{trade.opportunity_score}/100</td>
                    <td className={`px-4 py-4 tabular-nums ${trade.pnl_usdt >= 0 ? "text-mint" : "text-coral"}`}>
                      {formatCurrency(trade.pnl_usdt)} / {trade.pnl_percent}%
                    </td>
                    <td className="px-4 py-4 text-xs text-ink/60">{trade.opened_at ? new Date(trade.opened_at).toLocaleString("zh-CN") : "暂无"}</td>
                    <td className="px-4 py-4 text-xs text-ink/60">
                      {trade.closed_at ? `${trade.close_reason ?? "平仓"} · ${new Date(trade.closed_at).toLocaleString("zh-CN")}` : "未平仓"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  );
}

function EquityCurveChart({ points }: { points: EquityCurvePoint[] }) {
  if (!points.length) {
    return <div className="grid h-64 place-items-center rounded bg-panel text-sm text-ink/50">暂无资金曲线数据</div>;
  }

  const width = 900;
  const height = 260;
  const padding = 28;
  const values = points.map((point) => point.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const path = points
    .map((point, index) => {
      const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((point.equity - min) / span) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  const latest = points[points.length - 1];
  const first = points[0];
  const lineColor = latest.equity >= first.equity ? "#2a9d8f" : "#e76f51";

  return (
    <div className="overflow-hidden rounded bg-panel p-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-64 w-full">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#d7ded8" />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#d7ded8" />
        <path d={path} fill="none" stroke={lineColor} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        <text x={padding} y={22} className="fill-ink" fontSize="14">{formatCurrency(max)}</text>
        <text x={padding} y={height - 8} className="fill-ink" fontSize="14">{formatCurrency(min)}</text>
        <text x={width - padding - 130} y={22} className="fill-ink" fontSize="14">{latest.date}</text>
      </svg>
    </div>
  );
}

function HighlightStat({ label, value, tone = "ink" }: { label: string; value: string; tone?: "ink" | "mint" | "coral" }) {
  const color = tone === "mint" ? "text-mint" : tone === "coral" ? "text-coral" : "text-ink";
  return (
    <div className="min-w-0 rounded border border-ink/10 bg-white/80 p-3 sm:p-4">
      <p className="text-xs font-medium text-ink/50">{label}</p>
      <p className={`mt-2 break-words text-xl font-semibold tabular-nums sm:text-2xl ${color}`}>{value}</p>
    </div>
  );
}

function PnlCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-ink/10 bg-white p-4 sm:p-5">
      <p className="text-sm font-medium text-ink/55">{label}</p>
      <p className={`mt-4 break-words text-2xl font-semibold tabular-nums sm:text-3xl ${value >= 0 ? "text-mint" : "text-coral"}`}>
        {formatCurrency(value)}
      </p>
    </div>
  );
}
