# Ear AI Home Server Architecture

## Overview
The Ear AI Home Server is a FastAPI-based backend that powers voice assistant functionality on mobile earbuds. It handles natural language processing, music management, Spotify integration, and maintains conversation history.

## Technology Stack

### Core Framework
- **FastAPI** (0.111.0) - Modern Python web framework for building APIs
- **Uvicorn** (0.30.1) - ASGI server for production deployment
- **WebSockets** - Real-time bidirectional communication with mobile app

### AI & Language Processing
- **LM Studio** - Local LLM inference (via HTTP endpoint)
- **Spotipy** (2.22.1) - Spotify Web API client

### Data & Storage
- **Pydantic** (2.8.2) - Data validation and settings management
- **Python-dotenv** (1.0.1) - Environment configuration

### Additional Libraries
- **httpx** (0.27.0) - Async HTTP client for web lookups
- **python-multipart** - Multipart form data parsing

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Mobile App (Android)                     │
│                  WebSocket Connection                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                    WebSocket: /ws/assistant
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ear AI Home Server                        │
│                     (FastAPI Backend)                        │
├─────────────────────────────────────────────────────────────┤
│ Request Processing Layer                                    │
│ ├─ Input Validation (Pydantic models)                      │
│ ├─ Authentication (Bearer token)                           │
│ └─ Error Handling & Responses                              │
├─────────────────────────────────────────────────────────────┤
│ Core Processing Layer                                       │
│ ├─ Assistant Engine                                        │
│ │  ├─ Direct lookup (meta questions, time)                │
│ │  ├─ Web lookup (optional internet search)               │
│ │  └─ LM Studio integration (LLM inference)               │
│ ├─ Session Memory Management                              │
│ ├─ Rules Engine (assistant behavior)                      │
│ └─ Music Management                                        │
├─────────────────────────────────────────────────────────────┤
│ Integration Layer                                           │
│ ├─ LM Studio API Client                                    │
│ ├─ Spotify Web API Client                                  │
│ ├─ Music Player State Manager                              │
│ └─ Web Lookup Service                                      │
├─────────────────────────────────────────────────────────────┤
│ Configuration & Utilities                                   │
│ ├─ Environment Settings (.env)                             │
│ ├─ Logging & Session Tracking                              │
│ └─ Rules & Behavioral Configuration                        │
└─────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
   LM Studio Server    Spotify API         Local Music Folder
   (Port 1234)         (api.spotify.com)   (E:\Music)
```

## Core Components

### 1. **Main Application** (`app/main.py`)
The FastAPI app instance and route definitions.

#### Endpoints Available:

**Health & Status**
- `GET /health` - Server health check
- `GET /` - Root endpoint with available features

**Assistant Communication**
- `WebSocket /ws/assistant` - Main WebSocket for voice chat
  - Accepts JSON messages with session ID, text, and message type
  - Handles conversation history, web lookups, and LLM replies
  - Returns structured assistant responses with timestamps

**Music Management** (Local E:\Music folder)
- `GET /music/playlist` - List all available songs
- `GET /music/status` - Get current playback state
- `POST /music/play` - Start playing a song (by index)
- `POST /music/pause` - Pause current song
- `POST /music/resume` - Resume paused song
- `POST /music/stop` - Stop playback
- `POST /music/next` - Skip to next song
- `POST /music/previous` - Go to previous song
- `POST /music/random` - Play random song
- `POST /music/volume` - Set volume (0.0-1.0)

**Spotify Integration**
- `GET /spotify/status` - Check if Spotify is configured
- `POST /spotify/play?query=...` - Search and play on Spotify
- `GET /spotify/featured` - Get featured playlists
- `GET /spotify/new-releases` - Get new releases
- `GET /spotify/recommendations?genres=...` - Get recommendations

**File System Manager** (Currently Disabled - WIP)
- Full CRUD operations for file management in sandboxed sessions
- Goal execution for agent tasks

### 2. **LM Studio Client** (`app/lmstudio_client.py`)
Manages communication with local LLM via LM Studio.

**Methods**
- `generate_reply(text, system_prompt, history)` - Generate AI response
  - Sends user input with system prompt and conversation history
  - Returns text completion from local LLM
  - Configurable timeout (default 45s)

### 3. **Rules Engine** (`app/rules_engine.py`)
Loads and manages assistant behavior rules.

**Methods**
- `load_rules_text()` - Read rules from `config/assistant_rules.md`
- `build_system_prompt()` - Construct system prompt with rules

**Current Rules Cover**
- Response style (concise, natural language)
- Music control commands
- Spotify playback commands
- Web lookup policies
- Output constraints (no markdown, no disclaimers)

### 4. **Music Player** (`app/music_player.py`)
State and playlist management for local music library.

**Class: MusicPlayer**
- `__init__(music_folder)` - Initialize with folder path (default: E:\Music)
- `get_playlist()` - List all supported audio files
- `play(song_index)` - Start playing a song
- `pause()` / `resume()` / `stop()` - Playback controls
- `next_song()` / `previous_song()` - Navigation
- `set_volume(level)` - Volume control (0.0-1.0)
- `get_status()` - Return current player state

**Supported Formats**: `.mp3`, `.flac`, `.wav`, `.ogg`, `.m4a`, `.aac`

**State Tracking**
```python
PlayerState:
  - is_playing: bool
  - is_paused: bool
  - current_song: Song object
  - current_position_ms: int
  - volume: float (0.0-1.0)
