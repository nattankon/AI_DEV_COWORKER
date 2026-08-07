import json
import unittest

from chat_web_connector import WebSearchResponse, WebSearchResult
from chat_web_tools import WebResearchTools


class FakeConnector:
    def __init__(self):
        self.search_calls = []
        self.fetch_calls = []
        self.pages = {}
        self._timeout_seconds = 3.0
        self.search_error = ""

    def search(self, query, max_results):
        self.search_calls.append((query, max_results))
        return WebSearchResponse(
            query=query,
            error=self.search_error,
            results=[
                WebSearchResult(title="Alpha", url="https://example.test/a", snippet="A snippet"),
                WebSearchResult(title="Beta", url="https://example.test/b", snippet="B snippet", source_type="trusted-hint"),
            ] if not self.search_error else [],
        )

    def _fetcher(self, url, timeout):
        del timeout
        self.fetch_calls.append(url)
        return self.pages[url]


class FakePlaywrightFetcher:
    def __init__(self, html=None):
        self.html = html
        self.calls = []

    def fetch(self, url, *, timeout=8.0):
        self.calls.append((url, timeout))
        if isinstance(self.html, Exception):
            raise self.html
        return self.html


class WebResearchToolsTests(unittest.TestCase):
    def test_schemas_expose_only_strict_web_tools(self):
        tools = WebResearchTools(FakeConnector())

        schemas = tools.schemas

        names = [schema["function"]["name"] for schema in schemas]
        self.assertEqual(names, ["web_search", "web_fetch"])
        self.assertNotIn("read_file", names)
        self.assertNotIn("git_status", names)
        self.assertTrue(all(schema["function"]["strict"] for schema in schemas))
        self.assertTrue(all(schema["function"]["parameters"]["additionalProperties"] is False for schema in schemas))
        for schema in schemas:
            parameters = schema["function"]["parameters"]
            self.assertEqual(set(parameters["required"]), set(parameters["properties"]))
        web_search = schemas[0]["function"]["parameters"]
        self.assertEqual(web_search["properties"]["max_results"]["type"], ["integer", "null"])

    def test_web_search_registers_stable_indices_and_expected_shape(self):
        connector = FakeConnector()
        tools = WebResearchTools(connector)

        first = json.loads(tools.dispatch("web_search", {"query": "latest docs", "max_results": 99}))
        second = json.loads(tools.dispatch("web_search", {"query": "latest docs", "max_results": 2}))

        self.assertEqual(connector.search_calls[0], ("latest docs", 8))
        self.assertEqual(connector.fetch_calls, [])
        self.assertEqual(first["status"], "ok")
        self.assertEqual(
            first["results"],
            [
                {
                    "index": 1,
                    "title": "Alpha",
                    "url": "https://example.test/a",
                    "snippet": "A snippet",
                    "source_type": "search-result",
                },
                {
                    "index": 2,
                    "title": "Beta",
                    "url": "https://example.test/b",
                    "snippet": "B snippet",
                    "source_type": "trusted-hint",
                },
            ],
        )
        self.assertEqual([item["index"] for item in second["results"]], [1, 2])
        self.assertEqual(
            tools.sources(),
            [
                {"index": 1, "url": "https://example.test/a", "title": "Alpha", "source_type": "search-result"},
                {"index": 2, "url": "https://example.test/b", "title": "Beta", "source_type": "trusted-hint"},
            ],
        )

    def test_web_fetch_blocked_page_returns_blocked_without_raise(self):
        connector = FakeConnector()
        connector.pages["https://example.test/blocked"] = """
        <html><body><title>Blocked</title><p>Radware Captcha Page</p></body></html>
        """
        tools = WebResearchTools(connector)

        payload = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/blocked"}))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["index"], 1)
        self.assertEqual(payload["source_type"], "fetch-blocked")
        self.assertTrue(payload["blocked"])
        self.assertEqual(payload["evidence"], "")
        self.assertEqual(payload["tables"], [])

    def test_dispatch_error_paths_return_status_error(self):
        connector = FakeConnector()
        connector.search_error = "network unavailable"
        tools = WebResearchTools(connector)

        empty_query = json.loads(tools.dispatch("web_search", {"query": ""}))
        search_error = json.loads(tools.dispatch("web_search", {"query": "anything"}))
        empty_url = json.loads(tools.dispatch("web_fetch", {"url": ""}))
        fetch_error = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/missing"}))
        unknown_tool = json.loads(tools.dispatch("read_file", {"path": "PROJECT_STATE.md"}))

        self.assertEqual(empty_query, {"status": "error", "error": "query is required"})
        self.assertEqual(search_error, {"status": "error", "error": "network unavailable"})
        self.assertEqual(empty_url, {"status": "error", "error": "url is required"})
        self.assertEqual(fetch_error["status"], "error")
        self.assertIn("missing", fetch_error["error"])
        self.assertEqual(unknown_tool, {"status": "error", "error": "Unknown tool: read_file"})

    def test_web_fetch_table_page_returns_tables_and_non_table_evidence(self):
        connector = FakeConnector()
        connector.pages["https://example.test/prices"] = """
        <html><head><title>Price table</title></head><body>
          <p>Updated 28 June 2026.</p>
          <table>
            <caption>Retail</caption>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>เบนซิน 95</td><td>39.50</td></tr>
          </table>
        </body></html>
        """
        tools = WebResearchTools(connector)

        payload = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/prices"}))

        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["blocked"])
        self.assertEqual(payload["title"], "Price table")
        self.assertIn("Updated 28 June 2026", payload["evidence"])
        self.assertNotIn("เบนซิน 95", payload["evidence"])
        self.assertEqual(
            payload["tables"],
            [{"caption": "Retail", "headers": ["Fuel", "Price"], "rows": [["เบนซิน 95", "39.50"]]}],
        )

    def test_web_fetch_uses_source_adapter_before_html_extraction(self):
        connector = FakeConnector()
        connector.pages["https://oil-price.bangchak.co.th/apioilprice2/th"] = (
            "["
            '{"OilDateNow":"29/06/2569",'
            '"OilList":"[{\\"OilName\\":\\"Diesel B20\\",\\"PriceToday\\":32.50,'
            '\\"PriceTomorrow\\":32.50,\\"PriceDifTomorrow\\":0.00},'
            '{\\"OilName\\":\\"Premium Diesel\\",\\"PriceToday\\":54.25,'
            '\\"PriceTomorrow\\":54.25,\\"PriceDifTomorrow\\":0.00}]"}'
            "]"
        )
        tools = WebResearchTools(connector)

        payload = json.loads(tools.dispatch("web_fetch", {"url": "https://oil-price.bangchak.co.th/BcpOilPrice2/th"}))

        self.assertEqual(connector.fetch_calls, ["https://oil-price.bangchak.co.th/apioilprice2/th"])
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["blocked"])
        self.assertEqual(payload["source_type"], "fetched-data")
        self.assertEqual(payload["tables"][0]["rows"][0], ["Diesel B20", "32.50", "32.50", "0.00"])
        self.assertIn("Premium Diesel: 54.25", tools.evidence_corpus())

    def test_web_fetch_playwright_flag_off_never_invokes_fetcher(self):
        connector = FakeConnector()
        connector.pages["https://example.test/js-only"] = "<html><body><div id='app'></div></body></html>"
        playwright = FakePlaywrightFetcher("<html><body><p>Rendered</p></body></html>")
        tools = WebResearchTools(connector, playwright_fetch_enabled=False, playwright_fetcher=playwright)

        payload = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/js-only"}))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(playwright.calls, [])
        self.assertEqual(connector.fetch_calls, ["https://example.test/js-only"])

    def test_web_fetch_playwright_last_resort_extracts_rendered_tables(self):
        connector = FakeConnector()
        connector.pages["https://example.test/js-only"] = "<html><head><title>Loading</title></head><body><div id='app'></div></body></html>"
        rendered = """
        <html><head><title>Rendered prices</title></head><body>
          <p>Updated after JavaScript render.</p>
          <table>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>Diesel B7</td><td>31.94</td></tr>
            <tr><td>Gasohol 95</td><td>39.50</td></tr>
          </table>
        </body></html>
        """
        playwright = FakePlaywrightFetcher(rendered)
        tools = WebResearchTools(connector, playwright_fetch_enabled=True, playwright_fetcher=playwright)

        payload = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/js-only"}))

        self.assertEqual(playwright.calls, [("https://example.test/js-only", 8.0)])
        self.assertEqual(payload["title"], "Rendered prices")
        self.assertFalse(payload["blocked"])
        self.assertEqual(payload["tables"][0]["rows"], [["Diesel B7", "31.94"], ["Gasohol 95", "39.50"]])
        self.assertIn("Updated after JavaScript render", payload["evidence"])
        self.assertIn("Diesel B7: 31.94", tools.evidence_corpus())

    def test_web_fetch_playwright_timeout_falls_back_to_http_result(self):
        connector = FakeConnector()
        connector.pages["https://example.test/blocked"] = "<html><body><p>Radware Captcha Page</p></body></html>"
        playwright = FakePlaywrightFetcher(TimeoutError("render timed out"))
        tools = WebResearchTools(connector, playwright_fetch_enabled=True, playwright_fetcher=playwright)

        payload = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/blocked"}))

        self.assertEqual(playwright.calls, [("https://example.test/blocked", 8.0)])
        self.assertEqual(payload["source_type"], "fetch-blocked")
        self.assertTrue(payload["blocked"])
        self.assertEqual(payload["evidence"], "")
        self.assertEqual(payload["tables"], [])

    def test_web_fetch_playwright_rendered_placeholder_is_dropped(self):
        connector = FakeConnector()
        connector.pages["https://example.test/js-placeholder"] = "<html><body><div id='app'></div></body></html>"
        rendered = """
        <html><head><title>Rendered placeholder</title></head><body>
          <table>
            <caption>Loading.....</caption>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>Diesel</td><td>30.00</td></tr>
            <tr><td>Gasohol</td><td>30.00</td></tr>
          </table>
        </body></html>
        """
        playwright = FakePlaywrightFetcher(rendered)
        tools = WebResearchTools(connector, playwright_fetch_enabled=True, playwright_fetcher=playwright)

        payload = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/js-placeholder"}))

        self.assertEqual(playwright.calls, [("https://example.test/js-placeholder", 8.0)])
        self.assertEqual(payload["tables"], [])
        self.assertEqual(payload["evidence"], "")
        self.assertEqual(tools.evidence_corpus(), "")

    def test_web_fetch_cap_is_enforced(self):
        connector = FakeConnector()
        connector.pages["https://example.test/one"] = "<html><body><p>One</p></body></html>"
        connector.pages["https://example.test/two"] = "<html><body><p>Two</p></body></html>"
        tools = WebResearchTools(connector, max_fetch=1)

        first = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/one"}))
        second = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/two"}))

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second, {"status": "error", "error": "fetch limit reached"})

    def test_evidence_corpus_accumulates_fetched_prose_and_table_values(self):
        connector = FakeConnector()
        connector.pages["https://example.test/prices"] = """
        <html><head><title>Price table</title></head><body>
          <p>Updated 28 June 2026.</p>
          <table>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>Diesel B7</td><td>31.94</td></tr>
          </table>
        </body></html>
        """
        tools = WebResearchTools(connector)

        json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/prices"}))

        corpus = tools.evidence_corpus()
        self.assertIn("Updated 28 June 2026", corpus)
        self.assertIn("Diesel B7: 31.94", corpus)

    def test_sources_reflect_registered_order_with_no_index_reuse(self):
        connector = FakeConnector()
        connector.pages["https://example.test/a"] = "<html><body><p>Alpha page</p></body></html>"
        connector.pages["https://example.test/c"] = "<html><body><p>Gamma</p></body></html>"
        tools = WebResearchTools(connector)

        json.loads(tools.dispatch("web_search", {"query": "latest docs"}))
        fetched = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/c"}))
        repeated = json.loads(tools.dispatch("web_fetch", {"url": "https://example.test/a"}))

        self.assertEqual(fetched["index"], 3)
        self.assertEqual(repeated["index"], 1)
        self.assertEqual([source["index"] for source in tools.sources()], [1, 2, 3])
        self.assertEqual([source["url"] for source in tools.sources()], [
            "https://example.test/a",
            "https://example.test/b",
            "https://example.test/c",
        ])


if __name__ == "__main__":
    unittest.main()
