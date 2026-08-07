from __future__ import annotations

from dataclasses import dataclass, field
import subprocess
import sys
from typing import Callable, TextIO

try:
    from .cli_config import CliConfig, parse_cli_args
    from .cowork_agent import CoworkAgent, JsonlSessionRecorder, OpenAIChatModel
    from .developer_tools import CommandProposal
    from .local_ai import fetch_local_ai_models
    from .session_store import record_cowork_event
    from .workspace_tools import WorkspaceTools, WriteProposal
except ImportError:
    from cli_config import CliConfig, parse_cli_args
    from cowork_agent import CoworkAgent, JsonlSessionRecorder, OpenAIChatModel
    from developer_tools import CommandProposal
    from local_ai import fetch_local_ai_models
    from session_store import record_cowork_event
    from workspace_tools import WorkspaceTools, WriteProposal


@dataclass
class CliDependencies:
    stdout: TextIO = field(default_factory=lambda: sys.stdout)
    stderr: TextIO = field(default_factory=lambda: sys.stderr)
    input_fn: Callable[[str], str] = input
    model_factory: Callable[[CliConfig], object] = field(
        default=lambda config: OpenAIChatModel(config.base_url, config.api_key, config.model)
    )
    model_lister: Callable[[CliConfig], list[str]] = field(
        default=lambda config: fetch_local_ai_models(config.base_url, config.api_key)
    )
    recorder_factory: Callable[[], object] = JsonlSessionRecorder


def main(argv: list[str] | None = None, dependencies: CliDependencies | None = None) -> int:
    deps = dependencies or CliDependencies()
    try:
        config = parse_cli_args(argv)
        if config.list_models:
            for model_id in deps.model_lister(config):
                print(f"local:{model_id}", file=deps.stdout)
            return 0

        tools = WorkspaceTools(
            config.workspace,
            approve_write=_approval_adapter(config, deps),
            approve_command=_command_approval_adapter(config, deps),
            audit_sink=record_cowork_event,
        )
        agent = CoworkAgent(
            model=deps.model_factory(config),
            model_name=config.model,
            workspace=config.workspace,
            tools=tools,
            recorder=deps.recorder_factory(),
            max_iterations=config.max_iterations,
            event_sink=lambda event_type, payload: _render_event(event_type, payload, deps.stderr),
        )

        if config.prompt is not None:
            print(agent.run(config.prompt), file=deps.stdout)
            return 0

        return _interactive_loop(agent, config, deps)
    except (EOFError, KeyboardInterrupt):
        print(file=deps.stdout)
        return 0
    except Exception as exc:
        print(f"Cowork error: {exc}", file=deps.stderr)
        return 1


def run() -> None:
    raise SystemExit(main())


def _interactive_loop(agent: CoworkAgent, config: CliConfig, deps: CliDependencies) -> int:
    print(f"Standalone Cowork | {config.model} | {config.workspace}", file=deps.stdout)
    print("Commands: /models, /clear, /exit", file=deps.stdout)
    while True:
        prompt = deps.input_fn("cowork> ").strip()
        if not prompt:
            continue
        if prompt in {"/exit", "/quit"}:
            return 0
        if prompt == "/clear":
            agent.clear_history()
            print("History cleared.", file=deps.stdout)
            continue
        if prompt == "/models":
            for model_id in deps.model_lister(config):
                print(f"local:{model_id}", file=deps.stdout)
            continue
        print(agent.run(prompt), file=deps.stdout)


def _approval_adapter(config: CliConfig, deps: CliDependencies) -> Callable[[WriteProposal], bool]:
    if config.auto_approve:
        return lambda proposal: True

    def approve(proposal: WriteProposal) -> bool:
        print(f"\nProposed write: {proposal.relative_path}", file=deps.stderr)
        print(proposal.diff or "(content is unchanged)", file=deps.stderr)
        answer = deps.input_fn("Apply this write? [y/N] ").strip().casefold()
        return answer in {"y", "yes"}

    return approve


def _command_approval_adapter(
    config: CliConfig,
    deps: CliDependencies,
) -> Callable[[CommandProposal], bool]:
    if config.auto_approve:
        return lambda proposal: True

    def approve(proposal: CommandProposal) -> bool:
        rendered_command = subprocess.list2cmdline(list(proposal.argv))
        print(f"\nVerification preset: {proposal.name}", file=deps.stderr)
        print(f"Working directory: {proposal.cwd}", file=deps.stderr)
        print(f"Command: {rendered_command}", file=deps.stderr)
        print(f"Timeout: {proposal.timeout_seconds:g} seconds", file=deps.stderr)
        answer = deps.input_fn("Run this verification? [y/N] ").strip().casefold()
        return answer in {"y", "yes"}

    return approve


def _render_event(event_type: str, payload: dict, output: TextIO) -> None:
    if event_type == "tool_execution":
        print(f"[tool] {payload.get('tool_name', 'unknown')}", file=output)
