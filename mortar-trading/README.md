# Mortar Trading

A hierarchical multi-timeframe crypto volatility trading bot with sentiment analysis, machine learning, and reinforcement learning.

## Architecture

Mortar Trading implements a **three-layer hierarchical architecture**:

```
MACRO (Daily/4H) → Directional bias from sentiment + on-chain
    ↓
MESO  (1H/15M)   → Trade setup from volatility + regime
    ↓
MICRO (5M/1M)    → Entry/exit execution from order flow
```

**The cardinal rule**: Never trade against the higher timeframe direction.

## Features

### Data Pipeline
- Real-time WebSocket data from Binance Futures
- Historical data collection and storage
- Redis caching for features
- QuestDB time-series storage

### Sentiment Analysis
- **VADER**: Real-time lexicon-based analysis with crypto-specific enhancements
- **CryptoBERT**: Deep learning sentiment from transformer models
- Multi-source aggregation (LunarCrush, Santiment)
- Z-score normalization and momentum calculation

### Volatility Models
- **EGARCH(1,1)**: Conditional volatility with asymmetric effects
- **HAR-RV**: Multi-horizon realized volatility forecasting
- **ML Ensemble**: XGBoost + LightGBM volatility prediction
- Realized semivariance analysis (crypto-specific asymmetry)

### Market Regime Classification
- Trending + Low/High Volatility
- Range + Low/High Volatility
- Breakout detection
- Crisis/dislocation detection

### Reinforcement Learning
- **Macro PPO**: Direction and allocation from sentiment
- **Meso SAC**: Trade setup identification
- **Micro TD3**: Execution optimization
- Differential Sharpe Ratio rewards

### Risk Management
- Position limits (2% per trade)
- Portfolio heat limits (10% total)
- Correlation-based position reduction
- Daily/weekly/monthly circuit breakers
- ATR-based volatility-targeting position sizing

### Monitoring
- Prometheus metrics
- Telegram/Discord alerts
- Real-time performance tracking

## Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/mortar-trading.git
cd mortar-trading

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

Configuration is in `config/settings.yaml`. Key settings:

```yaml
# Risk Management (Non-negotiable limits)
risk:
  max_leverage: 5
  single_position_risk_pct: 2.0
  total_portfolio_heat_pct: 10.0
  daily_loss_limit_pct: 5.0

# Timeframes
trading:
  timeframes:
    macro:
      primary: "4h"
    meso:
      primary: "15m"
    micro:
      primary: "1m"
```

## Usage

### Paper Trading (Recommended Start)

```bash
# Run on Binance testnet
mortar paper
```

### Live Trading

```bash
# Run live (requires API keys)
mortar live
```

### Backtesting

```bash
# Run backtest
mortar backtest --start 2023-01-01 --end 2024-01-01 --capital 100000
```

### Master Input Override

The system supports manual directional override:

```python
from mortar_trading import TradingEngine

engine = TradingEngine()
await engine.initialize()

# Set bullish bias with high confidence
engine.set_master_direction("bull", "high")

# Set key levels
engine.set_key_levels(support=40000, resistance=45000)

# Add upcoming events
engine.add_upcoming_event("Fed Meeting", datetime(2024, 3, 20))
```

## Project Structure

```
mortar-trading/
├── config/
│   └── settings.yaml          # Main configuration
├── mortar_trading/
│   ├── config/                 # Configuration management
│   ├── core/                   # Core engine and events
│   ├── data/                   # Data collection and processing
│   ├── models/
│   │   ├── sentiment/          # VADER, CryptoBERT
│   │   ├── volatility/         # EGARCH, HAR-RV, ML
│   │   ├── regime/             # Market regime classifier
│   │   └── rl/                 # RL agents
│   ├── strategy/
│   │   ├── macro/              # Directional bias
│   │   ├── meso/               # Trade setups
│   │   ├── micro/              # Execution
│   │   └── portfolio/          # Risk management
│   ├── execution/              # Order execution
│   ├── monitoring/             # Metrics and alerts
│   └── backtest/               # Backtesting framework
└── tests/
```

## Key Concepts

### Sentiment-Price Lag

Research shows sentiment signals work best on 4-24 hour horizons:
- **Tweet volume** is the strongest predictor
- Influencer tweets show effects within **3 minutes**
- Optimal prediction accuracy at **16-hour lag**

This is why sentiment feeds the **Macro layer**, not minute-level trading.

### Crypto Volatility Asymmetry

Unlike equities, crypto shows **inverse leverage effects**:
- Positive returns → increased volatility (FOMO)
- Positive semivariance predicts future vol better than negative

The EGARCH and HAR-RV models capture this asymmetry.

### Regime-Based Strategy Adjustment

| Regime | Strategy | Position Size |
|--------|----------|---------------|
| Trending + Low Vol | Trend follow | 1.2x |
| Trending + High Vol | Trend follow | 0.8x |
| Range + Low Vol | Mean reversion | 1.0x |
| Range + High Vol | Defensive | 0.5x |
| Crisis | Minimal | 0.25x |

## Risk Limits (Non-Negotiable)

| Parameter | Limit |
|-----------|-------|
| Max leverage | 5x |
| Single position risk | 2% of equity |
| Total portfolio heat | 10% of equity |
| Max correlated positions | 3 |
| Daily loss limit | 5% |
| Weekly loss limit | 10% |
| Monthly loss limit | 15% |

## Backtesting Targets

Before going live, ensure your strategy meets:
- Sharpe Ratio: > 0.8
- Max Drawdown: < 20%
- Win Rate: > 55%
- Profit Factor: > 1.5

**Expect 60-70% of backtested returns to evaporate live.**

## Development

```bash
# Run tests
pytest tests/

# Type checking
mypy mortar_trading/

# Linting
ruff check mortar_trading/

# Format code
black mortar_trading/
```

## License

MIT License

## Disclaimer

This software is for educational purposes only. Cryptocurrency trading involves substantial risk of loss. Past performance does not guarantee future results. Use at your own risk.
