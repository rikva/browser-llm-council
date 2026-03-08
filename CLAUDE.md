# LLM Council

Browser-automated multi-LLM deliberation tool. No API keys — uses Playwright CDP to control ChatGPT, Claude, and Gemini through the user's browser sessions.

## Architecture

```
src/llm_council/
├── main.py          # FastAPI server, WebSocket endpoint, Chrome auto-start
├── config.py        # CSS selectors, URLs, timeouts per provider (FRAGILE - update when UIs change)
├── council.py       # 3-stage orchestration: responses → peer review → synthesis
├── storage.py       # SQLite history at ~/.llm-council-history.db
├── browser/
│   ├── manager.py   # CDP connection, tab lifecycle
│   ├── base.py      # LLMPage base: send prompt, wait for response, extract text+html
│   ├── chatgpt.py   # ChatGPT overrides
│   ├── claude.py    # Claude overrides (excludes thinking block from responses)
│   └── gemini.py    # Gemini overrides
└── static/
    └── index.html   # Single-page UI (pure HTML/CSS/JS, no framework)
```

## Key decisions

- **`document.execCommand('insertText')`** for input — clipboard paste races when tabs run in parallel; Gemini blocks `innerHTML` via Trusted Types
- **Separate Chrome profile** (`~/.llm-council-chrome`) — Chrome requires non-default `--user-data-dir` for CDP; also allows running alongside normal Chrome
- **Selectors are fragile** — LLM web UIs change frequently. When something breaks, inspect the DOM and update `config.py`. ChatGPT streaming uses `[data-testid="stop-button"]`, Claude uses `[data-is-streaming]`, Gemini uses text-stability polling
- **Claude thinking blocks** — `.font-claude-response` includes the "Deliberated on..." summary; `claude.py` extracts from `.standard-markdown` to skip it
- **Responses stored as both text and HTML** — text for prompts/stability checks, HTML for rich display in UI

## Running

```bash
pip install -e . && playwright install chromium
python -m llm_council.main  # auto-starts Chrome, serves at localhost:9741
```

## Common issues

- **ECONNREFUSED on 9222**: Chrome running without CDP. The server auto-launches a separate Chrome instance; if it can't, quit all Chrome instances and restart
- **Selector timeout**: UI changed. Open the failing provider's tab, inspect the DOM, update `config.py`
- **Clipboard race**: Should not happen (we use `execCommand` now), but if text appears in wrong tab, check the `send_prompt` methods
- **Cookie banners/CAPTCHAs**: Use retry button in UI, fix manually in the browser tab

## Code style

- Python 3.11+, no type stubs needed
- Async everywhere (Playwright + FastAPI)
- Provider-specific code goes in `browser/<provider>.py`, override `send_prompt` and/or `_extract_last_response`
- UI is a single HTML file — keep it that way
