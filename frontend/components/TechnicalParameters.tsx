import {
  ArrowDownToLine,
  ArrowUpToLine,
  BarChart3,
  ChartCandlestick,
  GitBranch,
  Layers,
  LineChart,
  Route,
  Shield,
  Waves
} from "lucide-react";
import type React from "react";
import { Asset, OhlcCandle } from "@/types/asset";
import { formatCurrency } from "@/lib/format";

type Overlay = {
  label: string;
  value?: number | null;
  color: string;
  kind?: "solid" | "dash";
};

type SlopedOverlay = {
  label: string;
  start: number;
  end: number;
  color: string;
};

type SeriesOverlay = {
  label: string;
  values: Array<number | null>;
  color: string;
};

type SnapshotCard = {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  overlays: Overlay[];
  series?: SeriesOverlay[];
  sloped?: SlopedOverlay[];
  footer: string;
};

export function TechnicalParameters({ asset, candles }: { asset: Asset; candles: OhlcCandle[] }) {
  const cards: SnapshotCard[] = [
    {
      title: "斐波那契回撤",
      subtitle: "近 90 日高低点映射",
      icon: <Layers size={18} />,
      overlays: [
        { label: "23.6", value: asset.fib_236, color: "#94a3b8", kind: "dash" },
        { label: "38.2", value: asset.fib_382, color: "#64748b", kind: "dash" },
        { label: "50.0", value: asset.fib_500, color: "#475569" },
        { label: "61.8", value: asset.fib_618, color: "#64748b", kind: "dash" },
        { label: "78.6", value: asset.fib_786, color: "#94a3b8", kind: "dash" }
      ],
      footer: `核心位：61.8% ${money(asset.fib_618)}`
    },
    {
      title: "DT 突破通道",
      subtitle: "上轨 / 下轨区间",
      icon: <Waves size={18} />,
      overlays: [
        { label: "DT 上轨", value: asset.dt_upper, color: "#f4a261" },
        { label: "DT 下轨", value: asset.dt_lower, color: "#f4a261" }
      ],
      footer: `当前状态：${asset.dt_signal}`
    },
    {
      title: "Vegas 均线通道",
      subtitle: "4 小时 EMA144 / EMA169 曲线",
      icon: <Route size={18} />,
      overlays: [],
      series: [
        { label: "EMA144", values: emaSeries(candles, 144), color: "#6d5dfc" },
        { label: "EMA169", values: emaSeries(candles, 169), color: "#8f63d8" }
      ],
      footer: asset.vegas_signal
    },
    {
      title: "MA 50 / 100 / 200",
      subtitle: "4 小时 MA50 / MA100 / MA200 曲线",
      icon: <LineChart size={18} />,
      overlays: [],
      series: [
        { label: "MA50", values: maSeries(candles, 50), color: "#2a9d8f" },
        { label: "MA100", values: maSeries(candles, 100), color: "#e9c46a" },
        { label: "MA200", values: maSeries(candles, 200), color: "#264653" }
      ],
      footer: maPosition(asset)
    },
    {
      title: "趋势线",
      subtitle: "近 60 根 K 线回归线",
      icon: <GitBranch size={18} />,
      overlays: [],
      sloped: [trendOverlay(candles)],
      footer: asset.trend_line
    },
    {
      title: "支撑 / 阻力",
      subtitle: "近 30 日关键边界",
      icon: <Shield size={18} />,
      overlays: [
        { label: "阻力", value: asset.resistance_level, color: "#e76f51" },
        { label: "支撑", value: asset.support_level, color: "#2a9d8f" }
      ],
      footer: `支撑 ${money(asset.support_level)} / 阻力 ${money(asset.resistance_level)}`
    },
    {
      title: "止盈 / 止损",
      subtitle: "交易计划线位",
      icon: <ChartCandlestick size={18} />,
      overlays: [
        { label: "止盈", value: asset.take_profit, color: "#e9c46a" },
        { label: "入场", value: asset.entry_price, color: "#111827", kind: "dash" },
        { label: "止损", value: asset.stop_loss, color: "#e76f51" }
      ],
      footer: `${asset.trade_signal}，盈亏比 ${asset.risk_reward_ratio ? `${asset.risk_reward_ratio}:1` : "暂无"}`
    },
    {
      title: "量价关系",
      subtitle: "价格路径与成交量状态",
      icon: <BarChart3 size={18} />,
      overlays: [{ label: "当前价", value: asset.current_price, color: "#2a9d8f" }],
      footer: asset.volume_price_relation
    },
    {
      title: "盘面周期",
      subtitle: "价格与均线周期位置",
      icon: <ArrowUpToLine size={18} />,
      overlays: [
        { label: "当前价", value: asset.current_price, color: "#111827" },
        { label: "MA50", value: asset.ma_50, color: "#2a9d8f" },
        { label: "MA200", value: asset.ma_200, color: "#264653" }
      ],
      footer: asset.market_cycle
    }
  ];

  return (
    <section className="mt-8">
      <div className="mb-4 flex items-center gap-2">
        <ChartCandlestick size={18} className="text-mint" />
        <h2 className="text-xl font-semibold">指标截图</h2>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <div key={card.title} className="rounded border border-ink/10 bg-white p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="grid h-8 w-8 place-items-center rounded bg-panel text-mint">{card.icon}</span>
                <div>
                  <h3 className="font-semibold">{card.title}</h3>
                  <p className="text-xs text-ink/50">{card.subtitle}</p>
                </div>
              </div>
            </div>
            <MiniKlineSnapshot candles={candles} overlays={card.overlays} series={card.series ?? []} sloped={card.sloped ?? []} />
            <div className="mt-3 flex items-center gap-2 text-sm text-ink/70">
              <ArrowDownToLine size={14} className="text-ink/40" />
              <span>{card.footer}</span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-ink/45">{asset.technical_note}</p>
    </section>
  );
}

