"""
RL Agents for Trading
=====================

Hierarchical RL agents using Stable Baselines3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import structlog

from mortar_trading.config import Settings

logger = structlog.get_logger(__name__)


class BaseRLAgent:
    """Base class for RL trading agents."""

    def __init__(
        self,
        settings: Settings,
        model_path: str | Path | None = None,
    ):
        self.settings = settings
        self.model_path = Path(model_path) if model_path else None
        self._model = None
        self._is_trained = False

    def train(self, env, total_timesteps: int, **kwargs) -> dict[str, Any]:
        """Train the agent."""
        raise NotImplementedError

    def predict(self, observation: np.ndarray, deterministic: bool = True) -> tuple[np.ndarray, Any]:
        """Predict action from observation."""
        raise NotImplementedError

    def save(self, path: str | Path) -> None:
        """Save model to disk."""
        if self._model:
            self._model.save(str(path))
            logger.info(f"Model saved to {path}")

    def load(self, path: str | Path) -> None:
        """Load model from disk."""
        raise NotImplementedError


class PPOAgent(BaseRLAgent):
    """
    Proximal Policy Optimization agent for Macro layer.

    PPO is well-suited for:
    - Discrete or continuous actions
    - Stable training
    - Sample efficiency
    """

    def __init__(self, settings: Settings, **kwargs):
        super().__init__(settings, **kwargs)
        self.config = settings.rl.macro

    def _create_model(self, env):
        """Create PPO model."""
        try:
            from stable_baselines3 import PPO

            self._model = PPO(
                policy="MlpPolicy",
                env=env,
                learning_rate=self.config.learning_rate,
                n_steps=self.config.n_steps,
                batch_size=self.config.batch_size,
                n_epochs=self.config.n_epochs,
                gamma=self.config.gamma,
                verbose=1,
            )
            logger.info("PPO model created")

        except ImportError:
            logger.warning("stable_baselines3 not installed")
            self._model = None

    def train(
        self,
        env,
        total_timesteps: int | None = None,
        callback=None,
    ) -> dict[str, Any]:
        """
        Train PPO agent.

        Args:
            env: Training environment
            total_timesteps: Number of timesteps
            callback: Training callback

        Returns:
            Training statistics
        """
        if self._model is None:
            self._create_model(env)

        if self._model is None:
            return {"error": "Model not created"}

        timesteps = total_timesteps or self.config.training_timesteps

        logger.info(f"Training PPO for {timesteps} timesteps")

        try:
            self._model.learn(
                total_timesteps=timesteps,
                callback=callback,
                progress_bar=True,
            )
            self._is_trained = True

            return {
                "timesteps": timesteps,
                "trained": True,
            }

        except Exception as e:
            logger.error(f"PPO training error: {e}")
            return {"error": str(e)}

    def predict(
        self,
        observation: np.ndarray,
        deterministic: bool = True,
    ) -> tuple[np.ndarray, Any]:
        """Predict action from observation."""
        if self._model is None:
            # Random action fallback
            return np.array([0]), None

        return self._model.predict(observation, deterministic=deterministic)

    def load(self, path: str | Path) -> None:
        """Load PPO model."""
        try:
            from stable_baselines3 import PPO

            self._model = PPO.load(str(path))
            self._is_trained = True
            logger.info(f"PPO model loaded from {path}")

        except Exception as e:
            logger.error(f"Failed to load PPO model: {e}")


class SACAgent(BaseRLAgent):
    """
    Soft Actor-Critic agent for Meso layer.

    SAC is well-suited for:
    - Continuous action spaces
    - Exploration via entropy regularization
    - Off-policy learning (sample efficient)
    """

    def __init__(self, settings: Settings, **kwargs):
        super().__init__(settings, **kwargs)
        self.config = settings.rl.meso

    def _create_model(self, env):
        """Create SAC model."""
        try:
            from stable_baselines3 import SAC

            self._model = SAC(
                policy="MlpPolicy",
                env=env,
                learning_rate=self.config.learning_rate,
                buffer_size=self.config.buffer_size,
                batch_size=self.config.batch_size,
                tau=self.config.tau,
                gamma=self.config.gamma,
                verbose=1,
            )
            logger.info("SAC model created")

        except ImportError:
            logger.warning("stable_baselines3 not installed")
            self._model = None

    def train(
        self,
        env,
        total_timesteps: int | None = None,
        callback=None,
    ) -> dict[str, Any]:
        """Train SAC agent."""
        if self._model is None:
            self._create_model(env)

        if self._model is None:
            return {"error": "Model not created"}

        timesteps = total_timesteps or self.config.training_timesteps

        logger.info(f"Training SAC for {timesteps} timesteps")

        try:
            self._model.learn(
                total_timesteps=timesteps,
                callback=callback,
                progress_bar=True,
            )
            self._is_trained = True

            return {"timesteps": timesteps, "trained": True}

        except Exception as e:
            logger.error(f"SAC training error: {e}")
            return {"error": str(e)}

    def predict(
        self,
        observation: np.ndarray,
        deterministic: bool = True,
    ) -> tuple[np.ndarray, Any]:
        """Predict action from observation."""
        if self._model is None:
            return np.array([0.0]), None

        return self._model.predict(observation, deterministic=deterministic)

    def load(self, path: str | Path) -> None:
        """Load SAC model."""
        try:
            from stable_baselines3 import SAC

            self._model = SAC.load(str(path))
            self._is_trained = True
            logger.info(f"SAC model loaded from {path}")

        except Exception as e:
            logger.error(f"Failed to load SAC model: {e}")


class TD3Agent(BaseRLAgent):
    """
    Twin Delayed DDPG agent for Micro layer.

    TD3 is well-suited for:
    - Continuous action spaces
    - Reduced overestimation bias
    - Deterministic policy (good for execution)
    """

    def __init__(self, settings: Settings, **kwargs):
        super().__init__(settings, **kwargs)
        self.config = settings.rl.micro

    def _create_model(self, env):
        """Create TD3 model."""
        try:
            from stable_baselines3 import TD3

            self._model = TD3(
                policy="MlpPolicy",
                env=env,
                learning_rate=self.config.learning_rate,
                buffer_size=self.config.buffer_size,
                batch_size=self.config.batch_size,
                tau=self.config.tau,
                gamma=self.config.gamma,
                policy_delay=self.config.policy_delay,
                verbose=1,
            )
            logger.info("TD3 model created")

        except ImportError:
            logger.warning("stable_baselines3 not installed")
            self._model = None

    def train(
        self,
        env,
        total_timesteps: int | None = None,
        callback=None,
    ) -> dict[str, Any]:
        """Train TD3 agent."""
        if self._model is None:
            self._create_model(env)

        if self._model is None:
            return {"error": "Model not created"}

        timesteps = total_timesteps or self.config.training_timesteps

        logger.info(f"Training TD3 for {timesteps} timesteps")

        try:
            self._model.learn(
                total_timesteps=timesteps,
                callback=callback,
                progress_bar=True,
            )
            self._is_trained = True

            return {"timesteps": timesteps, "trained": True}

        except Exception as e:
            logger.error(f"TD3 training error: {e}")
            return {"error": str(e)}

    def predict(
        self,
        observation: np.ndarray,
        deterministic: bool = True,
    ) -> tuple[np.ndarray, Any]:
        """Predict action from observation."""
        if self._model is None:
            return np.array([0.0]), None

        return self._model.predict(observation, deterministic=deterministic)

    def load(self, path: str | Path) -> None:
        """Load TD3 model."""
        try:
            from stable_baselines3 import TD3

            self._model = TD3.load(str(path))
            self._is_trained = True
            logger.info(f"TD3 model loaded from {path}")

        except Exception as e:
            logger.error(f"Failed to load TD3 model: {e}")


class HierarchicalAgent:
    """
    Hierarchical agent combining Macro, Meso, and Micro layers.

    Implements the cardinal rule: Never trade against higher timeframe direction.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        self.macro_agent = PPOAgent(settings)
        self.meso_agent = SACAgent(settings)
        self.micro_agent = TD3Agent(settings)

        self._macro_bias = 0  # -1, 0, 1
        self._macro_allocation = 1.0
        self._meso_signal = None

    def get_macro_decision(
        self,
        observation: np.ndarray,
    ) -> tuple[int, float]:
        """
        Get macro layer decision.

        Returns:
            (direction_bias, max_allocation)
        """
        action, _ = self.macro_agent.predict(observation)

        if hasattr(action, "__len__") and len(action) == 2:
            direction = int(action[0]) - 1  # Convert 0,1,2 to -1,0,1
            allocation = (int(action[1]) + 1) / 5  # Convert to 0.2-1.0
        else:
            direction = 0
            allocation = 0.5

        self._macro_bias = direction
        self._macro_allocation = allocation

        return direction, allocation

    def get_meso_decision(
        self,
        observation: np.ndarray,
    ) -> float:
        """
        Get meso layer decision (constrained by macro).

        Returns:
            Target position size
        """
        action, _ = self.meso_agent.predict(observation)

        if isinstance(action, np.ndarray):
            position = float(action[0])
        else:
            position = 0.0

        # Constrain by macro bias
        if self._macro_bias > 0:  # Bullish
            position = max(0, position) * self._macro_allocation
        elif self._macro_bias < 0:  # Bearish
            position = min(0, position) * self._macro_allocation
        else:
            position = position * self._macro_allocation * 0.5  # Reduced in neutral

        self._meso_signal = position
        return position

    def get_micro_decision(
        self,
        observation: np.ndarray,
    ) -> int:
        """
        Get micro layer decision (execution).

        Returns:
            Execution action (0: wait, 1: partial, 2: full, 3: aggressive)
        """
        action, _ = self.micro_agent.predict(observation)

        if isinstance(action, np.ndarray):
            return int(action[0])
        return 0

    def get_combined_action(
        self,
        macro_obs: np.ndarray,
        meso_obs: np.ndarray,
        micro_obs: np.ndarray,
    ) -> dict[str, Any]:
        """
        Get combined hierarchical decision.

        Returns:
            Dictionary with all layer decisions
        """
        macro_direction, macro_allocation = self.get_macro_decision(macro_obs)
        meso_position = self.get_meso_decision(meso_obs)
        micro_action = self.get_micro_decision(micro_obs)

        return {
            "macro": {
                "direction": macro_direction,
                "allocation": macro_allocation,
            },
            "meso": {
                "target_position": meso_position,
            },
            "micro": {
                "execution_action": micro_action,
            },
            "final_position": meso_position,  # Already constrained
        }

    def train_all(
        self,
        macro_env,
        meso_env,
        micro_env,
        macro_timesteps: int | None = None,
        meso_timesteps: int | None = None,
        micro_timesteps: int | None = None,
    ) -> dict[str, Any]:
        """Train all agents."""
        results = {}

        # Train macro first
        logger.info("Training Macro agent (PPO)")
        results["macro"] = self.macro_agent.train(macro_env, macro_timesteps)

        # Train meso (using macro policy for constraints)
        logger.info("Training Meso agent (SAC)")
        results["meso"] = self.meso_agent.train(meso_env, meso_timesteps)

        # Train micro (for execution optimization)
        logger.info("Training Micro agent (TD3)")
        results["micro"] = self.micro_agent.train(micro_env, micro_timesteps)

        return results

    def save_all(self, base_path: str | Path) -> None:
        """Save all agents."""
        base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)

        self.macro_agent.save(base_path / "macro_ppo")
        self.meso_agent.save(base_path / "meso_sac")
        self.micro_agent.save(base_path / "micro_td3")

    def load_all(self, base_path: str | Path) -> None:
        """Load all agents."""
        base_path = Path(base_path)

        self.macro_agent.load(base_path / "macro_ppo")
        self.meso_agent.load(base_path / "meso_sac")
        self.micro_agent.load(base_path / "micro_td3")
