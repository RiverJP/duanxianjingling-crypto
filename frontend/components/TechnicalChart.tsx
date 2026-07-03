"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp
} from "lightweight-charts";
import { Activity, ChartCandlestick } from "lucide-react";
import { Asset, OhlcCandle } from "@/types/asset";

type LinePoint = {
  time: UTCTimestamp;
  value: number;
};

export function TechnicalChart({ asset, candles }: { asset: Asset; candles: OhlcCandle[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const chartData = useMemo(
    () =>
      candles.map((candle) => ({
        time: candle.time as UTCTimestamp,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close
      })),
    [candles]
  );

  useEffect(() => {
    if (!containerRef.current || chartData.length === 0) {
      return;
    }

    const chart = createChart(containerRef.current, {
      height: 520,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#374151"
      },
      grid: {
        vertLines: { color: "#eef0ec" },
        horzLines: { color: "#eef0ec" }
      },
      rightPriceScale: {
        borderColor: "#d1d5db"
      },
      timeScale: {
        borderColor: "#d1d5db",
        timeVisible: false
      },
      crosshair: {
        mode: 1
      }
    });

    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#2a9d8f",
      downColor: "#e76f51",
      borderUpColor: "#2a9d8f",
      borderDownColor: "#e76f51",
      wickUpColor: "#2a9d8f",
      wickDownColor: "#e76f51"
    });
    candleSeries.setData(chartData);

    addLine(chart, movingAverage(chartData, 50), "#2a9d8f", "MA50", 2);
    addLine(chart, movingAverage(chartData, 100), "#e9c46a", "MA100", 2);
    addLine(chart, movingAverage(chartData, 200), "#264653", "MA200", 2);
    addLine(chart, exponentialAverage(chartData, 144), "#6d5dfc", "Vegas EMA144", 1);
    addLine(chart, exponentialAverage(chartData, 169), "#8f63d8", "Vegas EMA169", 1);
    addLine(chart, trendLine(chartData.slice(-60)), "#111827", "趋势线", 2, LineStyle.Dashed);

    addPriceLine(candleSeries, asset.resistance_level, "阻力", "#e76f51", LineStyle.Solid);
    addPriceLine(candleSeries, asset.support_level, "支撑", "#2a9d8f", LineStyle.Solid);
    addPriceLine(candleSeries, asset.dt_upper, "DT 上轨", "#f4a261", LineStyle.Dashed);
    addPriceLine(candleSeries, asset.dt_lower, "DT 下轨", "#f4a261", LineStyle.Dashed);
    addPriceLine(candleSeries, asset.fib_236, "Fib 23.6", "#94a3b8", LineStyle.Dotted);
    addPriceLine(candleSeries, asset.fib_382, "Fib 38.2", "#94a3b8", LineStyle.Dotted);
    addPriceLine(candleSeries, asset.fib_500, "Fib 50.0", "#64748b", LineStyle.Dotted);
    addPriceLine(candleSeries, asset.fib_618, "Fib 61.8", "#94a3b8", LineStyle.Dotted);
    addPriceLine(candleSeries, asset.fib_786, "Fib 78.6", "#94a3b8", LineStyle.Dotted);
    addPriceLine(candleSeries, asset.take_profit, "止盈", "#e9c46a", LineStyle.Solid);
    addPriceLine(candleSeries, asset.stop_loss, "止损", "#e76f51", LineStyle.Solid);

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [asset, chartData]);

  return (
    <section className="mt-8 rounded border border-ink/10 bg-white p-5">
      <div className="mb-4 flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded bg-panel text-mint">
            <ChartCandlestick size={18} />
          </span>
          <div>
            <h2 className="text-xl font-semibold">K 线指标图</h2>
            <p className="text-sm text-ink/55">4 小时 K 线、MA、Vegas、斐波那契、DT、支撑阻力和趋势线</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm text-ink/55">
          <Activity size={16} />
          {asset.symbol} / USD
        </div>
      </div>
      {candles.length ? (
        <div ref={containerRef} className="h-[520px] w-full" />
      ) : (
        <div className="grid h-[320px] place-items-center rounded border border-dashed border-ink/15 bg-panel text-center text-ink/55">
          <div>
            <p className="font-medium text-ink">K 线数据暂不可用</p>
            <p className="mt-2 text-sm">CoinGecko OHLC 接口可能正在限流，请稍后刷新。</p>
          </div>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-3 text-xs text-ink/55">
        <Legend color="#2a9d8f" label="MA50 / 支撑" />
        <Legend color="#e9c46a" label="MA100 / 止盈" />
        <Legend color="#264653" label="MA200" />
        <Legend color="#6d5dfc" label="Vegas" />
        <Legend color="#94a3b8" label="斐波那契" />
        <Legend color="#f4a261" label="DT 上下轨" />
        <Legend color="#e76f51" label="阻力 / 止损" />
      </div>
    </section>
  );
}

function addLine(
  chart: IChartApi,
  data: LinePoint[],
  color: string,
  title: string,
  lineWidth: 1 | 2 | 3 | 4 = 1,
  lineStyle: LineStyle = LineStyle.Solid
) {
  if (data.length < 2) {
    return;
  }
  const series = chart.addSeries(LineSeries, {
    color,
    lineWidth,
    lineStyle,
    title,
    priceLineVisible: false,
    lastValueVisible: false
  });
  series.setData(data);
}

function addPriceLine(
  series: ISeriesApi<"Candlestick">,
  price: number | null,
  title: string,
  color: string,
  lineStyle: LineStyle
) {
  if (!price) {
    return;
  }
  series.createPriceLine({
    price,
    color,
    lineWidth: 1,
    lineStyle,
    axisLabelVisible: true,
    title
  });
}

function movingAverage(data: Array<{ time: UTCTimestamp; close: number }>, length: number): LinePoint[] {
  if (data.length < length) {
    return [];
  }
  const points: LinePoint[] = [];
  for (let index = length - 1; index < data.length; index += 1) {
    const window = data.slice(index - length + 1, index + 1);
    const value = window.reduce((sum, candle) => sum + candle.close, 0) / length;
    points.push({ time: data[index].time, value });
  }
  return points;
}

function exponentialAverage(data: Array<{ time: UTCTimestamp; close: number }>, length: number): LinePoint[] {
  if (data.length < length) {
    return [];
  }
  const multiplier = 2 / (length + 1);
  let value = data.slice(0, length).reduce((sum, candle) => sum + candle.close, 0) / length;
  const points: LinePoint[] = [{ time: data[length - 1].time, value }];
  for (let index = length; index < data.length; index += 1) {
    value = data[index].close * multiplier + value * (1 - multiplier);
    points.push({ time: data[index].time, value });
  }
  return points;
}

function trendLine(data: Array<{ time: UTCTimestamp; close: number }>): LinePoint[] {
  if (data.length < 10) {
    return [];
  }
  const n = data.length;
  const xMean = (n - 1) / 2;
  const yMean = data.reduce((sum, item) => sum + item.close, 0) / n;
  const numerator = data.reduce((sum, item, index) => sum + (index - xMean) * (item.close - yMean), 0);
  const denominator = data.reduce((sum, _item, index) => sum + (index - xMean) ** 2, 0);
  const slope = denominator ? numerator / denominator : 0;
  const intercept = yMean - slope * xMean;
  return [
    { time: data[0].time, value: intercept },
    { time: data[n - 1].time, value: intercept + slope * (n - 1) }
  ];
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-2 w-5 rounded" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
