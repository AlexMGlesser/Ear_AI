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
agent_sandbox = AgentSandboxManager()
agent_executor = AgentExecutor(agent_sandbox)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/sessions", response_model=AgentSessionResponse)
async def create_agent_session(payload: AgentSessionCreateRequest) -> AgentSessionResponse:
    session = agent_sandbox.create_session(payload.label)
    return AgentSessionResponse(
        session_id=session.session_id,
        label=session.label,
        root_path=str(session.root_path),
        created_at=session.created_at,
    )


@app.get("/agent/sessions/{session_id}", response_model=AgentSessionResponse)
async def get_agent_session(session_id: str) -> AgentSessionResponse:
    try:
        root = agent_sandbox.get_session_root(session_id)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex

    return AgentSessionResponse(
        session_id=session_id,
        label=session_id,
        root_path=str(root),
        created_at=datetime.fromtimestamp(root.stat().st_ctime, tz=timezone.utc),
    )


@app.post("/agent/sessions/{session_id}/list")
async def list_agent_path(session_id: str, payload: AgentPathRequest) -> JSONResponse:
    try:
        entries = agent_sandbox.list_tree(session_id, payload.path)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, "path": payload.path, "entries": entries})


@app.post("/agent/sessions/{session_id}/read")
async def read_agent_file(session_id: str, payload: AgentReadFileRequest) -> JSONResponse:
    try:
        content = agent_sandbox.read_file(session_id, payload.path)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, "path": payload.path, "content": content})


@app.post("/agent/sessions/{session_id}/write")
async def write_agent_file(session_id: str, payload: AgentWriteFileRequest) -> JSONResponse:
    try:
        target = agent_sandbox.write_file(session_id, payload.path, payload.content, payload.overwrite)
    except FileExistsError as ex:
        raise HTTPException(status_code=409, detail=str(ex)) from ex
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, "path": str(target), "ok": True})


@app.post("/agent/sessions/{session_id}/append")
async def append_agent_file(session_id: str, payload: AgentAppendFileRequest) -> JSONResponse:
    try:
        target = agent_sandbox.append_file(session_id, payload.path, payload.content)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, "path": str(target), "ok": True})


@app.post("/agent/sessions/{session_id}/mkdir")
async def mkdir_agent_path(session_id: str, payload: AgentPathRequest) -> JSONResponse:
    try:
        target = agent_sandbox.make_dir(session_id, payload.path)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, "path": str(target), "ok": True})


@app.post("/agent/sessions/{session_id}/move")
async def move_agent_path(session_id: str, payload: AgentMovePathRequest) -> JSONResponse:
    try:
        _, destination = agent_sandbox.move_path(session_id, payload.source_path, payload.destination_path)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, "path": str(destination), "ok": True})


@app.post("/agent/sessions/{session_id}/delete")
async def delete_agent_path(session_id: str, payload: AgentDeletePathRequest) -> JSONResponse:
    try:
        agent_sandbox.delete_path(session_id, payload.path, payload.recursive)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex
    except OSError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, "path": payload.path, "ok": True})


@app.post("/agent/sessions/{session_id}/run")
async def run_agent_goal(session_id: str, payload: AgentRunGoalRequest) -> JSONResponse:
    try:
        result = await agent_executor.run_goal(
            session_id=session_id,
            goal=payload.goal,
            max_steps=payload.max_steps,
        )
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex)) from ex

    return JSONResponse({"session_id": session_id, **result})


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


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": "Ear AI Home Server",
            "websocket": "/ws/assistant",
            "health": "/health",
        }
    )
