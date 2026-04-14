"""3F — Engine: FactExtractor, Scoring, Reconcile, Reflection, Health, Metrics."""

from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.health import MemoryHealthScore, compute_health
from memory_palace.engine.metrics import MemoryMetrics, OperationTimer, get_metrics
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.engine.reflection import ReflectionEngine, should_reflect
from memory_palace.engine.scoring import (
    ScoredCandidate,
    combined_score,
    cosine_similarity,
    importance_score,
    normalize_bm25,
    rank,
    rank_legacy,
    recency_score,
)

__all__ = [
    "FactExtractor",
    "MemoryHealthScore",
    "MemoryMetrics",
    "OperationTimer",
    "ReconcileEngine",
    "ReflectionEngine",
    "ScoredCandidate",
    "combined_score",
    "compute_health",
    "cosine_similarity",
    "get_metrics",
    "importance_score",
    "normalize_bm25",
    "rank",
    "rank_legacy",
    "recency_score",
    "should_reflect",
]
