"""
Volatility Engine
=================

Main volatility analysis engine coordinating all models.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.models.volatility.egarch import EGARCHModel
from mortar_trading.models.volatility.har_rv import HARRVModel
from mortar_trading.models.volatility.ml_ensemble import MLVolatilityEnsemble, VolatilityRegimeClassifier

logger = structlog.get_logger(__name__)


class VolatilityEngine:
    """
    Main volatility analysis engine.

    Coordinates:
    - EGARCH for conditional volatility
    - HAR-RV for multi-horizon forecasts
    - ML ensemble for feature-rich predictions
    - Regime classification

    Publishes volatility updates and regime changes to event bus.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()

        # Initialize models
        vol_config = settings.volatility

        self.egarch = EGARCHModel(
            p=vol_config.egarch.p,
            q=vol_config.egarch.q,
            dist=vol_config.egarch.dist,
        ) if vol_config.egarch.enabled else None

        self.har_rv = HARRVModel(
            lags=vol_config.har_rv.lags,
            include_semivariances=True,
        ) if vol_config.har_rv.enabled else None

        self.ml_ensemble = MLVolatilityEnsemble(
            models=vol_config.ml_ensemble.models,
            features_window=vol_config.ml_ensemble.features_window,
        ) if vol_config.ml_ensemble.enabled else None

        self.regime_classifier = VolatilityRegimeClassifier()

        # Data storage
        self._returns: dict[str, pd.Series] = {}
        self._candle_data: dict[str, pd.DataFrame] = {}
        self._current_regime: dict[str, str] = {}
        self._last_update: dict[str, datetime] = {}

        self._running = False

    async def start(self) -> None:
        """Start the volatility engine."""
        logger.info("Starting volatility engine")
        self._running = True

    async def stop(self) -> None:
        """Stop the volatility engine."""
        logger.info("Stopping volatility engine")
        self._running = False

    async def update(self) -> None:
        """
        Update volatility estimates for all symbols.

        Called periodically by the main engine.
        """
        if not self._running:
            return

        for symbol in self.settings.symbols.all_symbols:
            try:
                await self._update_symbol(symbol)
            except Exception as e:
                logger.error(f"Volatility update error for {symbol}", error=str(e))

    async def process_candle(self, candle: dict[str, Any]) -> None:
        """
        Process incoming candle data.

        Args:
            candle: Candle data dictionary
        """
        symbol = candle.get("symbol")
        if not symbol:
            return

        # Initialize storage if needed
        if symbol not in self._candle_data:
            self._candle_data[symbol] = pd.DataFrame()
            self._returns[symbol] = pd.Series(dtype=float)

        # Add candle to storage
        timestamp = candle.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        new_row = pd.DataFrame([{
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
        }], index=[timestamp])

        self._candle_data[symbol] = pd.concat([
            self._candle_data[symbol],
            new_row,
        ]).tail(5000)  # Keep last 5000 candles

        # Calculate returns
        close = self._candle_data[symbol]["close"]
        returns = np.log(close / close.shift(1))
        self._returns[symbol] = returns.dropna()

    async def _update_symbol(self, symbol: str) -> None:
        """Update volatility for a single symbol."""
        returns = self._returns.get(symbol)

        if returns is None or len(returns) < 100:
            return

        # Check if we've updated recently (throttle updates)
        now = datetime.utcnow()
        last = self._last_update.get(symbol)
        if last and (now - last).seconds < 60:  # At most once per minute
            return

        self._last_update[symbol] = now

        # Get candle data for additional features
        candles = self._candle_data.get(symbol)

        # Calculate forecasts from each model
        forecasts = {}

        # EGARCH
        if self.egarch:
            egarch_result = self.egarch.fit(returns)
            egarch_forecast = self.egarch.forecast()
            forecasts["egarch"] = {
                "current_vol": egarch_forecast.conditional_volatility,
                "forecast_1": egarch_forecast.forecast_1step,
                "forecast_5": egarch_forecast.forecast_5step,
                "params": egarch_forecast.model_params,
            }

        # HAR-RV
        if self.har_rv:
            self.har_rv.fit(returns)
            har_forecast = self.har_rv.forecast(returns)
            forecasts["har_rv"] = {
                "rv_daily": har_forecast.rv_daily,
                "rv_weekly": har_forecast.rv_weekly,
                "rv_monthly": har_forecast.rv_monthly,
                "forecast_1": har_forecast.forecast_1day,
                "positive_semivar": har_forecast.positive_semivariance,
                "negative_semivar": har_forecast.negative_semivariance,
            }

        # ML Ensemble
        if self.ml_ensemble:
            ensemble_forecast = self.ml_ensemble.forecast(returns, candles)
            forecasts["ml_ensemble"] = {
                "forecast": ensemble_forecast.forecast,
                "xgb_forecast": ensemble_forecast.xgboost_forecast,
                "lgb_forecast": ensemble_forecast.lightgbm_forecast,
                "confidence": ensemble_forecast.confidence,
            }

        # Calculate combined volatility estimate
        vol_estimates = []
        weights = []

        if "egarch" in forecasts:
            vol_estimates.append(forecasts["egarch"]["current_vol"])
            weights.append(0.4)

        if "har_rv" in forecasts:
            vol_estimates.append(np.sqrt(forecasts["har_rv"]["rv_daily"]))
            weights.append(0.3)

        if "ml_ensemble" in forecasts:
            vol_estimates.append(forecasts["ml_ensemble"]["forecast"])
            weights.append(forecasts["ml_ensemble"]["confidence"] * 0.3)

        if vol_estimates:
            combined_vol = np.average(vol_estimates, weights=weights)
        else:
            combined_vol = returns.std() * np.sqrt(252)  # Annualized

        # Classify regime
        self.regime_classifier.fit(returns.rolling(20).std() * np.sqrt(252))
        new_regime = self.regime_classifier.classify(combined_vol)
        old_regime = self._current_regime.get(symbol)

        # Publish volatility update
        await self.event_bus.publish(
            Event(
                event_type=EventType.VOLATILITY_UPDATE,
                payload={
                    "symbol": symbol,
                    "volatility": combined_vol,
                    "forecasts": forecasts,
                    "regime": new_regime,
                    "timestamp": now.isoformat(),
                },
                symbol=symbol,
                source="volatility_engine",
            )
        )

        # Check for regime change
        if old_regime and old_regime != new_regime:
            await self.event_bus.publish(
                Event(
                    event_type=EventType.REGIME_CHANGE,
                    payload={
                        "symbol": symbol,
                        "old_regime": old_regime,
                        "new_regime": new_regime,
                        "volatility": combined_vol,
                        "timestamp": now.isoformat(),
                    },
                    symbol=symbol,
                    source="volatility_engine",
                )
            )
            logger.info(
                "Regime change",
                symbol=symbol,
                old=old_regime,
                new=new_regime,
            )

        self._current_regime[symbol] = new_regime

        # Check for volatility spike
        historical_vol = returns.rolling(100).std() * np.sqrt(252)
        vol_zscore = (combined_vol - historical_vol.mean()) / historical_vol.std()

        if vol_zscore > self.settings.monitoring.alerts.volatility_spike_multiplier:
            await self.event_bus.publish(
                Event(
                    event_type=EventType.VOLATILITY_SPIKE,
                    payload={
                        "symbol": symbol,
                        "volatility": combined_vol,
                        "zscore": vol_zscore,
                        "threshold": self.settings.monitoring.alerts.volatility_spike_multiplier,
                        "timestamp": now.isoformat(),
                    },
                    symbol=symbol,
                    source="volatility_engine",
                )
            )

    def get_current_volatility(self, symbol: str) -> dict[str, Any]:
        """Get current volatility estimate for a symbol."""
        returns = self._returns.get(symbol)
        if returns is None or len(returns) < 20:
            return {"volatility": None, "regime": "unknown"}

        current_vol = returns.rolling(20).std().iloc[-1] * np.sqrt(252)
        regime = self._current_regime.get(symbol, "unknown")

        return {
            "volatility": current_vol,
            "regime": regime,
            "returns_count": len(returns),
        }

    def get_volatility_forecast(
        self,
        symbol: str,
        horizon: int = 1,
    ) -> dict[str, Any]:
        """Get volatility forecast for a symbol."""
        returns = self._returns.get(symbol)
        candles = self._candle_data.get(symbol)

        if returns is None or len(returns) < 100:
            return {"forecast": None, "confidence": 0}

        forecasts = {}

        if self.egarch:
            egarch_forecast = self.egarch.forecast(horizon=horizon, returns=returns)
            forecasts["egarch"] = egarch_forecast.forecast_1step

        if self.har_rv:
            har_forecast = self.har_rv.forecast(returns)
            forecasts["har_rv"] = har_forecast.forecast_1day

        if self.ml_ensemble:
            ml_forecast = self.ml_ensemble.forecast(returns, candles)
            forecasts["ml"] = ml_forecast.forecast

        if forecasts:
            combined = np.mean(list(forecasts.values()))
            confidence = 1 - (np.std(list(forecasts.values())) / (combined + 1e-10))
        else:
            combined = returns.std() * np.sqrt(252)
            confidence = 0.3

        return {
            "forecast": combined,
            "forecasts": forecasts,
            "confidence": max(0, min(1, confidence)),
            "horizon": horizon,
        }

    def get_leverage_effect(self, symbol: str) -> dict[str, Any]:
        """Analyze leverage effect for a symbol."""
        if not self.egarch:
            return {"gamma": 0, "interpretation": "EGARCH not enabled"}

        returns = self._returns.get(symbol)
        if returns is None or len(returns) < 100:
            return {"gamma": 0, "interpretation": "Insufficient data"}

        self.egarch.fit(returns)
        return self.egarch.check_leverage_effect()

    def get_semivariance_analysis(self, symbol: str) -> dict[str, Any]:
        """Analyze semivariance asymmetry for a symbol."""
        if not self.har_rv:
            return {"insufficient_data": True}

        returns = self._returns.get(symbol)
        if returns is None or len(returns) < 100:
            return {"insufficient_data": True}

        return self.har_rv.check_crypto_asymmetry(returns)
