"""Real market data via yfinance / MetaApi with synthetic fallback."""

import logging
import math
import random
from datetime import datetime, timedelta
from typing import Any

from tbot.models.config import settings

logger = logging.getLogger(__name__)

YFINANCE_AVAILABLE = False
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    logger.warning("yfinance not installed — using synthetic data")

YFINANCE_TICKERS = {"EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X"}


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


BASE_PRICES = {"EUR/USD": 1.0800, "GBP/USD": 1.2500}
TREND = {
    "EUR/USD": {"weekly": 0.0002, "daily": 0.00015, "4h": 0.0001},
    "GBP/USD": {"weekly": -0.0001, "daily": -0.00008, "4h": -0.00005},
}


def _fetch_from_yfinance(pair: str, timeframe: str, bars: int) -> list[dict[str, Any]] | None:
    if not YFINANCE_AVAILABLE:
        return None
    ticker_str = YFINANCE_TICKERS.get(pair)
    if not ticker_str:
        logger.warning("No yfinance ticker for %s", pair)
        return None
    try:
        ticker = yf.Ticker(ticker_str)
        interval_map = {
            "weekly": "1wk",
            "daily": "1d",
            "4h": "1h",
        }
        interval = interval_map.get(timeframe, "1d")
        period = "2y" if timeframe == "weekly" else "6mo" if timeframe == "daily" else "60d"
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            logger.warning("yfinance returned empty DataFrame for %s (%s)", pair, timeframe)
            return None

        series: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            series.append({
                "timestamp": ts,
                "open": round(float(row["Open"]), 5),
                "high": round(float(row["High"]), 5),
                "low": round(float(row["Low"]), 5),
                "close": round(float(row["Close"]), 5),
                "volume": int(row["Volume"]) if "Volume" in row else 0,
            })

        if timeframe == "4h" and series:
            series = _resample_to_4h(series)

        if len(series) < 10:
            logger.warning("Too few %s bars from yfinance for %s (%d)", timeframe, pair, len(series))
            return None

        series = series[-bars:]
        logger.info("Fetched %d %s bars for %s via yfinance", len(series), timeframe, pair)
        return series
    except Exception as exc:
        logger.warning("yfinance fetch failed for %s (%s): %s", pair, timeframe, exc)
        return None


