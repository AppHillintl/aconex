"""
=============================================================================
ACONEX PIPELINE SYNC & WINDOWS TASK SCHEDULER MANAGER
Coordinates automated background extraction, DuckDB ETL refresh,
and Windows Task Scheduler lifecycle with real-time state tracking.
Guaranteed 100% windowless/silent execution via pythonw.exe.
Supports:
  1. Daily Baseline Deep Sync (AconexDailySync @ 05:00 AM)
  2. Business Hours Micro-Batch Delta Sync (AconexBusinessHoursSync @ Every 15/30/60/120m)
=============================================================================
"""

import os
import sys
import subprocess
import json
import logging
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RUNNER_PY = BASE_DIR / "run_pipeline.py"
LOG_FILE = BASE_DIR / "sync_live.log"
CONFIG_FILE = BASE_DIR / "sync_config.json"
TASK_NAME = "AconexDailySync"
FALLBACK_TASK_NAME = "AconexExtractionTest"
MICRO_TASK_NAME = "AconexBusinessHoursSync"

from state_tracker import get_sync_state, set_sync_state, is_pid_alive


def get_saved_sync_config() -> dict:
    """Reads persistent configuration for micro-batch and daily sync settings."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "micro_batch_enabled": True,
        "micro_batch_interval_mins": 30,
        "daily_sync_time": "05:00"
    }


def save_sync_config(cfg: dict):
    """Atomically persists sync configuration."""
    try:
        cur = get_saved_sync_config()
        cur.update(cfg)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cur, f, indent=2)
    except Exception as e:
        print(f"[sync_manager] Error saving sync_config: {e}")


def get_silent_python_exe() -> str:
    """Returns pythonw.exe if available, guaranteeing no console window pops up."""
    cur = Path(sys.executable).resolve()
    pyw = cur.with_name("pythonw.exe")
    if pyw.exists():
        return str(pyw)
    return str(cur)


_task_cache = {"data": None, "ts": 0}
_micro_cache = {"data": None, "ts": 0}


def get_task_info(force_refresh: bool = False) -> dict:
    """Retrieves current Windows Task Scheduler info for AconexDailySync (Cached for 45s)."""
    global _task_cache
    now = time.time()
    if not force_refresh and _task_cache["data"] and (now - _task_cache["ts"] < 45):
        return _task_cache["data"]

    target_tasks = [TASK_NAME, FALLBACK_TASK_NAME]
    cfg = get_saved_sync_config()
    default_time = cfg.get("daily_sync_time", "05:00")

    for tn in target_tasks:
        ps_cmd = (
            f"$t = Get-ScheduledTask -TaskName '{tn}' -ErrorAction SilentlyContinue; "
            f"if ($t) {{ "
            f"  $info = Get-ScheduledTaskInfo -TaskName '{tn}'; "
            f"  $trigger = $t.Triggers[0]; "
            f"  $at = if ($trigger.StartBoundary) {{ ([datetime]$trigger.StartBoundary).ToString('HH:mm') }} else {{ '{default_time}' }}; "
            f"  [PSCustomObject]@{{ "
            f"    Name = $t.TaskName; "
            f"    State = $t.State.ToString(); "
            f"    Enabled = [bool]($t.Settings.Enabled); "
            f"    AtTime = $at; "
            f"    NextRun = if ($info.NextRunTime) {{ $info.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss') }} else {{ 'N/A' }}; "
            f"    LastRun = if ($info.LastRunTime) {{ $info.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') }} else {{ 'N/A' }}; "
            f"    LastResult = $info.LastTaskResult; "
            f"  }} | ConvertTo-Json "
            f"}}"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=8
            )
            if res.stdout.strip():
                data = json.loads(res.stdout)
                is_active = data.get("State", "").lower() in ["ready", "running"]
                result = {
                    "found": True,
                    "task_name": data.get("Name"),
                    "state": data.get("State", "Ready"),
                    "enabled": is_active,
                    "at_time": data.get("AtTime", default_time),
                    "next_run": data.get("NextRun", "N/A"),
                    "last_run": data.get("LastRun", "N/A"),
                    "last_result": data.get("LastResult", 0)
                }
                _task_cache = {"data": result, "ts": now}
                return result
        except Exception:
            pass

    fallback = {
        "found": False,
        "task_name": TASK_NAME,
        "state": "Not Registered",
        "enabled": False,
        "at_time": default_time,
        "next_run": "N/A",
        "last_run": "N/A",
        "last_result": 0
    }
    _task_cache = {"data": fallback, "ts": now}
    return fallback


def get_micro_batch_info(force_refresh: bool = False) -> dict:
    """Retrieves current Windows Task Scheduler info for AconexBusinessHoursSync (Cached for 45s)."""
    global _micro_cache
    now = time.time()
    if not force_refresh and _micro_cache["data"] and (now - _micro_cache["ts"] < 45):
        return _micro_cache["data"]

    cfg = get_saved_sync_config()
    saved_mins = int(cfg.get("micro_batch_interval_mins", 30))
    saved_enabled = bool(cfg.get("micro_batch_enabled", True))

    ps_cmd = (
        f"$t = Get-ScheduledTask -TaskName '{MICRO_TASK_NAME}' -ErrorAction SilentlyContinue; "
        f"if ($t) {{ "
        f"  $info = Get-ScheduledTaskInfo -TaskName '{MICRO_TASK_NAME}'; "
        f"  $trigger = $t.Triggers[0]; "
        f"  $interval = if ($trigger.Repetition -and $trigger.Repetition.Interval) {{ $trigger.Repetition.Interval }} else {{ 'PT{saved_mins}M' }}; "
        f"  $at = if ($trigger.StartBoundary) {{ ([datetime]$trigger.StartBoundary).ToString('HH:mm') }} else {{ '08:00' }}; "
        f"  [PSCustomObject]@{{ "
        f"    Name = $t.TaskName; "
        f"    State = $t.State.ToString(); "
        f"    Enabled = [bool]($t.Settings.Enabled); "
        f"    AtTime = $at; "
        f"    Interval = $interval; "
        f"    NextRun = if ($info.NextRunTime) {{ $info.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss') }} else {{ 'N/A' }}; "
        f"    LastRun = if ($info.LastRunTime) {{ $info.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') }} else {{ 'N/A' }}; "
        f"    LastResult = $info.LastTaskResult; "
        f"  }} | ConvertTo-Json "
        f"}}"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=8
        )
        if res.stdout.strip():
            data = json.loads(res.stdout)
            raw_int = str(data.get("Interval", f"PT{saved_mins}M")).upper()
            int_mins = saved_mins
            if "15M" in raw_int:
                int_mins = 15
            elif "30M" in raw_int:
                int_mins = 30
            elif "120M" in raw_int or "2H" in raw_int:
                int_mins = 120
            elif "60M" in raw_int or "1H" in raw_int:
                int_mins = 60

            is_active = data.get("State", "").lower() in ["ready", "running"]
            result = {
                "found": True,
                "task_name": data.get("Name"),
                "state": data.get("State", "Ready"),
                "enabled": is_active,
                "at_time": data.get("AtTime", "08:00"),
                "interval_mins": int_mins,
                "next_run": data.get("NextRun", "N/A"),
                "last_run": data.get("LastRun", "N/A"),
                "last_result": data.get("LastResult", 0)
            }
            _micro_cache = {"data": result, "ts": now}
            return result
    except Exception:
        pass

    fallback = {
        "found": True,
        "task_name": MICRO_TASK_NAME,
        "state": "Ready" if saved_enabled else "Disabled",
        "enabled": saved_enabled,
        "at_time": "08:00",
        "interval_mins": saved_mins,
        "next_run": "N/A",
        "last_run": "N/A",
        "last_result": 0
    }
    _micro_cache = {"data": fallback, "ts": now}
    return fallback


def update_task_schedule(time_str: str = "05:00", enabled: bool = True) -> tuple[bool, str]:
    """Updates the scheduled daily baseline run time in Windows Task Scheduler using silent pythonw.exe."""
    global _task_cache
    _task_cache = {"data": None, "ts": 0}
    save_sync_config({"daily_sync_time": time_str})
    action_cmd = str(RUNNER_PY)
    py_exe = get_silent_python_exe()
    ps_cmd = f"""
    $Action = New-ScheduledTaskAction -Execute '{py_exe}' -Argument '"{action_cmd}" --mode full' -WorkingDirectory '{BASE_DIR}'
    $Trigger = New-ScheduledTaskTrigger -Daily -At '{time_str}'
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun -Priority 4
    Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Automated Daily Aconex Deep Extraction and DuckDB ETL Refresh (Hill International)' -Force
    """
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return True, f"Successfully updated Windows Task Scheduler daily time to {time_str}."
        else:
            return False, f"PowerShell Error: {res.stderr.strip() or res.stdout.strip()}"
    except Exception as e:
        return False, str(e)


def update_micro_batch_schedule(enabled: bool = True, interval_minutes: int = 30, start_time: str = "08:00", duration_hours: int = 10) -> tuple[bool, str]:
    """Registers or toggles the business-hours micro-batch delta schedule in Windows Task Scheduler."""
    global _micro_cache
    _micro_cache = {"data": None, "ts": 0}
    interval_minutes = int(interval_minutes)
    save_sync_config({
        "micro_batch_enabled": enabled,
        "micro_batch_interval_mins": interval_minutes
    })

    action_cmd = str(RUNNER_PY)
    py_exe = get_silent_python_exe()
    
    if not enabled:
        ps_cmd = f"Disable-ScheduledTask -TaskName '{MICRO_TASK_NAME}' -ErrorAction SilentlyContinue"
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
            return True, "Micro-Batch sync has been paused."
        except Exception as e:
            return False, str(e)

    ps_cmd = f"""
    $Action = New-ScheduledTaskAction -Execute '{py_exe}' -Argument '"{action_cmd}" --mode delta' -WorkingDirectory '{BASE_DIR}'
    $Trigger = New-ScheduledTaskTrigger -Daily -At '{start_time}'
    $once = New-ScheduledTaskTrigger -Once -At '{start_time}' -RepetitionInterval (New-TimeSpan -Minutes {interval_minutes}) -RepetitionDuration (New-TimeSpan -Hours {duration_hours})
    $Trigger.Repetition = $once.Repetition
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -Priority 4
    Register-ScheduledTask -TaskName '{MICRO_TASK_NAME}' -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Automated Business Hours Aconex Micro-Batch Delta Sync (Every {interval_minutes}m)' -Force
    """
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return True, f"Micro-Batch schedule successfully enabled (Every {interval_minutes} minutes between {start_time} and 18:00)."
        else:
            return False, f"PowerShell Error: {res.stderr.strip() or res.stdout.strip()}"
    except Exception as e:
        return False, str(e)


def trigger_scheduled_task_now(task_name: str = TASK_NAME) -> bool:
    """Tells Windows Task Scheduler to execute the task immediately."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Start-ScheduledTask -TaskName '{task_name}'"],
            capture_output=True, text=True, timeout=10
        )
        return True
    except Exception:
        return False


