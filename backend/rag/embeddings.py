"""Pluggable embedding providers for the RAG layer.

Default implementation uses scikit-learn's TF-IDF vectorizer so the whole
pipeline works fully offline with zero model downloads -- important since
this environment has no route to huggingface.co to pull BAAI/bge-m3 weights.
Swap in a SentenceTransformerEmbeddingProvider (bge-m3 or similar) once you
have model-hub access, by adding it here and pointing get_embedding_provider()
at it -- everything downstream (retriever.py) only depends on the
EmbeddingProvider interface, not on TF-IDF specifically.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class EmbeddingProvider(ABC):
    @abstractmethod
    def fit(self, corpus: list[str]) -> None: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray: ...


class TfidfEmbeddingProvider(EmbeddingProvider):
    """Good enough for schema-sized corpora (tens to low-thousands of
    table/column descriptions) -- not a semantic embedding, but a fast,
    deterministic, dependency-light default."""

    def __init__(self, max_features: int = 4096):
        self._vectorizer = TfidfVectorizer(max_features=max_features, ngram_range=(1, 2))
        self.is_fitted = False

    def fit(self, corpus: list[str]) -> None:
        if not corpus:
            return
        self._vectorizer.fit(corpus)
        self.is_fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self.is_fitted:
            self.fit(texts)
        return self._vectorizer.transform(texts).toarray()


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = TfidfEmbeddingProvider()
    return _provider
