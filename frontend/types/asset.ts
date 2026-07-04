export type Asset = {
  coingecko_id: string;
  symbol: string;
  name: string;
  image_url: string | null;
  current_price: number;
  market_cap: number;
  volume_24h: number;
  change_24h: number;
  ai_score: number;
  trend_score: number;
  liquidity_score: number;
  risk_score: number;
  trade_signal: string;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward_ratio: number | null;
  trade_rationale: string;
  opportunity_score: number;
  opportunity_status: string;
  opportunity_type: string;
  trigger_price: number | null;
  invalid_price: number | null;
  opportunity_reason: string;
  fib_236: number | null;
  fib_382: number | null;
  fib_500: number | null;
  fib_618: number | null;
  fib_786: number | null;
  dt_upper: number | null;
  dt_lower: number | null;
  dt_signal: string;
  vegas_fast: number | null;
  vegas_slow: number | null;
  vegas_signal: string;
  trend_line: string;
  support_level: number | null;
  resistance_level: number | null;
  market_cycle: string;
  volume_price_relation: string;
  ma_50: number | null;
  ma_100: number | null;
  ma_200: number | null;
  technical_note: string;
  ai_summary: string;
  source_updated_at: string | null;
  refreshed_at: string | null;
};

export type OhlcCandle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type PaperTradingSummary = {
  account_balance: number;
  margin_per_trade: number;
  leverage: number;
  fee_rate: number;
  min_opportunity_score: number;
  open_trades: number;
  closed_trades: number;
  used_margin: number;
  open_notional: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  total_fees: number;
  total_pnl_percent: number;
  daily_pnl: number;
  seven_day_pnl: number;
  thirty_day_pnl: number;
  win_rate: number;
};

export type EquityCurvePoint = {
  date: string;
  equity: number;
  pnl: number;
};

export type PaperTrade = {
  id: number;
  symbol: string;
  name: string;
  side: string;
  status: string;
  entry_price: number;
  current_price: number;
  exit_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  margin_usdt: number;
  leverage: number;
  notional_usdt: number;
  opportunity_score: number;
  pnl_usdt: number;
  pnl_percent: number;
  opened_at: string | null;
  closed_at: string | null;
  close_reason: string | null;
};

export type SchedulerStatus = {
  enabled: boolean;
  tasks: {
    market_scan_minutes: number;
    candidate_scan_minutes: number;
    paper_position_minutes: number;
    technical_refresh_minutes: number;
    latest_klines_minutes: number;
    latest_kline_intervals: string[];
    daily_snapshot: string;
  };
  candidate_min_opportunity_score: number;
  paper_min_opportunity_score: number;
  technical_refresh_limit: number;
  market_universe_source: string;
  tracked_asset_count: number;
};

export type BacktestSummary = {
  run_id: number | null;
  run_key: string | null;
  strategy_mode: string | null;
  strategy_version: string | null;
  generated_at: string | null;
  days: number;
  execution_interval: string;
  trend_interval: string;
  tested_assets: number;
  traded_assets: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  total_pnl_percent: number;
  average_pnl: number;
  fee_rate: number;
  total_fees: number;
  net_pnl: number;
  net_pnl_percent: number;
  average_net_pnl: number;
  net_win_rate: number;
  best_trade: number;
  worst_trade: number;
  excluded_period_end_trades: number;
  excluded_low_risk_reward_trades: number;
  excluded_portfolio_trades: number;
  max_concurrent_trades: number;
};

export type BacktestRules = {
  title: string;
  mode: string;
  version: string;
  timeframes: string[];
  entry_conditions: string[];
  long_logic: string[];
  short_logic: string[];
  stop_loss_logic: string[];
  take_profit_logic: string[];
  exit_logic: string[];
  indicator_analysis: string[];
  risk_notes: string[];
};

export type BacktestTrade = {
  symbol: string;
  name: string;
  side: string;
  entry_price: number;
  current_price: number;
  exit_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward_ratio: number | null;
  margin_usdt: number;
  leverage: number;
  notional_usdt: number;
  opportunity_score: number;
  execution_interval: string;
  strategy_type: string | null;
  market_regime: string | null;
  entry_reasons: string[];
  indicator_snapshot: Record<string, unknown>;
  opening_logic: string | null;
  pnl_usdt: number;
  pnl_percent: number;
  opened_at: string;
  closed_at: string | null;
  close_reason: string | null;
};

export type BacktestAsset = {
  symbol: string;
  name: string;
  market_cap: number;
  candle_count: number;
  best_opportunity_score: number;
  best_signal: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_pnl: number;
  status: string;
  execution_interval: string;
};

export type BacktestResult = {
  summary: BacktestSummary;
  rules: BacktestRules;
  equity_curve: EquityCurvePoint[];
  trades: BacktestTrade[];
  assets: BacktestAsset[];
};

export type BacktestRun = {
  id: number;
  run_key: string;
  strategy_mode: string;
  strategy_version: string;
  days: number;
  execution_interval: string;
  trend_interval: string;
  tested_assets: number;
  total_trades: number;
  total_pnl: number;
  win_rate: number;
  created_at: string;
};

export type BacktestComparisonItem = {
  days: number;
  label: string;
  source_run_key: string | null;
  source_days: number | null;
  derived: boolean;
  summary: BacktestSummary | null;
};

export type BacktestTradesPage = {
  days: number;
  interval: string;
  mode: string;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  filter_options: {
    symbols: string[];
    sides: string[];
    results: string[];
    strategy_types: string[];
  };
  trades: BacktestTrade[];
};
