import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_web_smoke import (
    HARD_SMOKE_URLS,
    build_source_smoke_profile,
    run_web_smoke,
    save_web_smoke_report,
    _write_json_stdout,
)


class ChatWebSmokeTests(unittest.TestCase):
    # Pin the search key OUT of the environment so the "not_checked" assertion is
    # env-independent (a real COWORK_SEARCH_API_KEY on the dev machine would
    # otherwise flip this to "brave_api").
    @patch.dict(os.environ, {"COWORK_SEARCH_API_KEY": ""})
    def test_run_web_smoke_reports_layer_shape_with_fake_fetcher(self):
        calls = []

        def fake_fetcher(url, timeout):
            del timeout
            calls.append(url)
            if "apioilprice2" in url:
                return '[{"OilDateNow":"2026-06-26","OilList":"[{\\"OilName\\":\\"Diesel\\",\\"PriceToday\\":31.94,\\"PriceTomorrow\\":31.94,\\"PriceDifTomorrow\\":0}]"}]'
            if "static.example" in url:
                return "<html><table><tr><th>Name</th><th>Value</th></tr><tr><td>Alpha</td><td>42</td></tr></table></html>"
            if "blocked.example" in url:
                return "<html>captcha page verify you are human</html>"
            return "<html><body></body></html>"

        report = run_web_smoke(
            [
                "https://oil-price.bangchak.co.th/BcpOilPrice2/th",
                "https://static.example/table",
                "https://blocked.example/captcha",
                "https://empty.example/page",
            ],
            fetcher=fake_fetcher,
        )

        rows = {item["url"]: item for item in report["results"]}
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["search_provider"], "not_checked")
        self.assertEqual(rows["https://oil-price.bangchak.co.th/BcpOilPrice2/th"]["layer_used"], "adapter")
        self.assertGreater(rows["https://oil-price.bangchak.co.th/BcpOilPrice2/th"]["evidence_len"], 0)
        self.assertTrue(rows["https://static.example/table"]["has_tables"])
        self.assertEqual(rows["https://static.example/table"]["layer_used"], "html")
        self.assertEqual(rows["https://blocked.example/captcha"]["layer_used"], "blocked")
        self.assertEqual(rows["https://empty.example/page"]["layer_used"], "empty")
        self.assertTrue(any("apioilprice2" in call for call in calls))

    def test_source_smoke_profile_accumulates_domain_quality(self):
        first = {
            "generated_at": "2026-07-02T01:00:00+0000",
            "results": [
                {
                    "url": "https://good.example/table",
                    "layer_used": "html",
                    "evidence_len": 120,
                    "has_tables": True,
                    "source_type": "fetched-page",
                    "quality_score": 4,
                },
                {
                    "url": "https://blocked.example/captcha",
                    "layer_used": "blocked",
                    "evidence_len": 0,
                    "has_tables": False,
                    "source_type": "fetch-blocked",
                    "quality_score": 0,
                },
            ],
        }
        second = {
            "generated_at": "2026-07-02T02:00:00+0000",
            "results": [
                {
                    "url": "https://good.example/another",
                    "layer_used": "adapter",
                    "evidence_len": 300,
                    "has_tables": True,
                    "source_type": "source-adapter",
                    "quality_score": 5,
                }
            ],
        }

        profile = build_source_smoke_profile(first)
        profile = build_source_smoke_profile(second, existing=profile)

        good = profile["domains"]["good.example"]
        blocked = profile["domains"]["blocked.example"]
        self.assertEqual(good["runs"], 2)
        self.assertEqual(good["successes"], 2)
        self.assertEqual(good["best_layer"], "adapter")
        self.assertEqual(good["avg_quality_score"], 4.5)
        self.assertEqual(good["success_rate"], 1.0)
        self.assertEqual(blocked["runs"], 1)
        self.assertEqual(blocked["blocked"], 1)
        self.assertEqual(blocked["success_rate"], 0.0)

    def test_save_web_smoke_report_updates_stable_source_profile(self):
        report = {
            "status": "ok",
            "generated_at": "2026-07-02T01:00:00+0000",
            "search_provider": "not_checked",
            "playwright_enabled": False,
            "results": [
                {
                    "url": "https://source.example/page",
                    "layer_used": "html",
                    "evidence_len": 80,
                    "has_tables": False,
                    "source_type": "fetched-page",
                    "quality_score": 3,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = save_web_smoke_report(report, output_dir=temp_dir)
            profile_path = Path(paths["source_profile"])
            self.assertTrue(profile_path.exists())
            self.assertEqual(profile_path.name, "chat-web-source-profile.json")
            self.assertIn('"source.example"', profile_path.read_text(encoding="utf-8"))

    def test_curated_hard_urls_do_not_contain_mojibake_slug(self):
        joined = "\n".join(HARD_SMOKE_URLS)
        self.assertNotIn("喔", joined)
        self.assertIn("ราคาขายปลีกน้ำมัน", joined)

    def test_write_json_stdout_uses_utf8_buffer_for_thai_text(self):
        class FakeStdout:
            def __init__(self):
                self.buffer = self
                self.payload = b""

            def write(self, value):
                self.payload += value

            def flush(self):
                pass

        fake = FakeStdout()
        with patch("chat_web_smoke.sys.stdout", fake):
            _write_json_stdout({"text": "ราคาขายปลีกน้ำมัน"})

        self.assertIn("ราคาขายปลีกน้ำมัน", fake.payload.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
