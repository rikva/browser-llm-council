# LLM Council

Multiple LLMs (ChatGPT, Claude, Gemini) answer your question, peer-review each other's responses, then a chairman synthesizes a final answer. All through your browser — no API keys needed.

## Setup

**Requirements:** Python 3.11+, Google Chrome

```bash
# Install
cd /path/to/llm-council
pip install -e .
playwright install chromium
```

## Usage

```bash
python -m llm_council.main
```

This will:
1. Launch a dedicated Chrome window (separate profile at `~/.llm-council-chrome`)
2. Start the web server at **http://localhost:9741**
3. Open the Council UI in that Chrome window

**First time only:** Log into ChatGPT, Claude, and Gemini in the Council Chrome window. Your sessions persist across restarts.

Then type your question, pick which LLMs to include, choose a chairman, and hit **Convene Council**.

## How it works

1. **Stage 1 — Initial Responses:** Your question is sent to all selected LLMs in parallel
2. **Stage 2 — Peer Review:** Each LLM reviews the others' responses (anonymized)
3. **Stage 3 — Synthesis:** The chairman combines everything into one definitive answer

If any LLM fails (cookie banner, rate limit, etc.), you'll get a **Retry/Skip** button. Fix the issue in the browser tab and click Retry.

## Troubleshooting

- **Chrome won't connect:** Make sure no other Chrome instance is using port 9222. The Council uses its own Chrome profile so it can run alongside your normal browser.
- **LLM not responding:** Check the tab in the Council Chrome — you may need to dismiss a cookie banner, solve a CAPTCHA, or log in.
- **Selectors outdated:** LLM websites change their HTML frequently. Update selectors in `src/llm_council/config.py`.
