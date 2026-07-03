from datetime import datetime
from time import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import generate_summary
from app.config import get_settings
from app.models import AssetSnapshot, PaperTrade
from app.scoring import calculate_scores
from app.technicals import calculate_technicals, empty_technicals
from app.trade_logic import build_trade_plan

SYMBOL_TO_ID = {"BTC": "bitcoin", "ETH": "ethereum"}
SYMBOL_TO_BINANCE_PAIR = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}
OHLC_CACHE_TTL_SECONDS = 900
OHLC_CACHE: dict[str, tuple[float, list[dict[str, float | int]]]] = {}


async def fetch_market_data(coingecko_ids: list[str] | None = None) -> list[dict]:
    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": settings.tracked_asset_count,
        "page": 1,
        "sparkline": "false",
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


async def fetch_historical_data(coingecko_id: str) -> dict[str, list[float]]:
    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=30) as client:
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


async def fetch_ohlc_data(symbol: str, coingecko_id: str | None = None) -> list[dict[str, float | int]]:
    normalized_symbol = symbol.upper()
    cached = OHLC_CACHE.get(normalized_symbol)
    if cached and time() - cached[0] < OHLC_CACHE_TTL_SECONDS:
        return cached[1]

    resolved_coingecko_id = coingecko_id or SYMBOL_TO_ID.get(normalized_symbol)
    if not resolved_coingecko_id:
        return []

    binance_candles = await fetch_binance_4h_ohlc(normalized_symbol)
    if binance_candles:
        OHLC_CACHE[normalized_symbol] = (time(), binance_candles)
        return binance_candles

    market_chart_candles = await fetch_market_chart_4h_ohlc(resolved_coingecko_id)
    if market_chart_candles:
        OHLC_CACHE[normalized_symbol] = (time(), market_chart_candles)
        return market_chart_candles

    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=30) as client:
        response = await client.get(f"/coins/{resolved_coingecko_id}/ohlc", params={"vs_currency": "usd", "days": 30}, headers=headers)
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
        OHLC_CACHE[normalized_symbol] = (time(), candles)
        return candles


async def fetch_market_chart_4h_ohlc(coingecko_id: str) -> list[dict[str, float | int]]:
    settings = get_settings()
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    try:
        async with httpx.AsyncClient(base_url=settings.coingecko_base_url, timeout=30) as client:
            response = await client.get(
                f"/coins/{coingecko_id}/market_chart",
                params={"vs_currency": "usd", "days": 90},
                headers=headers,
            )
            if response.status_code >= 400:
                return []
            prices = response.json().get("prices", [])
    except httpx.HTTPError:
        return []

    buckets: dict[int, list[float]] = {}
    for timestamp_ms, price in prices:
        bucket = int(timestamp_ms / 1000) // 14400 * 14400
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


async def fetch_binance_4h_ohlc(symbol: str) -> list[dict[str, float | int]]:
    pair = SYMBOL_TO_BINANCE_PAIR.get(symbol.upper())
    if not pair:
        return []

    try:
        async with httpx.AsyncClient(base_url="https://api.binance.com", timeout=20) as client:
            response = await client.get("/api/v3/klines", params={"symbol": pair, "interval": "4h", "limit": 500})
            if response.status_code >= 400:
                return []
            rows = response.json()
            return [
                {
                    "time": int(row[0] / 1000),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                }
                for row in rows
            ]
    except httpx.HTTPError:
        return []


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
            volumes=[],
            current_price=asset.current_price,
        )
        technicals["technical_note"] = f"后台每 {settings.technical_refresh_interval_minutes} 分钟重算；当前基于 {len(candles)} 根 4 小时 K 线。"
        for key, value in technicals.items():
            setattr(asset, key, value)
        refreshed.append(asset)
    db.commit()
    return refreshed


def select_candidate_assets(db: Session) -> list[AssetSnapshot]:
    settings = get_settings()
    open_symbols = set(db.scalars(select(PaperTrade.symbol).where(PaperTrade.status == "open")))
    candidates = list(
        db.scalars(
            select(AssetSnapshot)
            .where(
                (AssetSnapshot.opportunity_score >= settings.candidate_min_opportunity_score)
                | (AssetSnapshot.opportunity_status.in_(["高优先级", "可关注"]))
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
        trade_plan = build_trade_plan(
            current_price=current_price,
            change_24h=change_24h,
            ai_score=scores["ai_score"],
            trend_score=scores["trend_score"],
            liquidity_score=scores["liquidity_score"],
            risk_score=scores["risk_score"],
        )

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
        for key, value in trade_plan.items():
            setattr(asset, key, value)
        for key, value in technicals.items():
            setattr(asset, key, value)

        refreshed.append(asset)

    db.commit()
    return refreshed


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
