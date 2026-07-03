import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import AssetSnapshot, PaperTrade
from app.paper_trading import apply_paper_trading, build_equity_curve, build_paper_trading_summary, record_daily_snapshot
from app.schemas import AssetOut, EquityCurvePointOut, OhlcCandleOut, PaperTradeOut, PaperTradingSummaryOut, RefreshOut
from app.services import (
    fetch_ohlc_data,
    refresh_assets,
    refresh_candidate_assets,
    refresh_open_trade_assets,
    refresh_technical_indicators,
)
from app.technicals import calculate_technicals

settings = get_settings()
app = FastAPI(title="短线精灵 API", version="0.1.0")
auto_refresh_tasks: list[asyncio.Task] = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_trade_plan_columns()
    start_auto_refresh()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    for task in auto_refresh_tasks:
        task.cancel()
    for task in auto_refresh_tasks:
        with suppress(asyncio.CancelledError):
            await task


def start_auto_refresh() -> None:
    if not settings.auto_refresh_enabled:
        return
    if auto_refresh_tasks:
        return
    auto_refresh_tasks.extend(
        [
            asyncio.create_task(periodic_job("market-scan", settings.market_scan_interval_minutes, run_market_scan)),
            asyncio.create_task(periodic_job("candidate-scan", settings.candidate_scan_interval_minutes, run_candidate_scan)),
            asyncio.create_task(periodic_job("paper-positions", settings.paper_position_interval_minutes, run_paper_position_refresh)),
            asyncio.create_task(periodic_job("technical-refresh", settings.technical_refresh_interval_minutes, run_technical_refresh)),
            asyncio.create_task(daily_snapshot_loop()),
        ]
    )


async def periodic_job(name: str, interval_minutes: int, runner) -> None:
    interval_seconds = max(1, interval_minutes) * 60
    while True:
        await asyncio.sleep(interval_seconds)
        db = SessionLocal()
        try:
            count = await runner(db)
            print(f"{name} refreshed {count} items")
        except Exception as exc:
            print(f"{name} failed: {exc}")
            db.rollback()
        finally:
            db.close()


async def daily_snapshot_loop() -> None:
    while True:
        now = datetime.now(timezone.utc)
        next_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        await asyncio.sleep(max(1, int((next_midnight - now).total_seconds())))
        db = SessionLocal()
        try:
            snapshot = record_daily_snapshot(db, snapshot_date=next_midnight.date().isoformat())
            print(f"daily snapshot recorded: {snapshot.snapshot_date}")
        except Exception as exc:
            print(f"daily snapshot failed: {exc}")
            db.rollback()
        finally:
            db.close()


async def run_market_scan(db: Session) -> int:
    refreshed = await refresh_assets(db)
    apply_paper_trading(db, refreshed, open_new=True)
    return len(refreshed)


async def run_candidate_scan(db: Session) -> int:
    refreshed = await refresh_candidate_assets(db)
    apply_paper_trading(db, refreshed, open_new=True)
    return len(refreshed)


async def run_paper_position_refresh(db: Session) -> int:
    refreshed = await refresh_open_trade_assets(db)
    apply_paper_trading(db, refreshed, open_new=False)
    return len(refreshed)


async def run_technical_refresh(db: Session) -> int:
    refreshed = await refresh_technical_indicators(db)
    return len(refreshed)


def verify_refresh_token(x_refresh_token: str | None) -> None:
    if settings.refresh_token and x_refresh_token != settings.refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


def ensure_trade_plan_columns() -> None:
    statements = [
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS trade_signal VARCHAR(16) NOT NULL DEFAULT '观望'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS entry_price DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS stop_loss DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS take_profit DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS risk_reward_ratio DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS trade_rationale TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS opportunity_score INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS opportunity_status VARCHAR(24) NOT NULL DEFAULT '观察'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS opportunity_type VARCHAR(16) NOT NULL DEFAULT '观望'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS trigger_price DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS invalid_price DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS opportunity_reason TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS fib_236 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS fib_382 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS fib_500 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS fib_618 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS fib_786 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS dt_upper DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS dt_lower DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS dt_signal VARCHAR(32) NOT NULL DEFAULT '数据不足'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS vegas_fast DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS vegas_slow DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS vegas_signal VARCHAR(32) NOT NULL DEFAULT '数据不足'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS trend_line VARCHAR(32) NOT NULL DEFAULT '数据不足'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS support_level DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS resistance_level DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS market_cycle VARCHAR(32) NOT NULL DEFAULT '数据不足'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS volume_price_relation VARCHAR(32) NOT NULL DEFAULT '数据不足'",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS ma_50 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS ma_100 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS ma_200 DOUBLE PRECISION",
        "ALTER TABLE asset_snapshots ADD COLUMN IF NOT EXISTS technical_note TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE asset_snapshots ALTER COLUMN coingecko_id TYPE VARCHAR(64)",
        "ALTER TABLE asset_snapshots ALTER COLUMN symbol TYPE VARCHAR(16)",
        "ALTER TABLE asset_snapshots ALTER COLUMN name TYPE VARCHAR(96)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/scheduler/status")
def scheduler_status() -> dict:
    return {
        "enabled": settings.auto_refresh_enabled,
        "tasks": {
            "market_scan_minutes": settings.market_scan_interval_minutes,
            "candidate_scan_minutes": settings.candidate_scan_interval_minutes,
            "paper_position_minutes": settings.paper_position_interval_minutes,
            "technical_refresh_minutes": settings.technical_refresh_interval_minutes,
            "daily_snapshot": "00:00 UTC",
        },
        "candidate_min_opportunity_score": settings.candidate_min_opportunity_score,
        "paper_min_opportunity_score": settings.paper_min_opportunity_score,
        "technical_refresh_limit": settings.technical_refresh_limit,
    }


