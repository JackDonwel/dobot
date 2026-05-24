"""MetaApi integration — real MetaTrader market data and trade execution via metaapi-cloud-sdk."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from tbot.models.config import settings

logger = logging.getLogger(__name__)

METAAPI_AVAILABLE = False
try:
    from metaapi_cloud_sdk import MetaApi
    METAAPI_AVAILABLE = True
except ImportError:
    logger.info("metaapi-cloud-sdk not installed — MetaApi disabled")


class MetaApiConnection:
    """Wraps the MetaApi SDK for fetching market data and account info."""

    def __init__(self) -> None:
        self._api: Any = None
        self._account_client: Any = None
        self._account_info: Any = None
        self._ready = False
        self._error: str | None = None

    async def ensure_connected(self) -> bool:
        if self._ready:
            return True
        if not METAAPI_AVAILABLE:
            self._error = "metaapi-cloud-sdk not installed"
            return False
        if not settings.meta_api_token:
            self._error = "META_API_TOKEN not configured"
            return False

        try:
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context

            opts: dict[str, Any] = {}
            if settings.meta_api_domain:
                opts["domain"] = settings.meta_api_domain
            if settings.meta_api_region:
                opts["region"] = settings.meta_api_region

            self._api = MetaApi(token=settings.meta_api_token, opts=opts)
            accounts_api = self._api.metatrader_account_api

            if settings.meta_api_account_id:
                account = await accounts_api.get_account(settings.meta_api_account_id)
            else:
                accounts_page = await accounts_api.get_accounts_with_infinite_scroll_pagination()
                accs: list[Any] = []
                async for acc in accounts_page:
                    accs.append(acc)
                if not accs:
                    self._error = "No MetaTrader accounts found in MetaApi"
                    return False
                account = accs[0]

            if account.state != "DEPLOYED":
                logger.info("Deploying MetaTrader account %s...", account.id)
                await account.deploy()
                for _ in range(30):
                    await asyncio.sleep(2)
                    account = await accounts_api.get_account(account.id)
                    if account.state == "DEPLOYED":
                        break

            if account.connectionStatus != "CONNECTED":
                logger.info("Connecting MetaTrader account %s...", account.id)
                await account.connect()
                for _ in range(30):
                    await asyncio.sleep(2)
                    account = await accounts_api.get_account(account.id)
                    if account.connectionStatus == "CONNECTED":
                        break

            self._account_client = accounts_api.get_account(account.id)

            self._account_info = await self._account_client.get_account_information()
            logger.info(
                "MetaApi connected — account=%s balance=%.2f %s server=%s",
                account.id, self._account_info.balance, self._account_info.currency or "USD",
                account.server or "?",
            )

            self._ready = True
            return True

        except Exception as exc:
            err = str(exc)
            if "Unauthorized" in err:
                self._error = "MetaApi auth failed — check your token"
            else:
                self._error = f"MetaApi connection failed: {err[:120]}"
            logger.warning(self._error)
            return False

    async def get_historical_candles(
        self, symbol: str, timeframe: str, count: int = 100
    ) -> list[dict[str, Any]]:
        if not self._ready:
            return []
        try:
            tf_map = {"weekly": "1w", "daily": "1d", "4h": "1h"}
            interval = tf_map.get(timeframe, "1d")
            raw = await self._account_client.get_historical_candles(
                symbol, interval, count
            )
            series: list[dict[str, Any]] = []
            for c in raw:
                ts = c.time if hasattr(c, "time") else datetime.now()
                series.append({
                    "timestamp": ts,
                    "open": round(float(c.open), 5),
                    "high": round(float(c.high), 5),
                    "low": round(float(c.low), 5),
                    "close": round(float(c.close), 5),
                    "volume": int(getattr(c, "volume", 0) or 0),
                })
            if timeframe == "4h" and series:
                series = self._resample_4h(series)
            return series[-count:]
        except Exception as exc:
            logger.warning("Failed to fetch %s %s candles: %s", symbol, timeframe, exc)
            return []

    async def get_current_price(self, symbol: str) -> float | None:
        if not self._ready:
            return None
        try:
            candles = await self.get_historical_candles(symbol, "1h", 1)
            return candles[-1]["close"] if candles else None
        except Exception:
            return None

    async def get_account_summary(self) -> dict[str, Any]:
        if not self._ready:
            return {"error": self._error or "Not connected"}
        try:
            info = await self._account_client.get_account_information()
            positions = await self._account_client.get_positions()
            return {
                "balance": info.balance,
                "equity": info.equity,
                "margin": info.margin,
                "freeMargin": info.freeMargin,
                "currency": info.currency or "USD",
                "platform": info.platform,
                "open_positions": len(positions),
            }
        except Exception as exc:
            return {"error": str(exc)}

    async def place_market_order(
        self, symbol: str, order_type: str, volume: float,
        stop_loss: float | None = None, take_profit: float | None = None,
    ) -> dict[str, Any]:
        if not self._ready:
            return {"error": "MetaApi not connected"}
        try:
            buy = order_type.upper() == "BUY"
            if buy:
                result = await self._account_client.create_market_buy_order(
                    symbol, volume, stop_loss, take_profit
                )
            else:
                result = await self._account_client.create_market_sell_order(
                    symbol, volume, stop_loss, take_profit
                )
            return {
                "order_id": getattr(result, "orderId", str(result)),
                "price": getattr(result, "price", 0.0),
                "filled": True,
            } if result else {"error": "Order rejected"}
        except Exception as exc:
            return {"error": str(exc)}

    async def close_position(self, position_id: str) -> bool:
        if not self._ready:
            return False
        try:
            await self._account_client.close_position(position_id)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._api is not None:
            try:
                await self._api.close()
            except Exception:
                pass

    @staticmethod
    def _resample_4h(hourly: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not hourly:
            return []
        grouped: list[list[dict[str, Any]]] = []
        current = [hourly[0]]
        for bar in hourly[1:]:
            if len(current) >= 4:
                grouped.append(current)
                current = [bar]
            else:
                current.append(bar)
        if current:
            grouped.append(current)
        result = []
        for group in grouped:
            result.append({
                "timestamp": group[0]["timestamp"],
                "open": group[0]["open"],
                "high": max(b["high"] for b in group),
                "low": min(b["low"] for b in group),
                "close": group[-1]["close"],
                "volume": sum(b.get("volume", 0) for b in group),
            })
        return result


class MetaApiMarketDataProvider:
    """Adapter that provides OHLCV data matching the MarketDataProvider interface."""

    SYMBOL_MAP = {"EUR/USD": "EURUSD", "GBP/USD": "GBPUSD"}

    def __init__(self) -> None:
        self._conn = MetaApiConnection()
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._connected = False

    async def ensure(self) -> bool:
        if not self._connected:
            self._connected = await self._conn.ensure_connected()
        return self._connected

    async def get_ohlcv(self, pair: str, timeframe: str, bars: int = 200) -> list[dict[str, Any]]:
        key = f"{pair}_{timeframe}"
        if key in self._cache:
            return self._cache[key]

        if not await self.ensure():
            return []

        symbol = self.SYMBOL_MAP.get(pair, pair.replace("/", ""))
        data = await self._conn.get_historical_candles(symbol, timeframe, bars)
        if data:
            self._cache[key] = data
        return data

    async def current_price(self, pair: str) -> float | None:
        if not await self.ensure():
            return None
        symbol = self.SYMBOL_MAP.get(pair, pair.replace("/", ""))
        return await self._conn.get_current_price(symbol)

    async def current_prices(self, pairs: list[str] | None = None) -> dict[str, float | None]:
        if pairs is None:
            pairs = list(self.SYMBOL_MAP.keys())
        result: dict[str, float | None] = {}
        for pair in pairs:
            result[pair] = await self.current_price(pair)
        return result

    async def account_summary(self) -> dict[str, Any]:
        if not await self.ensure():
            return {"error": "Not connected"}
        return await self._conn.get_account_summary()

    async def close(self) -> None:
        await self._conn.close()
