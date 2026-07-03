from app.config import get_settings


def build_mock_summary(name: str, change_24h: float, liquidity_score: int, risk_score: int) -> str:
    direction = "上涨" if change_24h >= 0 else "下跌"
    return (
        f"{name} 过去 24 小时{direction} {abs(change_24h):.2f}%。"
        f"流动性评分为 {liquidity_score}/100，风险模型评分为 {risk_score}/100。"
        "这是一段用于研究筛选的模拟 AI 摘要，不构成投资建议。"
    )


async def generate_summary(name: str, symbol: str, price: float, change_24h: float, market_cap: float, volume_24h: float, liquidity_score: int, risk_score: int) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        return build_mock_summary(name, change_24h, liquidity_score, risk_score)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.responses.create(
            model="gpt-4.1-mini",
            input=(
                "请用中文写一段简洁的短线精灵加密市场扫描摘要。"
                "不要给出投资建议。"
                f"资产：{name}（{symbol.upper()}）；价格：${price:,.2f}；"
                f"24 小时变化：{change_24h:.2f}%；市值：${market_cap:,.0f}；"
                f"24 小时成交量：${volume_24h:,.0f}；流动性评分：{liquidity_score}；"
                f"风险评分：{risk_score}。"
            ),
        )
        return response.output_text.strip()
    except Exception:
        return build_mock_summary(name, change_24h, liquidity_score, risk_score)
