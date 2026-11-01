"""
Aconex Automated Data Extractor (Ras El Hekma Project ID: 1744833878)
=====================================================================
Automates full daily extraction of:
1. Document Register (ExportDocs-*.xlsx in parts from Temporary Files zip)
2. Mail Register (ExportMailAll-*.xlsx from Mail Search -> Export to Excel)
3. Standard BI Reports (Mail Response, Mail Thread, Workflow Status, 
   Document Transmittal Workflow, Workflow Documents Review Outcome)

All outputs are saved to 'output_data' for verification before ingestion.
"""

import os
import sys
import time
import zipfile
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import config

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.BASE_DIR / "extractor.log", encoding="utf-8")
    ]
)
log = logging.getLogger("AconexExtractor")

SCREENSHOTS_DIR = config.BASE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def take_snapshot(page, name):
    try:
        path = SCREENSHOTS_DIR / f"{name}_{int(time.time())}.png"
        page.screenshot(path=str(path))
        log.info(f"Snapshot saved: {path.name}")
        return path
    except Exception as e:
        log.warning(f"Could not save snapshot: {e}")
        return None


def ensure_login(page, context):
    """
    Ensures authentication into Aconex Hub with auto-login via Oracle Cloud SSO.
    """
    log.info("Navigating to Aconex Hub...")
    page.goto(config.URL_DOCUMENTS, timeout=90000)

    log.info("Checking authentication state (waiting for Oracle SSO or Aconex Hub)...")
    logged_in = False

    for i in range(45):
        time.sleep(1)
        cur_url = page.url.lower()

        # Oracle Cloud login form
        if page.locator("input[type='password']").count() > 0 or "oraclecloud" in cur_url or "idcslogin" in cur_url:
            log.info(f"[{i}s] Oracle Cloud Login Form Detected! URL: {page.url}")
            time.sleep(2)
            take_snapshot(page, "01_oracle_login_form")

            user_inp = page.locator("input[name='username'], input[type='text']")
            if user_inp.count() > 0 and user_inp.first.is_visible():
                if not user_inp.first.input_value() and config.ACONEX_USERNAME:
                    log.info(f"Filling username: {config.ACONEX_USERNAME}")
                    user_inp.first.fill(config.ACONEX_USERNAME)
                    time.sleep(0.5)

            pwd_inp = page.locator("input[type='password']")
            if pwd_inp.count() > 0 and pwd_inp.first.is_visible():
                if config.ACONEX_PASSWORD:
                    log.info("Auto-entering password from .env...")
                    pwd_inp.first.fill(config.ACONEX_PASSWORD)
                    time.sleep(1)
                else:
                    log.warning("No ACONEX_PASSWORD configured in .env!")

            signin_btn = page.locator("button:has-text('Sign In'), input[value='Sign In']")
            if signin_btn.count() > 0 and signin_btn.first.is_visible():
                log.info("Clicking Sign In button...")
                signin_btn.first.click()
                time.sleep(4)
                take_snapshot(page, "02_after_signin_click")

        # Check if Aconex Hub workspace loaded
        if "mea.aconex.com" in cur_url and "authentication/index.html" not in cur_url:
            log.info(f"[{i}s] Landed on Aconex Hub! URL: {page.url}")
            logged_in = True
            break
        if page.locator("text='ORACLE Aconex'").count() > 0 or page.locator("text='Ras El Hekma'").count() > 0:
            log.info(f"[{i}s] Aconex navigation bar detected!")
            logged_in = True
            break

    if not logged_in:
        log.error("Failed to reach Aconex Hub.")
        take_snapshot(page, "login_failed_timeout")
        return False

    log.info("Waiting 10s for Aconex Hub workspace to settle...")
    time.sleep(10)
    take_snapshot(page, "03_aconex_workspace_settled")

    try:
        context.storage_state(path=str(config.PROFILE_DIR / "storage_state.json"))
        log.info("Session storage state saved successfully.")
    except Exception as e:
        log.warning(f"Note on saving storage state: {e}")

    return True


