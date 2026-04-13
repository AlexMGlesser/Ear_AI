# Ear AI Desktop Control Center

A local GUI app for running and managing Ear AI on your computer.

## What it does
- Launches LM Studio from a selected executable path.
- Checks model availability using LM Studio API.
- Starts and stops the home server.
- Lets you choose the sandbox root path for the isolated AI environment.
- Shows runtime output and log files.
- Shows a visual sandbox file tree for the active agent session.
- Runs autonomous sandbox goals through the new `/agent/sessions/{id}/run` endpoint.

## Install
From repo root:
```powershell
cd d:\Code\Ear_AI
.\home-server\.venv\Scripts\python.exe -m pip install -r .\desktop-app\requirements.txt
```

## Run
From repo root:
```powershell
.\home-server\.venv\Scripts\python.exe .\desktop-app\control_center.py
```

## Notes
- Set LM Studio executable path in the GUI before launching.
- If model auto-start is needed, fill Optional model load command.
- Sandbox path updates write to `home-server/.env` as `AGENT_SANDBOX_ROOT`.