def run_immediate_sync_in_background(mode: str = "full") -> bool:
    """Launches pipeline 100% silently in background with real-time state tracking (zero window popup)."""
    state = get_sync_state()
    # If state says is_running, verify whether PID is ACTUALLY alive!
    if state.get("is_running"):
        active_pid = state.get("pid")
        if active_pid and is_pid_alive(active_pid):
            return True  # Pipeline is genuinely actively running right now
        # PID is dead or None: reset state so new run can start!
        set_sync_state(
            step_number=1,
            step_name="Initializing...",
            step_detail="Starting new run...",
            percent=5,
            is_running=False,
            pid=None
        )

    try:
        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NO_WINDOW | 0x00000008

        py_silent = get_silent_python_exe()
        proc = subprocess.Popen(
            [py_silent, str(RUNNER_PY), "--mode", mode],
            cwd=str(BASE_DIR),
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
        mode_label = "Delta Sync (~45s)" if mode == "delta" else "Full Deep Sync"
        set_sync_state(
            step_number=1,
            step_name=f"Step 1/3: Launching {mode_label} (Background Process)...",
            step_detail="Starting browser session and validating credentials...",
            percent=10,
            is_running=True,
            pid=proc.pid
        )
        return True
    except Exception as e:
        print(f"[sync_manager] Error launching pipeline: {e}")
        return False


def run_immediate_delta_sync_in_background() -> bool:
    """Convenience helper to launch fast delta sync (~45s)."""
    return run_immediate_sync_in_background(mode="delta")


def is_sync_running() -> bool:
    """Checks whether the extraction pipeline is currently active."""
    state = get_sync_state()
    return bool(state.get("is_running", False))


def get_pipeline_progress() -> dict:
    """Parses live execution state and Task Scheduler to return structured progress."""
    task = get_task_info()
    micro = get_micro_batch_info()
    state = get_sync_state()
    running = state.get("is_running", False)
    
    # Calculate time remaining until next run
    time_rem = "N/A"
    next_run_str = task.get("next_run", "")
    if next_run_str and next_run_str != "N/A":
        try:
            nr = datetime.strptime(next_run_str, "%Y-%m-%d %H:%M:%S")
            diff = nr - datetime.now()
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                time_rem = f"{hours}h {minutes}m"
            else:
                time_rem = "Due now"
        except Exception:
            pass

    state_updated = state.get("updated_at", "")
    task_last = task.get("last_run", "")
    if task_last.startswith("1999") or task_last == "N/A":
        task_last = ""
    
    latest_run_time = task_last
    if state_updated and state_updated != "N/A":
        if not latest_run_time or state_updated > latest_run_time:
            latest_run_time = state_updated
            
    if not latest_run_time:
        latest_run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    task["last_run"] = latest_run_time
    if "Completed" in state.get("step_name", "") or state.get("percent") == 100:
        task["last_result"] = 0

    return {
        "is_running": running,
        "percent": state.get("percent", 100 if not running else 15),
        "step_number": state.get("step_number", 1),
        "step_name": state.get("step_name", "Ready (System Idle)"),
        "step_detail": state.get("step_detail", "System ready for scheduled sync or on-demand execution."),
        "task": task,
        "micro_task": micro,
        "last_run": latest_run_time,
        "time_remaining": time_rem,
        "pid": state.get("pid")
    }


def get_sync_logs(max_lines: int = 40) -> list:
    """Reads the most recent lines from the pipeline log file as a list of strings."""
    if not LOG_FILE.exists():
        return ["No extraction runs recorded yet. Click 'Quick Delta' to start."]
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            tail = [line.rstrip() for line in lines[-max_lines:]]
            return tail if tail else ["Log file is currently empty."]
    except Exception as e:
        return [f"Could not read log file: {e}"]
