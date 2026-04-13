from datetime import datetime, timezone
import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from .agent_models import (
    AgentAppendFileRequest,
    AgentDeletePathRequest,
    AgentPathRequest,
    AgentReadFileRequest,
    AgentRunGoalRequest,
    AgentSessionCreateRequest,
    AgentSessionResponse,
    AgentWriteFileRequest,
    AgentMovePathRequest,
)
from .agent_executor import AgentExecutor
from .agent_sandbox import AgentSandboxManager
from .config import settings
from .lmstudio_client import generate_reply
from .models import AssistantResponse, ErrorResponse, UserUtterance
from .music_player import get_music_player
from .spotify_client import get_spotify_client
from .rules_engine import build_system_prompt
from .session_memory import SessionMemoryStore
from .session_logging import log_session_started
from .web_lookup import (
    build_web_context,
    direct_lookup_meta_response,
    direct_time_response,
    fallback_answer_from_web_context,
    log_lookup_result,
    looks_generic_or_unverified,
    needs_lookup_clarification,
    should_lookup,
)

app = FastAPI(title="Ear AI Home Server", version="0.1.0")
memory_store = SessionMemoryStore(max_messages=settings.session_history_messages)
session_lookup_status: dict[str, str] = {}
# agent_sandbox = AgentSandboxManager()
# agent_executor = AgentExecutor(agent_sandbox)
# ^ File system manager disabled for now (WIP for desktop app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ============================================================================
# FILE SYSTEM MANAGER ENDPOINTS - DISABLED (WIP for desktop app)
# ============================================================================
# @app.post("/agent/sessions", response_model=AgentSessionResponse)
# async def create_agent_session(payload: AgentSessionCreateRequest) -> AgentSessionResponse:
#     session = agent_sandbox.create_session(payload.label)
#     return AgentSessionResponse(...)
# 
# @app.get("/agent/sessions/{session_id}", response_model=AgentSessionResponse)
# async def get_agent_session(session_id: str) -> AgentSessionResponse: ...
# 
# @app.post("/agent/sessions/{session_id}/list") ...
# @app.post("/agent/sessions/{session_id}/read") ...
# @app.post("/agent/sessions/{session_id}/write") ...
# @app.post("/agent/sessions/{session_id}/append") ...
# @app.post("/agent/sessions/{session_id}/mkdir") ...
# @app.post("/agent/sessions/{session_id}/move") ...
# @app.post("/agent/sessions/{session_id}/delete") ...
# @app.post("/agent/sessions/{session_id}/run") ...
# ============================================================================


