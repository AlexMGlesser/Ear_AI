import asyncio
import datetime
import json
import uuid

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8765/ws/assistant"
    payload = {
        "type": "user_utterance",
        "session_id": str(uuid.uuid4()),
        "text": "look up latest OpenAI news and give one specific fact",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
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
