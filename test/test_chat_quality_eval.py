import unittest

from chat_quality_eval import evaluate_case_result, quality_eval_cases, run_quality_eval_snapshot


class ChatQualityEvalTests(unittest.TestCase):
    def test_quality_eval_cases_cover_core_chat_capabilities(self):
        cases = quality_eval_cases()
        categories = {case["category"] for case in cases}

        self.assertTrue({"general", "web", "thai", "attachment", "coding", "memory", "mcp"} <= categories)
        for case in cases:
            self.assertIn("prompt", case)
            self.assertIn("checks", case)
            self.assertGreater(len(case["checks"]), 0)

    def test_evaluate_case_result_scores_sources_language_and_latency(self):
        web_case = next(case for case in quality_eval_cases() if case["category"] == "web")

        result = evaluate_case_result(
            web_case,
            answer="The current docs say this [web:1].\n\nSources:\n- https://example.com/docs",
            sources=[{"url": "https://example.com/docs", "source_type": "official-docs", "quality_score": 3}],
            latency_ms=1200,
        )

        self.assertEqual(result["category"], "web")
        self.assertGreaterEqual(result["score"], 3)
        self.assertEqual(result["status"], "pass")

    def test_evaluate_case_result_flags_missing_web_sources(self):
        web_case = next(case for case in quality_eval_cases() if case["category"] == "web")

        result = evaluate_case_result(web_case, answer="The latest information is definitely available.", sources=[])

        self.assertEqual(result["status"], "fail")
        self.assertIn("missing sources", result["findings"])

    def test_evaluate_case_result_flags_indirect_general_non_answer(self):
        general_case = next(case for case in quality_eval_cases() if case["category"] == "general")

        result = evaluate_case_result(
            general_case,
            answer="I could not find specific information about this. Please provide more context.",
            evidence="",
        )

        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["direct"])
        self.assertTrue(any("not direct" in finding for finding in result["findings"]))

    def test_evaluate_case_result_flags_search_failure_style_general_non_answer(self):
        general_case = next(case for case in quality_eval_cases() if case["category"] == "general")

        result = evaluate_case_result(
            general_case,
            answer='Based on my search attempts, I was unable to find specific current information about "local-first AI coworker apps". Therefore, I cannot provide a practical explanation.',
            evidence="",
        )

        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["direct"])
        self.assertTrue(any("not direct" in finding for finding in result["findings"]))

    def test_evaluate_case_result_flags_vague_thai_non_answer(self):
        thai_case = next(case for case in quality_eval_cases() if case["category"] == "thai")

        result = evaluate_case_result(
            thai_case,
            answer="\u0e01\u0e23\u0e38\u0e13\u0e32\u0e23\u0e30\u0e1a\u0e38\u0e2b\u0e31\u0e27\u0e02\u0e49\u0e2d\u0e2b\u0e23\u0e37\u0e2d\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e40\u0e09\u0e1e\u0e32\u0e30\u0e17\u0e35\u0e48\u0e04\u0e38\u0e13\u0e15\u0e49\u0e2d\u0e07\u0e01\u0e32\u0e23 \u0e40\u0e0a\u0e48\u0e19 \u0e02\u0e48\u0e32\u0e27\u0e40\u0e28\u0e23\u0e29\u0e10\u0e01\u0e34\u0e08 \u0e02\u0e48\u0e32\u0e27\u0e40\u0e17\u0e04\u0e42\u0e19\u0e42\u0e25\u0e22\u0e35",
            evidence="",
        )

        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["direct"])
        self.assertTrue(any("not direct" in finding for finding in result["findings"]))

    def test_evaluate_case_result_flags_explicit_low_quality_web_sources(self):
        web_case = next(case for case in quality_eval_cases() if case["category"] == "web")

        result = evaluate_case_result(
            web_case,
            answer="The current docs say this [web:1].\n\nSources:\n- https://random-blog.example/post",
            sources=[{"index": 1, "url": "https://random-blog.example/post", "source_type": "search-result", "quality_score": 0}],
            evidence="The current docs say this.",
            latency_ms=1200,
        )

        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["source_quality_ok"])
        self.assertTrue(any("source quality" in finding for finding in result["findings"]))

    def test_evaluate_case_result_accepts_high_quality_web_sources(self):
        web_case = next(case for case in quality_eval_cases() if case["category"] == "web")

        result = evaluate_case_result(
            web_case,
            answer="The current docs say this [web:1].\n\nSources:\n- https://example.com/docs",
            sources=[{"index": 1, "url": "https://example.com/docs", "source_type": "official-docs", "quality_score": 3}],
            evidence="The current docs say this.",
            latency_ms=1200,
        )

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["source_quality_ok"])

    def test_evaluate_case_result_accepts_a_fetched_page_the_model_grounded_on(self):
        # A real page the model opened and cited (not a mere snippet) is a quality
        # source even when its heuristic quality_score is low. Mirrors the live case
        # where a fetched python.org page was wrongly scored low quality.
        web_case = next(case for case in quality_eval_cases() if case["category"] == "web")

        result = evaluate_case_result(
            web_case,
            answer="Python 3.14.7 is the latest stable release [web:1].\n\nSources:\n- https://www.python.org/downloads/",
            sources=[{"index": 1, "url": "https://www.python.org/downloads/", "source_type": "fetched-page", "quality_score": 1}],
            evidence="Download Python 3.14.7. Latest Python 3 release - Python 3.14.7.",
            latency_ms=1200,
        )

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["source_quality_ok"])

    def test_evaluate_case_result_flags_ungrounded_values_when_evidence_exists(self):
        web_case = next(case for case in quality_eval_cases() if case["category"] == "web")

        result = evaluate_case_result(
            web_case,
            answer="The official price is 49.59 THB per litre [web:1].\n\nSources:\n- https://example.com/pricing",
            sources=[{"index": 1, "url": "https://example.com/pricing", "source_type": "pricing", "quality_score": 4}],
            evidence="The official price is 39.50 THB per litre.",
        )

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any(finding.startswith("hallucinated:") for finding in result["findings"]))
        self.assertTrue(result["hallucinated"])

    def test_evaluate_case_result_allows_grounded_values_in_evidence(self):
        web_case = next(case for case in quality_eval_cases() if case["category"] == "web")

        result = evaluate_case_result(
            web_case,
            answer="The official price is 39.50 THB per litre [web:1].\n\nSources:\n- https://example.com/pricing",
            sources=[{"index": 1, "url": "https://example.com/pricing", "source_type": "pricing", "quality_score": 4}],
            evidence="The official price is 39.50 THB per litre.",
        )

        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["hallucinated"])

    def test_general_answer_with_empty_evidence_is_not_grounding_flagged(self):
        general_case = next(case for case in quality_eval_cases() if case["category"] == "general")

        result = evaluate_case_result(
            general_case,
            answer="Python 3.12 was released in 2023 and this answer is general model knowledge.",
            evidence="",
        )

        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["hallucinated"])

    def test_mcp_case_fails_hard_when_answered_without_the_tool_loop(self):
        mcp_case = next(case for case in quality_eval_cases() if case["category"] == "mcp")

        skipped_loop = evaluate_case_result(
            mcp_case,
            answer="The Roblox MCP connector is available with 85 tools ready to use.",
            evidence="",
            latency_ms=900,
            entered_tool_loop=False,
        )
        used_loop = evaluate_case_result(
            mcp_case,
            answer="Checked via MCP diagnostics: no connector matched. Ask the user to enable one.",
            evidence="",
            latency_ms=900,
            entered_tool_loop=True,
        )
        unknown_loop = evaluate_case_result(
            mcp_case,
            answer="Checked via MCP diagnostics: no connector matched. Ask the user to enable one.",
            evidence="",
            latency_ms=900,
        )

        self.assertEqual(skipped_loop["status"], "fail")
        self.assertTrue(any("without entering the tool loop" in item for item in skipped_loop["findings"]))
        self.assertEqual(used_loop["status"], "pass")
        # Older callers that do not report loop state must not be penalized.
        self.assertEqual(unknown_loop["status"], "pass")

    def test_mcp_case_carries_its_own_web_settings_for_the_runner(self):
        mcp_case = next(case for case in quality_eval_cases() if case["category"] == "mcp")

        self.assertEqual(mcp_case.get("web_settings"), {"mcp": "on"})
        self.assertTrue(mcp_case.get("requires_tool_loop"))

    def test_run_quality_eval_snapshot_scores_supplied_fixture_answers(self):
        snapshot = run_quality_eval_snapshot(
            [
                {
                    "category": "web",
                    "answer": "The official docs say this [web:1].\n\nSources:\n- https://example.com/docs",
                    "sources": [{"url": "https://example.com/docs", "source_type": "official-docs", "quality_score": 3}],
                    "evidence": "The official docs say this.",
                    "latency_ms": 500,
                },
                {
                    "category": "thai",
                    "answer": "คำตอบนี้เป็นภาษาไทยและสรุปจากข้อมูลที่ให้มา",
                    "latency_ms": 500,
                },
            ]
        )

        self.assertEqual(snapshot["count"], len(quality_eval_cases()))
        self.assertGreaterEqual(snapshot["passed"], 2)
        self.assertIn("results", snapshot)

    def test_run_quality_eval_snapshot_threads_evidence_into_grounding_metric(self):
        snapshot = run_quality_eval_snapshot(
            [
                {
                    "category": "web",
                    "answer": "The official price is 49.59 THB per litre [web:1].\n\nSources:\n- https://example.com/pricing",
                    "sources": [{"index": 1, "url": "https://example.com/pricing", "source_type": "pricing", "quality_score": 4}],
                    "evidence": "The official price is 39.50 THB per litre.",
                }
            ]
        )

        web_result = next(item for item in snapshot["results"] if item["category"] == "web")
        self.assertEqual(web_result["status"], "fail")
        self.assertTrue(web_result["hallucinated"])


if __name__ == "__main__":
    unittest.main()
