"""Base LLM page interaction: send prompt, wait for response, extract text."""

import asyncio
import time
from dataclasses import dataclass
from playwright.async_api import Page

from llm_council.config import (
    ProviderConfig,
    RESPONSE_TIMEOUT_MS,
    STABILITY_INTERVAL_S,
    STABILITY_CHECKS,
    TYPE_DELAY_MS,
)


@dataclass
class LLMResponse:
    text: str  # plain text for prompts/stability
    html: str  # rich HTML for display


class LLMPage:
    def __init__(self, page: Page, config: ProviderConfig):
        self.page = page
        self.config = config

    async def send_prompt(self, text: str):
        """Type the prompt into the input and submit."""
        input_el = await self.page.wait_for_selector(self.config.input_selector, timeout=10_000)
        await input_el.click()
        await asyncio.sleep(0.3)

        try:
            await self.page.evaluate(f"navigator.clipboard.writeText({repr(text)})")
            await asyncio.sleep(0.1)
            await self.page.keyboard.press("Meta+v")
            await asyncio.sleep(0.3)
        except Exception:
            await input_el.type(text, delay=TYPE_DELAY_MS)
            await asyncio.sleep(0.3)

        await self.page.keyboard.press(self.config.submit_shortcut)

    async def wait_for_response(self, callback=None) -> LLMResponse:
        """Wait for the LLM to finish responding and return text + html.

        callback: optional async callable(html) called periodically with partial HTML
        """
        await self.page.wait_for_selector(
            self.config.message_selector, timeout=30_000
        )

        start = time.time()
        last_text = ""
        stable_count = 0

        while (time.time() - start) < (RESPONSE_TIMEOUT_MS / 1000):
            await asyncio.sleep(STABILITY_INTERVAL_S)

            if self.config.streaming_check:
                try:
                    still_streaming = await self.page.evaluate(self.config.streaming_check)
                    if still_streaming:
                        current = await self._extract_last_response()
                        if callback and current.html:
                            await callback(current.html)
                        last_text = current.text
                        stable_count = 0
                        continue
                except Exception:
                    pass

            current = await self._extract_last_response()
            if callback and current.html and current.text != last_text:
                await callback(current.html)

            if current.text and current.text == last_text and len(current.text.strip()) > 0:
                stable_count += 1
                if stable_count >= STABILITY_CHECKS:
                    return current
            else:
                stable_count = 0
                last_text = current.text

        final = await self._extract_last_response()
        return final if final.text else LLMResponse(text=last_text, html=last_text)

    async def _extract_last_response(self) -> LLMResponse:
        """Extract text and HTML from the last assistant message."""
        try:
            messages = await self.page.query_selector_all(self.config.message_selector)
            if not messages:
                return LLMResponse(text="", html="")
            last = messages[-1]
            text = (await last.inner_text()).strip()
            html = (await last.inner_html()).strip()
            return LLMResponse(text=text, html=html)
        except Exception:
            return LLMResponse(text="", html="")
