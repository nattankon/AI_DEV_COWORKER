from __future__ import annotations

from typing import Any


def build_approval_payload(approval_kind: str, question: str, proposal: dict[str, Any]) -> dict[str, Any]:
    kind = str(approval_kind or "").strip()
    clean_proposal = proposal if isinstance(proposal, dict) else {}
    risk_level = _risk_level(kind, clean_proposal)
    subject = _subject(kind, clean_proposal)
    details = _details(kind, clean_proposal)
    risk_summary = _risk_summary(risk_level, kind, clean_proposal)
    payload = dict(clean_proposal)
    payload.update(
        {
            "risk_level": risk_level,
            "risk_summary": risk_summary,
            "subject": subject,
            "details": details,
            "full_payload": dict(clean_proposal),
            "default_decision": "deny",
            "allow_scopes": ["once"],
            "question": str(question or ""),
        }
    )
    return payload


def _risk_level(approval_kind: str, proposal: dict[str, Any]) -> str:
    if approval_kind == "chat_run_python":
        return "code"
    if approval_kind == "mcp_tool_call":
        tool = str(proposal.get("tool") or "").casefold()
        if any(marker in tool for marker in ("delete", "remove", "destroy", "drop", "wipe")):
            return "destructive"
        return "write"
    if approval_kind in {"write_file", "run_verification", "restore_backup"}:
        return "write"
    return "write"


def _subject(approval_kind: str, proposal: dict[str, Any]) -> str:
    if approval_kind == "chat_run_python":
        return "Python code execution"
    if approval_kind == "mcp_tool_call":
        server = str(proposal.get("server") or "mcp")
        tool = str(proposal.get("tool") or "tool")
        return f"{server}/{tool}"
    return str(proposal.get("relative_path") or proposal.get("name") or proposal.get("tool") or "Pending action")


def _details(approval_kind: str, proposal: dict[str, Any]) -> dict[str, Any]:
    if approval_kind == "chat_run_python":
        return {
            "tool": "run_python",
            "sandbox_level": proposal.get("sandbox_level"),
            "network_isolation": proposal.get("network_isolation"),
            "timeout_seconds": proposal.get("timeout_seconds"),
            "code_preview": str(proposal.get("code") or ""),
        }
    if approval_kind == "mcp_tool_call":
        return {
            "server": str(proposal.get("server") or ""),
            "tool": str(proposal.get("tool") or ""),
            "arguments": proposal.get("arguments") if isinstance(proposal.get("arguments"), dict) else {},
        }
    return dict(proposal)


def _risk_summary(risk_level: str, approval_kind: str, proposal: dict[str, Any]) -> str:
    if approval_kind == "chat_run_python":
        sandbox = str(proposal.get("sandbox_level") or "experimental sandbox")
        network = str(proposal.get("network_isolation") or "best-effort network check")
        return (
            f"Runs code in {sandbox}. Network filtering is {network}; this is not a production "
            "filesystem/network isolation boundary."
        )
    if approval_kind == "mcp_tool_call":
        if risk_level == "destructive":
            return "This MCP tool may make destructive changes in an external system."
        return "This MCP tool may write to or act in an external system."
    if approval_kind == "run_verification":
        return "Runs an allowlisted local verification command."
    if approval_kind == "write_file":
        return "Writes a local workspace file after approval."
    return "This action may change local or external state."
