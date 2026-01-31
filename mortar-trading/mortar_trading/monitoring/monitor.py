"""
System Monitor
==============

Central monitoring system.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.core.state import get_trading_state
from mortar_trading.monitoring.alerts import AlertManager
from mortar_trading.monitoring.metrics import MetricsCollector

logger = structlog.get_logger(__name__)


class Monitor:
    """
    Central monitoring system.

    Coordinates:
    - Metrics collection
    - Alert management
    - System health checks
    - Performance tracking
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()
        self.state = get_trading_state()

        self.alerts = AlertManager(settings)
        self.metrics = MetricsCollector()

        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Performance tracking
        self._trades: list[dict] = []
        self._peak_equity: float = 0
        self._start_equity: float = 0

    async def start(self) -> None:
        """Start the monitor."""
        logger.info("Starting monitor")
        self._running = True

        # Subscribe to events
        self.event_bus.subscribe(EventType.ORDER_PLACED, self._on_order_placed)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
        self.event_bus.subscribe(EventType.POSITION_OPENED, self._on_position_opened)
        self.event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)
        self.event_bus.subscribe(EventType.RISK_LIMIT_BREACH, self._on_risk_breach)
        self.event_bus.subscribe(EventType.CIRCUIT_BREAKER_TRIGGERED, self._on_circuit_breaker)
        self.event_bus.subscribe(EventType.REGIME_CHANGE, self._on_regime_change)
        self.event_bus.subscribe(EventType.VOLATILITY_SPIKE, self._on_volatility_spike)

        # Start metrics server
        if self.settings.monitoring.prometheus_enabled:
            self.metrics.start_server(self.settings.monitoring.prometheus_port)

        # Start periodic tasks
        self._tasks = [
            asyncio.create_task(self._update_metrics_loop()),
            asyncio.create_task(self._health_check_loop()),
        ]

        # Record starting equity
        account = await self.state.get_account()
        self._start_equity = account.equity
        self._peak_equity = account.equity

    async def stop(self) -> None:
        """Stop the monitor."""
        logger.info("Stopping monitor")
        self._running = False

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _update_metrics_loop(self) -> None:
        """Periodically update metrics."""
        while self._running:
            try:
                await self._update_metrics()
            except Exception as e:
                logger.error(f"Metrics update error: {e}")
            await asyncio.sleep(10)

    async def _health_check_loop(self) -> None:
        """Periodically check system health."""
        while self._running:
            try:
                await self._health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await asyncio.sleep(60)

    async def _update_metrics(self) -> None:
        """Update all metrics."""
        # Position metrics
        positions = await self.state.get_all_positions()
        self.metrics.update_position_count(len(positions))

        for position in positions:
            self.metrics.update_position_value(position.symbol, position.notional_value)
            self.metrics.update_unrealized_pnl(position.symbol, position.unrealized_pnl)

        # Risk metrics
        account = await self.state.get_account()
        total_position_value = await self.state.get_total_position_value()

        if account.equity > 0:
            heat = total_position_value / account.equity
            self.metrics.update_portfolio_heat(heat)

            leverage = total_position_value / account.equity
            self.metrics.update_leverage(leverage)

            # Track peak equity
            if account.equity > self._peak_equity:
                self._peak_equity = account.equity

            # Calculate drawdown
            if self._peak_equity > 0:
                drawdown = (self._peak_equity - account.equity) / self._peak_equity
                self.metrics.update_max_drawdown(drawdown)

            # Daily return
            if self._start_equity > 0:
                daily_return = (account.equity - self._start_equity) / self._start_equity
                self.metrics.update_daily_return(daily_return * 100)

    async def _health_check(self) -> None:
        """Perform system health check."""
        # Check account status
        account = await self.state.get_account()

        if account.equity <= 0:
            await self.alerts.send_alert(
                "Account Warning",
                "Account equity is zero or negative",
                "critical",
            )

        # Check for stale positions
        positions = await self.state.get_all_positions()
        for position in positions:
            # Alert if large unrealized loss
            if position.notional_value > 0:
                pnl_pct = (position.unrealized_pnl / position.notional_value) * 100
                threshold = self.settings.monitoring.alerts.position_pnl_alert_pct

                if pnl_pct <= -threshold:
                    await self.alerts.send_alert(
                        "Position Loss Warning",
                        f"Unrealized loss: {pnl_pct:.2f}%",
                        "warning",
                        position.symbol,
                    )

    # Event handlers

    async def _on_order_placed(self, event: Event) -> None:
        """Handle order placed event."""
        self.metrics.record_order_placed(
            symbol=event.payload.get("symbol", ""),
            side=event.payload.get("side", ""),
            order_type=event.payload.get("order_type", ""),
        )

    async def _on_order_filled(self, event: Event) -> None:
        """Handle order filled event."""
        self.metrics.record_order_filled(
            symbol=event.payload.get("symbol", ""),
            side=event.payload.get("side", ""),
        )

    async def _on_position_opened(self, event: Event) -> None:
        """Handle position opened event."""
        await self.alerts.alert_trade_opened(
            symbol=event.payload.get("symbol", ""),
            side=event.payload.get("side", ""),
            quantity=event.payload.get("quantity", 0),
            price=event.payload.get("entry_price", 0),
        )

    async def _on_position_closed(self, event: Event) -> None:
        """Handle position closed event."""
        entry_price = event.payload.get("entry_price", 0)
        exit_price = event.payload.get("exit_price", 0)
        quantity = event.payload.get("quantity", 0)
        pnl = event.payload.get("realized_pnl", 0)

        if entry_price > 0:
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = 0

        await self.alerts.alert_trade_closed(
            symbol=event.payload.get("symbol", ""),
            side=event.payload.get("side", ""),
            pnl=pnl,
            pnl_pct=pnl_pct,
        )

        # Record trade for performance tracking
        self._trades.append({
            "symbol": event.payload.get("symbol"),
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "timestamp": datetime.utcnow(),
        })

    async def _on_risk_breach(self, event: Event) -> None:
        """Handle risk limit breach."""
        await self.alerts.send_alert(
            "Risk Limit Breach",
            f"Breach type: {event.payload.get('breach_type')}\n"
            f"Current: {event.payload.get('current_value')}\n"
            f"Limit: {event.payload.get('limit_value')}",
            "error",
            event.symbol,
        )

    async def _on_circuit_breaker(self, event: Event) -> None:
        """Handle circuit breaker."""
        await self.alerts.alert_circuit_breaker(
            period=event.payload.get("period", ""),
            loss_pct=event.payload.get("loss_pct", 0),
        )

    async def _on_regime_change(self, event: Event) -> None:
        """Handle regime change."""
        await self.alerts.alert_regime_change(
            symbol=event.symbol or "",
            old_regime=event.payload.get("old_regime", ""),
            new_regime=event.payload.get("new_regime", ""),
        )

    async def _on_volatility_spike(self, event: Event) -> None:
        """Handle volatility spike."""
        await self.alerts.alert_volatility_spike(
            symbol=event.symbol or "",
            volatility=event.payload.get("volatility", 0),
            zscore=event.payload.get("zscore", 0),
        )

    # Performance reporting

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        if not self._trades:
            return {"trades": 0, "win_rate": 0, "total_pnl": 0}

        wins = [t for t in self._trades if t["pnl"] > 0]
        losses = [t for t in self._trades if t["pnl"] < 0]

        total_pnl = sum(t["pnl"] for t in self._trades)
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0

        return {
            "trades": len(self._trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self._trades) if self._trades else 0,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss else 0,
            "start_equity": self._start_equity,
            "peak_equity": self._peak_equity,
        }