def _resample_to_4h(hourly_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not hourly_series:
        return []
    grouped: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = [hourly_series[0]]
    for bar in hourly_series[1:]:
        if len(current_group) >= 4:
            grouped.append(current_group)
            current_group = [bar]
        else:
            current_group.append(bar)
    if current_group:
        grouped.append(current_group)

    result: list[dict[str, Any]] = []
    for group in grouped:
        if not group:
            continue
        result.append({
            "timestamp": group[0]["timestamp"],
            "open": group[0]["open"],
            "high": max(b["high"] for b in group),
            "low": min(b["low"] for b in group),
            "close": group[-1]["close"],
            "volume": sum(b.get("volume", 0) for b in group),
        })
    return result


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


def compute_indicators(series: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [c["close"] for c in series]

    ma20 = _sma(closes, min(20, len(closes)))
    ma50 = _sma(closes, min(50, len(closes)))

    macd_line = _ema(closes, 12) if len(closes) >= 12 else []
    ema26 = _ema(closes, 26) if len(closes) >= 26 else []
    macd = [m - e for m, e in zip(macd_line, ema26)] if macd_line and ema26 else []
    signal_line = _ema(macd, 9) if len(macd) >= 9 else []
    histogram = [m - s for m, s in zip(macd, signal_line)] if signal_line else []

    highs = [c["high"] for c in series]
    lows = [c["low"] for c in series]

    atr = _compute_atr(series, 14)

    return {
        "close": closes[-1] if closes else 0,
        "ma20": ma20[-1] if len(ma20) > 0 and not (isinstance(ma20[-1], float) and math.isnan(ma20[-1])) else closes[-1] if closes else 0,
        "ma50": ma50[-1] if len(ma50) > 0 and not (isinstance(ma50[-1], float) and math.isnan(ma50[-1])) else closes[-1] if closes else 0,
        "macd_line": macd[-1] if macd else 0,
        "signal_line": signal_line[-1] if signal_line else 0,
        "histogram": histogram[-1] if histogram else 0,
        "high": max(highs) if highs else 0,
        "low": min(lows) if lows else 0,
        "atr": atr,
        "support_resistance": _find_support_resistance(closes),
    }


def _compute_atr(series: list[dict[str, Any]], period: int = 14) -> float:
    if len(series) < period + 1:
        return 0.0
    tr_values: list[float] = []
    for i in range(1, len(series)):
        high = series[i]["high"]
        low = series[i]["low"]
        prev_close = series[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    if not tr_values:
        return 0.0
    return sum(tr_values[-period:]) / period


def _find_support_resistance(prices: list[float], num_levels: int = 3) -> list[float]:
    if len(prices) < 20:
        return [min(prices), max(prices)]
    levels: list[float] = []
    step = len(prices) // num_levels
    for i in range(num_levels):
        segment = prices[i * step : (i + 1) * step]
        levels.append(min(segment))
        levels.append(max(segment))
    return sorted(set(round(level, 5) for level in levels))[-num_levels * 2 :]


class MarketDataProvider:
    _cache: dict[str, list[dict[str, Any]]] = {}
    _metaapi_provider: Any = None
    _metaapi_tried = False

    @staticmethod
    def _get_metaapi():
        if not MarketDataProvider._metaapi_tried:
            MarketDataProvider._metaapi_tried = True
            if settings.data_provider in ("auto", "metaapi") and settings.meta_api_token:
                try:
                    from tbot.tools.metaapi_provider import MetaApiMarketDataProvider
                    MarketDataProvider._metaapi_provider = MetaApiMarketDataProvider()
                except Exception as exc:
                    logger.debug("MetaApi provider init failed: %s", exc)
        return MarketDataProvider._metaapi_provider

    def get_ohlcv(
        self, pair: str, timeframe: str, bars: int = 200
    ) -> list[dict[str, Any]]:
        key = f"{pair}_{timeframe}"
        if key in self._cache:
            return self._cache[key]

        metaapi = self._get_metaapi()
        if metaapi and settings.data_provider in ("auto", "metaapi"):
            try:
                import asyncio
                data = asyncio.run(metaapi.get_ohlcv(pair, timeframe, bars))
                if data and len(data) > 10:
                    self._cache[key] = data
                    logger.info("Fetched %d %s bars for %s via MetaApi", len(data), timeframe, pair)
                    return data
            except Exception as exc:
                logger.debug("MetaApi data fetch failed: %s", exc)

        real_data = _fetch_from_yfinance(pair, timeframe, bars)
        if real_data:
            self._cache[key] = real_data
            return real_data

        base_price = BASE_PRICES.get(pair, 1.10)
        trends = TREND.get(pair, {"weekly": 0.0, "daily": 0.0, "4h": 0.0})

        if timeframe == "weekly":
            series = _make_price_series(bars, base_price, trend=trends["weekly"], volatility=0.012)
        elif timeframe == "daily":
            series = _make_price_series(bars, base_price, trend=trends["daily"], volatility=0.008)
        else:
            series = _make_price_series(bars, base_price, trend=trends["4h"], volatility=0.006)

        self._cache[key] = series
        logger.info("Generated %d synthetic %s bars for %s", len(series), timeframe, pair)
        return series

    def clear_cache(self) -> None:
        self._cache.clear()

    def current_price(self, pair: str) -> float | None:
        metaapi = self._get_metaapi()
        if metaapi and settings.data_provider in ("auto", "metaapi"):
            try:
                import asyncio
                p = asyncio.run(metaapi.current_price(pair))
                if p is not None:
                    return p
            except Exception:
                pass

        if not YFINANCE_AVAILABLE:
            base = BASE_PRICES.get(pair, 1.10)
            jitter = random.uniform(-0.005, 0.005)
            return round(base + jitter, 5)
        ticker_str = YFINANCE_TICKERS.get(pair)
        if not ticker_str:
            return None
        try:
            import yfinance as yf
            ticker = yf.Ticker(ticker_str)
            df = ticker.history(period="1d", interval="1m")
            if df.empty:
                return None
            return round(float(df["Close"].iloc[-1]), 5)
        except Exception:
            return None

    def current_prices(self, pairs: list[str] | None = None) -> dict[str, float | None]:
        if pairs is None:
            pairs = list(YFINANCE_TICKERS.keys()) if YFINANCE_TICKERS else ["EUR/USD", "GBP/USD"]
        result: dict[str, float | None] = {}
        for pair in pairs:
            result[pair] = self.current_price(pair)
        return result
