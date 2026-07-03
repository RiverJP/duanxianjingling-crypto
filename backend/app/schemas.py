from datetime import datetime

from pydantic import BaseModel


class AssetOut(BaseModel):
    coingecko_id: str
    symbol: str
    name: str
    image_url: str | None
    current_price: float
    market_cap: float
    volume_24h: float
    change_24h: float
    ai_score: int
    trend_score: int
    liquidity_score: int
    risk_score: int
    trade_signal: str
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_reward_ratio: float | None
    trade_rationale: str
    opportunity_score: int
    opportunity_status: str
    opportunity_type: str
    trigger_price: float | None
    invalid_price: float | None
    opportunity_reason: str
    fib_236: float | None
    fib_382: float | None
    fib_500: float | None
    fib_618: float | None
    fib_786: float | None
    dt_upper: float | None
    dt_lower: float | None
    dt_signal: str
    vegas_fast: float | None
    vegas_slow: float | None
    vegas_signal: str
    trend_line: str
    support_level: float | None
    resistance_level: float | None
    market_cycle: str
    volume_price_relation: str
    ma_50: float | None
    ma_100: float | None
    ma_200: float | None
    technical_note: str
    ai_summary: str
    source_updated_at: datetime | None
    refreshed_at: datetime | None

    model_config = {"from_attributes": True}


class RefreshOut(BaseModel):
    refreshed: list[str]
    count: int


class OhlcCandleOut(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float


class PaperTradeOut(BaseModel):
    id: int
    symbol: str
    name: str
    side: str
    status: str
    entry_price: float
    current_price: float
    exit_price: float | None
    stop_loss: float | None
    take_profit: float | None
    margin_usdt: float
    leverage: int
    notional_usdt: float
    opportunity_score: int
    pnl_usdt: float
    pnl_percent: float
    opened_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None

    model_config = {"from_attributes": True}


class PaperTradingSummaryOut(BaseModel):
    account_balance: float
    margin_per_trade: float
    leverage: int
    min_opportunity_score: int
    open_trades: int
    closed_trades: int
    used_margin: float
    open_notional: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_pnl_percent: float
    daily_pnl: float
    seven_day_pnl: float
    thirty_day_pnl: float
    win_rate: float


class EquityCurvePointOut(BaseModel):
    date: str
    equity: float
    pnl: float
