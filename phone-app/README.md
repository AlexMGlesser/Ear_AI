# Ear AI Phone App

Android starter app for pocket-mode voice assistant usage.

## Features in this starter
- Minimal UI: computer/profile selection, host/port, Start, Stop.
- Foreground service for screen-off behavior.
- Wake phrase gate using "Dante" detection in speech recognition results.
- WebSocket client to home server.
- TTS playback of assistant responses.

## Build
1. Open `d:\Code\Ear_AI\phone-app` in Android Studio.
2. Let Gradle sync and install required SDK versions.
3. Connect Android phone with developer mode enabled.
4. Run app on device.

## Usage
1. Enter server host and port (`8765` by default).
2. Choose a voice in the `Voice` dropdown (or keep `Auto`).
3. Tap Start. If the service is already running, tap Stop then Start to apply voice changes immediately.
4. Say `Dante` then speak your request.
5. Tap Stop to end background listening.

## Offline Audio Path (recommended)
- Phase 2 now supports Vosk-based offline speech pipeline as primary mode.
- Follow setup in `OFFLINE_SETUP.md`.
- Fallback is now OFF by default to prevent recognizer tone loops.
- You can opt into fallback using the in-app switch `Allow online fallback if offline model missing`.

## Diagnostics Panel
- Main screen now includes live diagnostics for:
	- active engine
	- listening state
	- wake hit count
	- queries sent count
	- last transcript confidence
	- last round-trip latency to server
	- last error

## LAN Transport Note
- Current home-server transport uses `ws://` (cleartext) on local network.
- Android manifest/network security is configured to permit LAN cleartext for this starter.
- For hardened deployment, switch to `wss://` and restrict cleartext domains.

## Limitations (current starter)
- Wake-word detection currently uses phrase matching over local transcripts; a dedicated wake-word detector remains the next upgrade.
- Vendor battery optimizations can still stop background service unless whitelisted.
