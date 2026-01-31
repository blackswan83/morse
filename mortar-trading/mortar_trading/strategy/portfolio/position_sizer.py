"""
Position Sizing
===============

ATR-based and volatility-targeting position sizing.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

from mortar_trading.config import Settings

logger = structlog.get_logger(__name__)


class PositionSizer:
    """
    Position sizing calculator.

    Methods:
    - ATR-based with volatility targeting
    - Fixed fractional
    - Kelly criterion (Kelly/4 for safety)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.config = settings.position_sizing
        self.risk_config = settings.risk

    def calculate_size(
        self,
        equity: float,
        price: float,
        atr: float,
        volatility: float | None = None,
        signal_strength: float = 1.0,
    ) -> dict[str, float]:
        """
        Calculate position size based on configured method.

        Args:
            equity: Account equity
            price: Current price
            atr: Average True Range
            volatility: Annualized volatility (for vol targeting)
            signal_strength: Signal confidence (0 to 1)

        Returns:
            Dictionary with size info
        """
        if self.config.method == "atr_volatility_target":
            return self._atr_volatility_target(
                equity, price, atr, volatility, signal_strength
            )
        elif self.config.method == "fixed_fractional":
            return self._fixed_fractional(equity, price, atr, signal_strength)
        elif self.config.method == "kelly":
            return self._kelly_criterion(equity, price, signal_strength)
        else:
            return self._fixed_fractional(equity, price, atr, signal_strength)

    def _atr_volatility_target(
        self,
        equity: float,
        price: float,
        atr: float,
        volatility: float | None,
        signal_strength: float,
    ) -> dict[str, float]:
        """
        ATR-based sizing with volatility targeting.

        Target annual portfolio volatility is maintained by adjusting
        position sizes based on current realized volatility.
        """
        if price <= 0 or atr <= 0:
            return self._empty_result()

        target_vol = self.risk_config.target_annual_volatility_pct / 100
        current_vol = volatility if volatility else 0.5  # Default 50%

        # Volatility multiplier
        vol_multiplier = target_vol / current_vol if current_vol > 0 else 1
        vol_multiplier = max(0.2, min(2, vol_multiplier))  # Clamp

        # Risk per trade
        risk_per_trade = equity * (self.risk_config.single_position_risk_pct / 100)

        # ATR-based stop distance
        stop_distance = atr * self.config.atr_multiplier

        # Base size from risk
        base_size = risk_per_trade / stop_distance

        # Apply volatility adjustment
        adjusted_size = base_size * vol_multiplier * signal_strength

        # Convert to quantity
        quantity = adjusted_size / price

        # Apply limits
        notional_value = quantity * price
        min_size = self.config.min_position_usd / price
        max_size = self.config.max_position_usd / price

        quantity = max(min_size, min(max_size, quantity))
        notional_value = quantity * price

        # Check max leverage
        max_notional = equity * self.risk_config.max_leverage
        if notional_value > max_notional:
            quantity = max_notional / price
            notional_value = quantity * price

        return {
            "quantity": quantity,
            "notional_value": notional_value,
            "stop_distance": stop_distance,
            "risk_amount": quantity * stop_distance,
            "risk_percentage": (quantity * stop_distance / equity) * 100,
            "volatility_multiplier": vol_multiplier,
            "method": "atr_volatility_target",
        }

    def _fixed_fractional(
        self,
        equity: float,
        price: float,
        atr: float,
        signal_strength: float,
    ) -> dict[str, float]:
        """Fixed fractional position sizing."""
        if price <= 0 or atr <= 0:
            return self._empty_result()

        # Fixed percentage of equity at risk
        risk_per_trade = equity * (self.risk_config.single_position_risk_pct / 100)
        risk_per_trade *= signal_strength

        # Stop distance from ATR
        stop_distance = atr * self.config.atr_multiplier

        # Calculate size
        quantity = risk_per_trade / stop_distance

        # Apply limits
        notional_value = quantity * price
        min_size = self.config.min_position_usd / price
        max_size = self.config.max_position_usd / price

        quantity = max(min_size, min(max_size, quantity))
        notional_value = quantity * price

        return {
            "quantity": quantity,
            "notional_value": notional_value,
            "stop_distance": stop_distance,
            "risk_amount": risk_per_trade,
            "risk_percentage": (risk_per_trade / equity) * 100,
            "volatility_multiplier": 1.0,
            "method": "fixed_fractional",
        }

    def _kelly_criterion(
        self,
        equity: float,
        price: float,
        signal_strength: float,
        win_rate: float = 0.55,
        avg_win: float = 1.5,
        avg_loss: float = 1.0,
    ) -> dict[str, float]:
        """
        Kelly criterion position sizing (Kelly/4 for safety).

        f* = (bp - q) / b
        where:
        - b = avg_win / avg_loss (odds)
        - p = win_rate
        - q = 1 - p
        """
        if price <= 0:
            return self._empty_result()

        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p

        kelly = (b * p - q) / b
        kelly = max(0, kelly)  # Never negative

        # Kelly/4 for safety (half-kelly or quarter-kelly)
        safe_kelly = kelly / 4
        safe_kelly *= signal_strength

        # Calculate position
        risk_amount = equity * safe_kelly
        quantity = risk_amount / price

        # Apply limits
        notional_value = quantity * price
        min_size = self.config.min_position_usd / price
        max_size = self.config.max_position_usd / price

        quantity = max(min_size, min(max_size, quantity))
        notional_value = quantity * price

        return {
            "quantity": quantity,
            "notional_value": notional_value,
            "stop_distance": 0,
            "risk_amount": risk_amount,
            "risk_percentage": safe_kelly * 100,
            "kelly_fraction": kelly,
            "safe_kelly": safe_kelly,
            "method": "kelly",
        }

    def _empty_result(self) -> dict[str, float]:
        """Return empty sizing result."""
        return {
            "quantity": 0,
            "notional_value": 0,
            "stop_distance": 0,
            "risk_amount": 0,
            "risk_percentage": 0,
            "volatility_multiplier": 0,
            "method": "none",
        }

    def adjust_for_correlation(
        self,
        sizes: dict[str, dict[str, float]],
        correlation_matrix: dict[str, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        """
        Adjust position sizes based on correlation.

        When assets are highly correlated, reduce combined exposure.
        """
        if len(sizes) <= 1:
            return sizes

        # Calculate average correlation
        symbols = list(sizes.keys())
        correlations = []

        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1 :]:
                corr = correlation_matrix.get(sym1, {}).get(sym2, 0)
                correlations.append(abs(corr))

        avg_corr = np.mean(correlations) if correlations else 0

        # If high correlation, reduce sizes
        if avg_corr > self.risk_config.correlation_threshold:
            reduction_factor = 1 - (avg_corr - self.risk_config.correlation_threshold)
            reduction_factor = max(0.3, reduction_factor)  # Minimum 30%

            adjusted = {}
            for symbol, size_info in sizes.items():
                adjusted[symbol] = {
                    **size_info,
                    "quantity": size_info["quantity"] * reduction_factor,
                    "notional_value": size_info["notional_value"] * reduction_factor,
                    "correlation_adjustment": reduction_factor,
                }
            return adjusted

        return sizes
