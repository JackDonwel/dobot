from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tbot.models.config import settings
from tbot.models.schemas import Lesson, TradeResult

if TYPE_CHECKING:
    from tbot.memory.chroma_store import ChromaStore


class TradeMemory:
    def __init__(self) -> None:
        self.db_path = Path(settings.trade_log_db)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._vector_store: ChromaStore | None = None

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE,
                    pair TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    lot_size REAL NOT NULL,
                    risk_amount REAL NOT NULL,
                    reward_amount REAL NOT NULL,
                    pnl REAL,
                    pnl_pips REAL,
                    slippage REAL DEFAULT 0.0,
                    outcome TEXT,
                    holding_period_minutes INTEGER,
                    reasoning TEXT,
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER,
                    lesson_text TEXT NOT NULL,
                    behavioral_variance TEXT,
                    improvement_suggestion TEXT,
                    market_context TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (trade_id) REFERENCES trades(id)
                )
            """)

    def save_trade(self, trade: TradeResult) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                """INSERT INTO trades
                   (order_id, pair, direction, entry_price, exit_price,
                    stop_loss, take_profit, lot_size, risk_amount, reward_amount,
                    pnl, pnl_pips, slippage, outcome, holding_period_minutes,
                    reasoning, created_at, closed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade.position.order_id,
                    trade.position.signal.pair,
                    trade.position.signal.direction.value,
                    trade.position.entry_price,
                    trade.exit_price,
                    trade.position.stop_loss,
                    trade.position.take_profit,
                    trade.position.lot_size,
                    trade.position.risk_amount,
                    trade.position.reward_amount,
                    round(trade.pnl, 2),
                    round(trade.pnl_pips, 1),
                    round(trade.slippage, 5),
                    trade.outcome.value,
                    trade.holding_period_minutes,
                    trade.position.signal.reasoning,
                    trade.position.created_at.isoformat(),
                    trade.closed_at.isoformat(),
                ),
            )
            return cur.lastrowid or 0

    def save_lesson(self, lesson: Lesson, trade_db_id: int) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO lessons
                   (trade_id, lesson_text, behavioral_variance,
                    improvement_suggestion, market_context, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    trade_db_id,
                    lesson.lesson_text,
                    lesson.behavioral_variance,
                    lesson.improvement_suggestion,
                    lesson.market_context,
                    lesson.created_at.isoformat(),
                ),
            )

    def get_recent_trades(self, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_lessons(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM lessons ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def append_to_finetuning_dataset(self, lesson: Lesson) -> None:
        path = Path(settings.fine_tuning_dataset_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a forex trading critic. Analyze trades and produce lessons.",
                },
                {
                    "role": "user",
                    "content": f"Analyze this {lesson.trade_result.position.signal.pair} "
                    f"{lesson.trade_result.position.signal.direction.value} trade: "
                    f"PnL ${lesson.trade_result.pnl:.2f}, outcome: {lesson.trade_result.outcome.value}",
                },
                {"role": "assistant", "content": lesson.lesson_text},
            ]
        }
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    @property
    def vector_store(self) -> "ChromaStore":
        if self._vector_store is None:
            from tbot.memory.chroma_store import ChromaStore
            self._vector_store = ChromaStore()
        return self._vector_store