def download_temp_file_by_name(page, file_prefix, output_dir=config.OUTPUT_DIR, max_wait_sec=600):
    """
    Navigates to Temporary Files, filters by file_prefix, downloads the file,
    and extracts it if it is a ZIP archive.
    """
    log.info(f"Navigating to Temporary Files to locate: {file_prefix}...")
    nav_btn = page.locator("#nav-bar-DOC-DOC-UNREG")
    if not nav_btn.is_visible():
        page.locator("a:has-text('Documents')").first.click()
        time.sleep(1)
    nav_btn.click()
    time.sleep(8)

    frame = page.frame(name="main")
    if not frame:
        log.error("Content frame 'main' not found.")
        return None

    # Search by prefix
    search_input = frame.locator("input[placeholder*='document'], input.search-input, input[type='text']").first
    search_input.fill(file_prefix)
    time.sleep(1)
    frame.locator("button:has-text('Search'), input[value='Search']").first.click()
    log.info(f"Filtered Temporary Files by '{file_prefix}'. Waiting 8s for results...")
    time.sleep(8)

    # Locate download icon
    dl_icon = frame.locator("img[title='Download File'], [col-id='filetype'] img").first
    if dl_icon.count() == 0:
        log.warning(f"File matching '{file_prefix}' is not ready in Temporary Files yet.")
        return None

    log.info(f"Found download icon for {file_prefix}. Initiating download...")
    with page.expect_download(timeout=300000) as dl_info:
        dl_icon.click()
        log.info("Download clicked! Streaming from Aconex...")

    download = dl_info.value
    target_path = os.path.join(output_dir, download.suggested_filename)
    download.save_as(target_path)
    size_mb = os.path.getsize(target_path) / (1024 * 1024)
    log.info(f"[SUCCESS] Downloaded: {target_path} ({size_mb:.2f} MB)")

    # If ZIP, automatically extract all parts
    if target_path.endswith(".zip"):
        log.info("Extracting ZIP contents...")
        with zipfile.ZipFile(target_path, 'r') as z:
            for f in z.namelist():
                extracted = z.extract(f, output_dir)
                p_size = os.path.getsize(extracted) / (1024 * 1024)
                log.info(f"  - Extracted: {f} ({p_size:.2f} MB)")
        log.info("All parts extracted successfully.")

    return target_path


def trigger_mail_export(page):
    """
    Navigates to Mail Search, clicks Export to Excel, and selects 'Row per recipient'.
    """
    log.info("Navigating to Mail Search (All Mail)...")
    mail_nav = page.locator("#nav-bar-CORRESPONDENCE-CORRESPONDENCE-SEARCHALL")
    if not mail_nav.is_visible():
        page.locator("a:has-text('Mail')").first.click()
        time.sleep(1)
    mail_nav.click()
    time.sleep(8)

    frame = page.frame(name="main")
    if not frame:
        log.error("Could not find mail frame.")
        return False

    btn = frame.locator("button:has-text('Export to Excel')").first
    if btn.count() == 0:
        log.error("Could not find 'Export to Excel' button in Mail Search.")
        return False

    log.info("Clicking 'Export to Excel' button...")
    btn.click()
    time.sleep(2)

    # Click "Row per recipient"
    recipient_btn = frame.locator(".exportToExcelPanel button:has-text('Row per recipient')").first
    if recipient_btn.count() > 0:
        log.info("Clicking 'Row per recipient' export option...")
        recipient_btn.click()
        time.sleep(3)
        take_snapshot(page, "mail_export_started")
        log.info("[SUCCESS] Mail Export job started in background.")
        return True
    else:
        log.warning("Row per recipient button not found in modal.")
        return False


