from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AssetSnapshot, PaperDailySnapshot, PaperTrade

PAPER_MAX_HOLDING_SECONDS = 7 * 24 * 3600


def apply_paper_trading(db: Session, assets: list[AssetSnapshot], open_new: bool = True) -> None:
    update_open_trades(db, assets)
    if open_new:
        open_new_trades(db, assets)
    db.commit()


def update_open_trades(db: Session, assets: list[AssetSnapshot]) -> None:
    asset_by_symbol = {asset.symbol: asset for asset in assets}
    open_trades = list(db.scalars(select(PaperTrade).where(PaperTrade.status == "open")))

    for trade in open_trades:
        asset = asset_by_symbol.get(trade.symbol)
        if not asset:
            continue

        trade.current_price = asset.current_price
        trade.pnl_usdt = calculate_pnl(trade.side, trade.entry_price, asset.current_price, trade.notional_usdt)
        trade.pnl_percent = calculate_pnl_percent(trade.pnl_usdt, trade.margin_usdt)

        should_close, close_reason = should_close_trade(trade, asset.current_price)
        if should_close:
            trade.status = "closed"
            trade.exit_price = asset.current_price
            trade.closed_at = datetime.now(timezone.utc)
            trade.close_reason = close_reason


def open_new_trades(db: Session, assets: list[AssetSnapshot]) -> None:
    settings = get_settings()
    open_symbols = set(db.scalars(select(PaperTrade.symbol).where(PaperTrade.status == "open")))

    for asset in assets:
        if asset.symbol in open_symbols:
            continue
        if asset.opportunity_score < settings.paper_min_opportunity_score:
            continue
        if asset.trade_signal not in {"做多", "做空"}:
            continue
        if asset.risk_reward_ratio is None or asset.risk_reward_ratio < 1:
            continue
        if not asset.stop_loss or not asset.take_profit or asset.current_price <= 0:
            continue

        margin = settings.paper_margin_per_trade
        leverage = settings.paper_leverage
        trade = PaperTrade(
            symbol=asset.symbol,
            name=asset.name,
            side=asset.trade_signal,
            status="open",
            entry_price=asset.current_price,
            current_price=asset.current_price,
            stop_loss=asset.stop_loss,
            take_profit=asset.take_profit,
            margin_usdt=margin,
            leverage=leverage,
            notional_usdt=margin * leverage,
            opportunity_score=asset.opportunity_score,
            pnl_usdt=0,
            pnl_percent=0,
        )
        db.add(trade)
        open_symbols.add(asset.symbol)


def should_close_trade(trade: PaperTrade, current_price: float) -> tuple[bool, str | None]:
    if trade.side == "做多":
        if trade.take_profit and current_price >= trade.take_profit:
            return True, "止盈"
        if trade.stop_loss and current_price <= trade.stop_loss:
            return True, "止损"
    if trade.side == "做空":
        if trade.take_profit and current_price <= trade.take_profit:
            return True, "止盈"
        if trade.stop_loss and current_price >= trade.stop_loss:
            return True, "止损"
    opened_at = normalize_datetime(trade.opened_at) if trade.opened_at else datetime.now(timezone.utc)
    if datetime.now(timezone.utc) - opened_at >= timedelta(seconds=PAPER_MAX_HOLDING_SECONDS):
        return True, "到期平仓"
    return False, None


def calculate_pnl(side: str, entry_price: float, current_price: float, notional: float) -> float:
    if entry_price <= 0:
        return 0
    if side == "做空":
        value = (entry_price - current_price) / entry_price * notional
    else:
        value = (current_price - entry_price) / entry_price * notional
    return round(value, 2)


def calculate_pnl_percent(pnl_usdt: float, margin: float) -> float:
    if margin <= 0:
        return 0
    return round(pnl_usdt / margin * 100, 2)


