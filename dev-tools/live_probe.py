import asyncio
import json
import uuid
from datetime import datetime, timezone

import websockets


URI = "ws://127.0.0.1:8765/ws/assistant"
QUESTIONS = [
    "What is today's date?",
    "What is the current UTC date and time right now?",
    "Do you have internet access?",
    "Look up latest OpenAI news and give one specific fact.",
]


async def ask(question: str) -> dict:
    payload = {
        "type": "user_utterance",
        "session_id": str(uuid.uuid4()),
        "text": question,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    async with websockets.connect(URI) as ws:
        await ws.send(json.dumps(payload))
        raw = await ws.recv()

    return json.loads(raw)


async def main() -> None:
    for question in QUESTIONS:
        try:
            response = await ask(question)
            text = response.get("text") or response.get("message") or "(no text)"
        except Exception as exc:
            text = f"ERROR: {exc}"

        print(f"Q: {question}")
        print(f"A: {text}")
        print("-")


if __name__ == "__main__":
    asyncio.run(main())
