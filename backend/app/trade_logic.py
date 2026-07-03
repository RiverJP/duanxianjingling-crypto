def build_trade_plan(
    current_price: float,
    change_24h: float,
    ai_score: int,
    trend_score: int,
    liquidity_score: int,
    risk_score: int,
) -> dict[str, float | str | None]:
    opportunity_score = score_opportunity(ai_score, trend_score, liquidity_score, risk_score)

    if current_price <= 0:
        return empty_plan("观望", "价格数据无效，暂不生成交易计划。")

    risk_pct = max(0.015, min(0.08, risk_score / 100 * 0.06))
    reward_pct = risk_pct * (1.45 + liquidity_score / 160)

    if risk_score >= 78:
        return empty_plan("观望", "风险评分偏高，优先等待更清晰的入场机会。", current_price, opportunity_score)

    if liquidity_score < 40:
        return empty_plan("观望", "流动性评分偏低，滑点和执行风险较高。", current_price, opportunity_score)

    if trend_score >= 62 and change_24h > 0 and ai_score >= 55:
        stop_loss = current_price * (1 - risk_pct)
        take_profit = current_price * (1 + reward_pct)
        status = opportunity_status(opportunity_score, "做多")
        return {
            "trade_signal": "做多",
            "entry_price": round(current_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "risk_reward_ratio": round((take_profit - current_price) / (current_price - stop_loss), 2),
            "trade_rationale": "趋势和 AI 评分偏强，且流动性足以支持短线研究型多头计划。",
            "opportunity_score": opportunity_score,
            "opportunity_status": status,
            "opportunity_type": "做多",
            "trigger_price": round(current_price * 1.003, 2),
            "invalid_price": round(stop_loss, 2),
            "opportunity_reason": "价格强于 24 小时动量，趋势评分进入多头区，等待回踩不破或放量突破触发。",
        }

    if trend_score <= 42 and change_24h < 0 and ai_score <= 52 and risk_score < 72:
        stop_loss = current_price * (1 + risk_pct)
        take_profit = current_price * (1 - reward_pct)
        status = opportunity_status(opportunity_score, "做空")
        return {
            "trade_signal": "做空",
            "entry_price": round(current_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "risk_reward_ratio": round((current_price - take_profit) / (stop_loss - current_price), 2),
            "trade_rationale": "趋势和 AI 评分偏弱，且风险未进入极端区间，适合短线研究型空头计划。",
            "opportunity_score": opportunity_score,
            "opportunity_status": status,
            "opportunity_type": "做空",
            "trigger_price": round(current_price * 0.997, 2),
            "invalid_price": round(stop_loss, 2),
            "opportunity_reason": "价格弱于 24 小时动量，趋势评分偏空，等待跌破触发价后再观察空头延续。",
        }

    return empty_plan("观望", "当前信号不够一致，建议等待趋势、流动性和风险评分进一步共振。", current_price, opportunity_score)


def empty_plan(
    signal: str,
    rationale: str,
    entry_price: float | None = None,
    opportunity_score: int = 0,
) -> dict[str, float | str | None]:
    return {
        "trade_signal": signal,
        "entry_price": round(entry_price, 2) if entry_price else None,
        "stop_loss": None,
        "take_profit": None,
        "risk_reward_ratio": None,
        "trade_rationale": rationale,
        "opportunity_score": opportunity_score,
        "opportunity_status": opportunity_status(opportunity_score, signal),
        "opportunity_type": signal,
        "trigger_price": None,
        "invalid_price": None,
        "opportunity_reason": rationale,
    }


def score_opportunity(ai_score: int, trend_score: int, liquidity_score: int, risk_score: int) -> int:
    score = ai_score * 0.35 + trend_score * 0.3 + liquidity_score * 0.2 + (100 - risk_score) * 0.15
    return max(0, min(100, round(score)))


def opportunity_status(score: int, signal: str) -> str:
    if signal in {"做多", "做空"} and score >= 80:
        return "高优先级"
    if signal in {"做多", "做空"} and score >= 75:
        return "可关注"
    if score >= 55:
        return "等待触发"
    return "观察"
