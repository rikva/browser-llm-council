"""3-stage council orchestration and prompts."""

import asyncio
import json
import traceback
from fastapi import WebSocket

from llm_council.config import PROVIDERS
from llm_council.browser.manager import BrowserManager
from llm_council.browser.base import LLMResponse
from llm_council import storage
from llm_council.browser.chatgpt import ChatGPTPage
from llm_council.browser.claude import ClaudePage
from llm_council.browser.gemini import GeminiPage

PAGE_CLASSES = {
    "chatgpt": ChatGPTPage,
    "claude": ClaudePage,
    "gemini": GeminiPage,
}

STAGE1_PROMPT = (
    "You are participating in an LLM Council. Please provide your best, "
    "most thorough and accurate answer to the following question.\n\n"
    "Question: {question}"
)

STAGE2_PROMPT = (
    "You are a peer reviewer evaluating responses to this question:\n\n"
    '"{question}"\n\n'
    "{responses_block}\n\n"
    "Evaluate each response's strengths and weaknesses. Consider accuracy, "
    "completeness, clarity, and reasoning quality.\n\n"
    "Then provide:\n"
    "FINAL RANKING:\n"
    "1. [Best Response letter]\n"
    "2. [Next best]\n"
    "(and so on for all responses)"
)

STAGE3_PROMPT = (
    "You are the Chairman of an LLM Council. Multiple AI models have answered "
    "a question and peer-reviewed each other's responses. Your task is to "
    "synthesize all of this into a single, definitive answer.\n\n"
    'Original question: "{question}"\n\n'
    "{all_responses_and_reviews}\n\n"
    "Produce a comprehensive, well-structured answer that:\n"
    "- Incorporates the strongest points from all responses\n"
    "- Resolves any disagreements between responses\n"
    "- Corrects any errors identified in the peer reviews\n"
    "- Is clear, accurate, and thorough"
)

MAX_RETRIES = 3


async def _send_ws(ws: WebSocket, msg: dict):
    try:
        await ws.send_text(json.dumps(msg))
    except Exception:
        pass


async def _wait_for_retry(ws: WebSocket, provider: str, error_msg: str) -> bool:
    """Send error and wait for user to click retry or skip. Returns True if retry."""
    await _send_ws(ws, {
        "type": "provider_error",
        "provider": provider,
        "message": error_msg,
    })
    # Wait for client response
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=300)  # 5 min to respond
        data = json.loads(raw)
        return data.get("action") == "retry"
    except Exception:
        return False


async def _run_provider_with_retry(
    manager: BrowserManager,
    provider: str,
    stage: int,
    prompt: str,
    ws: WebSocket,
) -> LLMResponse | None:
    """Run a provider task with retry support. Returns LLMResponse or None."""
    for attempt in range(MAX_RETRIES):
        try:
            await _send_ws(ws, {
                "type": "provider_status", "provider": provider,
                "stage": stage, "status": "sending",
            })

            # Close any existing tab for this provider first
            await manager.close_provider_tab(provider)
            page = await manager.open_provider_tab(provider)
            llm_page = PAGE_CLASSES[provider](page)
            await llm_page.send_prompt(prompt)

            await _send_ws(ws, {
                "type": "provider_status", "provider": provider,
                "stage": stage, "status": "waiting",
            })

            async def on_partial(html):
                await _send_ws(ws, {
                    "type": "partial_response", "provider": provider,
                    "stage": stage, "html": html,
                })

            response = await llm_page.wait_for_response(callback=on_partial)

            await _send_ws(ws, {
                "type": "provider_status", "provider": provider,
                "stage": stage, "status": "done",
                "text": response.text, "html": response.html,
            })
            return response

        except Exception as e:
            error_msg = f"Stage {stage} error (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
            should_retry = await _wait_for_retry(ws, provider, error_msg)
            if not should_retry:
                return None

    return None


