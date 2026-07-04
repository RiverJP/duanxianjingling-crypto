import Link from "next/link";
import { BacktestComparison } from "@/components/BacktestComparison";
import { BacktestTradesExplorer } from "@/components/BacktestTradesExplorer";
import { Header } from "@/components/Header";
import { MetricCard } from "@/components/MetricCard";
import { getBacktestRuns, getSavedBacktestResult } from "@/lib/api";
import { formatCompactCurrency, formatCurrency } from "@/lib/format";
import { BacktestAsset, BacktestRules, BacktestRun, BacktestTrade, EquityCurvePoint } from "@/types/asset";

export const dynamic = "force-dynamic";

const PERIODS = [
  { days: 30, label: "1个月" },
  { days: 60, label: "2个月" },
  { days: 180, label: "6个月" },
];

const INTERVALS = [
  { interval: "15m", label: "15分钟开单" },
];

const VERSION_OPTIONS = [
  { value: "v1", label: "v1", description: "indicator-v1.1" },
  { value: "v2", label: "v2", description: "2026-07-04v2" },
  { value: "v3", label: "v3", description: "2026-07-04v3" },
];

export default async function BacktestPage({ searchParams }: { searchParams?: Promise<{ days?: string; interval?: string; version?: string }> }) {
  const params = await searchParams;
  const requestedDays = normalizeDays(params?.days);
  const requestedInterval = normalizeInterval(params?.interval);
  const requestedVersion = normalizeVersion(params?.version);
  const recentRuns = await getBacktestRuns(20);
  const result = await getSavedBacktestResult(requestedDays ?? 30, requestedInterval, "indicator", 0, requestedVersion).catch(() => null);
  if (!result) {
    return <BacktestMissingPage days={requestedDays ?? 30} interval={requestedInterval} version={requestedVersion} recentRuns={recentRuns} />;
  }
  const { summary, rules, assets, equity_curve: equityCurve } = result;
  const isFallback = !requestedDays && summary.days !== 30;
  const feeRatePercent = ((summary.fee_rate ?? 0) * 100).toFixed(2);
  const netPnl = summary.net_pnl ?? summary.total_pnl;
  const netPnlPercent = summary.net_pnl_percent ?? summary.total_pnl_percent;
  const totalFees = summary.total_fees ?? 0;
  const averageNetPnl = summary.average_net_pnl ?? summary.average_pnl;

  return (
    <>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8">
        <section className="mb-6 sm:mb-8">
          <p className="text-sm font-medium uppercase tracking-wide text-ink/50">策略回测</p>
          <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">近 {summary.days} 天指标策略回测</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/60">
            用日线 Vegas、EMA、DT、斐波那契、结构和支撑阻力先判断大方向，再用 15分钟执行开仓；15分钟执行时会同时用 1小时 + 4小时过滤方向。回测只读取已入库K线，不会临时改动模拟持仓，默认排除期末强制平仓单。
          </p>
          {summary.run_key ? (
            <div className="mt-4 inline-flex flex-wrap items-center gap-2 rounded border border-ink/10 bg-white px-3 py-2 text-xs text-ink/55">
              <span>回测编号</span>
              <span className="font-mono font-semibold text-ink">{summary.run_key}</span>
              <span>策略版本 {summary.strategy_version}</span>
            </div>
          ) : null}
          {summary.run_key && requestedDays && summary.generated_at ? (
            <p className="mt-2 text-xs text-ink/45">
              若当前周期没有独立回测记录，页面会自动使用更长周期保存记录按开仓时间切出当前周期数据。
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {VERSION_OPTIONS.map((item) => (
              <Link
                key={item.value}
                href={`/backtest?days=${summary.days}&interval=${summary.execution_interval}&version=${item.value}`}
                className={`rounded border px-3 py-2 text-sm font-medium ${
                  requestedVersion === item.value ? "border-ink bg-ink text-white" : "border-ink/10 bg-white text-ink/60 hover:text-ink"
                }`}
                title={item.description}
              >
                {item.label}
              </Link>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {PERIODS.map((period) => (
              <Link
                key={period.days}
                href={`/backtest?days=${period.days}&interval=${summary.execution_interval}&version=${requestedVersion}`}
                className={`rounded border px-3 py-2 text-sm font-medium ${
                  summary.days === period.days ? "border-mint bg-mint/15 text-mint" : "border-ink/10 bg-white text-ink/60 hover:text-ink"
                }`}
              >
                {period.label}
              </Link>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {INTERVALS.map((item) => (
              <Link
                key={item.interval}
                href={`/backtest?days=${summary.days}&interval=${item.interval}&version=${requestedVersion}`}
                className={`rounded border px-3 py-2 text-sm font-medium ${
                  summary.execution_interval === item.interval ? "border-gold bg-gold/15 text-ink" : "border-ink/10 bg-white text-ink/60 hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
          {isFallback ? (
            <p className="mt-3 rounded border border-gold/30 bg-gold/15 px-3 py-2 text-sm text-ink/70">
              近 1 个月没有触发交易，已自动扩展到 2 个月回测。
            </p>
          ) : null}
        </section>

        <section className={`mb-6 rounded border p-4 sm:p-5 lg:p-6 ${summary.total_pnl >= 0 ? "border-mint/25 bg-mint/10" : "border-coral/25 bg-coral/10"}`}>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:items-end">
            <div className="min-w-0">
              <p className="text-sm font-semibold uppercase tracking-wide text-ink/55">回测累计盈亏</p>
              <p className={`mt-3 break-words text-5xl font-semibold leading-none tabular-nums sm:text-6xl ${summary.total_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {formatCurrencyExact(summary.total_pnl)}
              </p>
              <p className={`mt-2 text-lg font-semibold tabular-nums ${summary.total_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                {summary.total_pnl_percent >= 0 ? "+" : ""}{summary.total_pnl_percent}% / 模拟本金
              </p>
              <p className={`mt-2 text-base font-semibold tabular-nums ${netPnl >= 0 ? "text-mint" : "text-coral"}`}>
                扣除 {feeRatePercent}%/笔手续费后：{formatCurrencyExact(netPnl)}（{netPnlPercent >= 0 ? "+" : ""}{netPnlPercent}%）
              </p>
              <p className="mt-3 text-sm leading-6 text-ink/65">
                回测范围 {summary.days} 天，使用 {formatInterval(summary.trend_interval)} 过滤方向、{formatInterval(summary.execution_interval)} 执行交易；测试现有 {summary.tested_assets} 个标的，其中 {summary.traded_assets} 个触发交易，共 {summary.total_trades} 笔闭环交易。
              </p>
              <p className="mt-2 text-xs leading-5 text-ink/55">
                当前规则：指标质量分 &gt;= 80，大趋势允许该方向，并且执行周期与观察周期不冲突才开仓；旧综合评分只作为参考。
              </p>
              {summary.excluded_period_end_trades > 0 ? (
                <p className="mt-2 text-xs leading-5 text-ink/55">
                  已排除 {summary.excluded_period_end_trades} 笔期末平仓单，当前胜率、盈亏和资金曲线只统计止盈、止损或到期平仓的闭环交易。
                </p>
              ) : null}
              {summary.excluded_low_risk_reward_trades > 0 ? (
                <p className="mt-2 text-xs leading-5 text-ink/55">
                  已排除 {summary.excluded_low_risk_reward_trades} 笔计划盈亏比低于 1:1 的交易。
                </p>
              ) : null}
            </div>
            <div className="grid min-w-0 grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
              <BacktestStat label="总交易" value={`${summary.total_trades} 笔`} />
              <BacktestStat label="胜率" value={`${summary.win_rate}%`} tone="mint" />
              <BacktestStat label="盈利笔数" value={`${summary.winning_trades} 笔`} tone="mint" />
              <BacktestStat label="亏损笔数" value={`${summary.losing_trades} 笔`} tone="coral" />
              <BacktestStat label="平均每笔" value={formatCurrencyExact(summary.average_pnl)} tone={summary.average_pnl >= 0 ? "mint" : "coral"} />
              <BacktestStat label="估算手续费" value={formatCurrencyExact(totalFees)} tone="coral" />
              <BacktestStat label="扣费后盈亏" value={formatCurrencyExact(netPnl)} tone={netPnl >= 0 ? "mint" : "coral"} />
              <BacktestStat label="扣费后平均" value={formatCurrencyExact(averageNetPnl)} tone={averageNetPnl >= 0 ? "mint" : "coral"} />
              <BacktestStat label="最大单笔盈利" value={formatCurrencyExact(summary.best_trade)} tone="mint" />
              <BacktestStat label="最大单笔亏损" value={formatCurrencyExact(summary.worst_trade)} tone="coral" />
              <BacktestStat label="触发标的数" value={`${summary.traded_assets} 个`} />
              <BacktestStat label="排除期末" value={`${summary.excluded_period_end_trades} 笔`} />
              <BacktestStat label="排除低盈亏比" value={`${summary.excluded_low_risk_reward_trades} 笔`} />
            </div>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          <MetricCard label="回测天数" value={`${summary.days} 天`} />
          <MetricCard label="执行周期" value={formatInterval(summary.execution_interval)} />
          <MetricCard label="趋势过滤" value={formatInterval(summary.trend_interval)} />
          <MetricCard label="测试标的" value={summary.tested_assets} />
          <MetricCard label="触发标的" value={summary.traded_assets} accent="gold" />
          <MetricCard label="盈利交易" value={summary.winning_trades} accent="mint" />
          <MetricCard label="亏损交易" value={summary.losing_trades} accent="coral" />
        </section>

        <BacktestRulesSection rules={rules} />

        <BacktestComparison version={requestedVersion} />

        <BacktestRunHistory runs={recentRuns} />

        <section className="mt-8 rounded border border-ink/10 bg-white p-5">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">回测资金曲线</h2>
              <p className="mt-1 text-sm text-ink/55">按每日已平仓收益累计，期末强制平仓单默认不计入曲线。</p>
            </div>
            <p className={`text-sm font-semibold ${summary.total_pnl >= 0 ? "text-mint" : "text-coral"}`}>
              期末权益 {formatCurrencyExact(10000 + summary.total_pnl)}
            </p>
          </div>
          <EquityCurveChart points={equityCurve} />
        </section>

        <section className="mt-8">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">全部回测标的</h2>
              <p className="mt-1 text-sm text-ink/55">
                本次逐个回测 {summary.tested_assets} 个标的，使用 {formatInterval(summary.execution_interval)} 执行交易、{formatInterval(summary.trend_interval)} 观察方向。只有指标质量分 &gt;= 80、方向为做多/做空、且有可执行止盈止损计划时才会开仓。
              </p>
            </div>
          </div>

          <div className="space-y-3 md:hidden">
            {assets.map((asset) => (
              <BacktestAssetCard key={asset.symbol} asset={asset} />
            ))}
          </div>

          <div className="hidden overflow-x-auto rounded border border-ink/10 bg-white md:block">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-panel text-xs uppercase tracking-wide text-ink/55">
                <tr>
                  <th className="px-4 py-3">标的</th>
                  <th className="px-4 py-3">状态</th>
                  <th className="px-4 py-3">最高指标分</th>
                  <th className="px-4 py-3">最佳方向</th>
                  <th className="px-4 py-3">交易</th>
                  <th className="px-4 py-3">盈亏</th>
                  <th className="px-4 py-3">执行周期</th>
                  <th className="px-4 py-3">K线数</th>
                  <th className="px-4 py-3">市值</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink/10">
                {assets.map((asset) => (
                  <tr key={asset.symbol}>
                    <td className="px-4 py-4 font-medium">
                      <Link href={`/asset/${asset.symbol.toLowerCase()}`} className="hover:text-mint">
                        {asset.symbol}
                      </Link>
                      <div className="text-xs text-ink/45">{asset.name}</div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`rounded px-2 py-1 text-xs font-medium ${asset.total_trades > 0 ? "bg-mint/15 text-mint" : "bg-ink/10 text-ink/60"}`}>
                        {asset.status}
                      </span>
                    </td>
                    <td className="px-4 py-4 tabular-nums">
                      <span className={asset.best_opportunity_score >= 80 ? "font-semibold text-mint" : "text-ink/70"}>
                        {asset.best_opportunity_score}/100
                      </span>
                    </td>
                    <td className="px-4 py-4">{asset.best_signal}</td>
                    <td className="px-4 py-4 tabular-nums">{asset.total_trades} 笔</td>
                    <td className={`px-4 py-4 font-semibold tabular-nums ${asset.total_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                      {formatCurrency(asset.total_pnl)}
                    </td>
                    <td className="px-4 py-4">{formatInterval(asset.execution_interval)}</td>
                    <td className="px-4 py-4 tabular-nums">{asset.candle_count}</td>
                    <td className="px-4 py-4 tabular-nums">{formatCompactCurrency(asset.market_cap)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <BacktestTradesExplorer days={summary.days} interval={summary.execution_interval} totalTrades={summary.total_trades} version={requestedVersion} />
      </main>
    </>
  );
}

function BacktestMissingPage({ days, interval, version, recentRuns }: { days: number; interval: string; version: string; recentRuns: BacktestRun[] }) {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8">
        <section className="rounded border border-gold/30 bg-gold/10 p-5 sm:p-6">
          <p className="text-sm font-medium uppercase tracking-wide text-ink/50">策略回测</p>
          <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">暂无已保存的 {days} 天 {formatInterval(interval)} 回测</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/65">
            为了避免页面打开时自动跑 180 天全市场长回测导致卡死，现在回测页优先读取数据库里的历史回测记录。当前组合还没有保存结果，可以先查看下面最近回测记录。
          </p>
        </section>
        <BacktestComparison version={version} />
        <BacktestRunHistory runs={recentRuns} />
      </main>
    </>
  );
}

function BacktestAssetCard({ asset }: { asset: BacktestAsset }) {
  return (
    <div className="rounded border border-ink/10 bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <Link href={`/asset/${asset.symbol.toLowerCase()}`} className="font-semibold hover:text-mint">
            {asset.symbol}
          </Link>
          <p className="text-xs text-ink/45">{asset.name}</p>
        </div>
        <span className={`rounded px-2 py-1 text-xs font-medium ${asset.total_trades > 0 ? "bg-mint/15 text-mint" : "bg-ink/10 text-ink/60"}`}>
          {asset.status}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <TradeMiniStat label="最高指标分" value={`${asset.best_opportunity_score}/100`} />
        <TradeMiniStat label="最佳方向" value={asset.best_signal} />
        <TradeMiniStat label="交易" value={`${asset.total_trades} 笔`} />
        <TradeMiniStat label="盈亏" value={formatCurrency(asset.total_pnl)} />
        <TradeMiniStat label="执行周期" value={formatInterval(asset.execution_interval)} />
        <TradeMiniStat label="K线数" value={`${asset.candle_count}`} />
      </div>
    </div>
  );
}

function BacktestRulesSection({ rules }: { rules: BacktestRules }) {
  return (
    <section className="mt-8 rounded border border-ink/10 bg-white p-5">
      <div className="mb-4">
        <p className="text-sm font-medium uppercase tracking-wide text-ink/45">策略条件</p>
        <h2 className="mt-1 text-xl font-semibold">{rules.title}</h2>
        <p className="mt-2 text-sm text-ink/55">
          当前回测使用 {rules.version}，下面是本次回测真正采用的条件、做单逻辑和指标分析方式。
        </p>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <RuleList title="周期与数据" items={rules.timeframes} />
        <RuleList title="开仓硬条件" items={rules.entry_conditions} />
        <RuleList title="做多逻辑" items={rules.long_logic} />
        <RuleList title="做空逻辑" items={rules.short_logic} />
        <RuleList title="止损逻辑" items={rules.stop_loss_logic} />
        <RuleList title="止盈逻辑" items={rules.take_profit_logic} />
        <RuleList title="平仓逻辑" items={rules.exit_logic} />
        <RuleList title="风险说明" items={rules.risk_notes} />
      </div>
      <div className="mt-3">
        <RuleList title="指标怎么分析" items={rules.indicator_analysis} wide />
      </div>
    </section>
  );
}

function RuleList({ title, items, wide = false }: { title: string; items: string[]; wide?: boolean }) {
  return (
    <div className={`rounded border border-ink/10 bg-panel p-4 ${wide ? "lg:col-span-2" : ""}`}>
      <h3 className="font-semibold text-ink">{title}</h3>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-ink/65">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-mint" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BacktestRunHistory({ runs }: { runs: BacktestRun[] }) {
  if (!runs.length) {
    return null;
  }

  return (
    <section className="mt-8 rounded border border-ink/10 bg-white p-5">
      <div className="mb-4">
        <h2 className="text-lg font-semibold">最近回测记录</h2>
        <p className="mt-1 text-sm text-ink/55">每次完整回测都会生成编号并保存到数据库，后面可以按编号追溯当时的参数、规则和结果。</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-panel text-xs uppercase tracking-wide text-ink/55">
            <tr>
              <th className="px-3 py-3">编号</th>
              <th className="px-3 py-3">周期</th>
              <th className="px-3 py-3">策略</th>
              <th className="px-3 py-3">交易</th>
              <th className="px-3 py-3">胜率</th>
              <th className="px-3 py-3">盈亏</th>
              <th className="px-3 py-3">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {runs.map((run) => (
              <tr key={run.id}>
                <td className="px-3 py-3 font-mono text-xs text-ink">{run.run_key}</td>
                <td className="px-3 py-3">{run.days}天 · {formatInterval(run.execution_interval)}</td>
                <td className="px-3 py-3">{run.strategy_version}</td>
                <td className="px-3 py-3 tabular-nums">{run.total_trades} 笔</td>
                <td className="px-3 py-3 tabular-nums">{run.win_rate}%</td>
                <td className={`px-3 py-3 font-semibold tabular-nums ${run.total_pnl >= 0 ? "text-mint" : "text-coral"}`}>
                  {formatCurrencyExact(run.total_pnl)}
                </td>
                <td className="px-3 py-3 text-xs text-ink/55">{formatDateTime(run.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function normalizeDays(value?: string): number | null {
  const parsed = Number(value);
  if (parsed === 30 || parsed === 60 || parsed === 180) {
    return parsed;
  }
  if (parsed > 180) {
    return 180;
  }
  return null;
}

function normalizeInterval(value?: string): string {
  return "15m";
}

function normalizeVersion(value?: string): string {
  if (value === "v1" || value === "v2" || value === "v3") {
    return value;
  }
  return "v3";
}

function formatInterval(value: string): string {
  if (value === "15m") {
    return "15分钟";
  }
  if (value === "1h") {
    return "1小时";
  }
  if (value === "1h+4h") {
    return "1小时 + 4小时";
  }
  return "4小时";
}

function formatCurrencyExact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function BacktestTradeCard({ trade }: { trade: BacktestTrade }) {
  return (
    <div className="rounded border border-ink/10 bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <Link href={`/asset/${trade.symbol.toLowerCase()}`} className="font-semibold hover:text-mint">
            {trade.symbol}
          </Link>
          <p className="text-xs text-ink/45">{trade.name}</p>
        </div>
        <span className={`rounded px-2 py-1 text-xs font-medium ${trade.side === "做多" ? "bg-mint/15 text-mint" : "bg-coral/15 text-coral"}`}>
          {trade.side}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <TradeMiniStat label="开仓" value={formatCurrency(trade.entry_price)} />
        <TradeMiniStat label="平仓" value={trade.exit_price ? formatCurrency(trade.exit_price) : "暂无"} />
        <TradeMiniStat label="止盈" value={trade.take_profit ? formatCurrency(trade.take_profit) : "暂无"} />
        <TradeMiniStat label="止损" value={trade.stop_loss ? formatCurrency(trade.stop_loss) : "暂无"} />
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-sm">
        <span className="text-ink/55">{trade.close_reason ?? "平仓"} · {trade.opportunity_score}/100</span>
        <span className={`font-semibold tabular-nums ${trade.pnl_usdt >= 0 ? "text-mint" : "text-coral"}`}>
          {formatCurrency(trade.pnl_usdt)} / {trade.pnl_percent >= 0 ? "+" : ""}{trade.pnl_percent}%
        </span>
      </div>
      <TradeLogicDetail trade={trade} compact />
    </div>
  );
}

function TradeLogicDetail({ trade, compact = false }: { trade: BacktestTrade; compact?: boolean }) {
  const snapshotEntries = formatSnapshotEntries(trade.indicator_snapshot);
  return (
    <div className={`mt-3 rounded border border-ink/10 bg-white p-3 ${compact ? "text-xs" : "text-sm"}`}>
      <div className="grid gap-3 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded bg-mint/15 px-2 py-1 text-xs font-medium text-mint">{trade.strategy_type ?? "策略未记录"}</span>
            <span className="rounded bg-gold/15 px-2 py-1 text-xs font-medium text-ink">{trade.market_regime ?? "结构未记录"}</span>
          </div>
          <p className="mt-3 leading-6 text-ink/70">{trade.opening_logic ?? "暂无开单逻辑说明"}</p>
          {trade.entry_reasons?.length ? (
            <ul className="mt-3 space-y-1 leading-5 text-ink/60">
              {trade.entry_reasons.map((reason) => (
                <li key={reason} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-mint" />
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="rounded bg-panel p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink/45">指标快照</p>
          <div className="grid grid-cols-2 gap-2">
            {snapshotEntries.map(([key, value]) => (
              <div key={key} className="min-w-0">
                <p className="text-[11px] text-ink/40">{key}</p>
                <p className="break-words font-medium text-ink">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatSnapshotEntries(snapshot: Record<string, unknown> | null | undefined): [string, string][] {
  if (!snapshot || Object.keys(snapshot).length === 0) {
    return [["说明", "暂无指标快照"]];
  }
  const labels: Record<string, string> = {
    price: "开仓价",
    one_hour_direction: "1H方向",
    four_hour_direction: "4H方向",
    market_regime: "日线结构",
    support: "支撑",
    resistance: "阻力",
    fib_supports: "斐波支撑",
    fib_resistances: "斐波阻力",
    dt_upper: "DT上轨",
    dt_lower: "DT下轨",
    ema50: "EMA50",
    ema100: "EMA100",
    ema144: "Vegas EMA144",
    ema169: "Vegas EMA169",
    ema200: "EMA200",
    near_support: "靠近支撑",
    near_resistance: "靠近阻力",
    near_fib_support: "靠近斐波支撑",
    near_fib_resistance: "靠近斐波阻力",
    double_bottom: "双底",
    double_top: "双顶",
    volume_to_market_cap_percent: "量价过滤",
    risk_reward_ratio: "计划盈亏比",
    strategy_type: "策略类型",
    signal_detail: "开仓信号",
    trend_filter_detail: "方向过滤",
    daily_ema_detail: "日线EMA",
    vegas_detail: "Vegas通道",
    dt_detail: "DT通道",
    fib_detail: "斐波那契",
    support_resistance_detail: "支撑阻力",
    structure_detail: "结构形态",
    volume_filter_detail: "量价过滤详情",
    risk_plan_detail: "止盈止损计划",
    entry_reason_detail: "入场原因汇总",
    note: "说明",
  };
  return Object.entries(snapshot).map(([key, value]) => [labels[key] ?? key, formatSnapshotValue(value)]);
}

function formatSnapshotValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => formatSnapshotValue(item)).join(" / ");
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? `${value}` : value.toFixed(Math.abs(value) < 1 ? 6 : 4).replace(/0+$/, "").replace(/\.$/, "");
  }
  if (value === null || value === undefined || value === "") {
    return "暂无";
  }
  return String(value);
}

function TradeMiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-panel p-3">
      <p className="text-xs text-ink/45">{label}</p>
      <p className="mt-1 break-words font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
}

function BacktestStat({ label, value, tone = "ink" }: { label: string; value: string; tone?: "ink" | "mint" | "coral" }) {
  const color = tone === "mint" ? "text-mint" : tone === "coral" ? "text-coral" : "text-ink";
  return (
    <div className="min-w-0 rounded border border-ink/10 bg-white/80 p-3 sm:p-4">
      <p className="text-xs font-medium text-ink/50">{label}</p>
      <p className={`mt-2 break-words text-xl font-semibold tabular-nums sm:text-2xl ${color}`}>{value}</p>
    </div>
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

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
