import csv
import io
import zipfile
from datetime import date, datetime, timedelta, timezone
from time import time

import httpx
from sqlalchemy import func, select, true
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ai import generate_summary
from app.config import get_settings
from app.models import AssetSnapshot, OhlcCandle, PaperTrade
from app.scoring import calculate_scores
from app.technicals import calculate_technicals, empty_technicals, volume_price_relation
from app.trade_logic import opportunity_status, round_price

SYMBOL_TO_ID = {"BTC": "bitcoin", "ETH": "ethereum"}
SYMBOL_TO_BINANCE_PAIR = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}
BINANCE_DATA_BASE_URL = "https://data.binance.vision"
BINANCE_FUTURES_ID_PREFIX = "binance-futures:"
OHLC_CACHE_TTL_SECONDS = 900
OHLC_CACHE: dict[str, tuple[float, list[dict[str, float | int]]]] = {}
SUPPORTED_KLINE_INTERVALS = {"15m", "1h", "4h"}


def load_ohlc_from_db(db: Session, symbol: str, interval: str, days: int) -> list[dict[str, float | int]]:
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    rows = list(
        db.scalars(
            select(OhlcCandle)
            .where(
                OhlcCandle.symbol == symbol.upper(),
                OhlcCandle.interval == interval,
                OhlcCandle.time >= cutoff,
            )
            .order_by(OhlcCandle.time.asc())
        )
    )
    return [
        {
            "time": row.time,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in rows
    ]


def load_ohlc_from_db_range(db: Session, symbol: str, interval: str, start_date: date, end_date: date) -> list[dict[str, float | int]]:
    start_timestamp = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    end_timestamp = int(datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    rows = list(
        db.scalars(
            select(OhlcCandle)
            .where(
                OhlcCandle.symbol == symbol.upper(),
                OhlcCandle.interval == interval,
                OhlcCandle.time >= start_timestamp,
                OhlcCandle.time < end_timestamp,
            )
            .order_by(OhlcCandle.time.asc())
        )
    )
    return [
        {
            "time": row.time,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in rows
    ]


def get_latest_ohlc_time(db: Session, symbol: str, interval: str) -> int | None:
    return db.scalar(
        select(func.max(OhlcCandle.time)).where(
            OhlcCandle.symbol == symbol.upper(),
            OhlcCandle.interval == interval,
        )
    )


async def ensure_volume_ohlc_from_data_vision(
    db: Session,
    symbol: str,
    coingecko_id: str,
    interval: str = "4h",
    days: int = 90,
) -> list[dict[str, float | int]]:
    normalized_interval = normalize_kline_interval(interval)
    existing = load_ohlc_from_db(db, symbol, normalized_interval, days)
    if sum(1 for candle in existing if float(candle.get("volume") or 0) > 0) >= 30:
        return existing

    pair = build_binance_pair(symbol)
    if not pair:
        return existing
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=max(30, min(days, 180)))
    data_vision_market = "futures_um" if is_binance_futures_asset(coingecko_id) else "spot"
    candles = await fetch_binance_data_vision_klines(pair, normalized_interval, start_date, today, market=data_vision_market)
    if candles:
        save_ohlc_to_db(db, symbol, coingecko_id, normalized_interval, candles, source="binance-data-vision")
        return load_ohlc_from_db(db, symbol, normalized_interval, days)
    candles = (
        await fetch_binance_futures_ohlc(pair, days, normalized_interval)
        if data_vision_market == "futures_um"
        else await fetch_binance_ohlc(symbol, days, normalized_interval)
    )
    if candles:
        save_ohlc_to_db(db, symbol, coingecko_id, normalized_interval, candles, source="binance-api")
        return load_ohlc_from_db(db, symbol, normalized_interval, days)
    return existing


def save_ohlc_to_db(
    db: Session,
    symbol: str,
    coingecko_id: str,
    interval: str,
    candles: list[dict[str, float | int]],
    source: str = "external",
) -> int:
    if not candles:
        return 0
    values = [
        {
            "symbol": symbol.upper(),
            "coingecko_id": coingecko_id,
            "interval": interval,
            "time": int(candle["time"]),
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
            "volume": float(candle.get("volume") or 0),
            "source": source,
        }
        for candle in candles
    ]
    batch_size = 3000
    for start in range(0, len(values), batch_size):
        statement = pg_insert(OhlcCandle).values(values[start : start + batch_size])
        statement = statement.on_conflict_do_update(
            constraint="uq_ohlc_symbol_interval_time",
            set_={
                "open": statement.excluded.open,
                "high": statement.excluded.high,
                "low": statement.excluded.low,
                "close": statement.excluded.close,
                "volume": statement.excluded.volume,
                "coingecko_id": statement.excluded.coingecko_id,
                "source": statement.excluded.source,
            },
        )
        db.execute(statement)
    db.commit()
    return len(values)


def has_enough_ohlc(candles: list[dict[str, float | int]], days: int, interval: str) -> bool:
    minimum = days * int(interval_candles_per_day(interval) * 0.75)
    return len(candles) >= minimum


def has_enough_ohlc_range(candles: list[dict[str, float | int]], start_date: date, end_date: date, interval: str) -> bool:
    days = max(1, (end_date - start_date).days + 1)
    minimum = days * int(interval_candles_per_day(interval) * 0.75)
    return len(candles) >= minimum


def normalize_kline_interval(interval: str) -> str:
    normalized = interval.strip()
    return normalized if normalized in SUPPORTED_KLINE_INTERVALS else "1h"


def interval_candles_per_day(interval: str) -> int:
    return {"15m": 96, "1h": 24, "4h": 6}.get(interval, 24)


def is_binance_futures_asset(coingecko_id: str | None) -> bool:
    return bool(coingecko_id and coingecko_id.startswith(BINANCE_FUTURES_ID_PREFIX))


def futures_asset_id(pair: str) -> str:
    return f"{BINANCE_FUTURES_ID_PREFIX}{pair.upper()}"


def normalize_futures_pair(symbol: str) -> str:
    normalized_symbol = symbol.upper()
    if normalized_symbol.endswith(("USDT", "USDC", "USD")):
        return normalized_symbol
    return build_binance_pair(normalized_symbol) or normalized_symbol


def parse_float(value, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def universe_asset_where_clause():
    if get_settings().market_universe_source == "binance_futures":
        return AssetSnapshot.coingecko_id.like(f"{BINANCE_FUTURES_ID_PREFIX}%")
    return true()


async def fetch_market_data(coingecko_ids: list[str] | None = None, sparkline: bool = False) -> list[dict]:
    settings = get_settings()
    if settings.market_universe_source == "binance_futures" and not sparkline:
        futures_ids = [item for item in coingecko_ids or [] if is_binance_futures_asset(item)]
        coingecko_only_ids = [item for item in coingecko_ids or [] if not is_binance_futures_asset(item)]
        rows = await fetch_binance_futures_market_data(futures_ids or None) if coingecko_ids is None or futures_ids else []
        if coingecko_only_ids:
            rows.extend(await fetch_coingecko_market_data(coingecko_only_ids, sparkline=False))
        return rows

    return await fetch_coingecko_market_data(coingecko_ids, sparkline)


async def fetch_coingecko_market_data(coingecko_ids: list[str] | None = None, sparkline: bool = False) -> list[dict]:
    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": settings.tracked_asset_count,
        "page": 1,
        "sparkline": "true" if sparkline else "false",
    }
    if coingecko_ids:
        params["ids"] = ",".join(coingecko_ids)
        params["per_page"] = min(max(len(coingecko_ids), 1), 250)

    async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=20) as client:
        response = await client.get(
            "/coins/markets",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


async def fetch_binance_futures_market_data(coingecko_ids: list[str] | None = None) -> list[dict]:
    settings = get_settings()
    wanted_ids = set(coingecko_ids or [])
    wanted_pairs = {item.removeprefix(BINANCE_FUTURES_ID_PREFIX).upper() for item in wanted_ids if is_binance_futures_asset(item)}

    exchange_info = None
    tickers = None
    for base_url in settings.futures_base_url_list:
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=20) as client:
                exchange_info_response = await client.get("/fapi/v1/exchangeInfo")
                ticker_response = await client.get("/fapi/v1/ticker/24hr")
                exchange_info_response.raise_for_status()
                ticker_response.raise_for_status()
                exchange_info = exchange_info_response.json()
                tickers = ticker_response.json()
                break
        except httpx.HTTPError:
            continue
    if exchange_info is None or tickers is None:
        return []

    quote_assets = settings.futures_quote_asset_list or {"USDT"}
    contract_type = settings.binance_futures_contract_type.upper()
    symbols_by_pair = {
        item["symbol"]: item
        for item in exchange_info.get("symbols", [])
        if item.get("status") == "TRADING"
        and item.get("quoteAsset", "").upper() in quote_assets
        and (contract_type == "ALL" or item.get("contractType", "").upper() == contract_type)
    }
    rows = []
    for ticker in tickers:
        pair = str(ticker.get("symbol") or "").upper()
        info = symbols_by_pair.get(pair)
        if not info:
            continue
        if wanted_pairs and pair not in wanted_pairs:
            continue
        last_price = parse_float(ticker.get("lastPrice"))
        quote_volume = parse_float(ticker.get("quoteVolume"))
        if last_price <= 0 or quote_volume <= 0:
            continue
        base_asset = str(info.get("baseAsset") or pair).upper()
        rows.append(
            {
                "id": futures_asset_id(pair),
                "symbol": pair,
                "name": f"{base_asset} {info.get('quoteAsset', 'USDT')} Perpetual",
                "image": None,
                "current_price": last_price,
                "market_cap": quote_volume,
                "total_volume": quote_volume,
                "price_change_percentage_24h": parse_float(ticker.get("priceChangePercent")),
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "binance_pair": pair,
                "base_asset": base_asset,
                "quote_asset": info.get("quoteAsset", "USDT"),
                "contract_type": info.get("contractType", "PERPETUAL"),
            }
        )

    rows.sort(key=lambda item: float(item["total_volume"]), reverse=True)
    if wanted_pairs:
        return rows
    return rows[: settings.tracked_asset_count]


async def fetch_historical_data(coingecko_id: str) -> dict[str, list[float]]:
    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=10) as client:
        response = await client.get(
            f"/coins/{coingecko_id}/market_chart",
            params={"vs_currency": "usd", "days": 365, "interval": "daily"},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "prices": [point[1] for point in data.get("prices", [])],
            "volumes": [point[1] for point in data.get("total_volumes", [])],
        }


