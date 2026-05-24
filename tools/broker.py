import random
import uuid
from datetime import datetime
from typing import Any

from models.config import settings
from models.schemas import Direction, OrderStatus, Position
from tools.positioning import compute_reward_amount


class MockBroker:
    def __init__(self) -> None:
        self.open_orders: dict[str, Position] = {}
        self.filled_orders: dict[str, Position] = {}
        self._slippage_model = SlippageModel()

    async def place_order(
        self,
        position: Position,
    ) -> Position:
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        slippage = self._slippage_model.simulate(position.entry_price)
        filled_price = self._apply_slippage(position.entry_price, position.signal.direction, slippage)

        filled = position.model_copy(deep=True)
        filled.order_id = order_id
        filled.status = OrderStatus.OPEN
        filled.entry_price = round(filled_price, 5)
        filled.execution_slippage = round(slippage, 5)
        filled.reward_amount = compute_reward_amount(
            filled_price, filled.take_profit, filled.lot_size
        )
        filled.created_at = datetime.now()

        self.open_orders[order_id] = filled
        return filled

    async def close_order(
        self, order_id: str, exit_price: float | None = None
    ) -> Position | None:
        pos = self.open_orders.pop(order_id, None)
        if pos is None:
            return None
        pos.status = OrderStatus.CLOSED
        self.filled_orders[order_id] = pos
        return pos

    async def check_position_status(
        self, order_id: str, current_price: float
    ) -> Position | None:
        pos = self.open_orders.get(order_id)
        if pos is None:
            return self.filled_orders.get(order_id)

        if pos.signal.direction == Direction.BUY:
            if current_price <= pos.stop_loss or current_price >= pos.take_profit:
                exit_price = current_price
                return await self.close_order(order_id, exit_price)
        else:
            if current_price >= pos.stop_loss or current_price <= pos.take_profit:
                exit_price = current_price
                return await self.close_order(order_id, exit_price)

        return pos

    async def get_account_balance(self) -> float:
        return settings.account_balance

    @staticmethod
    def _apply_slippage(
        price: float, direction: Direction, slippage: float
    ) -> float:
        if direction == Direction.BUY:
            return price + slippage
        return price - slippage


class SlippageModel:
    def __init__(self, base_slippage: float = 0.0001, volatility: float = 0.000_05) -> None:
        self.base_slippage = base_slippage
        self.volatility = volatility

    def simulate(self, price: float) -> float:
        return abs(random.gauss(self.base_slippage, self.volatility))
