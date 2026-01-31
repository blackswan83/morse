"""
ML Volatility Ensemble
======================

Machine learning ensemble for volatility prediction.

Combines multiple models (XGBoost, LightGBM) with technical and
sentiment features for robust volatility forecasting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EnsembleForecast:
    """Ensemble volatility forecast result."""

    forecast: float
    xgboost_forecast: float
    lightgbm_forecast: float
    confidence: float
    feature_importance: dict[str, float]
    timestamp: str


class MLVolatilityEnsemble:
    """
    Machine learning ensemble for volatility prediction.

    Uses:
    - XGBoost: Gradient boosting with regularization
    - LightGBM: Fast gradient boosting with leaf-wise growth

    Features include:
    - Historical realized volatility
    - EGARCH conditional volatility
    - HAR-RV components
    - Technical indicators
    - Sentiment features (if available)
    """

    def __init__(
        self,
        models: list[str] | None = None,
        features_window: int = 100,
        forecast_horizon: int = 1,
    ):
        self.models = models or ["xgboost", "lightgbm"]
        self.features_window = features_window
        self.forecast_horizon = forecast_horizon

        self._xgb_model = None
        self._lgb_model = None
        self._feature_names: list[str] = []
        self._fitted = False
        self._scaler = None

    def prepare_features(
        self,
        returns: pd.Series,
        additional_features: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        Prepare feature matrix for ML models.

        Args:
            returns: Return series
            additional_features: Optional additional features

        Returns:
            Feature DataFrame
        """
        features = pd.DataFrame(index=returns.index)

        # Realized volatility at different horizons
        for window in [5, 10, 20, 50, 100]:
            features[f"rv_{window}"] = (returns ** 2).rolling(window).sum()
            features[f"vol_{window}"] = returns.rolling(window).std()

        # Volatility of volatility
        vol_20 = returns.rolling(20).std()
        features["vol_of_vol"] = vol_20.rolling(20).std()

        # Return statistics
        features["return_mean_20"] = returns.rolling(20).mean()
        features["return_skew_20"] = returns.rolling(20).skew()
        features["return_kurt_20"] = returns.rolling(20).kurt()

        # Range-based volatility (Parkinson)
        # Assuming we have high/low data in additional_features
        if additional_features is not None and "high" in additional_features.columns:
            hl_ratio = np.log(additional_features["high"] / additional_features["low"])
            features["parkinson_vol"] = np.sqrt((hl_ratio ** 2).rolling(20).mean() / (4 * np.log(2)))

        # Semivariances
        pos_returns = returns.where(returns > 0, 0)
        neg_returns = returns.where(returns < 0, 0)
        features["rsv_positive"] = (pos_returns ** 2).rolling(20).sum()
        features["rsv_negative"] = (neg_returns ** 2).rolling(20).sum()

        # Asymmetry
        features["vol_asymmetry"] = features["rsv_positive"] / (
            features["rsv_negative"] + 1e-10
        )

        # Lagged features
        for lag in [1, 2, 3, 5]:
            features[f"rv_20_lag{lag}"] = features["rv_20"].shift(lag)
            features[f"vol_20_lag{lag}"] = features["vol_20"].shift(lag)

        # Add additional features if provided
        if additional_features is not None:
            for col in additional_features.columns:
                if col not in features.columns:
                    features[col] = additional_features[col]

        return features

    def fit(
        self,
        returns: pd.Series,
        additional_features: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """
        Fit ensemble models.

        Args:
            returns: Return series
            additional_features: Optional additional features

        Returns:
            Dictionary with training results
        """
        # Prepare features
        features = self.prepare_features(returns, additional_features)

        # Target: Future realized volatility
        target = (returns ** 2).rolling(self.forecast_horizon).sum().shift(-self.forecast_horizon)

        # Align data and drop NaN
        data = pd.concat([features, target.rename("target")], axis=1).dropna()

        if len(data) < 100:
            logger.warning("Insufficient data for ML training")
            return self._fallback_fit()

        X = data.drop("target", axis=1)
        y = data["target"]

        # Store feature names
        self._feature_names = list(X.columns)

        # Scale features
        try:
            from sklearn.preprocessing import StandardScaler

            self._scaler = StandardScaler()
            X_scaled = pd.DataFrame(
                self._scaler.fit_transform(X),
                columns=X.columns,
                index=X.index,
            )
        except ImportError:
            X_scaled = X

        # Train/test split
        split_idx = int(len(X_scaled) * 0.8)
        X_train, X_test = X_scaled.iloc[:split_idx], X_scaled.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        results = {"models": {}}

        # Train XGBoost
        if "xgboost" in self.models:
            try:
                import xgboost as xgb

                self._xgb_model = xgb.XGBRegressor(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    objective="reg:squarederror",
                    random_state=42,
                )
                self._xgb_model.fit(X_train, y_train)

                train_score = self._xgb_model.score(X_train, y_train)
                test_score = self._xgb_model.score(X_test, y_test)

                results["models"]["xgboost"] = {
                    "train_r2": train_score,
                    "test_r2": test_score,
                    "feature_importance": dict(
                        zip(X.columns, self._xgb_model.feature_importances_)
                    ),
                }

                logger.info(
                    "XGBoost trained",
                    train_r2=train_score,
                    test_r2=test_score,
                )

            except ImportError:
                logger.warning("XGBoost not installed")

        # Train LightGBM
        if "lightgbm" in self.models:
            try:
                import lightgbm as lgb

                self._lgb_model = lgb.LGBMRegressor(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    objective="regression",
                    random_state=42,
                    verbose=-1,
                )
                self._lgb_model.fit(X_train, y_train)

                train_score = self._lgb_model.score(X_train, y_train)
                test_score = self._lgb_model.score(X_test, y_test)

                results["models"]["lightgbm"] = {
                    "train_r2": train_score,
                    "test_r2": test_score,
                    "feature_importance": dict(
                        zip(X.columns, self._lgb_model.feature_importances_)
                    ),
                }

                logger.info(
                    "LightGBM trained",
                    train_r2=train_score,
                    test_r2=test_score,
                )

            except ImportError:
                logger.warning("LightGBM not installed")

        self._fitted = True
        return results

    def _fallback_fit(self) -> dict[str, Any]:
        """Fallback when training fails."""
        self._fitted = True
        return {"models": {}, "fallback": True}

    def forecast(
        self,
        returns: pd.Series,
        additional_features: pd.DataFrame | None = None,
    ) -> EnsembleForecast:
        """
        Generate ensemble volatility forecast.

        Args:
            returns: Return series
            additional_features: Optional additional features

        Returns:
            EnsembleForecast with predictions
        """
        if not self._fitted:
            self.fit(returns, additional_features)

        # Prepare latest features
        features = self.prepare_features(returns, additional_features)
        latest = features.iloc[[-1]]

        # Scale features
        if self._scaler is not None:
            try:
                latest_scaled = pd.DataFrame(
                    self._scaler.transform(latest),
                    columns=latest.columns,
                    index=latest.index,
                )
            except Exception:
                latest_scaled = latest
        else:
            latest_scaled = latest

        predictions = []
        xgb_pred = None
        lgb_pred = None
        feature_importance = {}

        # XGBoost prediction
        if self._xgb_model is not None:
            try:
                xgb_pred = float(self._xgb_model.predict(latest_scaled)[0])
                predictions.append(xgb_pred)
                feature_importance = dict(
                    zip(self._feature_names, self._xgb_model.feature_importances_)
                )
            except Exception as e:
                logger.warning(f"XGBoost prediction error: {e}")

        # LightGBM prediction
        if self._lgb_model is not None:
            try:
                lgb_pred = float(self._lgb_model.predict(latest_scaled)[0])
                predictions.append(lgb_pred)
                if not feature_importance:
                    feature_importance = dict(
                        zip(self._feature_names, self._lgb_model.feature_importances_)
                    )
            except Exception as e:
                logger.warning(f"LightGBM prediction error: {e}")

        # Ensemble prediction (average)
        if predictions:
            ensemble_pred = np.mean(predictions)
            # Confidence based on model agreement
            if len(predictions) > 1:
                confidence = 1 - (np.std(predictions) / (np.mean(predictions) + 1e-10))
            else:
                confidence = 0.5
        else:
            # Fallback to historical volatility
            ensemble_pred = float((returns ** 2).rolling(20).sum().iloc[-1])
            confidence = 0.3

        # Convert variance to volatility
        ensemble_vol = np.sqrt(max(ensemble_pred, 0))

        return EnsembleForecast(
            forecast=ensemble_vol,
            xgboost_forecast=np.sqrt(max(xgb_pred, 0)) if xgb_pred else ensemble_vol,
            lightgbm_forecast=np.sqrt(max(lgb_pred, 0)) if lgb_pred else ensemble_vol,
            confidence=max(0, min(1, confidence)),
            feature_importance=feature_importance,
            timestamp=datetime.utcnow().isoformat(),
        )

    def get_feature_importance(self) -> dict[str, float]:
        """Get aggregated feature importance across models."""
        importance = {}

        if self._xgb_model is not None:
            for name, imp in zip(self._feature_names, self._xgb_model.feature_importances_):
                importance[name] = importance.get(name, 0) + imp

        if self._lgb_model is not None:
            for name, imp in zip(self._feature_names, self._lgb_model.feature_importances_):
                importance[name] = importance.get(name, 0) + imp

        # Normalize
        total = sum(importance.values()) or 1
        return {k: v / total for k, v in sorted(importance.items(), key=lambda x: -x[1])}


class VolatilityRegimeClassifier:
    """
    Classify volatility regime using ML.

    Regimes:
    - Low: Below 25th percentile
    - Medium: 25th to 75th percentile
    - High: Above 75th percentile
    - Extreme: Above 95th percentile
    """

    def __init__(self, percentiles: tuple[int, int, int] = (25, 75, 95)):
        self.percentiles = percentiles
        self._thresholds: dict[str, float] = {}

    def fit(self, volatility: pd.Series) -> None:
        """Fit regime thresholds from historical data."""
        self._thresholds = {
            "low": np.percentile(volatility.dropna(), self.percentiles[0]),
            "high": np.percentile(volatility.dropna(), self.percentiles[1]),
            "extreme": np.percentile(volatility.dropna(), self.percentiles[2]),
        }
        logger.info("Volatility regime thresholds", thresholds=self._thresholds)

    def classify(self, current_vol: float) -> str:
        """Classify current volatility into regime."""
        if not self._thresholds:
            return "unknown"

        if current_vol >= self._thresholds["extreme"]:
            return "extreme"
        elif current_vol >= self._thresholds["high"]:
            return "high"
        elif current_vol >= self._thresholds["low"]:
            return "medium"
        else:
            return "low"

    def get_regime_probabilities(self, current_vol: float) -> dict[str, float]:
        """Get probability distribution over regimes."""
        if not self._thresholds:
            return {"low": 0.25, "medium": 0.5, "high": 0.2, "extreme": 0.05}

        # Simple distance-based probabilities
        distances = {
            "low": abs(current_vol - self._thresholds["low"] / 2),
            "medium": abs(current_vol - (self._thresholds["low"] + self._thresholds["high"]) / 2),
            "high": abs(current_vol - (self._thresholds["high"] + self._thresholds["extreme"]) / 2),
            "extreme": abs(current_vol - self._thresholds["extreme"] * 1.5),
        }

        # Inverse distance weighting
        inv_distances = {k: 1 / (v + 0.01) for k, v in distances.items()}
        total = sum(inv_distances.values())

        return {k: v / total for k, v in inv_distances.items()}
