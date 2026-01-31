"""
Event System for Mortar Trading
================================

Provides a pub/sub event bus for inter-component communication.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


class EventType(Enum):
    """Event types in the trading system."""

    # Market Data Events
    TICK = auto()
    CANDLE = auto()
    ORDERBOOK_UPDATE = auto()
    TRADE = auto()
    FUNDING_RATE = auto()
    LIQUIDATION = auto()

    # Sentiment Events
    SENTIMENT_UPDATE = auto()
    SOCIAL_VOLUME_SPIKE = auto()
    INFLUENCER_TWEET = auto()

    # Volatility Events
    VOLATILITY_UPDATE = auto()
    REGIME_CHANGE = auto()
    VOLATILITY_SPIKE = auto()

    # Signal Events
    MACRO_SIGNAL = auto()
    MESO_SIGNAL = auto()
    MICRO_SIGNAL = auto()
    MASTER_INPUT_UPDATE = auto()

    # Order Events
    ORDER_PLACED = auto()
    ORDER_FILLED = auto()
    ORDER_CANCELLED = auto()
    ORDER_REJECTED = auto()
    ORDER_PARTIAL_FILL = auto()

    # Position Events
    POSITION_OPENED = auto()
    POSITION_CLOSED = auto()
    POSITION_UPDATED = auto()
    POSITION_LIQUIDATED = auto()

    # Risk Events
    RISK_LIMIT_BREACH = auto()
    CIRCUIT_BREAKER_TRIGGERED = auto()
    CORRELATION_ALERT = auto()
    DRAWDOWN_WARNING = auto()

    # System Events
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    SYSTEM_ERROR = auto()
    HEARTBEAT = auto()
    CONNECTION_LOST = auto()
    CONNECTION_RESTORED = auto()


@dataclass
class Event:
    """
    Base event class for the trading system.

    All events carry a type, payload, and metadata.
    """

    event_type: EventType
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: UUID = field(default_factory=uuid4)
    source: str = "system"
    symbol: str | None = None

    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.name,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "symbol": self.symbol,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Create event from dictionary."""
        return cls(
            event_id=UUID(data["event_id"]),
            event_type=EventType[data["event_type"]],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            symbol=data.get("symbol"),
            payload=data["payload"],
        )


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Asynchronous event bus for pub/sub communication.

    Supports:
    - Multiple handlers per event type
    - Async handlers
    - Event filtering by symbol
    - Event history for debugging
    """

    def __init__(self, max_history: int = 1000):
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._history: list[Event] = []
        self._max_history = max_history
        self._running = False
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """Subscribe a handler to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("Handler subscribed", event_type=event_type.name)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to all event types."""
        self._global_handlers.append(handler)
        logger.debug("Global handler subscribed")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Events are queued and processed asynchronously.
        """
        await self._queue.put(event)

    def publish_sync(self, event: Event) -> None:
        """
        Synchronously add event to queue.

        Use this from non-async contexts.
        """
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping event", event_type=event.event_type.name)

    async def _process_event(self, event: Event) -> None:
        """Process a single event by calling all registered handlers."""
        # Add to history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Get handlers for this event type
        handlers = self._handlers.get(event.event_type, []) + self._global_handlers

        # Call all handlers concurrently
        if handlers:
            tasks = [asyncio.create_task(handler(event)) for handler in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any handler errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Event handler error",
                        event_type=event.event_type.name,
                        error=str(result),
                    )

    async def _run(self) -> None:
        """Main event processing loop."""
        logger.info("Event bus started")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Event bus error", error=str(e))

        logger.info("Event bus stopped")

    async def start(self) -> None:
        """Start the event bus."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        if self._task:
            await self._task
            self._task = None

    def get_history(
        self,
        event_type: EventType | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get recent events from history with optional filtering."""
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if symbol:
            events = [e for e in events if e.symbol == symbol]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
