from __future__ import annotations

import json
import locale
import sys
from pathlib import Path
from typing import Any


MOJIBAKE_MARKERS = ("�", "喔", "Ã", "Â", "à¸", "à¹")


def analyze_text_layers(layers: dict[str, str], *, max_findings: int = 12) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for layer, text in layers.items():
        content = str(text or "")
        marker = next((item for item in MOJIBAKE_MARKERS if item in content), "")
        if not marker:
            continue
        findings.append(
            {
                "layer": str(layer),
                "marker": marker,
                "sample": _compact_sample(content, marker),
            }
        )
        if len(findings) >= max_findings:
            break
    return {
        "status": "warning" if findings else "ok",
        "findings": findings,
    }


def build_mojibake_diagnostics(root: str | Path, *, max_files: int = 8, max_findings: int = 12) -> dict[str, Any]:
    root_path = Path(root)
    session_dir = root_path / "work_logs" / "sessions"
    files = sorted(session_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)[:max_files]
    layers: dict[str, str] = {}
    for file_path in files:
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        except OSError:
            continue
        for index, line in enumerate(lines):
            layers[f"{file_path.name}:{index}"] = line
    analysis = analyze_text_layers(layers, max_findings=max_findings)
    return {
        **analysis,
        "checked_files": [file_path.name for file_path in files],
        "runtime": {
            "filesystem_encoding": sys.getfilesystemencoding(),
            "default_encoding": sys.getdefaultencoding(),
            "preferred_encoding": locale.getencoding(),
            "stdout_encoding": getattr(sys.stdout, "encoding", None) or "",
        },
    }


def safe_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _compact_sample(text: str, marker: str) -> str:
    index = text.find(marker)
    if index < 0:
        return text[:160]
    start = max(0, index - 55)
    end = min(len(text), index + 105)
    return text[start:end].replace("\r", " ").replace("\n", " ")
