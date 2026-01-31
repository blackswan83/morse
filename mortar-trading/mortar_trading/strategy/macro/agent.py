"""
Macro Strategy Agent
====================

Daily/4H directional bias from sentiment and on-chain data.

The Macro layer determines:
- Overall market direction (bullish/bearish/neutral)
- Maximum allocation percentage
- Key levels to watch

Never trade against the Macro direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import structlog

from mortar_trading.config import Settings, Direction, Confidence
from mortar_trading.core.events import Event, EventType, get_event_bus

logger = structlog.get_logger(__name__)


@dataclass
class MacroSignal:
    """Macro layer signal output."""

    symbol: str
    direction: Direction
    confidence: Confidence
    max_allocation: float  # 0.0 to 1.0
    sentiment_score: float  # -1 to 1
    trend_score: float  # -1 to 1
    key_levels: dict[str, float]
    reasoning: str
    timestamp: datetime


class MacroAgent:
    """
    Macro strategy agent for directional bias.

    Analyzes:
    - Sentiment data (social, news)
    - On-chain metrics (if available)
    - Macro market structure
    - Master input override

    Outputs:
    - Direction bias for lower layers
    - Maximum allocation allowed
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()

        # Current state
        self._current_signals: dict[str, MacroSignal] = {}
        self._sentiment_data: dict[str, dict] = {}
        self._master_override: dict[str, Any] | None = None

        # Thresholds
        self._sentiment_threshold = 1.5  # Z-score for strong signal
        self._trend_threshold = 0.6  # Trend score for trending

    async def start(self) -> None:
        """Start the macro agent."""
        logger.info("Starting Macro agent")

    async def stop(self) -> None:
        """Stop the macro agent."""
        logger.info("Stopping Macro agent")

    def set_master_override(self, override: dict[str, Any]) -> None:
        """
        Set master input override.

        Master input takes precedence over automated signals.
        """
        self._master_override = override
        logger.info("Master override set", override=override)

    async def process_sentiment(self, sentiment_data: dict[str, Any]) -> None:
        """
        Process incoming sentiment data.

        Args:
            sentiment_data: Sentiment update from engine
        """
        symbol = sentiment_data.get("symbol")
        if not symbol:
            return

        self._sentiment_data[symbol] = sentiment_data

        # Generate signal
        signal = await self._generate_signal(symbol)
        if signal:
            self._current_signals[symbol] = signal

            # Publish macro signal
            await self.event_bus.publish(
                Event(
                    event_type=EventType.MACRO_SIGNAL,
                    payload={
                        "symbol": symbol,
                        "direction": signal.direction.value,
                        "confidence": signal.confidence.value,
                        "max_allocation": signal.max_allocation,
                        "sentiment_score": signal.sentiment_score,
                        "trend_score": signal.trend_score,
                        "key_levels": signal.key_levels,
                        "reasoning": signal.reasoning,
                        "timestamp": signal.timestamp.isoformat(),
                    },
                    symbol=symbol,
                    source="macro_agent",
                )
            )

    async def _generate_signal(self, symbol: str) -> MacroSignal | None:
        """Generate macro signal for a symbol."""
        sentiment = self._sentiment_data.get(symbol, {})

        if not sentiment:
            return None

        # Extract sentiment features
        features = sentiment.get("features", {})
        signal_data = sentiment.get("signal", {})

        sentiment_score = signal_data.get("zscore", 0)
        momentum = signal_data.get("momentum", 0)

        # Check for master override
        if self._master_override:
            return self._apply_master_override(symbol, sentiment_score)

        # Determine direction
        direction, confidence = self._determine_direction(sentiment_score, momentum)

        # Calculate allocation
        max_allocation = self._calculate_allocation(confidence, abs(sentiment_score))

        # Calculate trend score (simplified - would use price data in practice)
        trend_score = np.tanh(sentiment_score / 2)  # Normalize to -1,1

        # Identify key levels (placeholder - would use price analysis)
        key_levels = self._identify_key_levels(symbol)

        # Generate reasoning
        reasoning = self._generate_reasoning(direction, sentiment_score, momentum)

        return MacroSignal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            max_allocation=max_allocation,
            sentiment_score=sentiment_score,
            trend_score=trend_score,
            key_levels=key_levels,
            reasoning=reasoning,
            timestamp=datetime.utcnow(),
        )

    def _determine_direction(
        self,
        sentiment_score: float,
        momentum: float,
    ) -> tuple[Direction, Confidence]:
        """Determine direction and confidence from scores."""
        # Strong signals
        if sentiment_score > self._sentiment_threshold and momentum > 0:
            if sentiment_score > 2.5:
                return Direction.STRONG_BULL, Confidence.HIGH
            return Direction.BULL, Confidence.HIGH

        if sentiment_score < -self._sentiment_threshold and momentum < 0:
            if sentiment_score < -2.5:
                return Direction.STRONG_BEAR, Confidence.HIGH
            return Direction.BEAR, Confidence.HIGH

        # Moderate signals
        if sentiment_score > 0.5:
            return Direction.BULL, Confidence.MEDIUM
        if sentiment_score < -0.5:
            return Direction.BEAR, Confidence.MEDIUM

        # Weak/conflicting signals
        if abs(sentiment_score) > 0.2:
            direction = Direction.BULL if sentiment_score > 0 else Direction.BEAR
            return direction, Confidence.LOW

        return Direction.NEUTRAL, Confidence.MEDIUM

    def _calculate_allocation(
        self,
        confidence: Confidence,
        signal_strength: float,
    ) -> float:
        """Calculate maximum allocation based on confidence."""
        adjustments = self.settings.master_input.adjustments

        base_allocation = {
            Confidence.HIGH: adjustments.high_confidence_max_allocation,
            Confidence.MEDIUM: 0.6,
            Confidence.LOW: adjustments.low_confidence_size_reduction,
        }

        allocation = base_allocation.get(confidence, 0.5)

        # Scale by signal strength
        strength_factor = min(signal_strength / 3, 1)  # Cap at 1
        allocation *= (0.5 + 0.5 * strength_factor)  # 50% base + 50% from strength

        return min(allocation, 0.8)  # Never exceed 80%

    def _identify_key_levels(self, symbol: str) -> dict[str, float]:
        """Identify key support and resistance levels."""
        # This would use price data in practice
        # For now, return empty dict
        return {
            "support": 0,
            "resistance": 0,
        }

    def _generate_reasoning(
        self,
        direction: Direction,
        sentiment_score: float,
        momentum: float,
    ) -> str:
        """Generate human-readable reasoning for the signal."""
        parts = []

        if abs(sentiment_score) > self._sentiment_threshold:
            parts.append(f"Strong sentiment signal (z={sentiment_score:.2f})")
        elif abs(sentiment_score) > 0.5:
            parts.append(f"Moderate sentiment (z={sentiment_score:.2f})")
        else:
            parts.append(f"Weak sentiment (z={sentiment_score:.2f})")

        if momentum > 0.1:
            parts.append("positive momentum")
        elif momentum < -0.1:
            parts.append("negative momentum")
        else:
            parts.append("no clear momentum")

        direction_text = {
            Direction.STRONG_BULL: "strongly bullish",
            Direction.BULL: "bullish",
            Direction.NEUTRAL: "neutral",
            Direction.BEAR: "bearish",
            Direction.STRONG_BEAR: "strongly bearish",
        }

        return f"{direction_text.get(direction, 'neutral').capitalize()}: {', '.join(parts)}"

    def _apply_master_override(
        self,
        symbol: str,
        sentiment_score: float,
    ) -> MacroSignal:
        """Apply master input override."""
        override = self._master_override

        direction = Direction(override.get("direction", "neutral"))
        confidence = Confidence(override.get("confidence", "medium"))

        # Allocation from override or calculate
        if confidence == Confidence.HIGH:
            max_allocation = self.settings.master_input.adjustments.high_confidence_max_allocation
        elif confidence == Confidence.LOW:
            max_allocation = self.settings.master_input.adjustments.low_confidence_size_reduction
        else:
            max_allocation = 0.6

        return MacroSignal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            max_allocation=max_allocation,
            sentiment_score=sentiment_score,
            trend_score=0,
            key_levels=override.get("key_levels", {}),
            reasoning=f"Master override: {direction.value} with {confidence.value} confidence",
            timestamp=datetime.utcnow(),
        )

    def get_current_signal(self, symbol: str) -> MacroSignal | None:
        """Get current macro signal for a symbol."""
        return self._current_signals.get(symbol)

    def get_direction_constraint(self, symbol: str) -> tuple[int, float]:
        """
        Get direction constraint for lower layers.

        Returns:
            (direction, max_allocation)
            direction: -1 (short only), 0 (both), 1 (long only)
        """
        signal = self._current_signals.get(symbol)
        if not signal:
            return 0, 0.5  # Neutral, medium allocation

        direction_map = {
            Direction.STRONG_BULL: 1,
            Direction.BULL: 1,
            Direction.NEUTRAL: 0,
            Direction.BEAR: -1,
            Direction.STRONG_BEAR: -1,
        }

        return direction_map.get(signal.direction, 0), signal.max_allocation
