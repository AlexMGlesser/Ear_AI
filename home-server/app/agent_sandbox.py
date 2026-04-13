from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid

from .config import settings
from .datetime_formatter import format_datetime_for_logs


@dataclass
class AgentSession:
    session_id: str
    label: str
    root_path: Path
    created_at: datetime


class AgentSandboxManager:
    def __init__(self) -> None:
        self._base_dir = Path(settings.agent_sandbox_root).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, label: str | None = None) -> AgentSession:
        session_id = uuid.uuid4().hex
        safe_label = (label or "sandbox").strip() or "sandbox"
        session_dir = self._base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=False)

        meta = {
            "session_id": session_id,
            "label": safe_label,
            "created_at": format_datetime_for_logs(),
        }
        (session_dir / ".session.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        return AgentSession(
            session_id=session_id,
            label=safe_label,
            root_path=session_dir,
            created_at=datetime.now(timezone.utc),
        )

    def get_session_root(self, session_id: str) -> Path:
        root = (self._base_dir / session_id).resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Unknown sandbox session: {session_id}")
        self._ensure_within_base(root)
        return root

    def list_tree(self, session_id: str, relative_path: str = ".") -> list[dict]:
        root = self.get_session_root(session_id)
        target = self.resolve_path(root, relative_path)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"Directory not found: {relative_path}")

        entries: list[dict] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            rel = child.relative_to(root).as_posix()
            entries.append(
                {
                    "path": rel,
                    "is_dir": child.is_dir(),
                    "size": None if child.is_dir() else child.stat().st_size,
                }
            )
        return entries

    def read_file(self, session_id: str, relative_path: str) -> str:
        root = self.get_session_root(session_id)
        target = self.resolve_path(root, relative_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File not found: {relative_path}")

        size = target.stat().st_size
        if size > settings.agent_max_file_bytes:
            raise ValueError(f"File too large to read ({size} bytes)")

        return target.read_text(encoding="utf-8")

    def write_file(self, session_id: str, relative_path: str, content: str, overwrite: bool = True) -> Path:
        root = self.get_session_root(session_id)
        target = self.resolve_path(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {relative_path}")

        payload = content.encode("utf-8")
        if len(payload) > settings.agent_max_file_bytes:
            raise ValueError("Content exceeds max file size")

        target.write_bytes(payload)
        return target

    def append_file(self, session_id: str, relative_path: str, content: str) -> Path:
        root = self.get_session_root(session_id)
        target = self.resolve_path(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        existing = target.stat().st_size if target.exists() else 0
        add = len(content.encode("utf-8"))
        if existing + add > settings.agent_max_file_bytes:
            raise ValueError("Resulting file exceeds max file size")

        with target.open("a", encoding="utf-8") as handle:
            handle.write(content)
        return target

    def make_dir(self, session_id: str, relative_path: str) -> Path:
        root = self.get_session_root(session_id)
        target = self.resolve_path(root, relative_path)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def move_path(self, session_id: str, source_rel: str, dest_rel: str) -> tuple[Path, Path]:
        root = self.get_session_root(session_id)
        source = self.resolve_path(root, source_rel)
        destination = self.resolve_path(root, dest_rel)

        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source_rel}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        return source, destination

    def delete_path(self, session_id: str, relative_path: str, recursive: bool = False) -> None:
        root = self.get_session_root(session_id)
        target = self.resolve_path(root, relative_path)

        if not target.exists():
            raise FileNotFoundError(f"Path not found: {relative_path}")

        if target.is_dir():
            if recursive:
                shutil.rmtree(target)
            else:
                target.rmdir()
            return

        target.unlink()

    def resolve_path(self, root: Path, relative_path: str) -> Path:
        rel = (relative_path or ".").strip().replace("\\", "/")
        candidate = (root / rel).resolve()
        self._ensure_inside_root(root, candidate)
        return candidate

    def _ensure_inside_root(self, root: Path, path: Path) -> None:
        try:
            path.relative_to(root)
        except ValueError as ex:
            raise PermissionError("Path escapes sandbox root") from ex

    def _ensure_within_base(self, path: Path) -> None:
        try:
            path.relative_to(self._base_dir)
        except ValueError as ex:
            raise PermissionError("Sandbox path is outside base directory") from ex
