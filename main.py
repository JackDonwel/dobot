import asyncio
import logging
from datetime import datetime

from models.config import settings
from core.graph import AgentGraph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tbot")


def _within_session() -> bool:
    now = datetime.now()
    start_h, start_m = map(int, settings.london_session_start.split(":"))
    end_h, end_m = map(int, settings.london_session_end.split(":"))
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    return start <= now <= end


def _session_summary(states: list[dict]) -> str:
    signals = sum(1 for s in states if s.get("signal"))
    positions = sum(1 for s in states if s.get("position"))
    lessons = sum(1 for s in states if s.get("lesson"))
    errors = sum(1 for s in states if s.get("error"))
    return (
        f"\n{'='*50}\n"
        f"  Session Complete — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"  Pairs analyzed: {len(states)}\n"
        f"  Signals generated: {signals}\n"
        f"  Trades executed: {positions}\n"
        f"  Lessons logged: {lessons}\n"
        f"  Errors/Rejections: {errors}\n"
        f"{'='*50}"
    )


async def run_session() -> None:
    graph = AgentGraph()
    states: list[dict] = []

    logger.info("London Session trading cycle started — analyzing %d pairs", len(settings.major_pairs))

    for pair in settings.major_pairs:
        logger.info("─" * 40)
        logger.info("Processing %s", pair)
        try:
            result = await graph.run(pair)
            states.append(result)

            if result.get("position"):
                pos = result["position"]
                logger.info(
                    ">>> TRADE OPEN: %s %s | Lot=%.2f | Entry=%.5f | SL=%.5f | TP=%.5f | R:R=%.2f",
                    pos.signal.pair,
                    pos.signal.direction.value,
                    pos.lot_size,
                    pos.entry_price,
                    pos.stop_loss,
                    pos.take_profit,
                    pos.risk_reward_ratio,
                )

            if result.get("lesson"):
                les = result["lesson"]
                logger.info(
                    ">>> LESSON: %s %s — %s | %s",
                    les.trade_result.position.signal.pair,
                    les.trade_result.position.signal.direction.value,
                    les.trade_result.outcome.value,
                    les.lesson_text[:120],
                )

            if result.get("error") and not result.get("position"):
                logger.info(">>> NO TRADE: %s — %s", pair, result["error"])

        except Exception as exc:
            logger.error("Fatal error processing %s: %s", pair, exc)
            states.append({"pair": pair, "error": str(exc)})

    logger.info(_session_summary(states))


async def run_once() -> None:
    pair = settings.major_pairs[0]
    logger.info("Running single analysis on %s", pair)
    graph = AgentGraph()
    result = await graph.run(pair)
    logger.info("Result: signal=%s, position=%s, lesson=%s, error=%s",
                "yes" if result.get("signal") else "no",
                "yes" if result.get("position") else "no",
                "yes" if result.get("lesson") else "no",
                result.get("error"))


async def scheduler_loop(interval_seconds: int = 300) -> None:
    logger.info("Scheduler started — checking every %d seconds for London Session", interval_seconds)
    while True:
        if _within_session():
            logger.info("London Session is active — running trading cycle")
            await run_session()
            logger.info("Cycle complete. Next check in %d seconds.", interval_seconds)
        else:
            logger.debug("Outside London Session — waiting")

        await asyncio.sleep(interval_seconds)