```

### 5. **Spotify Client** (`app/spotify_client.py`)
Spotify Web API integration using Client Credentials OAuth flow.

**Class: SpotifyClient**
- `search_track(query)` - Search for a track
- `search_playlist(query)` - Search for a playlist
- `get_featured_playlists()` - Retrieve featured content
- `get_new_releases()` - Get new albums
- `get_recommendations(seed_tracks, seed_genres)` - Recommendations engine
- `format_for_playback(item)` - Format Spotify item for mobile app

**Authentication**
- Uses Client Credentials flow (server-to-server)
- No user login required for basic operations
- Credentials: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` in `.env`

### 6. **Session Memory** (`app/session_memory.py`)
Manages conversation history per session.

**Class: SessionMemoryStore**
- `get_history(session_id)` - Retrieve conversation history
- `append_turn(session_id, user_text, assistant_text)` - Add exchange
- `max_messages` - Configuration for history retention

### 7. **Web Lookup Service** (`app/web_lookup.py`)
Optional internet search to verify facts and enhance responses.

**Methods**
- `direct_time_response(text, current_time)` - Answer time-related queries
- `direct_lookup_meta_response(text)` - Answer meta questions (what is AI, etc.)
- `should_lookup(text)` - Determine if web search is needed
- `needs_lookup_clarification(text)` - Ask clarifying questions
- `build_web_context(text)` - Fetch and parse web results
- `looks_generic_or_unverified(text)` - Check response quality

### 8. **Configuration** (`app/config.py`)
Environment and settings management.

**Settings Class** (loaded from `.env`)
```
Core:
  - host, port (default: 0.0.0.0:8765)
  - auth_token (Bearer token for auth)

LM Studio:
  - lm_studio_base_url (default: http://127.0.0.1:1234)
  - lm_studio_model (model identifier)
  - request_timeout_seconds

Session:
  - session_history_messages (default: 12)

Web Lookup:
  - web_lookup_enabled
  - web_lookup_timeout_seconds
  - web_lookup_max_results
  - web_lookup_page_count

Spotify:
  - spotify_client_id
  - spotify_client_secret
  - spotify_redirect_uri

File System (WIP):
  - agent_sandbox_root
  - agent_max_file_bytes
```

## Data Models

### User Utterance (Input)
```json
{
  "type": "user_utterance",
  "session_id": "session-123",
  "text": "play music",
  "timestamp": "2026-04-13T10:30:00Z"
}
```

### Assistant Response (Output)
```json
{
  "session_id": "session-123",
  "text": "Playing music",
  "timestamp": "2026-04-13T10:30:01Z"
}
```

### Music Status
```json
{
  "is_playing": true,
  "is_paused": false,
  "current_song": {
    "filename": "song.mp3",
    "path": "E:\\Music\\song.mp3"
  },
  "current_position_ms": 5000,
  "volume": 0.8,
  "playlist_size": 150,
  "current_index": 5
}
```

### Spotify Playback Info
```json
{
  "ok": true,
  "uri": "spotify:track:xxx",
  "name": "Song Title",
  "artist": "Artist Name",
  "url": "https://open.spotify.com/track/xxx",
  "type": "track",
  "message": "Playing: Song Title by Artist Name"
}
```

## Processing Flow

### WebSocket Message Processing
```
1. Client connects to /ws/assistant
2. Server authenticates (Bearer token check)
3. Client sends JSON utterance
4. Server processes:
   a. Parse & validate input
   b. Check for direct responses (time, meta questions)
   c. Determine if web lookup needed
   d. Build system prompt with rules + context
   e. Call LM Studio for inference
   f. Validate response quality
   g. Store in session memory
5. Send structured response back
```

### Assistant Response Generation
```
System Prompt = [Rules] + [Context] + [Web Lookup Results] + [Time Info]
                    ↓
           LM Studio Inference
                    ↓
         Assistant Reply Text
                    ↓
      Session Memory + Quality Check
                    ↓
      JSON Response to Mobile App
```

## Authentication & Security

- **Bearer Token Auth** - Optional token in Authorization header
- **Session Isolation** - Each session maintains separate history
- **Error Handling** - Graceful failure with informative error messages
- **Input Validation** - Pydantic models validate all inputs
- **CORS/WebSocket Security** - Built-in Starlette/FastAPI protections

## Deployment

**Running the Server**
```bash
# Activate virtual environment
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# Install dependencies
pip install -r home-server/requirements.txt

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8765

# For development with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8765
```

**Configuration**
- Copy `.env.example` to `.env`
- Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`
- Set `LM_STUDIO_BASE_URL` and `LM_STUDIO_MODEL`
- Adjust other settings as needed

## Future Enhancements

- [ ] File system manager (desktop app integration)
- [ ] Voice activity detection optimization
- [ ] Local model switching
- [ ] Advanced caching for Spotify results
- [ ] User authentication (OAuth)
- [ ] Multi-user support
- [ ] Analytics and telemetry
- [ ] Rate limiting and throttling

## Dependencies Summary

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.111.0 | Web framework |
| uvicorn | 0.30.1 | ASGI server |
| httpx | 0.27.0 | HTTP client |
| pydantic | 2.8.2 | Data validation |
| pydantic-settings | 2.3.4 | Config management |
| python-dotenv | 1.0.1 | Environment variables |
| spotipy | 2.22.1 | Spotify API |
