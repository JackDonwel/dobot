from typing import Annotated, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from tbot.models.schemas import Lesson, Position, Signal, TradeResult


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    pair: str
    signal: Optional[Signal]
    position: Optional[Position]
    trade_result: Optional[TradeResult]
    lesson: Optional[Lesson]
    iteration: int
    error: Optional[str]
