"""MetaApi live broker — executes trades via MetaTrader accounts through MetaApi."""

import logging
import uuid
from datetime import datetime
from typing import Any

from tbot.models.config import settings
from tbot.models.schemas import OrderStatus, Position
from tbot.tools.positioning import compute_reward_amount

logger = logging.getLogger(__name__)


class MetaApiBroker:
    """Places real trades through a MetaTrader account connected to MetaApi."""

    SYMBOL_MAP = {"EUR/USD": "EURUSD", "GBP/USD": "GBPUSD"}

    def __init__(self) -> None:
        self._connection: Any = None
        self._ready = False

    async def _ensure(self) -> bool:
        if self._ready:
            return True
        if not settings.meta_api_token:
            logger.warning("META_API_TOKEN not configured — MetaApi broker unavailable")
            return False
        try:
            from tbot.tools.metaapi_provider import MetaApiConnection
            self._connection = MetaApiConnection()
            self._ready = await self._connection.ensure_connected()
            return self._ready
        except Exception as exc:
            logger.warning("MetaApi broker init failed: %s", exc)
            return False

    async def place_order(self, position: Position) -> Position:
        if not await self._ensure():
            logger.info("MetaApi broker unavailable — using paper fill fallback")
            return self._paper_fill(position)

        symbol = self.SYMBOL_MAP.get(position.signal.pair, position.signal.pair.replace("/", ""))
        volume = position.lot_size
        sl = position.stop_loss
        tp = position.take_profit
        order_type = position.signal.direction.value

        try:
            result = await self._connection.place_market_order(
                symbol=symbol,
                order_type=order_type,
                volume=volume,
                stop_loss=sl,
                take_profit=tp,
            )

            if result.get("error"):
                logger.warning("MetaApi order rejected: %s", result["error"])
                return self._paper_fill(position)

            filled = position.model_copy(deep=True)
            filled.order_id = result.get("order_id", f"ORD-{uuid.uuid4().hex[:8].upper()}")
            filled.status = OrderStatus.OPEN
            filled.entry_price = result.get("price", position.entry_price)
            filled.created_at = datetime.now()
            logger.info(
                "MetaApi trade executed: %s %s %.2f lot @ %.5f (order=%s)",
                symbol, order_type, volume, filled.entry_price, filled.order_id,
            )
            return filled

        except Exception as exc:
            logger.error("MetaApi place_order error: %s", exc)
            return self._paper_fill(position)

    async def close_order(self, order_id: str, exit_price: float | None = None) -> Position | None:
        if not await self._ensure():
            return None
        try:
            ok = await self._connection.close_position(order_id)
            if ok:
                logger.info("MetaApi position %s closed", order_id)
            return None
        except Exception as exc:
            logger.error("MetaApi close_order error: %s", exc)
            return None

    async def get_account_balance(self) -> float:
        if not await self._ensure():
            return settings.account_balance
        try:
            summary = await self._connection.get_account_summary()
            return float(summary.get("balance", settings.account_balance))
        except Exception:
            return settings.account_balance

    def _paper_fill(self, position: Position) -> Position:
        slippage = 0.0001
        filled = position.model_copy(deep=True)
        filled.order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        filled.status = OrderStatus.OPEN
        filled.execution_slippage = slippage
        filled.reward_amount = compute_reward_amount(
            filled.entry_price, filled.take_profit, filled.lot_size
        )
        filled.created_at = datetime.now()
        logger.info(
            "Paper-filled: %s %s %.2f lot @ %.5f",
            filled.signal.pair, filled.signal.direction.value,
            filled.lot_size, filled.entry_price,
        )
        return filled
