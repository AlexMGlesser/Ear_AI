from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .datetime_formatter import format_datetime_for_logs

SESSION_LOG_PATH = Path("logs/conversation_sessions.log")


def log_session_started(session_id: str, first_utterance: str) -> None:
    SESSION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = format_datetime_for_logs()
    safe_utterance = first_utterance.replace("\n", " ").strip()
    with SESSION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            f"[{timestamp}] session_started session_id={session_id} first_utterance={safe_utterance}\n"
        )
