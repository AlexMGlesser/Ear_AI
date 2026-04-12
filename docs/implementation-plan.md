# Implementation Plan (Starter)

## Phase 1 - Working Skeleton
- Android app with minimal UI and foreground service controls.
- Home server with WebSocket assistant endpoint and LM Studio bridge.
- Rules document loaded on each request.

## Phase 2 - Audio Intelligence
- Integrate robust wake-word detection for "Dante".
- Add VAD and better speech capture handling.
- Add better earbud routing controls and media session behavior.

### Phase 2 Status (in progress)
- Added wake/query state machine for clearer behavior between wake detection and command capture.
- Added query timeout window after wake phrase to avoid staying armed indefinitely.
- Added basic RMS gate to reduce accidental low-volume triggers in pocket mode.
- Added explicit voice-session audio routing/focus controller for earbud-first routing behavior.

### Remaining for full Phase 2
- Integrate dedicated offline wake-word engine (Porcupine/openWakeWord path).
- Replace RMS gate with proper VAD implementation.
- Add media session controls and improved Bluetooth route diagnostics.

## Phase 3 - Reliability and Security
- Add auth token and TLS or private VPN requirement.
- Add durable reconnect and offline queue behavior.
- Add structured logs and diagnostics UI.

## Deliverables Created In This Pass
- docs/system-design.md
- phone-app/* (Android starter project)
- home-server/* (FastAPI starter)
