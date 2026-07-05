import Link from "next/link";
import { Activity, Calculator, ChevronLeft, Compass, GitBranch, Target } from "lucide-react";
import { Asset, OhlcCandle } from "@/types/asset";
import { formatCompactCurrency, formatCurrency, formatPercent } from "@/lib/format";
import { MetricCard } from "@/components/MetricCard";
import { ScoreBar } from "@/components/ScoreBar";
import { TechnicalChart } from "@/components/TechnicalChart";

export function AssetDetail({ asset, candles }: { asset: Asset; candles: OhlcCandle[] }) {
  const strategyContext = buildStrategyContext(asset, candles);
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
  const calculatedShortOpportunity = clampScore((100 - asset.ai_score) * 0.35 + (100 - asset.trend_score) * 0.3 + asset.liquidity_score * 0.2 + riskReverse * 0.15);
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
    { label: "空头方向分 >= 55", passed: calculatedShortOpportunity >= 55 },
    { label: "风险分 < 78", passed: asset.risk_score < 78 },
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
        <MetricCard label="当前计划盈亏比" value={asset.risk_reward_ratio ? `${asset.risk_reward_ratio}:1` : "暂无"} />
      </section>

      <StrategyFramework asset={asset} context={strategyContext} />

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
                空头方向分 = (100 - AI) * 35% + (100 - 趋势) * 30% + 流动性 * 20% + 风险反向 * 15%，当前为 {calculatedShortOpportunity}/100。
              </p>
              <p>
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
    </main>
  );
}

type StrategyContext = {
  dailyRegime: string;
  preferredDirection: string;
  strategyType: string;
  volumePrice: string;
  trendLine: string;
  emaState: string;
  vegasState: string;
  dtState: string;
  fibState: string;
  structureState: string;
  supportResistance: string;
  longAllowed: boolean;
  shortAllowed: boolean;
  reasons: string[];
};

