"""
Settings Configuration for Mortar Trading Bot
==============================================

Uses Pydantic for type-safe configuration with environment variable support.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    PAPER = "paper"
    PRODUCTION = "production"


class Direction(str, Enum):
    """Master macro direction input."""

    STRONG_BEAR = "strong_bear"
    BEAR = "bear"
    NEUTRAL = "neutral"
    BULL = "bull"
    STRONG_BULL = "strong_bull"


class Confidence(str, Enum):
    """Master macro confidence level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TimeHorizon(str, Enum):
    """Master macro time horizon."""

    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class MarketRegime(str, Enum):
    """Market regime classification."""

    TRENDING_LOW_VOL = "trending_low_vol"
    TRENDING_HIGH_VOL = "trending_high_vol"
    RANGE_LOW_VOL = "range_low_vol"
    RANGE_HIGH_VOL = "range_high_vol"
    BREAKOUT = "breakout"
    CRISIS = "crisis"


class ExchangeConfig(BaseModel):
    """Exchange connection configuration."""

    name: str = "binance"
    testnet: bool = True
    api_key: SecretStr | None = None
    api_secret: SecretStr | None = None
    requests_per_second: int = 10
    orders_per_second: int = 5

    @property
    def rest_endpoint(self) -> str:
        if self.testnet:
            return "https://testnet.binancefuture.com"
        return "https://fapi.binance.com"

    @property
    def ws_endpoint(self) -> str:
        if self.testnet:
            return "wss://fstream.binancefuture.com"
        return "wss://fstream.binance.com"


class TimeframeConfig(BaseModel):
    """Timeframe configuration for each layer."""

    macro_primary: str = "4h"
    macro_secondary: str = "1d"
    meso_primary: str = "15m"
    meso_secondary: str = "1h"
    micro_primary: str = "1m"
    micro_secondary: str = "5m"


class RiskConfig(BaseModel):
    """Risk management configuration - Non-negotiable limits."""

    # Hard limits
    max_leverage: float = Field(default=5.0, le=10.0)
    single_position_risk_pct: float = Field(default=2.0, le=5.0)
    total_portfolio_heat_pct: float = Field(default=10.0, le=20.0)
    max_correlated_positions: int = Field(default=3, le=5)
    correlation_threshold: float = Field(default=0.8, ge=0.5, le=1.0)

    # Circuit breakers
    daily_loss_limit_pct: float = Field(default=5.0, le=10.0)
    weekly_loss_limit_pct: float = Field(default=10.0, le=20.0)
    monthly_loss_limit_pct: float = Field(default=15.0, le=30.0)

    # Volatility targeting
    target_annual_volatility_pct: float = 25.0
    volatility_lookback_days: int = 30


class PositionSizingConfig(BaseModel):
    """Position sizing configuration."""

    method: str = "atr_volatility_target"  # atr_volatility_target, fixed_fractional, kelly
    atr_period: int = 14
    atr_multiplier: float = 2.0
    min_position_usd: float = 100.0
    max_position_usd: float = 50000.0


class SentimentProviderConfig(BaseModel):
    """Individual sentiment provider configuration."""

    name: str
    enabled: bool = True
    api_key: SecretStr | None = None
    update_interval_seconds: int = 300


class SentimentConfig(BaseModel):
    """Sentiment analysis configuration."""

    providers: list[SentimentProviderConfig] = Field(default_factory=list)
    sentiment_zscore_window: int = 30
    volume_weight_decay: float = 0.95
    influencer_min_followers: int = 10000


class EGARCHConfig(BaseModel):
    """EGARCH model configuration."""

    enabled: bool = True
    p: int = 1
    q: int = 1
    dist: str = "studentst"


class HARRVConfig(BaseModel):
    """HAR-RV model configuration."""

    enabled: bool = True
    lags: list[int] = Field(default_factory=lambda: [1, 5, 22])


class MLEnsembleConfig(BaseModel):
    """ML ensemble configuration."""

    enabled: bool = True
    models: list[str] = Field(default_factory=lambda: ["xgboost", "lightgbm"])
    features_window: int = 100


class VolatilityConfig(BaseModel):
    """Volatility model configuration."""

    egarch: EGARCHConfig = Field(default_factory=EGARCHConfig)
    har_rv: HARRVConfig = Field(default_factory=HARRVConfig)
    ml_ensemble: MLEnsembleConfig = Field(default_factory=MLEnsembleConfig)


class RegimeConfig(BaseModel):
    """Regime classification configuration."""

    lookback_periods: int = 100
    volatility_percentiles: list[int] = Field(default_factory=lambda: [25, 75])
    trend_ema_periods: list[int] = Field(default_factory=lambda: [20, 50])


