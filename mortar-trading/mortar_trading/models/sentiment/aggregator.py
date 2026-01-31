"""
Sentiment Aggregator
====================

Aggregates sentiment from multiple sources into trading signals.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SentimentDataPoint:
    """Single sentiment data point."""

    timestamp: datetime
    source: str
    symbol: str
    score: float  # -1 to 1
    volume: float = 1.0  # Social volume weight
    influence: float = 1.0  # Influencer weight
    raw_data: dict[str, Any] = field(default_factory=dict)


class SentimentAggregator:
    """
    Aggregates sentiment from multiple sources and timeframes.

    Key features:
    - Z-score normalization against historical baseline
    - Volume-weighted sentiment
    - Influencer weighting
    - Multi-horizon aggregation
    - Sentiment momentum calculation
    """

    def __init__(
        self,
        zscore_window: int = 30,  # days
        volume_decay: float = 0.95,
        max_history_hours: int = 168,  # 7 days
    ):
        self.zscore_window = zscore_window
        self.volume_decay = volume_decay
        self.max_history_hours = max_history_hours

        # Store historical data by symbol
        self._history: dict[str, deque[SentimentDataPoint]] = {}
        self._daily_aggregates: dict[str, list[dict]] = {}

    def _get_history(self, symbol: str) -> deque[SentimentDataPoint]:
        """Get or create history for symbol."""
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=10000)
        return self._history[symbol]

    def add_data_point(self, data_point: SentimentDataPoint) -> None:
        """Add a new sentiment data point."""
        history = self._get_history(data_point.symbol)
        history.append(data_point)

        # Clean old data
        cutoff = datetime.utcnow() - timedelta(hours=self.max_history_hours)
        while history and history[0].timestamp < cutoff:
            history.popleft()

    def add_raw_data(
        self,
        symbol: str,
        source: str,
        score: float,
        volume: float = 1.0,
        influence: float = 1.0,
        raw_data: dict | None = None,
    ) -> None:
        """Add raw sentiment data."""
        data_point = SentimentDataPoint(
            timestamp=datetime.utcnow(),
            source=source,
            symbol=symbol,
            score=score,
            volume=volume,
            influence=influence,
            raw_data=raw_data or {},
        )
        self.add_data_point(data_point)

    def get_current_sentiment(
        self,
        symbol: str,
        lookback_hours: int = 1,
    ) -> dict[str, float]:
        """
        Get current aggregated sentiment for a symbol.

        Args:
            symbol: Trading symbol
            lookback_hours: Hours to look back

        Returns:
            Dictionary with sentiment metrics
        """
        history = self._get_history(symbol)
        if not history:
            return self._empty_sentiment()

        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        recent = [dp for dp in history if dp.timestamp >= cutoff]

        if not recent:
            return self._empty_sentiment()

        return self._aggregate_datapoints(recent)

    def _aggregate_datapoints(
        self,
        datapoints: list[SentimentDataPoint],
    ) -> dict[str, float]:
        """Aggregate multiple data points into metrics."""
        if not datapoints:
            return self._empty_sentiment()

        scores = np.array([dp.score for dp in datapoints])
        volumes = np.array([dp.volume for dp in datapoints])
        influences = np.array([dp.influence for dp in datapoints])

        # Combined weights
        weights = volumes * influences
        total_weight = weights.sum()

        if total_weight == 0:
            total_weight = 1

        # Weighted metrics
        weighted_score = np.average(scores, weights=weights)
        unweighted_score = scores.mean()

        # Sentiment distribution
        bullish_count = (scores > 0.1).sum()
        bearish_count = (scores < -0.1).sum()
        neutral_count = len(scores) - bullish_count - bearish_count

        return {
            "score": weighted_score,
            "score_unweighted": unweighted_score,
            "volume": volumes.sum(),
            "count": len(datapoints),
            "bullish_ratio": bullish_count / len(scores) if len(scores) > 0 else 0.5,
            "bearish_ratio": bearish_count / len(scores) if len(scores) > 0 else 0.5,
            "std": scores.std(),
            "min": scores.min(),
            "max": scores.max(),
        }

    def _empty_sentiment(self) -> dict[str, float]:
        """Return empty sentiment dict."""
        return {
            "score": 0.0,
            "score_unweighted": 0.0,
            "volume": 0.0,
            "count": 0,
            "bullish_ratio": 0.5,
            "bearish_ratio": 0.5,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
        }

    def get_zscore(
        self,
        symbol: str,
        lookback_hours: int = 1,
    ) -> float:
        """
        Calculate sentiment Z-score relative to historical baseline.

        A high Z-score means sentiment is unusually positive.
        A low Z-score means sentiment is unusually negative.

        Args:
            symbol: Trading symbol
            lookback_hours: Hours for current sentiment

        Returns:
            Z-score value
        """
        current = self.get_current_sentiment(symbol, lookback_hours)
        if current["count"] == 0:
            return 0.0

        # Get historical baseline
        history = self._get_history(symbol)
        all_scores = [dp.score for dp in history]

        if len(all_scores) < 10:
            return 0.0

        mean = np.mean(all_scores)
        std = np.std(all_scores)

        if std == 0:
            return 0.0

        return (current["score"] - mean) / std

    def get_momentum(
        self,
        symbol: str,
        short_hours: int = 1,
        long_hours: int = 24,
    ) -> float:
        """
        Calculate sentiment momentum (rate of change).

        Positive momentum = sentiment improving
        Negative momentum = sentiment deteriorating

        Args:
            symbol: Trading symbol
            short_hours: Short window
            long_hours: Long window

        Returns:
            Momentum value
        """
        short_sentiment = self.get_current_sentiment(symbol, short_hours)
        long_sentiment = self.get_current_sentiment(symbol, long_hours)

        if short_sentiment["count"] == 0 or long_sentiment["count"] == 0:
            return 0.0

        return short_sentiment["score"] - long_sentiment["score"]

    def get_volume_weighted_sentiment(
        self,
        symbol: str,
        lookback_hours: int = 4,
    ) -> dict[str, float]:
        """
        Get volume-weighted sentiment with temporal decay.

        More recent data has higher weight.

        Args:
            symbol: Trading symbol
            lookback_hours: Hours to look back

        Returns:
            Dictionary with weighted sentiment metrics
        """
        history = self._get_history(symbol)
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        recent = [dp for dp in history if dp.timestamp >= cutoff]

        if not recent:
            return self._empty_sentiment()

        now = datetime.utcnow()

        # Calculate time-decayed weights
        weights = []
        for dp in recent:
            hours_ago = (now - dp.timestamp).total_seconds() / 3600
            decay = self.volume_decay ** hours_ago
            weights.append(dp.volume * dp.influence * decay)

        weights = np.array(weights)
        scores = np.array([dp.score for dp in recent])

        total_weight = weights.sum()
        if total_weight == 0:
            total_weight = 1

        return {
            "score": np.average(scores, weights=weights),
            "volume": sum(dp.volume for dp in recent),
            "count": len(recent),
            "effective_weight": total_weight,
        }

    def get_by_source(
        self,
        symbol: str,
        lookback_hours: int = 1,
    ) -> dict[str, dict[str, float]]:
        """
        Get sentiment broken down by source.

        Args:
            symbol: Trading symbol
            lookback_hours: Hours to look back

        Returns:
            Dictionary mapping source -> sentiment metrics
        """
        history = self._get_history(symbol)
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        recent = [dp for dp in history if dp.timestamp >= cutoff]

        if not recent:
            return {}

        # Group by source
        by_source: dict[str, list[SentimentDataPoint]] = {}
        for dp in recent:
            if dp.source not in by_source:
                by_source[dp.source] = []
            by_source[dp.source].append(dp)

        return {
            source: self._aggregate_datapoints(points)
            for source, points in by_source.items()
        }

    def get_influencer_sentiment(
        self,
        symbol: str,
        min_influence: float = 10000,  # e.g., follower count
        lookback_hours: int = 4,
    ) -> dict[str, float]:
        """
        Get sentiment from high-influence sources only.

        Args:
            symbol: Trading symbol
            min_influence: Minimum influence threshold
            lookback_hours: Hours to look back

        Returns:
            Dictionary with influencer sentiment metrics
        """
        history = self._get_history(symbol)
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        recent = [
            dp for dp in history
            if dp.timestamp >= cutoff and dp.influence >= min_influence
        ]

        if not recent:
            return self._empty_sentiment()

        return self._aggregate_datapoints(recent)

    def get_sentiment_divergence(
        self,
        symbol: str,
        price_return: float,
        lookback_hours: int = 24,
    ) -> float:
        """
        Calculate divergence between sentiment and price.

        High divergence can signal reversal opportunities:
        - Bullish sentiment + negative returns = potential bounce
        - Bearish sentiment + positive returns = potential top

        Args:
            symbol: Trading symbol
            price_return: Recent price return (e.g., 24h return)
            lookback_hours: Sentiment lookback period

        Returns:
            Divergence score (-1 to 1)
        """
        sentiment = self.get_current_sentiment(symbol, lookback_hours)

        if sentiment["count"] == 0:
            return 0.0

        # Normalize to same scale
        norm_sentiment = sentiment["score"]  # Already -1 to 1
        norm_return = np.clip(price_return * 10, -1, 1)  # Scale returns

        # Divergence is when they move opposite directions
        divergence = norm_sentiment - norm_return

        return np.clip(divergence, -1, 1)

    def get_features(
        self,
        symbol: str,
    ) -> dict[str, float]:
        """
        Get all sentiment features for a symbol.

        Returns:
            Dictionary of all computed features
        """
        features = {}

        # Current sentiment at different horizons
        for hours in [1, 4, 24]:
            sent = self.get_current_sentiment(symbol, hours)
            features[f"sentiment_{hours}h"] = sent["score"]
            features[f"sentiment_volume_{hours}h"] = sent["volume"]
            features[f"bullish_ratio_{hours}h"] = sent["bullish_ratio"]

        # Z-score
        features["sentiment_zscore"] = self.get_zscore(symbol, 4)

        # Momentum
        features["sentiment_momentum_1h_24h"] = self.get_momentum(symbol, 1, 24)
        features["sentiment_momentum_4h_24h"] = self.get_momentum(symbol, 4, 24)

        # Volume-weighted
        vw = self.get_volume_weighted_sentiment(symbol, 4)
        features["sentiment_volume_weighted"] = vw["score"]

        # Influencer sentiment
        inf = self.get_influencer_sentiment(symbol)
        features["influencer_sentiment"] = inf["score"]
        features["influencer_count"] = inf["count"]

        return features

    def get_signal(
        self,
        symbol: str,
        threshold: float = 1.5,
    ) -> dict[str, Any]:
        """
        Get trading signal from sentiment analysis.

        Args:
            symbol: Trading symbol
            threshold: Z-score threshold for signals

        Returns:
            Signal dictionary with direction and strength
        """
        zscore = self.get_zscore(symbol, 4)
        momentum = self.get_momentum(symbol, 1, 24)
        current = self.get_current_sentiment(symbol, 4)

        # Determine direction
        if zscore > threshold and momentum > 0:
            direction = "bullish"
            strength = min(zscore / 3, 1.0)  # Cap at 1
        elif zscore < -threshold and momentum < 0:
            direction = "bearish"
            strength = min(abs(zscore) / 3, 1.0)
        else:
            direction = "neutral"
            strength = 0.0

        return {
            "symbol": symbol,
            "direction": direction,
            "strength": strength,
            "zscore": zscore,
            "momentum": momentum,
            "volume": current["volume"],
            "count": current["count"],
            "timestamp": datetime.utcnow().isoformat(),
        }
