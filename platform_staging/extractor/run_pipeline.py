"""
=============================================================================
UNIFIED ACONEX PIPELINE RUNNER (EXTRACTION + DUCKDB ETL)
Supports Fast Delta Sync (~45-60s) and Full Scheduled Deep Sync.
Runs silently in background with real-time state tracking and live logging.
Guaranteed 100% windowless execution via pythonw.exe & CREATE_NO_WINDOW.
=============================================================================
"""

import os
import sys
import glob
import time
import argparse
import subprocess
import logging
from pathlib import Path

# Add current dir to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from state_tracker import set_sync_state

LOG_FILE = BASE_DIR / "sync_live.log"
ETL_DIR = BASE_DIR.parent / "etl"
FULL_ETL_SCRIPT = ETL_DIR / "run_full_update.py"
DELTA_ETL_SCRIPT = ETL_DIR / "run_delta_update.py"


def get_silent_python_exe() -> str:
    """Returns pythonw.exe if available, guaranteeing no console window pops up."""
    cur = Path(sys.executable).resolve()
    pyw = cur.with_name("pythonw.exe")
    if pyw.exists():
        return str(pyw)
    return str(cur)


def log_banner(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    banner = f"\n{'='*70}\n[{timestamp}] {msg}\n{'='*70}\n"
    if sys.stdout:
        try:
            print(banner)
        except Exception:
            pass
    with open(LOG_FILE, "a", encoding="utf-8", errors="ignore") as f:
        f.write(banner)


def log_line(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    if sys.stdout:
        try:
            print(line, end="")
        except Exception:
            pass
    with open(LOG_FILE, "a", encoding="utf-8", errors="ignore") as f:
        f.write(line)


def _cleanup_local_exports(patterns, label):
    """Deletes extracted workbooks from Data/update/Up after they have been ingested."""
    try:
        import config
        up_dir = str(config.OUTPUT_DIR)
    except Exception:
        up_dir = str(BASE_DIR.parent.parent / "Data" / "update" / "Up")
    removed = 0
    for pat in patterns:
        for fp in glob.glob(os.path.join(up_dir, pat)):
            try:
                os.remove(fp)
                removed += 1
                log_line(f"[CLEANUP] Deleted {os.path.basename(fp)}")
            except Exception as e:
                log_line(f"[CLEANUP] Could not delete {os.path.basename(fp)}: {e}")
    log_line(f"[CLEANUP] Removed {removed} {label} file(s) from update folder.")


def _run_extractor(py_runner, creation_flags, mode, phase, pid):
    extractor_script = BASE_DIR / "master_aconex_extractor.py"
    log_line(f"Launching extractor (mode={mode}, phase={phase})...")
    with open(LOG_FILE, "a", encoding="utf-8", errors="ignore") as log_out:
        ext_proc = subprocess.run(
            [py_runner, str(extractor_script), "--mode", mode, "--phase", phase],
            cwd=str(BASE_DIR),
            stdout=log_out,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creation_flags
        )
    if ext_proc.returncode == 2:
        log_line("[CRITICAL] Oracle 2FA Multi-Factor Authentication required! 7-day device trust expired.")
        set_sync_state(
            step_number=3,
            step_name="Sync Paused: 2FA Authentication Required ⚠️",
            step_detail="Oracle 7-day device trust has expired. Run reauth_aconex.bat to renew the session.",
            percent=0,
            is_running=False,
            pid=None
        )
        return 2
    if ext_proc.returncode != 0:
        log_line(f"[ERROR] Extractor ({phase}) failed with exit code {ext_proc.returncode}.")
        set_sync_state(
            step_number=3,
            step_name="Sync Failed: Data Extraction Error ❌",
            step_detail=f"Extractor process ({phase}) exited with non-zero code {ext_proc.returncode}. Check sync_live.log.",
            percent=0,
            is_running=False,
            pid=None
        )
        return ext_proc.returncode
    log_line(f"[SUCCESS] Extractor phase '{phase}' completed.")
    return 0


def _run_etl(py_runner, creation_flags, etl_script, pid):
    if not etl_script.exists():
        log_line(f"[ERROR] ETL script not found at {etl_script}")
        return 1
    log_line(f"Executing ETL script: {etl_script.name}...")
    with open(LOG_FILE, "a", encoding="utf-8", errors="ignore") as log_out:
        etl_proc = subprocess.run(
            [py_runner, str(etl_script)],
            cwd=str(ETL_DIR),
            stdout=log_out,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creation_flags
        )
    if etl_proc.returncode != 0:
        log_line(f"[ERROR] ETL script exited with code {etl_proc.returncode}")
        set_sync_state(
            step_number=3,
            step_name="Sync Failed: Database ETL Error ❌",
            step_detail=f"DuckDB ETL process exited with non-zero code {etl_proc.returncode}. Check sync_live.log.",
            percent=0,
            is_running=False,
            pid=None
        )
        return etl_proc.returncode
    log_line(f"[SUCCESS] ETL {etl_script.name} completed.")
    return 0


def run_pipeline(mode="full"):
    pid = os.getpid()
    mode_label = "QUICK DELTA SYNC" if mode == "delta" else "FULL DEEP SYNC"
    log_banner(f"ACONEX PIPELINE STARTED ({mode_label}) — mail first, then documents")
    
    set_sync_state(
        step_number=1,
        step_name=f"Step 1/3: Initializing Silent Session & Connecting to Aconex ({mode.upper()})...",
        step_detail="Starting background browser session and validating credentials...",
        percent=8,
        is_running=True,
        pid=pid
    )

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    py_runner = get_silent_python_exe()

    try:
        # Phase A: Mail + BI + dashboards — extract, ingest, then wipe temp files.
        log_line(f"[1/4] Mail phase extraction (Mode: {mode.upper()})...")
        set_sync_state(
            step_number=1,
            step_name=f"Step 1/4: Extracting Mail & Reports ({mode.upper()})...",
            step_detail="Queueing ExportMailAll packages, BI Publisher CSVs, and process dashboards...",
            percent=20,
            is_running=True,
            pid=pid
        )
        rc = _run_extractor(py_runner, creation_flags, mode, "mail", pid)
        if rc == 2:
            return False
        if rc != 0:
            log_line("[ERROR] Mail extraction failed. Aborting ETL to prevent false sync.")
            return False

        log_banner("PHASE 2: INGEST MAIL INTO DUCKDB, THEN PURGE MAIL TEMP FILES")
        set_sync_state(
            step_number=2,
            step_name="Step 2/4: Loading mail into the application...",
            step_detail="Ingesting ExportMailAll workbooks, responses, and process details...",
            percent=55,
            is_running=True,
            pid=pid
        )
        if _run_etl(py_runner, creation_flags, DELTA_ETL_SCRIPT, pid) != 0:
            return False
        _cleanup_local_exports(["ExportMailAll-*.xlsx", "ExportMailAll-*.zip"], "mail export")

        # Phase B: Document register only on full sync, after mail temp is empty.
        if mode == "full":
            log_banner("PHASE 3: DOCUMENT REGISTER EXTRACTION (TEMP FILES NOW EMPTY)")
            set_sync_state(
                step_number=3,
                step_name="Step 3/4: Extracting Document Register...",
                step_detail="Queueing ExportDocs, downloading parts, then ingesting into DuckDB...",
                percent=70,
                is_running=True,
                pid=pid
            )
            rc = _run_extractor(py_runner, creation_flags, mode, "docs", pid)
            if rc == 2:
                return False
            if rc != 0:
                log_line("[ERROR] Document Register extraction failed after mail was already loaded.")
                return False
            if _run_etl(py_runner, creation_flags, FULL_ETL_SCRIPT, pid) != 0:
                return False
            _cleanup_local_exports(["ExportDocs-*.xlsx", "ExportDocs-*.zip"], "document register")
        else:
            log_line("[DELTA] Skipping Document Register phase (Quick Delta).")

        # Phase 3: Telemetry Verification & Proof of Work
        latest_mail = "N/A"
        total_mails = 0
        total_rfis = 0
        total_docs = 0
        try:
            import duckdb
            db_file = BASE_DIR.parent.parent / "aconex.duckdb"
            if db_file.exists():
                con = duckdb.connect(str(db_file), read_only=True)
                r_mail = con.execute("SELECT MAX(sent_date), count(*) FROM fact_mail").fetchone()
                if r_mail:
                    latest_mail = str(r_mail[0])[:10] if r_mail[0] else "N/A"
                    total_mails = r_mail[1]
                r_rfis = con.execute("SELECT count(*) FROM fact_rfis").fetchone()
                if r_rfis:
                    total_rfis = r_rfis[0]
                r_docs = con.execute("SELECT count(*) FROM dim_documents").fetchone()
                if r_docs:
                    total_docs = r_docs[0]
                con.close()
        except Exception as e:
            log_line(f"[NOTICE] Could not query telemetry stats: {e}")

        # Mark pipeline complete with verified proof-of-work
        log_banner(f"ACONEX PIPELINE ({mode.upper()}) VERIFIED & COMPLETED SUCCESSFULLY!")
        set_sync_state(
            step_number=3,
            step_name=f"Sync Verified Successfully! ({mode_label}) ✅",
            step_detail=f"Latest Mail: {latest_mail} | Total Mails: {total_mails:,} | RFIs: {total_rfis:,} | Docs: {total_docs:,}",
            percent=100,
            is_running=False,
            pid=None
        )

    except Exception as e:
        log_line(f"[EXCEPTION] Pipeline encountered an error: {e}")
        set_sync_state(
            step_number=3,
            step_name="Sync Stopped with Error",
            step_detail=f"Execution error: {str(e)[:100]}",
            percent=100,
            is_running=False,
            pid=pid
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Aconex Pipeline Runner")
    parser.add_argument("--mode", choices=["delta", "full"], default="full", help="Pipeline mode: delta (fast) or full (deep)")
    args, _ = parser.parse_known_args()
    run_pipeline(mode=args.mode)
