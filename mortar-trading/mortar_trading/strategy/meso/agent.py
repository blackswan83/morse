"""
Meso Strategy Agent
===================

1H/15M trade setup identification using volatility and regime.

The Meso layer:
- Identifies trade setups within macro direction
- Determines position size
- Sets stop loss and take profit levels
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.models.regime import MarketRegime

logger = structlog.get_logger(__name__)


@dataclass
class MesoSignal:
    """Meso layer signal output."""

    symbol: str
    action: str  # "enter_long", "enter_short", "exit", "hold"
    position_size: float  # -1 to 1
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    regime: str
    volatility: float
    setup_quality: float  # 0 to 1
    reasoning: str
    timestamp: datetime


class MesoAgent:
    """
    Meso strategy agent for trade setup identification.

    Constrained by Macro layer direction.

    Analyzes:
    - Volatility forecasts
    - Market regime
    - Technical setups
    - Order flow

    Outputs:
    - Entry/exit signals
    - Position sizing
    - Stop/take profit levels
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()

        # Macro constraints
        self._macro_bias: dict[str, int] = {}  # symbol -> direction (-1, 0, 1)
        self._max_allocation: dict[str, float] = {}  # symbol -> allocation

        # Current state
        self._current_regime: dict[str, MarketRegime] = {}
        self._volatility: dict[str, float] = {}
        self._current_signals: dict[str, MesoSignal] = {}

        # Setup detection thresholds
        self._vol_threshold_high = 0.4  # 40% annualized
        self._vol_threshold_low = 0.15  # 15% annualized

    async def start(self) -> None:
        """Start the meso agent."""
        logger.info("Starting Meso agent")

    async def stop(self) -> None:
        """Stop the meso agent."""
        logger.info("Stopping Meso agent")

    async def update_macro_bias(self, macro_signal: dict[str, Any]) -> None:
        """
        Update macro bias constraint.

        Args:
            macro_signal: Signal from Macro layer
        """
        symbol = macro_signal.get("symbol")
        if not symbol:
            return

        direction = macro_signal.get("direction", "neutral")
        direction_map = {
            "strong_bull": 1,
            "bull": 1,
            "neutral": 0,
            "bear": -1,
            "strong_bear": -1,
        }

        self._macro_bias[symbol] = direction_map.get(direction, 0)
        self._max_allocation[symbol] = macro_signal.get("max_allocation", 0.5)

        logger.debug(
            "Macro bias updated",
            symbol=symbol,
            direction=direction,
            allocation=self._max_allocation[symbol],
        )

    async def update_regime(self, regime: str) -> None:
        """Update market regime."""
        # This would be called with symbol context
        pass

    async def process_setup(self, data: dict[str, Any]) -> None:
        """
        Process potential trade setup.

        Args:
            data: Market data for setup analysis
        """
        symbol = data.get("symbol")
        if not symbol:
            return

        # Get current regime and volatility
        regime = self._current_regime.get(symbol, MarketRegime.UNKNOWN)
        volatility = self._volatility.get(symbol, 0.3)

        # Generate signal
        signal = self._analyze_setup(symbol, data, regime, volatility)

        if signal and signal.action != "hold":
            self._current_signals[symbol] = signal

            # Publish meso signal
            await self.event_bus.publish(
                Event(
                    event_type=EventType.MESO_SIGNAL,
                    payload={
                        "symbol": symbol,
                        "action": signal.action,
                        "position_size": signal.position_size,
                        "entry_price": signal.entry_price,
                        "stop_loss": signal.stop_loss,
                        "take_profit": signal.take_profit,
                        "regime": signal.regime,
                        "volatility": signal.volatility,
                        "setup_quality": signal.setup_quality,
                        "reasoning": signal.reasoning,
                        "timestamp": signal.timestamp.isoformat(),
                    },
                    symbol=symbol,
                    source="meso_agent",
                )
            )

    def _analyze_setup(
        self,
        symbol: str,
        data: dict[str, Any],
        regime: MarketRegime,
        volatility: float,
    ) -> MesoSignal:
        """
        Analyze data for trade setup.

        Returns:
            MesoSignal with trade recommendation
        """
        macro_bias = self._macro_bias.get(symbol, 0)
        max_alloc = self._max_allocation.get(symbol, 0.5)

        # Get price data
        current_price = data.get("price", 0)
        atr = data.get("atr", current_price * 0.02)  # Default 2% ATR

        # Get technical indicators
        rsi = data.get("rsi", 50)
        bb_pct = data.get("bb_pct", 0.5)  # Position in Bollinger Bands
        trend_strength = data.get("trend_strength", 0)

        # Determine setup quality and action
        action, position_size, setup_quality, reasoning = self._evaluate_setup(
            macro_bias=macro_bias,
            regime=regime,
            volatility=volatility,
            rsi=rsi,
            bb_pct=bb_pct,
            trend_strength=trend_strength,
        )

        # Apply allocation constraint
        position_size *= max_alloc

        # Calculate stops
        stop_loss, take_profit = self._calculate_levels(
            current_price=current_price,
            atr=atr,
            direction=1 if position_size > 0 else -1,
            regime=regime,
        )

        return MesoSignal(
            symbol=symbol,
            action=action,
            position_size=position_size,
            entry_price=current_price if action.startswith("enter") else None,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime=regime.value if isinstance(regime, MarketRegime) else str(regime),
            volatility=volatility,
            setup_quality=setup_quality,
            reasoning=reasoning,
            timestamp=datetime.utcnow(),
        )

    def _evaluate_setup(
        self,
        macro_bias: int,
        regime: MarketRegime,
        volatility: float,
        rsi: float,
        bb_pct: float,
        trend_strength: float,
    ) -> tuple[str, float, float, str]:
        """
        Evaluate setup quality and determine action.

        Returns:
            (action, position_size, quality, reasoning)
        """
        # Base position sizing on regime
        regime_adjustments = {
            MarketRegime.TRENDING_LOW_VOL: (1.2, "trend_follow"),
            MarketRegime.TRENDING_HIGH_VOL: (0.8, "trend_follow"),
            MarketRegime.RANGE_LOW_VOL: (1.0, "mean_reversion"),
            MarketRegime.RANGE_HIGH_VOL: (0.5, "defensive"),
            MarketRegime.BREAKOUT: (1.0, "momentum"),
            MarketRegime.CRISIS: (0.25, "defensive"),
            MarketRegime.UNKNOWN: (0.5, "neutral"),
        }

        size_mult, strategy = regime_adjustments.get(
            regime, (0.5, "neutral")
        )

        # Evaluate based on strategy
        if strategy == "trend_follow":
            return self._trend_follow_setup(
                macro_bias, size_mult, rsi, trend_strength, volatility
            )
        elif strategy == "mean_reversion":
            return self._mean_reversion_setup(
                macro_bias, size_mult, rsi, bb_pct
            )
        elif strategy == "momentum":
            return self._momentum_setup(
                macro_bias, size_mult, rsi, trend_strength
            )
        elif strategy == "defensive":
            return self._defensive_setup(macro_bias, size_mult)
        else:
            return "hold", 0, 0, "No clear setup"

    def _trend_follow_setup(
        self,
        macro_bias: int,
        size_mult: float,
        rsi: float,
        trend_strength: float,
        volatility: float,
    ) -> tuple[str, float, float, str]:
        """Evaluate trend-following setup."""
        # Strong trend with pullback
        if macro_bias > 0 and trend_strength > 0.5:
            if 40 <= rsi <= 55:  # Pullback in uptrend
                quality = 0.8 * size_mult
                return "enter_long", size_mult * 0.8, quality, "Trend pullback buy"
            elif rsi < 40:
                quality = 0.6 * size_mult
                return "enter_long", size_mult * 0.5, quality, "Oversold in uptrend"

        if macro_bias < 0 and trend_strength < -0.5:
            if 45 <= rsi <= 60:  # Pullback in downtrend
                quality = 0.8 * size_mult
                return "enter_short", -size_mult * 0.8, quality, "Trend pullback sell"
            elif rsi > 60:
                quality = 0.6 * size_mult
                return "enter_short", -size_mult * 0.5, quality, "Overbought in downtrend"

        return "hold", 0, 0, "Waiting for trend setup"

    def _mean_reversion_setup(
        self,
        macro_bias: int,
        size_mult: float,
        rsi: float,
        bb_pct: float,
    ) -> tuple[str, float, float, str]:
        """Evaluate mean-reversion setup."""
        # Oversold at lower BB
        if macro_bias >= 0 and rsi < 30 and bb_pct < 0.1:
            quality = 0.7 * size_mult
            return "enter_long", size_mult * 0.6, quality, "Mean reversion long"

        # Overbought at upper BB
        if macro_bias <= 0 and rsi > 70 and bb_pct > 0.9:
            quality = 0.7 * size_mult
            return "enter_short", -size_mult * 0.6, quality, "Mean reversion short"

        return "hold", 0, 0, "Waiting for mean reversion setup"

    def _momentum_setup(
        self,
        macro_bias: int,
        size_mult: float,
        rsi: float,
        trend_strength: float,
    ) -> tuple[str, float, float, str]:
        """Evaluate momentum/breakout setup."""
        # Breakout with momentum
        if macro_bias > 0 and trend_strength > 0.7 and rsi > 55:
            quality = 0.85 * size_mult
            return "enter_long", size_mult * 1.0, quality, "Momentum breakout long"

        if macro_bias < 0 and trend_strength < -0.7 and rsi < 45:
            quality = 0.85 * size_mult
            return "enter_short", -size_mult * 1.0, quality, "Momentum breakout short"

        return "hold", 0, 0, "Waiting for momentum confirmation"

    def _defensive_setup(
        self,
        macro_bias: int,
        size_mult: float,
    ) -> tuple[str, float, float, str]:
        """Defensive setup - minimal exposure."""
        # Very small positions only in direction of macro bias
        if macro_bias > 0:
            return "enter_long", size_mult * 0.3, 0.3, "Defensive small long"
        elif macro_bias < 0:
            return "enter_short", -size_mult * 0.3, 0.3, "Defensive small short"

        return "hold", 0, 0, "Staying flat in defensive mode"

    def _calculate_levels(
        self,
        current_price: float,
        atr: float,
        direction: int,
        regime: MarketRegime,
    ) -> tuple[float, float]:
        """Calculate stop loss and take profit levels."""
        if current_price <= 0 or atr <= 0:
            return 0, 0

        # Adjust multipliers by regime
        regime_multipliers = {
            MarketRegime.TRENDING_LOW_VOL: (2.0, 3.0),
            MarketRegime.TRENDING_HIGH_VOL: (1.5, 2.0),
            MarketRegime.RANGE_LOW_VOL: (1.2, 1.5),
            MarketRegime.RANGE_HIGH_VOL: (1.0, 1.2),
            MarketRegime.BREAKOUT: (1.5, 2.5),
            MarketRegime.CRISIS: (0.5, 1.0),
        }

        stop_mult, tp_mult = regime_multipliers.get(regime, (1.5, 2.0))

        if direction > 0:  # Long
            stop_loss = current_price - (atr * stop_mult)
            take_profit = current_price + (atr * tp_mult)
        else:  # Short
            stop_loss = current_price + (atr * stop_mult)
            take_profit = current_price - (atr * tp_mult)

        return stop_loss, take_profit

    def get_current_signal(self, symbol: str) -> MesoSignal | None:
        """Get current meso signal for a symbol."""
        return self._current_signals.get(symbol)
