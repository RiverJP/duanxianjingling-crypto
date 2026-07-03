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
  min_opportunity_score: number;
  open_trades: number;
  closed_trades: number;
  used_margin: number;
  open_notional: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
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
    daily_snapshot: string;
  };
  candidate_min_opportunity_score: number;
  paper_min_opportunity_score: number;
  technical_refresh_limit: number;
};
