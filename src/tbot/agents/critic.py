
from tbot.models.config import settings
from tbot.models.schemas import Lesson, Outcome, TradeResult
from tbot.tools.llm import get_llm

_CRITIC_SYSTEM_PROMPT = """You analyze completed forex trades. Output JSON with: lesson_text, behavioral_variance, improvement_suggestion."""


class CriticAgent:
    def __init__(self) -> None:
        self._use_llm = settings.llm_provider != "mock"

    async def analyze(self, trade: TradeResult) -> Lesson | None:
        if self._use_llm:
            return await self._llm_analysis(trade)
        return self._rule_analysis(trade)

    def _rule_analysis(self, trade: TradeResult) -> Lesson:
        direction_label = trade.position.signal.direction.value
        pair = trade.position.signal.pair

        if trade.outcome == Outcome.WIN:
            lesson_text = (
                f"The {direction_label} trade on {pair} was successful. "
                f"Entry at {trade.position.entry_price}, exit at {trade.exit_price}. "
                f"PnL: ${trade.pnl:.2f} ({trade.pnl_pips:.1f} pips). "
                f"Direction aligned with macro trend and momentum confirmed on entry."
            )
            variance = (
                f"Slippage: {trade.slippage:.5f}. "
                f"Holding period: {trade.holding_period_minutes} min."
            )
            improvement = "Maintain current filter strictness. Consider partial exits at 2:1 R:R for high-volatility setups."
        elif trade.outcome == Outcome.LOSS:
            lesson_text = (
                f"The {direction_label} trade on {pair} was a loss. "
                f"Entered at {trade.position.entry_price}, stopped at {trade.exit_price}. "
                f"PnL: ${trade.pnl:.2f} ({trade.pnl_pips:.1f} pips). "
                f"The market structure may have shifted against the macro thesis."
            )
            variance = (
                f"Slippage: {trade.slippage:.5f}. "
                f"Stop loss was hit within {trade.holding_period_minutes} min."
            )
            improvement = "Add a volatility filter to avoid entries during low-liquidity periods. Consider wider stops during news days."
        else:
            lesson_text = (
                f"The {direction_label} trade on {pair} broke even. "
                f"Entry at {trade.position.entry_price}, exit at {trade.exit_price}."
            )
            variance = "Minimal variance from plan."
            improvement = "Review if tighter stops would improve R:R without reducing win rate."

        return Lesson(
            trade_result=trade,
            market_context=(
                f"Pair: {pair}, Direction: {direction_label}, "
                f"Entry: {trade.position.entry_price}, Exit: {trade.exit_price}, "
                f"Outcome: {trade.outcome.value}"
            ),
            lesson_text=lesson_text,
            behavioral_variance=variance,
            improvement_suggestion=improvement,
        )

    async def _llm_analysis(self, trade: TradeResult) -> Lesson:
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm(temperature=0.3)
        prompt = (
            f"Trade: {trade.position.signal.pair} {trade.position.signal.direction.value} "
            f"entry={trade.position.entry_price:.5f} exit={trade.exit_price:.5f} "
            f"SL={trade.position.stop_loss:.5f} TP={trade.position.take_profit:.5f} "
            f"PnL=${trade.pnl:.2f} ({trade.pnl_pips:.1f}pips) outcome={trade.outcome.value} "
            f"slippage={trade.slippage:.5f}\n"
            f"Return JSON: lesson_text, behavioral_variance, improvement_suggestion."
        )
        try:
            result = await llm.ainvoke([
                SystemMessage(content=_CRITIC_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            import re
            match = re.search(r"\{.*\}", result.content, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            lesson = Lesson(
                trade_result=trade,
                market_context=f"{trade.position.signal.pair} {trade.position.signal.direction.value} trade on {trade.closed_at.date()}",
                lesson_text=data.get("lesson_text", ""),
                behavioral_variance=data.get("behavioral_variance", ""),
                improvement_suggestion=data.get("improvement_suggestion", ""),
            )
            return lesson
        except Exception:
            return self._rule_analysis(trade)
