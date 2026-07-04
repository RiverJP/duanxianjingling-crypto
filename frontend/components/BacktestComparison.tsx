"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BacktestComparisonItem } from "@/types/asset";

export function BacktestComparison({ version }: { version: string }) {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<BacktestComparisonItem[]>([]);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`/api/backtest/comparison?interval=15m&mode=indicator&version=${version}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Unable to load backtest comparison");
        }
        return response.json();
      })
      .then((rows) => setItems(rows))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));

    return () => {
      controller.abort();
    };
  }, [version]);

  return (
    <section className="mt-8 rounded border border-ink/10 bg-white p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">15m 周期对比</h2>
          <p className="mt-1 text-sm text-ink/55">同一套指标策略，固定 15分钟执行开单，对比 1个月、2个月、6个月表现。</p>
        </div>
        <Link href={`/backtest?days=180&interval=15m&version=${version}`} className="text-sm font-medium text-mint hover:text-ink">
          查看 15m 明细
        </Link>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {(items.length ? items : fallbackItems()).map((item) => {
          if (item.summary) {
            return <ComparisonCard key={item.days} item={item} />;
          }
          return <ComparisonPlaceholder key={item.days} label={item.label} loading={loading} />;
        })}
      </div>
    </section>
  );
}

function ComparisonCard({ item }: { item: BacktestComparisonItem }) {
  const summary = item.summary;
  if (!summary) {
    return null;
  }
  const netPnl = summary.net_pnl ?? summary.total_pnl;
  const netPnlPercent = summary.net_pnl_percent ?? summary.total_pnl_percent;
  return (
    <Link
      href={`/backtest?days=${item.days}&interval=15m&version=v4`}
      className={`block rounded border p-4 transition hover:-translate-y-0.5 hover:shadow-sm ${
        summary.total_pnl >= 0 ? "border-mint/20 bg-mint/10" : "border-coral/20 bg-coral/10"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{item.label}</p>
          <p className="mt-1 text-xs text-ink/50">15分钟开单 · {formatInterval(summary.trend_interval)}过滤</p>
        </div>
        <span className="rounded bg-white px-2 py-1 text-xs font-medium text-ink/60">{summary.total_trades} 笔</span>
      </div>
      <p className={`mt-4 text-3xl font-semibold tabular-nums ${summary.total_pnl >= 0 ? "text-mint" : "text-coral"}`}>
        {formatCurrencyExact(summary.total_pnl)}
      </p>
      <p className={`mt-1 text-sm font-semibold tabular-nums ${netPnl >= 0 ? "text-mint" : "text-coral"}`}>
        扣费后 {formatCurrencyExact(netPnl)}
      </p>
      {item.source_days ? (
        <p className="mt-2 text-xs text-ink/50">
          {item.derived ? `由 ${formatPeriod(item.source_days)} 回测记录按时间切出` : "独立回测记录"}
        </p>
      ) : null}
      {summary.excluded_period_end_trades > 0 ? (
        <p className="mt-1 text-xs text-ink/50">已排除期末平仓 {summary.excluded_period_end_trades} 笔</p>
      ) : null}
      {summary.excluded_low_risk_reward_trades > 0 ? (
        <p className="mt-1 text-xs text-ink/50">已排除低盈亏比 {summary.excluded_low_risk_reward_trades} 笔</p>
      ) : null}
      {summary.excluded_portfolio_trades > 0 ? (
        <p className="mt-1 text-xs text-ink/50">保证金过滤 {summary.excluded_portfolio_trades} 笔</p>
      ) : null}
      <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
        <MiniStat label="收益率" value={`${summary.total_pnl_percent >= 0 ? "+" : ""}${summary.total_pnl_percent}%`} />
        <MiniStat label="扣费后" value={`${netPnlPercent >= 0 ? "+" : ""}${netPnlPercent}%`} />
        <MiniStat label="胜率" value={`${summary.win_rate}%`} />
      </div>
    </Link>
  );
}

function ComparisonPlaceholder({ label, loading }: { label: string; loading: boolean }) {
  return (
    <div className="rounded border border-ink/10 bg-panel p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <p className="mt-1 text-xs text-ink/50">15分钟开单</p>
      <p className="mt-4 text-2xl font-semibold text-ink/35">{loading ? "计算中" : "暂无"}</p>
      <p className="mt-3 text-sm leading-5 text-ink/50">
        {loading ? "正在读取历史记录，完成后自动显示。" : "该周期还没有保存过回测结果。"}
      </p>
    </div>
  );
}

function fallbackItems(): BacktestComparisonItem[] {
  return [
    { days: 30, label: "1个月", source_run_key: null, source_days: null, derived: false, summary: null },
    { days: 60, label: "2个月", source_run_key: null, source_days: null, derived: false, summary: null },
    { days: 180, label: "6个月", source_run_key: null, source_days: null, derived: false, summary: null },
  ];
}

function formatPeriod(days: number): string {
  if (days === 30) {
    return "1个月";
  }
  if (days === 60) {
    return "2个月";
  }
  return "6个月";
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-white/75 p-2">
      <p className="text-xs text-ink/45">{label}</p>
      <p className="mt-1 font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
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