class RLAgentConfig(BaseModel):
    """Individual RL agent configuration."""

    algorithm: str
    learning_rate: float = 0.0003
    gamma: float = 0.99
    buffer_size: int = 1000000
    batch_size: int = 256
    n_steps: int = 2048  # For PPO
    n_epochs: int = 10  # For PPO
    tau: float = 0.005  # For SAC/TD3
    policy_delay: int = 2  # For TD3
    training_timesteps: int = 500000


class RLConfig(BaseModel):
    """RL agents configuration."""

    macro: RLAgentConfig = Field(
        default_factory=lambda: RLAgentConfig(
            algorithm="PPO",
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            training_timesteps=1000000,
        )
    )
    meso: RLAgentConfig = Field(
        default_factory=lambda: RLAgentConfig(
            algorithm="SAC",
            training_timesteps=500000,
        )
    )
    micro: RLAgentConfig = Field(
        default_factory=lambda: RLAgentConfig(
            algorithm="TD3",
            policy_delay=2,
            training_timesteps=500000,
        )
    )


class MasterInputAdjustments(BaseModel):
    """How master input affects the system."""

    high_confidence_max_allocation: float = 0.8
    low_confidence_size_reduction: float = 0.5
    event_position_reduction: float = 0.5
    event_stop_widening: float = 1.5


class MasterInputConfig(BaseModel):
    """Master macro input system configuration."""

    enabled: bool = True
    default_direction: Direction = Direction.NEUTRAL
    default_confidence: Confidence = Confidence.MEDIUM
    default_time_horizon: TimeHorizon = TimeHorizon.DAYS
    adjustments: MasterInputAdjustments = Field(default_factory=MasterInputAdjustments)


class DatabaseConfig(BaseModel):
    """Database configuration."""

    questdb_host: str = "localhost"
    questdb_port: int = 9009
    questdb_http_port: int = 9000
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None


class AlertConfig(BaseModel):
    """Alerting configuration."""

    telegram_enabled: bool = True
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    discord_enabled: bool = False
    discord_webhook_url: SecretStr | None = None
    position_pnl_alert_pct: float = 5.0
    daily_pnl_alert_pct: float = 3.0
    volatility_spike_multiplier: float = 2.0


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""

    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    alerts: AlertConfig = Field(default_factory=AlertConfig)


class BacktestCostsConfig(BaseModel):
    """Backtest transaction costs."""

    maker_fee_pct: float = 0.02
    taker_fee_pct: float = 0.04
    slippage_pct: float = 0.05


class BacktestTargetsConfig(BaseModel):
    """Backtest target metrics."""

    min_sharpe_ratio: float = 0.8
    max_drawdown_pct: float = 20.0
    min_win_rate_pct: float = 55.0
    min_profit_factor: float = 1.5


class BacktestConfig(BaseModel):
    """Backtesting configuration."""

    start_date: str = "2022-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 100000.0
    costs: BacktestCostsConfig = Field(default_factory=BacktestCostsConfig)
    targets: BacktestTargetsConfig = Field(default_factory=BacktestTargetsConfig)
    walk_forward_in_sample_ratio: float = 0.7
    walk_forward_n_splits: int = 5


class LoggingConfig(BaseModel):
    """Logging configuration."""

    format: str = "json"
    file_enabled: bool = True
    file_path: str = "logs/"
    rotation: str = "daily"
    retention_days: int = 30
    console_enabled: bool = True
    console_color: bool = True


class TradingSymbols(BaseModel):
    """Trading symbols configuration."""

    primary: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    secondary: list[str] = Field(
        default_factory=lambda: [
            "SOLUSDT",
            "BNBUSDT",
            "XRPUSDT",
            "ADAUSDT",
            "AVAXUSDT",
            "DOTUSDT",
            "MATICUSDT",
            "LINKUSDT",
        ]
    )

    @property
    def all_symbols(self) -> list[str]:
        return self.primary + self.secondary


