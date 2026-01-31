"""
CryptoBERT Sentiment Analyzer
=============================

Deep learning sentiment analysis using transformer models
fine-tuned on cryptocurrency text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BertResult:
    """BERT sentiment analysis result."""

    text: str
    label: str
    confidence: float
    scores: dict[str, float]

    @property
    def sentiment_score(self) -> float:
        """Get normalized sentiment score (-1 to 1)."""
        if "positive" in self.scores and "negative" in self.scores:
            return self.scores["positive"] - self.scores["negative"]
        return 0.0


class CryptoBertAnalyzer:
    """
    BERT-based sentiment analyzer for cryptocurrency text.

    Uses pre-trained models from HuggingFace fine-tuned on
    crypto-related text (tweets, Reddit posts, news).

    Recommended models:
    - ElKulako/cryptobert: Fine-tuned on crypto tweets
    - ProsusAI/finbert: Financial sentiment (general)
    - yiyanghkust/finbert-tone: Financial tone analysis
    """

    def __init__(
        self,
        model_name: str = "ElKulako/cryptobert",
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.device = device
        self._pipeline = None
        self._tokenizer = None
        self._model = None

    def _initialize(self) -> bool:
        """Initialize the transformer pipeline."""
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

            logger.info(f"Loading model: {self.model_name}")

            # Try pipeline first (simplest)
            try:
                self._pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.model_name,
                    device=0 if self.device == "cuda" else -1,
                    truncation=True,
                    max_length=512,
                )
                logger.info("Pipeline initialized")
                return True
            except Exception as e:
                logger.warning(f"Pipeline failed, trying manual loading: {e}")

            # Manual loading
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            )

            if self.device == "cuda":
                import torch
                if torch.cuda.is_available():
                    self._model = self._model.cuda()

            logger.info("Model loaded manually")
            return True

        except ImportError:
            logger.warning("transformers not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize CryptoBERT: {e}")
            return False

    def analyze(self, text: str) -> BertResult:
        """
        Analyze sentiment of text using BERT.

        Args:
            text: Text to analyze

        Returns:
            BertResult with sentiment classification
        """
        if self._pipeline is None and self._model is None:
            if not self._initialize():
                return self._fallback_result(text)

        try:
            if self._pipeline:
                result = self._pipeline(text[:512])[0]
                return BertResult(
                    text=text,
                    label=result["label"],
                    confidence=result["score"],
                    scores={result["label"].lower(): result["score"]},
                )
            else:
                return self._analyze_manual(text)

        except Exception as e:
            logger.error(f"BERT analysis error: {e}")
            return self._fallback_result(text)

    def _analyze_manual(self, text: str) -> BertResult:
        """Manual analysis when pipeline is not available."""
        import torch
        import torch.nn.functional as F

        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )

        if self.device == "cuda" and torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = F.softmax(outputs.logits, dim=-1)

        # Get label mapping
        id2label = self._model.config.id2label
        scores = {}
        for idx, prob in enumerate(probs[0].cpu().numpy()):
            label = id2label[idx].lower()
            scores[label] = float(prob)

        # Get top prediction
        top_idx = probs[0].argmax().item()
        top_label = id2label[top_idx]
        top_score = float(probs[0][top_idx])

        return BertResult(
            text=text,
            label=top_label,
            confidence=top_score,
            scores=scores,
        )

    def _fallback_result(self, text: str) -> BertResult:
        """Return neutral result when model is unavailable."""
        return BertResult(
            text=text,
            label="neutral",
            confidence=0.5,
            scores={"positive": 0.33, "negative": 0.33, "neutral": 0.34},
        )

    def analyze_batch(
        self,
        texts: list[str],
        batch_size: int = 16,
    ) -> list[BertResult]:
        """
        Analyze multiple texts in batches.

        More efficient for large numbers of texts.

        Args:
            texts: List of texts to analyze
            batch_size: Batch size for processing

        Returns:
            List of BertResult objects
        """
        if self._pipeline is None and self._model is None:
            if not self._initialize():
                return [self._fallback_result(t) for t in texts]

        results = []

        try:
            if self._pipeline:
                # Pipeline handles batching internally
                truncated = [t[:512] for t in texts]
                pipe_results = self._pipeline(truncated, batch_size=batch_size)

                for text, result in zip(texts, pipe_results):
                    results.append(
                        BertResult(
                            text=text,
                            label=result["label"],
                            confidence=result["score"],
                            scores={result["label"].lower(): result["score"]},
                        )
                    )
            else:
                # Manual batching
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    for text in batch:
                        results.append(self.analyze(text))

        except Exception as e:
            logger.error(f"Batch analysis error: {e}")
            results.extend([self._fallback_result(t) for t in texts[len(results):]])

        return results

    def get_embedding(self, text: str) -> list[float] | None:
        """
        Get text embedding from the model.

        Useful for similarity calculations or downstream ML.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if unavailable
        """
        if self._model is None and self._tokenizer is None:
            if not self._initialize():
                return None

        if self._tokenizer is None or self._model is None:
            return None

        try:
            import torch

            inputs = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            )

            if self.device == "cuda" and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs, output_hidden_states=True)
                # Use CLS token embedding from last hidden state
                embedding = outputs.hidden_states[-1][:, 0, :].squeeze()

            return embedding.cpu().numpy().tolist()

        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None


class FinBertAnalyzer(CryptoBertAnalyzer):
    """
    FinBERT analyzer for financial sentiment.

    Pre-trained on financial news and reports.
    Good for analyzing news headlines and formal content.
    """

    def __init__(self, device: str = "cpu"):
        super().__init__(
            model_name="ProsusAI/finbert",
            device=device,
        )


class MultiModelEnsemble:
    """
    Ensemble of multiple sentiment models for robust predictions.

    Combines VADER (fast, lexicon-based) with BERT models
    for improved accuracy.
    """

    def __init__(self, device: str = "cpu"):
        from mortar_trading.models.sentiment.vader import VaderAnalyzer

        self.vader = VaderAnalyzer()
        self.crypto_bert = CryptoBertAnalyzer(device=device)
        self.fin_bert = FinBertAnalyzer(device=device)

        # Model weights
        self.weights = {
            "vader": 0.2,
            "crypto_bert": 0.5,
            "fin_bert": 0.3,
        }

    def analyze(self, text: str) -> dict[str, Any]:
        """
        Analyze text with all models and ensemble results.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with individual and ensemble results
        """
        # Get individual predictions
        vader_result = self.vader.analyze(text)
        crypto_result = self.crypto_bert.analyze(text)
        fin_result = self.fin_bert.analyze(text)

        # Normalize to common scale (-1 to 1)
        vader_score = vader_result.compound
        crypto_score = crypto_result.sentiment_score
        fin_score = fin_result.sentiment_score

        # Weighted ensemble
        ensemble_score = (
            self.weights["vader"] * vader_score
            + self.weights["crypto_bert"] * crypto_score
            + self.weights["fin_bert"] * fin_score
        )

        # Ensemble confidence (based on agreement)
        scores = [vader_score, crypto_score, fin_score]
        import numpy as np
        agreement = 1 - np.std(scores)  # Higher agreement = higher confidence

        return {
            "text": text,
            "vader": {
                "score": vader_score,
                "label": vader_result.sentiment_label,
            },
            "crypto_bert": {
                "score": crypto_score,
                "label": crypto_result.label,
                "confidence": crypto_result.confidence,
            },
            "fin_bert": {
                "score": fin_score,
                "label": fin_result.label,
                "confidence": fin_result.confidence,
            },
            "ensemble": {
                "score": ensemble_score,
                "label": "positive" if ensemble_score > 0.1 else ("negative" if ensemble_score < -0.1 else "neutral"),
                "confidence": agreement * max(crypto_result.confidence, fin_result.confidence),
            },
        }
