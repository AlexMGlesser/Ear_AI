from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, ttk
from urllib import error, request

import customtkinter as ctk


REPO_ROOT = Path(__file__).resolve().parents[1]
HOME_SERVER_DIR = REPO_ROOT / "home-server"
ENV_PATH = HOME_SERVER_DIR / ".env"
LOGS_DIR = HOME_SERVER_DIR / "logs"
APP_SETTINGS = REPO_ROOT / "desktop-app" / "control_center_settings.json"


@dataclass
class ProcessHandle:
    process: subprocess.Popen | None = None
    thread: threading.Thread | None = None


class ControlCenter(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Ear AI Control Center")
        self.geometry("1280x860")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.server_proc = ProcessHandle()
        self.lm_proc = ProcessHandle()
        self.server_status = "stopped"  # "running" or "stopped"
        self.device_connected = False

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.settings = self._load_settings()

        self._build_ui()
        self.after(150, self._flush_logs)
        self.after(1000, self._check_server_health)

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color=("#1f2937", "#0f172a"), corner_radius=14)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ctk.CTkLabel(
            header,
            text="Ear AI Studio",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#7dd3fc",
        ).pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(
            header,
            text="Launch LM Studio, run server, inspect logs, and control sandbox agent environments.",
            font=ctk.CTkFont(size=14),
            text_color="#cbd5e1",
        ).pack(anchor="w", padx=16, pady=(2, 14))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ctk.CTkFrame(body, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self._build_left_panel(left)
        self._build_right_panel(right)

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="Runtime Controls", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        tabs = ctk.CTkTabview(parent, corner_radius=10)
        tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        tab_lm = tabs.add("LM Studio")
        tab_server = tabs.add("Server")
        tab_agent = tabs.add("Sandbox Agent")

        self._build_lm_tab(tab_lm)
        self._build_server_tab(tab_server)
        self._build_agent_tab(tab_agent)

    def _build_lm_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(parent, text="LM Studio executable path").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.lm_path = ctk.CTkEntry(parent)
        self.lm_path.insert(0, self.settings.get("lm_executable", ""))
        self.lm_path.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(10, 4))
        ctk.CTkButton(parent, text="Browse", width=90, command=self._pick_lm_executable).grid(row=0, column=2, padx=(0, 10), pady=(10, 4))

        ctk.CTkLabel(parent, text="Optional launch args").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.lm_args = ctk.CTkEntry(parent)
        self.lm_args.insert(0, self.settings.get("lm_args", ""))
        self.lm_args.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)

        ctk.CTkLabel(parent, text="Model id").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.model_id = ctk.CTkEntry(parent)
        self.model_id.insert(0, self.settings.get("model_id", "qwen/qwen3-14b"))
        self.model_id.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)

        ctk.CTkLabel(parent, text="Optional model load command").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        self.model_cmd = ctk.CTkEntry(parent)
        self.model_cmd.insert(0, self.settings.get("model_load_command", ""))
        self.model_cmd.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=(10, 8))
        ctk.CTkButton(row, text="Launch LM Studio", command=self.launch_lmstudio).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Check Model", command=self.check_model_loaded).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Start Model", command=self.start_model).pack(side="left")

    def _build_server_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(parent, text="Server host").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.server_host = ctk.CTkEntry(parent)
        self.server_host.insert(0, self.settings.get("server_host", "127.0.0.1"))
        self.server_host.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 4))

        ctk.CTkLabel(parent, text="Server port").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.server_port = ctk.CTkEntry(parent)
        self.server_port.insert(0, str(self.settings.get("server_port", 8765)))
        self.server_port.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=4)

        ctk.CTkLabel(parent, text="Agent sandbox root path").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.sandbox_root = ctk.CTkEntry(parent)
        self.sandbox_root.insert(0, self.settings.get("sandbox_root", str(HOME_SERVER_DIR / "sandboxes")))
        self.sandbox_root.grid(row=2, column=1, sticky="ew", padx=(0, 6), pady=4)
        ctk.CTkButton(parent, text="Browse", width=90, command=self.pick_sandbox_root).grid(row=2, column=2, padx=(0, 10), pady=4)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=(10, 8))
        ctk.CTkButton(row, text="Start Server", command=self.start_server).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Stop Server", command=self.stop_server).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Open Sandbox Folder", command=self.open_sandbox_folder).pack(side="left")

        # Status indicators
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 8))
        
        self.server_status_label = ctk.CTkLabel(
            status_frame,
            text="●  Server: stopped",
            text_color="#ef4444",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.server_status_label.pack(side="left", padx=(0, 16))
        
        self.device_status_label = ctk.CTkLabel(
            status_frame,
            text="●  Device: disconnected",
            text_color="#ef4444",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.device_status_label.pack(side="left")

    def _build_agent_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(parent, text="Goal for autonomous file agent").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.goal_box = ctk.CTkTextbox(parent, height=130)
        self.goal_box.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self.goal_box.insert("1.0", "Create a project folder with README and a starter src/main.py file.")

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 10))
        ctk.CTkButton(row, text="Create Session", command=self.create_agent_session).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Run Goal", command=self.run_agent_goal).pack(side="left", padx=(0, 8))

        self.session_label = ctk.CTkLabel(parent, text="Session: (none)")
        self.session_label.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 8))

    def _build_right_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(parent, text="Observability", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 8)
        )

        view_tabs = ctk.CTkTabview(parent, corner_radius=10)
        view_tabs.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=12, pady=(0, 12))

        tab_logs = view_tabs.add("Logs")
        tab_tree = view_tabs.add("Sandbox Tree")

        tab_logs.grid_rowconfigure(1, weight=1)
        tab_logs.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(tab_logs, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 8))
        ctk.CTkButton(top_row, text="Load web_lookup.log", command=lambda: self.load_log_file("web_lookup.log")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(top_row, text="Load sessions.log", command=lambda: self.load_log_file("conversation_sessions.log")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(top_row, text="Clear View", command=self.clear_log_view).pack(side="left")

        self.log_view = ctk.CTkTextbox(tab_logs, wrap="word")
        self.log_view.grid(row=1, column=0, sticky="nsew")

        self._build_tree_tab(tab_tree)

    def _build_tree_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 8))
        ctk.CTkButton(controls, text="Refresh Tree", command=self.refresh_tree_view).pack(side="left", padx=(0, 8))

        self.tree_status = ctk.CTkLabel(controls, text="No active session")
        self.tree_status.pack(side="left", padx=(4, 0))

        tree_frame = ctk.CTkFrame(parent)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.sandbox_tree = ttk.Treeview(tree_frame, columns=("type", "size"), show="tree headings")
        self.sandbox_tree.heading("#0", text="Path")
        self.sandbox_tree.heading("type", text="Type")
        self.sandbox_tree.heading("size", text="Size")
        self.sandbox_tree.column("#0", width=420, anchor="w")
        self.sandbox_tree.column("type", width=90, anchor="center")
        self.sandbox_tree.column("size", width=90, anchor="e")
        self.sandbox_tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sandbox_tree.yview)
        self.sandbox_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=0, column=1, sticky="ns")

    def refresh_tree_view(self) -> None:
        session_id = self.settings.get("active_session_id", "")
        self.sandbox_tree.delete(*self.sandbox_tree.get_children())

        if not session_id:
            self.tree_status.configure(text="No active session")
            return

        self.tree_status.configure(text=f"Session: {session_id}")
        self._populate_tree_node(session_id=session_id, parent_node="", relative_path=".")

    def _populate_tree_node(self, session_id: str, parent_node: str, relative_path: str) -> None:
        payload = self._http_post_json(
            f"http://127.0.0.1:8765/agent/sessions/{session_id}/list",
            {"path": relative_path},
        )
        if not payload:
            return

        for entry in payload.get("entries", []):
            path = entry.get("path", "")
            is_dir = bool(entry.get("is_dir"))
            size = entry.get("size")

            label = path.split("/")[-1] if "/" in path else path
            type_label = "dir" if is_dir else "file"
            size_label = "" if is_dir or size is None else str(size)

            node = self.sandbox_tree.insert(parent_node, "end", text=label, values=(type_label, size_label))

            if is_dir:
                self._populate_tree_node(session_id=session_id, parent_node=node, relative_path=path)

    def _flush_logs(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_view.insert("end", line)
                self.log_view.see("end")
        except queue.Empty:
            pass
        self.after(120, self._flush_logs)

    def _pick_lm_executable(self) -> None:
        file_path = filedialog.askopenfilename(title="Select LM Studio executable")
        if file_path:
            self.lm_path.delete(0, "end")
            self.lm_path.insert(0, file_path)
            self._save_settings()

    def pick_sandbox_root(self) -> None:
        directory = filedialog.askdirectory(title="Select sandbox root")
        if directory:
            self.sandbox_root.delete(0, "end")
            self.sandbox_root.insert(0, directory)
            self._save_settings()
            self._write_env_value("AGENT_SANDBOX_ROOT", directory)
            self._log(f"[cfg] AGENT_SANDBOX_ROOT updated to {directory}\n")

    def launch_lmstudio(self) -> None:
        exe = self.lm_path.get().strip()
        args = self.lm_args.get().strip()
        if not exe:
            self._log("[lm] Set LM Studio executable path first.\n")
            return

        command = [exe]
        if args:
            command.extend(args.split())

        try:
            proc = subprocess.Popen(command, cwd=str(Path(exe).parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.lm_proc.process = proc
            self.lm_proc.thread = threading.Thread(target=self._pump_output, args=(proc, "lm"), daemon=True)
            self.lm_proc.thread.start()
            self._log("[lm] Launch command sent.\n")
            self._save_settings()
        except Exception as ex:
            self._log(f"[lm] Failed to launch: {ex}\n")

    def start_model(self) -> None:
        model_cmd = self.model_cmd.get().strip()
        model_id = self.model_id.get().strip()
        self._save_settings()

        if self.check_model_loaded(show_success=False):
            self._log(f"[lm] Model already active: {model_id}\n")
            return

        if model_cmd:
            try:
                subprocess.Popen(model_cmd, cwd=str(REPO_ROOT), shell=True)
                self._log("[lm] Model load command launched.\n")
                return
            except Exception as ex:
                self._log(f"[lm] Model load command failed: {ex}\n")
                return

        self._log("[lm] Model not loaded. Set Optional model load command or load model in LM Studio UI.\n")

    def check_model_loaded(self, show_success: bool = True) -> bool:
        model_id = self.model_id.get().strip()
        payload = self._http_get_json("http://127.0.0.1:1234/v1/models")
        if payload is None:
            self._log("[lm] Could not reach LM Studio API at 127.0.0.1:1234.\n")
            return False

        model_ids = [item.get("id", "") for item in payload.get("data", [])]
        if model_id and model_id in model_ids:
            if show_success:
                self._log(f"[lm] Model available: {model_id}\n")
            return True

        if show_success:
            self._log(f"[lm] Model not present in API list: {model_id}\n")
        return False

    def start_server(self) -> None:
        if self.server_proc.process and self.server_proc.process.poll() is None:
            self._log("[server] Already running.\n")
            return

        host = self.server_host.get().strip() or "127.0.0.1"
        port = self.server_port.get().strip() or "8765"

        self._write_env_value("AGENT_SANDBOX_ROOT", self.sandbox_root.get().strip())
        self._save_settings()

        command = [
            str(HOME_SERVER_DIR / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            port,
        ]

        try:
            proc = subprocess.Popen(
                command,
                cwd=str(HOME_SERVER_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.server_proc.process = proc
            self.server_proc.thread = threading.Thread(target=self._pump_output, args=(proc, "server"), daemon=True)
            self.server_proc.thread.start()
            self.server_status = "running"
            self._update_server_status_label()
            self._log(f"[server] Starting on {host}:{port}\n")
        except Exception as ex:
            self._log(f"[server] Failed to start: {ex}\n")

    def stop_server(self) -> None:
        proc = self.server_proc.process
        if not proc or proc.poll() is not None:
            self._log("[server] Not running.\n")
            self.server_status = "stopped"
            self._update_server_status_label()
            return
        proc.terminate()
        self.server_status = "stopped"
        self._update_server_status_label()
        self._log("[server] Stop signal sent.\n")

    def open_sandbox_folder(self) -> None:
        target = Path(self.sandbox_root.get().strip() or (HOME_SERVER_DIR / "sandboxes"))
        target.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(target)])

    def create_agent_session(self) -> None:
        result = self._http_post_json(
            "http://127.0.0.1:8765/agent/sessions",
            {"label": "desktop-run"},
        )
        if not result:
            self._log("[agent] Failed to create session. Is server running?\n")
            return

        self.settings["active_session_id"] = result["session_id"]
        self.session_label.configure(text=f"Session: {result['session_id']}")
        self._save_settings()
        self._log(f"[agent] Session created: {result['session_id']}\n")
        self.refresh_tree_view()

    def run_agent_goal(self) -> None:
        session_id = self.settings.get("active_session_id", "")
        if not session_id:
            self._log("[agent] Create a session first.\n")
            return

        goal = self.goal_box.get("1.0", "end").strip()
        if not goal:
            self._log("[agent] Goal cannot be empty.\n")
            return

        result = self._http_post_json(
            f"http://127.0.0.1:8765/agent/sessions/{session_id}/run",
            {"goal": goal, "max_steps": 10},
        )
        if not result:
            self._log("[agent] Goal run failed.\n")
            return

        self._log(f"[agent] finished={result.get('finished')} ok={result.get('ok')}\n")
        self._log(f"[agent] summary: {result.get('summary', '')}\n")
        for step in result.get("steps", []):
            self._log(
                f"  - step={step.get('step')} action={step.get('action')} ok={step.get('ok')} msg={step.get('message')}\n"
            )
        self.refresh_tree_view()

    def load_log_file(self, filename: str) -> None:
        target = LOGS_DIR / filename
        if not target.exists():
            self._log(f"[logs] File not found: {target}\n")
            return

        content = target.read_text(encoding="utf-8", errors="ignore")
        self.log_view.delete("1.0", "end")
        self.log_view.insert("1.0", content[-80_000:])

    def clear_log_view(self) -> None:
        self.log_view.delete("1.0", "end")

    def _pump_output(self, proc: subprocess.Popen, label: str) -> None:
        if not proc.stdout:
            return
        for line in proc.stdout:
            self.log_queue.put(f"[{label}] {line}")
        # When process ends, update status
        if label == "server":
            self.server_status = "stopped"
            self._update_server_status_label()

    def _check_server_health(self) -> None:
        """Periodic health check to verify server status and device connections."""
        host = self.server_host.get().strip() or "127.0.0.1"
        port = self.server_port.get().strip() or "8765"
        health_url = f"http://{host}:{port}/health"
        
        # Check if server is actually responding
        health_ok = self._http_get_json(health_url) is not None
        
        if health_ok and self.server_proc.process and self.server_proc.process.poll() is None:
            self.server_status = "running"
        else:
            self.server_status = "stopped"
        
        # Check for device connections by counting active sessions
        # For now, we'll mark device as connected if there's an active session
        self.device_connected = False
        if health_ok:
            # Try to detect if there are active connections
            # This is a simple heuristic: check if there are any recent sandbox sessions
            sessions_dir = HOME_SERVER_DIR / self.settings.get("sandbox_root", "sandboxes")
            if sessions_dir.exists():
                recent_sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
                self.device_connected = len(recent_sessions) > 0
        
        self._update_server_status_label()
        self._update_device_status_label()
        self.after(2000, self._check_server_health)

    def _update_server_status_label(self) -> None:
        """Update the server status indicator label."""
        if self.server_status == "running":
            self.server_status_label.configure(
                text="●  Server: running",
                text_color="#22c55e"
            )
        else:
            self.server_status_label.configure(
                text="●  Server: stopped",
                text_color="#ef4444"
            )

    def _update_device_status_label(self) -> None:
        """Update the device connection status indicator label."""
        if self.device_connected:
            self.device_status_label.configure(
                text="●  Device: connected",
                text_color="#22c55e"
            )
        else:
            self.device_status_label.configure(
                text="●  Device: disconnected",
                text_color="#ef4444"
            )

    def _log(self, message: str) -> None:
        self.log_queue.put(message)
        # Also update status display on relevant messages
        if "Application startup complete" in message:
            self.server_status = "running"
            self._update_server_status_label()

    def _save_settings(self) -> None:
        self.settings.update(
            {
                "lm_executable": self.lm_path.get().strip(),
                "lm_args": self.lm_args.get().strip(),
                "model_id": self.model_id.get().strip(),
                "model_load_command": self.model_cmd.get().strip(),
                "server_host": self.server_host.get().strip(),
                "server_port": self.server_port.get().strip(),
                "sandbox_root": self.sandbox_root.get().strip(),
            }
        )
        APP_SETTINGS.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")

    def _load_settings(self) -> dict:
        if APP_SETTINGS.exists():
            try:
                return json.loads(APP_SETTINGS.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _write_env_value(self, key: str, value: str) -> None:
        lines: list[str] = []
        if ENV_PATH.exists():
            lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

        updated = False
        new_line = f"{key}={value}"
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = new_line
                updated = True
                break
        if not updated:
            lines.append(new_line)

        ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _http_get_json(self, url: str) -> dict | None:
        try:
            with request.urlopen(url, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    def _http_post_json(self, url: str, payload: dict) -> dict | None:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as ex:
            try:
                body = ex.read().decode("utf-8")
            except Exception:
                body = str(ex)
            self._log(f"[http] {url} failed: {body}\n")
            return None
        except Exception as ex:
            self._log(f"[http] {url} failed: {ex}\n")
            return None


def main() -> None:
    app = ControlCenter()
    app.mainloop()


if __name__ == "__main__":
    main()
