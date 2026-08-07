from __future__ import annotations

from typing import Callable, TypeVar


T = TypeVar("T")


def run_with_model_candidates(
    *,
    candidates: list[str],
    attempt: Callable[[str], T],
    on_fallback: Callable[[str, str, str], None] | None = None,
    no_candidate_error: str = "No model candidate is available.",
) -> tuple[T, str]:
    failures: list[str] = []
    for index, model in enumerate(candidates):
        try:
            return attempt(model), model
        except Exception as exc:
            message = str(exc).strip() or "model request failed"
            failures.append(f"{model}: {message}")
            if index < len(candidates) - 1:
                if on_fallback:
                    on_fallback(model, message, candidates[index + 1])
                continue
            raise RuntimeError("; ".join(failures)) from exc
    raise RuntimeError(no_candidate_error)
