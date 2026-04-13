# Agent Sandbox API

This API provides an isolated file-operation environment inside `home-server/sandboxes`.

## Safety model
- Each session gets its own folder: `sandboxes/<session_id>/`
- All operations are path-restricted to that session folder.
- Path traversal outside the sandbox is blocked.
- Per-file size limits are enforced by server config.

## Configuration
In `.env` (optional):
- `AGENT_SANDBOX_ROOT=sandboxes`
- `AGENT_MAX_FILE_BYTES=2000000`

## Endpoints
- `POST /agent/sessions`
  - Body: `{ "label": "optional-name" }`
  - Creates a new sandbox session.

- `GET /agent/sessions/{session_id}`
  - Returns metadata for an existing session.

- `POST /agent/sessions/{session_id}/list`
  - Body: `{ "path": "." }`
  - Lists files and folders.

- `POST /agent/sessions/{session_id}/read`
  - Body: `{ "path": "src/main.txt" }`
  - Reads file contents.

- `POST /agent/sessions/{session_id}/write`
  - Body: `{ "path": "src/main.txt", "content": "hello", "overwrite": true }`
  - Writes file contents.

- `POST /agent/sessions/{session_id}/append`
  - Body: `{ "path": "notes.txt", "content": "line\n" }`
  - Appends to file.

- `POST /agent/sessions/{session_id}/mkdir`
  - Body: `{ "path": "src/lib" }`
  - Creates directory recursively.

- `POST /agent/sessions/{session_id}/move`
  - Body: `{ "source_path": "a.txt", "destination_path": "archive/a.txt" }`
  - Moves or renames file/folder.

- `POST /agent/sessions/{session_id}/delete`
  - Body: `{ "path": "archive", "recursive": true }`
  - Deletes file/folder.

- `POST /agent/sessions/{session_id}/run`
  - Body: `{ "goal": "Create a project with README and src/main.py", "max_steps": 10 }`
  - Runs an autonomous multi-step planner/executor loop using sandbox tools.
  - Returns step-by-step action results and a final summary.

## Quick example (PowerShell)
```powershell
$session = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/agent/sessions" -Body (@{ label = "demo" } | ConvertTo-Json) -ContentType "application/json"

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/agent/sessions/$($session.session_id)/mkdir" -Body (@{ path = "project/src" } | ConvertTo-Json) -ContentType "application/json"

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/agent/sessions/$($session.session_id)/write" -Body (@{ path = "project/src/main.txt"; content = "hello"; overwrite = $true } | ConvertTo-Json) -ContentType "application/json"

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/agent/sessions/$($session.session_id)/list" -Body (@{ path = "project" } | ConvertTo-Json) -ContentType "application/json"
```
