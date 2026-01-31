"""
Main Trading Engine
===================

Orchestrates all components of the trading system.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime
from typing import Any

import structlog

from mortar_trading.config import Settings, get_settings
from mortar_trading.core.events import Event, EventBus, EventType, get_event_bus
from mortar_trading.core.state import TradingState, get_trading_state

logger = structlog.get_logger(__name__)


class TradingEngine:
    """
    Main trading engine that orchestrates all components.

    Implements the three-layer architecture:
    - Macro: Daily/4H directional bias from sentiment + on-chain
    - Meso: 1H/15M trade setup from volatility + regime
    - Micro: 5M/1M entry/exit execution from order flow

    The cardinal rule: Never trade against the higher timeframe direction.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.event_bus = get_event_bus()
        self.state = get_trading_state()

        # Component references (initialized during startup)
        self._data_collector = None
        self._sentiment_engine = None
        self._volatility_engine = None
        self._regime_classifier = None
        self._macro_agent = None
        self._meso_agent = None
        self._micro_agent = None
        self._risk_manager = None
        self._executor = None
        self._monitor = None

        # Engine state
        self._running = False
        self._shutdown_event: asyncio.Event | None = None
        self._tasks: list[asyncio.Task] = []

        # Master input state
        self._master_direction = self.settings.master_input.default_direction
        self._master_confidence = self.settings.master_input.default_confidence
        self._master_time_horizon = self.settings.master_input.default_time_horizon
        self._key_levels = {"support": None, "resistance": None}
        self._upcoming_events: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info(
            "Initializing trading engine",
            environment=self.settings.environment.value,
            symbols=self.settings.symbols.all_symbols,
        )

        # Import components here to avoid circular imports
        from mortar_trading.data import DataCollector
        from mortar_trading.models.sentiment import SentimentEngine
        from mortar_trading.models.volatility import VolatilityEngine
        from mortar_trading.models.regime import RegimeClassifier
        from mortar_trading.strategy.macro import MacroAgent
        from mortar_trading.strategy.meso import MesoAgent
        from mortar_trading.strategy.micro import MicroAgent
        from mortar_trading.strategy.portfolio import RiskManager
        from mortar_trading.execution import OrderExecutor
        from mortar_trading.monitoring import Monitor

        # Initialize components
        self._data_collector = DataCollector(self.settings)
        self._sentiment_engine = SentimentEngine(self.settings)
        self._volatility_engine = VolatilityEngine(self.settings)
        self._regime_classifier = RegimeClassifier(self.settings)
        self._macro_agent = MacroAgent(self.settings)
        self._meso_agent = MesoAgent(self.settings)
        self._micro_agent = MicroAgent(self.settings)
        self._risk_manager = RiskManager(self.settings)
        self._executor = OrderExecutor(self.settings)
        self._monitor = Monitor(self.settings)

        # Subscribe to events
        await self._setup_event_handlers()

        # Start event bus
        await self.event_bus.start()

        logger.info("Trading engine initialized")

    async def _setup_event_handlers(self) -> None:
        """Set up event handlers for all components."""
        # Market data -> Volatility engine
        self.event_bus.subscribe(EventType.CANDLE, self._on_candle)
        self.event_bus.subscribe(EventType.TICK, self._on_tick)

        # Sentiment updates -> Macro agent
        self.event_bus.subscribe(EventType.SENTIMENT_UPDATE, self._on_sentiment_update)

        # Volatility updates -> Regime classifier and Meso agent
        self.event_bus.subscribe(EventType.VOLATILITY_UPDATE, self._on_volatility_update)
        self.event_bus.subscribe(EventType.REGIME_CHANGE, self._on_regime_change)

        # Signal flow: Macro -> Meso -> Micro
        self.event_bus.subscribe(EventType.MACRO_SIGNAL, self._on_macro_signal)
        self.event_bus.subscribe(EventType.MESO_SIGNAL, self._on_meso_signal)
        self.event_bus.subscribe(EventType.MICRO_SIGNAL, self._on_micro_signal)

        # Risk events
        self.event_bus.subscribe(EventType.RISK_LIMIT_BREACH, self._on_risk_breach)
        self.event_bus.subscribe(EventType.CIRCUIT_BREAKER_TRIGGERED, self._on_circuit_breaker)

        # Order/Position updates
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
        self.event_bus.subscribe(EventType.POSITION_OPENED, self._on_position_opened)
        self.event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)

        logger.debug("Event handlers configured")

    async def start(self) -> None:
        """Start the trading engine."""
        if self._running:
            logger.warning("Trading engine already running")
            return

        logger.info("Starting trading engine")
        self._running = True
        self._shutdown_event = asyncio.Event()

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Publish system start event
        await self.event_bus.publish(
            Event(
                event_type=EventType.SYSTEM_START,
                payload={"timestamp": datetime.utcnow().isoformat()},
                source="engine",
            )
        )

        # Start component tasks
        self._tasks = [
            asyncio.create_task(self._run_data_collection()),
            asyncio.create_task(self._run_sentiment_updates()),
            asyncio.create_task(self._run_volatility_updates()),
            asyncio.create_task(self._run_heartbeat()),
            asyncio.create_task(self._run_position_reconciliation()),
        ]

        logger.info("Trading engine started")

        # Wait for shutdown
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """Stop the trading engine gracefully."""
        if not self._running:
            return

        logger.info("Stopping trading engine")
        self._running = False

        # Cancel all orders
        await self._cancel_all_orders()

        # Stop all tasks
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Publish system stop event
        await self.event_bus.publish(
            Event(
                event_type=EventType.SYSTEM_STOP,
                payload={"timestamp": datetime.utcnow().isoformat()},
                source="engine",
            )
        )

        # Stop event bus
        await self.event_bus.stop()

        if self._shutdown_event:
            self._shutdown_event.set()

        logger.info("Trading engine stopped")

    async def _run_data_collection(self) -> None:
        """Run data collection loop."""
        while self._running:
            try:
                if self._data_collector:
                    await self._data_collector.collect()
            except Exception as e:
                logger.error("Data collection error", error=str(e))
            await asyncio.sleep(1)

    async def _run_sentiment_updates(self) -> None:
        """Run sentiment update loop."""
        while self._running:
            try:
                if self._sentiment_engine:
                    await self._sentiment_engine.update()
            except Exception as e:
                logger.error("Sentiment update error", error=str(e))
            await asyncio.sleep(300)  # Every 5 minutes

    async def _run_volatility_updates(self) -> None:
        """Run volatility model updates."""
        while self._running:
            try:
                if self._volatility_engine:
                    await self._volatility_engine.update()
            except Exception as e:
                logger.error("Volatility update error", error=str(e))
            await asyncio.sleep(60)  # Every minute

    async def _run_heartbeat(self) -> None:
        """Run heartbeat for monitoring."""
        while self._running:
            await self.event_bus.publish(
                Event(
                    event_type=EventType.HEARTBEAT,
                    payload={
                        "timestamp": datetime.utcnow().isoformat(),
                        "positions": len(await self.state.get_all_positions()),
                        "open_orders": len(await self.state.get_open_orders()),
                    },
                    source="engine",
                )
            )
            await asyncio.sleep(10)

    async def _run_position_reconciliation(self) -> None:
        """Periodically reconcile positions with exchange."""
        while self._running:
            try:
                if self._executor:
                    await self._executor.reconcile_positions()
            except Exception as e:
                logger.error("Position reconciliation error", error=str(e))
            await asyncio.sleep(30)

    # Event Handlers

    async def _on_candle(self, event: Event) -> None:
        """Handle candle data updates."""
        if self._volatility_engine:
            await self._volatility_engine.process_candle(event.payload)

    async def _on_tick(self, event: Event) -> None:
        """Handle tick data updates."""
        # Update position PnLs
        symbol = event.symbol
        price = event.payload.get("price")
        if symbol and price:
            position = await self.state.get_position(symbol)
            if position:
                position.update_unrealized_pnl(price)

    async def _on_sentiment_update(self, event: Event) -> None:
        """Handle sentiment updates."""
        if self._macro_agent:
            await self._macro_agent.process_sentiment(event.payload)

    async def _on_volatility_update(self, event: Event) -> None:
        """Handle volatility updates."""
        if self._regime_classifier:
            await self._regime_classifier.process_volatility(event.payload)

    async def _on_regime_change(self, event: Event) -> None:
        """Handle regime changes."""
        new_regime = event.payload.get("regime")
        logger.info("Regime change detected", new_regime=new_regime)

        if self._meso_agent:
            await self._meso_agent.update_regime(new_regime)

        if self._risk_manager:
            await self._risk_manager.adjust_for_regime(new_regime)

    async def _on_macro_signal(self, event: Event) -> None:
        """Handle macro layer signals."""
        # Macro signals constrain meso agent
        if self._meso_agent:
            await self._meso_agent.update_macro_bias(event.payload)

    async def _on_meso_signal(self, event: Event) -> None:
        """Handle meso layer signals."""
        # Meso signals trigger micro agent for execution
        if self._micro_agent:
            await self._micro_agent.process_setup(event.payload)

    async def _on_micro_signal(self, event: Event) -> None:
        """Handle micro layer execution signals."""
        # Micro signals go to risk check then execution
        if self._risk_manager and self._executor:
            risk_approved = await self._risk_manager.check_order(event.payload)
            if risk_approved:
                await self._executor.execute(event.payload)
            else:
                logger.warning("Order rejected by risk manager", signal=event.payload)

    async def _on_risk_breach(self, event: Event) -> None:
        """Handle risk limit breaches."""
        breach_type = event.payload.get("breach_type")
        logger.error("Risk limit breached", breach_type=breach_type)

        # Reduce positions if needed
        if self._risk_manager:
            await self._risk_manager.handle_breach(event.payload)

    async def _on_circuit_breaker(self, event: Event) -> None:
        """Handle circuit breaker triggers."""
        logger.critical("Circuit breaker triggered", payload=event.payload)

        # Cancel all orders and close positions
        await self._cancel_all_orders()
        await self._close_all_positions()

        # Halt trading
        self._running = False

    async def _on_order_filled(self, event: Event) -> None:
        """Handle order fill events."""
        order_data = event.payload
        logger.info(
            "Order filled",
            symbol=order_data.get("symbol"),
            side=order_data.get("side"),
            quantity=order_data.get("filled_quantity"),
            price=order_data.get("fill_price"),
        )

    async def _on_position_opened(self, event: Event) -> None:
        """Handle position opened events."""
        position_data = event.payload
        logger.info(
            "Position opened",
            symbol=position_data.get("symbol"),
            side=position_data.get("side"),
            quantity=position_data.get("quantity"),
        )

    async def _on_position_closed(self, event: Event) -> None:
        """Handle position closed events."""
        position_data = event.payload
        logger.info(
            "Position closed",
            symbol=position_data.get("symbol"),
            realized_pnl=position_data.get("realized_pnl"),
        )

    async def _cancel_all_orders(self) -> None:
        """Cancel all open orders."""
        open_orders = await self.state.get_open_orders()
        if self._executor:
            for order in open_orders:
                await self._executor.cancel_order(order)

    async def _close_all_positions(self) -> None:
        """Close all open positions."""
        positions = await self.state.get_all_positions()
        if self._executor:
            for position in positions:
                await self._executor.close_position(position)

    # Master Input System

    def set_master_direction(self, direction: str, confidence: str = "medium") -> None:
        """
        Set master macro direction.

        Args:
            direction: strong_bear, bear, neutral, bull, strong_bull
            confidence: low, medium, high
        """
        from mortar_trading.config.settings import Direction, Confidence

        self._master_direction = Direction(direction)
        self._master_confidence = Confidence(confidence)

        logger.info(
            "Master direction updated",
            direction=direction,
            confidence=confidence,
        )

        # Publish event
        self.event_bus.publish_sync(
            Event(
                event_type=EventType.MASTER_INPUT_UPDATE,
                payload={
                    "direction": direction,
                    "confidence": confidence,
                    "time_horizon": self._master_time_horizon.value,
                },
                source="master_input",
            )
        )

    def set_key_levels(self, support: float | None, resistance: float | None) -> None:
        """Set key support and resistance levels."""
        self._key_levels = {"support": support, "resistance": resistance}
        logger.info("Key levels updated", support=support, resistance=resistance)

    def add_upcoming_event(self, event_name: str, event_time: datetime) -> None:
        """Add an upcoming market event."""
        self._upcoming_events.append({
            "name": event_name,
            "time": event_time,
        })
        logger.info("Upcoming event added", event=event_name, time=event_time)

    def get_master_bias(self) -> dict[str, Any]:
        """Get current master bias for strategy layers."""
        return {
            "direction": self._master_direction.value,
            "confidence": self._master_confidence.value,
            "time_horizon": self._master_time_horizon.value,
            "key_levels": self._key_levels,
            "upcoming_events": self._upcoming_events,
            "adjustments": self.settings.master_input.adjustments.model_dump(),
        }

    # Engine Info

    def get_status(self) -> dict[str, Any]:
        """Get engine status."""
        return {
            "running": self._running,
            "environment": self.settings.environment.value,
            "master_bias": self.get_master_bias(),
            "components": {
                "data_collector": self._data_collector is not None,
                "sentiment_engine": self._sentiment_engine is not None,
                "volatility_engine": self._volatility_engine is not None,
                "regime_classifier": self._regime_classifier is not None,
                "macro_agent": self._macro_agent is not None,
                "meso_agent": self._meso_agent is not None,
                "micro_agent": self._micro_agent is not None,
                "risk_manager": self._risk_manager is not None,
                "executor": self._executor is not None,
                "monitor": self._monitor is not None,
            },
        }
