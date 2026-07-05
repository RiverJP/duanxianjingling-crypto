import asyncio
import json
import uuid
from contextlib import suppress
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.backtesting import derive_backtest_period_result, derive_backtest_period_summary, run_month_backtest
from app.config import get_settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import AssetSnapshot, BacktestRun, PaperDailySnapshot, PaperTrade
from app.paper_trading import apply_paper_trading, build_equity_curve, build_paper_trading_summary, record_daily_snapshot
from app.schemas import AssetOut, BacktestComparisonOut, BacktestResultOut, BacktestRunOut, BacktestTradesPageOut, EquityCurvePointOut, OhlcCandleOut, PaperTradeOut, PaperTradingSummaryOut, RefreshOut
from app.services import (
    fetch_binance_4h_ohlc,
    fetch_ohlc_data,
    import_binance_data_vision_klines,
    ensure_volume_ohlc_from_data_vision,
    refresh_assets,
    refresh_candidate_assets,
    refresh_latest_klines,
    refresh_open_trade_assets,
    refresh_ohlc_cache,
    refresh_technical_indicators,
    universe_asset_where_clause,
)
from app.technicals import calculate_technicals

settings = get_settings()
app = FastAPI(title="短线精灵 API", version="0.1.0")
auto_refresh_tasks: list[asyncio.Task] = []
backtest_jobs: dict[str, dict] = {}
backtest_job_tasks: dict[str, asyncio.Task] = {}

BACKTEST_VERSION_ALIASES = {
    "v1": "indicator-v1.1",
    "v2": "2026-07-04v2",
    "v3": "2026-07-04v3",
    "v4": "2026-07-04v4-strict",
    "v5": "2026-07-04v5-selective",
    "v6": "2026-07-04v6-confirmed",
}

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
    ensure_ohlc_candle_columns()
    start_auto_refresh()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    for task in auto_refresh_tasks:
        task.cancel()
    for task in backtest_job_tasks.values():
        task.cancel()
    for task in auto_refresh_tasks:
        with suppress(asyncio.CancelledError):
            await task
    for task in backtest_job_tasks.values():
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
            asyncio.create_task(periodic_job("latest-klines", settings.kline_refresh_interval_minutes, run_latest_klines)),
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


async def run_latest_klines(db: Session) -> int:
    result = await refresh_latest_klines(db)
    return int(result["imported_assets"])


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_backtest_job(job_id: str, days: int, limit: int, interval: str, mode: str) -> None:
    job = backtest_jobs[job_id]
    job.update({"status": "running", "started_at": now_iso(), "updated_at": now_iso()})
    db = SessionLocal()
    try:
        def update_progress(update: dict) -> None:
            job.update(update)
            total = int(job.get("total_assets") or 0)
            completed = int(job.get("completed_assets") or 0)
            job["progress_percent"] = round(completed / total * 100, 2) if total else 0
            job["updated_at"] = now_iso()
            if "current_asset" in update:
                print(
                    f"backtest job {job_id}: {completed}/{total} "
                    f"current={update.get('current_asset')} trades={job.get('total_trades', 0)}"
                )

        result = await run_month_backtest(
            db,
            days=days,
            limit=limit,
            interval=interval,
            mode=mode,
            progress_callback=update_progress,
        )
        summary = result["summary"]
        job.update(
            {
                "status": "completed",
                "completed_at": now_iso(),
                "updated_at": now_iso(),
                "progress_percent": 100,
                "run_key": summary.get("run_key"),
                "summary": summary,
                "error": None,
            }
        )
        print(f"backtest job {job_id} completed run_key={summary.get('run_key')}")
    except asyncio.CancelledError:
        db.rollback()
        job.update({"status": "cancelled", "updated_at": now_iso(), "error": "cancelled"})
        raise
    except Exception as exc:
        db.rollback()
        job.update({"status": "failed", "updated_at": now_iso(), "error": str(exc)})
        print(f"backtest job {job_id} failed: {exc}")
    finally:
        db.close()
        backtest_job_tasks.pop(job_id, None)


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
        "ALTER TABLE asset_snapshots ALTER COLUMN symbol TYPE VARCHAR(32)",
        "ALTER TABLE asset_snapshots ALTER COLUMN name TYPE VARCHAR(96)",
        "ALTER TABLE paper_trades ALTER COLUMN symbol TYPE VARCHAR(32)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_ohlc_candle_columns() -> None:
    statements = [
        "ALTER TABLE ohlc_candles ALTER COLUMN time TYPE BIGINT",
        "ALTER TABLE ohlc_candles ALTER COLUMN symbol TYPE VARCHAR(32)",
        "ALTER TABLE ohlc_candles ADD COLUMN IF NOT EXISTS volume DOUBLE PRECISION NOT NULL DEFAULT 0",
        "DELETE FROM ohlc_candles WHERE time > 10000000000",
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
            "latest_klines_minutes": settings.kline_refresh_interval_minutes,
            "latest_kline_intervals": ["15m", "1h", "4h"],
            "daily_snapshot": "00:00 UTC",
        },
        "candidate_min_opportunity_score": settings.candidate_min_opportunity_score,
        "paper_min_opportunity_score": settings.paper_min_opportunity_score,
        "technical_refresh_limit": settings.technical_refresh_limit,
        "market_universe_source": settings.market_universe_source,
        "tracked_asset_count": settings.tracked_asset_count,
    }


