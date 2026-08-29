"""
module_3_candidate/semantic_backend.py — Pluggable semantic similarity backend.

RESPONSIBILITY: Provide `embed(texts: List[str]) -> np.ndarray` and
`cosine_sim(query_vec, matrix) -> np.ndarray` behind one interface, so the
retriever never cares which embedding model is actually running.

WHY A FALLBACK EXISTS:
  sentence-transformers requires downloading model weights from the internet
  on first use. In offline / restricted-network environments (CI, some
  sandboxes) that download fails. Rather than crash the whole retrieval
  layer, we fall back to a TF-IDF + cosine backend (scikit-learn, no network
  needed). This is strictly a degrade-gracefully path — on a normal dev
  machine with network access, sentence-transformers loads and is used.

  This is NOT scope creep: "semantic retrieval must still work if metadata
  is sparse" (equipment tag / location missing) is a stated requirement, and
  a semantic backend that hard-crashes when it can't reach the internet
  would silently break that requirement in some environments.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class SemanticBackend:
    """Wraps whichever embedding strategy is actually available."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        self._mode = None  # "sbert" or "tfidf"
        self._model = None
        self._vectorizer = None
        self._fitted = False
        self._load()

    def _load(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(self.model_name)
            self._mode = "sbert"
            logger.info("SemanticBackend: using sentence-transformers (%s)", self.model_name)
        except Exception as exc:  # noqa: BLE001 - intentional broad catch for graceful degrade
            logger.warning(
                "SemanticBackend: sentence-transformers unavailable (%s). "
                "Falling back to TF-IDF cosine backend.",
                exc,
            )
            self._mode = "tfidf"

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_mode(self) -> str:
        """Returns 'sbert' or 'tfidf' — which backend is actually active.
        Use this to detect a silent fallback (e.g. in health checks or logs)
        rather than poking the private _mode attribute."""
        return self._mode

    def is_fallback(self) -> bool:
        """True if running the TF-IDF degrade path instead of sentence-transformers."""
        return self._mode == "tfidf"

    # ------------------------------------------------------------------
    # Fitting (TF-IDF needs a corpus; sbert does not)
    # ------------------------------------------------------------------

    def fit_corpus(self, corpus: List[str], allow_refit: bool = False) -> None:
        """Must be called once with the full schedule text corpus before
        embedding queries, when running in tfidf mode. No-op for sbert.

        Guards against accidental re-fitting: once fit, a second call raises
        unless allow_refit=True is passed explicitly. This protects against
        a real bug class — e.g. a lone query embedded before the real corpus
        fit silently locking in a 1-document vocabulary, then the real
        fit_corpus() call being skipped because _vectorizer already exists.
        """
        if self._mode != "tfidf":
            return
        if self._fitted and not allow_refit:
            raise RuntimeError(
                "SemanticBackend.fit_corpus() called again after the backend was "
                "already fit. This usually means embed() was called before "
                "fit_corpus() and silently fit on a partial batch. Pass "
                "allow_refit=True if this is intentional."
            )

        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(stop_words="english")
        safe_corpus = [c if c and c.strip() else "unknown" for c in corpus]
        self._vectorizer.fit(safe_corpus)
        self._fitted = True

    def embed(self, texts: List[str]) -> np.ndarray:
        """Returns an (n, d) matrix. Empty/None strings still produce a row
        (never raises), so callers don't need to special-case sparse text."""
        safe_texts = [t if t and t.strip() else "unknown" for t in texts]

        if self._mode == "sbert":
            return np.asarray(self._model.encode(safe_texts, normalize_embeddings=True))

        # tfidf fallback
        if self._vectorizer is None:
            # Not fit yet (e.g. embedding a lone query before fit_corpus) —
            # fit on this batch as a last resort so we never crash. This is
            # logged loudly because it produces a low-quality, batch-local
            # vocabulary rather than the real corpus vocabulary.
            logger.warning(
                "SemanticBackend.embed() called before fit_corpus() — fitting "
                "TF-IDF on this %d-text batch as a last resort. Similarity "
                "quality will be degraded until fit_corpus() is called with "
                "the full corpus.",
                len(safe_texts),
            )
            self.fit_corpus(safe_texts)
        vecs = self._vectorizer.transform(safe_texts).toarray()
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    @staticmethod
    def cosine_sim(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """query_vec: (d,), matrix: (n, d) -> (n,) similarities in [-1, 1]."""
        if matrix.shape[0] == 0:
            return np.array([])
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1e-9
        return (matrix @ query_vec) / norms