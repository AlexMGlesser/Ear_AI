from collections import deque
from dataclasses import dataclass, field


@dataclass
class SessionMemoryStore:
    max_messages: int
    _store: dict[str, deque[dict[str, str]]] = field(default_factory=dict)

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        history = self._store.get(session_id)
        if history is None:
            return []
        return list(history)

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        if session_id not in self._store:
            self._store[session_id] = deque(maxlen=self.max_messages)

        history = self._store[session_id]
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": assistant_text})

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
