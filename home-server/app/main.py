from datetime import datetime, timezone
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from .config import settings
from .lmstudio_client import generate_reply
from .models import AssistantResponse, ErrorResponse, UserUtterance
from .rules_engine import build_system_prompt
from .session_memory import SessionMemoryStore
from .web_lookup import build_web_context, should_lookup

app = FastAPI(title="Ear AI Home Server", version="0.1.0")
memory_store = SessionMemoryStore(max_messages=settings.session_history_messages)
session_lookup_status: dict[str, str] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
                system_prompt = build_system_prompt()
                history = memory_store.get_history(utterance.session_id)
                web_context = ""
                lookup_used = False
                lookup_requested = should_lookup(utterance.text)
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


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": "Ear AI Home Server",
            "websocket": "/ws/assistant",
            "health": "/health",
        }
    )