def run_bi_report(page, report_id, report_name, output_dir=config.OUTPUT_DIR):
    """
    Navigates to BI Reporting Service, runs the report, and downloads CSV.
    """
    log.info(f"Opening BI Report: {report_name} (ID: {report_id})...")
    page.locator("#nav-bar-REPORTING").click()
    time.sleep(1)
    page.locator("#nav-bar-REPORTING-REPORTING-BIPREPORTSERVICE").click()
    time.sleep(8)

    frame = page.frame(name="main")
    if not frame:
        log.error("Could not find BI Reporting frame.")
        return None

    rep_link = frame.locator(f"a[data-report-id='{report_id}']").first
    if rep_link.count() == 0:
        log.error(f"Report link for {report_name} (ID: {report_id}) not found.")
        return None

    rep_link.click()
    log.info(f"Clicked report '{report_name}'. Waiting for processing...")

    # Handle 'Keep waiting' if background modal appears
    for _ in range(12):
        time.sleep(5)
        keep_waiting = frame.locator("button:has-text('Keep waiting'), #keep_waiting")
        if keep_waiting.count() > 0 and keep_waiting.is_visible():
            log.info("Modal 'Running this report in the background' appeared. Clicking 'Keep waiting'...")
            keep_waiting.click()
            break

    # Wait for #loading to disappear and #export to appear
    log.info("Waiting for report results and Export button...")
    export_btn = frame.locator("#export")
    for sec in range(0, 180, 5):
        time.sleep(5)
        is_loading = frame.locator("#loading").is_visible()
        if not is_loading and export_btn.is_visible():
            log.info(f"Report ready in {sec}s!")
            break

    if not export_btn.is_visible():
        log.warning(f"Report '{report_name}' timed out or needs background retrieval.")
        return None

    # Click Export As -> CSV
    log.info("Clicking Export As...")
    export_btn.click()
    time.sleep(2)

    csv_opt = frame.locator("a:has-text('CSV'), [data-format='csv']").first
    if csv_opt.count() > 0:
        with page.expect_download(timeout=60000) as dl_info:
            csv_opt.click()
            log.info("CSV export clicked, downloading...")
        download = dl_info.value
        out_path = os.path.join(output_dir, download.suggested_filename)
        download.save_as(out_path)
        log.info(f"[SUCCESS] Downloaded BI Report: {out_path} ({os.path.getsize(out_path):,} bytes)")
        return out_path
    else:
        log.warning("CSV format option not found in Export menu.")
        return None


def run_pipeline():
    """
    Main execution pipeline.
    """
    log.info("======================================================================")
    log.info("       ACONEX AUTOMATED EXTRACTION PIPELINE STARTING                  ")
    log.info(f"Target Output: {config.OUTPUT_DIR}")
    log.info(f"Project ID:    {config.PROJECT_ID}")
    log.info("======================================================================")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(config.PROFILE_DIR),
            headless=True,
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        if not ensure_login(page, ctx):
            ctx.close()
            return False

        # Phase 1: Document Register
        log.info("\n--- PHASE 1: Document Register ---")
        today_str = time.strftime("%Y%m%d")
        download_temp_file_by_name(page, today_str)

        # Phase 2: Mail Register Export
        log.info("\n--- PHASE 2: Mail Register ---")
        trigger_mail_export(page)

        # Phase 3: BI Reports
        log.info("\n--- PHASE 3: BI Reports ---")
        reports = [
            ("351510", "Workflow Status"),
            ("445707", "Mail Response"),
            ("445709", "Mail Thread"),
            ("351516", "Document Transmittal Workflow"),
            ("546201", "Workflow Documents Review Outcome")
        ]
        for rep_id, rep_name in reports:
            try:
                run_bi_report(page, rep_id, rep_name)
            except Exception as e:
                log.warning(f"Could not finish BI report {rep_name}: {e}")

        ctx.close()
        log.info("Pipeline run completed. Check output_data for results.")
        return True


if __name__ == "__main__":
    run_pipeline()
