from __future__ import annotations

import logging
from threading import Lock
from typing import Any

logger = logging.getLogger("agroagent.rerank")

_model_lock = Lock()
_reranker = None
_reranker_name: str | None = None


def _load_reranker(model_name: str):
    global _reranker, _reranker_name
    with _model_lock:
        if _reranker is not None and _reranker_name == model_name:
            return _reranker
        try:
            from sentence_transformers import CrossEncoder

            _reranker = CrossEncoder(model_name)
            _reranker_name = model_name
            logger.info("Loaded reranker model: %s", model_name)
            return _reranker
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reranker disabled (load failed): %s", exc)
            _reranker = None
            _reranker_name = None
            return None


def rerank_candidates(
    *,
    query: str,
    candidates: list[dict[str, Any]],
    model_name: str,
    batch_size: int,
    top_k: int,
) -> list[dict[str, Any]]:
    if not candidates:
        return []

    model = _load_reranker(model_name)
    if model is None:
        return candidates

    pairs = [(query, item.get("chunk_text", "")) for item in candidates[:top_k]]
    try:
        scores = model.predict(pairs, batch_size=max(1, batch_size))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reranker failed: %s", exc)
        return candidates

    for item, score in zip(candidates, scores):
        item["rerank_score"] = float(score)

    ranked = sorted(
        candidates,
        key=lambda item: (item.get("rerank_score") is not None, item.get("rerank_score", 0.0), item.get("score", 0.0)),
        reverse=True,
    )
    return ranked
