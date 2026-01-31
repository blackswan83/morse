"""
VADER Sentiment Analyzer
========================

Real-time sentiment analysis using VADER (Valence Aware Dictionary
and sEntiment Reasoner) optimized for social media text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class VaderResult:
    """VADER sentiment analysis result."""

    text: str
    positive: float
    negative: float
    neutral: float
    compound: float

    @property
    def sentiment_label(self) -> str:
        """Get sentiment label based on compound score."""
        if self.compound >= 0.05:
            return "positive"
        elif self.compound <= -0.05:
            return "negative"
        return "neutral"


class VaderAnalyzer:
    """
    VADER-based sentiment analyzer with crypto-specific enhancements.

    VADER is well-suited for social media text (Twitter, Reddit) and
    provides real-time analysis without GPU requirements.
    """

    def __init__(self):
        self._analyzer = None
        self._crypto_lexicon = self._build_crypto_lexicon()

    def _build_crypto_lexicon(self) -> dict[str, float]:
        """
        Build crypto-specific lexicon additions.

        These words have specific sentiment in crypto context that
        differs from general usage.
        """
        return {
            # Bullish terms
            "moon": 3.0,
            "mooning": 3.5,
            "bullish": 2.5,
            "pump": 2.0,
            "pumping": 2.5,
            "hodl": 1.5,
            "hodling": 1.5,
            "diamond hands": 2.5,
            "ath": 2.5,  # All-time high
            "breakout": 2.0,
            "accumulate": 1.5,
            "accumulating": 1.5,
            "dip": 1.0,  # Buying opportunity
            "buy the dip": 2.0,
            "btd": 2.0,
            "fomo": 1.5,  # Fear of missing out
            "wagmi": 2.0,  # We're all gonna make it
            "lfg": 2.0,  # Let's f***ing go
            "gm": 0.5,  # Good morning (positive signal)
            "rocket": 2.0,
            "green": 1.5,
            "gains": 2.0,
            "profit": 2.0,
            "rally": 2.0,
            "surge": 2.0,
            "soaring": 2.5,
            "skyrocket": 3.0,
            "halving": 1.5,
            "adoption": 1.5,
            "institutional": 1.0,
            "whale": 1.0,  # Context dependent
            "accumulation": 1.5,

            # Bearish terms
            "dump": -2.5,
            "dumping": -3.0,
            "bearish": -2.5,
            "crash": -3.0,
            "crashed": -3.5,
            "crashing": -3.5,
            "rekt": -3.0,
            "rug": -4.0,
            "rugpull": -4.0,
            "rug pull": -4.0,
            "scam": -3.5,
            "scammer": -3.5,
            "ponzi": -4.0,
            "liquidated": -3.0,
            "liquidation": -2.5,
            "ngmi": -2.0,  # Not gonna make it
            "paper hands": -2.0,
            "fud": -2.0,  # Fear, uncertainty, doubt
            "bear market": -2.0,
            "red": -1.5,
            "loss": -2.0,
            "losses": -2.0,
            "bleeding": -2.5,
            "plunge": -2.5,
            "collapse": -3.0,
            "tank": -2.5,
            "tanking": -3.0,
            "selloff": -2.0,
            "sell-off": -2.0,
            "capitulation": -3.0,
            "fear": -2.0,
            "panic": -2.5,
            "hack": -3.0,
            "hacked": -3.5,
            "exploit": -3.0,
            "ban": -2.5,
            "banned": -2.5,
            "regulation": -1.0,  # Context dependent
            "sec": -1.0,  # Context dependent
            "lawsuit": -2.5,

            # Neutral/contextual terms
            "whale watching": 0.5,
            "dyor": 0.0,  # Do your own research
            "nfa": 0.0,  # Not financial advice
            "ta": 0.0,  # Technical analysis
            "defi": 0.5,
            "nft": 0.0,
            "staking": 0.5,
            "yield": 0.5,
            "airdrop": 1.0,
        }

    def _initialize_analyzer(self) -> None:
        """Initialize VADER analyzer with custom lexicon."""
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self._analyzer = SentimentIntensityAnalyzer()

            # Add crypto-specific lexicon
            for word, score in self._crypto_lexicon.items():
                self._analyzer.lexicon[word] = score

            logger.info("VADER analyzer initialized with crypto lexicon")

        except ImportError:
            logger.warning("vaderSentiment not installed, using fallback")
            self._analyzer = None

    def preprocess(self, text: str) -> str:
        """
        Preprocess text for sentiment analysis.

        - Handles cashtags ($BTC, $ETH)
        - Preserves emoticons
        - Handles common crypto abbreviations
        """
        # Convert to lowercase for lexicon matching
        text = text.lower()

        # Handle cashtags (preserve but normalize)
        text = re.sub(r'\$([a-zA-Z]+)', r'\1', text)

        # Handle common crypto Twitter patterns
        text = re.sub(r'#(\w+)', r'\1', text)  # Remove hashtag symbol

        # Normalize multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def analyze(self, text: str) -> VaderResult:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            VaderResult with sentiment scores
        """
        if self._analyzer is None:
            self._initialize_analyzer()

        processed_text = self.preprocess(text)

        if self._analyzer:
            scores = self._analyzer.polarity_scores(processed_text)
            return VaderResult(
                text=text,
                positive=scores["pos"],
                negative=scores["neg"],
                neutral=scores["neu"],
                compound=scores["compound"],
            )
        else:
            # Fallback: simple word matching
            return self._fallback_analyze(processed_text)

    def _fallback_analyze(self, text: str) -> VaderResult:
        """Fallback analysis when VADER is not available."""
        words = text.split()

        positive_score = 0.0
        negative_score = 0.0

        for word in words:
            if word in self._crypto_lexicon:
                score = self._crypto_lexicon[word]
                if score > 0:
                    positive_score += score
                else:
                    negative_score += abs(score)

        # Normalize
        total = positive_score + negative_score
        if total > 0:
            pos = positive_score / (total * 2)
            neg = negative_score / (total * 2)
            neu = 1 - pos - neg
            compound = (positive_score - negative_score) / (total + 1)
        else:
            pos = neg = 0.0
            neu = 1.0
            compound = 0.0

        return VaderResult(
            text=text,
            positive=min(pos, 1.0),
            negative=min(neg, 1.0),
            neutral=max(neu, 0.0),
            compound=max(min(compound, 1.0), -1.0),
        )

    def analyze_batch(self, texts: list[str]) -> list[VaderResult]:
        """
        Analyze multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of VaderResult objects
        """
        return [self.analyze(text) for text in texts]

    def get_aggregate_sentiment(
        self,
        results: list[VaderResult],
        weights: list[float] | None = None,
    ) -> dict[str, float]:
        """
        Aggregate multiple sentiment results.

        Args:
            results: List of VaderResult objects
            weights: Optional weights for each result (e.g., follower count)

        Returns:
            Dictionary with aggregated metrics
        """
        if not results:
            return {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 0.0,
                "compound": 0.0,
                "count": 0,
            }

        if weights is None:
            weights = [1.0] * len(results)

        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1

        weighted_pos = sum(r.positive * w for r, w in zip(results, weights)) / total_weight
        weighted_neg = sum(r.negative * w for r, w in zip(results, weights)) / total_weight
        weighted_neu = sum(r.neutral * w for r, w in zip(results, weights)) / total_weight
        weighted_compound = sum(r.compound * w for r, w in zip(results, weights)) / total_weight

        return {
            "positive": weighted_pos,
            "negative": weighted_neg,
            "neutral": weighted_neu,
            "compound": weighted_compound,
            "count": len(results),
            "bullish_ratio": sum(1 for r in results if r.compound > 0.05) / len(results),
            "bearish_ratio": sum(1 for r in results if r.compound < -0.05) / len(results),
        }
