"""
Market Regime Classifier
========================

Classifies market regimes for strategy adaptation.

Regimes:
- Trending + Low Vol: Clear direction, compressed ranges
- Trending + High Vol: Strong moves with deep pullbacks
- Range + Low Vol: Consolidation, mean-reverting
- Range + High Vol: Choppy, whipsaw-prone
- Breakout: Vol expansion from compression
- Crisis: Extreme vol, correlation spike
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus

logger = structlog.get_logger(__name__)


class MarketRegime(Enum):
    """Market regime classifications."""

    TRENDING_LOW_VOL = "trending_low_vol"
    TRENDING_HIGH_VOL = "trending_high_vol"
    RANGE_LOW_VOL = "range_low_vol"
    RANGE_HIGH_VOL = "range_high_vol"
    BREAKOUT = "breakout"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


@dataclass
class RegimeState:
    """Current regime state with metadata."""

    regime: MarketRegime
    confidence: float
    trend_strength: float
    volatility_percentile: float
    duration_periods: int
    features: dict[str, float]
    timestamp: datetime


class RegimeClassifier:
    """
    Multi-factor market regime classifier.

    Uses:
    - Trend indicators (ADX, moving average alignment)
    - Volatility metrics (current vs historical)
    - Volume analysis
    - Price action patterns

    Adapts strategy parameters based on detected regime.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()

        config = settings.regime
        self.lookback = config.lookback_periods
        self.vol_percentiles = config.volatility_percentiles
        self.trend_periods = config.trend_ema_periods

        # State tracking
        self._current_regimes: dict[str, RegimeState] = {}
        self._regime_history: dict[str, list[MarketRegime]] = {}
        self._ml_classifier = None

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index (ADX)."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Smoothed averages
        atr = tr.rolling(period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(period).mean() / atr

        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(period).mean()

        return adx

    def _calculate_trend_strength(self, df: pd.DataFrame) -> dict[str, float]:
        """Calculate trend strength indicators."""
        close = df["close"]

        # EMA alignment
        ema_short = close.ewm(span=self.trend_periods[0], adjust=False).mean()
        ema_long = close.ewm(span=self.trend_periods[1], adjust=False).mean()

        ema_diff = (ema_short.iloc[-1] - ema_long.iloc[-1]) / ema_long.iloc[-1]

        # ADX
        adx = self._calculate_adx(df)
        current_adx = adx.iloc[-1] if not adx.empty else 0

        # Price momentum
        returns = np.log(close / close.shift(1))
        momentum = returns.rolling(20).mean().iloc[-1] * 100

        # Trend consistency (how often price is above/below MA)
        above_ema = (close > ema_long).rolling(20).mean().iloc[-1]

        return {
            "ema_diff": ema_diff,
            "adx": current_adx,
            "momentum": momentum,
            "trend_consistency": above_ema,
            "is_trending": current_adx > 25,
            "trend_direction": 1 if ema_diff > 0 else -1,
        }

    def _calculate_volatility_metrics(self, df: pd.DataFrame) -> dict[str, float]:
        """Calculate volatility metrics."""
        returns = np.log(df["close"] / df["close"].shift(1)).dropna()

        if len(returns) < 50:
            return {
                "current_vol": 0,
                "vol_percentile": 50,
                "vol_ratio": 1,
                "is_high_vol": False,
            }

        # Current and historical volatility
        current_vol = returns.rolling(20).std().iloc[-1] * np.sqrt(252)
        historical_vol = returns.rolling(100).std() * np.sqrt(252)

        # Percentile ranking
        vol_percentile = (
            (historical_vol < current_vol).sum() / len(historical_vol) * 100
        )

        # Volatility ratio (current vs average)
        vol_ratio = current_vol / historical_vol.mean() if historical_vol.mean() > 0 else 1

        # Vol of vol (stability)
        vol_of_vol = historical_vol.std() / historical_vol.mean() if historical_vol.mean() > 0 else 0

        return {
            "current_vol": current_vol,
            "historical_vol_mean": historical_vol.mean(),
            "vol_percentile": vol_percentile,
            "vol_ratio": vol_ratio,
            "vol_of_vol": vol_of_vol,
            "is_high_vol": vol_percentile > self.vol_percentiles[1],
            "is_extreme_vol": vol_percentile > 95,
        }

    def _calculate_range_metrics(self, df: pd.DataFrame) -> dict[str, float]:
        """Calculate range/consolidation metrics."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Price range compression
        atr = (high - low).rolling(14).mean().iloc[-1]
        price_range = (high.rolling(20).max() - low.rolling(20).min()).iloc[-1]
        range_ratio = atr / price_range if price_range > 0 else 0

        # Bollinger Band width
        sma = close.rolling(20).mean()
        std = close.rolling(20).std()
        bb_width = (std / sma).iloc[-1] * 2  # Normalized

        # Price position within range
        range_position = (
            (close.iloc[-1] - low.rolling(20).min().iloc[-1])
            / (high.rolling(20).max().iloc[-1] - low.rolling(20).min().iloc[-1] + 1e-10)
        )

        return {
            "atr": atr,
            "price_range": price_range,
            "range_ratio": range_ratio,
            "bb_width": bb_width,
            "range_position": range_position,
            "is_compressed": bb_width < 0.03,  # Tight BB
        }

    def _detect_breakout(self, df: pd.DataFrame) -> dict[str, Any]:
        """Detect potential breakout conditions."""
        close = df["close"]
        volume = df["volume"]

        # Bollinger Band breakout
        sma = close.rolling(20).mean()
        std = close.rolling(20).std()
        bb_upper = sma + 2 * std
        bb_lower = sma - 2 * std

        price_above_bb = close.iloc[-1] > bb_upper.iloc[-1]
        price_below_bb = close.iloc[-1] < bb_lower.iloc[-1]

        # Volume confirmation
        vol_avg = volume.rolling(20).mean().iloc[-1]
        vol_spike = volume.iloc[-1] > vol_avg * 1.5

        # Prior compression
        bb_width_history = std / sma
        was_compressed = bb_width_history.shift(5).iloc[-1] < 0.03

        is_breakout = (price_above_bb or price_below_bb) and vol_spike and was_compressed

        return {
            "is_breakout": is_breakout,
            "breakout_direction": 1 if price_above_bb else (-1 if price_below_bb else 0),
            "volume_confirmation": vol_spike,
            "prior_compression": was_compressed,
        }

    def _detect_crisis(
        self,
        df: pd.DataFrame,
        correlation_data: dict[str, pd.Series] | None = None,
    ) -> dict[str, Any]:
        """Detect crisis/dislocation conditions."""
        returns = np.log(df["close"] / df["close"].shift(1)).dropna()

        # Extreme volatility
        current_vol = returns.rolling(5).std().iloc[-1] * np.sqrt(252)
        historical_vol = returns.rolling(100).std().mean() * np.sqrt(252)
        vol_multiple = current_vol / historical_vol if historical_vol > 0 else 1

        # Large drawdown
        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        current_drawdown = drawdown.iloc[-1]

        # Correlation spike (if data available)
        correlation_spike = False
        if correlation_data and len(correlation_data) > 1:
            correlations = pd.DataFrame(correlation_data).corr()
            avg_correlation = correlations.values[np.triu_indices_from(correlations, k=1)].mean()
            correlation_spike = avg_correlation > 0.85

        is_crisis = (vol_multiple > 3) or (current_drawdown < -0.15) or correlation_spike

        return {
            "is_crisis": is_crisis,
            "vol_multiple": vol_multiple,
            "current_drawdown": current_drawdown,
            "correlation_spike": correlation_spike,
        }

    def classify(
        self,
        df: pd.DataFrame,
        correlation_data: dict[str, pd.Series] | None = None,
    ) -> RegimeState:
        """
        Classify market regime from price data.

        Args:
            df: OHLCV DataFrame
            correlation_data: Optional correlation data for crisis detection

        Returns:
            RegimeState with classification
        """
        if len(df) < self.lookback:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0,
                trend_strength=0,
                volatility_percentile=50,
                duration_periods=0,
                features={},
                timestamp=datetime.utcnow(),
            )

        # Calculate all metrics
        trend = self._calculate_trend_strength(df)
        volatility = self._calculate_volatility_metrics(df)
        range_metrics = self._calculate_range_metrics(df)
        breakout = self._detect_breakout(df)
        crisis = self._detect_crisis(df, correlation_data)

        # Classification logic
        if crisis["is_crisis"]:
            regime = MarketRegime.CRISIS
            confidence = min(crisis["vol_multiple"] / 3, 1)

        elif breakout["is_breakout"]:
            regime = MarketRegime.BREAKOUT
            confidence = 0.8 if breakout["volume_confirmation"] else 0.6

        elif trend["is_trending"]:
            if volatility["is_high_vol"]:
                regime = MarketRegime.TRENDING_HIGH_VOL
            else:
                regime = MarketRegime.TRENDING_LOW_VOL
            confidence = trend["adx"] / 50  # ADX normalized

        else:  # Range-bound
            if volatility["is_high_vol"]:
                regime = MarketRegime.RANGE_HIGH_VOL
            else:
                regime = MarketRegime.RANGE_LOW_VOL
            confidence = 1 - (trend["adx"] / 50)

        # Combine all features
        features = {
            **{f"trend_{k}": v for k, v in trend.items() if isinstance(v, (int, float))},
            **{f"vol_{k}": v for k, v in volatility.items() if isinstance(v, (int, float))},
            **{f"range_{k}": v for k, v in range_metrics.items() if isinstance(v, (int, float))},
        }

        return RegimeState(
            regime=regime,
            confidence=max(0, min(1, confidence)),
            trend_strength=trend["adx"],
            volatility_percentile=volatility["vol_percentile"],
            duration_periods=0,  # TODO: Track regime duration
            features=features,
            timestamp=datetime.utcnow(),
        )

    async def process_volatility(self, volatility_data: dict[str, Any]) -> None:
        """
        Process volatility update and check for regime changes.

        Args:
            volatility_data: Volatility update from engine
        """
        # This is called by the main engine when volatility updates
        # The actual classification happens when we have full candle data
        pass

    async def update_regime(
        self,
        symbol: str,
        df: pd.DataFrame,
        correlation_data: dict[str, pd.Series] | None = None,
    ) -> RegimeState:
        """
        Update regime classification for a symbol.

        Args:
            symbol: Trading symbol
            df: OHLCV DataFrame
            correlation_data: Optional correlation data

        Returns:
            Updated RegimeState
        """
        new_state = self.classify(df, correlation_data)
        old_state = self._current_regimes.get(symbol)

        self._current_regimes[symbol] = new_state

        # Track history
        if symbol not in self._regime_history:
            self._regime_history[symbol] = []
        self._regime_history[symbol].append(new_state.regime)
        if len(self._regime_history[symbol]) > 1000:
            self._regime_history[symbol] = self._regime_history[symbol][-1000:]

        # Emit regime change event if changed
        if old_state and old_state.regime != new_state.regime:
            await self.event_bus.publish(
                Event(
                    event_type=EventType.REGIME_CHANGE,
                    payload={
                        "symbol": symbol,
                        "old_regime": old_state.regime.value,
                        "new_regime": new_state.regime.value,
                        "confidence": new_state.confidence,
                        "features": new_state.features,
                        "timestamp": new_state.timestamp.isoformat(),
                    },
                    symbol=symbol,
                    source="regime_classifier",
                )
            )

        return new_state

    def get_current_regime(self, symbol: str) -> RegimeState | None:
        """Get current regime for a symbol."""
        return self._current_regimes.get(symbol)

    def get_strategy_adjustments(self, regime: MarketRegime) -> dict[str, Any]:
        """
        Get strategy adjustments for a regime.

        Returns recommended adjustments to:
        - Position sizing
        - Stop loss placement
        - Take profit levels
        - Trade frequency
        """
        adjustments = {
            MarketRegime.TRENDING_LOW_VOL: {
                "position_size_multiplier": 1.2,
                "stop_multiplier": 2.0,  # Wider stops
                "take_profit_multiplier": 3.0,
                "trade_frequency": "normal",
                "strategy_bias": "trend_follow",
                "description": "Clear trends with low noise - ideal for trend following",
            },
            MarketRegime.TRENDING_HIGH_VOL: {
                "position_size_multiplier": 0.8,
                "stop_multiplier": 1.5,  # Tighter stops
                "take_profit_multiplier": 2.0,
                "trade_frequency": "reduced",
                "strategy_bias": "trend_follow",
                "description": "Strong moves but volatile - reduce size, tighter management",
            },
            MarketRegime.RANGE_LOW_VOL: {
                "position_size_multiplier": 1.0,
                "stop_multiplier": 1.2,
                "take_profit_multiplier": 1.5,
                "trade_frequency": "reduced",
                "strategy_bias": "mean_reversion",
                "description": "Consolidation - mean reversion strategies work best",
            },
            MarketRegime.RANGE_HIGH_VOL: {
                "position_size_multiplier": 0.5,
                "stop_multiplier": 1.0,
                "take_profit_multiplier": 1.2,
                "trade_frequency": "minimal",
                "strategy_bias": "defensive",
                "description": "Choppy and dangerous - minimize exposure",
            },
            MarketRegime.BREAKOUT: {
                "position_size_multiplier": 1.0,
                "stop_multiplier": 1.5,
                "take_profit_multiplier": 2.5,
                "trade_frequency": "aggressive",
                "strategy_bias": "momentum",
                "description": "Volatility expansion - catch the move early",
            },
            MarketRegime.CRISIS: {
                "position_size_multiplier": 0.25,
                "stop_multiplier": 0.5,  # Very tight
                "take_profit_multiplier": 1.0,
                "trade_frequency": "minimal",
                "strategy_bias": "defensive",
                "description": "Crisis mode - preserve capital, minimize risk",
            },
        }

        return adjustments.get(regime, adjustments[MarketRegime.RANGE_HIGH_VOL])