@app.get("/assets", response_model=list[AssetOut])
def list_assets(db: Session = Depends(get_db)) -> list[AssetSnapshot]:
    return list(
        db.scalars(
            select(AssetSnapshot)
            .where(universe_asset_where_clause())
            .order_by(AssetSnapshot.opportunity_score.desc(), AssetSnapshot.market_cap.desc())
        )
    )


@app.get("/opportunities", response_model=list[AssetOut])
def list_opportunities(limit: int = 20, db: Session = Depends(get_db)) -> list[AssetSnapshot]:
    capped_limit = max(1, min(limit, 100))
    return list(
        db.scalars(
            select(AssetSnapshot)
            .where(universe_asset_where_clause())
            .order_by(AssetSnapshot.opportunity_score.desc(), AssetSnapshot.market_cap.desc())
            .limit(capped_limit)
        )
    )


@app.get("/assets/{symbol}", response_model=AssetOut)
async def get_asset(symbol: str, db: Session = Depends(get_db)) -> AssetSnapshot:
    asset = db.scalar(select(AssetSnapshot).where(AssetSnapshot.symbol == symbol.upper()))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    candles = await ensure_volume_ohlc_from_data_vision(db, asset.symbol, asset.coingecko_id, interval="4h", days=90)
    if not candles or not any(float(candle.get("volume") or 0) > 0 for candle in candles):
        candles = await fetch_binance_4h_ohlc(asset.symbol, days=90)
    if not candles:
        candles = await fetch_ohlc_data(asset.symbol, asset.coingecko_id)
    if candles:
        volumes = [float(candle.get("volume") or 0) for candle in candles]
        technicals = calculate_technicals(
            prices=[float(candle["close"]) for candle in candles],
            volumes=volumes,
            current_price=asset.current_price,
        )
        volume_note = "含真实成交量序列" if any(volume > 0 for volume in volumes) else "未拿到成交量序列"
        technicals["technical_note"] = f"基于 {len(candles)} 根 4 小时 K 线动态计算；{volume_note}。"
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


