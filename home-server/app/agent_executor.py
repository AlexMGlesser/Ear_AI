from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from .agent_sandbox import AgentSandboxManager
from .lmstudio_client import generate_reply


@dataclass
class AgentStepResult:
    step: int
    action: str
    args: dict[str, Any]
    ok: bool
    message: str
    data: dict[str, Any] | None = None


class AgentExecutor:
    def __init__(self, sandbox: AgentSandboxManager) -> None:
        self.sandbox = sandbox

    async def run_goal(self, session_id: str, goal: str, max_steps: int = 8) -> dict[str, Any]:
        max_steps = max(1, min(max_steps, 20))

        plan_system = (
            "You are a local file agent operating inside a sandbox. "
            "You must respond ONLY with JSON. No prose.\n\n"
            "Available actions:\n"
            "- list: {\"path\": \"relative/path\"}\n"
            "- read_file: {\"path\": \"relative/file\"}\n"
            "- write_file: {\"path\": \"relative/file\", \"content\": \"text\", \"overwrite\": true}\n"
            "- append_file: {\"path\": \"relative/file\", \"content\": \"text\"}\n"
            "- mkdir: {\"path\": \"relative/dir\"}\n"
            "- move: {\"source_path\": \"from\", \"destination_path\": \"to\"}\n"
            "- delete: {\"path\": \"relative/path\", \"recursive\": false}\n"
            "- finish: {\"summary\": \"final short summary\"}\n\n"
            "Response schema:\n"
            "{\"action\": \"...\", \"args\": { ... }}"
        )

        observations: list[str] = []
        steps: list[AgentStepResult] = []

        for i in range(1, max_steps + 1):
            prompt = self._build_prompt(goal, observations, i, max_steps)
            raw = await generate_reply(prompt, plan_system, history_messages=[])
            parsed = self._parse_action(raw)

            action = parsed.get("action", "")
            args = parsed.get("args", {}) if isinstance(parsed.get("args"), dict) else {}

            if action == "finish":
                summary = str(args.get("summary") or "Completed requested operations.")
                return {
                    "ok": True,
                    "finished": True,
                    "summary": summary,
                    "steps": [self._step_dict(step) for step in steps],
                }

            result = self._execute_action(session_id, i, action, args)
            steps.append(result)

            obs = {
                "step": i,
                "action": action,
                "ok": result.ok,
                "message": result.message,
                "data": result.data,
            }
            observations.append(json.dumps(obs, ensure_ascii=True))

        return {
            "ok": False,
            "finished": False,
            "summary": "Reached max steps before finish action.",
            "steps": [self._step_dict(step) for step in steps],
        }

    def _build_prompt(self, goal: str, observations: list[str], current_step: int, max_steps: int) -> str:
        if not observations:
            return (
                f"Goal: {goal}\n"
                f"Step {current_step}/{max_steps}.\n"
                "Return next JSON action only."
            )

        joined = "\n".join(observations[-6:])
        return (
            f"Goal: {goal}\n"
            f"Step {current_step}/{max_steps}.\n"
            "Recent observations:\n"
            f"{joined}\n"
            "Return next JSON action only."
        )

    def _parse_action(self, raw: str) -> dict[str, Any]:
        text = raw.strip()

        # Strip fenced blocks if model returns markdown wrappers.
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9_\-]*", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # Fallback: extract first JSON object.
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        return {"action": "finish", "args": {"summary": "Planner returned invalid JSON; stopping."}}

    def _execute_action(self, session_id: str, step: int, action: str, args: dict[str, Any]) -> AgentStepResult:
        try:
            if action == "list":
                path = str(args.get("path") or ".")
                entries = self.sandbox.list_tree(session_id, path)
                return AgentStepResult(step, action, args, True, f"Listed {len(entries)} entries", {"entries": entries})

            if action == "read_file":
                path = str(args.get("path") or "")
                content = self.sandbox.read_file(session_id, path)
                preview = content[:1000]
                return AgentStepResult(step, action, args, True, "Read file", {"preview": preview, "length": len(content)})

            if action == "write_file":
                path = str(args.get("path") or "")
                content = str(args.get("content") or "")
                overwrite = bool(args.get("overwrite", True))
                target = self.sandbox.write_file(session_id, path, content, overwrite)
                return AgentStepResult(step, action, args, True, "Wrote file", {"path": str(target)})

            if action == "append_file":
                path = str(args.get("path") or "")
                content = str(args.get("content") or "")
                target = self.sandbox.append_file(session_id, path, content)
                return AgentStepResult(step, action, args, True, "Appended file", {"path": str(target)})

            if action == "mkdir":
                path = str(args.get("path") or "")
                target = self.sandbox.make_dir(session_id, path)
                return AgentStepResult(step, action, args, True, "Created directory", {"path": str(target)})

            if action == "move":
                src = str(args.get("source_path") or "")
                dst = str(args.get("destination_path") or "")
                _, destination = self.sandbox.move_path(session_id, src, dst)
                return AgentStepResult(step, action, args, True, "Moved path", {"path": str(destination)})

            if action == "delete":
                path = str(args.get("path") or "")
                recursive = bool(args.get("recursive", False))
                self.sandbox.delete_path(session_id, path, recursive)
                return AgentStepResult(step, action, args, True, "Deleted path", {"path": path})

            return AgentStepResult(step, action, args, False, f"Unknown action: {action}")

        except Exception as ex:
            return AgentStepResult(step, action, args, False, str(ex))

    def _step_dict(self, step: AgentStepResult) -> dict[str, Any]:
        return {
            "step": step.step,
            "action": step.action,
            "args": step.args,
            "ok": step.ok,
            "message": step.message,
            "data": step.data,
        }
