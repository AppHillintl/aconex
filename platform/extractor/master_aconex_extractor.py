try:
    from state_tracker import set_sync_state
except Exception:
    def set_sync_state(*args, **kwargs): pass
"""
=============================================================================
ORACLE ACONEX MASTER AUTOMATED EXTRACTION PIPELINE
Project: Ras El Hekma (Project ID: 1744833878)
Target Directory: output_data/
=============================================================================
This script provides 100% automated end-to-end extraction of:
  1. Document Register: Multi-part Excel files (ExportDocs-*.xlsx)
  2. All 6 BI Publisher CSV Reports:
     - Document Transmittal Workflow (1).csv
     - Mail Response (2).csv
     - Mail Thread (2).csv
     - Workflow Status (1).csv
     - Workflow Documents Review Outcome (1).csv
     - Project Directory.csv (Clean CSV table with all users & orgs)
  3. Mail Register: 7 Saved Searches bundles (Row per recipient)
     - Automatically queued & downloaded from Temporary Files
  4. Dashboard Process Details Reports (Oracle Analytics):
     - Request for Information (RFI) -> 0006_PROCESS DETAILS TABLE MD2.xlsx
     - Safety NCR (HSNCR)           -> 0006_PROCESS DETAILS TABLE MD2 (1).xlsx
     - Non-Conformance (NCR)        -> 0006_PROCESS DETAILS TABLE MD2 (2).xlsx
     - Safety SOR (HSE)             -> 0006_PROCESS DETAILS TABLE MD2 (3).xlsx
     - Transmittal (TRANSMITTAL)    -> 0006_PROCESS DETAILS TABLE MD2 (4).xlsx
  5. Disk space conservation: Automatic extraction and removal of zip archives.
=============================================================================
"""

import os
import sys
import glob
import time
import zipfile
import csv
import logging
import urllib.parse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("master_extractor.log", mode="a", encoding="utf-8")
    ]
)
log = logging.getLogger("MasterExtractor")

# -----------------------------------------------------------------------------
# CONFIGURATION TARGETS
# -----------------------------------------------------------------------------
BIP_REPORT_TARGETS = [
    {"name": "Document Transmittal Workflow python", "result_id": "2534124", "filename": "Document Transmittal Workflow (1).csv"},
    {"name": "Mail Response python",                 "result_id": "2534121", "filename": "Mail Response (2).csv"},
    {"name": "Mail Thread python",                   "result_id": "2534122", "filename": "Mail Thread (2).csv"},
    {"name": "Workflow Status python",                "result_id": "2533941", "filename": "Workflow Status (1).csv"},
    {"name": "Workflow Documents Review Outcome",     "result_id": "2534130", "filename": "Workflow Documents Review Outcome (1).csv"},
    {"name": "Project Directory Python",             "result_id": "2534137", "filename": "Project Directory.csv", "is_html": True}
]

DASHBOARD_PROCESS_TARGETS = [
    {"name": "Request for Information (RFI)", "filename": "0006_PROCESS DETAILS TABLE MD2.xlsx",     "label": "RFI"},
    {"name": "Safety NCR",                   "filename": "0006_PROCESS DETAILS TABLE MD2 (1).xlsx", "label": "HSNCR"},
    {"name": "Non-Conformance",              "filename": "0006_PROCESS DETAILS TABLE MD2 (2).xlsx", "label": "NCR"},
    {"name": "Safety SOR",                   "filename": "0006_PROCESS DETAILS TABLE MD2 (3).xlsx", "label": "HSE"},
    {"name": "Transmittal",                  "filename": "0006_PROCESS DETAILS TABLE MD2 (4).xlsx", "label": "TRANSMITTAL"}
]


def ensure_login(page, context):
    """Logs into Aconex Hub via Oracle Cloud SSO if session is not active."""
    log.info("Checking authentication state on Aconex Hub...")
    page.goto(config.URL_DOCUMENTS, timeout=90000)
    
    for i in range(40):
        time.sleep(1)
        cur_url = page.url.lower()
        
        # Check for 2FA challenge screen (device trust expired)
        if "signin-security" in cur_url or "two-step" in cur_url or page.locator("text='Two-Step Verification'").count() > 0 or page.locator("text='Enter Passcode'").count() > 0:
            log.error("[AUTH_REQUIRED] Oracle 2FA Multi-Factor Authentication required. 7-day device trust expired.")
            sys.exit(2)
        
        # Detect Oracle SSO form
        if page.locator("input[type='password']").count() > 0 or "oraclecloud" in cur_url or "idcslogin" in cur_url:
            log.info("Oracle SSO login detected. Entering credentials...")
            time.sleep(2)
            user_inp = page.locator("input[name='username'], input[type='text']")
            if user_inp.count() > 0 and user_inp.first.is_visible():
                if not user_inp.first.input_value() and config.ACONEX_USERNAME:
                    user_inp.first.fill(config.ACONEX_USERNAME)
                    time.sleep(0.5)
            pwd_inp = page.locator("input[type='password']")
            if pwd_inp.count() > 0 and pwd_inp.first.is_visible() and config.ACONEX_PASSWORD:
                pwd_inp.first.fill(config.ACONEX_PASSWORD)
                time.sleep(1)
            btn = page.locator("button:has-text('Sign In'), input[value='Sign In']")
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                time.sleep(4)
                
        if "mea.aconex.com" in cur_url and "authentication/index.html" not in cur_url:
            log.info(f"Successfully authenticated on Aconex Hub! ({page.url})")
            time.sleep(5)
            return True
            
    if "mea.aconex.com" not in page.url.lower() or "authentication/index.html" in page.url.lower():
        log.error(f"[AUTH_FAILED] Could not authenticate on Aconex Hub. Current URL: {page.url}")
        sys.exit(1)
        
    log.warning("Authentication check finished.")
    return True