@app.websocket("/ws/assistant")
async def assistant_ws(websocket: WebSocket) -> None:
    auth_header = websocket.headers.get("authorization", "")
    if settings.auth_token and auth_header != f"Bearer {settings.auth_token}":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                utterance = UserUtterance(**payload)
            except Exception:
                await websocket.send_text(ErrorResponse(message="Invalid request payload").model_dump_json())
                continue

            if utterance.type != "user_utterance":
                await websocket.send_text(ErrorResponse(message="Unsupported message type").model_dump_json())
                continue

            try:
                now_utc = datetime.now(timezone.utc)
                system_prompt = (
                    f"{build_system_prompt()}\n\n"
                    f"Current UTC date/time: {now_utc.isoformat()}\n"
                    "Use this current date/time for any time-sensitive responses."
                )
                history = memory_store.get_history(utterance.session_id)
                if not history:
                    log_session_started(utterance.session_id, utterance.text)

                web_context = ""
                lookup_used = False

                meta_response = direct_lookup_meta_response(utterance.text)
                if meta_response:
                    reply_text = meta_response
                    memory_store.append_turn(utterance.session_id, utterance.text, reply_text)
                    response = AssistantResponse(
                        session_id=utterance.session_id,
                        text=reply_text,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await websocket.send_text(response.model_dump_json())
                    continue

                time_response = direct_time_response(utterance.text, now_utc.isoformat())
                if time_response:
                    reply_text = time_response
                    memory_store.append_turn(utterance.session_id, utterance.text, reply_text)
                    response = AssistantResponse(
                        session_id=utterance.session_id,
                        text=reply_text,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await websocket.send_text(response.model_dump_json())
                    continue

                lookup_requested = should_lookup(utterance.text)
                clarification = needs_lookup_clarification(utterance.text) if lookup_requested else ""

                if clarification:
                    reply_text = clarification
                    memory_store.append_turn(utterance.session_id, utterance.text, reply_text)
                    session_lookup_status[utterance.session_id] = "not_used"
                    response = AssistantResponse(
                        session_id=utterance.session_id,
                        text=reply_text,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await websocket.send_text(response.model_dump_json())
                    continue

                if lookup_requested:
                    web_context = await build_web_context(utterance.text)
                    lookup_used = bool(web_context.strip())

                if lookup_requested and not lookup_used:
                    reply_text = "I could not retrieve internet results right now, so I cannot verify that yet."
                    memory_store.append_turn(utterance.session_id, utterance.text, reply_text)
                    session_lookup_status[utterance.session_id] = "not_used"
                    response = AssistantResponse(
                        session_id=utterance.session_id,
                        text=reply_text,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await websocket.send_text(response.model_dump_json())
                    continue

                if lookup_requested and lookup_used and settings.web_lookup_direct_response:
                    log_lookup_result(utterance.text, web_context)
                    reply_text = fallback_answer_from_web_context(web_context)
                    memory_store.append_turn(utterance.session_id, utterance.text, reply_text)
                    session_lookup_status[utterance.session_id] = "used"
                    response = AssistantResponse(
                        session_id=utterance.session_id,
                        text=reply_text,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await websocket.send_text(response.model_dump_json())
                    continue

                if web_context:
                    system_prompt = f"{system_prompt}\n\n{web_context}"

                last_status = session_lookup_status.get(utterance.session_id, "none")
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "Tool usage policy:\n"
                    "- You may use read-only web lookup notes when provided in the prompt.\n"
                    "- If asked whether you checked the internet, answer truthfully based on this status.\n"
                    f"- Web lookup status for current turn: {'used' if lookup_used else 'not_used'}.\n"
                    f"- Web lookup status for previous turn: {last_status}.\n"
                    "- When web lookup notes are present, include at least one concrete detail (date, number, or named source).\n"
                    "- Avoid generic summaries when concrete details are available."
                )

                reply_text = await generate_reply(utterance.text, system_prompt, history)
                if lookup_used and looks_generic_or_unverified(reply_text):
                    log_lookup_result(utterance.text, web_context)
                    reply_text = fallback_answer_from_web_context(web_context)
                memory_store.append_turn(utterance.session_id, utterance.text, reply_text)
                session_lookup_status[utterance.session_id] = "used" if lookup_used else "not_used"
                response = AssistantResponse(
                    session_id=utterance.session_id,
                    text=reply_text,
                    timestamp=datetime.now(timezone.utc),
                )
                await websocket.send_text(response.model_dump_json())
            except Exception as ex:
                await websocket.send_text(
                    ErrorResponse(message=f"LM Studio request failed: {ex}").model_dump_json()
                )

    except WebSocketDisconnect:
        return


# Music Player Endpoints
@app.get("/music/playlist")
async def get_playlist() -> JSONResponse:
    """Get the list of available songs."""
    player = get_music_player()
    playlist = player.get_playlist()
    return JSONResponse({"ok": True, "playlist": playlist, "count": len(playlist)})


@app.get("/music/status")
async def get_music_status() -> JSONResponse:
    """Get current music player status."""
    player = get_music_player()
    status = player.get_status()
    return JSONResponse({"ok": True, **status})


@app.post("/music/play")
async def play_music(song_index: int = -1) -> JSONResponse:
    """Play a song. If song_index is -1, plays current or first song."""
    player = get_music_player()
    if song_index >= 0:
        result = player.play(song_index)
    else:
        result = player.play()
    return JSONResponse(result)


@app.post("/music/pause")
async def pause_music() -> JSONResponse:
    """Pause the currently playing music."""
    player = get_music_player()
    result = player.pause()
    return JSONResponse(result)


@app.post("/music/resume")
async def resume_music() -> JSONResponse:
    """Resume paused music."""
    player = get_music_player()
    result = player.resume()
    return JSONResponse(result)


@app.post("/music/stop")
async def stop_music() -> JSONResponse:
    """Stop the music player."""
    player = get_music_player()
    result = player.stop()
    return JSONResponse(result)


@app.post("/music/next")
async def next_song() -> JSONResponse:
    """Skip to next song."""
    player = get_music_player()
    result = player.next_song()
    return JSONResponse(result)


@app.post("/music/previous")
async def previous_song() -> JSONResponse:
    """Go to previous song."""
    player = get_music_player()
    result = player.previous_song()
    return JSONResponse(result)


@app.post("/music/random")
async def play_random_song() -> JSONResponse:
    """Play a random song from the playlist."""
    player = get_music_player()
    result = player.play_random()
    return JSONResponse(result)


@app.post("/music/volume")
async def set_volume(level: float = 0.5) -> JSONResponse:
    """Set volume level (0.0 to 1.0)."""
    if not 0.0 <= level <= 1.0:
        return JSONResponse({"ok": False, "message": "Volume must be between 0.0 and 1.0"})
    player = get_music_player()
    result = player.set_volume(level)
    return JSONResponse(result)


# Spotify Endpoints
@app.get("/spotify/status")
async def spotify_status() -> JSONResponse:
    """Check if Spotify is configured."""
    client = get_spotify_client()
    if not client:
        return JSONResponse({"ok": False, "message": "Spotify not configured"})
    return JSONResponse({"ok": True, "message": "Spotify ready"})


@app.post("/spotify/play")
async def spotify_play(query: str) -> JSONResponse:
    """Search for a track or playlist and return playback URI."""
    client = get_spotify_client()
    if not client:
        return JSONResponse({"ok": False, "message": "Spotify not configured"})
    
    # Try playlist first, then track
    playlist = client.search_playlist(query)
    if playlist and "error" not in playlist:
        result = client.format_for_playback(playlist)
        result["type"] = "playlist"
        result["message"] = f"Playing playlist: {playlist['name']}"
        return JSONResponse({"ok": True, **result})
    
    track = client.search_track(query)
    if track and "error" not in track:
        result = client.format_for_playback(track)
        result["type"] = "track"
        result["message"] = f"Playing: {track['name']} by {track['artist']}"
        return JSONResponse({"ok": True, **result})
    
    return JSONResponse({"ok": False, "message": f"Could not find '{query}' on Spotify"})


@app.get("/spotify/featured")
async def spotify_featured() -> JSONResponse:
    """Get currently featured playlists."""
    client = get_spotify_client()
    if not client:
        return JSONResponse({"ok": False, "message": "Spotify not configured"})
    
    playlists = client.get_featured_playlists()
    return JSONResponse({
        "ok": True,
        "playlists": [client.format_for_playback(p) for p in playlists if "error" not in p],
    })


@app.get("/spotify/new-releases")
async def spotify_new_releases() -> JSONResponse:
    """Get new releases on Spotify."""
    client = get_spotify_client()
    if not client:
        return JSONResponse({"ok": False, "message": "Spotify not configured"})
    
    albums = client.get_new_releases()
    return JSONResponse({
        "ok": True,
        "albums": [client.format_for_playback(a) for a in albums if "error" not in a],
    })


@app.get("/spotify/recommendations")
async def spotify_recommendations(genres: str = "pop") -> JSONResponse:
    """Get recommendations based on genres."""
    client = get_spotify_client()
    if not client:
        return JSONResponse({"ok": False, "message": "Spotify not configured"})
    
    genre_list = [g.strip() for g in genres.split(",")]
    tracks = client.get_recommendations(seed_genres=genre_list)
    return JSONResponse({
        "ok": True,
        "tracks": [client.format_for_playback(t) for t in tracks if "error" not in t],
    })


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": "Ear AI Home Server",
            "websocket": "/ws/assistant",
            "health": "/health",
            "agent": {
                "status": "Work in Progress (WIP for desktop app)",
                "note": "File system manager endpoints currently disabled",
            },
            "music": {
                "playlist": "/music/playlist",
                "status": "/music/status",
                "play": "/music/play",
                "pause": "/music/pause",
                "resume": "/music/resume",
                "stop": "/music/stop",
                "next": "/music/next",
                "previous": "/music/previous",
                "random": "/music/random",
                "volume": "/music/volume",
            },
            "spotify": {
                "status": "/spotify/status",
                "play": "/spotify/play?query=...",
                "featured": "/spotify/featured",
                "new_releases": "/spotify/new-releases",
                "recommendations": "/spotify/recommendations?genres=pop,rock",
            },
        }
    )
