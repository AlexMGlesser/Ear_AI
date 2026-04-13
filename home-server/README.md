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

## Agent Sandbox (Isolated File Ops)
- The server now includes an isolated agent sandbox API for safe file operations.
- Each session is restricted to its own folder under `sandboxes/`.
- See `AGENT_SANDBOX.md` for endpoint details and examples.
- Includes autonomous planner endpoint: `POST /agent/sessions/{session_id}/run` for multi-step file tasks.

## Desktop Control App
- A local GUI is available at `../desktop-app/control_center.py`.
- It can launch LM Studio, start/stop server, inspect logs, set sandbox root path, and execute autonomous agent goals.
- Setup and run instructions: `../desktop-app/README.md`.

## Conversation Memory
- The server now keeps per-session history using `session_id` from the phone app.
- Depth is controlled by `SESSION_HISTORY_MESSAGES` in `.env`.
- If you stop/start the phone service, a new session id is created and memory resets.
- New session starts are logged to `logs/conversation_sessions.log` with timestamp, session id, and first utterance.

## Read-Only Web Lookup
- Optional internet lookup can be enabled to improve factual/current answers.
- This mode is read-only: it performs HTTP GET lookups and returns summaries only.
- It does not perform purchases, form submissions, or other write actions.
- Spoken replies are concise summaries; full source URLs/snippets are logged to `logs/web_lookup.log`.

Enable in `.env`:
- `WEB_LOOKUP_ENABLED=true`
- `WEB_LOOKUP_TIMEOUT_SECONDS=10`
- `WEB_LOOKUP_MAX_RESULTS=4`

## Self-Play Quality Loop
- You can run a recursive self-play evaluator that simulates user prompts against the live WebSocket assistant endpoint.
- Each iteration asks test questions, scores human-like quality, checks factual overlap against retrieved web evidence, and then adjusts assistant rules.
- By default it applies the best discovered directives back into `config/assistant_rules.md`.

Run from project root:
```powershell
.\home-server\.venv\Scripts\python.exe .\dev-tools\self-play\self_play_quality_loop.py --iterations 6 --target 0.88
```

If you want report-only mode without changing active rules:
```powershell
.\home-server\.venv\Scripts\python.exe .\dev-tools\self-play\self_play_quality_loop.py --iterations 6 --target 0.88 --no-apply
```

Optional explicit endpoint override:
```powershell
.\home-server\.venv\Scripts\python.exe .\dev-tools\self-play\self_play_quality_loop.py --ws-url ws://127.0.0.1:8765/ws/assistant
```

Outputs:
- `logs/self_play_last_report.json`
- `config/assistant_rules.tuned.md`
- Optional update to `config/assistant_rules.md` when `--apply` is used.

Edit scenarios here:
- `../dev-tools/self-play/self_play_scenarios.json`

## If Replies Are Always Generic
- If you keep hearing "I do not have a response right now", verify:
	- `LM_STUDIO_MODEL` exactly matches a currently loaded model in LM Studio.
	- LM Studio local server is enabled and reachable at `LM_STUDIO_BASE_URL`.
	- Your model can answer normal chat requests through LM Studio UI/API.
