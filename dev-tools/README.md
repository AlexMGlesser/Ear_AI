# Ear AI Dev Tools

This folder contains non-production setup and testing utilities.

## Included Tools
- `start_ear_ai_server.ps1` - initializes venv/dependencies and launches `home-server`.
- `run_server.ps1` - quick uvicorn launcher for development.
- `check_internet_lookup.ps1` - verifies lookup fetching is returning context.
- `tools_ws_probe.py` - sends a direct WebSocket test message to the assistant server.
- `self-play/self_play_quality_loop.py` - recursive quality evaluator/tuner for answer quality.
- `self-play/self_play_scenarios.json` - editable test scenarios for self-play loop.

These tools can be removed for final production packaging if desired.
# Ear AI Dev Tools

This folder contains non-production setup and testing utilities.

## Included Tools
- `start_ear_ai_server.ps1` - initializes venv/dependencies and launches `home-server`.
- `run_server.ps1` - quick uvicorn launcher for development.
- `check_internet_lookup.ps1` - verifies lookup fetching is returning context.
- `tools_ws_probe.py` - sends a direct WebSocket test message to the assistant server.
- `self-play/self_play_quality_loop.py` - recursive quality evaluator/tuner for answer quality.
- `self-play/self_play_scenarios.json` - editable test scenarios for self-play loop.

These tools can be removed for final production packaging if desired.
