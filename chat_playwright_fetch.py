from __future__ import annotations


class PlaywrightFetcher:
    def fetch(self, url: str, *, timeout: float = 8.0) -> str | None:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except Exception:
            return None

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(str(url or ""), wait_until="networkidle", timeout=max(1, int(timeout * 1000)))
                    return page.content()
                finally:
                    browser.close()
        except PlaywrightTimeoutError:
            return None
        except Exception:
            return None