async def fetch_ohlc_data(symbol: str, coingecko_id: str | None = None, days: int = 90, interval: str = "4h") -> list[dict[str, float | int]]:
    normalized_symbol = symbol.upper()
    capped_days = max(30, min(days, 180))
    normalized_interval = normalize_kline_interval(interval)
    cache_key = f"{normalized_symbol}:{capped_days}:{normalized_interval}"
    cached = OHLC_CACHE.get(cache_key)
    if cached and time() - cached[0] < OHLC_CACHE_TTL_SECONDS:
        return cached[1]

    resolved_coingecko_id = coingecko_id or SYMBOL_TO_ID.get(normalized_symbol)
    if is_binance_futures_asset(resolved_coingecko_id):
        futures_candles = await fetch_binance_futures_ohlc(normalized_symbol, capped_days, normalized_interval)
        if futures_candles:
            OHLC_CACHE[cache_key] = (time(), futures_candles)
            return futures_candles
        return cached[1] if cached else []
    if not resolved_coingecko_id:
        return []

    if normalized_interval in {"15m", "1h"}:
        market_chart_candles = await fetch_market_chart_ohlc(resolved_coingecko_id, capped_days, normalized_interval)
        if market_chart_candles:
            OHLC_CACHE[cache_key] = (time(), market_chart_candles)
            return market_chart_candles

        binance_candles = await fetch_binance_ohlc(normalized_symbol, capped_days, normalized_interval)
        if binance_candles:
            OHLC_CACHE[cache_key] = (time(), binance_candles)
            return binance_candles
    else:
        binance_candles = await fetch_binance_ohlc(normalized_symbol, capped_days, normalized_interval)
        if binance_candles:
            OHLC_CACHE[cache_key] = (time(), binance_candles)
            return binance_candles

        market_chart_candles = await fetch_market_chart_ohlc(resolved_coingecko_id, capped_days, normalized_interval)
        if market_chart_candles:
            OHLC_CACHE[cache_key] = (time(), market_chart_candles)
            return market_chart_candles

    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=10) as client:
        response = await client.get(f"/coins/{resolved_coingecko_id}/ohlc", params={"vs_currency": "usd", "days": capped_days}, headers=headers)
        if response.status_code >= 400:
            return cached[1] if cached else []
        rows = response.json()
        candles = [
            {
                "time": int(row[0] / 1000),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
            }
            for row in rows
        ]
        OHLC_CACHE[cache_key] = (time(), candles)
        return candles


