from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


PROFILE_FILENAME = "model-performance-profile.json"


def build_model_performance_profile(matrix: dict[str, Any]) -> dict[str, Any]:
    cells = [cell for cell in matrix.get("cells", []) if isinstance(cell, dict)]
    by_model_category: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for cell in cells:
        model = str(cell.get("model") or "").strip()
        category = str(cell.get("category") or "general").strip() or "general"
        if not model:
            continue
        by_model_category.setdefault(model, {}).setdefault(category, []).append(cell)

    models: dict[str, Any] = {}
    for model, categories in by_model_category.items():
        category_metrics = {category: _summarize_cells(items) for category, items in categories.items()}
        all_cells = [cell for items in categories.values() for cell in items]
        models[model] = {
            "overall": _summarize_cells(all_cells),
            "categories": category_metrics,
        }

    return {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "models": models,
    }


def save_model_performance_profile(matrix: dict[str, Any], *, output_dir: str | Path = "work_logs") -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / PROFILE_FILENAME
    profile = build_model_performance_profile(matrix)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"profile": str(path)}


def load_model_performance_profile(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "models": {}}
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), dict):
        return {"schema_version": 1, "models": {}}
    return payload


def _summarize_cells(cells: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cells)
    skipped = sum(1 for cell in cells if cell.get("status") == "skipped")
    executed_cells = [cell for cell in cells if cell.get("status") != "skipped"]
    executed = len(executed_cells)
    passed = sum(1 for cell in executed_cells if cell.get("status") == "pass")
    failed = sum(1 for cell in executed_cells if cell.get("status") in {"fail", "failed"})
    hallucinated = sum(1 for cell in executed_cells if cell.get("hallucinated"))
    source_quality_ok = sum(1 for cell in executed_cells if cell.get("source_quality_ok", True))
    score_values = [float(cell.get("score") or 0) for cell in executed_cells]
    latencies = [int(cell.get("latency_ms") or 0) for cell in executed_cells if int(cell.get("latency_ms") or 0) > 0]
    pass_rate = round(passed / executed, 4) if executed else 0.0
    hallucination_rate = round(hallucinated / executed, 4) if executed else 0.0
    source_quality_rate = round(source_quality_ok / executed, 4) if executed else 0.0
    avg_score = round(sum(score_values) / len(score_values), 4) if score_values else 0.0
    avg_latency_ms = int(sum(latencies) / len(latencies)) if latencies else 0
    latency_penalty = min(0.25, avg_latency_ms / 120_000) if avg_latency_ms else 0.0
    router_score = max(0.0, round((pass_rate * 0.65) + (avg_score / 5 * 0.25) + (source_quality_rate * 0.1) - (hallucination_rate * 0.5) - latency_penalty, 4))
    return {
        "total": total,
        "executed": executed,
        "skipped": skipped,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "avg_score": avg_score,
        "avg_latency_ms": avg_latency_ms,
        "hallucination_rate": hallucination_rate,
        "source_quality_rate": source_quality_rate,
        "router_score": router_score if executed else 0.0,
    }
