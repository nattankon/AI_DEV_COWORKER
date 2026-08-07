import json
import unittest
from pathlib import Path

from chat_source_adapters import fetch_source_tables


FIXTURES = Path(__file__).with_name("fixtures")


class ChatSourceAdaptersTests(unittest.TestCase):
    def test_bangchak_adapter_maps_fixture_to_structured_price_rows(self):
        fixture = (FIXTURES / "bangchak_apioilprice2_th.json").read_text(encoding="utf-8")
        calls = []

        def fetcher(url: str, timeout: float) -> str:
            calls.append((url, timeout))
            return fixture

        tables = fetch_source_tables("https://oil-price.bangchak.co.th/BcpOilPrice2/th", fetcher=fetcher, timeout=4.0)

        self.assertEqual(calls, [("https://oil-price.bangchak.co.th/apioilprice2/th", 4.0)])
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertIn("Bangchak", table["caption"])
        self.assertEqual(table["headers"], ["Fuel", "PriceToday", "PriceTomorrow", "PriceDifTomorrow"])
        self.assertIn(["ดีเซล B20", "32.50", "32.50", "0.00"], table["rows"])
        self.assertIn(["ไฮ พรีเมียม ดีเซล พลัส", "54.25", "54.25", "0.00"], table["rows"])
        today_values = {row[1] for row in table["rows"]}
        self.assertGreater(len(today_values), 1)

    def test_bangchak_main_page_also_routes_through_the_api_adapter(self):
        fixture = (FIXTURES / "bangchak_apioilprice2_th.json").read_text(encoding="utf-8")
        calls = []

        def fetcher(url: str, timeout: float) -> str:
            calls.append((url, timeout))
            return fixture

        tables = fetch_source_tables("https://www.bangchak.co.th/th/oilprice", fetcher=fetcher, timeout=4.0)

        # The 2026-07-03 smoke showed this page falling to raw HTML (quality 2)
        # because only the subdomain matched; both must serve from the JSON API.
        self.assertEqual(calls, [("https://oil-price.bangchak.co.th/apioilprice2/th", 4.0)])
        self.assertEqual(len(tables), 1)

    def test_bangchak_non_price_pages_are_not_hijacked_by_the_adapter(self):
        def fetcher(url: str, timeout: float) -> str:
            raise AssertionError(f"adapter must not fetch for non-price pages, got {url}")

        # A corporate page must never return a fuel-price table as its content.
        tables = fetch_source_tables("https://www.bangchak.co.th/en/investor-relations", fetcher=fetcher, timeout=4.0)

        self.assertEqual(tables, [])

    def test_eppo_adapter_maps_fixture_to_company_fuel_rows(self):
        fixture = (FIXTURES / "eppo_oil_prices.json").read_text(encoding="utf-8")
        calls = []

        def fetcher(url: str, timeout: float) -> str:
            calls.append((url, timeout))
            return fixture

        tables = fetch_source_tables("https://www.eppo.go.th/data-energy-statistic/energy-price-th/foo", fetcher=fetcher, timeout=6.0)

        self.assertEqual(calls, [("https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices", 6.0)])
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertIn("EPPO", table["caption"])
        self.assertEqual(table["headers"], ["Provider", "Fuel", "Price", "Date", "Time"])
        self.assertIn(["ptt", "Gasoline 95", "47.64", "2026-06-25", "05:00"], table["rows"])
        self.assertIn(["bcp", "Premium Diesel", "54.25", "2026-06-25", "05:00"], table["rows"])
        self.assertIn(["shell", "Gasohol 95", "38.55", "2026-06-27", "05:00"], table["rows"])
        prices = {row[2] for row in table["rows"] if row[2] != "-"}
        self.assertGreater(len(prices), 1)

    def test_unknown_host_has_no_adapter(self):
        def fetcher(url: str, timeout: float) -> str:
            raise AssertionError(f"unexpected fetch: {url}")

        self.assertEqual(fetch_source_tables("https://example.test/page", fetcher=fetcher, timeout=1.0), [])


if __name__ == "__main__":
    unittest.main()
