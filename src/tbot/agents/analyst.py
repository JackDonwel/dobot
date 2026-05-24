from tbot.models.config import settings
from tbot.models.schemas import Direction, Signal, TimeframeAnalysis
from tbot.tools.llm import get_llm
from tbot.tools.market import MarketDataProvider, compute_indicators

_ANALYST_SYSTEM_PROMPT = "You are a forex analyst. Answer concisely in 1-3 words."


class AnalystAgent:
    def __init__(self, market: MarketDataProvider | None = None) -> None:
        self.market = market or MarketDataProvider()
        self._use_llm = settings.llm_provider != "mock"

    async def analyze(self, pair: str) -> Signal | None:
        weekly = self.market.get_ohlcv(pair, "weekly", bars=100)
        daily = self.market.get_ohlcv(pair, "daily", bars=100)
        h4 = self.market.get_ohlcv(pair, "4h", bars=200)

        wi = compute_indicators(weekly)
        di = compute_indicators(daily)
        hi = compute_indicators(h4)

        if self._use_llm:
            return await self._llm_analysis(pair, wi, di, hi)
        return self._rule_analysis(pair, wi, di, hi)

    def _rule_analysis(
        self,
        pair: str,
        weekly: dict,
        daily: dict,
        h4: dict,
    ) -> Signal | None:
        weekly_trend, weekly_strength = self._trend_assessment(weekly, "weekly")
        daily_trend, daily_strength = self._trend_assessment(daily, "daily")
        h4_trend, h4_strength = self._trend_assessment(h4, "4h")

        if weekly_trend is None or weekly_trend == "NEUTRAL":
            return None

        if daily_trend != weekly_trend:
            return None

        weekly_analysis = TimeframeAnalysis(
            timeframe="weekly",
            trend=weekly_trend,
            macd_status=self._macd_status(weekly),
            ma_alignment=self._ma_alignment(weekly),
            key_levels=weekly.get("support_resistance", []),
            assessment=f"Macro trend is {weekly_trend} with {weekly_strength} strength.",
        )

        daily_analysis = TimeframeAnalysis(
            timeframe="daily",
            trend=daily_trend,
            macd_status=self._macd_status(daily),
            ma_alignment=self._ma_alignment(daily),
            key_levels=daily.get("support_resistance", []),
            assessment=f"Daily aligns with {daily_trend} structure.",
        )

        h4_analysis = TimeframeAnalysis(
            timeframe="4h",
            trend=h4_trend,
            macd_status=self._macd_status(h4),
            ma_alignment=self._ma_alignment(h4),
            key_levels=h4.get("support_resistance", []),
            assessment=f"4H momentum confirms {h4_trend} entry.",
        )

        entry_zone = self._entry_zone(h4, weekly, daily, weekly_trend)
        if entry_zone is None:
            return None

        direction = Direction.BUY if weekly_trend == "BULLISH" else Direction.SELL
        entry_price = entry_zone["entry"]
        stop_loss = entry_zone["sl"]
        take_profit = entry_zone["tp"]

        confidence = round(
            (weekly_strength + daily_strength + h4_strength) / 3.0, 2
        )

        return Signal(
            pair=pair,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=(
                f"Weekly: {weekly_trend}. Daily: aligned. 4H: momentum confirms. "
                f"Confidence: {confidence:.0%}."
            ),
            weekly=weekly_analysis,
            daily=daily_analysis,
            h4=h4_analysis,
        )

    async def _llm_analysis(
        self, pair: str, weekly: dict, daily: dict, h4: dict
    ) -> Signal | None:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm(temperature=0.1)

        trend_question = (
            f"{pair} W:ma20={weekly.get('ma20'):.4f} ma50={weekly.get('ma50'):.4f} "
            f"D:ma20={daily.get('ma20'):.4f} ma50={daily.get('ma50'):.4f} "
            f"4H:ma20={h4.get('ma20'):.4f} ma50={h4.get('ma50'):.4f}. "
            "Trend? bullish/bearish/neutral"
        )
        try:
            resp = await llm.ainvoke([
                SystemMessage(content=_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=trend_question),
            ])
            answer = resp.content.strip().lower()

            if "bullish" in answer:
                direction = Direction.BUY
                weekly_trend = "BULLISH"
            elif "bearish" in answer:
                direction = Direction.SELL
                weekly_trend = "BEARISH"
            else:
                return self._rule_analysis(pair, weekly, daily, h4)

            conf_resp = await llm.ainvoke([
                SystemMessage(content=_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=f"{pair} trend conviction? answer 0-100"),
            ])
            conf_text = conf_resp.content.strip()
            import re
            nums = re.findall(r"\d+", conf_text)
            confidence = min(0.9, max(0.3, int(nums[0]) / 100)) if nums else 0.5

            entry_zone = self._entry_zone(h4, weekly, daily, weekly_trend)
            if not entry_zone:
                return self._rule_analysis(pair, weekly, daily, h4)

            return Signal(
                pair=pair,
                direction=direction,
                confidence=confidence,
                entry_price=entry_zone["entry"],
                stop_loss=entry_zone["sl"],
                take_profit=entry_zone["tp"],
                reasoning=f"LLM trend: {weekly_trend} (conf: {confidence:.0%})",
                weekly=TimeframeAnalysis(timeframe="weekly", trend=weekly_trend, macd_status="LLM", ma_alignment="LLM", key_levels=[], assessment=""),
                daily=TimeframeAnalysis(timeframe="daily", trend=weekly_trend, macd_status="LLM", ma_alignment="LLM", key_levels=[], assessment=""),
                h4=TimeframeAnalysis(timeframe="4h", trend=weekly_trend, macd_status="LLM", ma_alignment="LLM", key_levels=[], assessment=""),
            )
        except Exception:
            return self._rule_analysis(pair, weekly, daily, h4)

    @staticmethod
    def _trend_assessment(indicators: dict, label: str) -> tuple[str | None, float]:
        ma20 = indicators.get("ma20", 0)
        ma50 = indicators.get("ma50", 0)
        macd = indicators.get("macd_line", 0)
        signal = indicators.get("signal_line", 0)
        hist = indicators.get("histogram", 0)

        if ma20 <= 0 or ma50 <= 0:
            return None, 0.0

        if ma20 > ma50 and macd > signal and hist > 0:
            return "BULLISH", 0.85
        elif ma20 > ma50 and macd > signal:
            return "BULLISH", 0.65
        elif ma20 > ma50:
            return "BULLISH", 0.45
        elif ma20 < ma50 and macd < signal and hist < 0:
            return "BEARISH", 0.85
        elif ma20 < ma50 and macd < signal:
            return "BEARISH", 0.65
        elif ma20 < ma50:
            return "BEARISH", 0.45
        return "NEUTRAL", 0.2

    @staticmethod
    def _macd_status(indicators: dict) -> str:
        macd = indicators.get("macd_line", 0)
        signal = indicators.get("signal_line", 0)
        hist = indicators.get("histogram", 0)
        if macd > signal and hist > 0:
            return "BULLISH_MOMENTUM"
        elif macd > signal:
            return "BULLISH_CROSS"
        elif macd < signal and hist < 0:
            return "BEARISH_MOMENTUM"
        elif macd < signal:
            return "BEARISH_CROSS"
        return "NEUTRAL"

    @staticmethod
    def _ma_alignment(indicators: dict) -> str:
        ma20 = indicators.get("ma20", 0)
        ma50 = indicators.get("ma50", 0)
        if ma20 > ma50 * 1.002:
            return "BULLISH_ALIGNED"
        elif ma20 < ma50 * 0.998:
            return "BEARISH_ALIGNED"
        return "NEUTRAL"

    @staticmethod
    def _entry_zone(
        h4: dict, weekly: dict, daily: dict, trend: str
    ) -> dict | None:
        current = h4.get("close", 0)
        if current == 0:
            return None

        levels = h4.get("support_resistance", [])
        pip = 0.0001

        if trend == "BULLISH":
            nearby = [lev for lev in levels if lev < current and lev > current * 0.99]
            if nearby:
                sl = max(nearby)
            else:
                sl = current - 30 * pip
            risk = current - sl
            if risk <= 0:
                return None
            entry = current
            tp = current + risk * 4.0
        else:
            nearby = [lev for lev in levels if lev > current and lev < current * 1.01]
            if nearby:
                sl = min(nearby)
            else:
                sl = current + 30 * pip
            risk = sl - current
            if risk <= 0:
                return None
            entry = current
            tp = current - risk * 4.0

        return {"entry": round(entry, 5), "sl": round(sl, 5), "tp": round(tp, 5)}
