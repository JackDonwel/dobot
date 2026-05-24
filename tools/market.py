import math
import random
from datetime import datetime, timedelta
from typing import Any

import numpy as np


def _make_price_series(
    days: int, start_price: float, trend: float = 0.0, volatility: float = 0.02
) -> list[dict[str, Any]]:
    prices: list[float] = []
    p = start_price
    for _ in range(days):
        p += p * (trend + random.gauss(0, volatility))
        p = max(p, start_price * 0.5)
        prices.append(p)

    series: list[dict[str, Any]] = []
    base = datetime.now() - timedelta(days=days)
    for i, close in enumerate(prices):
        daily_vol = close * volatility * 0.5
        o = close + random.uniform(-daily_vol, daily_vol)
        h = max(o, close) + abs(random.gauss(0, daily_vol * 0.5))
        l_ = min(o, close) - abs(random.gauss(0, daily_vol * 0.5))
        series.append({
            "timestamp": base + timedelta(days=i),
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l_, 5),
            "close": round(close, 5),
            "volume": random.randint(1000, 10000),
        })
    return series


def _sma(data: list[float], period: int) -> list[float]:
    result: list[float] = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(float("nan"))
        else:
            result.append(sum(data[i - period + 1 : i + 1]) / period)
    return result


def _ema(data: list[float], period: int) -> list[float]:
    result: list[float] = []
    multiplier = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            result.append(data[i])
        else:
            result.append((data[i] - result[-1]) * multiplier + result[-1])
    return result


def compute_indicators(
    series: list[dict[str, Any]],
) -> dict[str, Any]:
    closes = [c["close"] for c in series]

    ma20 = _sma(closes, min(20, len(closes)))
    ma50 = _sma(closes, min(50, len(closes)))

    macd_line = _ema(closes, 12) if len(closes) >= 12 else []
    ema26 = _ema(closes, 26) if len(closes) >= 26 else []
    macd = [m - e for m, e in zip(macd_line, ema26)] if macd_line and ema26 else []
    signal_line = _ema(macd, 9) if len(macd) >= 9 else []
    histogram = [m - s for m, s in zip(macd, signal_line)] if signal_line else []

    return {
        "close": closes[-1] if closes else 0,
        "ma20": ma20[-1] if len(ma20) > 0 and not (isinstance(ma20[-1], float) and math.isnan(ma20[-1])) else closes[-1] if closes else 0,
        "ma50": ma50[-1] if len(ma50) > 0 and not (isinstance(ma50[-1], float) and math.isnan(ma50[-1])) else closes[-1] if closes else 0,
        "macd_line": macd[-1] if macd else 0,
        "signal_line": signal_line[-1] if signal_line else 0,
        "histogram": histogram[-1] if histogram else 0,
        "high": max(c["high"] for c in series) if series else 0,
        "low": min(c["low"] for c in series) if series else 0,
        "support_resistance": _find_support_resistance(closes),
    }


def _find_support_resistance(prices: list[float], num_levels: int = 3) -> list[float]:
    if len(prices) < 20:
        return [min(prices), max(prices)]
    levels: list[float] = []
    step = len(prices) // num_levels
    for i in range(num_levels):
        segment = prices[i * step : (i + 1) * step]
        levels.append(min(segment))
        levels.append(max(segment))
    return sorted(set(round(l, 5) for l in levels))[-num_levels * 2 :]


BASE_PRICES = {"EUR/USD": 1.0800, "GBP/USD": 1.2500}
TREND = {"EUR/USD": {"weekly": 0.0002, "daily": 0.00015, "4h": 0.0001},
         "GBP/USD": {"weekly": -0.0001, "daily": -0.00008, "4h": -0.00005}}


class MarketDataProvider:
    _cache: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def get_ohlcv(
        self, pair: str, timeframe: str, bars: int = 200
    ) -> list[dict[str, Any]]:
        key = f"{pair}_{timeframe}"
        if key in self._cache:
            return self._cache[key]

        base_price = BASE_PRICES.get(pair, 1.10)
        trends = TREND.get(pair, {"weekly": 0.0, "daily": 0.0, "4h": 0.0})

        if timeframe == "weekly":
            series = _make_price_series(
                bars, base_price, trend=trends["weekly"], volatility=0.012
            )
        elif timeframe == "daily":
            series = _make_price_series(
                bars, base_price, trend=trends["daily"], volatility=0.008
            )
        else:
            series = _make_price_series(
                bars, base_price, trend=trends["4h"], volatility=0.006
            )

        self._cache[key] = series
        return series

    def clear_cache(self) -> None:
        self._cache.clear()
