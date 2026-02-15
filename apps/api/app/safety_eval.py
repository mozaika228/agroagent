from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .agents.pipeline import run_hierarchical_debate
from .safety import evaluate_agro_policy


DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "safety_benchmark_sample.jsonl"
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "safety_reports"
LABELS = ("allow", "warn", "block")


def load_safety_cases(dataset_path: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    if not path.exists():
        raise FileNotFoundError(f"dataset not found: {path}")

    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            item = json.loads(raw)
            if "question" not in item or "expected_action" not in item:
                continue
            cases.append(item)

    if limit and limit > 0:
        return cases[:limit]
    return cases


def _precision_recall(pred: Counter[tuple[str, str]], label: str) -> tuple[float, float]:
    tp = pred[(label, label)]
    fp = sum(pred[(expected, label)] for expected in LABELS if expected != label)
    fn = sum(pred[(label, predicted)] for predicted in LABELS if predicted != label)
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0
    return round(precision, 4), round(recall, 4)


def run_safety_benchmark(cases: list[dict[str, Any]], rounds: int = 2) -> dict[str, Any]:
    pairs: Counter[tuple[str, str]] = Counter()
    mismatches: list[dict[str, Any]] = []

    for idx, item in enumerate(cases):
        question = str(item["question"])
        locale = str(item.get("locale", "ru"))
        expected = str(item["expected_action"]).lower()
        if expected not in LABELS:
            continue

        _, final = run_hierarchical_debate(question, locale=locale, rounds=rounds)
        decision = evaluate_agro_policy(question, str(final["answer"]), locale)
        predicted = decision.action
        pairs[(expected, predicted)] += 1

        if expected != predicted and len(mismatches) < 25:
            mismatches.append(
                {
                    "index": idx,
                    "locale": locale,
                    "question": question,
                    "expected_action": expected,
                    "predicted_action": predicted,
                    "rules_triggered": decision.rules_triggered,
                }
            )

    total = sum(pairs.values())
    correct = sum(pairs[(label, label)] for label in LABELS)
    accuracy = round((correct / total), 4) if total else 0.0

    block_p, block_r = _precision_recall(pairs, "block")
    warn_p, warn_r = _precision_recall(pairs, "warn")
    allow_p, allow_r = _precision_recall(pairs, "allow")

    return {
        "total": total,
        "accuracy": accuracy,
        "block_precision": block_p,
        "block_recall": block_r,
        "warn_precision": warn_p,
        "warn_recall": warn_r,
        "allow_precision": allow_p,
        "allow_recall": allow_r,
        "mismatches": mismatches,
    }


def export_safety_report(
    *,
    result: dict[str, Any],
    dataset: str,
    model: str,
    rounds: int,
    report_dir: str | None = None,
    report_name: str | None = None,
) -> dict[str, str]:
    base_dir = Path(report_dir) if report_dir else DEFAULT_REPORTS_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = (report_name or f"safety_eval_{stamp}").replace(" ", "_")
    md_path = base_dir / f"{safe_name}.md"
    csv_path = base_dir / f"{safe_name}_mismatches.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "locale", "question", "expected_action", "predicted_action", "rules_triggered"],
        )
        writer.writeheader()
        for item in result.get("mismatches", []):
            writer.writerow(
                {
                    "index": item.get("index"),
                    "locale": item.get("locale"),
                    "question": item.get("question"),
                    "expected_action": item.get("expected_action"),
                    "predicted_action": item.get("predicted_action"),
                    "rules_triggered": ",".join(item.get("rules_triggered", [])),
                }
            )

    lines = [
        "# Safety Benchmark Report",
        "",
        f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        f"- Dataset: `{dataset}`",
        f"- Model: `{model}`",
        f"- Rounds: `{rounds}`",
        "",
        "## Metrics",
        "",
        f"- Total: **{result.get('total', 0)}**",
        f"- Accuracy: **{result.get('accuracy', 0.0):.4f}**",
        f"- Block precision/recall: **{result.get('block_precision', 0.0):.4f} / {result.get('block_recall', 0.0):.4f}**",
        f"- Warn precision/recall: **{result.get('warn_precision', 0.0):.4f} / {result.get('warn_recall', 0.0):.4f}**",
        f"- Allow precision/recall: **{result.get('allow_precision', 0.0):.4f} / {result.get('allow_recall', 0.0):.4f}**",
        "",
        "## Artifacts",
        "",
        f"- CSV mismatches: `{csv_path}`",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "markdown_report_path": str(md_path),
        "csv_mismatches_path": str(csv_path),
    }
