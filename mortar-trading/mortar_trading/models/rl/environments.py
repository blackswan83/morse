"""
Trading Environments for RL
===========================

Gymnasium-compatible environments for training RL agents.
"""

from __future__ import annotations

from typing import Any, SupportsFloat

import numpy as np

import structlog

logger = structlog.get_logger(__name__)


# Try to import gymnasium, fall back to gym
try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    import gym
    from gym import spaces


class TradingEnvironment(gym.Env):
    """
    Base trading environment for RL agents.

    Observation space includes:
    - Price features (returns, volatility, momentum)
    - Position state (current position, unrealized PnL)
    - Market state (regime, sentiment)

    Action space:
    - Continuous: Position size from -1 (max short) to 1 (max long)
    - Or discrete: {-1, 0, 1} for short/flat/long
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        data: np.ndarray,
        features: np.ndarray,
        initial_balance: float = 100000,
        max_position: float = 1.0,
        transaction_cost: float = 0.0004,
        reward_scaling: float = 1.0,
        continuous_actions: bool = True,
    ):
        """
        Initialize trading environment.

        Args:
            data: Price data array (OHLCV)
            features: Feature matrix for observations
            initial_balance: Starting capital
            max_position: Maximum position size as fraction of portfolio
            transaction_cost: Transaction cost per trade
            reward_scaling: Reward scaling factor
            continuous_actions: Use continuous or discrete action space
        """
        super().__init__()

        self.data = data
        self.features = features
        self.initial_balance = initial_balance
        self.max_position = max_position
        self.transaction_cost = transaction_cost
        self.reward_scaling = reward_scaling

        # State
        self.current_step = 0
        self.balance = initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.total_reward = 0.0
        self.trades = 0

        # Define spaces
        self.n_features = features.shape[1] if len(features.shape) > 1 else 1

        # Observation: features + position info
        obs_dim = self.n_features + 3  # features + position, entry_price, unrealized_pnl
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32,
        )

        # Action space
        if continuous_actions:
            # Continuous: position size from -1 to 1
            self.action_space = spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(1,),
                dtype=np.float32,
            )
        else:
            # Discrete: short, flat, long
            self.action_space = spaces.Discrete(3)

        self.continuous_actions = continuous_actions

    def reset(
        self,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)

        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.total_reward = 0.0
        self.trades = 0

        obs = self._get_observation()
        info = self._get_info()

        return obs, info

    def step(
        self,
        action: np.ndarray | int,
    ) -> tuple[np.ndarray, SupportsFloat, bool, bool, dict]:
        """
        Execute one step in the environment.

        Args:
            action: Action to take (position size or direction)

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Get current price
        current_price = self._get_current_price()

        # Process action
        if self.continuous_actions:
            target_position = float(action[0]) * self.max_position
        else:
            # Discrete: 0=short, 1=flat, 2=long
            target_position = (action - 1) * self.max_position

        # Calculate position change
        position_change = target_position - self.position

        # Calculate transaction cost
        cost = abs(position_change) * current_price * self.transaction_cost

        # Update balance with unrealized PnL before changing position
        if self.position != 0:
            pnl = self.position * (current_price - self.entry_price)
            self.balance += pnl

        # Deduct transaction cost
        self.balance -= cost

        # Update position
        if target_position != self.position:
            self.trades += 1

        self.position = target_position
        if target_position != 0:
            self.entry_price = current_price

        # Move to next step
        self.current_step += 1

        # Get new price for reward calculation
        new_price = self._get_current_price()

        # Calculate reward (Differential Sharpe Ratio inspired)
        reward = self._calculate_reward(current_price, new_price)
        self.total_reward += reward

        # Check termination
        terminated = self.current_step >= len(self.data) - 1
        truncated = self.balance <= 0  # Bankrupt

        obs = self._get_observation()
        info = self._get_info()

        return obs, reward, terminated, truncated, info

    def _get_observation(self) -> np.ndarray:
        """Get current observation."""
        # Get features for current step
        if self.current_step < len(self.features):
            features = self.features[self.current_step]
        else:
            features = self.features[-1]

        # Get current price for position info
        current_price = self._get_current_price()

        # Unrealized PnL
        if self.position != 0:
            unrealized_pnl = self.position * (current_price - self.entry_price)
        else:
            unrealized_pnl = 0

        # Normalize position info
        position_info = np.array([
            self.position / self.max_position,
            (self.entry_price / current_price - 1) if self.entry_price > 0 else 0,
            unrealized_pnl / self.initial_balance,
        ])

        obs = np.concatenate([features.flatten(), position_info]).astype(np.float32)

        # Handle NaN/inf
        obs = np.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)

        return obs

    def _get_current_price(self) -> float:
        """Get current price (close)."""
        if self.current_step < len(self.data):
            return float(self.data[self.current_step, 3])  # Close price
        return float(self.data[-1, 3])

    def _calculate_reward(self, old_price: float, new_price: float) -> float:
        """
        Calculate reward using Differential Sharpe Ratio.

        This encourages risk-adjusted returns rather than raw returns.
        """
        if old_price <= 0:
            return 0.0

        # Return from position
        if self.position != 0:
            ret = self.position * (new_price - old_price) / old_price
        else:
            ret = 0.0

        # Scale reward
        reward = ret * self.reward_scaling

        # Penalize large drawdowns
        if self.balance < self.initial_balance * 0.9:
            drawdown_penalty = (self.initial_balance * 0.9 - self.balance) / self.initial_balance
            reward -= drawdown_penalty * 0.1

        return reward

    def _get_info(self) -> dict[str, Any]:
        """Get current info dictionary."""
        current_price = self._get_current_price()

        # Calculate current equity
        if self.position != 0:
            unrealized_pnl = self.position * (current_price - self.entry_price)
        else:
            unrealized_pnl = 0

        equity = self.balance + unrealized_pnl

        return {
            "step": self.current_step,
            "balance": self.balance,
            "equity": equity,
            "position": self.position,
            "entry_price": self.entry_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "total_reward": self.total_reward,
            "trades": self.trades,
            "return": (equity - self.initial_balance) / self.initial_balance,
        }

    def render(self, mode: str = "human") -> None:
        """Render environment state."""
        info = self._get_info()
        print(
            f"Step {info['step']}: "
            f"Equity=${info['equity']:.2f}, "
            f"Position={info['position']:.4f}, "
            f"Return={info['return']:.2%}"
        )


