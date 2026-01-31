"""
Backtest Results
================

Performance metrics and analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class BacktestResults:
    """Backtest performance results."""

    initial_capital: float
    final_equity: float
    trades: list
    equity_curve: list[tuple[datetime, float]]
    config: Any

    @property
    def total_return(self) -> float:
        """Total return in currency."""
        return self.final_equity - self.initial_capital

    @property
    def total_return_pct(self) -> float:
        """Total return as percentage."""
        return ((self.final_equity / self.initial_capital) - 1) * 100

    @property
    def num_trades(self) -> int:
        """Total number of trades."""
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        """Number of winning trades."""
        return len([t for t in self.trades if t.pnl > 0])

    @property
    def losing_trades(self) -> int:
        """Number of losing trades."""
        return len([t for t in self.trades if t.pnl < 0])

    @property
    def win_rate(self) -> float:
        """Win rate as percentage."""
        if self.num_trades == 0:
            return 0
        return (self.winning_trades / self.num_trades) * 100

    @property
    def avg_win(self) -> float:
        """Average winning trade."""
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        return np.mean(wins) if wins else 0

    @property
    def avg_loss(self) -> float:
        """Average losing trade."""
        losses = [t.pnl for t in self.trades if t.pnl < 0]
        return np.mean(losses) if losses else 0

    @property
    def profit_factor(self) -> float:
        """Profit factor (gross profit / gross loss)."""
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        return gross_profit / gross_loss if gross_loss > 0 else 0

    @property
    def max_drawdown(self) -> float:
        """Maximum drawdown as percentage."""
        if not self.equity_curve:
            return 0

        equities = [e[1] for e in self.equity_curve]
        peak = equities[0]
        max_dd = 0

        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd * 100

    @property
    def sharpe_ratio(self) -> float:
        """Annualized Sharpe ratio."""
        if len(self.equity_curve) < 2:
            return 0

        equities = np.array([e[1] for e in self.equity_curve])
        returns = np.diff(equities) / equities[:-1]

        if len(returns) == 0 or np.std(returns) == 0:
            return 0

        # Annualize (assuming hourly data)
        periods_per_year = 24 * 365
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        annualized_return = mean_return * periods_per_year
        annualized_std = std_return * np.sqrt(periods_per_year)

        return annualized_return / annualized_std if annualized_std > 0 else 0

    @property
    def sortino_ratio(self) -> float:
        """Annualized Sortino ratio."""
        if len(self.equity_curve) < 2:
            return 0

        equities = np.array([e[1] for e in self.equity_curve])
        returns = np.diff(equities) / equities[:-1]

        if len(returns) == 0:
            return 0

        # Downside deviation (only negative returns)
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0:
            return float("inf")  # No downside

        downside_std = np.std(negative_returns)
        if downside_std == 0:
            return 0

        periods_per_year = 24 * 365
        annualized_return = np.mean(returns) * periods_per_year
        annualized_downside = downside_std * np.sqrt(periods_per_year)

        return annualized_return / annualized_downside

    @property
    def calmar_ratio(self) -> float:
        """Calmar ratio (annual return / max drawdown)."""
        if self.max_drawdown == 0:
            return 0

        # Calculate annual return
        if len(self.equity_curve) < 2:
            return 0

        start_time = self.equity_curve[0][0]
        end_time = self.equity_curve[-1][0]
        days = (end_time - start_time).days

        if days == 0:
            return 0

        annual_return = (self.total_return_pct / 100) * (365 / days)
        return annual_return / (self.max_drawdown / 100)

    @property
    def total_fees(self) -> float:
        """Total fees paid."""
        return sum(t.fees for t in self.trades)

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "num_trades": self.num_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "total_fees": self.total_fees,
        }

    def summary(self) -> str:
        """Generate text summary of results."""
        return f"""
========================================
        BACKTEST RESULTS SUMMARY
========================================

Capital:
  Initial:        ${self.initial_capital:,.2f}
  Final:          ${self.final_equity:,.2f}
  Total Return:   ${self.total_return:,.2f} ({self.total_return_pct:+.2f}%)

Trades:
  Total:          {self.num_trades}
  Winners:        {self.winning_trades} ({self.win_rate:.1f}%)
  Losers:         {self.losing_trades}
  Average Win:    ${self.avg_win:,.2f}
  Average Loss:   ${self.avg_loss:,.2f}
  Profit Factor:  {self.profit_factor:.2f}

Risk Metrics:
  Max Drawdown:   {self.max_drawdown:.2f}%
  Sharpe Ratio:   {self.sharpe_ratio:.2f}
  Sortino Ratio:  {self.sortino_ratio:.2f}
  Calmar Ratio:   {self.calmar_ratio:.2f}

Costs:
  Total Fees:     ${self.total_fees:,.2f}

========================================
"""

    def check_targets(self) -> dict[str, bool]:
        """Check if results meet target thresholds."""
        targets = {
            "sharpe_ratio": self.sharpe_ratio >= 0.8,
            "max_drawdown": self.max_drawdown <= 20,
            "win_rate": self.win_rate >= 55,
            "profit_factor": self.profit_factor >= 1.5,
        }
        return targets
