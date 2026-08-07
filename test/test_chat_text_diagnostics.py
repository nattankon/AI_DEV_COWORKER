import json
import tempfile
import unittest
from pathlib import Path

from chat_text_diagnostics import analyze_text_layers, build_mojibake_diagnostics


class ChatTextDiagnosticsTests(unittest.TestCase):
    def test_analyze_text_layers_flags_mojibake_marker_by_layer(self):
        result = analyze_text_layers({"model_raw": "สวัสดี", "frontend": "喔曕腑喔氞笭"})

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["findings"][0]["layer"], "frontend")
        self.assertEqual(result["findings"][0]["marker"], "喔")

    def test_build_mojibake_diagnostics_scans_recent_session_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir) / "work_logs" / "sessions"
            session_dir.mkdir(parents=True)
            (session_dir / "latest.jsonl").write_text(
                json.dumps({"event": "cowork_log", "text": "喔曕腑喔氞笭"}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = build_mojibake_diagnostics(temp_dir)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["checked_files"], ["latest.jsonl"])
        self.assertIn("runtime", result)


if __name__ == "__main__":
    unittest.main()
