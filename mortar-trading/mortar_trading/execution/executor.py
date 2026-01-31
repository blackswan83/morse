"""
Order Executor
==============

Manages order execution and position management.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.core.state import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    TradingState,
    get_trading_state,
)
from mortar_trading.execution.binance_client import BinanceFuturesClient

logger = structlog.get_logger(__name__)


class OrderExecutor:
    """
    Order execution manager.

    Handles:
    - Order placement
    - Order tracking
    - Position reconciliation
    - Stop loss / take profit management
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()
        self.state = get_trading_state()

        self._client = BinanceFuturesClient(settings)
        self._running = False

        # Order tracking
        self._pending_orders: dict[str, Order] = {}  # client_id -> order
        self._order_monitors: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """Start the executor."""
        logger.info("Starting order executor")
        self._running = True

        # Initialize leverage for all symbols
        for symbol in self.settings.symbols.all_symbols:
            try:
                await self._client.set_leverage(
                    symbol,
                    int(self.settings.risk.max_leverage),
                )
            except Exception as e:
                logger.warning(f"Failed to set leverage for {symbol}: {e}")

    async def stop(self) -> None:
        """Stop the executor."""
        logger.info("Stopping order executor")
        self._running = False

        # Cancel all monitoring tasks
        for task in self._order_monitors.values():
            task.cancel()

        await self._client.close()

    async def execute(self, signal: dict[str, Any]) -> Order | None:
        """
        Execute a trading signal.

        Args:
            signal: Signal from micro layer

        Returns:
            Created order or None if failed
        """
        symbol = signal.get("symbol")
        if not symbol:
            return None

        side = OrderSide(signal.get("side", "buy"))
        order_type = OrderType(signal.get("order_type", "market"))
        quantity = signal.get("quantity", 0)
        limit_price = signal.get("limit_price")

        if quantity <= 0:
            logger.warning("Invalid quantity", quantity=quantity)
            return None

        # Create order object
        order = Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=limit_price,
        )

        # Place order
        try:
            response = await self._client.place_order(
                symbol=symbol,
                side=side.value.upper(),
                order_type=order_type.value.upper(),
                quantity=quantity,
                price=limit_price,
                client_order_id=order.client_order_id,
            )

            # Update order with exchange info
            order.exchange_order_id = str(response.get("orderId"))
            order.status = self._parse_status(response.get("status", "NEW"))

            if response.get("avgPrice"):
                order.average_fill_price = float(response["avgPrice"])
            if response.get("executedQty"):
                order.filled_quantity = float(response["executedQty"])

            # Add to state
            await self.state.add_order(order)

            # Publish order event
            await self._publish_order_event(order, EventType.ORDER_PLACED)

            # Start monitoring if not fully filled
            if order.is_open:
                self._start_order_monitor(order)

            logger.info(
                "Order placed",
                order_id=str(order.order_id),
                symbol=symbol,
                side=side.value,
                quantity=quantity,
                status=order.status.value,
            )

            return order

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            order.status = OrderStatus.REJECTED
            await self._publish_order_event(order, EventType.ORDER_REJECTED)
            return None

    async def cancel_order(self, order: Order) -> bool:
        """Cancel an open order."""
        if not order.is_open:
            return False

        try:
            await self._client.cancel_order(
                symbol=order.symbol,
                order_id=int(order.exchange_order_id) if order.exchange_order_id else None,
                client_order_id=order.client_order_id,
            )

            order.status = OrderStatus.CANCELLED
            await self.state.update_order(order)
            await self._publish_order_event(order, EventType.ORDER_CANCELLED)

            # Stop monitoring
            self._stop_order_monitor(order.client_order_id)

            logger.info("Order cancelled", order_id=str(order.order_id))
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    async def close_position(self, position: Position) -> Order | None:
        """Close an open position."""
        # Determine closing side
        if position.is_long:
            side = OrderSide.SELL
        else:
            side = OrderSide.BUY

        # Create market order to close
        order = Order(
            symbol=position.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=position.quantity,
            reduce_only=True,
        )

        try:
            response = await self._client.place_order(
                symbol=position.symbol,
                side=side.value.upper(),
                order_type="MARKET",
                quantity=position.quantity,
                reduce_only=True,
                client_order_id=order.client_order_id,
            )

            order.exchange_order_id = str(response.get("orderId"))
            order.status = self._parse_status(response.get("status", "NEW"))

            if order.status == OrderStatus.FILLED:
                # Calculate realized PnL
                fill_price = float(response.get("avgPrice", 0))
                realized_pnl = position.calculate_pnl(fill_price)

                # Update position
                position.realized_pnl = realized_pnl
                await self.state.remove_position(position.symbol)

                # Publish position closed event
                await self.event_bus.publish(
                    Event(
                        event_type=EventType.POSITION_CLOSED,
                        payload={
                            "symbol": position.symbol,
                            "side": position.side.value,
                            "entry_price": position.entry_price,
                            "exit_price": fill_price,
                            "quantity": position.quantity,
                            "realized_pnl": realized_pnl,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        symbol=position.symbol,
                        source="executor",
                    )
                )

            logger.info(
                "Position closed",
                symbol=position.symbol,
                realized_pnl=position.realized_pnl,
            )

            return order

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return None

    async def set_stop_loss(
        self,
        position: Position,
        stop_price: float,
    ) -> Order | None:
        """Set stop loss for a position."""
        if position.is_long:
            side = OrderSide.SELL
        else:
            side = OrderSide.BUY

        try:
            response = await self._client.place_order(
                symbol=position.symbol,
                side=side.value.upper(),
                order_type="STOP_MARKET",
                quantity=position.quantity,
                stop_price=stop_price,
                reduce_only=True,
            )

            order = Order(
                symbol=position.symbol,
                side=side,
                order_type=OrderType.STOP_MARKET,
                quantity=position.quantity,
                stop_price=stop_price,
                reduce_only=True,
            )
            order.exchange_order_id = str(response.get("orderId"))

            await self.state.add_order(order)

            # Update position
            position.stop_loss_price = stop_price
            await self.state.add_position(position)

            logger.info(
                "Stop loss set",
                symbol=position.symbol,
                stop_price=stop_price,
            )

            return order

        except Exception as e:
            logger.error(f"Failed to set stop loss: {e}")
            return None

    async def set_take_profit(
        self,
        position: Position,
        take_profit_price: float,
    ) -> Order | None:
        """Set take profit for a position."""
        if position.is_long:
            side = OrderSide.SELL
        else:
            side = OrderSide.BUY

        try:
            response = await self._client.place_order(
                symbol=position.symbol,
                side=side.value.upper(),
                order_type="TAKE_PROFIT_MARKET",
                quantity=position.quantity,
                stop_price=take_profit_price,
                reduce_only=True,
            )

            order = Order(
                symbol=position.symbol,
                side=side,
                order_type=OrderType.TAKE_PROFIT_MARKET,
                quantity=position.quantity,
                stop_price=take_profit_price,
                reduce_only=True,
            )
            order.exchange_order_id = str(response.get("orderId"))

            await self.state.add_order(order)

            # Update position
            position.take_profit_price = take_profit_price
            await self.state.add_position(position)

            logger.info(
                "Take profit set",
                symbol=position.symbol,
                take_profit_price=take_profit_price,
            )

            return order

        except Exception as e:
            logger.error(f"Failed to set take profit: {e}")
            return None

    async def reconcile_positions(self) -> None:
        """Reconcile local state with exchange positions."""
        try:
            exchange_positions = await self._client.get_positions()

            for pos_data in exchange_positions:
                symbol = pos_data["symbol"]
                local_position = await self.state.get_position(symbol)

                if local_position:
                    # Update local position
                    local_position.unrealized_pnl = pos_data["unrealized_pnl"]
                    await self.state.add_position(local_position)
                else:
                    # New position not in local state
                    position = Position(
                        symbol=symbol,
                        side=PositionSide.LONG if pos_data["side"] == "long" else PositionSide.SHORT,
                        entry_price=pos_data["entry_price"],
                        quantity=pos_data["quantity"],
                        leverage=pos_data["leverage"],
                        unrealized_pnl=pos_data["unrealized_pnl"],
                        liquidation_price=pos_data["liquidation_price"],
                    )
                    await self.state.add_position(position)

            # Update account balance
            balances = await self._client.get_balance()
            usdt_balance = balances.get("USDT", {})
            await self.state.update_account(
                balance=usdt_balance.get("wallet", 0),
                available_balance=usdt_balance.get("available", 0),
            )

        except Exception as e:
            logger.error(f"Position reconciliation failed: {e}")

    def _parse_status(self, status: str) -> OrderStatus:
        """Parse exchange order status."""
        status_map = {
            "NEW": OrderStatus.OPEN,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "EXPIRED": OrderStatus.EXPIRED,
            "REJECTED": OrderStatus.REJECTED,
        }
        return status_map.get(status, OrderStatus.PENDING)

    async def _publish_order_event(self, order: Order, event_type: EventType) -> None:
        """Publish order event."""
        await self.event_bus.publish(
            Event(
                event_type=event_type,
                payload=order.to_dict(),
                symbol=order.symbol,
                source="executor",
            )
        )

    def _start_order_monitor(self, order: Order) -> None:
        """Start monitoring an order for fills."""
        if order.client_order_id in self._order_monitors:
            return

        task = asyncio.create_task(self._monitor_order(order))
        self._order_monitors[order.client_order_id] = task

    def _stop_order_monitor(self, client_order_id: str) -> None:
        """Stop monitoring an order."""
        task = self._order_monitors.pop(client_order_id, None)
        if task:
            task.cancel()

    async def _monitor_order(self, order: Order) -> None:
        """Monitor order until filled or cancelled."""
        while self._running and order.is_open:
            try:
                response = await self._client.get_order(
                    symbol=order.symbol,
                    client_order_id=order.client_order_id,
                )

                new_status = self._parse_status(response.get("status", "NEW"))

                if new_status != order.status:
                    order.status = new_status
                    if response.get("avgPrice"):
                        order.average_fill_price = float(response["avgPrice"])
                    if response.get("executedQty"):
                        order.filled_quantity = float(response["executedQty"])

                    await self.state.update_order(order)

                    if new_status == OrderStatus.FILLED:
                        await self._handle_fill(order)
                        break
                    elif new_status == OrderStatus.PARTIALLY_FILLED:
                        await self._publish_order_event(order, EventType.ORDER_PARTIAL_FILL)

                await asyncio.sleep(1)  # Check every second

            except Exception as e:
                logger.error(f"Order monitoring error: {e}")
                await asyncio.sleep(5)

    async def _handle_fill(self, order: Order) -> None:
        """Handle order fill - create/update position."""
        await self._publish_order_event(order, EventType.ORDER_FILLED)

        # Check if this creates a new position or updates existing
        position = await self.state.get_position(order.symbol)

        if position:
            # Update existing position
            if order.side == OrderSide.BUY:
                if position.is_long:
                    # Adding to long
                    position.quantity += order.filled_quantity
                else:
                    # Closing short
                    position.quantity -= order.filled_quantity
                    if position.quantity <= 0:
                        await self.state.remove_position(order.symbol)
                        return
            else:  # SELL
                if position.is_short:
                    # Adding to short
                    position.quantity += order.filled_quantity
                else:
                    # Closing long
                    position.quantity -= order.filled_quantity
                    if position.quantity <= 0:
                        await self.state.remove_position(order.symbol)
                        return

            await self.state.add_position(position)
        else:
            # Create new position
            position = Position(
                symbol=order.symbol,
                side=PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT,
                entry_price=order.average_fill_price or order.price or 0,
                quantity=order.filled_quantity,
            )
            await self.state.add_position(position)

            await self.event_bus.publish(
                Event(
                    event_type=EventType.POSITION_OPENED,
                    payload=position.to_dict(),
                    symbol=order.symbol,
                    source="executor",
                )
            )
