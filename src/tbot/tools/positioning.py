
from tbot.models.config import settings
from tbot.models.schemas import Direction


def calculate_position_size(
    entry_price: float,
    stop_loss: float,
    account_balance: float | None = None,
    risk_percent: float | None = None,
    pair: str = "EUR/USD",
) -> dict[str, float]:
    balance = account_balance or settings.account_balance
    risk_pct = risk_percent or settings.risk_per_trade

    risk_amount = balance * risk_pct

    pip_value = 0.0001
    pip_distance = abs(entry_price - stop_loss) / pip_value

    if pip_distance == 0:
        return {"error": "Stop loss cannot equal entry price."}

    position_size_units = risk_amount / pip_distance
    lot_size = position_size_units / 100_000.0
    lot_size = round(lot_size, 2)

    if lot_size < 0.01:
        lot_size = 0.01

    actual_risk = lot_size * 100_000 * pip_distance * pip_value

    return {
        "lot_size": lot_size,
        "risk_amount": round(actual_risk, 2),
        "pip_distance": round(pip_distance, 1),
    }


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    direction: Direction,
    reward_ratio: float | None = None,
) -> float:
    ratio = reward_ratio or settings.min_reward_ratio
    risk = abs(entry_price - stop_loss)
    if direction == Direction.BUY:
        return entry_price + risk * ratio
    return entry_price - risk * ratio


def compute_reward_amount(
    entry_price: float,
    take_profit: float,
    lot_size: float,
    pair: str = "EUR/USD",
) -> float:
    pip_value = 0.0001
    pip_distance = abs(take_profit - entry_price) / pip_value
    return round(lot_size * 100_000 * pip_distance * pip_value, 2)
