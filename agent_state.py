from __future__ import annotations

import json


class AgentRunState:
    def __init__(self):
        self.current_stage = "inspect"
        self.stages: list[str] = []
        self._writes_performed = False
        self._verification_statuses: list[str] = []
        self._verification_runs: list[dict] = []

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "AgentRunState":
        if not isinstance(snapshot, dict):
            raise ValueError("Invalid agent state snapshot: expected object.")
        current_stage = snapshot.get("current_stage")
        stages = snapshot.get("stages")
        writes_performed = snapshot.get("writes_performed")
        verification_statuses = snapshot.get("verification_statuses")
        if (
            not isinstance(current_stage, str)
            or not current_stage.strip()
            or not isinstance(stages, list)
            or not all(isinstance(stage, str) and stage.strip() for stage in stages)
            or not isinstance(writes_performed, bool)
            or not isinstance(verification_statuses, list)
            or not all(isinstance(status, str) for status in verification_statuses)
        ):
            raise ValueError("Invalid agent state snapshot.")
        state = cls()
        state.current_stage = current_stage.strip()
        state.stages = [stage.strip() for stage in stages]
        state._writes_performed = writes_performed
        state._verification_statuses = list(verification_statuses)
        state._verification_runs = _coerce_verification_runs(snapshot.get("verification_runs"))
        return state

    def record_stage(self, stage: str) -> dict | None:
        normalized_stage = str(stage or "").strip()
        if not normalized_stage:
            raise ValueError("Stage cannot be empty.")
        if self.current_stage == normalized_stage and self.stages and self.stages[-1] == normalized_stage:
            return None
        self.current_stage = normalized_stage
        self.stages.append(normalized_stage)
        return {"stage": normalized_stage}

    def observe_tool_result(self, tool_name: str, result: str) -> None:
        payload = _decode_result(result)
        status = str(payload.get("status") or "")
        if tool_name in {"write_file", "edit_file"} and status == "written":
            self._writes_performed = True
        elif tool_name == "restore_backup" and status == "restored":
            self._writes_performed = True
        elif tool_name == "run_verification":
            self._verification_statuses.append(status)
            self._verification_runs.append(
                {"name": str(payload.get("name") or ""), "status": status}
            )

    def requires_verification_before_report(self) -> bool:
        return self._writes_performed and not self._verification_passed()

    def completion_evidence(self) -> dict:
        return {
            "writes_performed": self._writes_performed,
            "verification_observed": bool(self._verification_statuses),
            "verification_passed": self._verification_passed(),
            "verification_statuses": list(self._verification_statuses),
            "verification_runs": [dict(run) for run in self._verification_runs],
        }

    def to_snapshot(self) -> dict:
        return {
            "current_stage": self.current_stage,
            "stages": list(self.stages),
            **self.completion_evidence(),
        }

    def _verification_passed(self) -> bool:
        return any(status == "passed" for status in self._verification_statuses)


def _coerce_verification_runs(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    runs: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        runs.append(
            {
                "name": str(item.get("name") or ""),
                "status": str(item.get("status") or ""),
            }
        )
    return runs


def _decode_result(result: str) -> dict:
    try:
        payload = json.loads(result)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}
