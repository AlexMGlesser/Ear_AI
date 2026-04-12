from datetime import datetime, timezone
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from .config import settings
from .lmstudio_client import generate_reply
from .models import AssistantResponse, ErrorResponse, UserUtterance
from .rules_engine import build_system_prompt
from .session_memory import SessionMemoryStore

app = FastAPI(title="Ear AI Home Server", version="0.1.0")
memory_store = SessionMemoryStore(max_messages=settings.session_history_messages)


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
                reply_text = await generate_reply(utterance.text, system_prompt, history)
                memory_store.append_turn(utterance.session_id, utterance.text, reply_text)
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
