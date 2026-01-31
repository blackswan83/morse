"""
Backtest Engine
===============

Event-driven backtesting framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import numpy as np
import pandas as pd
import structlog

from mortar_trading.config import Settings
from mortar_trading.backtest.results import BacktestResults

logger = structlog.get_logger(__name__)


@dataclass
class BacktestConfig:
    """Backtest configuration."""

    start_date: str | datetime
    end_date: str | datetime
    initial_capital: float = 100000
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage: float = 0.0005
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframe: str = "1h"


@dataclass
class BacktestTrade:
    """Single trade in backtest."""

    symbol: str
    side: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    quantity: float = 0
    pnl: float = 0
    pnl_pct: float = 0
    fees: float = 0


class BacktestEngine:
    """
    Event-driven backtesting engine.

    Features:
    - Walk-forward validation
    - Realistic transaction costs
    - Slippage modeling
    - Performance metrics calculation
    """

    def __init__(self, settings: Settings | None = None, config: BacktestConfig | None = None):
        self.settings = settings or Settings()
        self.config = config or self._config_from_settings()

        # State
        self._equity: float = self.config.initial_capital
        self._cash: float = self.config.initial_capital
        self._positions: dict[str, dict] = {}
        self._trades: list[BacktestTrade] = []
        self._equity_curve: list[tuple[datetime, float]] = []

        # Data
        self._data: dict[str, pd.DataFrame] = {}
        self._current_idx: int = 0

    def _config_from_settings(self) -> BacktestConfig:
        """Create config from settings."""
        bt_settings = self.settings.backtest
        return BacktestConfig(
            start_date=bt_settings.start_date,
            end_date=bt_settings.end_date,
            initial_capital=bt_settings.initial_capital,
            maker_fee=bt_settings.costs.maker_fee_pct / 100,
            taker_fee=bt_settings.costs.taker_fee_pct / 100,
            slippage=bt_settings.costs.slippage_pct / 100,
            symbols=self.settings.symbols.all_symbols,
        )

    def load_data(self, data: dict[str, pd.DataFrame]) -> None:
        """
        Load OHLCV data for backtesting.

        Args:
            data: Dictionary of symbol -> DataFrame with OHLCV columns
        """
        self._data = data

        # Validate data
        for symbol, df in data.items():
            required_cols = ["open", "high", "low", "close", "volume"]
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                raise ValueError(f"Missing columns for {symbol}: {missing}")

            logger.info(f"Loaded {len(df)} candles for {symbol}")

    def run(
        self,
        strategy: Callable[[dict[str, pd.DataFrame], dict[str, dict]], dict[str, float]],
    ) -> BacktestResults:
        """
        Run backtest with given strategy.

        Args:
            strategy: Function that takes (data_dict, positions) and returns
                      {symbol: target_position} where position is -1 to 1

        Returns:
            BacktestResults with performance metrics
        """
        if not self._data:
            raise ValueError("No data loaded. Call load_data() first.")

        # Reset state
        self._reset()

        # Get minimum length across all symbols
        min_len = min(len(df) for df in self._data.values())

        logger.info(f"Running backtest for {min_len} periods")

        for i in range(min_len):
            self._current_idx = i

            # Get current data slice
            current_data = {
                symbol: df.iloc[: i + 1]
                for symbol, df in self._data.items()
            }

            # Get current prices
            current_prices = {
                symbol: df.iloc[i]["close"]
                for symbol, df in self._data.items()
            }

            # Get timestamp
            timestamp = list(self._data.values())[0].index[i]

            # Update position PnLs
            self._update_positions(current_prices)

            # Get strategy signals
            try:
                signals = strategy(current_data, self._positions.copy())
            except Exception as e:
                logger.error(f"Strategy error at {timestamp}: {e}")
                signals = {}

            # Execute signals
            for symbol, target_position in signals.items():
                if symbol in current_prices:
                    self._execute_signal(
                        symbol=symbol,
                        target_position=target_position,
                        price=current_prices[symbol],
                        timestamp=timestamp,
                    )

            # Update equity
            self._update_equity(current_prices, timestamp)

        # Close all positions at end
        final_prices = {
            symbol: df.iloc[-1]["close"]
            for symbol, df in self._data.items()
        }
        final_timestamp = list(self._data.values())[0].index[-1]

        for symbol in list(self._positions.keys()):
            self._close_position(symbol, final_prices[symbol], final_timestamp)

        # Generate results
        return self._generate_results()

    def _reset(self) -> None:
        """Reset backtest state."""
        self._equity = self.config.initial_capital
        self._cash = self.config.initial_capital
        self._positions = {}
        self._trades = []
        self._equity_curve = []

    def _update_positions(self, prices: dict[str, float]) -> None:
        """Update position unrealized PnLs."""
        for symbol, pos in self._positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                entry_price = pos["entry_price"]
                quantity = pos["quantity"]

                if pos["side"] == "long":
                    pos["unrealized_pnl"] = (current_price - entry_price) * quantity
                else:
                    pos["unrealized_pnl"] = (entry_price - current_price) * quantity

    def _update_equity(self, prices: dict[str, float], timestamp: datetime) -> None:
        """Update total equity."""
        position_value = sum(
            pos.get("unrealized_pnl", 0)
            for pos in self._positions.values()
        )
        self._equity = self._cash + position_value
        self._equity_curve.append((timestamp, self._equity))

    def _execute_signal(
        self,
        symbol: str,
        target_position: float,
        price: float,
        timestamp: datetime,
    ) -> None:
        """Execute position change signal."""
        # Clamp to -1, 1
        target_position = max(-1, min(1, target_position))

        current_pos = self._positions.get(symbol, {})
        current_quantity = current_pos.get("quantity", 0)
        current_side = current_pos.get("side", None)

        # Calculate current position as fraction
        if current_side == "long":
            current_fraction = current_quantity * price / self.config.initial_capital
        elif current_side == "short":
            current_fraction = -current_quantity * price / self.config.initial_capital
        else:
            current_fraction = 0

        # Calculate position change needed
        change = target_position - current_fraction

        if abs(change) < 0.01:  # Minimum change threshold
            return

        # Calculate new position size
        target_notional = abs(target_position) * self.config.initial_capital
        target_quantity = target_notional / price if price > 0 else 0

        # Close existing position if changing sides or reducing
        if current_quantity > 0:
            if (current_side == "long" and target_position <= 0) or \
               (current_side == "short" and target_position >= 0):
                self._close_position(symbol, price, timestamp)
                current_quantity = 0
                current_side = None

        # Open or adjust position
        if target_position > 0:
            if current_side != "long":
                self._open_position(symbol, "long", target_quantity, price, timestamp)
            elif target_quantity > current_quantity:
                # Add to position
                add_qty = target_quantity - current_quantity
                self._add_to_position(symbol, add_qty, price)
        elif target_position < 0:
            if current_side != "short":
                self._open_position(symbol, "short", target_quantity, price, timestamp)
            elif target_quantity > current_quantity:
                add_qty = target_quantity - current_quantity
                self._add_to_position(symbol, add_qty, price)

    def _open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        timestamp: datetime,
    ) -> None:
        """Open a new position."""
        # Apply slippage
        if side == "long":
            fill_price = price * (1 + self.config.slippage)
        else:
            fill_price = price * (1 - self.config.slippage)

        # Calculate fees
        notional = quantity * fill_price
        fees = notional * self.config.taker_fee

        self._cash -= fees

        self._positions[symbol] = {
            "side": side,
            "quantity": quantity,
            "entry_price": fill_price,
            "entry_time": timestamp,
            "unrealized_pnl": 0,
            "fees_paid": fees,
        }

        logger.debug(
            f"Opened {side} position",
            symbol=symbol,
            quantity=quantity,
            price=fill_price,
        )

    def _add_to_position(self, symbol: str, quantity: float, price: float) -> None:
        """Add to existing position."""
        pos = self._positions[symbol]

        # Apply slippage
        if pos["side"] == "long":
            fill_price = price * (1 + self.config.slippage)
        else:
            fill_price = price * (1 - self.config.slippage)

        # Calculate new average entry
        old_notional = pos["quantity"] * pos["entry_price"]
        add_notional = quantity * fill_price
        total_quantity = pos["quantity"] + quantity

        pos["entry_price"] = (old_notional + add_notional) / total_quantity
        pos["quantity"] = total_quantity

        # Fees
        fees = add_notional * self.config.taker_fee
        pos["fees_paid"] += fees
        self._cash -= fees

    def _close_position(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
    ) -> None:
        """Close an existing position."""
        pos = self._positions.get(symbol)
        if not pos:
            return

        # Apply slippage
        if pos["side"] == "long":
            fill_price = price * (1 - self.config.slippage)
        else:
            fill_price = price * (1 + self.config.slippage)

        # Calculate PnL
        if pos["side"] == "long":
            pnl = (fill_price - pos["entry_price"]) * pos["quantity"]
        else:
            pnl = (pos["entry_price"] - fill_price) * pos["quantity"]

        # Exit fees
        exit_fees = pos["quantity"] * fill_price * self.config.taker_fee
        total_fees = pos["fees_paid"] + exit_fees
        pnl -= exit_fees

        self._cash += pnl

        # Record trade
        entry_notional = pos["quantity"] * pos["entry_price"]
        pnl_pct = (pnl / entry_notional) * 100 if entry_notional > 0 else 0

        trade = BacktestTrade(
            symbol=symbol,
            side=pos["side"],
            entry_time=pos["entry_time"],
            entry_price=pos["entry_price"],
            exit_time=timestamp,
            exit_price=fill_price,
            quantity=pos["quantity"],
            pnl=pnl,
            pnl_pct=pnl_pct,
            fees=total_fees,
        )
        self._trades.append(trade)

        del self._positions[symbol]

        logger.debug(
            f"Closed position",
            symbol=symbol,
            pnl=pnl,
            pnl_pct=pnl_pct,
        )

    def _generate_results(self) -> BacktestResults:
        """Generate backtest results."""
        return BacktestResults(
            initial_capital=self.config.initial_capital,
            final_equity=self._equity,
            trades=self._trades,
            equity_curve=self._equity_curve,
            config=self.config,
        )


def run_walk_forward(
    settings: Settings,
    data: dict[str, pd.DataFrame],
    strategy: Callable,
    n_splits: int = 5,
    train_ratio: float = 0.7,
) -> list[BacktestResults]:
    """
    Run walk-forward validation.

    Args:
        settings: Trading settings
        data: OHLCV data
        strategy: Strategy function
        n_splits: Number of walk-forward splits
        train_ratio: Ratio of data for training in each split

    Returns:
        List of BacktestResults for each split
    """
    results = []

    # Get minimum length
    min_len = min(len(df) for df in data.values())
    split_size = min_len // n_splits

    for i in range(n_splits):
        # Calculate split indices
        test_start = i * split_size
        test_end = (i + 1) * split_size if i < n_splits - 1 else min_len

        # Split data
        test_data = {
            symbol: df.iloc[test_start:test_end]
            for symbol, df in data.items()
        }

        # Run backtest on test split
        engine = BacktestEngine(settings)
        engine.load_data(test_data)
        result = engine.run(strategy)
        results.append(result)

        logger.info(
            f"Walk-forward split {i + 1}/{n_splits}",
            sharpe=result.sharpe_ratio,
            return_pct=result.total_return_pct,
        )

    return results
