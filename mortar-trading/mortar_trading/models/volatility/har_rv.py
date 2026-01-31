"""
HAR-RV Volatility Model
=======================

Heterogeneous Autoregressive model of Realized Volatility.

Uses daily, weekly, and monthly realized variance components to forecast
future volatility. Well-suited for multi-horizon volatility prediction.

Key insight for crypto: Positive semivariance (upside volatility) predicts
future volatility better than negative semivariance (opposite of equities).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class HARForecast:
    """HAR-RV model forecast result."""

    rv_daily: float
    rv_weekly: float
    rv_monthly: float
    forecast_1day: float
    forecast_5day: float
    forecast_22day: float
    positive_semivariance: float
    negative_semivariance: float
    model_r2: float
    timestamp: str


class HARRVModel:
    """
    Heterogeneous Autoregressive Realized Volatility model.

    HAR-RV captures different trading horizons:
    - Daily (RV_d): Short-term traders
    - Weekly (RV_w): Medium-term traders
    - Monthly (RV_m): Long-term traders

    Extended with realized semivariances for asymmetric effects:
    - RS+: Realized semivariance from positive returns
    - RS-: Realized semivariance from negative returns

    For crypto, RS+ is often more predictive than RS-.

    Model specification:
    RV_{t+h} = β₀ + β₁ RV_d + β₂ RV_w + β₃ RV_m + ε
    """

    def __init__(
        self,
        lags: list[int] | None = None,
        include_semivariances: bool = True,
        include_jumps: bool = False,
    ):
        self.lags = lags or [1, 5, 22]  # Daily, weekly, monthly
        self.include_semivariances = include_semivariances
        self.include_jumps = include_jumps

        self._coefficients: dict[str, float] = {}
        self._r2: float = 0.0
        self._fitted = False

    def calculate_realized_variance(
        self,
        returns: pd.Series,
        window: int = 1,
    ) -> pd.Series:
        """
        Calculate realized variance over rolling window.

        Args:
            returns: Return series
            window: Number of periods in window

        Returns:
            Realized variance series
        """
        # Realized variance is sum of squared returns
        return (returns ** 2).rolling(window).sum()

    def calculate_semivariances(
        self,
        returns: pd.Series,
        window: int = 22,
    ) -> tuple[pd.Series, pd.Series]:
        """
        Calculate realized semivariances.

        Args:
            returns: Return series
            window: Rolling window size

        Returns:
            Tuple of (positive_semivariance, negative_semivariance)
        """
        positive_returns = returns.where(returns > 0, 0)
        negative_returns = returns.where(returns < 0, 0)

        rs_positive = (positive_returns ** 2).rolling(window).sum()
        rs_negative = (negative_returns ** 2).rolling(window).sum()

        return rs_positive, rs_negative

    def calculate_jump_component(
        self,
        returns: pd.Series,
        window: int = 22,
    ) -> pd.Series:
        """
        Calculate jump component using bipower variation.

        Jump = max(RV - BV, 0)
        where BV is bipower variation.
        """
        abs_returns = returns.abs()

        # Bipower variation: E[|r_t| * |r_{t-1}|] * (π/2)
        bv = (abs_returns * abs_returns.shift(1)).rolling(window).sum() * (np.pi / 2)
        rv = (returns ** 2).rolling(window).sum()

        jump = (rv - bv).clip(lower=0)
        return jump

    def prepare_features(self, returns: pd.Series) -> pd.DataFrame:
        """
        Prepare feature matrix for HAR-RV model.

        Args:
            returns: Return series

        Returns:
            DataFrame with HAR-RV features
        """
        features = pd.DataFrame(index=returns.index)

        # Realized variance at different horizons
        for lag in self.lags:
            rv = self.calculate_realized_variance(returns, lag)
            features[f"rv_{lag}"] = rv

        # Semivariances
        if self.include_semivariances:
            rs_pos, rs_neg = self.calculate_semivariances(returns)
            features["rs_positive"] = rs_pos
            features["rs_negative"] = rs_neg

        # Jump component
        if self.include_jumps:
            features["jump"] = self.calculate_jump_component(returns)

        return features

    def fit(
        self,
        returns: pd.Series,
        forecast_horizon: int = 1,
    ) -> dict[str, Any]:
        """
        Fit HAR-RV model using OLS.

        Args:
            returns: Return series
            forecast_horizon: Horizon to forecast (default 1 day)

        Returns:
            Dictionary with model results
        """
        try:
            from sklearn.linear_model import LinearRegression
            from sklearn.metrics import r2_score

            # Prepare features
            features = self.prepare_features(returns)

            # Target: Future realized variance
            target = self.calculate_realized_variance(returns, forecast_horizon).shift(-forecast_horizon)

            # Align data
            data = pd.concat([features, target.rename("target")], axis=1).dropna()

            if len(data) < 50:
                raise ValueError("Insufficient data for HAR-RV fitting")

            X = data.drop("target", axis=1)
            y = data["target"]

            # Fit linear regression
            model = LinearRegression()
            model.fit(X, y)

            # Store coefficients
            self._coefficients = dict(zip(X.columns, model.coef_))
            self._coefficients["intercept"] = model.intercept_
            self._r2 = r2_score(y, model.predict(X))
            self._fitted = True

            logger.info(
                "HAR-RV model fitted",
                samples=len(data),
                r2=self._r2,
                features=list(X.columns),
            )

            return {
                "coefficients": self._coefficients,
                "r2": self._r2,
                "feature_importance": dict(
                    sorted(
                        zip(X.columns, np.abs(model.coef_)),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                ),
            }

        except ImportError:
            logger.warning("sklearn not installed, using fallback")
            return self._fallback_fit(returns)
        except Exception as e:
            logger.error(f"HAR-RV fitting error: {e}")
            return self._fallback_fit(returns)

    def _fallback_fit(self, returns: pd.Series) -> dict[str, Any]:
        """Fallback using simple averages."""
        self._coefficients = {
            "rv_1": 0.3,
            "rv_5": 0.4,
            "rv_22": 0.3,
            "intercept": 0,
        }
        self._r2 = 0
        self._fitted = True

        return {
            "coefficients": self._coefficients,
            "r2": 0,
            "feature_importance": {},
        }

    def forecast(self, returns: pd.Series) -> HARForecast:
        """
        Generate volatility forecast.

        Args:
            returns: Return series (should include recent data)

        Returns:
            HARForecast with predictions
        """
        from datetime import datetime

        if not self._fitted:
            self.fit(returns)

        # Calculate current features
        features = self.prepare_features(returns)
        latest = features.iloc[-1]

        # Generate forecast using fitted coefficients
        forecast_rv = self._coefficients.get("intercept", 0)

        for feature, coef in self._coefficients.items():
            if feature != "intercept" and feature in latest:
                forecast_rv += coef * latest[feature]

        # Convert to volatility
        forecast_vol = np.sqrt(forecast_rv) if forecast_rv > 0 else 0

        # Multi-horizon forecasts (simple scaling)
        rv_daily = latest.get("rv_1", 0)
        rv_weekly = latest.get("rv_5", 0)
        rv_monthly = latest.get("rv_22", 0)

        rs_pos = latest.get("rs_positive", 0)
        rs_neg = latest.get("rs_negative", 0)

        return HARForecast(
            rv_daily=rv_daily,
            rv_weekly=rv_weekly,
            rv_monthly=rv_monthly,
            forecast_1day=forecast_vol,
            forecast_5day=forecast_vol * np.sqrt(5),  # Approximate scaling
            forecast_22day=forecast_vol * np.sqrt(22),
            positive_semivariance=rs_pos,
            negative_semivariance=rs_neg,
            model_r2=self._r2,
            timestamp=datetime.utcnow().isoformat(),
        )

    def get_volatility_decomposition(self, returns: pd.Series) -> dict[str, float]:
        """
        Decompose volatility into components.

        Returns:
            Dictionary with volatility breakdown
        """
        features = self.prepare_features(returns)
        latest = features.iloc[-1]

        total_rv = latest.get("rv_22", 0)
        rs_pos = latest.get("rs_positive", 0)
        rs_neg = latest.get("rs_negative", 0)

        return {
            "total_realized_variance": total_rv,
            "upside_variance": rs_pos,
            "downside_variance": rs_neg,
            "asymmetry_ratio": rs_pos / rs_neg if rs_neg > 0 else 1,
            "jump_component": latest.get("jump", 0) if self.include_jumps else 0,
            "continuous_component": total_rv - latest.get("jump", 0),
        }

    def check_crypto_asymmetry(self, returns: pd.Series) -> dict[str, Any]:
        """
        Check for crypto-specific volatility asymmetry.

        In crypto, upside volatility often predicts future vol better than downside.
        """
        features = self.prepare_features(returns)

        # Correlation of semivariances with future RV
        future_rv = self.calculate_realized_variance(returns, 1).shift(-1)

        data = pd.concat([features, future_rv.rename("future_rv")], axis=1).dropna()

        if len(data) < 50:
            return {"insufficient_data": True}

        corr_positive = data["rs_positive"].corr(data["future_rv"])
        corr_negative = data["rs_negative"].corr(data["future_rv"])

        return {
            "correlation_upside_rv": corr_positive,
            "correlation_downside_rv": corr_negative,
            "upside_more_predictive": corr_positive > corr_negative,
            "is_crypto_typical": corr_positive > corr_negative,  # Common in crypto
            "interpretation": (
                "Upside volatility is more predictive (typical for crypto)"
                if corr_positive > corr_negative
                else "Downside volatility is more predictive (typical for equities)"
            ),
        }