async def fetch_market_chart_4h_ohlc(coingecko_id: str, days: int = 90) -> list[dict[str, float | int]]:
    return await fetch_market_chart_ohlc(coingecko_id, days, "4h")


async def fetch_coingecko_ohlc_endpoint(coingecko_id: str, days: int = 90) -> list[dict[str, float | int]]:
    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key
    supported_days = 90 if days <= 90 else 180
    cutoff = int((datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds()) - days * 86400

    try:
        async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=8) as client:
            response = await client.get(
                f"/coins/{coingecko_id}/ohlc",
                params={"vs_currency": "usd", "days": supported_days},
                headers=headers,
            )
            if response.status_code >= 400:
                return []
            rows = response.json()
    except httpx.HTTPError:
        return []

    candles = [
        {
            "time": int(row[0] / 1000),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        }
        for row in rows
        if int(row[0] / 1000) >= cutoff
    ]
    return candles


async def fetch_market_chart_ohlc(coingecko_id: str, days: int = 90, interval: str = "4h") -> list[dict[str, float | int]]:
    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    try:
        async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=10) as client:
            response = await client.get(
                f"/coins/{coingecko_id}/market_chart",
                params={"vs_currency": "usd", "days": days},
                headers=headers,
            )
            if response.status_code >= 400:
                return []
            prices = response.json().get("prices", [])
    except httpx.HTTPError:
        return []

    buckets: dict[int, list[float]] = {}
    bucket_seconds = {"15m": 900, "1h": 3600, "4h": 14400}.get(interval, 14400)
    for timestamp_ms, price in prices:
        bucket = int(timestamp_ms / 1000) // bucket_seconds * bucket_seconds
        buckets.setdefault(bucket, []).append(float(price))

    candles = []
    for bucket, values in sorted(buckets.items()):
        if not values:
            continue
        candles.append(
            {
                "time": bucket,
                "open": values[0],
                "high": max(values),
                "low": min(values),
                "close": values[-1],
            }
        )
    return candles


async def fetch_binance_4h_ohlc(symbol: str, days: int = 90) -> list[dict[str, float | int]]:
    return await fetch_binance_ohlc(symbol, days, "4h")


