"""
module_4_matching/semantic_matcher.py — Semantic similarity scoring signal.

Module 3 already computed a cosine similarity between the report text and
each candidate's (activity_name + activity_description) embedding, as
retrieval_signals.semantic_score. Recomputing that here would mean loading
a second copy of the embedding model for no benefit — the prompt explicitly
says to reuse the embedding model where practical and keep dependencies
minimal — so Module 4 reuses that score directly as its semantic signal.

If a future revision needs a *different* embedding/model for the detailed
matching stage, replace `score_semantic` internals; the SignalResult
contract below is what the rest of Module 4 depends on.
"""

from __future__ import annotations

from .equipment_matcher import SignalResult


def score_semantic(retrieval_signals) -> SignalResult:
    semantic_score = getattr(retrieval_signals, "semantic_score", None)

    if semantic_score is None:
        return SignalResult(0.0, False, False, [])

    score = max(0.0, min(1.0, float(semantic_score)))
    if score >= 0.85:
        label = "High semantic similarity"
    elif score >= 0.5:
        label = "Moderate semantic similarity"
    else:
        label = "Low semantic similarity"
    return SignalResult(score, True, False, [f"{label} (score={score:.2f})"])