function StrategyFramework({ asset, context }: { asset: Asset; context: StrategyContext }) {
  const rows = [
    { label: "日线大趋势", value: context.dailyRegime, detail: "由 4H K线合成日线，先判断牛熊与震荡。" },
    { label: "优先方向", value: context.preferredDirection, detail: "上升趋势优先多，下降趋势优先空，震荡区间看边界。" },
    { label: "策略类型", value: context.strategyType, detail: "趋势单、趋势里的区间单、纯区间单分开处理。" },
    { label: "量价关系", value: context.volumePrice, detail: "用4H K线价格变化和真实成交量序列判断放量/缩量。" },
    { label: "趋势线", value: context.trendLine, detail: "近60根4H回归线，判断价格路径斜率。" },
    { label: "EMA 均线", value: context.emaState, detail: "EMA50/100/200 判断价格在均线系统中的位置。" },
    { label: "Vegas 通道", value: context.vegasState, detail: "EMA144/169 看中期通道，多空最好顺通道。" },
    { label: "DT 指标", value: context.dtState, detail: "靠近上轨看突破或压力，靠近下轨看支撑或破位。" },
    { label: "斐波那契", value: context.fibState, detail: "近90根高低点回撤，判断回踩/反弹关键区。" },
    { label: "结构", value: context.structureState, detail: "双底偏多，双顶偏空，无结构则降低确定性。" },
    { label: "支撑阻力", value: context.supportResistance, detail: "上升趋势回踩支撑可做多，下降趋势反弹阻力可做空。" },
  ];

  return (
    <section className="mt-8 rounded border border-ink/10 bg-white p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Compass size={18} />
          <h2 className="text-lg font-semibold">多空策略框架</h2>
        </div>
        <span className={`rounded px-3 py-1 text-sm font-semibold ${asset.trade_signal === "做多" ? "bg-mint/15 text-mint" : asset.trade_signal === "做空" ? "bg-coral/15 text-coral" : "bg-panel text-ink/60"}`}>
          当前系统方向：{asset.trade_signal}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded border border-ink/10 bg-panel/60 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Activity size={16} />
            当前结论
          </div>
          <p className="mt-3 text-2xl font-semibold">{context.preferredDirection}</p>
          <p className="mt-2 text-sm leading-6 text-ink/65">
            {context.dailyRegime} · {context.strategyType}。这里展示后台 v6 确认指标策略当前保存的方向、结构和风控结论，和上方交易方向保持同一套口径。
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <DecisionBadge label="做多条件" passed={context.longAllowed} />
            <DecisionBadge label="做空条件" passed={context.shortAllowed} />
          </div>
          <div className="mt-4 rounded bg-white p-3 text-sm leading-6 text-ink/70">
            {context.reasons.map((reason) => (
              <p key={reason}>• {reason}</p>
            ))}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {rows.map((row) => (
            <div key={row.label} className="rounded border border-ink/10 p-3">
              <div className="mb-2 flex items-start justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink/45">{row.label}</p>
                <GitBranch size={14} className="shrink-0 text-ink/30" />
              </div>
              <p className="font-semibold text-ink">{row.value}</p>
              <p className="mt-1 text-xs leading-5 text-ink/55">{row.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function DecisionBadge({ label, passed }: { label: string; passed: boolean }) {
  return (
    <div className={`rounded border px-3 py-2 ${passed ? "border-mint/25 bg-mint/10 text-mint" : "border-ink/10 bg-white text-ink/55"}`}>
      <p className="text-xs text-ink/45">{label}</p>
      <p className="mt-1 font-semibold">{passed ? "允许" : "过滤"}</p>
    </div>
  );
}

function buildStrategyContext(asset: Asset, candles: OhlcCandle[]): StrategyContext {
  const current = asset.current_price || candles.at(-1)?.close || 0;
  const dailyRegime = asset.market_cycle && asset.market_cycle !== "数据不足" ? asset.market_cycle : "等待K线结构确认";
  const preferredDirection = asset.trade_signal === "做多" ? "当前策略做多" : asset.trade_signal === "做空" ? "当前策略做空" : "当前观望";
  const strategyType = extractStrategyType(asset.opportunity_reason) || extractStrategyType(asset.trade_rationale) || (asset.trade_signal === "观望" ? "未触发v6开仓" : "v6确认指标策略");
  const support = asset.support_level;
  const resistance = asset.resistance_level;
  const fibText = fibLevelsText(asset);
  const reasons = buildSavedStrategyReasons(asset);

  return {
    dailyRegime,
    preferredDirection,
    strategyType,
    volumePrice: asset.volume_price_relation || "等待4H成交量序列",
    trendLine: asset.trend_line || "趋势线数据不足",
    emaState: emaState(current, asset.ma_50, asset.ma_100, asset.ma_200),
    vegasState: asset.vegas_signal || vegasState(current, asset.vegas_fast, asset.vegas_slow),
    dtState: dtState(current, asset.dt_upper, asset.dt_lower),
    fibState: fibText,
    structureState: extractStructureState(asset.opportunity_reason || asset.trade_rationale),
    supportResistance: `支撑 ${support ? formatCurrency(support) : "暂无"} / 阻力 ${resistance ? formatCurrency(resistance) : "暂无"}`,
    longAllowed: asset.trade_signal === "做多",
    shortAllowed: asset.trade_signal === "做空",
    reasons,
  };
}

function extractStrategyType(text: string | null | undefined): string | null {
  if (!text) {
    return null;
  }
  const match = text.match(/v[356](?:精选|确认)?指标策略[:：]([^。；]+)/);
  if (match?.[1]) {
    return match[1].trim();
  }
  const fallback = text.match(/策略类型(?:为|=)([^。；，,]+)/);
  return fallback?.[1]?.trim() || null;
}

function extractStructureState(text: string | null | undefined): string {
  if (!text) {
    return "等待结构确认";
  }
  if (text.includes("双底")) {
    return "双底结构，偏多确认";
  }
  if (text.includes("双顶")) {
    return "双顶结构，偏空确认";
  }
  if (text.includes("靠近支撑")) {
    return "靠近支撑区域";
  }
  if (text.includes("靠近阻力")) {
    return "靠近阻力区域";
  }
  return "暂无明确双底/双顶";
}

function fibLevelsText(asset: Asset): string {
  const levels = [asset.fib_382, asset.fib_500, asset.fib_618].filter((value): value is number => Boolean(value));
  if (!levels.length) {
    return "Fib数据不足";
  }
  return `Fib 38.2/50/61.8：${levels.map((level) => formatCurrency(level)).join(" / ")}`;
}

function buildSavedStrategyReasons(asset: Asset): string[] {
  const source = asset.opportunity_reason || asset.trade_rationale;
  if (!source) {
    return ["等待 v6 确认指标策略刷新。"];
  }
  const cleaned = source.replace(/^v[356](?:精选|确认)?指标策略[:：][^。]*。?/, "");
  const items = cleaned.split(/[；。]/).map((item) => item.trim()).filter(Boolean);
  if (items.length) {
    return items.slice(0, 5);
  }
  return [source];
}

function emaValue(values: number[], period: number): number | null {
  if (values.length < period) {
    return null;
  }
  const multiplier = 2 / (period + 1);
  let value = values.slice(0, period).reduce((sum, item) => sum + item, 0) / period;
  for (const price of values.slice(period)) {
    value = price * multiplier + value * (1 - multiplier);
  }
  return value;
}

function nearLevel(price: number, level: number | null | undefined, tolerance: number) {
  return Boolean(level && price > 0 && Math.abs(price - level) / price <= tolerance);
}

function emaState(price: number, ema50: number | null, ema100: number | null, ema200: number | null): string {
  if (!ema50 || !ema100) {
    return "EMA数据不足";
  }
  if (price > ema50 && ema50 > ema100 && (!ema200 || ema100 > ema200)) {
    return "多头排列，价格在均线上方";
  }
  if (price < ema50 && ema50 < ema100 && (!ema200 || ema100 < ema200)) {
    return "空头排列，价格在均线下方";
  }
  return "均线缠绕，趋势不够干净";
}

function vegasState(price: number, ema144: number | null, ema169: number | null): string {
  if (!ema144 || !ema169) {
    return "Vegas数据不足";
  }
  const upper = Math.max(ema144, ema169);
  const lower = Math.min(ema144, ema169);
  if (price > upper) {
    return "价格在Vegas通道上方，偏多";
  }
  if (price < lower) {
    return "价格在Vegas通道下方，偏空";
  }
  return "价格在Vegas通道内，等待方向";
}

function dtState(price: number, upper: number | null, lower: number | null): string {
  if (!upper || !lower) {
    return "DT数据不足";
  }
  if (price >= upper) {
    return "价格接近或突破DT上轨";
  }
  if (price <= lower) {
    return "价格接近或跌破DT下轨";
  }
  return "价格在DT通道内部";
}

function fibState(price: number, high: number | null, low: number | null): string {
  if (!high || !low || high <= low) {
    return "Fib数据不足";
  }
  const range = high - low;
  const supports = [high - range * 0.382, high - range * 0.5, high - range * 0.618];
  const resistances = [low + range * 0.382, low + range * 0.5, low + range * 0.618];
  if (supports.some((level) => nearLevel(price, level, 0.03))) {
    return "靠近Fib回撤支撑区";
  }
  if (resistances.some((level) => nearLevel(price, level, 0.03))) {
    return "靠近Fib反弹压力区";
  }
  return "不在核心Fib区域";
}

function volumePriceState(change24h: number, volumeToCap: number): string {
  const active = volumeToCap >= 0.08;
  if (change24h > 0 && active) {
    return "放量上涨，偏多确认";
  }
  if (change24h < 0 && active) {
    return "放量下跌，偏空确认";
  }
  if (change24h > 0) {
    return "缩量上涨，追多谨慎";
  }
  if (change24h < 0) {
    return "缩量下跌，追空谨慎";
  }
  return "量价中性";
}

function hasDoubleBottom(candles: OhlcCandle[]): boolean {
  if (candles.length < 20) {
    return false;
  }
  const lows = candles.map((candle) => candle.low);
  const closes = candles.map((candle) => candle.close);
  const firstLow = Math.min(...lows.slice(0, -8));
  const firstIndex = lows.indexOf(firstLow);
  const secondLow = Math.min(...lows.slice(firstIndex + 5));
  const neckline = Math.max(...closes.slice(firstIndex, Math.max(firstIndex + 6, candles.length - 3)));
  return Math.abs(secondLow - firstLow) / Math.max(firstLow, 0.00000001) <= 0.035 && closes.at(-1)! > neckline;
}

function hasDoubleTop(candles: OhlcCandle[]): boolean {
  if (candles.length < 20) {
    return false;
  }
  const highs = candles.map((candle) => candle.high);
  const closes = candles.map((candle) => candle.close);
  const firstHigh = Math.max(...highs.slice(0, -8));
  const firstIndex = highs.indexOf(firstHigh);
  const secondHigh = Math.max(...highs.slice(firstIndex + 5));
  const neckline = Math.min(...closes.slice(firstIndex, Math.max(firstIndex + 6, candles.length - 3)));
  return Math.abs(secondHigh - firstHigh) / Math.max(firstHigh, 0.00000001) <= 0.035 && closes.at(-1)! < neckline;
}

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}
