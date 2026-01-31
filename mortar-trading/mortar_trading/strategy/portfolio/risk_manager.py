"""
Risk Manager
============

Portfolio risk management and circuit breakers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.core.state import get_trading_state
from mortar_trading.models.regime import MarketRegime
from mortar_trading.strategy.portfolio.position_sizer import PositionSizer

logger = structlog.get_logger(__name__)


class RiskManager:
    """
    Portfolio risk manager.

    Enforces:
    - Position limits
    - Portfolio heat limits
    - Correlation limits
    - Daily/weekly/monthly loss limits (circuit breakers)
    - Volatility-based adjustments
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()
        self.state = get_trading_state()

        self.position_sizer = PositionSizer(settings)
        self.risk_config = settings.risk

        # PnL tracking
        self._daily_pnl: float = 0
        self._weekly_pnl: float = 0
        self._monthly_pnl: float = 0
        self._last_reset_daily: datetime = datetime.utcnow()
        self._last_reset_weekly: datetime = datetime.utcnow()
        self._last_reset_monthly: datetime = datetime.utcnow()

        # Circuit breaker state
        self._circuit_breaker_active: bool = False
        self._circuit_breaker_until: datetime | None = None

        # Regime adjustments
        self._current_regime_adjustment: float = 1.0

    async def start(self) -> None:
        """Start the risk manager."""
        logger.info("Starting risk manager")

    async def stop(self) -> None:
        """Stop the risk manager."""
        logger.info("Stopping risk manager")

    async def check_order(self, order_signal: dict[str, Any]) -> bool:
        """
        Check if an order passes risk checks.

        Args:
            order_signal: Order signal from micro layer

        Returns:
            True if order is approved, False otherwise
        """
        # Check circuit breaker
        if self._circuit_breaker_active:
            if self._circuit_breaker_until and datetime.utcnow() < self._circuit_breaker_until:
                logger.warning("Circuit breaker active, rejecting order")
                return False
            else:
                self._circuit_breaker_active = False

        symbol = order_signal.get("symbol")
        quantity = order_signal.get("quantity", 0)

        if quantity <= 0:
            return False

        # Get current account state
        account = await self.state.get_account()
        equity = account.equity

        if equity <= 0:
            logger.warning("No equity available")
            return False

        # Calculate notional value
        current_price = order_signal.get("entry_price", 0)
        if current_price <= 0:
            return False

        notional_value = quantity * current_price

        # Check 1: Single position risk
        if not await self._check_position_risk(symbol, notional_value, equity):
            return False

        # Check 2: Portfolio heat
        if not await self._check_portfolio_heat(notional_value, equity):
            return False

        # Check 3: Correlated positions
        if not await self._check_correlation_limit(symbol):
            return False

        # Check 4: Max leverage
        if not self._check_leverage(notional_value, equity):
            return False

        return True

    async def _check_position_risk(
        self,
        symbol: str,
        notional_value: float,
        equity: float,
    ) -> bool:
        """Check single position risk limit."""
        max_position_value = equity * (self.risk_config.single_position_risk_pct / 100)
        max_position_value *= self._current_regime_adjustment

        # Include existing position
        existing_position = await self.state.get_position(symbol)
        if existing_position:
            existing_notional = existing_position.notional_value
            total_notional = existing_notional + notional_value
        else:
            total_notional = notional_value

        if total_notional > max_position_value:
            logger.warning(
                "Position risk limit exceeded",
                symbol=symbol,
                requested=notional_value,
                max_allowed=max_position_value,
            )
            await self._publish_breach("position_risk", symbol, total_notional, max_position_value)
            return False

        return True

    async def _check_portfolio_heat(
        self,
        additional_notional: float,
        equity: float,
    ) -> bool:
        """Check total portfolio heat limit."""
        max_heat = equity * (self.risk_config.total_portfolio_heat_pct / 100)
        max_heat *= self._current_regime_adjustment

        current_heat = await self.state.get_total_position_value()
        new_heat = current_heat + additional_notional

        if new_heat > max_heat:
            logger.warning(
                "Portfolio heat limit exceeded",
                current_heat=current_heat,
                additional=additional_notional,
                max_allowed=max_heat,
            )
            await self._publish_breach("portfolio_heat", None, new_heat, max_heat)
            return False

        return True

    async def _check_correlation_limit(self, symbol: str) -> bool:
        """Check correlated positions limit."""
        positions = await self.state.get_all_positions()

        if len(positions) >= self.risk_config.max_correlated_positions:
            # Check if adding same asset class
            # For simplicity, count positions in same category
            # In practice, would use actual correlation data

            # BTC/ETH are highly correlated
            correlated_pairs = [
                {"BTCUSDT", "ETHUSDT"},
                {"SOLUSDT", "AVAXUSDT", "DOTUSDT"},  # Alt L1s
            ]

            symbol_positions = {p.symbol for p in positions}
            symbol_positions.add(symbol)

            for pair_group in correlated_pairs:
                count = len(symbol_positions.intersection(pair_group))
                if count > self.risk_config.max_correlated_positions:
                    logger.warning(
                        "Correlated positions limit exceeded",
                        symbol=symbol,
                        group=pair_group,
                    )
                    await self._publish_breach("correlation", symbol, count, self.risk_config.max_correlated_positions)
                    return False

        return True

    def _check_leverage(self, notional_value: float, equity: float) -> bool:
        """Check maximum leverage."""
        max_leverage = self.risk_config.max_leverage

        implied_leverage = notional_value / equity if equity > 0 else float("inf")

        if implied_leverage > max_leverage:
            logger.warning(
                "Leverage limit exceeded",
                implied=implied_leverage,
                max_allowed=max_leverage,
            )
            return False

        return True

    async def update_pnl(self, realized_pnl: float) -> None:
        """Update PnL tracking and check circuit breakers."""
        now = datetime.utcnow()

        # Reset periods if needed
        if (now - self._last_reset_daily).days >= 1:
            self._daily_pnl = 0
            self._last_reset_daily = now

        if (now - self._last_reset_weekly).days >= 7:
            self._weekly_pnl = 0
            self._last_reset_weekly = now

        if (now - self._last_reset_monthly).days >= 30:
            self._monthly_pnl = 0
            self._last_reset_monthly = now

        # Update PnL
        self._daily_pnl += realized_pnl
        self._weekly_pnl += realized_pnl
        self._monthly_pnl += realized_pnl

        # Check circuit breakers
        account = await self.state.get_account()
        equity = account.equity

        if equity > 0:
            daily_pct = (self._daily_pnl / equity) * 100
            weekly_pct = (self._weekly_pnl / equity) * 100
            monthly_pct = (self._monthly_pnl / equity) * 100

            if daily_pct <= -self.risk_config.daily_loss_limit_pct:
                await self._trigger_circuit_breaker("daily", daily_pct)
            elif weekly_pct <= -self.risk_config.weekly_loss_limit_pct:
                await self._trigger_circuit_breaker("weekly", weekly_pct)
            elif monthly_pct <= -self.risk_config.monthly_loss_limit_pct:
                await self._trigger_circuit_breaker("monthly", monthly_pct)

    async def _trigger_circuit_breaker(self, period: str, loss_pct: float) -> None:
        """Trigger circuit breaker."""
        logger.critical(
            "Circuit breaker triggered",
            period=period,
            loss_pct=loss_pct,
        )

        self._circuit_breaker_active = True

        # Set cooldown period
        if period == "daily":
            self._circuit_breaker_until = datetime.utcnow() + timedelta(hours=24)
        elif period == "weekly":
            self._circuit_breaker_until = datetime.utcnow() + timedelta(days=7)
        else:
            self._circuit_breaker_until = datetime.utcnow() + timedelta(days=30)

        await self.event_bus.publish(
            Event(
                event_type=EventType.CIRCUIT_BREAKER_TRIGGERED,
                payload={
                    "period": period,
                    "loss_pct": loss_pct,
                    "until": self._circuit_breaker_until.isoformat(),
                },
                source="risk_manager",
            )
        )

    async def adjust_for_regime(self, regime: str | MarketRegime) -> None:
        """Adjust risk parameters based on market regime."""
        if isinstance(regime, str):
            try:
                regime = MarketRegime(regime)
            except ValueError:
                regime = MarketRegime.UNKNOWN

        adjustments = {
            MarketRegime.TRENDING_LOW_VOL: 1.2,
            MarketRegime.TRENDING_HIGH_VOL: 0.8,
            MarketRegime.RANGE_LOW_VOL: 1.0,
            MarketRegime.RANGE_HIGH_VOL: 0.5,
            MarketRegime.BREAKOUT: 1.0,
            MarketRegime.CRISIS: 0.25,
            MarketRegime.UNKNOWN: 0.5,
        }

        self._current_regime_adjustment = adjustments.get(regime, 0.5)

        logger.info(
            "Regime adjustment applied",
            regime=regime.value if isinstance(regime, MarketRegime) else regime,
            adjustment=self._current_regime_adjustment,
        )

    async def handle_breach(self, breach_data: dict[str, Any]) -> None:
        """Handle risk limit breach."""
        breach_type = breach_data.get("breach_type")

        if breach_type == "drawdown":
            # Reduce all positions by 50%
            positions = await self.state.get_all_positions()
            logger.warning(
                "Reducing positions due to drawdown",
                position_count=len(positions),
            )

    async def _publish_breach(
        self,
        breach_type: str,
        symbol: str | None,
        current_value: float,
        limit_value: float,
    ) -> None:
        """Publish risk breach event."""
        await self.event_bus.publish(
            Event(
                event_type=EventType.RISK_LIMIT_BREACH,
                payload={
                    "breach_type": breach_type,
                    "symbol": symbol,
                    "current_value": current_value,
                    "limit_value": limit_value,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                symbol=symbol,
                source="risk_manager",
            )
        )

    def get_risk_status(self) -> dict[str, Any]:
        """Get current risk status."""
        return {
            "circuit_breaker_active": self._circuit_breaker_active,
            "circuit_breaker_until": (
                self._circuit_breaker_until.isoformat()
                if self._circuit_breaker_until
                else None
            ),
            "daily_pnl": self._daily_pnl,
            "weekly_pnl": self._weekly_pnl,
            "monthly_pnl": self._monthly_pnl,
            "regime_adjustment": self._current_regime_adjustment,
            "limits": {
                "max_leverage": self.risk_config.max_leverage,
                "single_position_risk_pct": self.risk_config.single_position_risk_pct,
                "portfolio_heat_pct": self.risk_config.total_portfolio_heat_pct,
                "daily_loss_limit_pct": self.risk_config.daily_loss_limit_pct,
                "weekly_loss_limit_pct": self.risk_config.weekly_loss_limit_pct,
                "monthly_loss_limit_pct": self.risk_config.monthly_loss_limit_pct,
            },
        }
