"""Claude-specific overrides."""

import asyncio
from playwright.async_api import Page
from llm_council.config import PROVIDERS
from llm_council.browser.base import LLMPage, LLMResponse


class ClaudePage(LLMPage):
    def __init__(self, page: Page):
        super().__init__(page, PROVIDERS["claude"])

    async def send_prompt(self, text: str):
        # Wait for the input element to actually exist in DOM first
        await self.page.wait_for_selector(self.config.input_selector, timeout=10_000)
        await asyncio.sleep(0.5)

        await self.page.evaluate("""() => {
            const el = document.querySelector('.tiptap.ProseMirror')
                    || document.querySelector('[contenteditable="true"].ProseMirror')
                    || document.querySelector('[contenteditable="true"][role="textbox"]');
            if (!el) throw new Error('Input not found');
            el.focus();
        }""")
        await asyncio.sleep(0.3)
        await self.page.keyboard.press("Meta+a")
        await asyncio.sleep(0.1)
        await self.page.evaluate("(text) => document.execCommand('insertText', false, text)", text)
        await asyncio.sleep(0.5)
        await self.page.keyboard.press("Enter")

    async def _extract_last_response(self) -> LLMResponse:
        """Extract response excluding the thinking/deliberation block."""
        try:
            # Prefer .standard-markdown inside the response (excludes thinking block)
            result = await self.page.evaluate("""() => {
                const responses = document.querySelectorAll('.font-claude-response');
                if (!responses.length) return null;
                const last = responses[responses.length - 1];
                // Try the markdown content first (excludes thinking block)
                const md = last.querySelector('.standard-markdown');
                if (md && md.innerText.trim().length > 0) {
                    return { text: md.innerText.trim(), html: md.innerHTML.trim() };
                }
                // Fallback to full response
                return { text: last.innerText.trim(), html: last.innerHTML.trim() };
            }""")
            if result:
                return LLMResponse(text=result["text"], html=result["html"])
            return LLMResponse(text="", html="")
        except Exception:
            return LLMResponse(text="", html="")
