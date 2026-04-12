# Ear AI Home Server

FastAPI WebSocket server that receives user utterances from the Android app, applies response rules, and queries LM Studio.

## Requirements
- Python 3.11+
- LM Studio running with local server enabled

## Setup (PowerShell)
```powershell
cd d:\Code\Ear_AI\home-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` values:
- `LM_STUDIO_BASE_URL` (default `http://127.0.0.1:1234`)
- `LM_STUDIO_MODEL` to match your loaded model name
- optional `AUTH_TOKEN`

## Run
```powershell
cd d:\Code\Ear_AI\home-server
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```

Health check:
- `http://<server-ip>:8765/health`

WebSocket endpoint:
- `ws://<server-ip>:8765/ws/assistant`

## Assistant Rules
Edit `config/assistant_rules.md` to control style and verbosity.

## Conversation Memory
- The server now keeps per-session history using `session_id` from the phone app.
- Depth is controlled by `SESSION_HISTORY_MESSAGES` in `.env`.
- If you stop/start the phone service, a new session id is created and memory resets.

## Read-Only Web Lookup
- Optional internet lookup can be enabled to improve factual/current answers.
- This mode is read-only: it performs HTTP GET lookups and returns summaries only.
- It does not perform purchases, form submissions, or other write actions.

Enable in `.env`:
- `WEB_LOOKUP_ENABLED=true`
- `WEB_LOOKUP_TIMEOUT_SECONDS=10`
- `WEB_LOOKUP_MAX_RESULTS=4`

## If Replies Are Always Generic
- If you keep hearing "I do not have a response right now", verify:
	- `LM_STUDIO_MODEL` exactly matches a currently loaded model in LM Studio.
	- LM Studio local server is enabled and reachable at `LM_STUDIO_BASE_URL`.
	- Your model can answer normal chat requests through LM Studio UI/API.
