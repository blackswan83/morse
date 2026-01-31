"""
Micro Strategy Agent
====================

5M/1M entry/exit execution optimization.

The Micro layer:
- Optimizes entry/exit timing
- Manages order execution
- Uses order book and microstructure
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.core.state import OrderSide, OrderType

logger = structlog.get_logger(__name__)


@dataclass
class MicroSignal:
    """Micro layer execution signal."""

    symbol: str
    action: str  # "execute_now", "wait", "scale_in", "scale_out"
    order_type: OrderType
    side: OrderSide
    quantity: float
    limit_price: float | None
    urgency: float  # 0 to 1
    slippage_estimate: float
    reasoning: str
    timestamp: datetime


class MicroAgent:
    """
    Micro strategy agent for execution optimization.

    Uses:
    - Order book analysis
    - Price action
    - Volume profile
    - Execution timing

    Outputs:
    - Optimized order parameters
    - Execution timing signals
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()

        # Meso signals to execute
        self._pending_setups: dict[str, dict] = {}

        # Order book state
        self._order_book: dict[str, dict] = {}

        # Execution state
        self._in_execution: dict[str, bool] = {}

        # Thresholds
        self._spread_threshold = 0.001  # 0.1% spread threshold
        self._imbalance_threshold = 0.3  # Order book imbalance

    async def start(self) -> None:
        """Start the micro agent."""
        logger.info("Starting Micro agent")

    async def stop(self) -> None:
        """Stop the micro agent."""
        logger.info("Stopping Micro agent")

    async def process_setup(self, meso_signal: dict[str, Any]) -> None:
        """
        Process incoming setup from Meso layer.

        Args:
            meso_signal: Signal from Meso layer
        """
        symbol = meso_signal.get("symbol")
        if not symbol:
            return

        action = meso_signal.get("action", "")

        if action.startswith("enter"):
            self._pending_setups[symbol] = meso_signal
            await self._evaluate_execution(symbol)
        elif action == "exit":
            await self._execute_exit(symbol, meso_signal)

    async def update_order_book(self, order_book: dict[str, Any]) -> None:
        """
        Update order book data.

        Args:
            order_book: Order book snapshot
        """
        symbol = order_book.get("symbol")
        if not symbol:
            return

        self._order_book[symbol] = order_book

        # Check if we have pending setup to execute
        if symbol in self._pending_setups:
            await self._evaluate_execution(symbol)

    async def _evaluate_execution(self, symbol: str) -> None:
        """Evaluate whether to execute pending setup."""
        setup = self._pending_setups.get(symbol)
        if not setup:
            return

        # Don't re-evaluate if already executing
        if self._in_execution.get(symbol, False):
            return

        order_book = self._order_book.get(symbol, {})

        # Calculate execution metrics
        spread = self._calculate_spread(order_book)
        imbalance = self._calculate_imbalance(order_book)
        depth = self._calculate_depth(order_book)

        # Determine execution strategy
        signal = self._determine_execution(
            symbol=symbol,
            setup=setup,
            spread=spread,
            imbalance=imbalance,
            depth=depth,
        )

        if signal.action in ["execute_now", "scale_in"]:
            await self._publish_signal(signal)

    def _calculate_spread(self, order_book: dict) -> float:
        """Calculate bid-ask spread as percentage."""
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])

        if not bids or not asks:
            return 0.01  # Default 1%

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2

        return (best_ask - best_bid) / mid if mid > 0 else 0.01

    def _calculate_imbalance(self, order_book: dict) -> float:
        """Calculate order book imbalance."""
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])

        if not bids or not asks:
            return 0

        # Sum top 5 levels
        bid_volume = sum(float(b[1]) for b in bids[:5])
        ask_volume = sum(float(a[1]) for a in asks[:5])

        total = bid_volume + ask_volume
        if total == 0:
            return 0

        return (bid_volume - ask_volume) / total  # -1 to 1

    def _calculate_depth(self, order_book: dict) -> float:
        """Calculate order book depth (liquidity indicator)."""
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])

        bid_depth = sum(float(b[0]) * float(b[1]) for b in bids[:10])
        ask_depth = sum(float(a[0]) * float(a[1]) for a in asks[:10])

        return bid_depth + ask_depth

    def _determine_execution(
        self,
        symbol: str,
        setup: dict,
        spread: float,
        imbalance: float,
        depth: float,
    ) -> MicroSignal:
        """Determine optimal execution strategy."""
        position_size = setup.get("position_size", 0)
        entry_price = setup.get("entry_price", 0)
        quality = setup.get("setup_quality", 0.5)

        # Determine direction
        is_long = position_size > 0
        side = OrderSide.BUY if is_long else OrderSide.SELL

        # Check if conditions favor execution
        spread_ok = spread < self._spread_threshold

        # Favorable imbalance (lots of bids for long, lots of asks for short)
        imbalance_favorable = (is_long and imbalance > self._imbalance_threshold) or \
                              (not is_long and imbalance < -self._imbalance_threshold)

        # Determine action and order type
        if spread_ok and imbalance_favorable:
            # Good conditions - execute immediately
            action = "execute_now"
            order_type = OrderType.MARKET
            urgency = 0.9
            reasoning = f"Favorable conditions: spread={spread:.4f}, imbalance={imbalance:.2f}"
        elif spread_ok:
            # Spread ok but not favorable imbalance - use limit order
            action = "execute_now"
            order_type = OrderType.LIMIT
            urgency = 0.7
            reasoning = f"Using limit order: spread ok, imbalance neutral"
        elif quality > 0.8:
            # High quality setup but suboptimal conditions - scale in
            action = "scale_in"
            order_type = OrderType.LIMIT
            urgency = 0.5
            reasoning = f"High quality setup, scaling in due to spread={spread:.4f}"
        else:
            # Wait for better conditions
            action = "wait"
            order_type = OrderType.LIMIT
            urgency = 0.3
            reasoning = f"Waiting for better conditions: spread={spread:.4f}"

        # Calculate limit price
        if order_type == OrderType.LIMIT:
            if is_long:
                limit_price = entry_price * 0.999  # Slightly below current
            else:
                limit_price = entry_price * 1.001  # Slightly above current
        else:
            limit_price = None

        # Estimate slippage
        slippage = spread / 2 if action == "execute_now" else spread

        return MicroSignal(
            symbol=symbol,
            action=action,
            order_type=order_type,
            side=side,
            quantity=abs(position_size),
            limit_price=limit_price,
            urgency=urgency,
            slippage_estimate=slippage,
            reasoning=reasoning,
            timestamp=datetime.utcnow(),
        )

    async def _publish_signal(self, signal: MicroSignal) -> None:
        """Publish micro execution signal."""
        self._in_execution[signal.symbol] = True

        await self.event_bus.publish(
            Event(
                event_type=EventType.MICRO_SIGNAL,
                payload={
                    "symbol": signal.symbol,
                    "action": signal.action,
                    "order_type": signal.order_type.value,
                    "side": signal.side.value,
                    "quantity": signal.quantity,
                    "limit_price": signal.limit_price,
                    "urgency": signal.urgency,
                    "slippage_estimate": signal.slippage_estimate,
                    "reasoning": signal.reasoning,
                    "timestamp": signal.timestamp.isoformat(),
                },
                symbol=signal.symbol,
                source="micro_agent",
            )
        )

        # Clear pending setup if fully executed
        if signal.action == "execute_now":
            self._pending_setups.pop(signal.symbol, None)
            self._in_execution[signal.symbol] = False

    async def _execute_exit(self, symbol: str, meso_signal: dict) -> None:
        """Execute position exit."""
        # For exits, we typically use market orders
        signal = MicroSignal(
            symbol=symbol,
            action="execute_now",
            order_type=OrderType.MARKET,
            side=OrderSide.SELL if meso_signal.get("position_size", 0) > 0 else OrderSide.BUY,
            quantity=abs(meso_signal.get("position_size", 0)),
            limit_price=None,
            urgency=1.0,
            slippage_estimate=0.001,
            reasoning="Exit signal from Meso layer",
            timestamp=datetime.utcnow(),
        )

        await self._publish_signal(signal)