# -----------------------------------------------------------------------------
# STEP 0: PRE-EXTRACTION CLEANUP (ACONEX & LOCAL SCRATCH)
# -----------------------------------------------------------------------------
def clear_local_scratch():
    """Purges previous temporary downloads while keeping the parsed CSV cache intact."""
    log.info("\n" + "="*80)
    log.info("LOCAL CLEANUP: Purging incomplete temporary downloads...")
    log.info("="*80)
    scratch_dir = getattr(config, "SCRATCH_DIR", None) or os.path.join(config.DATA_DIR, "update", "scratch")
    if os.path.exists(scratch_dir):
        count = 0
        for f in os.listdir(scratch_dir):
            if f.endswith(".downloading") or f.endswith(".tmp"):
                try:
                    fp = os.path.join(scratch_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                        count += 1
                except Exception:
                    pass
        log.info(f"[CLEANUP] Purged {count} temporary download files.")


def clear_aconex_temporary_files(page):
    """
    Cleans up all residual/old temporary files from Aconex backend
    before queueing and extracting new packages.
    """
    log.info("\n" + "="*80)
    log.info("PRE-SYNC CLEANUP: Purging all old Temporary Files in Aconex backend...")
    log.info("="*80)
    try:
        page.locator("#nav-bar-DOC, a:has-text('Documents')").first.click()
        time.sleep(1)
        page.locator("#nav-bar-DOC-DOC-UNREG").click()
        time.sleep(8)
        
        frame = page.frame(name="main")
        if not frame:
            log.warning("Could not access frame 'main' in Temporary Files.")
            return False
            
        s_btn = frame.locator("button:has-text('Search'), input[value='Search']").first
        if s_btn.count() > 0:
            s_btn.click()
            time.sleep(8)
            
        res = frame.evaluate("""() => {
            const form = document.forms[0];
            const inputs = form ? form.querySelectorAll('input[name="selectedIdsInPage"]') : [];
            Array.from(inputs).forEach(inp => inp.checked = true);
            return inputs.length;
        }""")
        
        if res > 0:
            log.info(f"Found {res} old temporary file(s) in Aconex. Purging via doSearch(11)...")
            page.on("dialog", lambda dialog: dialog.accept())
            frame.evaluate("() => { if (typeof doSearch === 'function') doSearch(11); }")
            time.sleep(8)
            log.info("[CLEANUP SUCCESS] Successfully purged old Temporary Files from Aconex backend!")
        else:
            log.info("Aconex Temporary Files is already clean (0 files).")
        return True
    except Exception as e:
        log.warning(f"Error during Aconex Temporary Files purge: {e}")
        return False


# -----------------------------------------------------------------------------
# STEP 1: EXTRACT DOCUMENT REGISTER
# -----------------------------------------------------------------------------
def extract_document_register(page, output_dir=config.OUTPUT_DIR):
    """Locates the latest ExportDocs zip in Temporary Files, downloads and extracts parts."""
    log.info("\n" + "="*80)
    log.info("STEP 1: EXTRACTING DOCUMENT REGISTER (ExportDocs-*.xlsx)")
    log.info("="*80)
    
    page.locator("#nav-bar-DOC, a:has-text('Documents')").first.click()
    time.sleep(1)
    page.locator("#nav-bar-DOC-DOC-UNREG").click()
    time.sleep(8)
    
    frame = page.frame(name="main")
    if not frame:
        log.error("Could not access content frame 'main'.")
        return False
        
    search_term = f"ExportDocs-{time.strftime('%Y%m')}"
    search_inp = frame.locator("input[placeholder*='document'], input.search-input, input[type='text']").first
    search_inp.fill(search_term)
    time.sleep(1)
    frame.locator("button:has-text('Search'), input[value='Search']").first.click()
    log.info(f"Filtered Temporary Files by '{search_term}'. Waiting 8s for results...")
    time.sleep(8)
    
    # Locate all ExportDocs rows and pick the one with the latest timestamp in filename
    best_row_info = frame.evaluate(r'''() => {
        const agRows = Array.from(document.querySelectorAll('.ag-center-cols-container .ag-row, .ag-row'));
        const matches = [];
        agRows.forEach(r => {
            const text = r.innerText.trim();
            const rowIdx = r.getAttribute('row-index');
            const m = text.match(/ExportDocs-(\d{8}_\d{2}-\d{2})/);
            const isZip = text.toLowerCase().includes('.zip') || r.querySelector('img[src*="zip" i], img[title*="ZIP" i]');
            if (m && isZip) {
                matches.push({ rowIdx: parseInt(rowIdx), name: m[0], stamp: m[1] });
            }
        });
        if (matches.length === 0) return null;
        matches.sort((a, b) => b.stamp.localeCompare(a.stamp));
        return matches[0];
    }''')
    
    if not best_row_info:
        log.info("ExportDocs zip not ready yet. Polling Temporary Files...")
        for wait_i in range(24):
            time.sleep(20)
            try:
                frame.locator("button:has-text('Search'), input[value='Search']").first.click()
                time.sleep(5)
            except Exception:
                pass
            best_row_info = frame.evaluate(r'''() => {
                const agRows = Array.from(document.querySelectorAll('.ag-center-cols-container .ag-row, .ag-row'));
                const matches = [];
                agRows.forEach(r => {
                    const text = r.innerText.trim();
                    const rowIdx = r.getAttribute('row-index');
                    const m = text.match(/ExportDocs-(\d{8}_\d{2}-\d{2})/);
                    const isZip = text.toLowerCase().includes('.zip') || r.querySelector('img[src*="zip" i], img[title*="ZIP" i]');
                    const hasDl = r.querySelector('[col-id="filetype"] img, img[title="Download File"]') !== null;
                    if (m && (isZip || hasDl)) {
                        matches.push({ rowIdx: parseInt(rowIdx), name: m[0], stamp: m[1] });
                    }
                });
                if (matches.length === 0) return null;
                matches.sort((a, b) => b.stamp.localeCompare(a.stamp));
                return matches[0];
            }''')
            log.info(f"  [Poll {wait_i+1}/24] ExportDocs ready: {'yes' if best_row_info else 'no'}")
            if best_row_info:
                break
        if not best_row_info:
            log.warning("ExportDocs zip not ready in Temporary Files after polling.")
            return False
        
    # Download all matched ExportDocs packages from today (to support multiple groups)
    all_packages = frame.evaluate(r'''() => {
        const agRows = Array.from(document.querySelectorAll('.ag-center-cols-container .ag-row, .ag-row'));
        const matches = [];
        agRows.forEach(r => {
            const text = r.innerText.trim();
            const rowIdx = r.getAttribute('row-index');
            const m = text.match(/ExportDocs-(\d{8}_\d{2}-\d{2})/);
            const isZip = text.toLowerCase().includes('.zip') || r.querySelector('img[src*="zip" i], img[title*="ZIP" i]');
            const hasDl = r.querySelector('[col-id="filetype"] img, img[title="Download File"]') !== null;
            if (m && (isZip || hasDl)) {
                matches.push({ rowIdx: parseInt(rowIdx), name: m[0], stamp: m[1] });
            }
        });
        return matches;
    }''')

    seen = set()
    unique_pkgs = []
    for pkg in all_packages:
        if pkg['name'] not in seen:
            unique_pkgs.append(pkg)
            seen.add(pkg['name'])

    log.info(f"Found {len(unique_pkgs)} ready ExportDocs package(s) from groups. Starting downloads...")
    for idx, pkg in enumerate(unique_pkgs):
        try:
            log.info(f"\n[{idx+1}/{len(unique_pkgs)}] Downloading ExportDocs package: {pkg['name']} (row {pkg['rowIdx']})...")
            dl_icon = frame.locator(f".ag-row[row-index='{pkg['rowIdx']}'] [col-id='filetype'] img, .ag-row[row-index='{pkg['rowIdx']}'] img[title='Download File']").first
            if dl_icon.count() == 0:
                continue
            with page.expect_download(timeout=300000) as dl_info:
                dl_icon.click()
            dl = dl_info.value
            zip_path = os.path.join(output_dir, dl.suggested_filename)
            dl.save_as(zip_path)
            size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            log.info(f"[SUCCESS] Downloaded: {zip_path} ({size_mb:.2f} MB)")
            
            if zip_path.endswith(".zip"):
                with zipfile.ZipFile(zip_path, 'r') as z:
                    for f in z.namelist():
                        extracted = z.extract(f, output_dir)
                        p_size = os.path.getsize(extracted) / (1024 * 1024)
                        log.info(f"  - Extracted: {f} ({p_size:.2f} MB)")
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"Error downloading {pkg['name']}: {e}")
    log.info("All Document Register packages and parts processed successfully.")
            
    return True


