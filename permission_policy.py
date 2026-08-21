from __future__ import annotations

from typing import Any


PERMISSION_MODES = frozenset({"manual", "trusted", "full"})
KNOWN_APPROVAL_KINDS = frozenset(
    {
        "write_file",
        "run_verification",
        "restore_backup",
        "chat_run_python",
        "mcp_tool_call",
    }
)


def normalize_permission_mode(value: Any) -> str:
    """Return a supported permission mode, defaulting unknown values to fail-closed."""
    mode = str(value or "").strip().casefold()
    return mode if mode in PERMISSION_MODES else "manual"


def should_auto_approve(mode: Any, approval_kind: Any, approval_payload: dict[str, Any] | None) -> bool:
    """Decide whether a known side effect can bypass the interactive approval prompt.

    This policy only changes prompt frequency. Workspace containment and Secret Guard
    remain enforced by WorkspaceTools in every mode.
    """
    normalized_mode = normalize_permission_mode(mode)
    kind = str(approval_kind or "").strip()
    if kind not in KNOWN_APPROVAL_KINDS or normalized_mode == "manual":
        return False
    if normalized_mode == "full":
        return True
    payload = approval_payload if isinstance(approval_payload, dict) else {}
    routine_local_action = kind in {"write_file", "run_verification"}
    return routine_local_action and str(payload.get("risk_level") or "").strip().casefold() == "write"
