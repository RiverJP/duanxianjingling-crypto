import Link from "next/link";
import { Calculator, ChevronLeft, Target } from "lucide-react";
import { Asset, OhlcCandle } from "@/types/asset";
import { formatCompactCurrency, formatCurrency, formatPercent } from "@/lib/format";
import { MetricCard } from "@/components/MetricCard";
import { ScoreBar } from "@/components/ScoreBar";
import { TechnicalChart } from "@/components/TechnicalChart";
import { TechnicalParameters } from "@/components/TechnicalParameters";

export function AssetDetail({ asset, candles }: { asset: Asset; candles: OhlcCandle[] }) {
  const volumeToCap = asset.market_cap > 0 ? asset.volume_24h / asset.market_cap : 0;
  const volatilityPenalty = Math.min(Math.abs(asset.change_24h) * 3, 35);
  const riskDiscount = asset.liquidity_score * 0.15;
  const riskReverse = 100 - asset.risk_score;
  const riskPct = Math.max(0.015, Math.min(0.08, (asset.risk_score / 100) * 0.06));
  const rewardPct = riskPct * (1.45 + asset.liquidity_score / 160);
  const calculatedTrend = clampScore(50 + asset.change_24h * 4);
  const calculatedLiquidity = clampScore(45 + volumeToCap * 500);
  const calculatedRisk = clampScore(55 + volatilityPenalty - riskDiscount);
  const calculatedAi = clampScore(asset.trend_score * 0.4 + asset.liquidity_score * 0.35 + riskReverse * 0.25);
  const calculatedOpportunity = clampScore(asset.ai_score * 0.35 + asset.trend_score * 0.3 + asset.liquidity_score * 0.2 + riskReverse * 0.15);
  const longChecks = [
    { label: "趋势分 >= 62", passed: asset.trend_score >= 62 },
    { label: "24 小时涨幅 > 0", passed: asset.change_24h > 0 },
    { label: "AI 评分 >= 55", passed: asset.ai_score >= 55 },
    { label: "风险分 < 78", passed: asset.risk_score < 78 },
    { label: "流动性分 >= 40", passed: asset.liquidity_score >= 40 },
  ];
  const shortChecks = [
    { label: "趋势分 <= 42", passed: asset.trend_score <= 42 },
    { label: "24 小时跌幅 < 0", passed: asset.change_24h < 0 },
    { label: "AI 评分 <= 52", passed: asset.ai_score <= 52 },
    { label: "风险分 < 72", passed: asset.risk_score < 72 },
    { label: "流动性分 >= 40", passed: asset.liquidity_score >= 40 },
  ];

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <Link href="/" className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-ink/65 hover:text-ink">
        <ChevronLeft size={16} />
        返回仪表盘
      </Link>

      <section className="mb-8 flex flex-col justify-between gap-4 border-b border-ink/10 pb-8 md:flex-row md:items-end">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-ink/50">{asset.symbol}</p>
          <h1 className="mt-2 text-4xl font-semibold">{asset.name}</h1>
        </div>
        <div className={`text-xl font-semibold ${asset.change_24h >= 0 ? "text-mint" : "text-coral"}`}>
          {formatPercent(asset.change_24h)} / 24 小时
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <MetricCard label="当前价格" value={formatCurrency(asset.current_price)} accent="mint" />
        <MetricCard label="市值" value={formatCompactCurrency(asset.market_cap)} />
        <MetricCard label="24 小时成交量" value={formatCompactCurrency(asset.volume_24h)} />
        <MetricCard label="AI 评分" value={`${asset.ai_score}/100`} accent="gold" />
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-5">
        <MetricCard label="交易方向" value={asset.trade_signal} accent={asset.trade_signal === "做多" ? "mint" : asset.trade_signal === "做空" ? "coral" : "ink"} />
        <MetricCard label="参考入场" value={asset.entry_price ? formatCurrency(asset.entry_price) : "等待"} />
        <MetricCard label="止盈" value={asset.take_profit ? formatCurrency(asset.take_profit) : "暂无"} accent="gold" />
        <MetricCard label="止损" value={asset.stop_loss ? formatCurrency(asset.stop_loss) : "暂无"} accent="coral" />
        <MetricCard label="盈亏比" value={asset.risk_reward_ratio ? `${asset.risk_reward_ratio}:1` : "暂无"} />
      </section>

      <section className="mt-8 rounded border border-ink/10 bg-white p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Target size={18} />
            <h2 className="text-lg font-semibold">每日开单机会</h2>
          </div>
          <span className={`rounded px-3 py-1 text-sm font-medium ${asset.opportunity_status === "高优先级" ? "bg-gold/20 text-ink" : asset.opportunity_status === "可关注" ? "bg-mint/15 text-mint" : "bg-panel text-ink/60"}`}>
            {asset.opportunity_status} · {asset.opportunity_score}/100
          </span>
        </div>
        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard label="机会方向" value={asset.opportunity_type} accent={asset.opportunity_type === "做多" ? "mint" : asset.opportunity_type === "做空" ? "coral" : "ink"} />
          <MetricCard label="触发价" value={asset.trigger_price ? formatCurrency(asset.trigger_price) : "等待"} accent="gold" />
          <MetricCard label="失效价" value={asset.invalid_price ? formatCurrency(asset.invalid_price) : "暂无"} accent="coral" />
          <MetricCard label="参考入场" value={asset.entry_price ? formatCurrency(asset.entry_price) : "等待"} />
        </div>
        <p className="mt-4 leading-7 text-ink/70">{asset.opportunity_reason || asset.trade_rationale}</p>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.25fr]">
        <div className="rounded border border-ink/10 bg-white p-5">
          <h2 className="mb-5 text-lg font-semibold">信号评分</h2>
          <div className="space-y-5">
            <ScoreBar label="趋势" value={asset.trend_score} tone="mint" />
            <ScoreBar label="流动性" value={asset.liquidity_score} tone="gold" />
            <ScoreBar label="风险" value={asset.risk_score} tone="coral" />
          </div>
        </div>
        <div className="rounded border border-ink/10 bg-white p-5">
          <h2 className="mb-3 text-lg font-semibold">AI 摘要</h2>
          <p className="leading-7 text-ink/70">{asset.ai_summary}</p>
          <div className="mt-5 border-t border-ink/10 pt-5">
            <h3 className="text-sm font-semibold text-ink">交易计划逻辑</h3>
            <p className="mt-2 leading-7 text-ink/70">{asset.trade_rationale}</p>
          </div>
          <p className="mt-5 text-xs text-ink/45">
            数据源更新时间：{asset.source_updated_at ? new Date(asset.source_updated_at).toLocaleString("zh-CN") : "暂无"}
          </p>
        </div>
      </section>

      <section className="mt-8 rounded border border-ink/10 bg-white p-5">
        <div className="mb-5 flex items-center gap-2">
          <Calculator size={18} />
          <h2 className="text-lg font-semibold">评分逻辑</h2>
        </div>

        <div className="mb-4 rounded border border-ink/10 bg-panel/60 p-4 text-sm leading-6 text-ink/70">
          <p className="font-medium text-ink">当前版本定位：市场初筛，不是最终开单确认。</p>
          <p className="mt-2">
            当前评分主要基于 24 小时价格动量、市值、24 小时成交量和风险控制，适合先从 100 个标的里筛出值得看的币。下方 4 小时 K 线、Vegas、MA、支撑阻力用于进一步确认。
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded border border-ink/10 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">1. 趋势分</h3>
              <span className="rounded bg-mint/15 px-2 py-1 text-sm font-semibold text-mint">{asset.trend_score}/100</span>
            </div>
            <div className="space-y-2 text-sm leading-6 text-ink/70">
              <p>用途：衡量 24 小时动量强弱，越高越偏多，越低越偏空。</p>
              <p>公式：趋势分 = 50 + 24h涨跌幅 * 4，结果限制在 0 到 100。</p>
              <p>当前：50 + {asset.change_24h.toFixed(2)} * 4 = {calculatedTrend}/100。</p>
              <p>解释：{asset.symbol} 当前 24 小时为 {formatPercent(asset.change_24h)}，所以趋势分偏{asset.trend_score >= 62 ? "强，接近多头筛选区" : asset.trend_score <= 42 ? "弱，接近空头筛选区" : "中性，暂时更像观察区"}。</p>
            </div>
          </div>

          <div className="rounded border border-ink/10 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">2. 流动性分</h3>
              <span className="rounded bg-gold/20 px-2 py-1 text-sm font-semibold text-ink">{asset.liquidity_score}/100</span>
            </div>
            <div className="space-y-2 text-sm leading-6 text-ink/70">
              <p>用途：衡量这个币当天是否好进出，成交越活跃、滑点风险越低，分数越高。</p>
              <p>公式：流动性分 = 45 + (24h成交量 / 市值) * 500，结果限制在 0 到 100。</p>
              <p>当前成交量/市值 = {(volumeToCap * 100).toFixed(2)}%。</p>
              <p>当前：45 + {volumeToCap.toFixed(4)} * 500 = {calculatedLiquidity}/100。</p>
            </div>
          </div>

          <div className="rounded border border-ink/10 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">3. 风险分</h3>
              <span className="rounded bg-coral/15 px-2 py-1 text-sm font-semibold text-coral">{asset.risk_score}/100</span>
            </div>
            <div className="space-y-2 text-sm leading-6 text-ink/70">
              <p>用途：衡量当天波动是否过猛。风险分越高越危险，不是越高越好。</p>
              <p>公式：波动惩罚 = min(abs(24h涨跌幅) * 3, 35)。</p>
              <p>风险分 = 55 + 波动惩罚 - 流动性分 * 0.15，结果限制在 0 到 100。</p>
              <p>当前：波动惩罚 {volatilityPenalty.toFixed(2)}，流动性折扣 {riskDiscount.toFixed(2)}，风险分 = {calculatedRisk}/100。</p>
            </div>
          </div>

          <div className="rounded border border-ink/10 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">4. AI 评分</h3>
              <span className="rounded bg-gold/20 px-2 py-1 text-sm font-semibold text-ink">{asset.ai_score}/100</span>
            </div>
            <div className="space-y-2 text-sm leading-6 text-ink/70">
              <p>用途：把趋势、流动性和风险整合成一个质量分。当前不是 AI 读图评分，而是规则综合分。</p>
              <p>公式：AI评分 = 趋势分 * 40% + 流动性分 * 35% + 风险反向分 * 25%。</p>
              <p>风险反向分 = 100 - 风险分 = {riskReverse}。</p>
              <p>当前：{asset.trend_score} * 40% + {asset.liquidity_score} * 35% + {riskReverse} * 25% = {calculatedAi}/100。</p>
            </div>
          </div>

          <div className="rounded border border-ink/10 p-4 lg:col-span-2">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">5. 机会分与等级</h3>
              <span className="rounded bg-ink px-2 py-1 text-sm font-semibold text-white">{asset.opportunity_status} · {asset.opportunity_score}/100</span>
            </div>
            <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
              <div className="space-y-2 text-sm leading-6 text-ink/70">
                <p>用途：首页排序主要看机会分，用来判断今天是否值得点进详情页继续看。</p>
                <p>公式：机会分 = AI评分 * 35% + 趋势分 * 30% + 流动性分 * 20% + 风险反向分 * 15%。</p>
                <p>当前：{asset.ai_score} * 35% + {asset.trend_score} * 30% + {asset.liquidity_score} * 20% + {riskReverse} * 15% = {calculatedOpportunity}/100。</p>
              </div>
              <div className="rounded bg-panel p-3 text-sm leading-6 text-ink/70">
                <p>做多/做空 且 机会分 &gt;= 80：高优先级，并进入模拟开单观察</p>
                <p>做多/做空 且 机会分 &gt;= 75：可关注</p>
                <p>机会分 &gt;= 55 但方向不明确：等待触发</p>
                <p>低于 55：观察</p>
              </div>
            </div>
          </div>

          <div className="rounded border border-ink/10 p-4">
            <h3 className="text-sm font-semibold text-ink">6. 做多检查</h3>
            <div className="mt-3 space-y-2 text-sm leading-6 text-ink/70">
              {longChecks.map((check) => (
                <div key={check.label} className="flex items-center justify-between gap-3">
                  <span>{check.label}</span>
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${check.passed ? "bg-mint/15 text-mint" : "bg-ink/10 text-ink/55"}`}>
                    {check.passed ? "通过" : "未满足"}
                  </span>
                </div>
              ))}
              <p className="border-t border-ink/10 pt-2">
                若通过，触发价 = 当前价 * 1.003，表示向上突破约 0.3% 后再确认。
              </p>
            </div>
          </div>

          <div className="rounded border border-ink/10 p-4">
            <h3 className="text-sm font-semibold text-ink">7. 做空检查</h3>
            <div className="mt-3 space-y-2 text-sm leading-6 text-ink/70">
              {shortChecks.map((check) => (
                <div key={check.label} className="flex items-center justify-between gap-3">
                  <span>{check.label}</span>
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${check.passed ? "bg-mint/15 text-mint" : "bg-ink/10 text-ink/55"}`}>
                    {check.passed ? "通过" : "未满足"}
                  </span>
                </div>
              ))}
              <p className="border-t border-ink/10 pt-2">
                若通过，触发价 = 当前价 * 0.997，表示向下跌破约 0.3% 后再确认。
              </p>
            </div>
          </div>

          <div className="rounded border border-ink/10 p-4 lg:col-span-2">
            <h3 className="text-sm font-semibold text-ink">8. 止损止盈怎么估</h3>
            <div className="mt-3 grid gap-4 text-sm leading-6 text-ink/70 md:grid-cols-2">
              <div>
                <p>风险百分比 = max(1.5%, min(8%, 风险分/100 * 6%))。</p>
                <p>当前风险百分比约 {(riskPct * 100).toFixed(2)}%。风险分越高，止损距离越宽。</p>
              </div>
              <div>
                <p>奖励百分比 = 风险百分比 * (1.45 + 流动性分/160)。</p>
                <p>当前奖励百分比约 {(rewardPct * 100).toFixed(2)}%。流动性越好，目标空间会略放大。</p>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-4 text-xs leading-5 text-ink/45">
          这个评分目前用于市场初筛，偏日内到短线观察；真正开单仍需要结合下方 4 小时 K 线、Vegas、MA、支撑阻力和成交量确认。
        </p>
      </section>

      <TechnicalChart asset={asset} candles={candles} />
      <TechnicalParameters asset={asset} candles={candles} />
    </main>
  );
}

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}
