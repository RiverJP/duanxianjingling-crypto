from statistics import mean


def calculate_technicals(prices: list[float], volumes: list[float], current_price: float) -> dict[str, float | str | None]:
    clean_prices = [float(price) for price in prices if price is not None and price > 0]
    clean_volumes = [float(volume) for volume in volumes if volume is not None and volume >= 0]

    if len(clean_prices) < 50:
        return empty_technicals("历史数据不足，暂无法计算完整技术参数。")

    ma_50 = simple_ma(clean_prices, 50)
    ma_100 = simple_ma(clean_prices, 100)
    ma_200 = simple_ma(clean_prices, 200)
    ema_144 = ema(clean_prices, 144)
    ema_169 = ema(clean_prices, 169)
    fib = fibonacci_levels(clean_prices[-90:])
    dt = dual_thrust_proxy(clean_prices[-21:], current_price)
    trend = trend_line_signal(clean_prices[-30:])
    support = min(clean_prices[-30:])
    resistance = max(clean_prices[-30:])
    cycle = market_cycle(current_price, ma_50, ma_100, ma_200)
    volume_price = volume_price_relation(clean_prices, clean_volumes)
    vegas = vegas_signal(current_price, ema_144, ema_169)

    return {
        "fib_236": fib["fib_236"],
        "fib_382": fib["fib_382"],
        "fib_500": fib["fib_500"],
        "fib_618": fib["fib_618"],
        "fib_786": fib["fib_786"],
        "dt_upper": dt["dt_upper"],
        "dt_lower": dt["dt_lower"],
        "dt_signal": dt["dt_signal"],
        "vegas_fast": round(ema_144, 2) if ema_144 else None,
        "vegas_slow": round(ema_169, 2) if ema_169 else None,
        "vegas_signal": vegas,
        "trend_line": trend,
        "support_level": round(support, 2),
        "resistance_level": round(resistance, 2),
        "market_cycle": cycle,
        "volume_price_relation": volume_price,
        "ma_50": round(ma_50, 2) if ma_50 else None,
        "ma_100": round(ma_100, 2) if ma_100 else None,
        "ma_200": round(ma_200, 2) if ma_200 else None,
        "technical_note": "基于 CoinGecko 日频价格与成交量计算，DT 与趋势线为研究近似值。",
    }


def empty_technicals(note: str) -> dict[str, float | str | None]:
    return {
        "fib_236": None,
        "fib_382": None,
        "fib_500": None,
        "fib_618": None,
        "fib_786": None,
        "dt_upper": None,
        "dt_lower": None,
        "dt_signal": "数据不足",
        "vegas_fast": None,
        "vegas_slow": None,
        "vegas_signal": "数据不足",
        "trend_line": "数据不足",
        "support_level": None,
        "resistance_level": None,
        "market_cycle": "数据不足",
        "volume_price_relation": "数据不足",
        "ma_50": None,
        "ma_100": None,
        "ma_200": None,
        "technical_note": note,
    }


def simple_ma(values: list[float], length: int) -> float | None:
    if len(values) < length:
        return None
    return mean(values[-length:])


def ema(values: list[float], length: int) -> float | None:
    if len(values) < length:
        return None
    multiplier = 2 / (length + 1)
    value = mean(values[:length])
    for price in values[length:]:
        value = price * multiplier + value * (1 - multiplier)
    return value


def fibonacci_levels(values: list[float]) -> dict[str, float | None]:
    if len(values) < 2:
        return {key: None for key in ["fib_236", "fib_382", "fib_500", "fib_618", "fib_786"]}
    low = min(values)
    high = max(values)
    span = high - low
    return {
        "fib_236": round(high - span * 0.236, 2),
        "fib_382": round(high - span * 0.382, 2),
        "fib_500": round(high - span * 0.5, 2),
        "fib_618": round(high - span * 0.618, 2),
        "fib_786": round(high - span * 0.786, 2),
    }


def dual_thrust_proxy(values: list[float], current_price: float) -> dict[str, float | str | None]:
    if len(values) < 21:
        return {"dt_upper": None, "dt_lower": None, "dt_signal": "数据不足"}
    window = values[:-1]
    open_proxy = values[-2]
    range_proxy = max(max(window) - min(window), abs(max(window) - open_proxy), abs(open_proxy - min(window)))
    upper = open_proxy + range_proxy * 0.5
    lower = open_proxy - range_proxy * 0.5
    if current_price > upper:
        signal = "突破上轨"
    elif current_price < lower:
        signal = "跌破下轨"
    else:
        signal = "区间内"
    return {"dt_upper": round(upper, 2), "dt_lower": round(lower, 2), "dt_signal": signal}


def trend_line_signal(values: list[float]) -> str:
    if len(values) < 10:
        return "数据不足"
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = mean(values)
    numerator = sum((index - x_mean) * (price - y_mean) for index, price in enumerate(values))
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    slope = numerator / denominator if denominator else 0
    slope_pct = slope / y_mean * 100 if y_mean else 0
    if slope_pct > 0.12:
        return "上升趋势线"
    if slope_pct < -0.12:
        return "下降趋势线"
    return "横盘趋势线"


def vegas_signal(current_price: float, fast: float | None, slow: float | None) -> str:
    if not fast or not slow:
        return "数据不足"
    tunnel_high = max(fast, slow)
    tunnel_low = min(fast, slow)
    if current_price > tunnel_high:
        return "站上 Vegas 通道"
    if current_price < tunnel_low:
        return "跌破 Vegas 通道"
    return "处于 Vegas 通道内"


def market_cycle(current_price: float, ma_50: float | None, ma_100: float | None, ma_200: float | None) -> str:
    if not ma_50 or not ma_100 or not ma_200:
        return "数据不足"
    if current_price > ma_50 > ma_100 > ma_200:
        return "多头扩张期"
    if current_price < ma_50 < ma_100 < ma_200:
        return "空头下行期"
    if current_price > ma_200 and ma_50 > ma_200:
        return "震荡偏多期"
    if current_price < ma_200 and ma_50 < ma_200:
        return "震荡偏空期"
    return "盘整观察期"


def volume_price_relation(prices: list[float], volumes: list[float]) -> str:
    if len(prices) < 8 or len(volumes) < 30:
        return "数据不足"
    price_change = (prices[-1] - prices[-8]) / prices[-8] * 100
    recent_volume = mean(volumes[-7:])
    base_volume = mean(volumes[-30:])
    volume_ratio = recent_volume / base_volume if base_volume else 0
    if price_change > 0 and volume_ratio >= 1.15:
        return "放量上涨"
    if price_change > 0 and volume_ratio < 0.9:
        return "缩量上涨"
    if price_change < 0 and volume_ratio >= 1.15:
        return "放量下跌"
    if price_change < 0 and volume_ratio < 0.9:
        return "缩量下跌"
    return "量价中性"
