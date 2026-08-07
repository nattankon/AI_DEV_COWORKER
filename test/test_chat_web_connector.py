import unittest
import time

import os

import chat_web_connector as cwc
from chat_web_connector import ChatWebConnector, _extract_page_evidence, _extract_tables


class FakeSearchProvider:
    def __init__(self, results=None, error: Exception | None = None):
        self.results = list(results or [])
        self.error = error
        self.calls = []

    def search(self, query: str, *, count: int):
        self.calls.append((query, count))
        if self.error:
            raise self.error
        return list(self.results)


class ChatWebConnectorTests(unittest.TestCase):
    def setUp(self):
        self._original_search_api_key = os.environ.pop("COWORK_SEARCH_API_KEY", None)
        self._original_search_api_provider = os.environ.pop("COWORK_SEARCH_API_PROVIDER", None)

    def tearDown(self):
        if self._original_search_api_key is not None:
            os.environ["COWORK_SEARCH_API_KEY"] = self._original_search_api_key
        else:
            os.environ.pop("COWORK_SEARCH_API_KEY", None)
        if self._original_search_api_provider is not None:
            os.environ["COWORK_SEARCH_API_PROVIDER"] = self._original_search_api_provider
        else:
            os.environ.pop("COWORK_SEARCH_API_PROVIDER", None)

    def test_extract_tables_preserves_row_cell_structure(self):
        html = """
        <html><body>
          <h2>Retail prices</h2>
          <table>
            <caption>Bangkok</caption>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>เบนซิน 95</td><td>39.50</td></tr>
            <tr><td>Diesel B7</td><td>31.94 THB/litre</td></tr>
          </table>
        </body></html>
        """

        tables = _extract_tables(html)

        self.assertEqual(
            tables,
            [
                {
                    "caption": "Bangkok",
                    "headers": ["Fuel", "Price"],
                    "rows": [["เบนซิน 95", "39.50"], ["Diesel B7", "31.94 THB/litre"]],
                }
            ],
        )

    def test_extract_tables_handles_multiple_tables_and_caps(self):
        html = """
        <html><body>
          <h2>First heading</h2>
          <table>
            <tr><th>Name</th><th>Value</th></tr>
            <tr><td>A</td><td>1</td></tr>
            <tr><td>B</td><td>2</td></tr>
          </table>
          <h2>Second heading</h2>
          <table>
            <tr><td>C</td><td>3</td></tr>
          </table>
          <table><tr><td>D</td><td>4</td></tr></table>
        </body></html>
        """

        tables = _extract_tables(html, max_tables=2, max_rows=1)

        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["caption"], "First heading")
        self.assertEqual(tables[0]["headers"], ["Name", "Value"])
        self.assertEqual(tables[0]["rows"], [["A", "1"]])
        self.assertEqual(tables[1]["caption"], "Second heading")
        self.assertEqual(tables[1]["rows"], [["C", "3"]])

    def test_extract_tables_ignores_nested_table_rows(self):
        html = """
        <html><body>
          <table>
            <tr><th>Name</th><th>Value</th></tr>
            <tr>
              <td>Outer <table><tr><td>Inner</td></tr></table> Tail</td>
              <td>Kept</td>
            </tr>
          </table>
        </body></html>
        """

        tables = _extract_tables(html)

        self.assertEqual(tables[0]["rows"], [["Outer Tail", "Kept"]])

    def test_extract_tables_preserves_empty_cells_for_alignment(self):
        html = """
        <html><body>
          <table>
            <tr><th></th><th>2026</th><th>2027</th></tr>
            <tr><td>Gasoline</td><td>39.50</td><td>40.00</td></tr>
          </table>
        </body></html>
        """

        tables = _extract_tables(html)

        self.assertEqual(tables[0]["headers"], ["", "2026", "2027"])
        self.assertEqual(tables[0]["rows"], [["Gasoline", "39.50", "40.00"]])

    def test_extract_tables_uses_preceding_heading_for_first_following_table_only(self):
        html = """
        <html><body>
          <h2>Quarterly data</h2>
          <table><tr><td>A</td><td>1</td></tr></table>
          <table><tr><td>B</td><td>2</td></tr></table>
        </body></html>
        """

        tables = _extract_tables(html)

        self.assertEqual(tables[0]["caption"], "Quarterly data")
        self.assertEqual(tables[1]["caption"], "")

    def test_extract_page_evidence_serializes_multi_column_tables_with_delimiters(self):
        html = """
        <html><body>
          <table>
            <tr><th>Fuel</th><th>Bangkok</th><th>Region</th></tr>
            <tr><td>Gasoline</td><td>39.50</td><td>40.00</td></tr>
            <tr><td>Diesel</td><td>31.94</td><td>32.44</td></tr>
          </table>
        </body></html>
        """

        evidence = _extract_page_evidence(html, query="fuel prices")

        self.assertIn("Gasoline: Bangkok 39.50; Region 40.00", evidence)
        self.assertIn("39.50; Region 40.00 | Diesel:", evidence)

    def test_extract_page_evidence_prioritizes_table_lines_when_prose_is_long(self):
        html = """
        <html><body>
          <p>This page has a very long introduction that can consume the evidence budget before
          the table appears. It repeats background context many times so the extractor must still
          preserve the structured row values.</p>
          <table>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>Diesel B7</td><td>31.94 THB/litre</td></tr>
          </table>
        </body></html>
        """

        evidence = _extract_page_evidence(html, query="fuel prices", max_chars=50)

        self.assertIn("Diesel B7: 31.94 THB/litre", evidence)

    def test_extract_page_evidence_adds_table_label_value_lines(self):
        html = """
        <html><body>
          <main>
            <p>Updated 28 June 2026.</p>
            <table>
              <tr><th>Fuel</th><th>Price</th></tr>
              <tr><td>เบนซิน 95</td><td>39.50</td></tr>
              <tr><td>Diesel B7</td><td>31.94 THB/litre</td></tr>
            </table>
          </main>
        </body></html>
        """

        evidence = _extract_page_evidence(html, query="fuel prices")

        self.assertIn("Updated 28 June 2026", evidence)
        self.assertIn("เบนซิน 95: 39.50", evidence)
        self.assertIn("Diesel B7: 31.94 THB/litre", evidence)

    def test_extract_tables_drops_loading_placeholder_table(self):
        html = """
        <html><body>
          <table>
            <caption>Loading.....</caption>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>Gasoline 95</td><td>30.00</td></tr>
            <tr><td>Diesel B7</td><td>30.00</td></tr>
          </table>
        </body></html>
        """

        self.assertEqual(_extract_tables(html), [])

    def test_extract_page_evidence_drops_uniform_numeric_placeholder_values(self):
        html = """
        <html><body>
          <p>Retail price table is loaded dynamically.</p>
          <table>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>Gasoline 95</td><td>30.00</td></tr>
            <tr><td>Diesel B7</td><td>30.00</td></tr>
            <tr><td>E20</td><td>30.00</td></tr>
          </table>
        </body></html>
        """

        evidence = _extract_page_evidence(html, query="fuel price")

        self.assertNotIn("Gasoline 95: 30.00", evidence)
        self.assertNotIn("Diesel B7: 30.00", evidence)
        self.assertIn("Retail price table is loaded dynamically", evidence)

    def test_extract_tables_keeps_real_varied_numeric_table(self):
        html = """
        <html><body>
          <table>
            <tr><th>Fuel</th><th>Price</th></tr>
            <tr><td>Gasoline 95</td><td>39.50</td></tr>
            <tr><td>Diesel B7</td><td>31.94</td></tr>
          </table>
        </body></html>
        """

        tables = _extract_tables(html)

        self.assertEqual(tables[0]["rows"], [["Gasoline 95", "39.50"], ["Diesel B7", "31.94"]])

    def test_extract_page_evidence_no_table_page_unaffected(self):
        html = "<html><body><p>Updated 28 June 2026.</p><p>No table here.</p></body></html>"

        evidence = _extract_page_evidence(html, query="updated", max_chars=200)

        self.assertEqual(evidence, "Updated 28 June 2026. . No table here. .")

    def test_search_parses_duckduckgo_html_results_with_sources(self):
        html = """
        <html><body>
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs">Example Docs</a>
          <a class="result__snippet">Official documentation for the example product.</a>
          <a class="result__a" href="https://example.org/news">Example News</a>
          <a class="result__snippet">Recent release notes and updates.</a>
        </body></html>
        """
        requested_urls: list[str] = []

        def fetcher(url: str, timeout: float) -> str:
            requested_urls.append(url)
            return html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("latest example docs", max_results=2)

        self.assertEqual(response.query, "latest example docs")
        self.assertEqual(len(response.results), 2)
        self.assertEqual(response.results[0].title, "Example Docs")
        self.assertEqual(response.results[0].url, "https://example.com/docs")
        self.assertEqual(response.results[0].snippet, "Official documentation for the example product.")
        self.assertEqual(response.results[1].url, "https://example.org/news")
        self.assertIn("duckduckgo.com/html", requested_urls[0])
        self.assertNotIn("api_key", repr(response).casefold())

    def test_search_reports_fetch_error_without_results(self):
        def fetcher(_url: str, _timeout: float) -> str:
            raise RuntimeError("network unavailable")

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("current pricing", max_results=3)

        self.assertEqual(response.results, [])
        self.assertIn("network unavailable", response.error)

    def test_search_fetches_engines_and_pages_concurrently_preserving_order(self):
        def search_html(items: list[tuple[str, str, str]]) -> str:
            body = []
            for title, url, snippet in items:
                body.append(
                    f"""
                    <li class="b_algo">
                      <h2><a href="{url}">{title}</a></h2>
                      <p>{snippet}</p>
                    </li>
                    <a class="result__a" href="{url}">{title}</a>
                    <a class="result__snippet">{snippet}</a>
                    """
                )
            return "<html><body>" + "\n".join(body) + "</body></html>"

        def fetcher(url: str, timeout: float) -> str:
            del timeout
            time.sleep(0.15)
            if "duckduckgo.com" in url:
                return search_html(
                    [
                        ("Alpha Docs", "https://alpha.example/docs", "alpha docs current"),
                        ("Alpha Blog", "https://alpha.example/blog", "alpha blog current"),
                    ]
                )
            if "bing.com/search" in url:
                return search_html([("Alpha News", "https://alpha.example/news", "alpha news current")])
            return f"<html><body><p>Fresh evidence for {url}</p></body></html>"

        connector = ChatWebConnector(fetcher=fetcher)

        started = time.perf_counter()
        response = connector.search("alpha current", max_results=3)
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.55)
        self.assertEqual([result.url for result in response.results], [
            "https://alpha.example/docs",
            "https://alpha.example/blog",
            "https://alpha.example/news",
        ])
        self.assertTrue(all(result.source_type == "fetched-page" for result in response.results))

    def test_search_falls_back_to_bing_when_duckduckgo_has_no_results(self):
        bing_html = """
        <html><body>
          <li class="b_algo">
            <cite>platform.openai.com</cite>
            <h2><a href="https://www.bing.com/ck/a?!&&u=a1aHR0cHM6Ly9wbGF0Zm9ybS5vcGVuYWkuY29tL2RvY3M&ntb=1">OpenAI Docs</a></h2>
            <p>Explore official OpenAI API documentation.</p>
          </li>
        </body></html>
        """
        requested_urls: list[str] = []

        def fetcher(url: str, timeout: float) -> str:
            requested_urls.append(url)
            return "<html><body>challenge</body></html>" if "duckduckgo.com" in url else bing_html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("OpenAI official docs", max_results=2)

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].title, "OpenAI Docs")
        self.assertEqual(response.results[0].url, "https://platform.openai.com/docs")
        self.assertIn("duckduckgo.com/html", requested_urls[0])
        self.assertIn("bing.com/search", requested_urls[1])

    def test_search_uses_generic_query_terms_for_non_oil_topic(self):
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://weather.example/bangkok">Bangkok weather forecast</a></h2>
            <p>Current Bangkok weather forecast and rain probability.</p>
          </li>
          <li class="b_algo">
            <h2><a href="https://tourism.example/thailand">Thailand travel guide</a></h2>
            <p>Hotels, beaches, shopping, and tourism information.</p>
          </li>
          <li class="b_algo">
            <h2><a href="https://wiki.example/thailand">Thailand - encyclopedia</a></h2>
            <p>General country information about Thailand.</p>
          </li>
        </body></html>
        """

        def fetcher(url: str, timeout: float) -> str:
            return "<html></html>" if "duckduckgo.com" in url else search_html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("Bangkok current weather forecast", max_results=4)

        urls = [result.url for result in response.results]
        self.assertIn("https://weather.example/bangkok", urls)
        self.assertNotIn("https://tourism.example/thailand", urls)
        self.assertNotIn("https://wiki.example/thailand", urls)

    def test_search_gates_all_off_topic_results_when_no_query_terms_overlap(self):
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://www.douyin.com/search/video">短视频热榜</a></h2>
            <p>热门视频、娱乐和直播内容。</p>
          </li>
          <li class="b_algo">
            <h2><a href="https://www.zhihu.com/question/123">生活问答</a></h2>
            <p>与三维软件发布说明无关的中文问答。</p>
          </li>
        </body></html>
        """

        def fetcher(url: str, timeout: float) -> str:
            return "<html></html>" if "duckduckgo.com" in url else search_html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("Blender latest version release notes", max_results=4)

        self.assertEqual(response.results, [])
        self.assertEqual(response.error, "")

    def test_search_keeps_relevant_official_result_with_minimal_overlap(self):
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://www.videolan.org/vlc/">VLC media player</a></h2>
            <p>Official VLC media player downloads and release information.</p>
          </li>
          <li class="b_algo">
            <h2><a href="https://video.example/trends">Video trends</a></h2>
            <p>Short video entertainment updates.</p>
          </li>
        </body></html>
        """

        def fetcher(url: str, timeout: float) -> str:
            return "<html></html>" if "duckduckgo.com" in url else search_html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("VLC media player", max_results=3)

        self.assertEqual([result.url for result in response.results], ["https://www.videolan.org/vlc/"])

    def test_search_keeps_relevant_thai_result(self):
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://gold.example/thai">ราคาทองวันนี้</a></h2>
            <p>ราคาทองคำวันนี้ อัปเดตล่าสุดจากสมาคมค้าทองคำ</p>
          </li>
          <li class="b_algo">
            <h2><a href="https://travel.example/thai">ท่องเที่ยวไทย</a></h2>
            <p>แนะนำสถานที่ท่องเที่ยวและโรงแรม</p>
          </li>
        </body></html>
        """

        def fetcher(url: str, timeout: float) -> str:
            return "<html></html>" if "duckduckgo.com" in url else search_html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("ราคาทองวันนี้", max_results=3)

        self.assertEqual([result.url for result in response.results], ["https://gold.example/thai"])

    def test_search_api_provider_results_flow_through_normal_pipeline(self):
        provider = FakeSearchProvider(
            [
                {
                    "title": "Blender Release Notes",
                    "url": "https://www.blender.org/download/releases/4-3/",
                    "snippet": "Official Blender 4.3 release notes.",
                },
                {
                    "title": "Unrelated Video Trends",
                    "url": "https://video.example/trends",
                    "snippet": "Short video entertainment.",
                },
            ]
        )
        requested_urls: list[str] = []

        def fetcher(url: str, timeout: float) -> str:
            del timeout
            requested_urls.append(url)
            return "<html><body><p>Blender 4.3 release notes and version details.</p></body></html>"

        connector = ChatWebConnector(fetcher=fetcher, search_provider=provider)

        response = connector.search("Blender latest version release notes", max_results=4)

        self.assertEqual(provider.calls, [("Blender latest version release notes", 4)])
        self.assertEqual([result.url for result in response.results], ["https://www.blender.org/download/releases/4-3/"])
        self.assertEqual(response.results[0].source_type, "fetched-page")
        self.assertIn("Blender 4.3 release notes", response.results[0].evidence)
        self.assertTrue(all("duckduckgo.com" not in url and "bing.com/search" not in url for url in requested_urls))

    def test_search_without_provider_uses_html_scraping_path(self):
        requested_urls: list[str] = []
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://www.videolan.org/vlc/">VLC media player</a></h2>
            <p>Official VLC media player downloads.</p>
          </li>
        </body></html>
        """

        def fetcher(url: str, timeout: float) -> str:
            del timeout
            requested_urls.append(url)
            return "<html></html>" if "duckduckgo.com" in url else search_html

        connector = ChatWebConnector(fetcher=fetcher, search_provider=None)

        response = connector.search("VLC media player", max_results=2)

        self.assertEqual([result.url for result in response.results], ["https://www.videolan.org/vlc/"])
        self.assertTrue(any("duckduckgo.com/html" in url for url in requested_urls))
        self.assertTrue(any("bing.com/search" in url for url in requested_urls))

    def test_search_api_error_falls_back_to_html_scraping(self):
        provider = FakeSearchProvider(error=TimeoutError("api timeout"))
        requested_urls: list[str] = []
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://www.videolan.org/vlc/">VLC media player</a></h2>
            <p>Official VLC media player downloads.</p>
          </li>
        </body></html>
        """

        def fetcher(url: str, timeout: float) -> str:
            del timeout
            requested_urls.append(url)
            return "<html></html>" if "duckduckgo.com" in url else search_html

        connector = ChatWebConnector(fetcher=fetcher, search_provider=provider)

        response = connector.search("VLC media player", max_results=2)

        self.assertEqual(provider.calls, [("VLC media player", 2)])
        self.assertEqual([result.url for result in response.results], ["https://www.videolan.org/vlc/"])
        self.assertTrue(any("bing.com/search" in url for url in requested_urls))

    def test_search_api_removes_bad_html_source_class_for_blender_query(self):
        provider = FakeSearchProvider(
            [
                {
                    "title": "Blender 4.3 Release Notes",
                    "url": "https://developer.blender.org/docs/release_notes/4.3/",
                    "snippet": "Official Blender latest version release notes.",
                }
            ]
        )

        connector = ChatWebConnector(
            fetcher=lambda _url, _timeout: "<html><body><p>Official Blender release notes.</p></body></html>",
            search_provider=provider,
        )

        response = connector.search("Blender latest version", max_results=3)

        self.assertEqual([result.url for result in response.results], ["https://developer.blender.org/docs/release_notes/4.3/"])
        self.assertIn("Blender", response.results[0].title)

    def test_search_fetches_pages_and_extracts_evidence_for_synthesis(self):
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://energy.example/oil">Official Oil Prices</a></h2>
            <p>Current Thai retail fuel prices.</p>
          </li>
        </body></html>
        """
        page_html = """
        <html>
          <head><title>Official Oil Prices</title><script>ignoreMe()</script><style>.x{}</style></head>
          <body>
            <main>
              <h1>Retail oil price update</h1>
              <p>Updated 28 June 2026 at 10:30.</p>
              <table><tr><th>Fuel</th><th>Price</th></tr><tr><td>Diesel B7</td><td>31.94 THB/litre</td></tr></table>
            </main>
          </body>
        </html>
        """

        def fetcher(url: str, timeout: float) -> str:
            return page_html if url == "https://energy.example/oil" else search_html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("current fuel prices", max_results=1)

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].source_type, "fetched-page")
        self.assertGreaterEqual(response.results[0].quality_score, 1)
        self.assertIn("Updated 28 June 2026", response.results[0].evidence)
        self.assertIn("Diesel B7", response.results[0].evidence)
        self.assertIn("31.94 THB/litre", response.analysis)

    def test_search_adds_fuel_source_hints_from_generic_registry(self):
        def fetcher(_url: str, _timeout: float) -> str:
            return "<html></html>"

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("ราคาน้ำมันล่าสุด ประเทศไทย", max_results=5)

        urls = [result.url for result in response.results]
        self.assertIn("https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices", urls)
        self.assertIn("https://oil-price.bangchak.co.th/apioilprice2/th", urls)
        self.assertIn("https://www.globalpetrolprices.com/Thailand/gasoline_prices/", urls)
        self.assertTrue(all(result.source_type == "trusted-hint" for result in response.results))

    def test_source_hint_registry_is_generic_for_non_oil_profiles(self):
        original_profiles = cwc._SOURCE_HINT_PROFILES
        cwc._SOURCE_HINT_PROFILES = (
            *original_profiles,
            {
                "keywords": ("weatherbot",),
                "hints": (
                    {
                        "title": "WeatherBot official status",
                        "url": "https://status.weatherbot.example/current",
                        "snippet": "Official WeatherBot current status feed.",
                        "source_type": "trusted-hint",
                        "quality_score": 7,
                    },
                ),
            },
        )
        try:
            connector = ChatWebConnector(fetcher=lambda _url, _timeout: "<html></html>")

            response = connector.search("weatherbot current status", max_results=3)
        finally:
            cwc._SOURCE_HINT_PROFILES = original_profiles

        self.assertEqual(response.results[0].url, "https://status.weatherbot.example/current")
        self.assertEqual(response.results[0].source_type, "trusted-hint")

    def test_captcha_pages_are_not_treated_as_extracted_evidence(self):
        search_html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://blocked.example/oil">Blocked Oil Prices</a></h2>
            <p>Current Thai retail fuel prices.</p>
          </li>
        </body></html>
        """
        captcha_html = """
        <html><body>
          <title>Radware Captcha Page</title>
          <p>We apologize for the inconvenience but your activity made us think that you are a bot.</p>
        </body></html>
        """

        def fetcher(url: str, timeout: float) -> str:
            return captcha_html if url == "https://blocked.example/oil" else search_html

        connector = ChatWebConnector(fetcher=fetcher)

        response = connector.search("current fuel prices", max_results=1)

        self.assertEqual(response.results[0].source_type, "fetch-blocked")
        self.assertEqual(response.results[0].evidence, "")
        self.assertIn("fetch blocked", response.analysis)
        self.assertIn("does not contain extracted exact values", response.analysis)


if __name__ == "__main__":
    unittest.main()



