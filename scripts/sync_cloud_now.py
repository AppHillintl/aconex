import os
import sys
import time
import requests
from pathlib import Path

# Add scripts dir to path to import export_cloud_duckdb
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from export_cloud_duckdb import build_cloud_database_and_zip

RENDER_URL = os.environ.get("RENDER_APP_URL", "https://aconex.onrender.com")
SYNC_SECRET = os.environ.get("HILL_SYNC_SECRET", "HILL_REH_SYNC_SECRET_2026")

def push_to_render_cloud(render_url=None, sync_secret=None, logger=None):
    """
    Exports clean cloud snapshot from local aconex.duckdb, compresses it,
    and sends it via secure HTTP POST to Render (https://aconex.onrender.com).
    Triggers an instant, zero-downtime hot reload on the cloud dashboard!
    """
    url = (render_url or RENDER_URL).rstrip("/")
    secret = sync_secret or SYNC_SECRET
    
    def log(msg):
        if logger:
            logger(msg)
        else:
            try:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
            except UnicodeEncodeError:
                safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {safe_msg}")

    log("=" * 70)
    log(f"[SYNC] INITIATING INSTANT CLOUD SYNC TO RENDER ({url})")
    log("=" * 70)

    t0 = time.time()
    try:
        # Step 1: Export & Compress
        log("[1/2] Exporting clean dashboard snapshot & compressing...")
        zip_path = build_cloud_database_and_zip()
        zip_mb = zip_path.stat().st_size / (1024 * 1024)
        log(f"      Snapshot ready: {zip_mb:.2f} MB")

        # Step 2: Upload to Render
        log(f"[2/2] Uploading to {url}/api/sync/cloud-push...")
        endpoint = f"{url}/api/sync/cloud-push"
        headers = {"x-sync-secret": secret}
        
        with open(zip_path, "rb") as f:
            resp = requests.post(
                endpoint,
                files={"file": ("aconex_cloud.duckdb.zip", f, "application/zip")},
                headers=headers,
                timeout=300
            )

        if resp.status_code == 200:
            data = resp.json()
            elapsed = time.time() - t0
            log(f"[OK] SUCCESS: Render Cloud is 100% updated and hot-reloaded in {elapsed:.1f}s!")
            log(f"   Cutoff Date: {data.get('cutoff_date')} | Total Mails: {data.get('total_mails'):,} | RFIs: {data.get('total_rfis'):,} | Docs: {data.get('total_docs'):,}")
            log("=" * 70)
            return True, data
        else:
            log(f"[ERROR] Render returned status {resp.status_code}: {resp.text[:300]}")
            return False, resp.text
            
    except Exception as e:
        log(f"[EXCEPTION] during cloud sync: {e}")
        return False, str(e)

if __name__ == "__main__":
    push_to_render_cloud()
