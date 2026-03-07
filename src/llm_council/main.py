"""FastAPI app, WebSocket endpoint, serves UI."""

import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from llm_council.council import run_council
from llm_council.config import PROVIDERS

app = FastAPI(title="LLM Council")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text())


@app.get("/api/providers")
async def get_providers():
    return [
        {"name": p.name, "display_name": p.display_name}
        for p in PROVIDERS.values()
    ]


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)
        question = data["question"]
        providers = data.get("providers", ["chatgpt", "claude", "gemini"])
        chairman = data.get("chairman", "claude")

        # Validate
        for p in providers:
            if p not in PROVIDERS:
                await ws.send_text(json.dumps({
                    "type": "error", "provider": "council",
                    "message": f"Unknown provider: {p}",
                }))
                return

        if chairman not in providers:
            await ws.send_text(json.dumps({
                "type": "error", "provider": "council",
                "message": f"Chairman '{chairman}' must be one of the selected providers",
            }))
            return

        if len(providers) < 2:
            await ws.send_text(json.dumps({
                "type": "error", "provider": "council",
                "message": "Select at least 2 providers",
            }))
            return

        await run_council(question, providers, chairman, ws)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_text(json.dumps({
                "type": "error", "provider": "council",
                "message": str(e),
            }))
        except Exception:
            pass


import os

PORT = 9741
CDP_PORT = 9222
CHROME_DATA_DIR = os.path.expanduser("~/.llm-council-chrome")


def _cdp_is_available():
    """Check if Chrome CDP endpoint is actually responding (not just port open)."""
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2)
        return resp.status == 200
    except Exception:
        return False


def ensure_chrome_running():
    """Start a dedicated Chrome instance with remote debugging."""
    import subprocess
    import sys
    import time

    if _cdp_is_available():
        print(f"Chrome CDP already available on port {CDP_PORT}")
        return

    chrome_paths = {
        "darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "linux": "google-chrome",
    }
    chrome = chrome_paths.get(sys.platform)
    if not chrome:
        print(f"Please start Chrome manually with --remote-debugging-port={CDP_PORT} --user-data-dir={CHROME_DATA_DIR}")
        return

    print(f"Starting Chrome with remote debugging on port {CDP_PORT}...")
    print(f"Using profile directory: {CHROME_DATA_DIR}")
    subprocess.Popen(
        [chrome, f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={CHROME_DATA_DIR}",
         f"http://localhost:{PORT}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(15):
        time.sleep(1)
        if _cdp_is_available():
            print("Chrome CDP is ready")
            return
    print("Warning: Chrome CDP did not become available.")


def main():
    import uvicorn
    ensure_chrome_running()
    print(f"Starting LLM Council at http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