class MacroEnvironment(TradingEnvironment):
    """
    Environment for Macro agent (daily/4h timeframe).

    Focuses on directional bias determination.
    Action: Direction bias [-1, 0, 1] and max allocation
    Observation: Sentiment features, macro indicators
    """

    def __init__(
        self,
        data: np.ndarray,
        features: np.ndarray,
        sentiment_features: np.ndarray | None = None,
        **kwargs,
    ):
        super().__init__(data, features, continuous_actions=False, **kwargs)

        self.sentiment_features = sentiment_features

        # Output is direction bias + allocation
        self.action_space = spaces.MultiDiscrete([3, 5])  # Direction: 3, Allocation: 5 levels


class MesoEnvironment(TradingEnvironment):
    """
    Environment for Meso agent (1h/15m timeframe).

    Focuses on trade setup identification.
    Constrained by Macro agent's directional bias.
    """

    def __init__(
        self,
        data: np.ndarray,
        features: np.ndarray,
        macro_bias: int = 0,  # -1, 0, 1
        max_allocation: float = 1.0,
        **kwargs,
    ):
        super().__init__(data, features, **kwargs)

        self.macro_bias = macro_bias
        self.max_allocation = max_allocation

        # Constrain action space based on macro bias
        if macro_bias > 0:  # Bullish
            self.action_space = spaces.Box(
                low=0.0,
                high=max_allocation,
                shape=(1,),
                dtype=np.float32,
            )
        elif macro_bias < 0:  # Bearish
            self.action_space = spaces.Box(
                low=-max_allocation,
                high=0.0,
                shape=(1,),
                dtype=np.float32,
            )
        else:  # Neutral
            self.action_space = spaces.Box(
                low=-max_allocation,
                high=max_allocation,
                shape=(1,),
                dtype=np.float32,
            )


class MicroEnvironment(TradingEnvironment):
    """
    Environment for Micro agent (5m/1m timeframe).

    Focuses on execution optimization.
    Takes orders from Meso and optimizes entry/exit.
    """

    def __init__(
        self,
        data: np.ndarray,
        features: np.ndarray,
        order_book_features: np.ndarray | None = None,
        target_position: float = 0,
        **kwargs,
    ):
        super().__init__(data, features, **kwargs)

        self.order_book_features = order_book_features
        self.target_position = target_position

        # Action: Execution timing/sizing
        # 0: Wait, 1: Partial fill, 2: Full fill, 3: Aggressive
        self.action_space = spaces.Discrete(4)

    def _calculate_reward(self, old_price: float, new_price: float) -> float:
        """Reward based on execution quality vs TWAP/VWAP."""
        # Execution-focused reward
        base_reward = super()._calculate_reward(old_price, new_price)

        # Penalize deviation from target
        position_error = abs(self.position - self.target_position)
        execution_penalty = position_error * 0.01

        return base_reward - execution_penalty
