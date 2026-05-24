from datetime import datetime

from tbot.models.config import settings
from tbot.models.schemas import Position, Signal
from tbot.tools.broker import MockBroker
from tbot.tools.news import NewsFilter
from tbot.tools.positioning import (
    calculate_position_size,
    compute_reward_amount,
)


class ExecutorAgent:
    def __init__(
        self, broker: MockBroker | None = None, news_filter: NewsFilter | None = None
    ) -> None:
        self.broker = broker or MockBroker()
        self.news = news_filter or NewsFilter()

    async def execute(self, signal: Signal) -> Position | None:
        if not self._check_london_session():
            return None

        self.news.refresh()
        if self.news.is_blocked():
            return None

        if not self._verify_entry(signal):
            return None

        sizing = calculate_position_size(
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            pair=signal.pair,
        )
        if "error" in sizing:
            return None

        lot_size = sizing["lot_size"]
        risk_amount = sizing["risk_amount"]

        take_profit = signal.take_profit
        reward_amount = compute_reward_amount(
            signal.entry_price, take_profit, lot_size
        )
        rr_ratio = round(reward_amount / risk_amount, 2) if risk_amount > 0 else 0.0

        position = Position(
            signal=signal,
            lot_size=lot_size,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount,
            reward_amount=reward_amount,
            risk_reward_ratio=rr_ratio,
        )

        filled = await self.broker.place_order(position)
        return filled

    @staticmethod
    def _verify_entry(signal: Signal) -> bool:
        if signal.confidence < 0.3:
            return False

        risk = abs(signal.entry_price - signal.stop_loss)
        reward = abs(signal.take_profit - signal.entry_price)
        if risk > 0:
            rr_ratio = reward / risk
            if round(rr_ratio, 4) < settings.min_reward_ratio:
                return False

        return True

    @staticmethod
    def _check_london_session() -> bool:
        now = datetime.now()
        start_h, start_m = map(int, settings.london_session_start.split(":"))
        end_h, end_m = map(int, settings.london_session_end.split(":"))
        session_start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        session_end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        return session_start <= now <= session_end
