"""
Trading State Management
========================

Manages positions, orders, and account state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


class OrderSide(Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT_MARKET = "take_profit_market"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(Enum):
    """Position side."""

    LONG = "long"
    SHORT = "short"


@dataclass
class Order:
    """Represents a trading order."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    order_id: UUID = field(default_factory=uuid4)
    exchange_order_id: str | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    reduce_only: bool = False
    time_in_force: str = "GTC"
    client_order_id: str | None = None

    def __post_init__(self):
        if self.client_order_id is None:
            self.client_order_id = f"mortar_{self.order_id.hex[:16]}"

    @property
    def is_open(self) -> bool:
        """Check if order is still open."""
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)

    @property
    def remaining_quantity(self) -> float:
        """Get remaining unfilled quantity."""
        return self.quantity - self.filled_quantity

    @property
    def fill_percentage(self) -> float:
        """Get fill percentage."""
        return (self.filled_quantity / self.quantity) * 100 if self.quantity > 0 else 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": str(self.order_id),
            "exchange_order_id": self.exchange_order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "reduce_only": self.reduce_only,
            "time_in_force": self.time_in_force,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Position:
    """Represents an open trading position."""

    symbol: str
    side: PositionSide
    entry_price: float
    quantity: float
    leverage: float = 1.0
    position_id: UUID = field(default_factory=uuid4)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    liquidation_price: float | None = None
    margin: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    trailing_stop_pct: float | None = None
    strategy_layer: str = "unknown"  # macro, meso, micro
    signal_id: str | None = None

    @property
    def notional_value(self) -> float:
        """Get position notional value."""
        return self.quantity * self.entry_price

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side == PositionSide.LONG

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.side == PositionSide.SHORT

    @property
    def direction_multiplier(self) -> int:
        """Get direction multiplier (+1 for long, -1 for short)."""
        return 1 if self.is_long else -1

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL at current price."""
        price_diff = current_price - self.entry_price
        return price_diff * self.quantity * self.direction_multiplier

    def calculate_pnl_percentage(self, current_price: float) -> float:
        """Calculate PnL as percentage of entry."""
        pnl = self.calculate_pnl(current_price)
        return (pnl / self.notional_value) * 100 if self.notional_value > 0 else 0

    def update_unrealized_pnl(self, current_price: float) -> None:
        """Update unrealized PnL based on current price."""
        self.unrealized_pnl = self.calculate_pnl(current_price)
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position_id": str(self.position_id),
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "leverage": self.leverage,
            "notional_value": self.notional_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "liquidation_price": self.liquidation_price,
            "margin": self.margin,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "trailing_stop_pct": self.trailing_stop_pct,
            "strategy_layer": self.strategy_layer,
            "signal_id": self.signal_id,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class AccountState:
    """Represents account state."""

    balance: float = 0.0
    available_balance: float = 0.0
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    realized_pnl_week: float = 0.0
    realized_pnl_month: float = 0.0
    max_drawdown_today: float = 0.0
    peak_balance_today: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def equity(self) -> float:
        """Get total equity."""
        return self.balance + self.unrealized_pnl

    @property
    def margin_ratio(self) -> float:
        """Get margin utilization ratio."""
        return self.margin_used / self.equity if self.equity > 0 else 0

    def update_drawdown(self) -> None:
        """Update max drawdown tracking."""
        if self.equity > self.peak_balance_today:
            self.peak_balance_today = self.equity

        current_drawdown = (self.peak_balance_today - self.equity) / self.peak_balance_today
        if current_drawdown > self.max_drawdown_today:
            self.max_drawdown_today = current_drawdown

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "balance": self.balance,
            "available_balance": self.available_balance,
            "equity": self.equity,
            "margin_used": self.margin_used,
            "margin_ratio": self.margin_ratio,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl_today": self.realized_pnl_today,
            "realized_pnl_week": self.realized_pnl_week,
            "realized_pnl_month": self.realized_pnl_month,
            "max_drawdown_today": self.max_drawdown_today,
            "updated_at": self.updated_at.isoformat(),
        }


class TradingState:
    """
    Central trading state manager.

    Maintains all positions, orders, and account state.
    Thread-safe through async locking.
    """

    def __init__(self):
        self._positions: dict[str, Position] = {}  # symbol -> position
        self._orders: dict[UUID, Order] = {}  # order_id -> order
        self._account = AccountState()
        self._lock = None  # Will be initialized async

    async def _get_lock(self):
        """Lazy initialize async lock."""
        if self._lock is None:
            import asyncio
            self._lock = asyncio.Lock()
        return self._lock

    # Position Management

    async def add_position(self, position: Position) -> None:
        """Add or update a position."""
        lock = await self._get_lock()
        async with lock:
            self._positions[position.symbol] = position
            logger.info(
                "Position added",
                symbol=position.symbol,
                side=position.side.value,
                quantity=position.quantity,
                entry_price=position.entry_price,
            )

    async def get_position(self, symbol: str) -> Position | None:
        """Get position for a symbol."""
        return self._positions.get(symbol)

    async def remove_position(self, symbol: str) -> Position | None:
        """Remove and return a position."""
        lock = await self._get_lock()
        async with lock:
            position = self._positions.pop(symbol, None)
            if position:
                logger.info("Position removed", symbol=symbol)
            return position

    async def get_all_positions(self) -> list[Position]:
        """Get all open positions."""
        return list(self._positions.values())

    async def get_total_position_value(self) -> float:
        """Get total notional value of all positions."""
        return sum(p.notional_value for p in self._positions.values())

    async def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    # Order Management

    async def add_order(self, order: Order) -> None:
        """Add an order."""
        lock = await self._get_lock()
        async with lock:
            self._orders[order.order_id] = order
            logger.info(
                "Order added",
                order_id=str(order.order_id),
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
            )

    async def get_order(self, order_id: UUID) -> Order | None:
        """Get an order by ID."""
        return self._orders.get(order_id)

    async def update_order(self, order: Order) -> None:
        """Update an existing order."""
        lock = await self._get_lock()
        async with lock:
            order.updated_at = datetime.utcnow()
            self._orders[order.order_id] = order

    async def remove_order(self, order_id: UUID) -> Order | None:
        """Remove and return an order."""
        lock = await self._get_lock()
        async with lock:
            return self._orders.pop(order_id, None)

    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Get all open orders, optionally filtered by symbol."""
        orders = [o for o in self._orders.values() if o.is_open]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    # Account Management

    async def update_account(
        self,
        balance: float | None = None,
        available_balance: float | None = None,
        margin_used: float | None = None,
    ) -> None:
        """Update account state."""
        lock = await self._get_lock()
        async with lock:
            if balance is not None:
                self._account.balance = balance
            if available_balance is not None:
                self._account.available_balance = available_balance
            if margin_used is not None:
                self._account.margin_used = margin_used

            # Update unrealized PnL from positions
            self._account.unrealized_pnl = sum(
                p.unrealized_pnl for p in self._positions.values()
            )
            self._account.update_drawdown()
            self._account.updated_at = datetime.utcnow()

    async def get_account(self) -> AccountState:
        """Get account state."""
        return self._account

    # Risk Checks

    async def check_position_limit(self, symbol: str, additional_notional: float) -> bool:
        """Check if adding position would exceed limits."""
        current_total = await self.get_total_position_value()
        return (current_total + additional_notional) <= (
            self._account.equity * 0.1  # 10% portfolio heat limit
        )

    async def get_portfolio_heat(self) -> float:
        """Get current portfolio heat (total position value / equity)."""
        total_position = await self.get_total_position_value()
        return total_position / self._account.equity if self._account.equity > 0 else 0

    # State Export

    def to_dict(self) -> dict[str, Any]:
        """Export full state to dictionary."""
        return {
            "account": self._account.to_dict(),
            "positions": {
                symbol: pos.to_dict() for symbol, pos in self._positions.items()
            },
            "orders": {
                str(oid): order.to_dict() for oid, order in self._orders.items()
            },
        }


# Global state instance
_trading_state: TradingState | None = None


def get_trading_state() -> TradingState:
    """Get the global trading state instance."""
    global _trading_state
    if _trading_state is None:
        _trading_state = TradingState()
    return _trading_state
