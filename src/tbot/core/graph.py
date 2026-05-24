import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from tbot.agents.analyst import AnalystAgent
from tbot.agents.critic import CriticAgent
from tbot.agents.executor import ExecutorAgent
from tbot.core.state import AgentState
from tbot.memory.store import TradeMemory
from tbot.models.schemas import Outcome, TradeResult

logger = logging.getLogger(__name__)


def _build_state(pair: str) -> dict[str, Any]:
    return {
        "messages": [],
        "pair": pair,
        "signal": None,
        "position": None,
        "trade_result": None,
        "lesson": None,
        "iteration": 0,
        "error": None,
    }


class AgentGraph:
    def __init__(self) -> None:
        self.analyst = AnalystAgent()
        self.executor = ExecutorAgent()
        self.critic = CriticAgent()
        self.memory = TradeMemory()
        self._graph = self._build()

    def _build(self) -> StateGraph:
        builder = StateGraph(AgentState)

        builder.add_node("analyst", self._analyst_node)
        builder.add_node("executor", self._executor_node)
        builder.add_node("critic", self._critic_node)
        builder.add_node("vetoed", self._vetoed_node)

        builder.set_entry_point("analyst")

        builder.add_conditional_edges(
            "analyst",
            self._route_after_analyst,
            {"executor": "executor", END: END},
        )

        builder.add_conditional_edges(
            "executor",
            self._route_after_executor,
            {"critic": "critic", "vetoed": "vetoed", END: END},
        )

        builder.add_edge("critic", END)
        builder.add_edge("vetoed", END)

        return builder.compile(checkpointer=MemorySaver())

    async def _analyst_node(self, state: AgentState) -> dict[str, Any]:
        pair = state.get("pair", "EUR/USD")
        logger.info("Agent A: Analyzing %s", pair)
        try:
            signal = await self.analyst.analyze(pair)
            if signal:
                logger.info(
                    "Agent A: Signal generated — %s %s at %.5f (conf: %.0f%%)",
                    pair, signal.direction.value, signal.entry_price, signal.confidence * 100,
                )
            else:
                logger.info("Agent A: No signal — timeframes not aligned")
            return {"signal": signal, "iteration": state.get("iteration", 0) + 1}
        except Exception as exc:
            logger.error("Agent A failed: %s", exc)
            return {"signal": None, "error": str(exc)}

    async def _executor_node(self, state: AgentState) -> dict[str, Any]:
        signal = state.get("signal")
        if signal is None:
            logger.warning("Agent B: No signal to execute")
            return {"error": "No signal"}

        logger.info("Agent B: Validating signal for %s", signal.pair)
        try:
            position = await self.executor.execute(signal)
            if position:
                logger.info(
                    "Agent B: Trade executed — %s lot, SL=%.5f, TP=%.5f, R:R=%.2f",
                    position.lot_size, position.stop_loss, position.take_profit,
                    position.risk_reward_ratio,
                )
                return {"position": position, "error": None}
            logger.info("Agent B: Trade vetoed — conditions not met")
            return {"error": "Trade vetoed", "position": None}
        except Exception as exc:
            logger.error("Agent B failed: %s", exc)
            return {"error": str(exc), "position": None}

    async def _critic_node(self, state: AgentState) -> dict[str, Any]:
        trade = state.get("trade_result")
        if trade is None:
            position = state.get("position")
            if position is None:
                logger.warning("Agent C: No trade to analyze")
                return {"error": "No trade result"}
            trade = self._simulate_trade_result(position)

        logger.info("Agent C: Analyzing %s %s (outcome: %s)",
                     trade.position.signal.pair, trade.position.signal.direction.value,
                     trade.outcome.value)
        try:
            lesson = await self.critic.analyze(trade)

            trade_id = self.memory.save_trade(trade)
            self.memory.save_lesson(lesson, trade_id)
            self.memory.append_to_finetuning_dataset(lesson)

            stored = self.memory.vector_store.add_lesson(lesson)
            logger.info("Agent C: Lesson stored (SQLite OK, ChromaDB=%s)", stored)
            return {
                "trade_result": trade,
                "lesson": lesson,
                "error": None,
            }
        except Exception as exc:
            logger.error("Agent C failed: %s", exc)
            return {"error": str(exc)}

    async def _vetoed_node(self, state: AgentState) -> dict[str, Any]:
        logger.info("Veto log: %s signal was vetoed by Agent B", state.get("pair"))
        return {"error": state.get("error", "Trade vetoed by risk checks")}

    @staticmethod
    def _route_after_analyst(state: AgentState) -> str:
        if state.get("signal") is not None and state.get("error") is None:
            return "executor"
        return END

    @staticmethod
    def _route_after_executor(state: AgentState) -> str:
        if state.get("error") and "vetoed" in str(state.get("error", "")).lower():
            return "vetoed"
        if state.get("position") is not None:
            trade = AgentGraph._simulate_trade_result(state["position"])
            state["trade_result"] = trade
            return "critic"
        return END

    @staticmethod
    def _simulate_trade_result(position) -> TradeResult:
        import random
        entry = position.entry_price
        sl = position.stop_loss
        tp = position.take_profit

        hit_tp = random.random() < 0.45
        if hit_tp:
            exit_price = tp + random.uniform(-0.0002, 0.0002)
            pnl_pips = abs(exit_price - entry) / 0.0001
            pnl = pnl_pips * position.lot_size * 100_000 * 0.0001
            outcome = Outcome.WIN
        else:
            exit_price = sl + random.uniform(-0.0002, 0.0002)
            pnl_pips = -abs(entry - exit_price) / 0.0001
            pnl = pnl_pips * position.lot_size * 100_000 * 0.0001
            outcome = Outcome.LOSS

        return TradeResult(
            position=position,
            exit_price=round(exit_price, 5),
            pnl=round(pnl, 2),
            pnl_pips=round(pnl_pips, 1),
            slippage=position.execution_slippage,
            holding_period_minutes=random.randint(30, 480),
            outcome=outcome,
        )

    async def run(self, pair: str) -> AgentState:
        state = _build_state(pair)
        config = {"configurable": {"thread_id": f"trade_{pair}_{hash(pair)}"}}
        result = await self._graph.ainvoke(state, config)
        return result
