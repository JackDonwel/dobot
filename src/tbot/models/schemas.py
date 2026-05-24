from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class Outcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAK_EVEN = "BREAK_EVEN"


class TimeframeAnalysis(BaseModel):
    timeframe: str
    trend: str
    macd_status: str
    ma_alignment: str
    key_levels: list[float]
    assessment: str


class Signal(BaseModel):
    pair: str
    direction: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    entry_price: float
    stop_loss: float
    take_profit: float
    reasoning: str
    weekly: TimeframeAnalysis
    daily: TimeframeAnalysis
    h4: TimeframeAnalysis
    generated_at: datetime = Field(default_factory=datetime.now)


class Position(BaseModel):
    signal: Signal
    lot_size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = ""
    execution_slippage: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)


class TradeResult(BaseModel):
    position: Position
    exit_price: float
    pnl: float
    pnl_pips: float
    slippage: float
    holding_period_minutes: int
    outcome: Outcome
    closed_at: datetime = Field(default_factory=datetime.now)


class Lesson(BaseModel):
    trade_result: TradeResult
    market_context: str
    lesson_text: str
    behavioral_variance: str
    improvement_suggestion: str
    created_at: datetime = Field(default_factory=datetime.now)
