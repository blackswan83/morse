"""
Metrics Collector
=================

Prometheus metrics for monitoring.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """
    Collects and exposes metrics for Prometheus.

    Metrics include:
    - Position metrics (count, value, PnL)
    - Order metrics (placed, filled, rejected)
    - Risk metrics (drawdown, heat, leverage)
    - Performance metrics (returns, Sharpe, etc.)
    """

    def __init__(self):
        self._metrics: dict[str, Any] = {}
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

        try:
            from prometheus_client import Counter, Gauge, Histogram, start_http_server

            # Order metrics
            self.orders_placed = Counter(
                "mortar_orders_placed_total",
                "Total orders placed",
                ["symbol", "side", "order_type"],
            )
            self.orders_filled = Counter(
                "mortar_orders_filled_total",
                "Total orders filled",
                ["symbol", "side"],
            )
            self.orders_rejected = Counter(
                "mortar_orders_rejected_total",
                "Total orders rejected",
                ["symbol", "reason"],
            )

            # Position metrics
            self.position_count = Gauge(
                "mortar_position_count",
                "Number of open positions",
            )
            self.position_value = Gauge(
                "mortar_position_value",
                "Total position value",
                ["symbol"],
            )
            self.unrealized_pnl = Gauge(
                "mortar_unrealized_pnl",
                "Unrealized PnL",
                ["symbol"],
            )

            # Risk metrics
            self.portfolio_heat = Gauge(
                "mortar_portfolio_heat",
                "Portfolio heat percentage",
            )
            self.max_drawdown = Gauge(
                "mortar_max_drawdown",
                "Maximum drawdown percentage",
            )
            self.current_leverage = Gauge(
                "mortar_current_leverage",
                "Current leverage",
            )

            # Performance metrics
            self.daily_return = Gauge(
                "mortar_daily_return",
                "Daily return percentage",
            )
            self.sharpe_ratio = Gauge(
                "mortar_sharpe_ratio",
                "Current Sharpe ratio",
            )

            # Volatility metrics
            self.market_volatility = Gauge(
                "mortar_market_volatility",
                "Market volatility",
                ["symbol"],
            )

            # Sentiment metrics
            self.sentiment_score = Gauge(
                "mortar_sentiment_score",
                "Sentiment score",
                ["symbol"],
            )

            # Trade duration histogram
            self.trade_duration = Histogram(
                "mortar_trade_duration_seconds",
                "Trade duration in seconds",
                buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 28800],
            )

            self._prometheus_available = True
            logger.info("Prometheus metrics initialized")

        except ImportError:
            logger.warning("prometheus_client not installed, using fallback metrics")
            self._prometheus_available = False

    def start_server(self, port: int = 9090) -> None:
        """Start Prometheus metrics server."""
        if self._prometheus_available:
            try:
                from prometheus_client import start_http_server
                start_http_server(port)
                logger.info(f"Prometheus metrics server started on port {port}")
            except Exception as e:
                logger.error(f"Failed to start metrics server: {e}")

    # Order metrics

    def record_order_placed(self, symbol: str, side: str, order_type: str) -> None:
        """Record order placed."""
        if self._prometheus_available:
            self.orders_placed.labels(symbol=symbol, side=side, order_type=order_type).inc()
        self._counters[f"orders_placed_{symbol}_{side}"] = (
            self._counters.get(f"orders_placed_{symbol}_{side}", 0) + 1
        )

    def record_order_filled(self, symbol: str, side: str) -> None:
        """Record order filled."""
        if self._prometheus_available:
            self.orders_filled.labels(symbol=symbol, side=side).inc()
        self._counters[f"orders_filled_{symbol}_{side}"] = (
            self._counters.get(f"orders_filled_{symbol}_{side}", 0) + 1
        )

    def record_order_rejected(self, symbol: str, reason: str) -> None:
        """Record order rejected."""
        if self._prometheus_available:
            self.orders_rejected.labels(symbol=symbol, reason=reason).inc()
        self._counters[f"orders_rejected_{symbol}"] = (
            self._counters.get(f"orders_rejected_{symbol}", 0) + 1
        )

    # Position metrics

    def update_position_count(self, count: int) -> None:
        """Update position count."""
        if self._prometheus_available:
            self.position_count.set(count)
        self._gauges["position_count"] = count

    def update_position_value(self, symbol: str, value: float) -> None:
        """Update position value."""
        if self._prometheus_available:
            self.position_value.labels(symbol=symbol).set(value)
        self._gauges[f"position_value_{symbol}"] = value

    def update_unrealized_pnl(self, symbol: str, pnl: float) -> None:
        """Update unrealized PnL."""
        if self._prometheus_available:
            self.unrealized_pnl.labels(symbol=symbol).set(pnl)
        self._gauges[f"unrealized_pnl_{symbol}"] = pnl

    # Risk metrics

    def update_portfolio_heat(self, heat: float) -> None:
        """Update portfolio heat."""
        if self._prometheus_available:
            self.portfolio_heat.set(heat)
        self._gauges["portfolio_heat"] = heat

    def update_max_drawdown(self, drawdown: float) -> None:
        """Update max drawdown."""
        if self._prometheus_available:
            self.max_drawdown.set(drawdown)
        self._gauges["max_drawdown"] = drawdown

    def update_leverage(self, leverage: float) -> None:
        """Update current leverage."""
        if self._prometheus_available:
            self.current_leverage.set(leverage)
        self._gauges["current_leverage"] = leverage

    # Performance metrics

    def update_daily_return(self, return_pct: float) -> None:
        """Update daily return."""
        if self._prometheus_available:
            self.daily_return.set(return_pct)
        self._gauges["daily_return"] = return_pct

    def update_sharpe_ratio(self, sharpe: float) -> None:
        """Update Sharpe ratio."""
        if self._prometheus_available:
            self.sharpe_ratio.set(sharpe)
        self._gauges["sharpe_ratio"] = sharpe

    # Market metrics

    def update_volatility(self, symbol: str, vol: float) -> None:
        """Update market volatility."""
        if self._prometheus_available:
            self.market_volatility.labels(symbol=symbol).set(vol)
        self._gauges[f"volatility_{symbol}"] = vol

    def update_sentiment(self, symbol: str, score: float) -> None:
        """Update sentiment score."""
        if self._prometheus_available:
            self.sentiment_score.labels(symbol=symbol).set(score)
        self._gauges[f"sentiment_{symbol}"] = score

    # Trade metrics

    def record_trade_duration(self, duration_seconds: float) -> None:
        """Record trade duration."""
        if self._prometheus_available:
            self.trade_duration.observe(duration_seconds)
        if "trade_durations" not in self._histograms:
            self._histograms["trade_durations"] = []
        self._histograms["trade_durations"].append(duration_seconds)

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics as dictionary."""
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": {k: list(v) for k, v in self._histograms.items()},
        }
