import argparse
import asyncio
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

APP_DIR = Path(__file__).resolve().parent


def _ensure_data_dir() -> None:
    (APP_DIR.parent.parent / "data").mkdir(parents=True, exist_ok=True)


async def _cmd_run() -> None:
    from tbot.main import run_session
    await run_session()


async def _cmd_once(pair: str) -> None:
    from tbot.core.graph import AgentGraph
    graph = AgentGraph()
    result = await graph.run(pair)
    s = result.get("signal")
    p = result.get("position")
    t = result.get("trade_result")
    l_ = result.get("lesson")
    e = result.get("error")
    print()
    if s:
        print(f"Signal:      {s.direction.value} {s.pair} @ {s.entry_price:.5f}  (conf: {s.confidence:.0%})")
        print(f"  SL: {s.stop_loss:.5f}  TP: {s.take_profit:.5f}")
    else:
        print("Signal:      NONE")
    if p:
        print(f"Position:    {p.lot_size} lot  Risk=${p.risk_amount:.2f}  Reward=${p.reward_amount:.2f}  R:R={p.risk_reward_ratio}")
        print(f"Order ID:    {p.order_id}")
    if t:
        print(f"Trade:       {t.outcome.value}  PnL=${t.pnl:.2f}  Pips={t.pnl_pips:.1f}")
    if l_:
        print(f"Lesson:      {l_.lesson_text[:100]}...")
    if e:
        print(f"Error:       {e}")


async def _cmd_watch(interval: int) -> None:
    from tbot.main import scheduler_loop
    await scheduler_loop(interval_seconds=interval)


def _cmd_status() -> None:
    from tbot.memory.store import TradeMemory
    from tbot.models.config import settings
    mem = TradeMemory()
    trades = mem.get_recent_trades(5)
    vs_count = mem.vector_store.count_lessons()
    try:
        with open(APP_DIR.parent.parent / "data" / "lessons.jsonl") as f:
            ft_count = len(f.readlines())
    except FileNotFoundError:
        ft_count = 0
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    losses = sum(1 for t in trades if t["outcome"] == "LOSS")
    total = wins + losses
    print()
    print(f"  {'='*50}")
    print("  TBot System Status")
    print(f"  {'='*50}")
    print(f"  LLM Provider:  {settings.llm_provider}")
    print(f"  Account:       ${settings.account_balance:,.2f}")
    print(f"  Risk/Trade:    {settings.risk_per_trade:.0%}")
    print(f"  Min R:R:       1:{settings.min_reward_ratio:.0f}")
    print(f"  Session:       {settings.london_session_start} – {settings.london_session_end} EAT")
    print(f"  Pairs:         {', '.join(settings.major_pairs)}")
    print(f"  {'─'*50}")
    print(f"  Trades logged: {len(mem.get_recent_trades(999))}")
    if total > 0:
        print(f"  Win rate:      {wins}/{total} ({wins/total*100:.0f}%)")
    print(f"  Lessons (ChromaDB): {vs_count}")
    print(f"  Fine-tuning entries: {ft_count}")
    print(f"  {'='*50}")


def _cmd_dashboard(host: str, port: int) -> None:
    import uvicorn

    from tbot.web.app import app
    print(f"  TBot Dashboard → http://{host}:{port}")
    print("  Press Ctrl+C to stop")
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    _ensure_data_dir()
    parser = argparse.ArgumentParser(
        prog="tbot",
        description="TBot — Multi-Agent AI Trading System (London Session, Major Pairs)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Full London-session analysis of all major pairs")
    sub.add_parser("status", help="Show system state, trade stats, vector store size")

    once_p = sub.add_parser("once", help="Single pair analysis")
    once_p.add_argument("pair", nargs="?", default="EUR/USD", help="Pair to analyze (default: EUR/USD)")

    watch_p = sub.add_parser("watch", help="Continuous monitoring during session hours")
    watch_p.add_argument("interval", nargs="?", type=int, default=300, help="Check interval in seconds (default: 300)")

    dash_p = sub.add_parser("dashboard", help="Launch web dashboard UI")
    dash_p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    dash_p.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(_cmd_run())
    elif args.command == "once":
        asyncio.run(_cmd_once(args.pair))
    elif args.command == "watch":
        asyncio.run(_cmd_watch(args.interval))
    elif args.command == "status":
        _cmd_status()
    elif args.command == "dashboard":
        _cmd_dashboard(args.host, args.port)


if __name__ == "__main__":
    main()
