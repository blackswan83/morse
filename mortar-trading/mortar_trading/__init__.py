"""
Mortar Trading - Crypto Volatility Trading Bot
===============================================

A hierarchical multi-timeframe trading system combining:
- Sentiment analysis (Macro layer)
- Volatility forecasting (Meso layer)
- Order flow execution (Micro layer)

Architecture:
    MACRO (Daily/4H) -> Directional bias from sentiment + on-chain
    MESO  (1H/15M)   -> Trade setup from volatility + regime
    MICRO (5M/1M)    -> Entry/exit execution from order flow
"""

__version__ = "0.1.0"
__author__ = "Mortar Trading Team"

from mortar_trading.config import Settings, get_settings
from mortar_trading.core import TradingEngine

__all__ = [
    "Settings",
    "get_settings",
    "TradingEngine",
    "__version__",
]