# -----------------------------------------------------------------------------
# STEP 2: EXTRACT ALL 6 BI PUBLISHER CSV REPORTS
# -----------------------------------------------------------------------------
def extract_all_bip_reports(page, context, output_dir=config.OUTPUT_DIR):
    """Captures session authorization & streams all 6 BIP reports directly via HTTP."""
    log.info("\n" + "="*80)
    log.info("STEP 2: EXTRACTING ALL 6 BI PUBLISHER CSV REPORTS")
    log.info("="*80)
    
    captured_headers = {}
    def on_req(req):
        if "reportResult" in req.url:
            captured_headers.update(req.headers)
    page.on("request", on_req)
    
    rep_nav = page.locator("#nav-bar-REPORTING-REPORTING-BIPREPORTSERVICE")
    if not rep_nav.is_visible():
        page.locator("a:has-text('Insights')").first.click()
        time.sleep(1)
    rep_nav.click()
    time.sleep(8)
    
    frame = page.frame(name="main")
    if frame:
        custom_tab = frame.locator("#nav-custom-tab, a:has-text('Custom')").first
        if custom_tab.count() > 0:
            custom_tab.evaluate("el => el.click()")
            time.sleep(2)
            
        row = frame.locator("tr.dataRow:has-text('Document Transmittal Workflow python')").first
        if row.count() > 0:
            row.locator("#contextMenuOptions, button").first.evaluate("el => el.click()")
            time.sleep(1)
            frame.locator("li[data-action='viewHistory']").first.evaluate("el => el.click()")
            time.sleep(4)
            
        # Trigger ajax inside browser to capture the exact headers
        log.info("Capturing live Aconex session token & headers...")
        frame.evaluate('''() => {
            const jq = typeof $ !== 'undefined' ? $ : jQuery;
            jq.ajax({
                url: '/bipreporting-service/reportResult/2534124/true',
                type: 'POST',
                contentType: 'application/json'
            });
        }''')
        time.sleep(3)
        
    cookies = {c['name']: c['value'] for c in context.cookies() if 'aconex.com' in c.get('domain', '')}
    log.info(f"Captured {len(captured_headers)} request headers & {len(cookies)} cookies.")
    
    req_headers = dict(captured_headers)
    req_headers.pop('host', None)
    req_headers.pop('content-length', None)
    
    for rep in BIP_REPORT_TARGETS:
        res_id = rep["result_id"]
        fname = rep["filename"]
        out_file = os.path.join(output_dir, fname)
        url = f"https://mea.aconex.com/bipreporting-service/reportResult/{res_id}/true"
        log.info(f"\n[STREAMING] Fetching {rep['name']} (resultId: {res_id}) -> {fname}...")
        
        temp_out = out_file + ".downloading"
        try:
            r = requests.post(url, headers=req_headers, cookies=cookies, stream=True, timeout=300)
            if r.status_code == 200:
                total = 0
                with open(temp_out, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                            if total % (20*1024*1024) < len(chunk):
                                log.info(f"  Streamed {total/(1024*1024):.1f} MB...")
                
                # Validate that download is real data and not an HTML redirect / login page
                is_valid = True
                with open(temp_out, "rb") as f_chk:
                    sample = f_chk.read(500).lower()
                    if b"<html" in sample or b"<!doctype" in sample or b"url=/logon" in sample:
                        is_valid = False
                
                if total > 1000 and is_valid:
                    if os.path.exists(out_file):
                        try:
                            os.remove(out_file)
                        except Exception:
                            pass
                    os.rename(temp_out, out_file)
                    size_mb = os.path.getsize(out_file) / (1024 * 1024)
                    log.info(f"[SUCCESS] Saved {fname} ({size_mb:.2f} MB)!")
                    if rep.get("is_html"):
                        format_project_directory(out_file)
                else:
                    log.warning(f"[PROTECTION] Downloaded {fname} was an invalid/login redirect ({total} bytes). Preserving existing valid file!")
                    if os.path.exists(temp_out):
                        os.remove(temp_out)
            else:
                log.warning(f"Error fetching {rep['name']}: HTTP {r.status_code}")
        except Exception as e:
            log.error(f"Exception downloading {rep['name']}: {e}")
            if os.path.exists(temp_out):
                try:
                    os.remove(temp_out)
                except Exception:
                    pass


def format_project_directory(file_path):
    """Converts HTML table output of Project Directory into a clean UTF-8 CSV."""
    log.info(f"Formatting Project Directory into clean UTF-8 CSV...")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            
        tables = soup.find_all("table")
        target_table = None
        for t in tables:
            txt = t.get_text()
            if "User Name" in txt or "Organization" in txt:
                target_table = t
                break
        if not target_table and tables:
            target_table = tables[0]
            
        if target_table:
            rows = []
            for tr in target_table.find_all("tr"):
                cells = [td.get_text().strip() for td in tr.find_all(["td", "th"])]
                if cells and any(cells):
                    rows.append(cells)
                    
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            log.info(f"[SUCCESS] Project Directory formatted: {len(rows):,} records ({os.path.getsize(file_path)/1024:.1f} KB).")
    except Exception as e:
        log.warning(f"Could not format Project Directory: {e}")


# -----------------------------------------------------------------------------
# STEP 3: TRIGGER & DOWNLOAD 7 MAIL BUNDLES
# -----------------------------------------------------------------------------
def extract_mail_bundles(page, output_dir=config.OUTPUT_DIR, is_delta=False):
    """Triggers export for all relevant Mail saved searches and downloads them."""
    log.info("\n" + "="*80)
    log.info(f"STEP 3: EXTRACTING MAIL REGISTER ({'DELTA / RECENT' if is_delta else 'ALL SAVED SEARCHES'})")
    log.info("="*80)
    
    page.locator("#nav-bar-CORRESPONDENCE, a:has-text('Mail')").first.click()
    time.sleep(1)
    page.locator("#nav-bar-CORRESPONDENCE-CORRESPONDENCE-SEARCHALL").first.click()
    time.sleep(8)
    
    frame = page.frame(name="main")
    if not frame:
        log.error("Content frame 'main' not found for Mail Search.")
        return False
        
    # Target EXCLUSIVELY "My Searches" (strictly ignore and exclude "My Organization's Searches")
    my_searches_group = frame.locator("ul.saved-search-list-container > li:has(heading:text-matches('My.*Search', 'i')):not(:has(heading:text-matches('Org', 'i')))")
    if my_searches_group.count() == 0:
        my_searches_group = frame.locator("ul:has(heading:text-matches('My.*Search', 'i')):not(:has(heading:text-matches('Org', 'i')))")

    items = my_searches_group.locator("li[title^='Load: '] > div[ng-click*='triggerSavedSearch']")
    count = items.count()
    log.info(f"Total 'My Saved Searches' (User Criteria / Contract-based) available: {count} (Organization searches excluded).")
    
    if count == 0:
        # Fallback if list structure varies: filter out any items whose parent heading mentions Organization
        log.warning("Explicit 'My Searches' group container not resolved via CSS. Filtering items via DOM...")
        all_lis = frame.locator("li[title^='Load: '] > div[ng-click*='triggerSavedSearch']")
        count = all_lis.count()
        items = all_lis

    for idx in range(count):
        try:
            item_el = items.nth(idx)
            item_text = item_el.inner_text().strip()
            
            # Check heading in parent container to strictly reject any organization searches
            is_org = item_el.evaluate("""(el) => {
                let parent = el.closest('ul, li');
                while (parent) {
                    const h = parent.querySelector('heading, h2, h3, h4, h5');
                    if (h && /org/i.test(h.innerText)) return true;
                    parent = parent.parentElement;
                }
                return false;
            }""")
            if is_org:
                log.info(f"Skipping Organization search: '{item_text}' (Excluded by user directive).")
                continue

            log.info(f"\n[{idx+1}/{count}] Triggering My Saved Search bundle: '{item_text}'...")
            item_el.click()
            time.sleep(8)
            
            # Click Export to Excel -> Row per recipient
            exp_btn = frame.locator("button:has-text('Export to Excel')").first
            if exp_btn.count() > 0 and exp_btn.is_visible():
                exp_btn.click()
                time.sleep(2)
                recip = frame.locator("button:has-text('Row per recipient')").first
                if recip.count() > 0 and recip.is_visible():
                    try:
                        with page.expect_download(timeout=8000) as dl_info:
                            recip.click()
                            time.sleep(2)
                        dl = dl_info.value
                        sugg_name = dl.suggested_filename
                        dest = os.path.join(output_dir, sugg_name)
                        dl.save_as(dest)
                        log.info(f"[INSTANT DOWNLOAD] Saved {dest} ({os.path.getsize(dest):,} bytes)!")
                        if sugg_name.endswith(".zip"):
                            with zipfile.ZipFile(dest, 'r') as z:
                                for zf in z.namelist():
                                    z.extract(zf, output_dir)
                    except Exception:
                        log.info(f"Queued bundle '{item_text}' to Temporary Files in Aconex backend.")
                        time.sleep(2)
                        close_btn = frame.locator("button:has-text('Close'), a:has-text('Close'), .ui-dialog-titlebar-close").first
                        if close_btn.count() > 0 and close_btn.is_visible():
                            close_btn.click()
                        time.sleep(2)
            time.sleep(3)
        except Exception as e:
            log.warning(f"Error triggering bundle {idx}: {e}")
        
    # Download all generated Mail files from Temporary Files
    download_mail_files_from_temp(page, output_dir)


def download_mail_files_from_temp(page, output_dir=config.OUTPUT_DIR):
    """Downloads all today's ExportMailAll files from Temporary Files with distinct names."""
    log.info("\nChecking Temporary Files for completed ExportMailAll packages...")
    page.locator("#nav-bar-DOC, a:has-text('Documents')").first.click()
    time.sleep(1)
    page.locator("#nav-bar-DOC-DOC-UNREG").click()
    time.sleep(8)
    
    frame = page.frame(name="main")
    if not frame:
        log.error("Could not access frame 'main' in Temporary Files.")
        return
        
    search_inp = frame.locator("input[placeholder*='document'], input.search-input, input[type='text']").first
    search_inp.fill("ExportMailAll")
    time.sleep(1)
    frame.locator("button:has-text('Search'), input[value='Search']").first.click()
    time.sleep(8)
    
    today_str = time.strftime('%d/%m/%Y')
    today_ymd = time.strftime('%Y%m%d')
    today_alt = time.strftime('%d-%m-%Y')
    today_us = time.strftime('%m/%d/%Y')
    
    # Poll up to ~12 minutes waiting for mail bundles. After a pre-sync purge,
    # every remaining ExportMailAll file belongs to this run (do not require a date match).
    max_rounds = 30
    stable_count = 0
    last_count = 0
    rows = []
    
    for round_idx in range(max_rounds):
        frame.locator("button:has-text('Search'), input[value='Search']").first.click()
        time.sleep(5)
        
        js_code = '''(t_info) => {
            // Aconex ag-Grid splits columns across pinned-left and center containers.
            // Pinned-left container contains col-id="filetype" (download icon) while center contains title/filename text.
            const centerRows = Array.from(document.querySelectorAll('.ag-center-cols-container .ag-row, .ag-row'));
            const pinnedRows = Array.from(document.querySelectorAll('.ag-pinned-left-cols-container .ag-row'));
            const pinnedMap = new Map();
            pinnedRows.forEach(pr => {
                const idx = pr.getAttribute('row-index');
                if (idx !== null) pinnedMap.set(idx, pr);
            });

            const seen = new Set();
            const out = [];
            centerRows.forEach(r => {
                const text = (r.innerText || '').trim().replace(/\\s+/g, ' ');
                if (!/ExportMailAll/i.test(text)) return;
                const rowIdx = r.getAttribute('row-index');
                const key = rowIdx || text.slice(0, 80);
                if (seen.has(key)) return;
                seen.add(key);

                // Check download element in center row or corresponding pinned-left row
                const pRow = rowIdx !== null ? pinnedMap.get(rowIdx) : null;
                const hasDlInCenter = r.querySelector('[col-id="filetype"] img, img[title="Download File"], .fileTypeTemplate, aui-file-icon') !== null;
                const hasDlInPinned = pRow && pRow.querySelector('[col-id="filetype"] img, img[title="Download File"], .fileTypeTemplate, aui-file-icon') !== null;
                const hasDl = hasDlInCenter || !!hasDlInPinned;

                const isToday = text.includes(t_info.d) || text.includes(t_info.ymd)
                    || text.includes(t_info.alt) || text.includes(t_info.us);
                out.push({
                    rowIdx: parseInt(rowIdx),
                    text: text,
                    isToday: isToday,
                    hasDl: hasDl
                });
            });
            const ready = out.filter(x => x.hasDl);
            return ready.length ? ready : out.filter(x => x.isToday && x.hasDl);
        }'''
        rows = frame.evaluate(js_code, {'d': today_str, 'ymd': today_ymd, 'alt': today_alt, 'us': today_us})
        
        current_count = len(rows)
        log.info(f"  [Poll {round_idx+1}/{max_rounds}] Ready ExportMailAll files: {current_count}")
        
        if current_count >= 6:
            log.info(f"All {current_count} mail packages are ready!")
            break
        elif current_count > 0 and current_count == last_count and round_idx >= 6:
            stable_count += 1
            if stable_count >= 3:
                log.info(f"Aconex mail generation finished with {current_count} completed packages.")
                break
        else:
            stable_count = 0
            
        last_count = current_count
        time.sleep(20)
        
    log.info(f"Total ready ExportMailAll files for download: {len(rows)}\n")
    for i, r in enumerate(rows):
        row_idx = r['rowIdx']
        dl_icon = frame.locator(
            f".ag-pinned-left-cols-container .ag-row[row-index='{row_idx}'] [col-id='filetype'] img, "
            f".ag-pinned-left-cols-container .ag-row[row-index='{row_idx}'] [col-id='filetype'] .fileTypeTemplate, "
            f".ag-row[row-index='{row_idx}'] [col-id='filetype'] img, "
            f".ag-row[row-index='{row_idx}'] img[title='Download File']"
        ).first
        try:
            with page.expect_download(timeout=180000) as dl_info:
                dl_icon.click()
                time.sleep(2)
            dl = dl_info.value
            sugg_name = dl.suggested_filename
            target_path = os.path.join(output_dir, sugg_name)
            dl.save_as(target_path)
            size_mb = os.path.getsize(target_path) / (1024 * 1024)
            log.info(f"[SUCCESS] Saved: {sugg_name} ({size_mb:.2f} MB)")
            if sugg_name.endswith(".zip"):
                log.info(f"Extracting zip archive {sugg_name}...")
                with zipfile.ZipFile(target_path, 'r') as z:
                    for zf in z.namelist():
                        z.extract(zf, output_dir)
                        log.info(f"  Extracted: {zf}")
        except Exception as e:
            log.warning(f"Error downloading row {row_idx}: {e}")

    ready_local = glob.glob(os.path.join(output_dir, "ExportMailAll-*.xlsx"))
    log.info(f"Local ExportMailAll files now on disk: {len(ready_local)}")
    return len(ready_local)


download_ready_mail_packages = download_mail_files_from_temp


def trigger_document_register_export(page):
    """Queues Document Register export using user's grouped Saved Searches from 'My Searches'."""
    log.info("\n" + "="*80)
    log.info("TRIGGERING DOCUMENT REGISTER EXPORT (Using User's 'My Searches' Groups)")
    log.info("="*80)
    try:
        page.locator("#nav-bar-DOC, a:has-text('Documents')").first.click()
        time.sleep(1)
        search_nav = page.locator("#nav-bar-DOC-DOC-SEARCH, #nav-bar-DOC-SEARCH")
        if search_nav.count() > 0:
            search_nav.first.click()
        else:
            page.goto(config.URL_DOCUMENTS, timeout=90000)
        time.sleep(8)
        frame = page.frame(name="main")
        if not frame:
            log.warning("Document Search frame not found.")
            return None

        # Open Saved Searches dropdown if present
        saved_btn = frame.locator("button:has-text('Saved Searches'), button[ng-click*='openPopup'], div[ng-bind*='savedSearch.displayText']").first
        if saved_btn.count() > 0 and saved_btn.is_visible():
            saved_btn.click()
            time.sleep(2)

        # Locate ONLY 'My Searches' group (strictly exclude Organization Saved Searches)
        doc_group = frame.locator("ul.saved-search-list-container > li:has(heading:text-matches('My.*Search', 'i')):not(:has(heading:text-matches('Org', 'i')))")
        if doc_group.count() == 0:
            doc_group = frame.locator("ul:has(heading:text-matches('My.*Search', 'i')):not(:has(heading:text-matches('Org', 'i')))")

        doc_items = doc_group.locator("li[title^='Load: '] > div[ng-click*='triggerSavedSearch']")
        doc_count = doc_items.count()
        log.info(f"Total 'My Saved Searches' Document groups available: {doc_count}")

        if doc_count > 0:
            for d_idx in range(doc_count):
                item_el = doc_items.nth(d_idx)
                group_name = item_el.inner_text().strip()
                log.info(f"\n[DOC GROUP {d_idx+1}/{doc_count}] Triggering My Saved Search: '{group_name}'...")
                item_el.click()
                time.sleep(8)

                # Click Export to Excel -> confirm
                exp = frame.locator("button:has-text('Export to Excel'), button:has-text('Export'), a:has-text('Export')").first
                if exp.count() > 0 and exp.is_visible():
                    exp.click()
                    time.sleep(2)
                    confirm = frame.locator("button:has-text('OK'), button:has-text('Export'), button:has-text('Continue')").first
                    if confirm.count() > 0 and confirm.is_visible():
                        confirm.click()
                    log.info(f"[SUCCESS] Document Register group '{group_name}' queued to Temporary Files.")
                time.sleep(3)
            return doc_count
        else:
            log.warning("No grouped saved searches found under 'My Searches' in Documents. Executing default search export as fallback.")
            s_btn = frame.locator("button:has-text('Search'), input[value='Search']").first
            if s_btn.count() > 0:
                s_btn.click()
                time.sleep(10)
            exp = frame.locator("button:has-text('Export to Excel'), button:has-text('Export'), a:has-text('Export')").first
            if exp.count() > 0 and exp.is_visible():
                exp.click()
                time.sleep(2)
                confirm = frame.locator("button:has-text('OK'), button:has-text('Export'), button:has-text('Continue')").first
                if confirm.count() > 0 and confirm.is_visible():
                    confirm.click()
                log.info("[SUCCESS] Fallback document register export queued.")
            return 1
    except Exception as e:
        log.warning(f"Could not trigger Document Register export: {e}")
        return None


def count_local_export_docs(output_dir):
    """Counts rows in downloaded ExportDocs parts for comparison with the app."""
    files = sorted(glob.glob(os.path.join(str(output_dir), "ExportDocs-*.xlsx")))
    if not files:
        log.info("[DOC COUNT] No ExportDocs-*.xlsx files found locally.")
        return 0
    total = 0
    for fp in files:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(fp, read_only=True, data_only=True)
            ws = wb.active
            n = 0
            header = False
            for row in ws.iter_rows(values_only=True):
                if not header:
                    if row and str(row[0] or '').strip() == 'Document No':
                        header = True
                    continue
                if row and row[0]:
                    n += 1
            wb.close()
            total += n
            log.info(f"  [DOC COUNT] {os.path.basename(fp)}: {n:,} documents")
        except Exception as e:
            log.warning(f"  [DOC COUNT] Could not read {os.path.basename(fp)}: {e}")
    log.info(f"[DOC COUNT] Combined ExportDocs rows: {total:,}")
    return total


# -----------------------------------------------------------------------------
# STEP 4: EXTRACT 5 DASHBOARD PROCESS DETAILS REPORTS (ORACLE ANALYTICS)
# -----------------------------------------------------------------------------
def extract_dashboard_reports(page, output_dir=config.OUTPUT_DIR):
    """Extracts all 5 Mail-based Process Details Excel files directly via Oracle Analytics."""
    log.info("\n" + "="*80)
    log.info("STEP 4: EXTRACTING 5 DASHBOARD PROCESS DETAILS REPORTS (ORACLE ANALYTICS)")
    log.info("="*80)
    
    for idx, item in enumerate(DASHBOARD_PROCESS_TARGETS):
        proc_name = item["name"]
        out_fname = item["filename"]
        out_path = os.path.join(output_dir, out_fname)
        
        log.info(f"\n[{idx+1}/5] Exporting Dashboard Process: '{proc_name}' -> {out_fname}...")
        
        p_encoded = urllib.parse.quote(f'"{proc_name}"')
        url = (
            f"https://analytics.mea.aconex.com/analytics/saw.dll?Dashboard"
            f"&PortalPath=%2Fshared%2FInsights%2F_portal%2FMail-based%20Processes"
            f"&Page=More%20Details%20By%20Orgs&Action=Navigate"
            f"&col1=CAST%28%22General%20-%20%28Project%29%22.%22Project%20Object%20ID%22%20AS%20char%29&val1=%221744833878%22"
            f"&col2=%22General%20-%20(Config%20Insights)%22.%22Config%20Action%22&val2=%22Any%22"
            f"&col3=%22General%20-%20(Config%20Insights)%22.%22Config%20Involved%20As%22&val3=%22Both%22"
            f"&col4=%22General%20-%20(Config%20Insights)%22.%22Config%20Process%20Name%22&val4={p_encoded}"
        )
        
        page.goto(url, timeout=90000)
        time.sleep(12)
        
        # Extract with resilient retry
        for attempt in range(2):
            try:
                page.goto(url, timeout=90000)
                time.sleep(12)
                with page.expect_download(timeout=60000) as dl_info:
                    page.evaluate('''() => {
                        const btn = document.querySelector('a[title*=\"XLSX\"]') || Array.from(document.querySelectorAll('a')).find(a => a.innerText.trim() === 'XLSX');
                        if (btn) btn.click();
                    }''')
                    time.sleep(2)
                dl = dl_info.value
                dl.save_as(out_path)
                size_kb = os.path.getsize(out_path) / 1024
                log.info(f"[SUCCESS] Saved: {out_fname} ({size_kb:,.1f} KB)")
                break
            except Exception as e:
                if attempt == 1:
                    log.warning(f"Error downloading {out_fname}: {e}")
                else:
                    log.info(f"Retrying download for {proc_name}...")
                time.sleep(4)
            
        time.sleep(2)


def cleanup_screenshots_and_temp():
    """Removes screenshots and temporary artifacts to conserve disk space."""
    log.info("\nCleaning up screenshots and temporary files...")
    s_dir = getattr(config, "SCREENSHOTS_DIR", None) or os.path.join(os.path.dirname(__file__), "screenshots")
    if os.path.exists(s_dir):
        count = 0
        for f in os.listdir(s_dir):
            try:
                fp = os.path.join(s_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
                    count += 1
            except Exception:
                pass
        log.info(f"[CLEANUP] Deleted {count} temporary screenshots.")


# -----------------------------------------------------------------------------
# MAIN PIPELINE ENTRY POINT
# -----------------------------------------------------------------------------
def run_master_pipeline(mode="full", phase="all"):
    import argparse
    parser = argparse.ArgumentParser(description="Aconex Automated Extractor Pipeline")
    parser.add_argument("--mode", choices=["delta", "full"], default=mode, help="Extraction mode: delta (fast) or full (deep)")
    parser.add_argument("--phase", choices=["mail", "docs", "all"], default=phase,
                        help="mail = correspondence first; docs = document register; all = mail then docs")
    args, _ = parser.parse_known_args()
    active_mode = args.mode
    active_phase = args.phase
    run_mail = active_phase in ("mail", "all")
    run_docs = active_phase in ("docs", "all") and active_mode == "full"

    print("=" * 80)
    print(f"      ACONEX AUTOMATED MASTER EXTRACTION PIPELINE")
    print(f"      MODE: {active_mode.upper()} | PHASE: {active_phase.upper()}")
    print(f"      Target Directory: {config.OUTPUT_DIR}")
    print("=" * 80)
    t0 = time.time()
    
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(config.PROFILE_DIR),
            headless=True,
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        total_steps = 3 if not run_docs else 4
        set_sync_state(1, f"Step 1/{total_steps}: Authenticating Session & Connecting to Aconex...", "Connecting to Aconex Hub and validating session...", 12)
        ensure_login(page, ctx)
        
        set_sync_state(1, f"Step 1/{total_steps}: Purging Residual Temporary Files...", "Purging old temporary files in Aconex and local scratch...", 18)
        clear_local_scratch()
        clear_aconex_temporary_files(page)

        if run_mail:
            set_sync_state(2, f"Step 2/{total_steps}: Exporting BI Publisher Reports (CSV)...", "Streaming workflow transmittal statuses, review outcomes, and project directory...", 40)
            extract_all_bip_reports(page, ctx, config.OUTPUT_DIR)

            set_sync_state(2, f"Step 2/{total_steps}: Extracting Mail Register...", "Queueing and downloading mail archive bundles from Temporary Files...", 58)
            extract_mail_bundles(page, config.OUTPUT_DIR, is_delta=(active_mode == "delta"))

            set_sync_state(2, f"Step 2/{total_steps}: Exporting Oracle Analytics Dashboards...", "Exporting Process Details reports (RFIs, NCRs, HSE observations)...", 72)
            extract_dashboard_reports(page, config.OUTPUT_DIR)

            mail_n = len(glob.glob(os.path.join(str(config.OUTPUT_DIR), "ExportMailAll-*.xlsx")))
            if mail_n == 0:
                log.error("No ExportMailAll-*.xlsx files were downloaded. Mail phase failed.")
                ctx.close()
                sys.exit(1)
            log.info(f"[MAIL PHASE] {mail_n} ExportMailAll workbook(s) ready for ingest.")
            # Free Aconex Temporary Files before the large Document Register zip.
            clear_aconex_temporary_files(page)

        if run_docs:
            set_sync_state(3, f"Step 3/{total_steps}: Extracting Document Register (ExportDocs)...", "Queueing a fresh document register export, then downloading multi-part Excel...", 82)
            trigger_document_register_export(page)
            time.sleep(15)
            extract_document_register(page, config.OUTPUT_DIR)
            count_local_export_docs(config.OUTPUT_DIR)
            clear_aconex_temporary_files(page)

        ctx.close()
        
    cleanup_screenshots_and_temp()

    elapsed = time.time() - t0
    log.info("\n" + "=" * 80)
    log.info(f"MASTER EXTRACTION ({active_mode.upper()}/{active_phase.upper()}) COMPLETED IN {elapsed:.1f}s ({elapsed/60:.1f} minutes)!")
    log.info("=" * 80)


if __name__ == "__main__":
    run_master_pipeline()
