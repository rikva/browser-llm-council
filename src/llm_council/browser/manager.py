"""BrowserManager: CDP connection and tab lifecycle."""

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from llm_council.config import PROVIDERS, PAGE_LOAD_TIMEOUT_MS


class BrowserManager:
    def __init__(self, cdp_url: str = "http://127.0.0.1:9222"):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._pages: dict[str, Page] = {}

    async def connect(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
        self._context = self._browser.contexts[0]

    async def disconnect(self):
        # Close only the tabs we opened
        for page in self._pages.values():
            try:
                await page.close()
            except Exception:
                pass
        self._pages.clear()
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            self._browser = None
            self._context = None

    async def open_provider_tab(self, provider_name: str) -> Page:
        if self._context is None:
            raise RuntimeError("Not connected to browser")
        config = PROVIDERS[provider_name]
        page = await self._context.new_page()
        page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
        await page.goto(config.new_chat_url, wait_until="domcontentloaded")
        # Wait for input to be ready, then wait for page to stabilize
        # (some providers like Claude redirect/refresh after initial load)
        await page.wait_for_selector(config.input_selector, timeout=PAGE_LOAD_TIMEOUT_MS)
        await asyncio.sleep(3)
        # Re-check input is still there after settle (handles redirects)
        await page.wait_for_selector(config.input_selector, timeout=PAGE_LOAD_TIMEOUT_MS)
        self._pages[provider_name] = page
        return page

    async def get_page(self, provider_name: str) -> Page | None:
        return self._pages.get(provider_name)

    async def close_provider_tab(self, provider_name: str):
        page = self._pages.pop(provider_name, None)
        if page:
            try:
                await page.close()
            except Exception:
                pass
