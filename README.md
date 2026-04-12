# Ear AI

Starter implementation for a pocket-mode Android voice assistant that wakes on "Dante" and routes LLM responses through a home computer running LM Studio.

## Project Layout
- `docs/` - architecture and implementation docs.
- `phone-app/` - Android app (foreground service + wake flow + WebSocket client + TTS).
- `home-server/` - FastAPI server that loads assistant rules and forwards prompts to LM Studio.

## Quick Start
1. Set up and run `home-server` first.
2. Start LM Studio local server (`/v1/chat/completions` compatible endpoint).
3. Build/install `phone-app` on your Android phone.
4. In the app, set your home server IP and tap Start.
5. Say "Dante", then your command.

## Important Notes
- This is a starter baseline, not production hardening.
- For reliability while screen is off, disable battery optimization for the app.
- For secure remote access outside home network, use Tailscale/WireGuard or TLS+auth.
