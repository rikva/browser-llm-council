"""Provider configuration: URLs, selectors, and constants."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    display_name: str
    new_chat_url: str
    input_selector: str
    message_selector: str
    streaming_check: str  # JS expression that returns true while still streaming
    submit_shortcut: str  # keyboard shortcut to submit


PROVIDERS: dict[str, ProviderConfig] = {
    "chatgpt": ProviderConfig(
        name="chatgpt",
        display_name="ChatGPT",
        new_chat_url="https://chatgpt.com/",
        input_selector="#prompt-textarea",
        message_selector='[data-message-author-role="assistant"]',
        streaming_check='document.querySelector("[data-testid=\\"stop-button\\"]") !== null || document.querySelector(".streaming-animation") !== null',
        submit_shortcut="Enter",
    ),
    "claude": ProviderConfig(
        name="claude",
        display_name="Claude",
        new_chat_url="https://claude.ai/new",
        input_selector='[contenteditable="true"].ProseMirror',
        message_selector=".font-claude-response",
        streaming_check="""(() => {
            const el = document.querySelector('[data-is-streaming]');
            return el ? el.getAttribute('data-is-streaming') === 'true' : false;
        })()""",
        submit_shortcut="Enter",
    ),
    "gemini": ProviderConfig(
        name="gemini",
        display_name="Gemini",
        new_chat_url="https://gemini.google.com/app",
        input_selector=".ql-editor",
        message_selector=".model-response-text",
        streaming_check="",  # uses text-stability polling
        submit_shortcut="Enter",
    ),
}

# Timeouts
PAGE_LOAD_TIMEOUT_MS = 15_000
RESPONSE_TIMEOUT_MS = 180_000  # 3 minutes max for LLM response
STABILITY_INTERVAL_S = 1.5  # seconds of unchanged text = done
STABILITY_CHECKS = 3  # number of consecutive stable checks needed
TYPE_DELAY_MS = 10  # delay between keystrokes for fallback typing
