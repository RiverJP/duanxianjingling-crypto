import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from time import time
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AssetSnapshot, BacktestRun
from app.scoring import calculate_scores
from app.services import (
    fetch_coingecko_ohlc_endpoint,
    fetch_market_data,
    fetch_ohlc_data,
    has_enough_ohlc,
    interval_candles_per_day,
    load_ohlc_from_db,
    normalize_kline_interval,
    save_ohlc_to_db,
    universe_asset_where_clause,
)
from app.trade_logic import build_trade_plan, round_price

BACKTEST_CACHE_TTL_SECONDS = 300
BACKTEST_CACHE: dict[str, tuple[float, dict]] = {}
TREND_LOOKBACK_CANDLES = 60
BACKTEST_STRATEGY_VERSION = "2026-07-04v4-strict"
MIN_BACKTEST_RISK_REWARD_RATIO = 1.0
MAX_STRUCTURE_STOP_DISTANCE_RATIO = 0.05
BACKTEST_FEE_RATE = 0.0012


async def run_month_backtest(
    db: Session,
    days: int = 30,
    limit: int = 100,
    interval: str = "1h",
    mode: str = "indicator",
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    settings = get_settings()
    execution_interval = normalize_kline_interval(interval)
    strategy_mode = "score" if mode == "score" else "indicator"
    max_days = 180
    capped_days = max(30, min(days, max_days))
    capped_limit = max(1, min(limit, settings.tracked_asset_count))
    cache_key = f"{BACKTEST_STRATEGY_VERSION}:{strategy_mode}:{capped_days}:{capped_limit}:{execution_interval}:{settings.paper_min_opportunity_score}"
    cached = BACKTEST_CACHE.get(cache_key)
    if cached and time() - cached[0] < BACKTEST_CACHE_TTL_SECONDS:
        return cached[1]
    assets = list(
        db.scalars(
            select(AssetSnapshot)
            .where(universe_asset_where_clause())
            .order_by(AssetSnapshot.market_cap.desc())
            .limit(capped_limit)
        )
    )
    if progress_callback:
        progress_callback(
            {
                "total_assets": len(assets),
                "completed_assets": 0,
                "current_asset": None,
                "total_trades": 0,
            }
        )

    async def run_asset(asset: AssetSnapshot) -> dict:
        candles = load_ohlc_from_db(db, asset.symbol, execution_interval, capped_days)
        asset_execution_interval = execution_interval
        trend_candles = resample_candles(candles, 14400) if asset_execution_interval in {"15m", "1h"} else candles
        trend_filters = {"4h": trend_candles}
        daily_candles = resample_candles(trend_candles, 86400)
        if asset_execution_interval == "15m":
            one_hour_candles = load_ohlc_from_db(db, asset.symbol, "1h", capped_days)
            if not has_enough_ohlc(one_hour_candles, capped_days, "1h"):
                one_hour_candles = resample_candles(candles, 3600)
            four_hour_candles = load_ohlc_from_db(db, asset.symbol, "4h", capped_days)
            if not has_enough_ohlc(four_hour_candles, capped_days, "4h"):
                four_hour_candles = trend_candles
            trend_filters = {"1h": one_hour_candles, "4h": four_hour_candles}
            daily_candles = resample_candles(four_hour_candles, 86400)
        return await asyncio.to_thread(
            backtest_asset,
            asset,
            candles,
            capped_days,
            settings.paper_margin_per_trade,
            settings.paper_leverage,
            settings.paper_min_opportunity_score,
            asset_execution_interval,
            trend_candles,
            trend_filters,
            daily_candles,
            strategy_mode,
        )

    semaphore = asyncio.Semaphore(1)

    async def run_asset_limited(index: int, asset: AssetSnapshot) -> dict:
        async with semaphore:
            if progress_callback:
                progress_callback(
                    {
                        "total_assets": len(assets),
                        "completed_assets": index - 1,
                        "current_asset": asset.symbol,
                    }
                )
            try:
                result = await asyncio.wait_for(run_asset(asset), timeout=30)
            except TimeoutError:
                result = {
                    "trades": [],
                    "asset": build_asset_result(asset, 0, 0, "观望", [], "K线不足", execution_interval),
                }
            if progress_callback:
                progress_callback(
                    {
                        "total_assets": len(assets),
                        "completed_assets": index,
                        "current_asset": asset.symbol,
                        "last_asset_trades": len(result["trades"]),
                    }
                )
            return result

    results = []
    for index, asset in enumerate(assets, start=1):
        results.append(await run_asset_limited(index, asset))

    trades: list[dict] = []
    asset_results: list[dict] = []
    for result in results:
        trades.extend(result["trades"])
        asset_results.append(result["asset"])
        if progress_callback:
            progress_callback(
                {
                    "total_assets": len(assets),
                    "completed_assets": len(asset_results),
                    "current_asset": result["asset"]["symbol"],
                    "total_trades": len(trades),
                }
            )

    trades.sort(key=lambda trade: trade["opened_at"])
    portfolio_trades, excluded_portfolio_trades, max_concurrent_trades = apply_portfolio_margin_limit(
        trades,
        settings.paper_account_balance,
    )
    period_closed_trades = exclude_period_end_trades(portfolio_trades)
    report_trades = exclude_low_risk_reward_trades(period_closed_trades)
    excluded_period_end_trades = len(portfolio_trades) - len(period_closed_trades)
    excluded_low_risk_reward_trades = len(period_closed_trades) - len(report_trades)
    trend_interval = "1h+4h" if execution_interval == "15m" else "4h"
    summary = build_backtest_summary(
        report_trades,
        settings.paper_account_balance,
        capped_days,
        len(assets),
        execution_interval,
        trend_interval,
        excluded_period_end_trades=excluded_period_end_trades,
        excluded_low_risk_reward_trades=excluded_low_risk_reward_trades,
        excluded_portfolio_trades=excluded_portfolio_trades,
        max_concurrent_trades=max_concurrent_trades,
    )
    rules = build_backtest_rules(strategy_mode, execution_interval, trend_interval, settings.paper_min_opportunity_score)
    result = {
        "summary": summary,
        "rules": rules,
        "equity_curve": build_backtest_equity_curve(report_trades, settings.paper_account_balance, capped_days),
        "trades": sorted(report_trades, key=lambda trade: trade["opened_at"], reverse=True),
        "all_trades": sorted(portfolio_trades, key=lambda trade: trade["opened_at"], reverse=True),
        "assets": build_report_asset_results(asset_results, report_trades, execution_interval),
    }
    saved_run = save_backtest_run(
        db,
        result,
        parameters={
            "days": capped_days,
            "limit": capped_limit,
            "execution_interval": execution_interval,
            "trend_interval": trend_interval,
            "strategy_mode": strategy_mode,
            "min_quality_score": settings.paper_min_opportunity_score,
            "margin_per_trade": settings.paper_margin_per_trade,
            "leverage": settings.paper_leverage,
            "max_used_margin": settings.paper_account_balance,
        },
    )
    result["summary"]["run_id"] = saved_run.id
    result["summary"]["run_key"] = saved_run.run_key
    result["summary"]["strategy_mode"] = strategy_mode
    result["summary"]["strategy_version"] = BACKTEST_STRATEGY_VERSION
    result["summary"]["generated_at"] = saved_run.created_at.isoformat() if saved_run.created_at else datetime.now(timezone.utc).isoformat()
    BACKTEST_CACHE[cache_key] = (time(), result)
    if progress_callback:
        progress_callback(
            {
                "total_assets": len(assets),
                "completed_assets": len(assets),
                "current_asset": None,
                "total_trades": len(portfolio_trades),
                "run_key": saved_run.run_key,
            }
        )
    return result


def save_backtest_run(db: Session, result: dict, parameters: dict) -> BacktestRun:
    summary = result["summary"]
    rules = result["rules"]
    created_at = datetime.now(timezone.utc)
    fingerprint = hashlib.sha1(
        json.dumps(
            {
                "parameters": parameters,
                "summary": summary,
                "created_at": created_at.isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:8]
    run_key = f"BT-{created_at.strftime('%Y%m%d-%H%M%S')}-{fingerprint}"
    run = BacktestRun(
        run_key=run_key,
        strategy_mode=str(parameters["strategy_mode"]),
        strategy_version=BACKTEST_STRATEGY_VERSION,
        days=int(parameters["days"]),
        execution_interval=str(parameters["execution_interval"]),
        trend_interval=str(parameters["trend_interval"]),
        tested_assets=int(summary["tested_assets"]),
        total_trades=int(summary["total_trades"]),
        total_pnl=float(summary["total_pnl"]),
        win_rate=float(summary["win_rate"]),
        parameters_json=json.dumps(parameters, ensure_ascii=False),
        rules_json=json.dumps(rules, ensure_ascii=False),
        summary_json=json.dumps(summary, ensure_ascii=False),
        equity_curve_json=json.dumps(result["equity_curve"], ensure_ascii=False),
        assets_json=json.dumps(result["assets"], ensure_ascii=False),
        trades_json=json.dumps(result.get("all_trades") or result["trades"], ensure_ascii=False),
        created_at=created_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def build_backtest_rules(strategy_mode: str, execution_interval: str, trend_interval: str, min_quality_score: int) -> dict:
    return {
        "title": BACKTEST_STRATEGY_VERSION,
        "mode": strategy_mode,
        "version": BACKTEST_STRATEGY_VERSION,
        "timeframes": [
            f"执行周期：{execution_interval}",
            f"方向过滤：{trend_interval}",
            "日线由 4H K 线聚合，但只使用信号时刻之前已经完整收盘的日线。",
            "15m 信号在当前 K 线收盘后生成，下一根 15m K 线开盘价成交。",
        ],
        "entry_conditions": [
            f"指标质量分必须 >= {min_quality_score}。",
            f"计划盈亏比必须 >= {MIN_BACKTEST_RISK_REWARD_RATIO:.1f}:1。",
            "市值成交活跃度过滤：24h 成交额 / 市值 >= 1.5%。",
            "上升趋势只允许做多；下降趋势只允许做空；震荡区间允许靠近支撑做多、靠近阻力做空。",
            "15m 执行时，1H 和 4H 方向不能与开仓方向冲突。",
            "信号必须有可计算的止盈价和止损价，否则不允许开仓。",
        ],
        "long_logic": [
            "日线/4H 判断为上升趋势，且 4H 指标方向为做多。",
            "1H 方向不能为做空。",
            "满足以下至少一类入场原因：靠近支撑、靠近斐波那契回撤支撑、出现双底结构、突破 DT 上轨、或 1H 顺势做多。",
            "震荡区间中，只在靠近支撑或双底结构时做多。",
        ],
        "short_logic": [
            "日线/4H 判断为下降趋势，且 4H 指标方向为做空。",
            "1H 方向不能为做多。",
            "满足以下至少一类入场原因：靠近阻力、靠近斐波那契反弹阻力、出现双顶结构、跌破 DT 下轨、或 1H 顺势做空。",
            "震荡区间中，只在靠近阻力或双顶结构时做空。",
        ],
        "stop_loss_logic": [
            "基础止损距离取最近 20 根执行周期 K 线平均波幅 * 1.6。",
            "最小止损距离不低于入场价的 1.2%。",
            "做多止损优先放在支撑下方；做空止损优先放在阻力上方。",
            f"只有支撑/阻力距离开仓价不超过 {MAX_STRUCTURE_STOP_DISTANCE_RATIO * 100:.0f}% 时，才允许作为结构止损；距离太远则回退为波幅止损。",
        ],
        "take_profit_logic": [
            "趋势单默认盈亏比约 2.0:1。",
            "区间单默认盈亏比约 1.8:1。",
            "止盈价基于最终止损距离重新计算，避免结构止损过远时出现低盈亏比单。",
            "区间多的止盈会参考上方阻力；区间空的止盈会参考下方支撑。",
        ],
        "exit_logic": [
            "价格触发止盈时平仓。",
            "价格触发止损时平仓。",
            "15m 单最长持仓延长到 7 天；到期仍未触发止盈止损时，按当根收盘价到期平仓。",
            "回测结束仍未触发止盈止损的单会标记为期末平仓，但默认不纳入胜率、盈亏和资金曲线统计。",
        ],
        "indicator_analysis": [
            f"策略名称：{BACKTEST_STRATEGY_VERSION}。核心思路是先用已收盘日线和4H判断大环境，再用已收盘1H过滤方向，最后用15m收盘信号、下一根15m开盘执行。",
            "EMA：20/50 用于执行和观察周期方向；50/100 用于日线趋势判定；144/169 作为 Vegas 通道中轴。",
            "Vegas：价格在 EMA144/EMA169 通道上方偏多，在下方偏空。",
            "DT：近 20 根 K 线高低点作为突破通道，上破偏多，下破偏空。",
            "斐波那契：用近 90 根日线聚合高低点计算 38.2%、50%、61.8% 回撤/反弹区域。",
            "趋势线：使用最近 60 根观察周期 K 线和 EMA 排列判断方向。",
            "结构：近 45 根日线聚合 K 线检测双底/双顶。",
            "支撑阻力：近 30 根日线聚合 K 线低点为支撑，高点为阻力。",
            "量价关系：当前版本用 24h 成交额 / 市值做流动性过滤；后续可接入每根 K 线成交量后升级成真实量价确认。",
        ],
        "risk_notes": [
            f"手续费按每笔名义仓位 {BACKTEST_FEE_RATE * 100:.2f}% 估算，汇总会同时展示扣费前和扣费后结果。",
            "当前回测未计入滑点和盘口深度冲击。",
            "当前回测会按模拟账户本金限制同时持仓保证金占用，保证金不足的信号会被跳过。",
            "当前标的池仍使用回测启动时的币安合约成交量前 150，尚未还原历史每一天的成分股变化。",
            "结果只用于验证策略逻辑，不代表实盘收益。",
        ],
    }


async def build_sparkline_fallbacks(assets: list[AssetSnapshot]) -> dict[str, list[dict[str, float | int]]]:
    ids = [asset.coingecko_id for asset in assets if asset.coingecko_id]
    if not ids:
        return {}
    try:
        rows = await fetch_market_data(ids, sparkline=True)
    except Exception:
        return {}
    fallback: dict[str, list[dict[str, float | int]]] = {}
    now = int(datetime.now(timezone.utc).timestamp())
    for row in rows:
        prices = row.get("sparkline_in_7d", {}).get("price", [])
        if len(prices) < 12:
            continue
        start = now - (len(prices) - 1) * 3600
        candles = []
        previous = float(prices[0])
        for index, price in enumerate(prices[1:], start=1):
            close = float(price)
            candles.append(
                {
                    "time": start + index * 3600,
                    "open": previous,
                    "high": max(previous, close),
                    "low": min(previous, close),
                    "close": close,
                }
            )
            previous = close
        fallback[row["id"]] = candles
    return fallback


def backtest_asset(
    asset: AssetSnapshot,
    candles: list[dict[str, float | int]],
    days: int,
    margin_per_trade: float,
    leverage: int,
    min_opportunity_score: int,
    execution_interval: str = "4h",
    trend_candles: list[dict[str, float | int]] | None = None,
    trend_filters: dict[str, list[dict[str, float | int]]] | None = None,
    daily_candles: list[dict[str, float | int]] | None = None,
    strategy_mode: str = "indicator",
) -> dict:
    if len(candles) < 12:
        return {
            "trades": [],
            "asset": build_asset_result(asset, len(candles), 0, "观望", [], "K线不足", execution_interval),
        }

    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    rows = [candle for candle in candles if int(candle["time"]) >= cutoff]
    if len(rows) < 12:
        candles_per_day = interval_candles_per_day(execution_interval)
        rows = candles[-min(len(candles), days * candles_per_day):]

    trades: list[dict] = []
    open_trade: dict | None = None
    notional = margin_per_trade * leverage
    max_holding_seconds = backtest_max_holding_seconds(execution_interval)
    best_opportunity_score = 0
    best_signal = "观望"
    lookback_candles = interval_candles_per_day(execution_interval)
    trend_rows = trend_candles or rows
    trend_filter_rows = trend_filters or {"4h": trend_rows}
    daily_rows = daily_candles or resample_candles(trend_rows, 86400)

    execution_seconds = interval_seconds(execution_interval)

    for index in range(lookback_candles, len(rows) - 1):
        candle = rows[index]
        next_candle = rows[index + 1]
        close = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])
        candle_time = int(candle["time"])
        signal_time = candle_time + execution_seconds

        if open_trade:
            closed = maybe_close_trade(open_trade, high, low, close, signal_time)
            if closed:
                trades.append(closed)
                open_trade = None
            continue

        previous_close = float(rows[index - lookback_candles]["close"])
        if previous_close <= 0 or close <= 0:
            continue

        change_24h = (close - previous_close) / previous_close * 100
        scores = calculate_scores(change_24h, float(asset.market_cap), float(asset.volume_24h))
        score_plan = build_trade_plan(
            current_price=close,
            change_24h=change_24h,
            ai_score=scores["ai_score"],
            trend_score=scores["trend_score"],
            liquidity_score=scores["liquidity_score"],
            risk_score=scores["risk_score"],
        )
        opportunity_score = directional_opportunity_score(
            str(score_plan["trade_signal"]),
            scores["ai_score"],
            scores["trend_score"],
            scores["liquidity_score"],
            scores["risk_score"],
        )
        trend_signals = {
            label: build_trend_signal(filter_rows, signal_time, asset, label)
            for label, filter_rows in trend_filter_rows.items()
        }
        market_context = build_daily_market_context(daily_rows, signal_time, close)

        if strategy_mode == "indicator":
            plan = build_indicator_trade_plan(asset, rows, index, close, signal_time, trend_filter_rows, market_context)
            if plan is None:
                continue
            opportunity_score = int(plan["opportunity_score"])
            strategy_type = str(plan["strategy_type"])
        else:
            plan = dict(score_plan)
            plan["opportunity_score"] = opportunity_score
            strategy_type = classify_strategy_type(str(plan["trade_signal"]), close, market_context)

        if opportunity_score > best_opportunity_score:
            best_opportunity_score = opportunity_score
            best_signal = str(plan["trade_signal"])
        if plan["trade_signal"] not in {"做多", "做空"}:
            continue
        if strategy_mode == "score" and execution_interval in {"15m", "1h"} and not all(signal == plan["trade_signal"] for signal in trend_signals.values()):
            continue
        if strategy_mode == "score" and not is_allowed_by_market_context(str(plan["trade_signal"]), strategy_type, market_context):
            continue
        if strategy_mode == "score":
            opportunity_score = min(100, opportunity_score + context_score_bonus(strategy_type, market_context))
        if opportunity_score > best_opportunity_score:
            best_opportunity_score = opportunity_score
            best_signal = str(plan["trade_signal"])
        if opportunity_score < min_opportunity_score:
            continue
        if not plan["take_profit"] or not plan["stop_loss"]:
            continue
        entry_price = float(next_candle["open"])
        entry_time = int(next_candle["time"])
        stop_loss = float(plan["stop_loss"])
        take_profit = float(plan["take_profit"])
        if not is_valid_delayed_entry(str(plan["trade_signal"]), entry_price, stop_loss, take_profit):
            continue
        delayed_risk_reward_ratio = calculate_plan_risk_reward(entry_price, stop_loss, take_profit)
        if delayed_risk_reward_ratio < MIN_BACKTEST_RISK_REWARD_RATIO:
            continue

        entry_reasons = list(plan.get("entry_reasons") or [])
        entry_reasons.append("v4严格回测：信号K线收盘后确认，下一根15m K线开盘价成交")
        indicator_snapshot = dict(plan.get("indicator_snapshot") or {})
        indicator_snapshot["signal_price"] = round_price(close)
        indicator_snapshot["entry_price"] = round_price(entry_price)
        indicator_snapshot["risk_reward_ratio"] = delayed_risk_reward_ratio
        indicator_snapshot["execution_detail"] = "信号K线收盘后确认，下一根15m K线开盘价成交；1H/4H/日线只读取已完整收盘K线。"

        opening_logic = build_trade_opening_logic(
            asset.symbol,
            str(plan["trade_signal"]),
            strategy_type,
            opportunity_score,
            entry_price,
            stop_loss,
            take_profit,
            market_context,
            indicator_snapshot,
            entry_reasons,
        )
        open_trade = {
            "symbol": asset.symbol,
            "name": asset.name,
            "side": plan["trade_signal"],
            "entry_price": entry_price,
            "current_price": entry_price,
            "exit_price": None,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward_ratio": delayed_risk_reward_ratio,
            "margin_usdt": margin_per_trade,
            "leverage": leverage,
            "notional_usdt": notional,
            "opportunity_score": opportunity_score,
            "execution_interval": execution_interval,
            "strategy_type": strategy_type,
            "market_regime": market_context["regime"],
            "entry_reasons": entry_reasons,
            "indicator_snapshot": indicator_snapshot,
            "opening_logic": opening_logic,
            "signal_timestamp": signal_time,
            "opened_timestamp": entry_time,
            "max_holding_seconds": max_holding_seconds,
            "signal_at": iso_from_timestamp(signal_time),
            "opened_at": iso_from_timestamp(entry_time),
            "closed_at": None,
            "close_reason": None,
            "pnl_usdt": 0.0,
            "pnl_percent": 0.0,
        }

    if open_trade:
        last = rows[-1]
        closed = maybe_close_trade(
            open_trade,
            float(last["high"]),
            float(last["low"]),
            float(last["close"]),
            int(last["time"]) + execution_seconds,
        )
        trades.append(closed or close_trade(open_trade, float(last["close"]), int(last["time"]) + execution_seconds, "期末平仓"))

    status = "触发交易"
    if not trades:
        status = f"未达{min_opportunity_score}分" if best_opportunity_score < min_opportunity_score else "高分但无可执行信号"

    return {
        "trades": trades,
        "asset": build_asset_result(asset, len(rows), best_opportunity_score, best_signal, trades, status, execution_interval),
    }


def backtest_max_holding_seconds(execution_interval: str) -> int:
    if execution_interval in {"15m", "1h"}:
        return 7 * 24 * 3600
    return 21 * 24 * 3600


def interval_seconds(interval: str) -> int:
    return {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}.get(interval, 3600)


def completed_candles(rows: list[dict[str, float | int]], timestamp: int, interval: str) -> list[dict[str, float | int]]:
    seconds = interval_seconds(interval)
    return [row for row in rows if int(row["time"]) + seconds <= timestamp]


def infer_candle_interval(rows: list[dict[str, float | int]]) -> str:
    if len(rows) < 2:
        return "4h"
    delta = max(1, int(rows[-1]["time"]) - int(rows[-2]["time"]))
    if delta <= 900:
        return "15m"
    if delta <= 3600:
        return "1h"
    if delta <= 14400:
        return "4h"
    return "1d"


def is_valid_delayed_entry(side: str, entry_price: float, stop_loss: float, take_profit: float) -> bool:
    if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
        return False
    if side == "做多":
        return stop_loss < entry_price < take_profit
    if side == "做空":
        return take_profit < entry_price < stop_loss
    return False


def build_indicator_trade_plan(
    asset: AssetSnapshot,
    rows: list[dict[str, float | int]],
    index: int,
    price: float,
    timestamp: int,
    trend_filter_rows: dict[str, list[dict[str, float | int]]],
    market_context: dict,
) -> dict | None:
    if market_context["regime"] == "数据不足" or price <= 0:
        return None

    volume_to_cap = float(asset.volume_24h) / float(asset.market_cap) if asset.market_cap else 0
    if volume_to_cap < 0.015:
        return None

    trend_directions = {
        label: indicator_trend_direction(filter_rows, timestamp)
        for label, filter_rows in trend_filter_rows.items()
    }
    one_hour_direction = trend_directions.get("1h", "观望")
    four_hour_direction = trend_directions.get("4h", one_hour_direction)
    market_regime = str(market_context["regime"])
    long_context = market_context["near_support"] or market_context["near_fib_support"] or market_context["double_bottom"]
    short_context = market_context["near_resistance"] or market_context["near_fib_resistance"] or market_context["double_top"]
    dt_break_long = price >= float(market_context.get("dt_upper") or price * 10)
    dt_break_short = price <= float(market_context.get("dt_lower") or 0)

    signal = "观望"
    strategy_type = "不匹配"
    quality = 76

    if market_regime == "上升趋势":
        if four_hour_direction == "做多" and one_hour_direction != "做空" and (long_context or dt_break_long or one_hour_direction == "做多"):
            signal = "做多"
            strategy_type = "上升趋势区间多" if long_context else "趋势多"
    elif market_regime == "下降趋势":
        if four_hour_direction == "做空" and one_hour_direction != "做多" and (short_context or dt_break_short or one_hour_direction == "做空"):
            signal = "做空"
            strategy_type = "下降趋势区间空" if short_context else "趋势空"
    else:
        if long_context and one_hour_direction != "做空":
            signal = "做多"
            strategy_type = "区间多"
        elif short_context and one_hour_direction != "做多":
            signal = "做空"
            strategy_type = "区间空"

    if signal == "观望":
        return None

    quality += 4 if four_hour_direction == signal else 0
    quality += 3 if one_hour_direction == signal else 0
    quality += 3 if strategy_type in {"上升趋势区间多", "下降趋势区间空", "区间多", "区间空"} else 0
    quality += 2 if market_context["near_fib_support"] or market_context["near_fib_resistance"] else 0
    quality += 2 if market_context["double_bottom"] or market_context["double_top"] else 0
    quality += 2 if volume_to_cap >= 0.08 else 0
    quality = min(100, quality)

    if quality < 80:
        return None

    stop_loss, take_profit = build_indicator_exit_prices(signal, price, rows, index, market_context, strategy_type)
    if not stop_loss or not take_profit:
        return None
    risk_reward_ratio = calculate_plan_risk_reward(price, stop_loss, take_profit)
    if risk_reward_ratio < MIN_BACKTEST_RISK_REWARD_RATIO:
        return None
    entry_reasons = build_entry_reasons(
        signal,
        strategy_type,
        market_regime,
        one_hour_direction,
        four_hour_direction,
        market_context,
        dt_break_long,
        dt_break_short,
        volume_to_cap,
    )
    entry_reasons.append(f"计划盈亏比为{risk_reward_ratio:.2f}:1，达到最低 {MIN_BACKTEST_RISK_REWARD_RATIO:.1f}:1 开仓要求")
    indicator_snapshot = build_indicator_snapshot(
        price,
        trend_directions,
        market_context,
        volume_to_cap,
        signal,
        strategy_type,
        quality,
        stop_loss,
        take_profit,
        entry_reasons,
    )

    return {
        "trade_signal": signal,
        "entry_price": round_price(price),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward_ratio": risk_reward_ratio,
        "opportunity_score": quality,
        "strategy_type": strategy_type,
        "entry_reasons": entry_reasons,
        "indicator_snapshot": indicator_snapshot,
        "opening_logic": build_trade_opening_logic(
            asset.symbol,
            signal,
            strategy_type,
            quality,
            price,
            stop_loss,
            take_profit,
            market_context,
            indicator_snapshot,
            entry_reasons,
        ),
    }


def build_entry_reasons(
    signal: str,
    strategy_type: str,
    market_regime: str,
    one_hour_direction: str,
    four_hour_direction: str,
    market_context: dict,
    dt_break_long: bool,
    dt_break_short: bool,
    volume_to_cap: float,
) -> list[str]:
    reasons = [
        f"大级别结构为{market_regime}",
        f"4H 方向为{four_hour_direction}",
        f"1H 方向为{one_hour_direction}",
        f"策略类型为{strategy_type}",
        f"24h成交额/市值为{volume_to_cap * 100:.2f}%，满足最低流动性过滤",
    ]
    if signal == "做多":
        if market_context.get("near_support"):
            reasons.append("价格靠近日线支撑区域，允许做多")
        if market_context.get("near_fib_support"):
            reasons.append("价格靠近斐波那契回撤支撑区域")
        if market_context.get("double_bottom"):
            reasons.append("日线结构出现双底确认")
        if dt_break_long:
            reasons.append("价格突破 DT 上轨，属于顺势突破做多")
    else:
        if market_context.get("near_resistance"):
            reasons.append("价格靠近日线阻力区域，允许做空")
        if market_context.get("near_fib_resistance"):
            reasons.append("价格靠近斐波那契反弹阻力区域")
        if market_context.get("double_top"):
            reasons.append("日线结构出现双顶确认")
        if dt_break_short:
            reasons.append("价格跌破 DT 下轨，属于顺势突破做空")
    return reasons


def build_indicator_snapshot(
    price: float,
    trend_directions: dict[str, str],
    market_context: dict,
    volume_to_cap: float,
    signal: str,
    strategy_type: str,
    quality: int,
    stop_loss: float,
    take_profit: float,
    entry_reasons: list[str],
) -> dict:
    risk = abs(price - stop_loss)
    reward = abs(take_profit - price)
    rr = reward / risk if risk else 0
    ema50 = round_optional_price(market_context.get("ema50"))
    ema100 = round_optional_price(market_context.get("ema100"))
    ema144 = round_optional_price(market_context.get("ema144"))
    ema169 = round_optional_price(market_context.get("ema169"))
    ema200 = round_optional_price(market_context.get("ema200"))
    support = round_optional_price(market_context.get("support"))
    resistance = round_optional_price(market_context.get("resistance"))
    dt_upper = round_optional_price(market_context.get("dt_upper"))
    dt_lower = round_optional_price(market_context.get("dt_lower"))
    fib_supports = [round_optional_price(level) for level in market_context.get("fib_supports", [])]
    fib_resistances = [round_optional_price(level) for level in market_context.get("fib_resistances", [])]
    return {
        "price": round_price(price),
        "one_hour_direction": trend_directions.get("1h"),
        "four_hour_direction": trend_directions.get("4h"),
        "market_regime": market_context.get("regime"),
        "support": support,
        "resistance": resistance,
        "fib_supports": fib_supports,
        "fib_resistances": fib_resistances,
        "dt_upper": dt_upper,
        "dt_lower": dt_lower,
        "ema50": ema50,
        "ema100": ema100,
        "ema144": ema144,
        "ema169": ema169,
        "ema200": ema200,
        "near_support": bool(market_context.get("near_support")),
        "near_resistance": bool(market_context.get("near_resistance")),
        "near_fib_support": bool(market_context.get("near_fib_support")),
        "near_fib_resistance": bool(market_context.get("near_fib_resistance")),
        "double_bottom": bool(market_context.get("double_bottom")),
        "double_top": bool(market_context.get("double_top")),
        "volume_to_market_cap_percent": round(volume_to_cap * 100, 2),
        "risk_reward_ratio": round(rr, 2),
        "signal_detail": f"开仓方向={signal}，策略类型={strategy_type}，指标质量分={quality}/100。",
        "trend_filter_detail": f"1H方向={trend_directions.get('1h') or '无'}，4H方向={trend_directions.get('4h') or '无'}；15m执行时，1H/4H不能与开仓方向冲突。",
        "daily_ema_detail": f"日线结构={market_context.get('regime')}；EMA50={format_optional_level(ema50)}，EMA100={format_optional_level(ema100)}，EMA200={format_optional_level(ema200)}。",
        "vegas_detail": f"Vegas EMA144={format_optional_level(ema144)}，EMA169={format_optional_level(ema169)}；价格在通道上方偏多、下方偏空。",
        "dt_detail": f"DT上轨={format_optional_level(dt_upper)}，DT下轨={format_optional_level(dt_lower)}；上破偏多，下破偏空。",
        "fib_detail": f"斐波支撑={format_level_list(fib_supports)}；斐波阻力={format_level_list(fib_resistances)}；靠近支撑={format_bool(market_context.get('near_fib_support'))}，靠近阻力={format_bool(market_context.get('near_fib_resistance'))}。",
        "support_resistance_detail": f"日线支撑={format_optional_level(support)}，日线阻力={format_optional_level(resistance)}；靠近支撑={format_bool(market_context.get('near_support'))}，靠近阻力={format_bool(market_context.get('near_resistance'))}。",
        "structure_detail": f"双底={format_bool(market_context.get('double_bottom'))}，双顶={format_bool(market_context.get('double_top'))}。",
        "volume_filter_detail": f"24h成交额/市值={volume_to_cap * 100:.2f}%，最低要求>=1.50%。",
        "risk_plan_detail": f"止损={round_price(stop_loss)}，止盈={round_price(take_profit)}，计划盈亏比约{rr:.2f}:1；结构止损距离上限为开仓价的{MAX_STRUCTURE_STOP_DISTANCE_RATIO * 100:.0f}%，超出则使用波幅止损；v4严格口径会在信号K线收盘后，以下一根15m开盘价成交。",
        "entry_reason_detail": "；".join(entry_reasons),
    }


def build_trade_opening_logic(
    symbol: str,
    signal: str,
    strategy_type: str,
    quality: int,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    market_context: dict,
    indicator_snapshot: dict,
    entry_reasons: list[str] | None = None,
) -> str:
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    rr = reward / risk if risk else 0
    direction_text = "多单" if signal == "做多" else "空单"
    reasons = entry_reasons or []
    reason_text = "；".join(reasons) if reasons else "符合当前指标策略过滤条件"
    indicator_detail_text = "；".join(
        str(indicator_snapshot.get(key))
        for key in [
            "trend_filter_detail",
            "daily_ema_detail",
            "vegas_detail",
            "dt_detail",
            "fib_detail",
            "support_resistance_detail",
            "structure_detail",
            "volume_filter_detail",
            "risk_plan_detail",
        ]
        if indicator_snapshot.get(key)
    )
    return (
        f"{symbol} 触发{direction_text}，策略类型为{strategy_type}，指标质量分 {quality}/100。"
        f"开仓价 {round_price(entry_price)}，止损 {round_price(stop_loss)}，止盈 {round_price(take_profit)}，计划盈亏比约 {rr:.2f}:1。"
        f"判断依据：{reason_text}。"
        f"逐项指标：{indicator_detail_text}。"
    )


def indicator_trend_direction(trend_rows: list[dict[str, float | int]], timestamp: int) -> str:
    available_rows = completed_candles(trend_rows, timestamp, infer_candle_interval(trend_rows))
    if len(available_rows) < TREND_LOOKBACK_CANDLES:
        return "观望"

    closes = [float(row["close"]) for row in available_rows]
    close = closes[-1]
    previous = closes[-TREND_LOOKBACK_CANDLES]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    if close <= 0 or previous <= 0 or ema20 is None or ema50 is None:
        return "观望"

    change = (close - previous) / previous
    if close > ema20 > ema50 and change > 0.015:
        return "做多"
    if close < ema20 < ema50 and change < -0.015:
        return "做空"
    return "观望"


def build_indicator_exit_prices(
    signal: str,
    price: float,
    rows: list[dict[str, float | int]],
    index: int,
    market_context: dict,
    strategy_type: str,
) -> tuple[float | None, float | None]:
    recent = rows[max(0, index - 20): index + 1]
    if not recent:
        return None, None

    average_range = sum(float(row["high"]) - float(row["low"]) for row in recent) / len(recent)
    stop_distance = max(average_range * 1.6, price * 0.012)
    reward_multiple = 2.0 if strategy_type in {"趋势多", "趋势空"} else 1.8

    support = market_context.get("support")
    resistance = market_context.get("resistance")
    if signal == "做多":
        raw_stop = price - stop_distance
        if support and float(support) < price:
            support_stop = float(support) * 0.995
            if (price - support_stop) / price <= MAX_STRUCTURE_STOP_DISTANCE_RATIO:
                raw_stop = min(raw_stop, support_stop)
        final_risk = max(price - raw_stop, stop_distance)
        raw_take_profit = price + final_risk * reward_multiple
        if strategy_type in {"区间多", "上升趋势区间多"} and resistance and float(resistance) > price:
            raw_take_profit = max(raw_take_profit, float(resistance) * 0.995)
        return round_price(raw_stop), round_price(raw_take_profit)

    raw_stop = price + stop_distance
    if resistance and float(resistance) > price:
        resistance_stop = float(resistance) * 1.005
        if (resistance_stop - price) / price <= MAX_STRUCTURE_STOP_DISTANCE_RATIO:
            raw_stop = max(raw_stop, resistance_stop)
    final_risk = max(raw_stop - price, stop_distance)
    raw_take_profit = price - final_risk * reward_multiple
    if strategy_type in {"区间空", "下降趋势区间空"} and support and float(support) < price:
        raw_take_profit = min(raw_take_profit, float(support) * 1.005)
    if raw_take_profit <= 0:
        raw_take_profit = price * 0.98
    return round_price(raw_stop), round_price(raw_take_profit)


def directional_opportunity_score(signal: str, ai_score: int, trend_score: int, liquidity_score: int, risk_score: int) -> int:
    if signal == "做空":
        directional_ai = 100 - ai_score
        directional_trend = 100 - trend_score
    else:
        directional_ai = ai_score
        directional_trend = trend_score
    score = directional_ai * 0.35 + directional_trend * 0.3 + liquidity_score * 0.2 + (100 - risk_score) * 0.15
    return max(0, min(100, round(score)))


def build_trend_signal(trend_rows: list[dict[str, float | int]], timestamp: int, asset: AssetSnapshot, interval: str = "4h") -> str:
    available_rows = completed_candles(trend_rows, timestamp, interval)
    lookback = TREND_LOOKBACK_CANDLES
    if len(available_rows) <= lookback:
        return "观望"
    current = available_rows[-1]
    previous = available_rows[-1 - lookback]
    current_close = float(current["close"])
    previous_close = float(previous["close"])
    if current_close <= 0 or previous_close <= 0:
        return "观望"
    change_24h = (current_close - previous_close) / previous_close * 100
    scores = calculate_scores(change_24h, float(asset.market_cap), float(asset.volume_24h))
    plan = build_trade_plan(
        current_price=current_close,
        change_24h=change_24h,
        ai_score=scores["ai_score"],
        trend_score=scores["trend_score"],
        liquidity_score=scores["liquidity_score"],
        risk_score=scores["risk_score"],
    )
    return str(plan["trade_signal"])


def build_daily_market_context(daily_rows: list[dict[str, float | int]], timestamp: int, execution_price: float) -> dict:
    available_rows = completed_candles(daily_rows, timestamp, "1d")
    if len(available_rows) < TREND_LOOKBACK_CANDLES:
        return {
            "regime": "数据不足",
            "near_support": False,
            "near_resistance": False,
            "near_fib_support": False,
            "near_fib_resistance": False,
            "double_bottom": False,
            "double_top": False,
        }

    closes = [float(row["close"]) for row in available_rows]
    highs = [float(row["high"]) for row in available_rows]
    lows = [float(row["low"]) for row in available_rows]
    close = float(closes[-1] or execution_price)
    recent_high = max(highs[-90:])
    recent_low = min(lows[-90:])
    support = min(lows[-30:])
    resistance = max(highs[-30:])
    range_size = max(recent_high - recent_low, close * 0.001)
    fib_382 = recent_high - range_size * 0.382
    fib_500 = recent_high - range_size * 0.5
    fib_618 = recent_high - range_size * 0.618
    down_fib_382 = recent_low + range_size * 0.382
    down_fib_500 = recent_low + range_size * 0.5
    down_fib_618 = recent_low + range_size * 0.618
    ema50 = ema(closes, 50)
    ema100 = ema(closes, 100)
    ema144 = ema(closes, 144)
    ema169 = ema(closes, 169)
    ema200 = ema(closes, 200)
    dt_upper = max(highs[-20:])
    dt_lower = min(lows[-20:])
    trend_slope = close - closes[-TREND_LOOKBACK_CANDLES]
    vegas_ready = ema144 is not None and ema169 is not None
    vegas_mid = ((ema144 or close) + (ema169 or close)) / 2
    uptrend = ema50 is not None and ema100 is not None and close > ema50 > ema100 and trend_slope > 0
    downtrend = ema50 is not None and ema100 is not None and close < ema50 < ema100 and trend_slope < 0
    if vegas_ready:
        uptrend = uptrend and close >= vegas_mid
        downtrend = downtrend and close <= vegas_mid

    if uptrend:
        regime = "上升趋势"
    elif downtrend:
        regime = "下降趋势"
    else:
        regime = "震荡区间"

    return {
        "regime": regime,
        "ema50": ema50,
        "ema100": ema100,
        "ema144": ema144,
        "ema169": ema169,
        "ema200": ema200,
        "dt_upper": dt_upper,
        "dt_lower": dt_lower,
        "support": support,
        "resistance": resistance,
        "fib_supports": [fib_382, fib_500, fib_618],
        "fib_resistances": [down_fib_382, down_fib_500, down_fib_618],
        "near_support": is_near_level(execution_price, support, 0.025),
        "near_resistance": is_near_level(execution_price, resistance, 0.025),
        "near_fib_support": any(is_near_level(execution_price, level, 0.025) for level in [fib_382, fib_500, fib_618]),
        "near_fib_resistance": any(is_near_level(execution_price, level, 0.025) for level in [down_fib_382, down_fib_500, down_fib_618]),
        "double_bottom": has_double_bottom(available_rows[-45:]),
        "double_top": has_double_top(available_rows[-45:]),
    }


def classify_strategy_type(signal: str, price: float, market_context: dict) -> str:
    regime = market_context["regime"]
    if regime == "上升趋势" and signal == "做多":
        if market_context["near_support"] or market_context["near_fib_support"] or market_context["double_bottom"]:
            return "上升趋势区间多"
        return "趋势多"
    if regime == "下降趋势" and signal == "做空":
        if market_context["near_resistance"] or market_context["near_fib_resistance"] or market_context["double_top"]:
            return "下降趋势区间空"
        return "趋势空"
    if regime == "震荡区间":
        if signal == "做多" and (market_context["near_support"] or market_context["double_bottom"]):
            return "区间多"
        if signal == "做空" and (market_context["near_resistance"] or market_context["double_top"]):
            return "区间空"
    return "不匹配"


def is_allowed_by_market_context(signal: str, strategy_type: str, market_context: dict) -> bool:
    regime = market_context["regime"]
    if regime == "数据不足":
        return False
    if strategy_type == "不匹配":
        return False
    if regime == "上升趋势":
        return signal == "做多"
    if regime == "下降趋势":
        return signal == "做空"
    return strategy_type in {"区间多", "区间空"}


def context_score_bonus(strategy_type: str, market_context: dict) -> int:
    bonus = 0
    if strategy_type in {"上升趋势区间多", "下降趋势区间空"}:
        bonus += 3
    if strategy_type in {"区间多", "区间空"}:
        bonus += 2
    if market_context["double_bottom"] or market_context["double_top"]:
        bonus += 2
    if market_context["near_fib_support"] or market_context["near_fib_resistance"]:
        bonus += 1
    return bonus


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    value = sum(values[:period]) / period
    for price in values[period:]:
        value = (price - value) * multiplier + value
    return value


def is_near_level(price: float, level: float | None, tolerance: float) -> bool:
    if not level or price <= 0:
        return False
    return abs(price - level) / price <= tolerance


def has_double_bottom(rows: list[dict[str, float | int]]) -> bool:
    if len(rows) < 20:
        return False
    lows = [float(row["low"]) for row in rows]
    closes = [float(row["close"]) for row in rows]
    first_index = lows.index(min(lows[:-8]))
    second_segment = lows[first_index + 5:]
    if len(second_segment) < 5:
        return False
    second_low = min(second_segment)
    first_low = lows[first_index]
    neckline = max(closes[first_index:first_index + len(second_segment)])
    return abs(second_low - first_low) / max(first_low, 0.00000001) <= 0.035 and closes[-1] > neckline


def has_double_top(rows: list[dict[str, float | int]]) -> bool:
    if len(rows) < 20:
        return False
    highs = [float(row["high"]) for row in rows]
    closes = [float(row["close"]) for row in rows]
    first_index = highs.index(max(highs[:-8]))
    second_segment = highs[first_index + 5:]
    if len(second_segment) < 5:
        return False
    second_high = max(second_segment)
    first_high = highs[first_index]
    neckline = min(closes[first_index:first_index + len(second_segment)])
    return abs(second_high - first_high) / max(first_high, 0.00000001) <= 0.035 and closes[-1] < neckline


def resample_candles(candles: list[dict[str, float | int]], bucket_seconds: int) -> list[dict[str, float | int]]:
    buckets: dict[int, list[dict[str, float | int]]] = {}
    for candle in candles:
        bucket = int(candle["time"]) // bucket_seconds * bucket_seconds
        buckets.setdefault(bucket, []).append(candle)

    rows = []
    for bucket, bucket_candles in sorted(buckets.items()):
        rows.append(
            {
                "time": bucket,
                "open": float(bucket_candles[0]["open"]),
                "high": max(float(candle["high"]) for candle in bucket_candles),
                "low": min(float(candle["low"]) for candle in bucket_candles),
                "close": float(bucket_candles[-1]["close"]),
                "volume": sum(float(candle.get("volume") or 0) for candle in bucket_candles),
            }
        )
    return rows


def build_asset_result(asset: AssetSnapshot, candle_count: int, best_score: int, best_signal: str, trades: list[dict], status: str, execution_interval: str) -> dict:
    total_pnl = round(sum(trade["pnl_usdt"] for trade in trades), 2)
    wins = sum(1 for trade in trades if trade["pnl_usdt"] > 0)
    losses = sum(1 for trade in trades if trade["pnl_usdt"] < 0)
    return {
        "symbol": asset.symbol,
        "name": asset.name,
        "market_cap": float(asset.market_cap),
        "candle_count": candle_count,
        "best_opportunity_score": best_score,
        "best_signal": best_signal,
        "total_trades": len(trades),
        "winning_trades": wins,
        "losing_trades": losses,
        "total_pnl": total_pnl,
        "status": status,
        "execution_interval": execution_interval,
    }


def build_report_asset_results(source_assets: list[dict], trades: list[dict], execution_interval: str) -> list[dict]:
    trades_by_symbol: dict[str, list[dict]] = {}
    for trade in trades:
        trades_by_symbol.setdefault(str(trade["symbol"]), []).append(trade)

    results = []
    for asset in source_assets:
        symbol = str(asset["symbol"])
        symbol_trades = trades_by_symbol.get(symbol, [])
        wins = sum(1 for trade in symbol_trades if trade["pnl_usdt"] > 0)
        losses = sum(1 for trade in symbol_trades if trade["pnl_usdt"] < 0)
        original_trades = int(asset.get("total_trades") or 0)
        if symbol_trades:
            status = "触发交易"
        elif original_trades > 0:
            status = "期末平仓已排除"
        else:
            status = str(asset.get("status") or "未触发")
        results.append(
            {
                **asset,
                "total_trades": len(symbol_trades),
                "winning_trades": wins,
                "losing_trades": losses,
                "total_pnl": round(sum(float(trade["pnl_usdt"]) for trade in symbol_trades), 2),
                "status": status,
                "execution_interval": execution_interval,
            }
        )

    return sorted(results, key=lambda item: (item["total_trades"], item["best_opportunity_score"], item["market_cap"]), reverse=True)


def maybe_close_trade(trade: dict, high: float, low: float, close: float, timestamp: int) -> dict | None:
    if trade["side"] == "做多":
        if low <= trade["stop_loss"]:
            return close_trade(trade, trade["stop_loss"], timestamp, "止损")
        if high >= trade["take_profit"]:
            return close_trade(trade, trade["take_profit"], timestamp, "止盈")
    if trade["side"] == "做空":
        if high >= trade["stop_loss"]:
            return close_trade(trade, trade["stop_loss"], timestamp, "止损")
        if low <= trade["take_profit"]:
            return close_trade(trade, trade["take_profit"], timestamp, "止盈")
    opened_timestamp = int(trade.get("opened_timestamp") or timestamp)
    max_holding_seconds = int(trade.get("max_holding_seconds") or 0)
    if max_holding_seconds and timestamp - opened_timestamp >= max_holding_seconds:
        return close_trade(trade, close, timestamp, "到期平仓")
    trade["current_price"] = close
    return None


def close_trade(trade: dict, exit_price: float, timestamp: int, reason: str) -> dict:
    closed = dict(trade)
    closed["exit_price"] = exit_price
    closed["current_price"] = exit_price
    closed["closed_timestamp"] = timestamp
    closed["closed_at"] = iso_from_timestamp(timestamp)
    closed["close_reason"] = reason
    closed["pnl_usdt"] = calculate_pnl(closed["side"], closed["entry_price"], exit_price, closed["notional_usdt"])
    closed["pnl_percent"] = round(closed["pnl_usdt"] / closed["margin_usdt"] * 100, 2) if closed["margin_usdt"] else 0
    return closed


def apply_portfolio_margin_limit(trades: list[dict], account_balance: float) -> tuple[list[dict], int, int]:
    if account_balance <= 0:
        return trades, 0, 0

    accepted: list[dict] = []
    open_trades: list[dict] = []
    max_concurrent = 0
    skipped = 0

    for trade in sorted(trades, key=lambda item: (int(item.get("opened_timestamp") or 0), str(item.get("symbol") or ""))):
        opened_timestamp = int(trade.get("opened_timestamp") or 0)
        open_trades = [
            open_trade
            for open_trade in open_trades
            if int(open_trade.get("closed_timestamp") or 0) > opened_timestamp
        ]
        used_margin = sum(float(open_trade.get("margin_usdt") or 0) for open_trade in open_trades)
        trade_margin = float(trade.get("margin_usdt") or 0)
        if used_margin + trade_margin > account_balance:
            skipped += 1
            continue
        accepted.append(trade)
        open_trades.append(trade)
        max_concurrent = max(max_concurrent, len(open_trades))

    return accepted, skipped, max_concurrent


def calculate_max_concurrent_trades(trades: list[dict]) -> int:
    events: list[tuple[int, int]] = []
    for trade in trades:
        opened_timestamp = int(trade.get("opened_timestamp") or 0)
        closed_timestamp = int(trade.get("closed_timestamp") or 0)
        if opened_timestamp:
            events.append((opened_timestamp, 1))
        if closed_timestamp:
            events.append((closed_timestamp, -1))
    active = 0
    max_active = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        active += delta
        max_active = max(max_active, active)
    return max_active


def calculate_pnl(side: str, entry_price: float, exit_price: float, notional: float) -> float:
    if entry_price <= 0:
        return 0
    if side == "做空":
        value = (entry_price - exit_price) / entry_price * notional
    else:
        value = (exit_price - entry_price) / entry_price * notional
    return round(value, 2)


def calculate_trade_fee(trade: dict) -> float:
    notional = float(trade.get("notional_usdt") or 0)
    if notional <= 0:
        notional = float(trade.get("margin_usdt") or 0) * float(trade.get("leverage") or 0)
    return round(notional * BACKTEST_FEE_RATE, 2) if notional > 0 else 0


def calculate_plan_risk_reward(entry_price: float, stop_loss: float, take_profit: float) -> float:
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    if risk <= 0:
        return 0
    return round(reward / risk, 2)


def build_backtest_summary(
    trades: list[dict],
    account_balance: float,
    days: int,
    tested_assets: int,
    execution_interval: str,
    trend_interval: str = "4h",
    excluded_period_end_trades: int = 0,
    excluded_low_risk_reward_trades: int = 0,
    excluded_portfolio_trades: int = 0,
    max_concurrent_trades: int = 0,
) -> dict:
    total_pnl = round(sum(trade["pnl_usdt"] for trade in trades), 2)
    total_fees = round(sum(calculate_trade_fee(trade) for trade in trades), 2)
    net_pnl = round(total_pnl - total_fees, 2)
    wins = sum(1 for trade in trades if trade["pnl_usdt"] > 0)
    losses = sum(1 for trade in trades if trade["pnl_usdt"] < 0)
    net_wins = sum(1 for trade in trades if round(float(trade["pnl_usdt"]) - calculate_trade_fee(trade), 2) > 0)
    return {
        "days": days,
        "tested_assets": tested_assets,
        "traded_assets": len({trade["symbol"] for trade in trades}),
        "total_trades": len(trades),
        "winning_trades": wins,
        "losing_trades": losses,
        "win_rate": round(wins / len(trades) * 100, 2) if trades else 0,
        "total_pnl": total_pnl,
        "total_pnl_percent": round(total_pnl / account_balance * 100, 2) if account_balance else 0,
        "average_pnl": round(total_pnl / len(trades), 2) if trades else 0,
        "fee_rate": BACKTEST_FEE_RATE,
        "total_fees": total_fees,
        "net_pnl": net_pnl,
        "net_pnl_percent": round(net_pnl / account_balance * 100, 2) if account_balance else 0,
        "average_net_pnl": round(net_pnl / len(trades), 2) if trades else 0,
        "net_win_rate": round(net_wins / len(trades) * 100, 2) if trades else 0,
        "best_trade": max((trade["pnl_usdt"] for trade in trades), default=0),
        "worst_trade": min((trade["pnl_usdt"] for trade in trades), default=0),
        "execution_interval": execution_interval,
        "trend_interval": trend_interval,
        "excluded_period_end_trades": excluded_period_end_trades,
        "excluded_low_risk_reward_trades": excluded_low_risk_reward_trades,
        "excluded_portfolio_trades": excluded_portfolio_trades,
        "max_concurrent_trades": max_concurrent_trades,
    }


def derive_backtest_period_summary(source_run: BacktestRun, target_days: int, account_balance: float) -> dict:
    source_summary = json.loads(source_run.summary_json)
    trades = json.loads(source_run.trades_json)
    period_trades = filter_trades_for_recent_days(trades, target_days)
    period_closed_trades = exclude_period_end_trades(period_trades)
    filtered_trades = exclude_low_risk_reward_trades(period_closed_trades)
    excluded_period_end_trades = len(period_trades) - len(period_closed_trades)
    excluded_low_risk_reward_trades = len(period_closed_trades) - len(filtered_trades)
    if excluded_period_end_trades == 0 and target_days == source_run.days:
        excluded_period_end_trades = int(source_summary.get("excluded_period_end_trades") or 0)
    excluded_portfolio_trades = int(source_summary.get("excluded_portfolio_trades") or 0) if target_days == source_run.days else 0
    max_concurrent_trades = calculate_max_concurrent_trades(filtered_trades)
    summary = build_backtest_summary(
        filtered_trades,
        account_balance,
        target_days,
        int(source_summary.get("tested_assets") or source_run.tested_assets),
        source_run.execution_interval,
        source_run.trend_interval,
        excluded_period_end_trades=excluded_period_end_trades,
        excluded_low_risk_reward_trades=excluded_low_risk_reward_trades,
        excluded_portfolio_trades=excluded_portfolio_trades,
        max_concurrent_trades=max_concurrent_trades,
    )
    summary.update(
        {
            "run_id": source_run.id,
            "run_key": source_run.run_key,
            "strategy_mode": source_run.strategy_mode,
            "strategy_version": source_run.strategy_version,
            "generated_at": source_run.created_at.isoformat() if source_run.created_at else None,
        }
    )
    return summary


def derive_backtest_period_result(source_run: BacktestRun, target_days: int, account_balance: float, trade_limit: int | None = None) -> dict:
    trades = json.loads(source_run.trades_json)
    period_trades = filter_trades_for_recent_days(trades, target_days)
    filtered_trades = annotate_backtest_trades(exclude_low_risk_reward_trades(exclude_period_end_trades(period_trades)))
    summary = derive_backtest_period_summary(source_run, target_days, account_balance)
    sorted_trades = sorted(filtered_trades, key=lambda trade: trade["opened_at"], reverse=True)
    if trade_limit is not None:
        sorted_trades = sorted_trades[:max(0, trade_limit)]
    return {
        "summary": summary,
        "rules": normalize_backtest_rules(json.loads(source_run.rules_json), source_run.strategy_mode, source_run.execution_interval, source_run.trend_interval, source_run.strategy_version),
        "equity_curve": build_backtest_equity_curve(filtered_trades, account_balance, target_days),
        "trades": sorted_trades,
        "assets": build_derived_asset_results(json.loads(source_run.assets_json), filtered_trades, source_run.execution_interval),
    }


def normalize_backtest_rules(rules: dict, strategy_mode: str, execution_interval: str, trend_interval: str, strategy_version: str | None = None) -> dict:
    normalized = dict(rules or {})
    if strategy_mode == "indicator" and strategy_version == BACKTEST_STRATEGY_VERSION:
        fresh_rules = build_backtest_rules(strategy_mode, execution_interval, trend_interval, get_settings().paper_min_opportunity_score)
        for key, value in fresh_rules.items():
            normalized[key] = value
    normalized["title"] = strategy_version or BACKTEST_STRATEGY_VERSION
    normalized["version"] = strategy_version or BACKTEST_STRATEGY_VERSION
    return normalized


def exclude_period_end_trades(trades: list[dict]) -> list[dict]:
    return [trade for trade in trades if trade.get("close_reason") != "期末平仓"]


def exclude_low_risk_reward_trades(trades: list[dict]) -> list[dict]:
    return [trade for trade in trades if get_trade_risk_reward_ratio(trade) >= MIN_BACKTEST_RISK_REWARD_RATIO]


def get_trade_risk_reward_ratio(trade: dict) -> float:
    stored = trade.get("risk_reward_ratio")
    if stored is not None:
        try:
            return float(stored)
        except (TypeError, ValueError):
            pass
    try:
        return calculate_plan_risk_reward(
            float(trade.get("entry_price") or 0),
            float(trade.get("stop_loss") or 0),
            float(trade.get("take_profit") or 0),
        )
    except (TypeError, ValueError):
        return 0


def annotate_backtest_trades(trades: list[dict]) -> list[dict]:
    return [annotate_backtest_trade(trade) for trade in trades]


def annotate_backtest_trade(trade: dict) -> dict:
    annotated = dict(trade)
    strategy_type = str(annotated.get("strategy_type") or infer_strategy_type_from_trade(annotated))
    market_regime = str(annotated.get("market_regime") or infer_market_regime_from_strategy_type(strategy_type))
    annotated["strategy_type"] = strategy_type
    annotated["market_regime"] = market_regime
    if not isinstance(annotated.get("entry_reasons"), list):
        annotated["entry_reasons"] = build_legacy_entry_reasons(annotated, strategy_type, market_regime)
    if not isinstance(annotated.get("indicator_snapshot"), dict):
        annotated["indicator_snapshot"] = build_legacy_indicator_snapshot(annotated, strategy_type, market_regime)
    if not annotated.get("opening_logic"):
        annotated["opening_logic"] = build_legacy_opening_logic(annotated, strategy_type, market_regime)
    return annotated


def infer_strategy_type_from_trade(trade: dict) -> str:
    side = trade.get("side")
    if side == "做空":
        return "趋势空"
    if side == "做多":
        return "趋势多"
    return "未知策略"


def infer_market_regime_from_strategy_type(strategy_type: str) -> str:
    if "多" in strategy_type and "区间" not in strategy_type:
        return "上升趋势"
    if "空" in strategy_type and "区间" not in strategy_type:
        return "下降趋势"
    if "上升" in strategy_type:
        return "上升趋势"
    if "下降" in strategy_type:
        return "下降趋势"
    if "区间" in strategy_type:
        return "震荡区间"
    return "未知"


def build_legacy_entry_reasons(trade: dict, strategy_type: str, market_regime: str) -> list[str]:
    reasons = [
        f"历史回测交易，保存时未记录完整逐项指标快照，当前根据已保存字段还原说明",
        f"大级别结构记录为{market_regime}",
        f"策略类型记录为{strategy_type}",
        f"开仓方向为{trade.get('side') or '未知'}",
        f"指标质量分为{trade.get('opportunity_score') or 0}/100，达到 80 分开仓门槛",
    ]
    if trade.get("stop_loss") and trade.get("take_profit"):
        reasons.append("开仓时已生成止盈止损计划，因此允许进入回测交易")
    return reasons


def build_legacy_indicator_snapshot(trade: dict, strategy_type: str, market_regime: str) -> dict:
    return {
        "price": trade.get("entry_price"),
        "market_regime": market_regime,
        "strategy_type": strategy_type,
        "note": "旧回测记录未保存逐项指标数值；重新跑回测后会记录 1H/4H方向、日线EMA、Vegas、DT、斐波、支撑阻力和量价过滤。",
    }


def build_legacy_opening_logic(trade: dict, strategy_type: str, market_regime: str) -> str:
    entry_price = float(trade.get("entry_price") or 0)
    stop_loss = float(trade.get("stop_loss") or 0)
    take_profit = float(trade.get("take_profit") or 0)
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    rr = reward / risk if risk else 0
    return (
        f"{trade.get('symbol')} 历史回测触发{trade.get('side')}，策略类型为{strategy_type}，大级别结构为{market_regime}，"
        f"指标质量分 {trade.get('opportunity_score') or 0}/100。开仓价 {round_price(entry_price)}，"
        f"止损 {round_price(stop_loss)}，止盈 {round_price(take_profit)}，计划盈亏比约 {rr:.2f}:1。"
        "这条旧记录保存时还没有逐项指标快照，当前说明由已保存的方向、策略类型、开仓价、止盈止损和分数还原；重新跑回测后会保存完整指标明细。"
    )


def build_derived_asset_results(source_assets: list[dict], trades: list[dict], execution_interval: str) -> list[dict]:
    trades_by_symbol: dict[str, list[dict]] = {}
    for trade in trades:
        trades_by_symbol.setdefault(str(trade["symbol"]), []).append(trade)

    assets_by_symbol = {str(asset["symbol"]): asset for asset in source_assets}
    results = []
    for symbol, symbol_trades in trades_by_symbol.items():
        source = assets_by_symbol.get(symbol, {})
        wins = sum(1 for trade in symbol_trades if trade["pnl_usdt"] > 0)
        losses = sum(1 for trade in symbol_trades if trade["pnl_usdt"] < 0)
        results.append(
            {
                "symbol": symbol,
                "name": source.get("name") or symbol_trades[0].get("name") or symbol,
                "market_cap": float(source.get("market_cap") or 0),
                "candle_count": int(source.get("candle_count") or 0),
                "best_opportunity_score": max((int(trade.get("opportunity_score") or 0) for trade in symbol_trades), default=0),
                "best_signal": symbol_trades[0].get("side") or "观望",
                "total_trades": len(symbol_trades),
                "winning_trades": wins,
                "losing_trades": losses,
                "total_pnl": round(sum(float(trade["pnl_usdt"]) for trade in symbol_trades), 2),
                "status": "派生交易",
                "execution_interval": execution_interval,
            }
        )

    return sorted(results, key=lambda item: (item["total_trades"], item["best_opportunity_score"], item["total_pnl"]), reverse=True)


def filter_trades_for_recent_days(trades: list[dict], days: int) -> list[dict]:
    if not trades:
        return []

    timestamps = [parse_backtest_time(trade.get("opened_at")) for trade in trades if trade.get("opened_at")]
    timestamps = [timestamp for timestamp in timestamps if timestamp is not None]
    if not timestamps:
        return []

    end_time = max(timestamps)
    cutoff = end_time - timedelta(days=days)
    return [
        trade for trade in trades
        if (opened_at := parse_backtest_time(trade.get("opened_at"))) is not None and opened_at >= cutoff
    ]


def parse_backtest_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def round_optional_price(value) -> float | None:
    if value is None:
        return None
    try:
        return round_price(float(value))
    except (TypeError, ValueError):
        return None


def format_optional_level(value) -> str:
    rounded = round_optional_price(value)
    return str(rounded) if rounded is not None else "暂无"


def format_level_list(values: list[float | None]) -> str:
    formatted = [format_optional_level(value) for value in values if value is not None]
    return " / ".join(formatted) if formatted else "暂无"


def format_bool(value) -> str:
    return "是" if bool(value) else "否"


def build_backtest_equity_curve(trades: list[dict], account_balance: float, days: int) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    points = []
    cumulative = 0.0
    trades_by_date: dict[str, list[dict]] = {}
    for trade in trades:
        date_key = str(datetime.fromisoformat(trade["closed_at"].replace("Z", "+00:00")).date())
        trades_by_date.setdefault(date_key, []).append(trade)

    for offset in range(days):
        current_date = start + timedelta(days=offset)
        for trade in trades_by_date.get(str(current_date), []):
            cumulative += trade["pnl_usdt"]
        points.append(
            {
                "date": current_date.isoformat(),
                "equity": round(account_balance + cumulative, 2),
                "pnl": round(cumulative, 2),
            }
        )
    return points


def iso_from_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