async def fetch_binance_futures_ohlc(symbol: str, days: int = 90, interval: str = "4h") -> list[dict[str, float | int]]:
    pair = normalize_futures_pair(symbol)
    for base_url in get_settings().futures_base_url_list:
        candles = await fetch_binance_klines(
            pair,
            days=days,
            interval=interval,
            base_url=base_url,
            path="/fapi/v1/klines",
            source_limit=1500,
        )
        if candles:
            return candles
    return []


async def fetch_binance_ohlc(symbol: str, days: int = 90, interval: str = "4h") -> list[dict[str, float | int]]:
    normalized_symbol = symbol.upper()
    pairs = []
    configured_pair = SYMBOL_TO_BINANCE_PAIR.get(normalized_symbol)
    if configured_pair:
        pairs.append(configured_pair)
    if normalized_symbol.endswith(("USDT", "USDC")):
        pairs.append(normalized_symbol)
    elif not normalized_symbol.startswith("USD"):
        pairs.append(f"{normalized_symbol}USDT")
    pairs.append(f"{normalized_symbol}USDC")

    for pair in dict.fromkeys(pairs):
        rows = await fetch_binance_klines(
            pair,
            days=days,
            interval=interval,
            base_url="https://api.binance.com",
            path="/api/v3/klines",
            source_limit=1500,
        )
        if rows:
            return rows
    return []


async def fetch_binance_klines(
    pair: str,
    days: int = 90,
    interval: str = "4h",
    base_url: str = "https://api.binance.com",
    path: str = "/api/v3/klines",
    source_limit: int = 1500,
) -> list[dict[str, float | int]]:
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
            candles_per_day = interval_candles_per_day(interval)
            target_limit = min(source_limit, max(100, days * candles_per_day + 12))
            rows = []
            end_time = int(time() * 1000)
            while len(rows) < target_limit:
                limit = min(1000, target_limit - len(rows))
                response = await client.get(
                    path,
                    params={"symbol": pair, "interval": interval, "limit": limit, "endTime": end_time},
                )
                if response.status_code >= 400:
                    return []
                batch = response.json()
                if not batch:
                    break
                rows = batch + rows
                first_open_time = int(batch[0][0])
                if len(batch) < limit:
                    break
                end_time = first_open_time - 1
            return binance_rows_to_candles(rows)
    except httpx.HTTPError:
        return []


async def fetch_binance_recent_klines(pair: str, interval: str = "15m", limit: int = 8) -> list[dict[str, float | int]]:
    try:
        async with httpx.AsyncClient(base_url="https://api.binance.com", timeout=8) as client:
            response = await client.get(
                "/api/v3/klines",
                params={"symbol": pair, "interval": interval, "limit": max(2, min(limit, 100))},
            )
            if response.status_code >= 400:
                return []
            rows = response.json()
    except httpx.HTTPError:
        return []

    now_ms = int(time() * 1000)
    candles = []
    for row in rows:
        close_time = int(row[6])
        if close_time > now_ms:
            continue
        candles.append(
            {
                "time": int(int(row[0]) / 1000),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        )
    return candles


async def fetch_binance_futures_recent_klines(pair: str, interval: str = "15m", limit: int = 8) -> list[dict[str, float | int]]:
    rows = []
    for base_url in get_settings().futures_base_url_list:
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=8) as client:
                response = await client.get(
                    "/fapi/v1/klines",
                    params={"symbol": normalize_futures_pair(pair), "interval": interval, "limit": max(2, min(limit, 100))},
                )
                if response.status_code >= 400:
                    continue
                rows = response.json()
                break
        except httpx.HTTPError:
            continue
    if not rows:
        return []
    return [
        candle
        for candle in binance_rows_to_candles(rows)
        if int(candle["time"]) <= int(time())
    ]


