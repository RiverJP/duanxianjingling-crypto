from datetime import datetime

from pydantic import BaseModel, Field


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


class BacktestSummaryOut(BaseModel):
    run_id: int | None = None
    run_key: str | None = None
    strategy_mode: str | None = None
    strategy_version: str | None = None
    generated_at: str | None = None
    days: int
    execution_interval: str
    trend_interval: str
    tested_assets: int
    traded_assets: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    average_pnl: float
    fee_rate: float = 0
    total_fees: float = 0
    net_pnl: float = 0
    net_pnl_percent: float = 0
    average_net_pnl: float = 0
    net_win_rate: float = 0
    best_trade: float
    worst_trade: float
    excluded_period_end_trades: int = 0
    excluded_low_risk_reward_trades: int = 0


class BacktestTradeOut(BaseModel):
    symbol: str
    name: str
    side: str
    entry_price: float
    current_price: float
    exit_price: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_reward_ratio: float | None = None
    margin_usdt: float
    leverage: int
    notional_usdt: float
    opportunity_score: int
    execution_interval: str
    strategy_type: str | None = None
    market_regime: str | None = None
    entry_reasons: list[str] = Field(default_factory=list)
    indicator_snapshot: dict = Field(default_factory=dict)
    opening_logic: str | None = None
    pnl_usdt: float
    pnl_percent: float
    opened_at: str
    closed_at: str | None
    close_reason: str | None


class BacktestAssetOut(BaseModel):
    symbol: str
    name: str
    market_cap: float
    candle_count: int
    best_opportunity_score: int
    best_signal: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    status: str
    execution_interval: str


class BacktestResultOut(BaseModel):
    summary: BacktestSummaryOut
    rules: dict
    equity_curve: list[EquityCurvePointOut]
    trades: list[BacktestTradeOut]
    assets: list[BacktestAssetOut]


class BacktestRunOut(BaseModel):
    id: int
    run_key: str
    strategy_mode: str
    strategy_version: str
    days: int
    execution_interval: str
    trend_interval: str
    tested_assets: int
    total_trades: int
    total_pnl: float
    win_rate: float
    created_at: datetime

    model_config = {"from_attributes": True}


class BacktestComparisonOut(BaseModel):
    days: int
    label: str
    source_run_key: str | None
    source_days: int | None
    derived: bool
    summary: BacktestSummaryOut | None


class BacktestTradesPageOut(BaseModel):
    days: int
    interval: str
    mode: str
    page: int
    page_size: int
    total: int
    total_pages: int
    filter_options: dict[str, list[str]]
    trades: list[BacktestTradeOut]