async def run_council(
    question: str,
    providers: list[str],
    chairman: str,
    ws: WebSocket,
):
    """Run the full 3-stage council flow."""
    manager = BrowserManager()

    try:
        # Verify CDP is reachable
        import urllib.request
        try:
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3)
        except Exception:
            await _send_ws(ws, {
                "type": "error", "provider": "council",
                "message": "Chrome CDP not available on port 9222. Restart the server to auto-launch Chrome, or start Chrome manually with: --remote-debugging-port=9222",
            })
            return

        await _send_ws(ws, {"type": "status", "message": "Connecting to browser..."})
        await manager.connect()

        # Create session in storage
        session_id = storage.create_session(question, providers, chairman)
        await _send_ws(ws, {"type": "session_id", "session_id": session_id})

        # ── Stage 1: Initial Responses ──
        await _send_ws(ws, {"type": "stage", "stage": 1, "status": "starting"})

        responses: dict[str, LLMResponse] = {}
        prompt = STAGE1_PROMPT.format(question=question)

        # Run all providers in parallel
        async def stage1_task(p):
            result = await _run_provider_with_retry(manager, p, 1, prompt, ws)
            if result is not None:
                responses[p] = result

        await asyncio.gather(*[stage1_task(p) for p in providers])

        # All providers must succeed
        failed = [p for p in providers if p not in responses]
        if failed:
            await _send_ws(ws, {
                "type": "error", "provider": "council",
                "message": f"Council stopped: {', '.join(PROVIDERS[p].display_name for p in failed)} failed in Stage 1. Fix the issue and try again.",
            })
            return

        await _send_ws(ws, {"type": "stage", "stage": 1, "status": "complete"})

        # Save stage 1 responses
        for p, resp in responses.items():
            storage.save_response(session_id, p, 1, resp.text, resp.html)

        # Close stage 1 tabs
        for p in providers:
            await manager.close_provider_tab(p)

        # ── Stage 2: Peer Review ──
        await _send_ws(ws, {"type": "stage", "stage": 2, "status": "starting"})

        provider_order = list(responses.keys())
        letter_map = {p: chr(65 + i) for i, p in enumerate(provider_order)}

        reviews: dict[str, LLMResponse] = {}

        async def stage2_task(reviewer):
            other_providers = [p for p in provider_order if p != reviewer]
            parts = [f"Response {letter_map[p]}:\n{responses[p].text}" for p in other_providers]
            responses_block = "\n\n---\n\n".join(parts)
            review_prompt = STAGE2_PROMPT.format(
                question=question,
                responses_block=responses_block,
            )
            result = await _run_provider_with_retry(manager, reviewer, 2, review_prompt, ws)
            if result is not None:
                reviews[reviewer] = result

        await asyncio.gather(*[stage2_task(p) for p in provider_order])

        failed = [p for p in provider_order if p not in reviews]
        if failed:
            await _send_ws(ws, {
                "type": "error", "provider": "council",
                "message": f"Council stopped: {', '.join(PROVIDERS[p].display_name for p in failed)} failed in Stage 2. Fix the issue and try again.",
            })
            return

        await _send_ws(ws, {"type": "stage", "stage": 2, "status": "complete"})

        # Save stage 2 reviews
        for p, rev in reviews.items():
            storage.save_response(session_id, p, 2, rev.text, rev.html)

        # Close stage 2 tabs
        for p in provider_order:
            await manager.close_provider_tab(p)

        # ── Stage 3: Chairman Synthesis ──
        await _send_ws(ws, {"type": "stage", "stage": 3, "status": "starting"})

        parts = []
        for p in provider_order:
            display = PROVIDERS[p].display_name
            parts.append(f"=== Response from {display} ===\n{responses[p].text}")
        for p in provider_order:
            if p in reviews:
                display = PROVIDERS[p].display_name
                parts.append(f"=== Peer Review by {display} ===\n{reviews[p].text}")

        all_context = "\n\n".join(parts)
        synthesis_prompt = STAGE3_PROMPT.format(
            question=question,
            all_responses_and_reviews=all_context,
        )

        final = await _run_provider_with_retry(manager, chairman, 3, synthesis_prompt, ws)
        if final is None:
            await _send_ws(ws, {
                "type": "error", "provider": "council",
                "message": "Chairman synthesis failed.",
            })
            return

        storage.save_synthesis(session_id, final.text, final.html)

        await _send_ws(ws, {"type": "final", "text": final.text, "html": final.html, "chairman": chairman})
        await _send_ws(ws, {"type": "stage", "stage": 3, "status": "complete"})

    except Exception as e:
        await _send_ws(ws, {
            "type": "error", "provider": "council",
            "message": f"Council error: {e}\n{traceback.format_exc()}",
        })
    finally:
        await manager.disconnect()