def binance_rows_to_candles(rows: list) -> list[dict[str, float | int]]:
    return [
        {
            "time": int(int(row[0]) / 1000),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in rows
    ]


async def refresh_assets(db: Session) -> list[AssetSnapshot]:
    rows = await fetch_market_data()
    return await upsert_market_rows(db, rows, include_summary=True, include_core_technicals=True)


async def refresh_candidate_assets(db: Session) -> list[AssetSnapshot]:
    candidates = select_candidate_assets(db)
    if not candidates:
        return []
    rows = await fetch_market_data([asset.coingecko_id for asset in candidates])
    return await upsert_market_rows(db, rows, include_summary=False, include_core_technicals=False)


async def refresh_open_trade_assets(db: Session) -> list[AssetSnapshot]:
    symbols = list(db.scalars(select(PaperTrade.symbol).where(PaperTrade.status == "open")))
    if not symbols:
        return []
    assets = list(db.scalars(select(AssetSnapshot).where(AssetSnapshot.symbol.in_(symbols))))
    if not assets:
        return []
    rows = await fetch_market_data([asset.coingecko_id for asset in assets])
    return await upsert_market_rows(db, rows, include_summary=False, include_core_technicals=False)


async def refresh_technical_indicators(db: Session) -> list[AssetSnapshot]:
    settings = get_settings()
    assets = list(
        db.scalars(
            select(AssetSnapshot)
            .where(
                (AssetSnapshot.symbol.in_(settings.core_technical_symbol_list))
                | (AssetSnapshot.opportunity_score >= settings.candidate_min_opportunity_score)
            )
            .order_by(AssetSnapshot.opportunity_score.desc(), AssetSnapshot.market_cap.desc())
            .limit(settings.technical_refresh_limit)
        )
    )
    refreshed: list[AssetSnapshot] = []
    for asset in assets:
        candles = await fetch_ohlc_data(asset.symbol, asset.coingecko_id)
        if not candles:
            continue
        technicals = calculate_technicals(
            prices=[float(candle["close"]) for candle in candles],
            volumes=[float(candle.get("volume") or 0) for candle in candles],
            current_price=asset.current_price,
        )
        technicals["technical_note"] = f"后台每 {settings.technical_refresh_interval_minutes} 分钟重算；当前基于 {len(candles)} 根 4 小时 K 线。"
        for key, value in technicals.items():
            setattr(asset, key, value)
        refreshed.append(asset)
    db.commit()
    return refreshed


async def refresh_latest_klines(db: Session, limit: int = 100, intervals: list[str] | None = None) -> dict:
    capped_limit = max(1, min(limit, get_settings().tracked_asset_count))
    normalized_intervals = [normalize_kline_interval(item) for item in (intervals or ["15m", "1h", "4h"])]
    normalized_intervals = list(dict.fromkeys(normalized_intervals))
    assets = list(
        db.scalars(
            select(AssetSnapshot)
            .where(universe_asset_where_clause())
            .order_by(AssetSnapshot.market_cap.desc())
            .limit(capped_limit)
        )
    )
    imported: list[dict[str, int | str]] = []
    skipped: list[str] = []
    total_candles = 0

    for asset in assets:
        pair = build_binance_pair(asset.symbol)
        if not pair:
            skipped.append(asset.symbol)
            continue
        for normalized_interval in normalized_intervals:
            latest_time = get_latest_ohlc_time(db, asset.symbol, normalized_interval)
            is_futures = is_binance_futures_asset(asset.coingecko_id)
            candles = (
                await fetch_binance_futures_recent_klines(pair, interval=normalized_interval, limit=8)
                if is_futures
                else await fetch_binance_recent_klines(pair, interval=normalized_interval, limit=8)
            )
            if not candles:
                today = datetime.now(timezone.utc).date()
                candles = await fetch_binance_data_vision_klines(
                    pair,
                    normalized_interval,
                    today - timedelta(days=1),
                    today,
                    market="futures_um" if is_futures else "spot",
                )
            if latest_time is not None:
                candles = [candle for candle in candles if int(candle["time"]) > latest_time]
            if not candles:
                skipped.append(f"{asset.symbol}:{normalized_interval}")
                continue
            saved = save_ohlc_to_db(db, asset.symbol, asset.coingecko_id, normalized_interval, candles, source="binance-futures" if is_futures else "binance-api")
            imported.append({"symbol": asset.symbol, "pair": pair, "interval": normalized_interval, "candles": saved})
            total_candles += saved

    return {
        "intervals": normalized_intervals,
        "imported": imported,
        "skipped": skipped,
        "imported_assets": len(imported),
        "skipped_assets": len(skipped),
        "candles": total_candles,
    }


async def refresh_ohlc_cache(db: Session, days: int = 60, interval: str = "1h", limit: int = 100) -> list[str]:
    normalized_interval = normalize_kline_interval(interval)
    capped_days = max(7, min(days, 180))
    capped_limit = max(1, min(limit, get_settings().tracked_asset_count))
    assets = list(
        db.scalars(
            select(AssetSnapshot)
            .where(universe_asset_where_clause())
            .order_by(AssetSnapshot.market_cap.desc())
            .limit(capped_limit)
        )
    )
    refreshed: list[str] = []
    for asset in assets:
        cached = load_ohlc_from_db(db, asset.symbol, normalized_interval, capped_days)
        if has_enough_ohlc(cached, capped_days, normalized_interval):
            refreshed.append(asset.symbol)
            continue
        candles = await fetch_ohlc_data(asset.symbol, asset.coingecko_id, days=capped_days, interval=normalized_interval)
        if candles:
            save_ohlc_to_db(db, asset.symbol, asset.coingecko_id, normalized_interval, candles, source="external")
            refreshed.append(asset.symbol)
    return refreshed


async def import_binance_data_vision_klines(
    db: Session,
    days: int = 60,
    interval: str = "1h",
    limit: int = 100,
    intervals: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    normalized_intervals = [normalize_kline_interval(item) for item in (intervals or [interval])]
    normalized_intervals = list(dict.fromkeys(normalized_intervals))
    today = datetime.now(timezone.utc).date()
    range_end = min(end_date or today, today)
    range_start = start_date or (range_end - timedelta(days=max(1, min(days, 365))))
    if range_start > range_end:
        range_start, range_end = range_end, range_start
    capped_days = max(1, (range_end - range_start).days + 1)
    capped_limit = max(1, min(limit, get_settings().tracked_asset_count))
    assets = list(
        db.scalars(
            select(AssetSnapshot)
            .where(universe_asset_where_clause())
            .order_by(AssetSnapshot.market_cap.desc())
            .limit(capped_limit)
        )
    )
    imported: list[dict[str, int | str]] = []
    cached_assets: list[dict[str, int | str]] = []
    skipped: list[str] = []
    total_candles = 0

    for asset in assets:
        pair = build_binance_pair(asset.symbol)
        if not pair:
            skipped.append(asset.symbol)
            continue
        for normalized_interval in normalized_intervals:
            cached = load_ohlc_from_db_range(db, asset.symbol, normalized_interval, range_start, range_end)
            if has_enough_ohlc_range(cached, range_start, range_end, normalized_interval):
                cached_assets.append({"symbol": asset.symbol, "pair": pair, "interval": normalized_interval, "candles": len(cached)})
                continue
            is_futures = is_binance_futures_asset(asset.coingecko_id)
            candles = await fetch_binance_data_vision_klines(
                pair,
                normalized_interval,
                range_start,
                range_end,
                market="futures_um" if is_futures else "spot",
            )
            if not candles:
                skipped.append(f"{asset.symbol}:{normalized_interval}")
                continue
            saved = save_ohlc_to_db(db, asset.symbol, asset.coingecko_id, normalized_interval, candles, source="binance-futures-data-vision" if is_futures else "binance-data-vision")
            imported.append({"symbol": asset.symbol, "pair": pair, "interval": normalized_interval, "candles": saved})
            total_candles += saved

    return {
        "intervals": normalized_intervals,
        "days": capped_days,
        "start_date": range_start.isoformat(),
        "end_date": range_end.isoformat(),
        "imported": imported,
        "cached": cached_assets,
        "skipped": skipped,
        "imported_assets": len(imported),
        "cached_assets": len(cached_assets),
        "skipped_assets": len(skipped),
        "candles": total_candles,
    }


def build_binance_pair(symbol: str) -> str | None:
    normalized_symbol = symbol.upper()
    if normalized_symbol.startswith("USD"):
        return None
    if normalized_symbol.endswith(("USDT", "USDC")):
        return normalized_symbol
    return SYMBOL_TO_BINANCE_PAIR.get(normalized_symbol) or f"{normalized_symbol}USDT"


async def fetch_binance_data_vision_klines(pair: str, interval: str, start_date: date, end_date: date, market: str = "spot") -> list[dict[str, float | int]]:
    candles: list[dict[str, float | int]] = []
    data_root = "/data/futures/um" if market == "futures_um" else "/data/spot"

    async with httpx.AsyncClient(base_url=BINANCE_DATA_BASE_URL, timeout=30) as client:
        for year, month in month_range(start_date, end_date):
            if year == end_date.year and month == end_date.month:
                continue
            filename = f"{pair}-{interval}-{year:04d}-{month:02d}.zip"
            path = f"{data_root}/monthly/klines/{pair}/{interval}/{filename}"
            candles.extend(await fetch_binance_data_vision_zip(client, path, start_date))

        daily_start = max(start_date, date(end_date.year, end_date.month, 1))
        for current_date in date_range(daily_start, end_date):
            filename = f"{pair}-{interval}-{current_date.isoformat()}.zip"
            path = f"{data_root}/daily/klines/{pair}/{interval}/{filename}"
            candles.extend(await fetch_binance_data_vision_zip(client, path, start_date))

    unique: dict[int, dict[str, float | int]] = {}
    for candle in candles:
        unique[int(candle["time"])] = candle
    return [unique[key] for key in sorted(unique)]


async def fetch_binance_data_vision_zip(client: httpx.AsyncClient, path: str, start_date: date) -> list[dict[str, float | int]]:
    try:
        response = await client.get(path)
    except httpx.HTTPError:
        return []
    if response.status_code >= 400:
        return []

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            csv_name = archive.namelist()[0]
            with archive.open(csv_name) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8")
                return parse_binance_kline_csv(text, start_date)
    except (zipfile.BadZipFile, IndexError, ValueError):
        return []


def parse_binance_kline_csv(text, start_date: date) -> list[dict[str, float | int]]:
    cutoff = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    candles: list[dict[str, float | int]] = []
    for row in csv.reader(text):
        if len(row) < 6 or row[0] == "open_time":
            continue
        try:
            open_time = normalize_binance_timestamp(int(row[0]))
            if open_time < cutoff:
                continue
            candles.append(
                {
                    "time": open_time,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )
        except ValueError:
            continue
    return candles


def normalize_binance_timestamp(raw_timestamp: int) -> int:
    if raw_timestamp > 10_000_000_000_000:
        return int(raw_timestamp / 1_000_000)
    if raw_timestamp > 10_000_000_000:
        return int(raw_timestamp / 1000)
    return raw_timestamp


def month_range(start_date: date, end_date: date):
    year = start_date.year
    month = start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        yield year, month
        month += 1
        if month > 12:
            year += 1
            month = 1


def date_range(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def select_candidate_assets(db: Session) -> list[AssetSnapshot]:
    settings = get_settings()
    open_symbols = set(db.scalars(select(PaperTrade.symbol).where(PaperTrade.status == "open")))
    universe_clause = universe_asset_where_clause()
    opportunity_clause = (
        (AssetSnapshot.opportunity_score >= settings.candidate_min_opportunity_score)
        | (AssetSnapshot.opportunity_status.in_(["高优先级", "可关注"]))
    )
    candidates = list(
        db.scalars(
            select(AssetSnapshot)
            .where(
                (universe_clause & opportunity_clause)
                | (AssetSnapshot.symbol.in_(open_symbols or ["__none__"]))
            )
            .order_by(AssetSnapshot.opportunity_score.desc(), AssetSnapshot.market_cap.desc())
            .limit(50)
        )
    )
    return candidates


async def upsert_market_rows(
    db: Session,
    rows: list[dict],
    include_summary: bool,
    include_core_technicals: bool,
) -> list[AssetSnapshot]:
    settings = get_settings()
    refreshed: list[AssetSnapshot] = []

    for row in rows:
        change_24h = float(row.get("price_change_percentage_24h") or 0)
        market_cap = float(row.get("market_cap") or 0)
        volume_24h = float(row.get("total_volume") or 0)
        current_price = float(row.get("current_price") or 0)
        symbol = row["symbol"].upper()
        if include_core_technicals and symbol in settings.core_technical_symbol_list:
            historical = await fetch_historical_data(row["id"])
            technicals = calculate_technicals(
                prices=historical["prices"],
                volumes=historical["volumes"],
                current_price=current_price,
            )
        else:
            technicals = empty_technicals("市场扫描标的先使用价格、量能和评分发现机会；打开详情页可查看 4 小时 K 线。")
        scores = calculate_scores(change_24h, market_cap, volume_24h)
        asset = db.scalar(select(AssetSnapshot).where(AssetSnapshot.coingecko_id == row["id"]))
        if asset is None:
            asset = AssetSnapshot(coingecko_id=row["id"], symbol=symbol, name=row["name"])
            db.add(asset)

        asset.symbol = symbol
        asset.name = row["name"]
        asset.image_url = row.get("image")
        asset.current_price = current_price
        asset.market_cap = market_cap
        asset.volume_24h = volume_24h
        asset.change_24h = change_24h
        if include_summary or not asset.ai_summary:
            asset.ai_summary = await generate_summary(
                name=row["name"],
                symbol=row["symbol"],
                price=current_price,
                change_24h=change_24h,
                market_cap=market_cap,
                volume_24h=volume_24h,
                liquidity_score=scores["liquidity_score"],
                risk_score=scores["risk_score"],
            )
        asset.source_updated_at = parse_datetime(row.get("last_updated"))
        asset.refreshed_at = datetime.utcnow()
        for key, value in scores.items():
            setattr(asset, key, value)
        for key, value in technicals.items():
            setattr(asset, key, value)
        await refresh_asset_latest_klines(db, asset, intervals=["15m", "1h", "4h"])
        await ensure_volume_ohlc_from_data_vision(db, asset.symbol, asset.coingecko_id, interval="4h", days=90)
        trade_plan = build_live_indicator_trade_plan(db, asset) or build_live_empty_plan("15m K线不足，首页不再使用24h初筛生成开仓机会。", current_price)
        for key, value in trade_plan.items():
            setattr(asset, key, value)

        refreshed.append(asset)

    db.commit()
    return refreshed


async def refresh_asset_latest_klines(db: Session, asset: AssetSnapshot, intervals: list[str]) -> int:
    pair = build_binance_pair(asset.symbol)
    if not pair:
        return 0
    is_futures = is_binance_futures_asset(asset.coingecko_id)
    saved_total = 0
    today = datetime.now(timezone.utc).date()
    for interval in intervals:
        normalized_interval = normalize_kline_interval(interval)
        latest_time = get_latest_ohlc_time(db, asset.symbol, normalized_interval)
        candles = (
            await fetch_binance_futures_recent_klines(pair, interval=normalized_interval, limit=8)
            if is_futures
            else await fetch_binance_recent_klines(pair, interval=normalized_interval, limit=8)
        )
        if not candles:
            candles = await fetch_binance_data_vision_klines(
                pair,
                normalized_interval,
                today - timedelta(days=1),
                today,
                market="futures_um" if is_futures else "spot",
            )
        if latest_time is not None:
            candles = [candle for candle in candles if int(candle["time"]) > latest_time]
        if not candles:
            continue
        saved_total += save_ohlc_to_db(db, asset.symbol, asset.coingecko_id, normalized_interval, candles, source="binance-futures" if is_futures else "binance-api")
    return saved_total


def build_live_indicator_trade_plan(db: Session, asset: AssetSnapshot) -> dict[str, float | str | None] | None:
    try:
        from app.backtesting import build_daily_market_context, build_indicator_trade_plan, resample_candles
    except ImportError:
        return None

    execution_rows = load_ohlc_from_db(db, asset.symbol, "15m", 180)
    if len(execution_rows) < 80:
        return None

    one_hour_rows = load_ohlc_from_db(db, asset.symbol, "1h", 180)
    if not has_enough_ohlc(one_hour_rows, 30, "1h"):
        one_hour_rows = resample_candles(execution_rows, 3600)
    four_hour_rows = load_ohlc_from_db(db, asset.symbol, "4h", 180)
    if not has_enough_ohlc(four_hour_rows, 30, "4h"):
        four_hour_rows = resample_candles(one_hour_rows or execution_rows, 14400)
    daily_rows = resample_candles(four_hour_rows, 86400)
    if len(daily_rows) < 60:
        return None

    latest_row = execution_rows[-1]
    timestamp = int(latest_row["time"])
    price = float(asset.current_price or latest_row["close"] or 0)
    if price <= 0:
        return None

    market_context = build_daily_market_context(daily_rows, timestamp, price)
    apply_live_indicator_context(asset, market_context, price, one_hour_rows, four_hour_rows, timestamp)
    if market_context.get("regime") == "数据不足":
        return build_live_empty_plan("v6.2 确认指标策略数据不足，暂不进入模拟开仓。", price)

    plan = build_indicator_trade_plan(
        asset,
        execution_rows,
        len(execution_rows) - 1,
        price,
        timestamp,
        {"1h": one_hour_rows, "4h": four_hour_rows},
        market_context,
    )
    if not plan:
        return build_live_empty_plan("v6.2 确认指标策略未满足1H/4H同向、日线结构、15m确认、真实放量、波动、质量分或盈亏比过滤，当前观望。", price)

    signal = str(plan["trade_signal"])
    score = int(plan["opportunity_score"])
    entry_reasons = plan.get("entry_reasons") or []
    strategy_type = str(plan.get("strategy_type") or "指标策略")
    reason_text = "；".join(str(item) for item in entry_reasons) if entry_reasons else str(plan.get("opening_logic") or "")
    return {
        "trade_signal": signal,
        "entry_price": plan["entry_price"],
        "stop_loss": plan["stop_loss"],
        "take_profit": plan["take_profit"],
        "risk_reward_ratio": plan["risk_reward_ratio"],
        "trade_rationale": str(plan.get("opening_logic") or reason_text),
        "opportunity_score": score,
        "opportunity_status": opportunity_status(score, signal),
        "opportunity_type": signal,
        "trigger_price": plan["entry_price"],
        "invalid_price": plan["stop_loss"],
        "opportunity_reason": f"v6.2确认指标策略：{strategy_type}。{reason_text}",
    }


def apply_live_indicator_context(
    asset: AssetSnapshot,
    market_context: dict,
    price: float,
    one_hour_rows: list[dict[str, float | int]],
    four_hour_rows: list[dict[str, float | int]],
    timestamp: int,
) -> None:
    from app.backtesting import indicator_trend_direction

    asset.ma_50 = market_context.get("ema50")
    asset.ma_100 = market_context.get("ema100")
    asset.ma_200 = market_context.get("ema200")
    asset.vegas_fast = market_context.get("ema144")
    asset.vegas_slow = market_context.get("ema169")
    asset.dt_upper = market_context.get("dt_upper")
    asset.dt_lower = market_context.get("dt_lower")
    asset.support_level = market_context.get("support")
    asset.resistance_level = market_context.get("resistance")
    asset.market_cycle = str(market_context.get("regime") or "数据不足")
    asset.trend_line = f"1H {indicator_trend_direction(one_hour_rows, timestamp)} / 4H {indicator_trend_direction(four_hour_rows, timestamp)}"
    asset.vegas_signal = live_channel_signal(price, market_context.get("ema144"), market_context.get("ema169"), "Vegas")
    asset.dt_signal = live_dt_signal(price, market_context.get("dt_upper"), market_context.get("dt_lower"))
    asset.volume_price_relation = live_candle_volume_relation(four_hour_rows)
    asset.technical_note = "首页和模拟开仓已切换为 v6.2 确认指标策略：15m 执行，1H/4H 必须同向，日线结构和15m确认K线同时满足，最低计划盈亏比 1.3:1。"


def build_live_empty_plan(rationale: str, price: float) -> dict[str, float | str | None]:
    return {
        "trade_signal": "观望",
        "entry_price": round_price(price),
        "stop_loss": None,
        "take_profit": None,
        "risk_reward_ratio": None,
        "trade_rationale": rationale,
        "opportunity_score": 0,
        "opportunity_status": "观察",
        "opportunity_type": "观望",
        "trigger_price": None,
        "invalid_price": None,
        "opportunity_reason": rationale,
    }


def live_channel_signal(price: float, fast: float | None, slow: float | None, label: str) -> str:
    if not fast or not slow:
        return f"{label}数据不足"
    upper = max(float(fast), float(slow))
    lower = min(float(fast), float(slow))
    if price > upper:
        return f"价格在{label}上方，偏多"
    if price < lower:
        return f"价格在{label}下方，偏空"
    return f"价格在{label}通道内"


def live_dt_signal(price: float, upper: float | None, lower: float | None) -> str:
    if not upper or not lower:
        return "DT数据不足"
    if price >= float(upper):
        return "接近或突破DT上轨"
    if price <= float(lower):
        return "接近或跌破DT下轨"
    return "DT通道内部"


def live_candle_volume_relation(rows: list[dict[str, float | int]]) -> str:
    paired_rows = [
        (float(row["close"]), float(row.get("volume") or 0))
        for row in rows
        if float(row.get("close") or 0) > 0 and float(row.get("volume") or 0) > 0
    ]
    closes = [close for close, _volume in paired_rows]
    volumes = [volume for _close, volume in paired_rows]
    return volume_price_relation(closes, volumes)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