@app.post("/scheduler/futures-universe")
async def scheduler_futures_universe(
    import_klines: bool = False,
    days: int = 60,
    intervals: str = "15m,1h,4h",
    limit: int = 150,
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    verify_refresh_token(x_refresh_token)
    refreshed = await refresh_assets(db)
    kline_result = None
    if import_klines:
        parsed_intervals = [item.strip() for item in intervals.split(",") if item.strip()]
        kline_result = await import_binance_data_vision_klines(db, days=days, intervals=parsed_intervals, limit=limit)
    return {
        "refreshed": [asset.symbol for asset in refreshed],
        "count": len(refreshed),
        "import_klines": import_klines,
        "klines": kline_result,
    }


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


@app.post("/scheduler/latest-klines")
async def scheduler_latest_klines(
    limit: int = 100,
    intervals: str | None = None,
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    verify_refresh_token(x_refresh_token)
    parsed_intervals = [item.strip() for item in intervals.split(",") if item.strip()] if intervals else None
    return await refresh_latest_klines(db, limit=limit, intervals=parsed_intervals)


@app.post("/scheduler/latest-15m-klines")
async def scheduler_latest_15m_klines(
    limit: int = 100,
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    verify_refresh_token(x_refresh_token)
    return await refresh_latest_klines(db, limit=limit, intervals=["15m"])


@app.post("/scheduler/ohlc-cache")
async def scheduler_ohlc_cache(
    days: int = 60,
    interval: str = "1h",
    limit: int = 100,
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    verify_refresh_token(x_refresh_token)
    refreshed = await refresh_ohlc_cache(db, days=days, interval=interval, limit=limit)
    return {"refreshed": refreshed, "count": len(refreshed), "days": days, "interval": interval}


@app.post("/scheduler/import-binance-klines")
async def scheduler_import_binance_klines(
    days: int = 60,
    interval: str = "1h",
    intervals: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    verify_refresh_token(x_refresh_token)
    parsed_intervals = [item.strip() for item in intervals.split(",") if item.strip()] if intervals else None
    parsed_start_date = parse_query_date(start_date, "start_date") if start_date else None
    parsed_end_date = parse_query_date(end_date, "end_date") if end_date else None
    return await import_binance_data_vision_klines(
        db,
        days=days,
        interval=interval,
        intervals=parsed_intervals,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        limit=limit,
    )


def parse_query_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be YYYY-MM-DD") from exc


def resolve_backtest_version(version: str | None) -> str | None:
    if not version:
        return None
    return BACKTEST_VERSION_ALIASES.get(version, version)


def select_saved_backtest_run(days: int, interval: str, mode: str, version: str | None = None):
    statement = select(BacktestRun).where(
        BacktestRun.execution_interval == interval,
        BacktestRun.strategy_mode == mode,
        BacktestRun.days >= days,
    )
    strategy_version = resolve_backtest_version(version)
    if strategy_version:
        statement = statement.where(BacktestRun.strategy_version == strategy_version)
    return statement.order_by(BacktestRun.days.desc(), BacktestRun.created_at.desc()).limit(1)


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


@app.post("/paper-trading/reset")
async def paper_trading_reset(
    reopen: bool = True,
    refresh_first: bool = True,
    db: Session = Depends(get_db),
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    verify_refresh_token(x_refresh_token)
    removed_trades = len(list(db.scalars(select(PaperTrade.id))))
    removed_snapshots = len(list(db.scalars(select(PaperDailySnapshot.id))))
    db.execute(delete(PaperTrade))
    db.execute(delete(PaperDailySnapshot))
    db.commit()

    refreshed_assets = []
    if reopen:
        if refresh_first:
            refreshed_assets = await refresh_candidate_assets(db)
        else:
            refreshed_assets = list(
                db.scalars(
                    select(AssetSnapshot)
                    .where(universe_asset_where_clause())
                    .order_by(AssetSnapshot.opportunity_score.desc())
                )
            )
        apply_paper_trading(db, refreshed_assets, open_new=True)

    return {
        "reset": True,
        "removed_trades": removed_trades,
        "removed_daily_snapshots": removed_snapshots,
        "reopened": reopen,
        "refreshed_assets": len(refreshed_assets),
        "summary": build_paper_trading_summary(db),
    }


@app.post("/backtest/jobs")
async def backtest_job_start(
    days: int = 30,
    limit: int = 150,
    interval: str = "15m",
    mode: str = "indicator",
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    verify_refresh_token(x_refresh_token)
    active_job = next(
        (job for job in backtest_jobs.values() if job.get("status") in {"queued", "running"}),
        None,
    )
    if active_job:
        raise HTTPException(status_code=409, detail={"message": "Backtest job already running", "job": active_job})

    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "started_at": None,
        "completed_at": None,
        "parameters": {
            "days": days,
            "limit": limit,
            "interval": interval,
            "mode": mode,
        },
        "total_assets": 0,
        "completed_assets": 0,
        "current_asset": None,
        "last_asset_trades": 0,
        "total_trades": 0,
        "progress_percent": 0,
        "run_key": None,
        "summary": None,
        "error": None,
    }
    backtest_jobs[job_id] = job
    backtest_job_tasks[job_id] = asyncio.create_task(run_backtest_job(job_id, days, limit, interval, mode))
    return job


@app.get("/backtest/jobs")
def backtest_job_list() -> list[dict]:
    return sorted(backtest_jobs.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True)


@app.get("/backtest/jobs/{job_id}")
def backtest_job_detail(job_id: str) -> dict:
    job = backtest_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found")
    return job


@app.get("/backtest/month", response_model=BacktestResultOut)
async def backtest_month(days: int = 30, limit: int = 100, interval: str = "1h", mode: str = "indicator", db: Session = Depends(get_db)) -> dict:
    return await run_month_backtest(db, days=days, limit=limit, interval=interval, mode=mode)


@app.get("/backtest/runs", response_model=list[BacktestRunOut])
def backtest_runs(limit: int = 20, db: Session = Depends(get_db)) -> list[BacktestRun]:
    capped_limit = max(1, min(limit, 100))
    return list(db.scalars(select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(capped_limit)))


@app.get("/backtest/comparison", response_model=list[BacktestComparisonOut])
def backtest_comparison(interval: str = "15m", mode: str = "indicator", version: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    settings = get_settings()
    periods = [
        {"days": 30, "label": "1个月"},
        {"days": 60, "label": "2个月"},
        {"days": 180, "label": "6个月"},
    ]
    statement = select(BacktestRun).where(BacktestRun.execution_interval == interval, BacktestRun.strategy_mode == mode)
    strategy_version = resolve_backtest_version(version)
    if strategy_version:
        statement = statement.where(BacktestRun.strategy_version == strategy_version)
    available_runs = list(
        db.scalars(statement.order_by(BacktestRun.days.desc(), BacktestRun.created_at.desc()))
    )

    rows = []
    for period in periods:
        source = next((run for run in available_runs if run.days >= period["days"]), None)
        if not source:
            rows.append(
                {
                    "days": period["days"],
                    "label": period["label"],
                    "source_run_key": None,
                    "source_days": None,
                    "derived": False,
                    "summary": None,
                }
            )
            continue
        rows.append(
            {
                "days": period["days"],
                "label": period["label"],
                "source_run_key": source.run_key,
                "source_days": source.days,
                "derived": source.days != period["days"],
                "summary": derive_backtest_period_summary(source, period["days"], settings.paper_account_balance),
            }
        )
    return rows


@app.get("/backtest/runs/{run_key}", response_model=BacktestResultOut)
def backtest_run_detail(run_key: str, days: int | None = None, db: Session = Depends(get_db)) -> dict:
    run = db.scalar(select(BacktestRun).where(BacktestRun.run_key == run_key))
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    if days and days != run.days:
        if days > run.days:
            raise HTTPException(status_code=400, detail="Requested days exceed source run days")
        return derive_backtest_period_result(run, days, get_settings().paper_account_balance)
    return derive_backtest_period_result(run, run.days, get_settings().paper_account_balance)


@app.get("/backtest/saved-result", response_model=BacktestResultOut)
def backtest_saved_result(days: int = 30, interval: str = "15m", mode: str = "indicator", version: str | None = None, trade_limit: int | None = None, db: Session = Depends(get_db)) -> dict:
    run = db.scalar(select_saved_backtest_run(days, interval, mode, version))
    if not run:
        raise HTTPException(status_code=404, detail="Saved backtest result not found")
    capped_limit = None if trade_limit is None else max(0, min(trade_limit, 500))
    return derive_backtest_period_result(run, days, get_settings().paper_account_balance, trade_limit=capped_limit)


@app.get("/backtest/trades", response_model=BacktestTradesPageOut)
def backtest_trades(
    days: int = 30,
    interval: str = "15m",
    mode: str = "indicator",
    page: int = 1,
    page_size: int = 50,
    symbol: str | None = None,
    side: str | None = None,
    result: str | None = None,
    strategy_type: str | None = None,
    version: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    run = db.scalar(select_saved_backtest_run(days, interval, mode, version))
    if not run:
        raise HTTPException(status_code=404, detail="Saved backtest result not found")

    data = derive_backtest_period_result(run, days, get_settings().paper_account_balance)
    all_trades = data["trades"]
    filter_options = {
        "symbols": sorted({str(trade.get("symbol")) for trade in all_trades if trade.get("symbol")}),
        "sides": sorted({str(trade.get("side")) for trade in all_trades if trade.get("side")}),
        "results": sorted({str(trade.get("close_reason") or "平仓") for trade in all_trades}),
        "strategy_types": sorted({str(trade.get("strategy_type")) for trade in all_trades if trade.get("strategy_type")}),
    }

    filtered = all_trades
    if symbol:
        filtered = [trade for trade in filtered if str(trade.get("symbol", "")).upper() == symbol.upper()]
    if side:
        filtered = [trade for trade in filtered if trade.get("side") == side]
    if result:
        filtered = [trade for trade in filtered if (trade.get("close_reason") or "平仓") == result]
    if strategy_type:
        filtered = [trade for trade in filtered if trade.get("strategy_type") == strategy_type]

    capped_page_size = max(10, min(page_size, 100))
    total = len(filtered)
    total_pages = max(1, (total + capped_page_size - 1) // capped_page_size)
    current_page = max(1, min(page, total_pages))
    start = (current_page - 1) * capped_page_size
    return {
        "days": days,
        "interval": interval,
        "mode": mode,
        "page": current_page,
        "page_size": capped_page_size,
        "total": total,
        "total_pages": total_pages,
        "filter_options": filter_options,
        "trades": filtered[start:start + capped_page_size],
    }
