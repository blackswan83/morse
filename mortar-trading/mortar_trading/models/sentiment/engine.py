"""
Sentiment Engine
================

Main sentiment analysis engine that coordinates all components.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from mortar_trading.config import Settings
from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.models.sentiment.vader import VaderAnalyzer
from mortar_trading.models.sentiment.crypto_bert import CryptoBertAnalyzer
from mortar_trading.models.sentiment.aggregator import SentimentAggregator

logger = structlog.get_logger(__name__)


class LunarCrushClient:
    """Client for LunarCrush social metrics API."""

    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self.base_url = "https://lunarcrush.com/api4/public"

    async def get_coin_metrics(self, symbol: str) -> dict[str, Any] | None:
        """Get social metrics for a coin."""
        if not self.api_key:
            return None

        try:
            import aiohttp

            # Map trading symbols to coin names
            symbol_map = {
                "BTCUSDT": "bitcoin",
                "ETHUSDT": "ethereum",
                "SOLUSDT": "solana",
                "BNBUSDT": "binance-coin",
                "XRPUSDT": "ripple",
                "ADAUSDT": "cardano",
                "AVAXUSDT": "avalanche",
                "DOTUSDT": "polkadot",
                "MATICUSDT": "polygon",
                "LINKUSDT": "chainlink",
            }

            coin = symbol_map.get(symbol, symbol.lower().replace("usdt", ""))
            url = f"{self.base_url}/coins/{coin}/v1"

            headers = {"Authorization": f"Bearer {self.api_key}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(
                            "LunarCrush API error",
                            status=response.status,
                            symbol=symbol,
                        )
                        return None

        except Exception as e:
            logger.error("LunarCrush fetch error", error=str(e))
            return None

    def parse_metrics(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse LunarCrush response into standardized format."""
        if not data or "data" not in data:
            return {}

        coin_data = data["data"]

        return {
            "galaxy_score": coin_data.get("galaxy_score", 0),
            "alt_rank": coin_data.get("alt_rank", 0),
            "social_volume": coin_data.get("social_volume", 0),
            "social_score": coin_data.get("social_score", 0),
            "social_contributors": coin_data.get("social_contributors", 0),
            "social_dominance": coin_data.get("social_dominance", 0),
            "market_dominance": coin_data.get("market_dominance", 0),
            "sentiment": coin_data.get("sentiment", 50) / 100 * 2 - 1,  # Normalize to -1 to 1
            "spam_ratio": coin_data.get("spam_ratio", 0),
            "news_count": coin_data.get("news", 0),
        }


