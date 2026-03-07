"""Gemini-specific overrides."""

import asyncio
from playwright.async_api import Page
from llm_council.config import PROVIDERS
from llm_council.browser.base import LLMPage


class GeminiPage(LLMPage):
    def __init__(self, page: Page):
        super().__init__(page, PROVIDERS["gemini"])

    async def send_prompt(self, text: str):
        await self.page.evaluate("""() => {
            const el = document.querySelector('.ql-editor');
            if (!el) throw new Error('Input not found');
            el.focus();
        }""")
        await asyncio.sleep(0.3)
        await self.page.keyboard.press("Meta+a")
        await asyncio.sleep(0.1)
        await self.page.evaluate("(text) => document.execCommand('insertText', false, text)", text)
        await asyncio.sleep(0.5)
        await self.page.keyboard.press("Enter")
