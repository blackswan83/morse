"""
Mortar Trading CLI
==================

Command-line interface for the trading bot.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    import logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )


async def run_live(args: argparse.Namespace) -> None:
    """Run live trading."""
    from mortar_trading.config import get_settings
    from mortar_trading.core import TradingEngine

    logger = structlog.get_logger(__name__)
    logger.info("Starting live trading mode")

    settings = get_settings()
    engine = TradingEngine(settings)

    try:
        await engine.initialize()
        await engine.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await engine.stop()


async def run_paper(args: argparse.Namespace) -> None:
    """Run paper trading."""
    from mortar_trading.config import get_settings, Environment
    from mortar_trading.core import TradingEngine

    logger = structlog.get_logger(__name__)
    logger.info("Starting paper trading mode")

    settings = get_settings()
    settings.environment = Environment.PAPER
    settings.exchange.testnet = True

    engine = TradingEngine(settings)

    try:
        await engine.initialize()
        await engine.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await engine.stop()


def run_backtest(args: argparse.Namespace) -> None:
    """Run backtesting."""
    from mortar_trading.config import get_settings
    from mortar_trading.backtest import BacktestEngine, BacktestConfig

    logger = structlog.get_logger(__name__)
    logger.info("Running backtest")

    settings = get_settings()

    config = BacktestConfig(
        start_date=args.start or settings.backtest.start_date,
        end_date=args.end or settings.backtest.end_date,
        initial_capital=args.capital or settings.backtest.initial_capital,
        symbols=args.symbols.split(",") if args.symbols else settings.symbols.primary,
    )

    engine = BacktestEngine(settings, config)

    # Load data (would need actual data loading here)
    logger.info("Backtest engine created. Load data and run with engine.run(strategy)")

    print("\nBacktest Configuration:")
    print(f"  Start Date: {config.start_date}")
    print(f"  End Date: {config.end_date}")
    print(f"  Initial Capital: ${config.initial_capital:,.2f}")
    print(f"  Symbols: {config.symbols}")


def show_status(args: argparse.Namespace) -> None:
    """Show current system status."""
    from mortar_trading.config import get_settings

    settings = get_settings()

    print("\nMortar Trading Status")
    print("=" * 40)
    print(f"Environment: {settings.environment.value}")
    print(f"Exchange: {settings.exchange.name}")
    print(f"Testnet: {settings.exchange.testnet}")
    print(f"Symbols: {', '.join(settings.symbols.primary)}")
    print(f"\nRisk Limits:")
    print(f"  Max Leverage: {settings.risk.max_leverage}x")
    print(f"  Position Risk: {settings.risk.single_position_risk_pct}%")
    print(f"  Daily Loss Limit: {settings.risk.daily_loss_limit_pct}%")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Mortar Trading - Crypto Volatility Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mortar live          Run live trading
  mortar paper         Run paper trading (testnet)
  mortar backtest      Run backtesting
  mortar status        Show system status

For more information, see: https://github.com/mortar-trading/mortar-trading
        """,
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Live trading
    live_parser = subparsers.add_parser("live", help="Run live trading")
    live_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without executing trades",
    )

    # Paper trading
    paper_parser = subparsers.add_parser("paper", help="Run paper trading")

    # Backtesting
    backtest_parser = subparsers.add_parser("backtest", help="Run backtesting")
    backtest_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    backtest_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    backtest_parser.add_argument("--capital", type=float, help="Initial capital")
    backtest_parser.add_argument("--symbols", help="Comma-separated symbols")

    # Status
    status_parser = subparsers.add_parser("status", help="Show system status")

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    # Run command
    if args.command == "live":
        asyncio.run(run_live(args))
    elif args.command == "paper":
        asyncio.run(run_paper(args))
    elif args.command == "backtest":
        run_backtest(args)
    elif args.command == "status":
        show_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