class Settings(BaseSettings):
    """
    Main settings class for Mortar Trading Bot.

    Configuration is loaded from:
    1. Environment variables (highest priority)
    2. .env file
    3. config/settings.yaml
    4. Default values (lowest priority)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # System
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    timezone: str = "UTC"

    # Exchange credentials (from environment)
    binance_api_key: SecretStr | None = None
    binance_api_secret: SecretStr | None = None

    # Sentiment API keys (from environment)
    lunarcrush_api_key: SecretStr | None = None
    santiment_api_key: SecretStr | None = None
    twitter_api_key: SecretStr | None = None
    twitter_api_secret: SecretStr | None = None
    twitter_bearer_token: SecretStr | None = None

    # Database credentials (from environment)
    redis_password: SecretStr | None = None

    # Alert credentials (from environment)
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    discord_webhook_url: SecretStr | None = None

    # Nested configurations
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    symbols: TradingSymbols = Field(default_factory=TradingSymbols)
    timeframes: TimeframeConfig = Field(default_factory=TimeframeConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    position_sizing: PositionSizingConfig = Field(default_factory=PositionSizingConfig)
    sentiment: SentimentConfig = Field(default_factory=SentimentConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    rl: RLConfig = Field(default_factory=RLConfig)
    master_input: MasterInputConfig = Field(default_factory=MasterInputConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def model_post_init(self, __context: Any) -> None:
        """Apply environment variables to nested configs after initialization."""
        # Apply exchange credentials
        if self.binance_api_key:
            self.exchange.api_key = self.binance_api_key
        if self.binance_api_secret:
            self.exchange.api_secret = self.binance_api_secret

        # Apply database credentials
        if self.redis_password:
            self.database.redis_password = self.redis_password

        # Apply alert credentials
        if self.telegram_bot_token:
            self.monitoring.alerts.telegram_bot_token = self.telegram_bot_token
        if self.telegram_chat_id:
            self.monitoring.alerts.telegram_chat_id = self.telegram_chat_id
        if self.discord_webhook_url:
            self.monitoring.alerts.discord_webhook_url = self.discord_webhook_url

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "Settings":
        """Load settings from a YAML file."""
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            return cls()

        with open(yaml_path) as f:
            yaml_config = yaml.safe_load(f)

        # Flatten nested yaml structure for pydantic
        flat_config = cls._flatten_yaml_config(yaml_config)
        return cls(**flat_config)

    @staticmethod
    def _flatten_yaml_config(config: dict) -> dict:
        """Flatten YAML config to match Pydantic model structure."""
        result = {}

        if "system" in config:
            result["environment"] = config["system"].get("environment", "development")
            result["log_level"] = config["system"].get("log_level", "INFO")
            result["timezone"] = config["system"].get("timezone", "UTC")

        if "exchange" in config:
            result["exchange"] = ExchangeConfig(
                name=config["exchange"].get("name", "binance"),
                testnet=config["exchange"].get("testnet", True),
            )

        if "trading" in config:
            trading = config["trading"]
            if "symbols" in trading:
                result["symbols"] = TradingSymbols(
                    primary=trading["symbols"].get("primary", ["BTCUSDT", "ETHUSDT"]),
                    secondary=trading["symbols"].get("secondary", []),
                )
            if "timeframes" in trading:
                tf = trading["timeframes"]
                result["timeframes"] = TimeframeConfig(
                    macro_primary=tf.get("macro", {}).get("primary", "4h"),
                    macro_secondary=tf.get("macro", {}).get("secondary", "1d"),
                    meso_primary=tf.get("meso", {}).get("primary", "15m"),
                    meso_secondary=tf.get("meso", {}).get("secondary", "1h"),
                    micro_primary=tf.get("micro", {}).get("primary", "1m"),
                    micro_secondary=tf.get("micro", {}).get("secondary", "5m"),
                )

        if "risk" in config:
            risk = config["risk"]
            result["risk"] = RiskConfig(
                max_leverage=risk.get("max_leverage", 5),
                single_position_risk_pct=risk.get("single_position_risk_pct", 2.0),
                total_portfolio_heat_pct=risk.get("total_portfolio_heat_pct", 10.0),
                max_correlated_positions=risk.get("max_correlated_positions", 3),
                correlation_threshold=risk.get("correlation_threshold", 0.8),
                daily_loss_limit_pct=risk.get("loss_limits", {}).get("daily_pct", 5.0),
                weekly_loss_limit_pct=risk.get("loss_limits", {}).get("weekly_pct", 10.0),
                monthly_loss_limit_pct=risk.get("loss_limits", {}).get("monthly_pct", 15.0),
                target_annual_volatility_pct=risk.get("target_annual_volatility_pct", 25.0),
                volatility_lookback_days=risk.get("volatility_lookback_days", 30),
            )

        return result

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_paper_trading(self) -> bool:
        """Check if running in paper trading mode."""
        return self.environment == Environment.PAPER


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Loads from config/settings.yaml if it exists, otherwise uses defaults.
    Environment variables always override.
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    if config_path.exists():
        settings = Settings.from_yaml(config_path)
    else:
        settings = Settings()
    return settings
