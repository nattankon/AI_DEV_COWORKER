from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Sequence


DEFAULT_LOCAL_AI_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_LOCAL_AI_MODEL = "local:qwen/qwen3.5-9b"


@dataclass(frozen=True)
class CliConfig:
    workspace: Path
    base_url: str
    api_key: str
    model: str
    prompt: str | None
    auto_approve: bool
    max_iterations: int
    list_models: bool

    @property
    def model_id(self) -> str:
        return self.model.split(":", 1)[1] if self.model.lower().startswith("local:") else self.model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cowork",
        description="Standalone Local AI coding coworker.",
    )
    parser.add_argument("--workspace", help="Workspace directory. Defaults to the current directory.")
    parser.add_argument("--base-url", help="OpenAI-compatible Local AI base URL.")
    parser.add_argument("--api-key", help="Local AI API key when the server requires one.")
    parser.add_argument("--model", help="Local model identifier, optionally prefixed with local:.")
    parser.add_argument("--prompt", help="Run one prompt and exit instead of entering interactive mode.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Approve all proposed file writes and allowlisted verification runs in this process.",
    )
    parser.add_argument("--max-iterations", type=int, default=20, help="Maximum model/tool loop iterations.")
    parser.add_argument("--list-models", action="store_true", help="List models exposed by Local AI and exit.")
    return parser


def parse_cli_args(argv: Sequence[str] | None = None, cwd: Path | None = None) -> CliConfig:
    args = build_parser().parse_args(argv)
    current_dir = Path.cwd() if cwd is None else Path(cwd)
    workspace = Path(args.workspace).expanduser() if args.workspace else current_dir
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ValueError(f"Workspace directory does not exist: {workspace}")
    if args.max_iterations < 1:
        raise ValueError("--max-iterations must be at least 1.")

    base_url = (args.base_url or os.environ.get("LOCAL_AI_BASE_URL") or DEFAULT_LOCAL_AI_BASE_URL).rstrip("/")
    api_key = args.api_key if args.api_key is not None else os.environ.get("LOCAL_AI_API_KEY", "")
    model = args.model or os.environ.get("LOCAL_AI_MODEL") or DEFAULT_LOCAL_AI_MODEL

    return CliConfig(
        workspace=workspace,
        base_url=base_url,
        api_key=api_key,
        model=model,
        prompt=args.prompt,
        auto_approve=bool(args.yes),
        max_iterations=args.max_iterations,
        list_models=bool(args.list_models),
    )
