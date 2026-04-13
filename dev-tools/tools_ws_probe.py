import asyncio
import json
import uuid
from datetime import datetime

import websockets

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOME_SERVER_DIR = PROJECT_ROOT / "home-server"

if str(HOME_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(HOME_SERVER_DIR))

from app.datetime_formatter import format_datetime_for_logs


async def main() -> None:
    uri = "ws://127.0.0.1:8765/ws/assistant"
    payload = {
        "type": "user_utterance",
        "session_id": str(uuid.uuid4()),
        "text": "look up latest OpenAI news and give one specific fact",
        "timestamp": format_datetime_for_logs(),
    }

    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps(payload))
            message = await ws.recv()
            print(message)
    except Exception as exc:
        print(f"WS_TEST_ERROR: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
