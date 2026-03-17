from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any

import httpx

logger = logging.getLogger("agroagent.llm")

_llm_lock = Lock()
_llm_metrics = {
    "total_requests": 0,
    "failed_requests": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_latency_ms": 0.0,
}


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def record_llm_metrics(prompt_tokens: int, completion_tokens: int, latency_ms: float, ok: bool) -> None:
    with _llm_lock:
        _llm_metrics["total_requests"] += 1
        if not ok:
            _llm_metrics["failed_requests"] += 1
        _llm_metrics["prompt_tokens"] += max(0, int(prompt_tokens))
        _llm_metrics["completion_tokens"] += max(0, int(completion_tokens))
        _llm_metrics["total_latency_ms"] += float(latency_ms)


def get_llm_metrics() -> dict[str, float]:
    with _llm_lock:
        total = int(_llm_metrics["total_requests"])
        avg_latency = (_llm_metrics["total_latency_ms"] / total) if total else 0.0
        return {
            "total_requests": total,
            "failed_requests": int(_llm_metrics["failed_requests"]),
            "prompt_tokens": int(_llm_metrics["prompt_tokens"]),
            "completion_tokens": int(_llm_metrics["completion_tokens"]),
            "avg_latency_ms": float(avg_latency),
        }


def ollama_chat(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    timeout: float = 30.0,
) -> str:
    start = time.perf_counter()
    prompt_tokens = sum(estimate_tokens(msg.get("content", "")) for msg in messages)
    completion_tokens = 0
    ok = False
    content = ""

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {}) if isinstance(data, dict) else {}
            content = str(msg.get("content", ""))
            completion_tokens = int(data.get("eval_count") or estimate_tokens(content))
            prompt_tokens = int(data.get("prompt_eval_count") or prompt_tokens)
            ok = True
            return content
    except httpx.HTTPError as exc:
        logger.warning("ollama_chat failed: %s", exc)
        return ""
    finally:
        latency_ms = (time.perf_counter() - start) * 1000.0
        record_llm_metrics(prompt_tokens, completion_tokens, latency_ms, ok)
