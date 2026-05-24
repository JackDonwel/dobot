from datetime import datetime, timedelta
from typing import Any


HIGH_IMPACT_EVENTS: list[dict[str, Any]] = [
    {"event": "Non-Farm Payrolls", "impact": "high", "day": "first_friday"},
    {"event": "FOMC Rate Decision", "impact": "high", "day": "second_wednesday"},
    {"event": "ECB Rate Decision", "impact": "high", "day": "third_thursday"},
    {"event": "BOE Rate Decision", "impact": "high", "day": "second_thursday"},
    {"event": "US CPI (YoY)", "impact": "high", "day": "second_tuesday"},
    {"event": "US GDP (QoQ)", "impact": "high", "day": "last_wednesday"},
    {"event": "UK CPI (YoY)", "impact": "high", "day": "third_wednesday"},
    {"event": "UK GDP (MoM)", "impact": "high", "day": "second_friday"},
    {"event": "EU CPI (YoY)", "impact": "high", "day": "last_tuesday"},
    {"event": "EU GDP (QoQ)", "impact": "high", "day": "second_tuesday"},
]


def _get_nth_weekday(year: int, month: int, weekday: int, nth: int) -> datetime:
    """nth weekday of month, e.g. first_friday → weekday=4, nth=1"""
    first = datetime(year, month, 1)
    count = 0
    for day in range(1, 32):
        try:
            d = datetime(year, month, day)
        except ValueError:
            break
        if d.weekday() == weekday:
            count += 1
            if count == nth:
                return d
    return first


_DAY_MAP = {
    "first_friday": (4, 1),
    "second_wednesday": (2, 2),
    "third_thursday": (3, 3),
    "second_thursday": (3, 2),
    "second_tuesday": (1, 2),
    "last_wednesday": (2, 5),
    "third_wednesday": (2, 3),
    "second_friday": (4, 2),
    "last_tuesday": (1, 5),
    "last_thursday": (3, 5),
}


def _resolve_event_date(event: dict[str, Any], now: datetime) -> datetime:
    day_key = event["day"]
    if day_key not in _DAY_MAP:
        return now + timedelta(days=1)
    weekday, nth = _DAY_MAP[day_key]
    dt = _get_nth_weekday(now.year, now.month, weekday, nth)
    if dt < now:
        next_month = now.month + 1
        next_year = now.year + (next_month - 1) // 12
        next_month = ((next_month - 1) % 12) + 1
        dt = _get_nth_weekday(next_year, next_month, weekday, nth)
    return dt.replace(hour=14, minute=0, second=0)


class NewsFilter:
    def __init__(self) -> None:
        self.upcoming: list[dict[str, Any]] = []

    def refresh(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now()
        events: list[dict[str, Any]] = []
        for ev in HIGH_IMPACT_EVENTS:
            event_date = _resolve_event_date(ev, now)
            events.append({
                "event": ev["event"],
                "impact": ev["impact"],
                "datetime": event_date,
                "pair_relevance": self._pair_relevance(ev["event"]),
            })
        events.sort(key=lambda e: e["datetime"])
        self.upcoming = events
        return events

    def is_blocked(self, now: datetime | None = None, buffer_minutes: int = 30) -> bool:
        now = now or datetime.now()
        if not self.upcoming:
            self.refresh(now)
        for ev in self.upcoming:
            ev_time = ev["datetime"]
            if abs((ev_time - now).total_seconds()) / 60 <= buffer_minutes:
                return True
        return False

    def next_event(self, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or datetime.now()
        upcoming = [e for e in self.upcoming if e["datetime"] > now]
        return upcoming[0] if upcoming else None

    @staticmethod
    def _pair_relevance(event_name: str) -> list[str]:
        name = event_name.lower()
        pairs: list[str] = []
        if "fomc" in name or "federal" in name or "us " in name or "nfp" in name or name.startswith("us "):
            pairs.extend(["EUR/USD", "GBP/USD"])
        if "ecb" in name or "eu " in name or "euro" in name:
            pairs.append("EUR/USD")
        if "boe" in name or "uk " in name or "british" in name:
            pairs.append("GBP/USD")
        return pairs if pairs else ["EUR/USD", "GBP/USD"]