class SantimentClient:
    """Client for Santiment on-chain and social metrics."""

    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self.base_url = "https://api.santiment.net/graphql"

    async def get_social_volume(
        self,
        symbol: str,
        hours: int = 24,
    ) -> dict[str, Any] | None:
        """Get social volume metrics."""
        if not self.api_key:
            return None

        try:
            import aiohttp

            # Map to Santiment slugs
            symbol_map = {
                "BTCUSDT": "bitcoin",
                "ETHUSDT": "ethereum",
                "SOLUSDT": "solana",
                "BNBUSDT": "binance-coin",
            }

            slug = symbol_map.get(symbol, symbol.lower().replace("usdt", ""))

            query = """
            query ($slug: String!, $from: DateTime!, $to: DateTime!) {
                getMetric(metric: "social_volume_total") {
                    timeseriesData(
                        slug: $slug,
                        from: $from,
                        to: $to,
                        interval: "1h"
                    ) {
                        datetime
                        value
                    }
                }
                sentiment: getMetric(metric: "sentiment_balance") {
                    timeseriesData(
                        slug: $slug,
                        from: $from,
                        to: $to,
                        interval: "1h"
                    ) {
                        datetime
                        value
                    }
                }
            }
            """

            from_time = (datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat()
            to_time = datetime.utcnow().isoformat()

            variables = {
                "slug": slug,
                "from": from_time,
                "to": to_time,
            }

            headers = {
                "Authorization": f"Apikey {self.api_key}",
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json={"query": query, "variables": variables},
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None

        except Exception as e:
            logger.error("Santiment fetch error", error=str(e))
            return None


class SentimentEngine:
    """
    Main sentiment analysis engine.

    Coordinates:
    - Real-time text analysis (VADER, CryptoBERT)
    - External sentiment APIs (LunarCrush, Santiment)
    - Sentiment aggregation and feature generation
    - Signal publishing to event bus
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.event_bus = get_event_bus()

        # Initialize analyzers
        self.vader = VaderAnalyzer()
        self.crypto_bert = CryptoBertAnalyzer(device="cpu")

        # Initialize aggregator
        self.aggregator = SentimentAggregator(
            zscore_window=settings.sentiment.sentiment_zscore_window,
            volume_decay=settings.sentiment.volume_weight_decay,
        )

        # Initialize API clients
        self.lunarcrush = LunarCrushClient(
            api_key=(
                settings.lunarcrush_api_key.get_secret_value()
                if settings.lunarcrush_api_key
                else None
            )
        )
        self.santiment = SantimentClient(
            api_key=(
                settings.santiment_api_key.get_secret_value()
                if settings.santiment_api_key
                else None
            )
        )

        self._running = False

    async def start(self) -> None:
        """Start the sentiment engine."""
        logger.info("Starting sentiment engine")
        self._running = True

    async def stop(self) -> None:
        """Stop the sentiment engine."""
        logger.info("Stopping sentiment engine")
        self._running = False

    async def update(self) -> None:
        """
        Update sentiment for all symbols.

        Called periodically by the main engine.
        """
        if not self._running:
            return

        symbols = self.settings.symbols.all_symbols

        for symbol in symbols:
            try:
                await self._update_symbol(symbol)
            except Exception as e:
                logger.error(f"Sentiment update error for {symbol}", error=str(e))

            await asyncio.sleep(0.5)  # Rate limiting

    async def _update_symbol(self, symbol: str) -> None:
        """Update sentiment for a single symbol."""
        # Fetch from LunarCrush
        lunar_data = await self.lunarcrush.get_coin_metrics(symbol)
        if lunar_data:
            metrics = self.lunarcrush.parse_metrics(lunar_data)
            self.aggregator.add_raw_data(
                symbol=symbol,
                source="lunarcrush",
                score=metrics.get("sentiment", 0),
                volume=metrics.get("social_volume", 1),
                raw_data=metrics,
            )

        # Fetch from Santiment
        sant_data = await self.santiment.get_social_volume(symbol, hours=24)
        if sant_data and "data" in sant_data:
            # Extract latest sentiment
            sentiment_data = sant_data.get("data", {}).get("sentiment", {})
            if sentiment_data and sentiment_data.get("timeseriesData"):
                latest = sentiment_data["timeseriesData"][-1]
                self.aggregator.add_raw_data(
                    symbol=symbol,
                    source="santiment",
                    score=latest.get("value", 0) / 100,  # Normalize
                    volume=1,
                    raw_data=sant_data,
                )

        # Get aggregated sentiment
        sentiment = self.aggregator.get_features(symbol)
        signal = self.aggregator.get_signal(symbol)

        # Publish sentiment update
        await self.event_bus.publish(
            Event(
                event_type=EventType.SENTIMENT_UPDATE,
                payload={
                    "symbol": symbol,
                    "features": sentiment,
                    "signal": signal,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                symbol=symbol,
                source="sentiment_engine",
            )
        )

        logger.debug(
            "Sentiment updated",
            symbol=symbol,
            direction=signal["direction"],
            zscore=signal["zscore"],
        )

    async def analyze_text(self, text: str) -> dict[str, Any]:
        """
        Analyze sentiment of arbitrary text.

        Args:
            text: Text to analyze

        Returns:
            Combined sentiment analysis
        """
        vader_result = self.vader.analyze(text)
        bert_result = self.crypto_bert.analyze(text)

        return {
            "text": text,
            "vader": {
                "score": vader_result.compound,
                "label": vader_result.sentiment_label,
            },
            "bert": {
                "score": bert_result.sentiment_score,
                "label": bert_result.label,
                "confidence": bert_result.confidence,
            },
            "combined_score": (vader_result.compound + bert_result.sentiment_score) / 2,
        }

    async def process_social_data(
        self,
        symbol: str,
        texts: list[str],
        source: str,
        weights: list[float] | None = None,
    ) -> dict[str, Any]:
        """
        Process batch of social media texts for a symbol.

        Args:
            symbol: Trading symbol
            texts: List of texts to analyze
            source: Source name (twitter, reddit, etc.)
            weights: Optional weights (e.g., follower counts)

        Returns:
            Aggregated sentiment
        """
        if not texts:
            return {"score": 0, "count": 0}

        # Analyze all texts
        vader_results = self.vader.analyze_batch(texts)

        # Calculate aggregate
        aggregate = self.vader.get_aggregate_sentiment(vader_results, weights)

        # Add to aggregator
        for i, result in enumerate(vader_results):
            weight = weights[i] if weights else 1.0
            self.aggregator.add_raw_data(
                symbol=symbol,
                source=source,
                score=result.compound,
                volume=1,
                influence=weight,
                raw_data={"text": result.text},
            )

        return aggregate

    def get_sentiment(self, symbol: str) -> dict[str, Any]:
        """Get current sentiment for a symbol."""
        return {
            "current": self.aggregator.get_current_sentiment(symbol, 4),
            "zscore": self.aggregator.get_zscore(symbol, 4),
            "momentum": self.aggregator.get_momentum(symbol, 1, 24),
            "by_source": self.aggregator.get_by_source(symbol, 4),
            "signal": self.aggregator.get_signal(symbol),
        }

    def get_all_features(self) -> dict[str, dict[str, float]]:
        """Get sentiment features for all symbols."""
        features = {}
        for symbol in self.settings.symbols.all_symbols:
            features[symbol] = self.aggregator.get_features(symbol)
        return features
