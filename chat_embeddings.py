from __future__ import annotations

from functools import lru_cache
import argparse
import json
import os
from pathlib import Path
from typing import Callable, Any


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def create_local_embedder(
    *,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    cache_dir: str | Path | None = None,
) -> Callable[[str], list[float]] | None:
    try:
        from fastembed import TextEmbedding
    except Exception:
        return None

    resolved_cache = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    try:
        resolved_cache.mkdir(parents=True, exist_ok=True)
        model = _text_embedding_model(TextEmbedding, str(model_name), str(resolved_cache))
    except Exception:
        return None

    def embed(text: str) -> list[float]:
        content = str(text or "").strip()
        if not content:
            return []
        try:
            vectors = list(model.embed([content]))
        except Exception:
            return []
        if not vectors:
            return []
        return [float(value) for value in list(vectors[0])]

    return embed


def _default_cache_dir() -> Path:
    root = Path(os.environ.get("COWORK_USER_DATA_DIR") or Path.cwd())
    return root / "chat_memory" / "embeddings"


@lru_cache(maxsize=4)
def _text_embedding_model(text_embedding_cls: Any, model_name: str, cache_dir: str) -> Any:
    return text_embedding_cls(model_name=model_name, cache_dir=cache_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in smoke test for the local fastembed memory embedder.")
    parser.add_argument("--live", action="store_true", help="Required. May download the embedding model on first use.")
    parser.add_argument("--text", default="hello memory")
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--cache-dir", default="")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required because first use may download an embedding model.")
    embedder = create_local_embedder(
        model_name=args.model,
        cache_dir=args.cache_dir or None,
    )
    if embedder is None:
        print(json.dumps({"status": "unavailable", "model": args.model}, ensure_ascii=False))
        return 1
    vector = embedder(args.text)
    print(json.dumps({"status": "ok", "model": args.model, "dimensions": len(vector)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
