"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { formatCurrency } from "@/lib/format";
import { BacktestTrade, BacktestTradesPage } from "@/types/asset";

const PAGE_SIZE = 50;

type Filters = {
  symbol: string;
  side: string;
  result: string;
  strategyType: string;
};

const EMPTY_FILTERS: Filters = {
  symbol: "",
  side: "",
  result: "",
  strategyType: "",
};

export function BacktestTradesExplorer({ days, interval, totalTrades, version }: { days: number; interval: string; totalTrades: number; version: string }) {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [data, setData] = useState<BacktestTradesPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams({
      days: String(days),
      interval,
      mode: "indicator",
      version,
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (filters.symbol) params.set("symbol", filters.symbol);
    if (filters.side) params.set("side", filters.side);
    if (filters.result) params.set("result", filters.result);
    if (filters.strategyType) params.set("strategy_type", filters.strategyType);
    return params.toString();
  }, [days, interval, version, page, filters]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetch(`/api/backtest/trades?${query}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Unable to load backtest trades");
        }
        return response.json();
      })
      .then((payload: BacktestTradesPage) => setData(payload))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError("交易记录加载失败，请稍后刷新。");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [query]);

  const options = data?.filter_options ?? { symbols: [], sides: [], results: [], strategy_types: [] };

  function updateFilter(key: keyof Filters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  return (
    <section className="mt-8">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">严格开仓交易记录</h2>
          <p className="mt-1 text-sm text-ink/55">
            全部 {totalTrades} 笔交易按分页加载，可按标的、方向、结果和策略类型筛选，每笔都保留完整开单逻辑。
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setFilters(EMPTY_FILTERS);
            setPage(1);
          }}
          className="rounded border border-ink/10 bg-white px-3 py-2 text-sm font-medium text-ink/60 hover:text-ink"
        >
          清空筛选
        </button>
      </div>

      <div className="mb-4 grid gap-3 rounded border border-ink/10 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
        <FilterSelect label="标的" value={filters.symbol} options={options.symbols} onChange={(value) => updateFilter("symbol", value)} />
        <FilterSelect label="方向" value={filters.side} options={options.sides} onChange={(value) => updateFilter("side", value)} />
        <FilterSelect label="结果" value={filters.result} options={options.results} onChange={(value) => updateFilter("result", value)} />
        <FilterSelect label="策略类型" value={filters.strategyType} options={options.strategy_types} onChange={(value) => updateFilter("strategyType", value)} />
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded border border-ink/10 bg-panel px-4 py-3 text-sm text-ink/60">
        <span>
          {loading ? "加载中..." : `当前筛选 ${data?.total ?? 0} 笔，第 ${data?.page ?? page} / ${data?.total_pages ?? 1} 页`}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={loading || page <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            className="rounded border border-ink/10 bg-white px-3 py-2 font-medium text-ink/60 disabled:cursor-not-allowed disabled:opacity-40"
          >
            上一页
          </button>
          <button
            type="button"
            disabled={loading || page >= (data?.total_pages ?? 1)}
            onClick={() => setPage((value) => value + 1)}
            className="rounded border border-ink/10 bg-white px-3 py-2 font-medium text-ink/60 disabled:cursor-not-allowed disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>

      {error ? <div className="rounded border border-coral/30 bg-coral/10 p-4 text-sm text-coral">{error}</div> : null}

      {!loading && !data?.trades.length ? (
        <div className="rounded border border-ink/10 bg-white p-8 text-sm text-ink/60">当前筛选下没有交易记录。</div>
      ) : null}

      <div className="space-y-3 md:hidden">
        {(data?.trades ?? []).map((trade, index) => (
          <BacktestTradeCard key={`${trade.symbol}-${trade.opened_at}-${index}`} trade={trade} />
        ))}
      </div>

      <div className="hidden overflow-x-auto rounded border border-ink/10 bg-white md:block">
        <table className="w-full min-w-[1200px] text-left text-sm">
          <thead className="bg-panel text-xs uppercase tracking-wide text-ink/55">
            <tr>
              <th className="px-4 py-3">标的</th>
              <th className="px-4 py-3">方向</th>
              <th className="px-4 py-3">开仓 / 平仓</th>
              <th className="px-4 py-3">止盈 / 止损</th>
              <th className="px-4 py-3">盈亏比</th>
              <th className="px-4 py-3">指标分</th>
              <th className="px-4 py-3">结果</th>
              <th className="px-4 py-3">盈亏</th>
              <th className="px-4 py-3">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {(data?.trades ?? []).map((trade, index) => (
              <TradeRow key={`${trade.symbol}-${trade.opened_at}-${index}`} trade={trade} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/45">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded border border-ink/10 bg-panel px-3 py-2 text-sm text-ink outline-none focus:border-mint"
      >
        <option value="">全部</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function TradeRow({ trade }: { trade: BacktestTrade }) {
  return (
    <>
      <tr>
        <td className="px-4 py-4 font-medium">
          <Link href={`/asset/${trade.symbol.toLowerCase()}`} className="hover:text-mint">
            {trade.symbol}
          </Link>
          <div className="text-xs text-ink/45">{trade.name}</div>
        </td>
        <td className="px-4 py-4">{trade.side}</td>
        <td className="px-4 py-4 tabular-nums">{formatCurrency(trade.entry_price)} / {trade.exit_price ? formatCurrency(trade.exit_price) : "暂无"}</td>
        <td className="px-4 py-4 tabular-nums">{trade.take_profit ? formatCurrency(trade.take_profit) : "暂无"} / {trade.stop_loss ? formatCurrency(trade.stop_loss) : "暂无"}</td>
        <td className="px-4 py-4 font-semibold tabular-nums">{formatRiskReward(trade)}</td>
        <td className="px-4 py-4 tabular-nums">{trade.opportunity_score}/100</td>
        <td className="px-4 py-4">{trade.close_reason ?? "平仓"}</td>
        <td className={`px-4 py-4 font-semibold tabular-nums ${trade.pnl_usdt >= 0 ? "text-mint" : "text-coral"}`}>
          {formatCurrency(trade.pnl_usdt)} / {trade.pnl_percent >= 0 ? "+" : ""}{trade.pnl_percent}%
        </td>
        <td className="px-4 py-4 text-xs leading-5 text-ink/60">
          <p>开：{formatDateTime(trade.opened_at)}</p>
          <p>平：{trade.closed_at ? formatDateTime(trade.closed_at) : "暂无"}</p>
        </td>
      </tr>
      <tr className="bg-panel/60">
        <td colSpan={9} className="px-4 pb-5 pt-0">
          <TradeLogicDetail trade={trade} />
        </td>
      </tr>
    </>
  );
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
        <MiniStat label="开仓" value={formatCurrency(trade.entry_price)} />
        <MiniStat label="平仓" value={trade.exit_price ? formatCurrency(trade.exit_price) : "暂无"} />
        <MiniStat label="止盈" value={trade.take_profit ? formatCurrency(trade.take_profit) : "暂无"} />
        <MiniStat label="止损" value={trade.stop_loss ? formatCurrency(trade.stop_loss) : "暂无"} />
        <MiniStat label="盈亏比" value={formatRiskReward(trade)} />
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

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-panel p-3">
      <p className="text-xs text-ink/45">{label}</p>
      <p className="mt-1 break-words font-semibold tabular-nums text-ink">{value}</p>
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

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatRiskReward(trade: BacktestTrade): string {
  const stored = trade.risk_reward_ratio;
  if (typeof stored === "number" && Number.isFinite(stored)) {
    return `${stored.toFixed(2)}:1`;
  }
  if (!trade.stop_loss || !trade.take_profit || trade.entry_price <= 0) {
    return "暂无";
  }
  const risk = Math.abs(trade.entry_price - trade.stop_loss);
  const reward = Math.abs(trade.take_profit - trade.entry_price);
  if (risk <= 0) {
    return "暂无";
  }
  return `${(reward / risk).toFixed(2)}:1`;
}