def build_paper_trading_summary(db: Session) -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    trades = list(db.scalars(select(PaperTrade).order_by(PaperTrade.opened_at.desc())))
    open_trades = [trade for trade in trades if trade.status == "open"]
    closed_trades = [trade for trade in trades if trade.status == "closed"]

    realized_total = sum(trade.pnl_usdt for trade in closed_trades)
    unrealized_total = sum(trade.pnl_usdt for trade in open_trades)
    total_pnl = realized_total + unrealized_total
    open_notional = sum(trade.notional_usdt for trade in open_trades)

    return {
        "account_balance": settings.paper_account_balance,
        "margin_per_trade": settings.paper_margin_per_trade,
        "leverage": settings.paper_leverage,
        "min_opportunity_score": settings.paper_min_opportunity_score,
        "open_trades": len(open_trades),
        "closed_trades": len(closed_trades),
        "used_margin": round(sum(trade.margin_usdt for trade in open_trades), 2),
        "open_notional": round(open_notional, 2),
        "realized_pnl": round(realized_total, 2),
        "unrealized_pnl": round(unrealized_total, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_percent": round(total_pnl / settings.paper_account_balance * 100, 2) if settings.paper_account_balance else 0,
        "daily_pnl": round(period_pnl(closed_trades, now - timedelta(days=1)) + unrealized_total, 2),
        "seven_day_pnl": round(period_pnl(closed_trades, now - timedelta(days=7)) + unrealized_total, 2),
        "thirty_day_pnl": round(period_pnl(closed_trades, now - timedelta(days=30)) + unrealized_total, 2),
        "win_rate": win_rate(closed_trades),
    }


def build_equity_curve(db: Session, days: int = 30) -> list[dict[str, float | str]]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    start = now.date() - timedelta(days=max(1, days) - 1)
    trades = list(db.scalars(select(PaperTrade).order_by(PaperTrade.opened_at.asc())))
    closed_trades = [trade for trade in trades if trade.status == "closed" and trade.closed_at]
    open_trades = [trade for trade in trades if trade.status == "open"]
    unrealized_total = sum(trade.pnl_usdt for trade in open_trades)

    points = []
    cumulative_realized = 0.0
    for offset in range(max(1, days)):
        current_date = start + timedelta(days=offset)
        day_realized = sum(
            trade.pnl_usdt
            for trade in closed_trades
            if normalize_datetime(trade.closed_at).date() == current_date
        )
        cumulative_realized += day_realized
        floating = unrealized_total if current_date == now.date() else 0
        total_pnl = cumulative_realized + floating
        points.append(
            {
                "date": current_date.isoformat(),
                "equity": round(settings.paper_account_balance + total_pnl, 2),
                "pnl": round(total_pnl, 2),
            }
        )
    return points


def record_daily_snapshot(db: Session, snapshot_date: str | None = None) -> PaperDailySnapshot:
    now = datetime.now(timezone.utc)
    target_date = snapshot_date or now.date().isoformat()
    summary = build_paper_trading_summary(db)
    snapshot = db.scalar(select(PaperDailySnapshot).where(PaperDailySnapshot.snapshot_date == target_date))
    if snapshot is None:
        snapshot = PaperDailySnapshot(snapshot_date=target_date)
        db.add(snapshot)

    snapshot.account_balance = summary["account_balance"]
    snapshot.equity = round(summary["account_balance"] + summary["total_pnl"], 2)
    snapshot.total_pnl = summary["total_pnl"]
    snapshot.realized_pnl = summary["realized_pnl"]
    snapshot.unrealized_pnl = summary["unrealized_pnl"]
    snapshot.open_trades = summary["open_trades"]
    snapshot.closed_trades = summary["closed_trades"]
    snapshot.win_rate = summary["win_rate"]
    db.commit()
    db.refresh(snapshot)
    return snapshot


def period_pnl(trades: list[PaperTrade], start: datetime) -> float:
    return sum(trade.pnl_usdt for trade in trades if trade.closed_at and normalize_datetime(trade.closed_at) >= start)


def win_rate(trades: list[PaperTrade]) -> float:
    if not trades:
        return 0
    wins = sum(1 for trade in trades if trade.pnl_usdt > 0)
    return round(wins / len(trades) * 100, 2)


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo:
        return value
    return value.replace(tzinfo=timezone.utc)
