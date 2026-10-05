# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Resolve the repo root no matter how scripts.py is launched.

    - From source (python tools/command_center/main.py), services.py's own path is
      <repo>/tools/command_center/services.py, so parents[2] with no env var is the repo.
    - From the PyInstaller exe (PathfinderGodCommandCenter.exe), __file__ points inside
      the temp _MEIPASS unpack dir, so parents[2] lands on a temp path and every
      start_hub then fails with "No module named app" / WinError 3. Use the exe's own
      location instead: <repo>/tools/command_center/dist/PathfinderGodCommandCenter.exe,
      whose parents[3] is the repo root.
    - Override with the PFGOD_REPO_ROOT env var when the exe is relocated.
    """
    env = os.environ.get("PFGOD_REPO_ROOT")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parents[3]
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _repo_root()
HUB_DIR = REPO_ROOT / "hub"
VENV_PYTHON = Path(r"C:\venv-hub\venv\Scripts\python.exe")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class ManagedProcess:
    def __init__(self, name: str):
        self.name = name
        self.proc: subprocess.Popen | None = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> tuple[bool, str]:
        if self.running:
            return False, f"{self.name} already managed and running"
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        log_dir = REPO_ROOT / "tools" / "command_center" / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{self.name.lower()}.log"
        try:
            # Kept on self, not passed inline. Popen never closes the handle it is given, so
            # `stdout=open(...)` leaked one OS file descriptor per start, and used the Windows
            # default (cp1252) rather than UTF-8 - which mangles the em dash and box glyphs the
            # hub emits and get_log_tail then decodes as UTF-8. Closed in stop().
            self._log_handle = open(log_file, "a", encoding="utf-8", errors="replace")
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=full_env,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
            return True, f"{self.name} started (pid {self.proc.pid}) — log: {log_file}"
        except OSError as e:
            self.proc = None
            self._close_log()
            return False, f"{self.name} failed to start: {e}"

    def _close_log(self) -> None:
        handle = getattr(self, "_log_handle", None)
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
            self._log_handle = None

    def stop(self) -> tuple[bool, str]:
        if not self.running:
            self.proc = None
            self._close_log()
            return False, f"{self.name} is not running"
        proc, self.proc = self.proc, None
        proc.terminate()
        try:
            proc.wait(timeout=8)
            self._close_log()
            return True, f"{self.name} stopped"
        except subprocess.TimeoutExpired:
            proc.kill()
            self._close_log()
            return True, f"{self.name} force-killed"

    def get_log_tail(self, lines: int = 50) -> str:
        log_file = REPO_ROOT / "tools" / "command_center" / "logs" / f"{self.name.lower()}.log"
        if not log_file.exists():
            return "No log file yet."
        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
            return "\n".join(content.splitlines()[-lines:])
        except Exception as e:
            return f"Failed to read log: {e}"


ollama = ManagedProcess("Ollama")
hub = ManagedProcess("Hub")


def start_ollama() -> tuple[bool, str]:
    return ollama.start(["ollama.exe", "serve"])


def start_hub() -> tuple[bool, str]:
    if not VENV_PYTHON.exists():
        return False, f"venv python not found at {VENV_PYTHON}"
    return hub.start([str(VENV_PYTHON), "-m", "app.main"], cwd=HUB_DIR)
