import logging
from typing import Any

from tbot.models.config import settings
from tbot.models.schemas import Lesson

logger = logging.getLogger(__name__)


class ChromaStore:
    def __init__(self) -> None:
        self._collection = None
        self._client = None
        self._ready = False
        self._init()

    def _init(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            persist_dir = settings.chroma_persist_dir
            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="trade_lessons",
                metadata={"hnsw:space": "cosine"},
            )
            self._ready = True
            logger.info("ChromaDB initialized at %s", persist_dir)
        except Exception as exc:
            logger.warning("ChromaDB not available (%s). Lessons stored only in SQLite.", exc)

    def add_lesson(self, lesson: Lesson) -> bool:
        if not self._ready:
            return False

        try:
            doc_id = f"lesson_{lesson.trade_result.position.order_id}_{lesson.created_at.timestamp()}"
            self._collection.add(
                documents=[lesson.lesson_text],
                metadatas=[{
                    "pair": lesson.trade_result.position.signal.pair,
                    "direction": lesson.trade_result.position.signal.direction.value,
                    "outcome": lesson.trade_result.outcome.value,
                    "pnl": round(lesson.trade_result.pnl, 2),
                    "confidence": lesson.trade_result.position.signal.confidence,
                    "timestamp": lesson.created_at.isoformat(),
                }],
                ids=[doc_id],
            )
            return True
        except Exception as exc:
            logger.error("Failed to add lesson to ChromaDB: %s", exc)
            return False

    def query_similar_lessons(
        self, query: str, n_results: int = 5
    ) -> list[dict[str, Any]]:
        if not self._ready:
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
            )
            output: list[dict[str, Any]] = []
            if results["metadatas"] and results["documents"]:
                for meta, doc in zip(results["metadatas"][0], results["documents"][0]):
                    output.append({"metadata": meta, "lesson": doc})
            return output
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return []

    def count_lessons(self) -> int:
        if not self._ready:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0
