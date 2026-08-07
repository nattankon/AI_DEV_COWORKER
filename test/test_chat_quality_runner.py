import unittest
import tempfile

import chat_quality_runner as cqr
from chat_quality_runner import _matrix_markdown, run_quality_eval_live


class ChatQualityRunnerTests(unittest.TestCase):
    def test_live_quality_runner_scores_model_category_matrix(self):
        calls = []

        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            calls.append((model, prompt, effort, web_settings))
            if model == "model-a":
                return {
                    "answer": "The official docs say this [web:1].\n\nSources:\n- https://example.com/docs",
                    "sources": [{"index": 1, "url": "https://example.com/docs", "source_type": "official-docs", "quality_score": 3}],
                    "evidence_corpus": "The official docs say this.",
                    "latency_ms": 1000,
                    "used_model": model,
                }
            return {
                "answer": "The official docs say this [web:1].\n\nSources:\n- https://example.com/docs",
                "sources": [{"index": 1, "url": "https://example.com/docs", "source_type": "official-docs", "quality_score": 3}],
                "evidence_corpus": "The official docs say this.",
                "latency_ms": 2000,
                "used_model": model,
            }

        matrix = run_quality_eval_live(
            models=["model-a", "model-b"],
            run_chat_once=fake_run_chat_once,
            categories=["web"],
            effort="High",
            web_settings={"webMode": "auto"},
        )

        self.assertEqual(matrix["summary"]["total_cells"], 2)
        self.assertEqual(len(matrix["cells"]), 2)
        self.assertTrue(all(cell["status"] == "pass" for cell in matrix["cells"]))
        self.assertEqual(matrix["models"]["model-a"]["pass_rate"], 1.0)
        self.assertEqual(matrix["models"]["model-b"]["avg_latency_ms"], 2000)
        self.assertEqual(calls[0][2], "High")
        self.assertEqual(calls[0][3], {"webMode": "auto"})

    def test_legacy_routes_sentinel_labels_and_parses_distinctly(self):
        self.assertEqual(cqr._parse_routes("legacy"), cqr.LEGACY_ROUTES)
        self.assertEqual(cqr._parse_routes("web,project"), ("web", "project"))
        self.assertIsNone(cqr._parse_routes(""))
        # Labels: unlabeled now means the GATED config default; legacy is explicit.
        # Pre-2026-07-03 archived reports labeled "default" are legacy runs.
        self.assertEqual(cqr._route_variant(None), "default:gated")
        self.assertEqual(cqr._route_variant(cqr.LEGACY_ROUTES), "legacy")
        self.assertEqual(cqr._route_variant(("web", "project")), "routes:web,project")

    def test_mcp_case_merges_its_own_web_settings_over_the_base(self):
        seen_settings = []

        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            del prompt, model, effort
            seen_settings.append(dict(web_settings))
            return {
                "answer": "Checked MCP diagnostics: no connector configured.",
                "sources": [],
                "evidence_corpus": "",
                "latency_ms": 700,
                "used_model": "model-a",
                "entered_tool_loop": True,
            }

        matrix = run_quality_eval_live(
            models=["model-a"],
            run_chat_once=fake_run_chat_once,
            categories=["mcp"],
            web_settings={"webMode": "auto", "searchProvider": "auto"},
        )

        self.assertEqual(seen_settings, [{"webMode": "auto", "searchProvider": "auto", "mcp": "on"}])
        self.assertEqual(matrix["cells"][0]["status"], "pass")

    def test_mcp_cell_fails_when_the_loop_never_ran(self):
        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            del prompt, model, effort, web_settings
            return {
                "answer": "The Roblox MCP connector is available with many tools.",
                "sources": [],
                "evidence_corpus": "",
                "latency_ms": 700,
                "used_model": "model-a",
                "entered_tool_loop": False,
            }

        matrix = run_quality_eval_live(
            models=["model-a"],
            run_chat_once=fake_run_chat_once,
            categories=["mcp"],
        )

        self.assertEqual(matrix["cells"][0]["status"], "fail")
        self.assertTrue(any("without entering the tool loop" in item for item in matrix["cells"][0]["findings"]))

    def test_live_quality_runner_flags_hallucinated_cells(self):
        def fake_run_chat_once(_prompt, *, model, effort, web_settings):
            del effort, web_settings
            return {
                "answer": f"{model} says the official price is 49.59 THB per litre [web:1].\n\nSources:\n- https://example.com/pricing",
                "sources": [{"index": 1, "url": "https://example.com/pricing", "source_type": "pricing", "quality_score": 4}],
                "evidence_corpus": "The official price is 39.50 THB per litre.",
                "latency_ms": 900,
                "used_model": model,
            }

        matrix = run_quality_eval_live(models=["model-a"], run_chat_once=fake_run_chat_once, categories=["web"])

        cell = matrix["cells"][0]
        self.assertEqual(cell["status"], "fail")
        self.assertTrue(cell["hallucinated"])
        self.assertEqual(matrix["models"]["model-a"]["hallucination_rate"], 1.0)

    def test_live_quality_runner_records_cell_error_and_continues(self):
        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            del prompt, effort, web_settings
            if model == "broken":
                raise RuntimeError("model unavailable")
            return {
                "answer": "This is a direct practical explanation of a local-first AI coworker app.",
                "sources": [],
                "evidence_corpus": "",
                "latency_ms": 500,
                "used_model": model,
            }

        matrix = run_quality_eval_live(models=["broken", "ok"], run_chat_once=fake_run_chat_once, categories=["general"])

        by_model = {cell["model"]: cell for cell in matrix["cells"]}
        self.assertEqual(by_model["broken"]["status"], "failed")
        self.assertIn("model unavailable", by_model["broken"]["findings"][0])
        self.assertEqual(by_model["ok"]["status"], "pass")
        self.assertEqual(matrix["summary"]["failed_cells"], 1)

    def test_live_quality_runner_filters_categories(self):
        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            del prompt, model, effort, web_settings
            return {
                "answer": "คำตอบนี้เป็นภาษาไทยและมีรายละเอียดเพียงพอสำหรับการทดสอบ",
                "sources": [],
                "evidence_corpus": "",
                "latency_ms": 700,
                "used_model": "model-a",
            }

        matrix = run_quality_eval_live(models=["model-a"], run_chat_once=fake_run_chat_once, categories=["thai"])

        self.assertEqual([cell["category"] for cell in matrix["cells"]], ["thai"])
        self.assertEqual(matrix["categories"]["thai"]["total"], 1)

    def test_live_quality_runner_retries_retryable_provider_errors(self):
        calls = {"count": 0}

        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            del prompt, model, effort, web_settings
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("Error code: 429 - temporarily overloaded")
            return {
                "answer": "The official docs say this [web:1].\n\nSources:\n- https://example.com/docs",
                "sources": [{"index": 1, "url": "https://example.com/docs", "source_type": "official-docs", "quality_score": 3}],
                "evidence_corpus": "The official docs say this.",
                "latency_ms": 600,
                "used_model": "model-a",
            }

        matrix = run_quality_eval_live(
            models=["model-a"],
            run_chat_once=fake_run_chat_once,
            categories=["web"],
            retry_attempts=1,
            retry_backoff_seconds=0,
        )

        cell = matrix["cells"][0]
        self.assertEqual(calls["count"], 2)
        self.assertEqual(cell["status"], "pass")
        self.assertEqual(cell["attempts"], 2)

    def test_live_quality_runner_does_not_retry_non_retryable_errors(self):
        calls = {"count": 0}

        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            del prompt, model, effort, web_settings
            calls["count"] += 1
            raise RuntimeError("invalid model id")

        matrix = run_quality_eval_live(
            models=["broken"],
            run_chat_once=fake_run_chat_once,
            categories=["web"],
            retry_attempts=2,
            retry_backoff_seconds=0,
        )

        cell = matrix["cells"][0]
        self.assertEqual(calls["count"], 1)
        self.assertEqual(cell["status"], "failed")
        self.assertEqual(cell["attempts"], 1)

    def test_live_quality_runner_skips_billing_or_credit_required_models(self):
        def fake_run_chat_once(prompt, *, model, effort, web_settings):
            del prompt, model, effort, web_settings
            raise RuntimeError("Error code: 402 - insufficient credit or billing required")

        matrix = run_quality_eval_live(
            models=["paid-model"],
            run_chat_once=fake_run_chat_once,
            categories=["general"],
        )

        cell = matrix["cells"][0]
        self.assertEqual(cell["status"], "skipped")
        self.assertEqual(cell["skip_reason"], "billing_required")
        self.assertEqual(matrix["summary"]["skipped_cells"], 1)
        self.assertEqual(matrix["summary"]["failed_cells"], 0)

    def test_live_quality_runner_plumbs_route_variant_and_diagnostics(self):
        calls = []

        def fake_run_chat_once(prompt, *, model, effort, web_settings, tool_research_routes=None):
            calls.append((prompt, model, effort, web_settings, tool_research_routes))
            return {
                "answer": "This is a direct practical explanation of a local-first AI coworker app.",
                "sources": [],
                "evidence_corpus": "",
                "latency_ms": 500,
                "used_model": model,
                "entered_tool_loop": True,
                "research_iterations": 2,
                "research_forced": False,
                "answer_path_ms": 432,
            }

        matrix = run_quality_eval_live(
            models=["model-a"],
            run_chat_once=fake_run_chat_once,
            categories=["general"],
            tool_research_routes=("web", "project"),
        )

        cell = matrix["cells"][0]
        self.assertEqual(calls[0][4], ("web", "project"))
        self.assertEqual(cell["variant"], "routes:web,project")
        self.assertTrue(cell["entered_tool_loop"])
        self.assertEqual(cell["research_iterations"], 2)
        self.assertFalse(cell["research_forced"])
        self.assertEqual(cell["answer_path_ms"], 432)
        self.assertEqual(matrix["summary"]["variant"], "routes:web,project")
        markdown = _matrix_markdown(matrix)
        self.assertIn("| Model | Category | Status | Score | Attempts | Latency ms | Loop | Iters | Path ms |", markdown)
        self.assertIn("routes:web,project", markdown)

    def test_live_quality_runner_default_variant_labels_as_gated(self):
        calls = []

        def fake_run_chat_once(prompt, *, model, effort, web_settings, tool_research_routes=None):
            del prompt, effort, web_settings
            calls.append(tool_research_routes)
            return {
                "answer": "This is a direct practical explanation of a local-first AI coworker app.",
                "sources": [],
                "evidence_corpus": "",
                "latency_ms": 500,
                "used_model": model,
            }

        matrix = run_quality_eval_live(models=["model-a"], run_chat_once=fake_run_chat_once, categories=["general"])

        # No routes override -> run_chat_once receives None -> the sidecar's gated
        # config default applies. The label must say "gated", not the bare "default"
        # that archived pre-2026-07-03 (legacy) reports carry.
        self.assertEqual(calls, [None])
        self.assertEqual(matrix["cells"][0]["variant"], "default:gated")
        self.assertEqual(matrix["summary"]["variant"], "default:gated")

    def test_live_quality_runner_plumbs_search_provider_into_cell_and_markdown(self):
        def fake_run_chat_once(prompt, *, model, effort, web_settings, tool_research_routes=None):
            del prompt, effort, web_settings, tool_research_routes
            return {
                "answer": "This is a direct practical explanation of a local-first AI coworker app.",
                "sources": [],
                "evidence_corpus": "",
                "latency_ms": 500,
                "used_model": model,
                "search_provider": "brave_api",
            }

        matrix = run_quality_eval_live(models=["model-a"], run_chat_once=fake_run_chat_once, categories=["general"])

        cell = matrix["cells"][0]
        self.assertEqual(cell["search_provider"], "brave_api")
        markdown = _matrix_markdown(matrix)
        self.assertIn("Provider", markdown)
        self.assertIn("brave_api", markdown)

    def test_run_chat_once_passes_route_config_and_returns_diagnostics(self):
        seen_routes = []

        class FakeSidecar:
            def __init__(self, dependencies):
                seen_routes.append(dependencies.chat_config.tool_research_routes)

            def _run_plain_chat(self, *args, **kwargs):
                assert kwargs["return_diagnostics"]
                return (
                    "answer",
                    "used-model",
                    [{"index": 1, "url": "https://example.test"}],
                    {
                        "evidence_corpus": "evidence",
                        "entered_tool_loop": True,
                        "research_iterations": 3,
                        "research_forced": True,
                        "answer_path_ms": 789,
                        "search_provider": "brave_api",
                    },
                )

        original_sidecar = cqr.IpcSidecar
        cqr.IpcSidecar = FakeSidecar
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                payload = cqr.run_chat_once(
                    "hello",
                    model="model-a",
                    app_root=temp_dir,
                    workspace=temp_dir,
                    tool_research_routes=("web", "project"),
                )
        finally:
            cqr.IpcSidecar = original_sidecar

        self.assertEqual(seen_routes, [("web", "project")])
        self.assertEqual(payload["evidence_corpus"], "evidence")
        self.assertTrue(payload["entered_tool_loop"])
        self.assertEqual(payload["research_iterations"], 3)
        self.assertTrue(payload["research_forced"])
        self.assertEqual(payload["answer_path_ms"], 789)
        self.assertEqual(payload["search_provider"], "brave_api")


if __name__ == "__main__":
    unittest.main()
