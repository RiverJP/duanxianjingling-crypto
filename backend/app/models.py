from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coingecko_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(96))
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    current_price: Mapped[float] = mapped_column(Float, default=0)
    market_cap: Mapped[float] = mapped_column(Float, default=0)
    volume_24h: Mapped[float] = mapped_column(Float, default=0)
    change_24h: Mapped[float] = mapped_column(Float, default=0)
    ai_score: Mapped[int] = mapped_column(Integer, default=50)
    trend_score: Mapped[int] = mapped_column(Integer, default=50)
    liquidity_score: Mapped[int] = mapped_column(Integer, default=50)
    risk_score: Mapped[int] = mapped_column(Integer, default=50)
    trade_signal: Mapped[str] = mapped_column(String(16), default="观望")
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    trade_rationale: Mapped[str] = mapped_column(Text, default="")
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    opportunity_status: Mapped[str] = mapped_column(String(24), default="观察")
    opportunity_type: Mapped[str] = mapped_column(String(16), default="观望")
    trigger_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    invalid_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    opportunity_reason: Mapped[str] = mapped_column(Text, default="")
    fib_236: Mapped[float | None] = mapped_column(Float, nullable=True)
    fib_382: Mapped[float | None] = mapped_column(Float, nullable=True)
    fib_500: Mapped[float | None] = mapped_column(Float, nullable=True)
    fib_618: Mapped[float | None] = mapped_column(Float, nullable=True)
    fib_786: Mapped[float | None] = mapped_column(Float, nullable=True)
    dt_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    dt_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    dt_signal: Mapped[str] = mapped_column(String(32), default="数据不足")
    vegas_fast: Mapped[float | None] = mapped_column(Float, nullable=True)
    vegas_slow: Mapped[float | None] = mapped_column(Float, nullable=True)
    vegas_signal: Mapped[str] = mapped_column(String(32), default="数据不足")
    trend_line: Mapped[str] = mapped_column(String(32), default="数据不足")
    support_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    resistance_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cycle: Mapped[str] = mapped_column(String(32), default="数据不足")
    volume_price_relation: Mapped[str] = mapped_column(String(32), default="数据不足")
    ma_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_200: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_note: Mapped[str] = mapped_column(Text, default="")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(96))
    side: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_usdt: Mapped[float] = mapped_column(Float, default=500)
    leverage: Mapped[int] = mapped_column(Integer, default=5)
    notional_usdt: Mapped[float] = mapped_column(Float, default=2500)
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    pnl_usdt: Mapped[float] = mapped_column(Float, default=0)
    pnl_percent: Mapped[float] = mapped_column(Float, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    close_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PaperDailySnapshot(Base):
    __tablename__ = "paper_daily_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    account_balance: Mapped[float] = mapped_column(Float, default=10000)
    equity: Mapped[float] = mapped_column(Float, default=10000)
    total_pnl: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    open_trades: Mapped[int] = mapped_column(Integer, default=0)
    closed_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class OhlcCandle(Base):
    __tablename__ = "ohlc_candles"
    __table_args__ = (UniqueConstraint("symbol", "interval", "time", name="uq_ohlc_symbol_interval_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    coingecko_id: Mapped[str] = mapped_column(String(64), index=True)
    interval: Mapped[str] = mapped_column(String(8), index=True)
    time: Mapped[int] = mapped_column(BigInteger, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(32), default="external")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_key: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    strategy_mode: Mapped[str] = mapped_column(String(24), index=True)
    strategy_version: Mapped[str] = mapped_column(String(48), index=True)
    days: Mapped[int] = mapped_column(Integer, index=True)
    execution_interval: Mapped[str] = mapped_column(String(8), index=True)
    trend_interval: Mapped[str] = mapped_column(String(16), index=True)
    tested_assets: Mapped[int] = mapped_column(Integer, default=0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0)
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    rules_json: Mapped[str] = mapped_column(Text, default="{}")
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    equity_curve_json: Mapped[str] = mapped_column(Text, default="[]")
    assets_json: Mapped[str] = mapped_column(Text, default="[]")
    trades_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
