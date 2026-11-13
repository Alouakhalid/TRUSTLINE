"""Dual-mode embedding providers supporting local offline SentenceTransformer and deterministic mock."""
import hashlib
import math
import os
from abc import ABC, abstractmethod
from typing import List, Optional

class BaseEmbeddingProvider(ABC):
    """Abstract interface for text embedding generation."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

class SentenceTransformerEmbeddingProvider(BaseEmbeddingProvider):
    """Local dense embedding provider using cached SentenceTransformer models without internet access."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._dimension = 384
        self._model = None
        self._init_model()

    def _init_model(self):
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except Exception as exc:
            raise RuntimeError(f"Failed to load local SentenceTransformer '{self.model_name}': {str(exc)}") from exc

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> List[float]:
        if not self._model:
            raise RuntimeError("SentenceTransformer model is not initialized.")
        cleaned = text.strip() or "empty"
        emb = self._model.encode(cleaned, normalize_embeddings=True)
        return emb.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._model:
            raise RuntimeError("SentenceTransformer model is not initialized.")
        cleaned = [t.strip() or "empty" for t in texts]
        embs = self._model.encode(cleaned, normalize_embeddings=True)
        return embs.tolist()

class DeterministicMockEmbeddingProvider(BaseEmbeddingProvider):
    """Fast, reproducible pseudo-semantic vector generator for offline unit tests without neural models."""

    def __init__(self, dimension: int = 384):
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        vec = [0.0] * self._dim
        words = text.lower().split()
        if not words:
            vec[0] = 1.0
            return vec

        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            weight = math.log1p(len(word))
            vec[idx] += sign * weight

        # Also hash bigrams for slight local semantic awareness
        for i in range(len(words) - 1):
            bg = f"{words[i]}_{words[i+1]}"
            h = int(hashlib.sha256(bg.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            vec[idx] += sign * 1.5

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0
        return vec

def get_embedding_provider(mode: str = "auto") -> BaseEmbeddingProvider:
    """Factory returning either dense local SentenceTransformer or deterministic mock provider."""
    if mode == "mock":
        return DeterministicMockEmbeddingProvider()
    elif mode == "dense":
        return SentenceTransformerEmbeddingProvider()
    
    # Auto mode: try dense, fallback to mock on failure
    try:
        return SentenceTransformerEmbeddingProvider()
    except Exception:
        return DeterministicMockEmbeddingProvider()
