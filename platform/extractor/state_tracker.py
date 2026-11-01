import os
import json
import time
import ctypes
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "sync_state.json"


def is_pid_alive(pid: int) -> bool:
    """Checks if a process ID is currently running on Windows."""
    if not pid or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
            
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        return exit_code.value == STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def set_sync_state(step_number: int, step_name: str, step_detail: str, percent: int, is_running: bool = True, pid: int = None):
    """Writes the current pipeline progress state atomically."""
    current_pid = pid if pid is not None else os.getpid()
    state = {
        "is_running": is_running,
        "percent": max(0, min(100, percent)),
        "step_number": step_number,
        "step_name": step_name,
        "step_detail": step_detail,
        "pid": current_pid if is_running else None,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        tmp_file = STATE_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        tmp_file.replace(STATE_FILE)
    except Exception as e:
        print(f"[state_tracker] Error writing state: {e}")


def get_sync_state() -> dict:
    """Reads the current pipeline progress state."""
    if not STATE_FILE.exists():
        return {
            "is_running": False,
            "percent": 100,
            "step_number": 4,
            "step_name": "Ready (System Idle)",
            "step_detail": "System ready for scheduled daily sync or on-demand execution.",
            "pid": None
        }
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        # Verify if reported running process is actually alive
        if state.get("is_running") and state.get("pid"):
            if not is_pid_alive(state["pid"]):
                state["is_running"] = False
                state["percent"] = 100
                state["step_name"] = "Ready (System Idle)"
                state["step_detail"] = "Previous execution completed. System is idle."
                # Persist updated state
                set_sync_state(
                    step_number=4,
                    step_name=state["step_name"],
                    step_detail=state["step_detail"],
                    percent=100,
                    is_running=False
                )
        return state
    except Exception:
        return {
            "is_running": False,
            "percent": 100,
            "step_number": 4,
            "step_name": "Ready (System Idle)",
            "step_detail": "System ready for scheduled daily sync or on-demand execution.",
            "pid": None
        }