@app.get("/assets", response_model=list[AssetOut])
def list_assets(db: Session = Depends(get_db)) -> list[AssetSnapshot]:
    return list(db.scalars(select(AssetSnapshot).order_by(AssetSnapshot.opportunity_score.desc(), AssetSnapshot.market_cap.desc())))


@app.get("/opportunities", response_model=list[AssetOut])
def list_opportunities(limit: int = 20, db: Session = Depends(get_db)) -> list[AssetSnapshot]:
    capped_limit = max(1, min(limit, 100))
    return list(
        db.scalars(
            select(AssetSnapshot)
            .order_by(AssetSnapshot.opportunity_score.desc(), AssetSnapshot.market_cap.desc())
            .limit(capped_limit)
        )
    )


@app.get("/assets/{symbol}", response_model=AssetOut)
async def get_asset(symbol: str, db: Session = Depends(get_db)) -> AssetSnapshot:
    asset = db.scalar(select(AssetSnapshot).where(AssetSnapshot.symbol == symbol.upper()))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    candles = await fetch_ohlc_data(asset.symbol, asset.coingecko_id)
    if candles:
        technicals = calculate_technicals(
            prices=[float(candle["close"]) for candle in candles],
            volumes=[],
            current_price=asset.current_price,
        )
        technicals["technical_note"] = f"基于 {len(candles)} 根 4 小时 K 线动态计算；量价关系需要成交量序列，当前以价格技术指标为主。"
        for key, value in technicals.items():
            setattr(asset, key, value)
        db.commit()
        db.refresh(asset)
    return asset


@app.get("/assets/{symbol}/ohlc", response_model=list[OhlcCandleOut])
async def get_asset_ohlc(symbol: str, db: Session = Depends(get_db)) -> list[dict[str, float | int]]:
    asset = db.scalar(select(AssetSnapshot).where(AssetSnapshot.symbol == symbol.upper()))
    candles = await fetch_ohlc_data(symbol, asset.coingecko_id if asset else None)
    return candles


@app.post("/refresh", response_model=RefreshOut)
async def refresh(
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> RefreshOut:
    verify_refresh_token(x_refresh_token)
    refreshed = await refresh_assets(db)
    apply_paper_trading(db, refreshed, open_new=True)
    return RefreshOut(refreshed=[asset.symbol for asset in refreshed], count=len(refreshed))


@app.post("/scheduler/refresh", response_model=RefreshOut)
async def scheduler_refresh(
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> RefreshOut:
    return await refresh(db=db, x_refresh_token=x_refresh_token)


@app.post("/scheduler/market-scan", response_model=RefreshOut)
async def scheduler_market_scan(
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> RefreshOut:
    verify_refresh_token(x_refresh_token)
    refreshed = await refresh_assets(db)
    apply_paper_trading(db, refreshed, open_new=True)
    return RefreshOut(refreshed=[asset.symbol for asset in refreshed], count=len(refreshed))


@app.post("/scheduler/candidate-scan", response_model=RefreshOut)
async def scheduler_candidate_scan(
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> RefreshOut:
    verify_refresh_token(x_refresh_token)
    refreshed = await refresh_candidate_assets(db)
    apply_paper_trading(db, refreshed, open_new=True)
    return RefreshOut(refreshed=[asset.symbol for asset in refreshed], count=len(refreshed))


@app.post("/scheduler/paper-positions", response_model=RefreshOut)
async def scheduler_paper_positions(
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> RefreshOut:
    verify_refresh_token(x_refresh_token)
    refreshed = await refresh_open_trade_assets(db)
    apply_paper_trading(db, refreshed, open_new=False)
    return RefreshOut(refreshed=[asset.symbol for asset in refreshed], count=len(refreshed))


@app.post("/scheduler/technical-refresh", response_model=RefreshOut)
async def scheduler_technical_refresh(
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> RefreshOut:
    verify_refresh_token(x_refresh_token)
    refreshed = await refresh_technical_indicators(db)
    return RefreshOut(refreshed=[asset.symbol for asset in refreshed], count=len(refreshed))


@app.post("/scheduler/daily-snapshot")
def scheduler_daily_snapshot(
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> dict[str, str | float | int]:
    verify_refresh_token(x_refresh_token)
    snapshot = record_daily_snapshot(db)
    return {
        "date": snapshot.snapshot_date,
        "equity": snapshot.equity,
        "total_pnl": snapshot.total_pnl,
        "open_trades": snapshot.open_trades,
    }


@app.get("/paper-trading/summary", response_model=PaperTradingSummaryOut)
def paper_trading_summary(db: Session = Depends(get_db)) -> dict:
    return build_paper_trading_summary(db)


@app.get("/paper-trading/equity-curve", response_model=list[EquityCurvePointOut])
def paper_trading_equity_curve(days: int = 30, db: Session = Depends(get_db)) -> list[dict[str, float | str]]:
    return build_equity_curve(db, days=max(1, min(days, 365)))


@app.get("/paper-trading/trades", response_model=list[PaperTradeOut])
def paper_trading_trades(status_filter: str | None = None, db: Session = Depends(get_db)) -> list[PaperTrade]:
    statement = select(PaperTrade).order_by(PaperTrade.opened_at.desc())
    if status_filter:
        statement = select(PaperTrade).where(PaperTrade.status == status_filter).order_by(PaperTrade.opened_at.desc())
    return list(db.scalars(statement))


@app.post("/paper-trading/run", response_model=PaperTradingSummaryOut)
def paper_trading_run(db: Session = Depends(get_db)) -> dict:
    assets = list(db.scalars(select(AssetSnapshot).order_by(AssetSnapshot.opportunity_score.desc())))
    apply_paper_trading(db, assets)
    return build_paper_trading_summary(db)
