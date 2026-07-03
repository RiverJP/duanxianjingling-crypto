def clamp(value: float, lower: int = 0, upper: int = 100) -> int:
    return int(max(lower, min(upper, round(value))))


def calculate_scores(change_24h: float, market_cap: float, volume_24h: float) -> dict[str, int]:
    trend_score = clamp(50 + change_24h * 4)
    volume_to_cap = volume_24h / market_cap if market_cap else 0
    liquidity_score = clamp(45 + volume_to_cap * 500)
    volatility_penalty = min(abs(change_24h) * 3, 35)
    risk_score = clamp(55 + volatility_penalty - liquidity_score * 0.15)
    ai_score = clamp(trend_score * 0.4 + liquidity_score * 0.35 + (100 - risk_score) * 0.25)

    return {
        "ai_score": ai_score,
        "trend_score": trend_score,
        "liquidity_score": liquidity_score,
        "risk_score": risk_score,
    }
