import tempfile
import unittest
from pathlib import Path

from model_performance import build_model_performance_profile, load_model_performance_profile, save_model_performance_profile


class ModelPerformanceTests(unittest.TestCase):
    def test_build_profile_summarizes_executed_cells_and_keeps_skips_separate(self):
        matrix = {
            "cells": [
                {"model": "model-a", "category": "coding", "status": "pass", "score": 4, "latency_ms": 1000, "hallucinated": False, "source_quality_ok": True},
                {"model": "model-a", "category": "coding", "status": "fail", "score": 1, "latency_ms": 2000, "hallucinated": True, "source_quality_ok": True},
                {"model": "model-b", "category": "coding", "status": "skipped", "skip_reason": "billing_required", "score": 0, "latency_ms": 0},
            ]
        }

        profile = build_model_performance_profile(matrix)

        coding_a = profile["models"]["model-a"]["categories"]["coding"]
        coding_b = profile["models"]["model-b"]["categories"]["coding"]
        self.assertEqual(coding_a["executed"], 2)
        self.assertEqual(coding_a["skipped"], 0)
        self.assertEqual(coding_a["pass_rate"], 0.5)
        self.assertGreater(coding_a["router_score"], 0)
        self.assertEqual(coding_b["executed"], 0)
        self.assertEqual(coding_b["skipped"], 1)
        self.assertEqual(coding_b["router_score"], 0)

    def test_save_and_load_profile_uses_stable_latest_file(self):
        matrix = {"cells": [{"model": "model-a", "category": "general", "status": "pass", "score": 3, "latency_ms": 100}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = save_model_performance_profile(matrix, output_dir=temp_dir)
            loaded = load_model_performance_profile(Path(temp_dir) / "model-performance-profile.json")

            self.assertEqual(Path(paths["profile"]).name, "model-performance-profile.json")
            self.assertIn("model-a", loaded["models"])


if __name__ == "__main__":
    unittest.main()