function MiniKlineSnapshot({
  candles,
  overlays,
  series,
  sloped
}: {
  candles: OhlcCandle[];
  overlays: Overlay[];
  series: SeriesOverlay[];
  sloped: SlopedOverlay[];
}) {
  const visibleCandles = candles.slice(-60);
  if (!visibleCandles.length) {
    return <div className="grid h-44 place-items-center rounded bg-panel text-sm text-ink/50">K 线数据暂不可用</div>;
  }

  const width = 420;
  const height = 190;
  const padX = 18;
  const padY = 16;
  const validOverlayValues = overlays.map((item) => item.value).filter((value): value is number => Boolean(value));
  const validSeriesValues = series.flatMap((line) => line.values.slice(-60)).filter((value): value is number => Boolean(value));
  const validSlopedValues = sloped.flatMap((line) => [line.start, line.end]).filter((value) => Boolean(value));
  const allPrices = [
    ...visibleCandles.flatMap((candle) => [candle.high, candle.low]),
    ...validOverlayValues,
    ...validSeriesValues,
    ...validSlopedValues
  ];
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const priceSpan = maxPrice - minPrice || 1;
  const candleStep = (width - padX * 2) / visibleCandles.length;
  const bodyWidth = Math.max(2, candleStep * 0.55);

  const yFor = (price: number) => height - padY - ((price - minPrice) / priceSpan) * (height - padY * 2);
  const xFor = (index: number) => padX + index * candleStep + candleStep / 2;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full rounded bg-panel" role="img" aria-label="指标 K 线截图">
      <rect width={width} height={height} fill="#f7f7f2" />
      {[0.25, 0.5, 0.75].map((ratio) => (
        <line key={ratio} x1={padX} x2={width - padX} y1={height * ratio} y2={height * ratio} stroke="#e5e7eb" strokeWidth="1" />
      ))}
      {visibleCandles.map((candle, index) => {
        const x = xFor(index);
        const openY = yFor(candle.open);
        const closeY = yFor(candle.close);
        const highY = yFor(candle.high);
        const lowY = yFor(candle.low);
        const up = candle.close >= candle.open;
        const color = up ? "#2a9d8f" : "#e76f51";
        return (
          <g key={`${candle.time}-${index}`}>
            <line x1={x} x2={x} y1={highY} y2={lowY} stroke={color} strokeWidth="1.2" />
            <rect
              x={x - bodyWidth / 2}
              y={Math.min(openY, closeY)}
              width={bodyWidth}
              height={Math.max(2, Math.abs(closeY - openY))}
              fill={up ? "#2a9d8f" : "#e76f51"}
              opacity="0.9"
              rx="0.8"
            />
          </g>
        );
      })}
      {sloped.map((line) => (
        <g key={line.label}>
          <line x1={padX} x2={width - padX} y1={yFor(line.start)} y2={yFor(line.end)} stroke={line.color} strokeWidth="2" strokeDasharray="5 4" />
          <text x={width - padX - 48} y={yFor(line.end) - 5} fill={line.color} fontSize="10" fontWeight="600">{line.label}</text>
        </g>
      ))}
      {series.map((line) => {
        const points = line.values.slice(-60).map((value, index) => (value ? `${xFor(index)},${yFor(value)}` : "")).filter(Boolean).join(" ");
        const lastValue = line.values.slice(-60).filter((value): value is number => Boolean(value)).at(-1);
        const lastIndex = line.values.slice(-60).findLastIndex((value) => Boolean(value));
        if (!points || !lastValue || lastIndex < 0) {
          return null;
        }
        return (
          <g key={line.label}>
            <polyline points={points} fill="none" stroke={line.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            <rect x={Math.min(width - padX - 58, xFor(lastIndex) + 4)} y={yFor(lastValue) - 13} width="58" height="16" rx="3" fill="#ffffff" opacity="0.92" />
            <text x={Math.min(width - padX - 54, xFor(lastIndex) + 8)} y={yFor(lastValue) - 2} fill={line.color} fontSize="10" fontWeight="700">{line.label}</text>
          </g>
        );
      })}
      {overlays.filter((item) => item.value).map((item, index) => {
        const y = yFor(item.value as number);
        const labelX = index % 2 === 0 ? padX + 4 : width - padX - 58;
        return (
          <g key={`${item.label}-${item.value}`}>
            <line
              x1={padX}
              x2={width - padX}
              y1={y}
              y2={y}
              stroke={item.color}
              strokeWidth="1.5"
              strokeDasharray={item.kind === "dash" ? "5 4" : undefined}
            />
            <rect x={labelX - 2} y={y - 13} width="58" height="16" rx="3" fill="#ffffff" opacity="0.92" />
            <text x={labelX + 2} y={y - 2} fill={item.color} fontSize="10" fontWeight="700">{item.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

function maSeries(candles: OhlcCandle[], length: number): Array<number | null> {
  return candles.map((_candle, index) => {
    if (index < length - 1) {
      return null;
    }
    const window = candles.slice(index - length + 1, index + 1);
    return window.reduce((sum, candle) => sum + candle.close, 0) / length;
  });
}

function emaSeries(candles: OhlcCandle[], length: number): Array<number | null> {
  const values: Array<number | null> = Array(candles.length).fill(null);
  if (candles.length < length) {
    return values;
  }
  const multiplier = 2 / (length + 1);
  let ema = candles.slice(0, length).reduce((sum, candle) => sum + candle.close, 0) / length;
  values[length - 1] = ema;
  for (let index = length; index < candles.length; index += 1) {
    ema = candles[index].close * multiplier + ema * (1 - multiplier);
    values[index] = ema;
  }
  return values;
}

function trendOverlay(candles: OhlcCandle[]): SlopedOverlay {
  const data = candles.slice(-60);
  if (data.length < 10) {
    return { label: "趋势线", start: 0, end: 0, color: "#111827" };
  }
  const n = data.length;
  const xMean = (n - 1) / 2;
  const yMean = data.reduce((sum, candle) => sum + candle.close, 0) / n;
  const numerator = data.reduce((sum, candle, index) => sum + (index - xMean) * (candle.close - yMean), 0);
  const denominator = data.reduce((sum, _candle, index) => sum + (index - xMean) ** 2, 0);
  const slope = denominator ? numerator / denominator : 0;
  const intercept = yMean - slope * xMean;
  return { label: "趋势线", start: intercept, end: intercept + slope * (n - 1), color: "#111827" };
}

function money(value: number | null): string {
  return value ? formatCurrency(value) : "暂无";
}

function maPosition(asset: Asset): string {
  if (!asset.ma_50 || !asset.ma_200) {
    return "数据不足";
  }
  if (asset.current_price > asset.ma_50 && asset.ma_50 > asset.ma_200) {
    return "价格在 MA50/200 上方";
  }
  if (asset.current_price < asset.ma_50 && asset.ma_50 < asset.ma_200) {
    return "价格在 MA50/200 下方";
  }
  return "价格靠近均线区间";
}
