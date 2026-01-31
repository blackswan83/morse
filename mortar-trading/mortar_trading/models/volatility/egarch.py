"""
EGARCH Volatility Model
=======================

Exponential GARCH model for volatility forecasting.

Key insight for crypto: Shows inverse leverage effects - positive returns
increase volatility via FOMO (opposite of equities where negative returns
increase volatility more).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EGARCHForecast:
    """EGARCH model forecast result."""

    conditional_volatility: float
    forecast_1step: float
    forecast_5step: float
    forecast_10step: float
    model_params: dict[str, float]
    timestamp: str


class EGARCHModel:
    """
    EGARCH(p,q) model for volatility forecasting.

    The EGARCH model captures:
    - Volatility clustering (high vol follows high vol)
    - Asymmetric effects (leverage effects)
    - Log volatility (ensures positivity)

    For crypto, we often see positive leverage effects:
    - Positive returns -> increased volatility (FOMO)
    - Negative returns -> less extreme volatility increase

    Model specification:
    log(σ²_t) = ω + Σ αᵢ g(z_{t-i}) + Σ βⱼ log(σ²_{t-j})

    where g(z) = θz + γ(|z| - E|z|)
    """

    def __init__(
        self,
        p: int = 1,
        q: int = 1,
        dist: str = "studentst",  # Normal, studentst, skewstudent
        mean: str = "Zero",  # Zero, Constant, AR
    ):
        self.p = p
        self.q = q
        self.dist = dist
        self.mean = mean
        self._model = None
        self._fit_result = None
        self._last_returns = None

    def fit(self, returns: pd.Series | np.ndarray) -> dict[str, Any]:
        """
        Fit EGARCH model to return series.

        Args:
            returns: Return series (log returns recommended)

        Returns:
            Dictionary with model parameters and diagnostics
        """
        try:
            from arch import arch_model

            # Convert to pandas Series if needed
            if isinstance(returns, np.ndarray):
                returns = pd.Series(returns)

            # Remove NaN values
            returns = returns.dropna()

            if len(returns) < 100:
                raise ValueError("Insufficient data for EGARCH fitting")

            # Store for forecasting
            self._last_returns = returns

            # Create EGARCH model
            self._model = arch_model(
                returns * 100,  # Scale for numerical stability
                vol="EGARCH",
                p=self.p,
                q=self.q,
                dist=self.dist,
                mean=self.mean,
            )

            # Fit model
            self._fit_result = self._model.fit(disp="off", show_warning=False)

            # Extract parameters
            params = {
                "omega": self._fit_result.params.get("omega", 0),
                "alpha": self._fit_result.params.get("alpha[1]", 0),
                "gamma": self._fit_result.params.get("gamma[1]", 0),  # Asymmetry
                "beta": self._fit_result.params.get("beta[1]", 0),
            }

            # Add distribution parameters if present
            if "nu" in self._fit_result.params:
                params["nu"] = self._fit_result.params["nu"]  # Degrees of freedom
            if "lambda" in self._fit_result.params:
                params["lambda"] = self._fit_result.params["lambda"]  # Skewness

            logger.info(
                "EGARCH model fitted",
                samples=len(returns),
                aic=self._fit_result.aic,
                bic=self._fit_result.bic,
            )

            return {
                "params": params,
                "aic": self._fit_result.aic,
                "bic": self._fit_result.bic,
                "log_likelihood": self._fit_result.loglikelihood,
                "conditional_volatility": self._fit_result.conditional_volatility / 100,
            }

        except ImportError:
            logger.warning("arch package not installed, using fallback")
            return self._fallback_fit(returns)
        except Exception as e:
            logger.error(f"EGARCH fitting error: {e}")
            return self._fallback_fit(returns)

    def _fallback_fit(self, returns: pd.Series) -> dict[str, Any]:
        """Fallback volatility estimation using rolling std."""
        if isinstance(returns, np.ndarray):
            returns = pd.Series(returns)

        returns = returns.dropna()
        self._last_returns = returns

        # Simple rolling volatility as fallback
        vol = returns.rolling(20).std() * np.sqrt(252)

        return {
            "params": {"omega": 0, "alpha": 0.1, "gamma": 0, "beta": 0.85},
            "aic": 0,
            "bic": 0,
            "log_likelihood": 0,
            "conditional_volatility": vol,
        }

    def forecast(
        self,
        horizon: int = 10,
        returns: pd.Series | None = None,
    ) -> EGARCHForecast:
        """
        Forecast volatility for future periods.

        Args:
            horizon: Number of periods to forecast
            returns: Optional new return data

        Returns:
            EGARCHForecast with predictions
        """
        from datetime import datetime

        if returns is not None:
            self.fit(returns)

        if self._fit_result is not None:
            try:
                # Generate forecast
                forecast = self._fit_result.forecast(horizon=horizon)
                variance_forecast = forecast.variance.iloc[-1].values / 10000  # Unscale

                current_vol = self._fit_result.conditional_volatility.iloc[-1] / 100

                return EGARCHForecast(
                    conditional_volatility=current_vol,
                    forecast_1step=np.sqrt(variance_forecast[0]) if len(variance_forecast) > 0 else current_vol,
                    forecast_5step=np.sqrt(variance_forecast[4]) if len(variance_forecast) > 4 else current_vol,
                    forecast_10step=np.sqrt(variance_forecast[9]) if len(variance_forecast) > 9 else current_vol,
                    model_params=dict(self._fit_result.params),
                    timestamp=datetime.utcnow().isoformat(),
                )

            except Exception as e:
                logger.warning(f"EGARCH forecast error: {e}")

        # Fallback
        if self._last_returns is not None:
            vol = self._last_returns.std() * np.sqrt(252)
        else:
            vol = 0.5  # Default 50% annualized vol

        return EGARCHForecast(
            conditional_volatility=vol,
            forecast_1step=vol,
            forecast_5step=vol,
            forecast_10step=vol,
            model_params={},
            timestamp=datetime.utcnow().isoformat(),
        )

    def get_conditional_volatility(self) -> pd.Series | None:
        """Get the fitted conditional volatility series."""
        if self._fit_result is not None:
            return self._fit_result.conditional_volatility / 100
        return None

    def get_standardized_residuals(self) -> pd.Series | None:
        """Get standardized residuals for diagnostics."""
        if self._fit_result is not None:
            return self._fit_result.std_resid
        return None

    def check_leverage_effect(self) -> dict[str, Any]:
        """
        Check for leverage effect in the fitted model.

        In crypto, we often see positive gamma (inverse leverage):
        - gamma > 0: Positive returns increase volatility more
        - gamma < 0: Negative returns increase volatility more (traditional)
        """
        if self._fit_result is None:
            return {"gamma": 0, "interpretation": "Model not fitted"}

        gamma = self._fit_result.params.get("gamma[1]", 0)

        if gamma > 0.1:
            interpretation = "Strong positive leverage (FOMO effect)"
        elif gamma > 0:
            interpretation = "Mild positive leverage"
        elif gamma > -0.1:
            interpretation = "No significant leverage effect"
        else:
            interpretation = "Negative leverage (fear effect)"

        return {
            "gamma": gamma,
            "interpretation": interpretation,
            "is_crypto_typical": gamma > 0,  # Crypto often shows positive
        }


class GJRGARCHModel:
    """
    GJR-GARCH model as alternative to EGARCH.

    Also captures asymmetric volatility but with different specification.
    Useful for comparison and ensemble.
    """

    def __init__(self, p: int = 1, o: int = 1, q: int = 1, dist: str = "studentst"):
        self.p = p
        self.o = o
        self.q = q
        self.dist = dist
        self._model = None
        self._fit_result = None

    def fit(self, returns: pd.Series) -> dict[str, Any]:
        """Fit GJR-GARCH model."""
        try:
            from arch import arch_model

            returns = returns.dropna()

            self._model = arch_model(
                returns * 100,
                vol="GARCH",
                p=self.p,
                o=self.o,
                q=self.q,
                dist=self.dist,
            )

            self._fit_result = self._model.fit(disp="off", show_warning=False)

            return {
                "params": dict(self._fit_result.params),
                "aic": self._fit_result.aic,
                "bic": self._fit_result.bic,
                "conditional_volatility": self._fit_result.conditional_volatility / 100,
            }

        except Exception as e:
            logger.error(f"GJR-GARCH error: {e}")
            return {"params": {}, "conditional_volatility": returns.rolling(20).std()}
