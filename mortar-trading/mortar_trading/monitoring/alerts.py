"""
Alert Manager
=============

Sends alerts via Telegram, Discord, etc.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import aiohttp
import structlog

from mortar_trading.config import Settings

logger = structlog.get_logger(__name__)


class TelegramNotifier:
    """Telegram notification sender."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram."""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        text = await response.text()
                        logger.warning(f"Telegram error: {text}")
                        return False

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False


class DiscordNotifier:
    """Discord webhook notification sender."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_message(
        self,
        message: str,
        title: str | None = None,
        color: int = 0x00FF00,
    ) -> bool:
        """Send a message to Discord."""
        try:
            payload = {
                "embeds": [
                    {
                        "title": title or "Mortar Trading Alert",
                        "description": message,
                        "color": color,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    return response.status == 204

        except Exception as e:
            logger.error(f"Discord send error: {e}")
            return False


class AlertManager:
    """
    Manages alerts and notifications.

    Supports:
    - Telegram notifications
    - Discord webhooks
    - Rate limiting to prevent spam
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.alert_config = settings.monitoring.alerts

        # Initialize notifiers
        self._telegram: TelegramNotifier | None = None
        self._discord: DiscordNotifier | None = None

        if self.alert_config.telegram_enabled and self.alert_config.telegram_bot_token:
            self._telegram = TelegramNotifier(
                bot_token=self.alert_config.telegram_bot_token.get_secret_value(),
                chat_id=self.alert_config.telegram_chat_id or "",
            )

        if self.alert_config.discord_enabled and self.alert_config.discord_webhook_url:
            self._discord = DiscordNotifier(
                webhook_url=self.alert_config.discord_webhook_url.get_secret_value(),
            )

        # Rate limiting
        self._last_alerts: dict[str, datetime] = {}
        self._min_interval_seconds = 60  # Minimum 1 minute between same alerts

    async def send_alert(
        self,
        title: str,
        message: str,
        level: str = "info",
        symbol: str | None = None,
    ) -> None:
        """
        Send an alert to all configured channels.

        Args:
            title: Alert title
            message: Alert message
            level: Alert level (info, warning, error, critical)
            symbol: Optional trading symbol
        """
        # Rate limit check
        alert_key = f"{title}:{symbol}"
        if not self._should_send_alert(alert_key):
            return

        self._last_alerts[alert_key] = datetime.utcnow()

        # Format message
        emoji = self._get_emoji(level)
        formatted = f"{emoji} <b>{title}</b>\n\n{message}"

        if symbol:
            formatted += f"\n\nSymbol: {symbol}"

        formatted += f"\n\nTime: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

        # Send to all channels
        tasks = []

        if self._telegram:
            tasks.append(self._telegram.send_message(formatted))

        if self._discord:
            color = self._get_discord_color(level)
            tasks.append(self._discord.send_message(message, title, color))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Alert sent", title=title, level=level, symbol=symbol)

    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if alert should be sent based on rate limiting."""
        last_sent = self._last_alerts.get(alert_key)
        if not last_sent:
            return True

        elapsed = (datetime.utcnow() - last_sent).total_seconds()
        return elapsed >= self._min_interval_seconds

    def _get_emoji(self, level: str) -> str:
        """Get emoji for alert level."""
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
            "success": "✅",
            "trade": "💰",
        }
        return emojis.get(level, "📢")

    def _get_discord_color(self, level: str) -> int:
        """Get Discord embed color for alert level."""
        colors = {
            "info": 0x3498DB,  # Blue
            "warning": 0xF39C12,  # Yellow
            "error": 0xE74C3C,  # Red
            "critical": 0x992D22,  # Dark red
            "success": 0x2ECC71,  # Green
            "trade": 0x9B59B6,  # Purple
        }
        return colors.get(level, 0x95A5A6)

    # Convenience methods

    async def alert_trade_opened(self, symbol: str, side: str, quantity: float, price: float) -> None:
        """Alert for new trade opened."""
        message = f"Opened {side.upper()} position\n"
        message += f"Quantity: {quantity}\n"
        message += f"Entry Price: ${price:,.2f}"
        await self.send_alert("Trade Opened", message, "trade", symbol)

    async def alert_trade_closed(
        self,
        symbol: str,
        side: str,
        pnl: float,
        pnl_pct: float,
    ) -> None:
        """Alert for trade closed."""
        level = "success" if pnl >= 0 else "warning"
        message = f"Closed {side.upper()} position\n"
        message += f"PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)"
        await self.send_alert("Trade Closed", message, level, symbol)

    async def alert_circuit_breaker(self, period: str, loss_pct: float) -> None:
        """Alert for circuit breaker triggered."""
        message = f"Loss limit exceeded for {period}\n"
        message += f"Loss: {loss_pct:.2f}%\n"
        message += "Trading halted until cooldown expires"
        await self.send_alert("Circuit Breaker Triggered", message, "critical")

    async def alert_regime_change(self, symbol: str, old_regime: str, new_regime: str) -> None:
        """Alert for regime change."""
        message = f"Regime changed: {old_regime} → {new_regime}"
        await self.send_alert("Regime Change", message, "info", symbol)

    async def alert_volatility_spike(self, symbol: str, volatility: float, zscore: float) -> None:
        """Alert for volatility spike."""
        message = f"Volatility spike detected\n"
        message += f"Current Vol: {volatility:.2%}\n"
        message += f"Z-Score: {zscore:.2f}"
        await self.send_alert("Volatility Spike", message, "warning", symbol)
