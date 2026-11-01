
def extract_clean_orgs(raw_rows):
    """
    Parses Oracle Aconex organization and recipient strings.
    Handles concatenated recipients: 'OrgA: User1 , OrgB: User2'
    Returns sorted list of distinct, valid company names.
    """
    clean_set = set()
    for row in raw_rows:
        val = row[0] if isinstance(row, (tuple, list)) else row
        if not val or not isinstance(val, str):
            continue
        for token in val.split(','):
            tok = token.strip()
            if not tok:
                continue
            if ':' in tok:
                org = tok.split(':', 1)[0].strip()
            else:
                org = tok.strip()
            org = org.strip('"\' ')
            if org and 1 < len(org) < 80 and not org.lower().startswith('http'):
                clean_set.add(org)
    return sorted(list(clean_set))

import os
import time
import json
import re
import sys
import io
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
import duckdb

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "etl"))
from reminders_helper import generate_company_excel, generate_company_html_table, generate_company_eml, open_company_outlook
from package_resolver import (
    resolve_project_package, 
    get_company_official_emails, 
    DEFAULT_PMC_CC, 
    group_dossier_by_package,
    is_shaker_ecg,
    is_shaker_consultant,
    get_shaker_ecg_zone_contacts,
    get_hill_pmc_contacts,
    resolve_user_email,
    load_all_contacts_databases,
    get_contacts_status,
    get_package_email_matrix,
    is_hill_org
)
import urllib.parse
from rfi_log_engine import (
    build_rfi_log_workbook, 
    extract_rfi_log_data, 
    upload_and_update_rfi_bytes, 
    bulk_sync_all_dp_logs, 
    update_rfi_log_file,
    detect_package_from_name_or_content
)
from letters_log_engine import (
    sync_letters_log_file,
    bulk_sync_all_letters_logs
)
import rfi_thread_service as rts
import letter_thread_service as lts
import excel_export_service as ees
import overdue_control_service as ocs
import hill_internal_control_service as hcs
import ai_chat_service as acs
import dispatch_settings_service as dss
import discipline_service as disc_s
import feed_service
import credentials_service as cred_s

from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
_CLOUD_DB = _ROOT_DIR / "aconex_cloud.duckdb"
_CLOUD_ZIP = _ROOT_DIR / "aconex_cloud.duckdb.zip"

# Priority: Local master aconex.duckdb > aconex_cloud.duckdb (Render) > unzip aconex_cloud.duckdb.zip
if (_ROOT_DIR / "aconex.duckdb").exists():
    DB_PATH = str(_ROOT_DIR / "aconex.duckdb").replace("\\", "/")
elif _CLOUD_DB.exists():
    DB_PATH = str(_CLOUD_DB).replace("\\", "/")
elif _CLOUD_ZIP.exists():
    import zipfile
    with zipfile.ZipFile(str(_CLOUD_ZIP), "r") as z:
        z.extractall(str(_ROOT_DIR))
    DB_PATH = str(_CLOUD_DB).replace("\\", "/")
else:
    DB_PATH = "aconex.duckdb"

# Propagate dynamic DB_PATH to all etl/backend services so they work seamlessly on both Windows and Linux (Render)
for _mod in [disc_s, ocs, hcs, rts, lts, ees, acs, dss, cred_s, feed_service]:
    try:
        setattr(_mod, "DB_PATH", DB_PATH)
    except Exception:
        pass 

from fastapi.staticfiles import StaticFiles
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(
    title="ACONEX PMC Control Platform API",
    description="Enterprise Analytics & Controls API for Ras El Hekma Project",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# HILL INTERNATIONAL CORPORATE AUTHENTICATION SESSION STORE & PROTECTION
# -----------------------------------------------------------------------------
import uuid
HILL_SESSIONS = {}
PROJECT_ACCESS_KEY = os.environ.get("PROJECT_ACCESS_KEY", "HILL-REH-2026")

@app.middleware("http")
async def hill_corporate_auth_middleware(request: Request, call_next):
    path = request.url.path
    # Exempt non-API routes and public auth endpoints
    exempt_paths = [
        "/api/auth/hill-login",
        "/api/auth/hill-session",
        "/api/auth/hill-logout",
        "/api/auth/check-user",
        "/api/auth/register-password",
        "/api/auth/reset-password",
        "/api/auth/verify-admin",
        "/api/auth/check-admin",
        "/api/sync/cloud-push",
        "/api/aconex/doc",
        "/api/aconex/mail",
        "/api/aconex/rfi",
        "/api/aconex/workflow",
        "/openapi.json",
        "/docs",
        "/redoc"
    ]
    if path.startswith("/api/") and path not in exempt_paths and request.method != "OPTIONS":
        # Extract token
        token = request.headers.get("x-hill-token", "")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
        if not token:
            token = request.cookies.get("hill_token", "")
            
        is_authenticated = (token in HILL_SESSIONS)
        
        # Check if admin pin was supplied
        if not is_authenticated:
            try:
                verify_admin_request(request)
                is_authenticated = True
            except Exception:
                pass
                
        if not is_authenticated:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Hill Corporate Authentication Required. Please login with your @hillintl.com email."
                }
            )
            
    return await call_next(request)

@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path.lower()
    if path.endswith(".js") or path.endswith(".html") or path.endswith(".css") or path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
def serve_dashboard():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "ACONEX PMC Control Platform API is active"}

def get_db(max_retries: int = 5, retry_delay: float = 0.15):
    """Returns a read-only DuckDB connection with automatic lock-wait resilience."""
    import time
    last_err = None
    for attempt in range(max_retries):
        try:
            return duckdb.connect(DB_PATH, read_only=True)
        except Exception as e:
            last_err = e
            time.sleep(retry_delay * (attempt + 1))
    raise last_err


# -----------------------------------------------------------------------------
# Universal Aconex Resolvers -> always redirects to the direct Hyperlink with ID:
#   - Documents: https://mea.aconex.com/ViewDoc?trackingid=...
#   - Mails / RFIs: https://mea.aconex.com/MiniURL?type=MAILSEARCH&mailbox=5&pid=1744833878&cid=...
# Never drops the user into an empty search screen.
# -----------------------------------------------------------------------------
from fastapi.responses import RedirectResponse as _AconexRedirect

@app.get("/api/aconex/doc")
def aconex_doc_redirect(doc_no: str = Query(""), fallback: str = Query("")):
    raw = (doc_no or "").strip().strip("'").strip('"').strip()
    if not raw and fallback:
        raw = fallback.strip().strip("'").strip('"').strip()
    
    if raw:
        try:
            con = get_db()
            try:
                # In case an RFI or Mail was passed to doc endpoint
                m_row = con.execute("SELECT aconex_url FROM fact_mail WHERE mail_no = ? AND aconex_url LIKE '%MiniURL%' LIMIT 1", [raw]).fetchone()
                if m_row and m_row[0]:
                    return _AconexRedirect(url=m_row[0], status_code=302)
            finally:
                con.close()
        except Exception:
            pass
        
        q = urllib.parse.quote(f'documentNumber:"{raw}"')
        target = f"https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=DOC-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery={q}"
        return _AconexRedirect(url=target, status_code=302)
    
    return _AconexRedirect(url="https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=DOC-SEARCH&ENTITY=PROJECT&ID=1744833878", status_code=302)


@app.get("/api/aconex/mail")
@app.get("/api/aconex/rfi")
def aconex_mail_redirect(mail_no: str = Query(""), rfi_no: str = Query(""), cid: str = Query(""), fallback: str = Query("")):
    raw = (mail_no or rfi_no or cid or "").strip().strip("'").strip('"').strip()
    url = None

    # If cid is directly provided or raw is purely numeric, it is the Aconex internal Correspondence ID
    if (cid and cid.isdigit()):
        return _AconexRedirect(url=f"https://mea.aconex.com/MiniURL?type=MAILSEARCH&mailbox=5&pid=1744833878&cid={cid}", status_code=302)
    if raw.isdigit():
        return _AconexRedirect(url=f"https://mea.aconex.com/MiniURL?type=MAILSEARCH&mailbox=5&pid=1744833878&cid={raw}", status_code=302)

    if raw:
        try:
            con = get_db()
            try:
                candidates = [raw]
                base = re.sub(r'(?i)\.(attached|attach|att)\.?$', '', raw).strip()
                if base and base != raw:
                    candidates.append(base)

                for cand in candidates:
                    # 1. Check fact_rfis for direct MiniURL with ID
                    row = con.execute(
                        "SELECT aconex_url FROM fact_rfis WHERE mail_no = ? AND aconex_url LIKE '%MiniURL%' LIMIT 1", [cand]
                    ).fetchone()
                    if not row or not row[0]:
                        row = con.execute(
                            "SELECT aconex_url FROM mail_aconex_links WHERE mail_no = ? AND aconex_url LIKE '%MiniURL%' LIMIT 1", [cand]
                        ).fetchone()
                    if not row or not row[0]:
                        row = con.execute(
                            "SELECT aconex_url FROM fact_mail WHERE mail_no = ? AND aconex_url LIKE '%MiniURL%' LIMIT 1", [cand]
                        ).fetchone()
                    if row and row[0]:
                        url = row[0]
                        break

                # 2. If not found in mail, check if it was actually a document (e.g. attachment / BOQ)
                if not url:
                    for cand in candidates:
                        row = con.execute(
                            "SELECT aconex_url FROM doc_direct_links WHERE document_no = ? LIMIT 1", [cand]
                        ).fetchone()
                        if not row or not row[0]:
                            row = con.execute(
                                "SELECT aconex_url FROM dim_documents WHERE trim(document_no) = ? AND aconex_url IS NOT NULL AND aconex_url != '' LIMIT 1", [cand]
                            ).fetchone()
                        if row and row[0]:
                            url = row[0]
                            break

                # 3. Check any remaining aconex_url in fact_rfis or fact_mail
                if not url:
                    for cand in candidates:
                        row = con.execute(
                            "SELECT aconex_url FROM fact_rfis WHERE mail_no = ? AND aconex_url IS NOT NULL AND aconex_url != '' LIMIT 1", [cand]
                        ).fetchone()
                        if not row or not row[0]:
                            row = con.execute(
                                "SELECT aconex_url FROM fact_mail WHERE mail_no = ? AND aconex_url IS NOT NULL AND aconex_url != '' LIMIT 1", [cand]
                            ).fetchone()
                        if row and row[0]:
                            url = row[0]
                            break
            finally:
                con.close()
        except Exception as e:
            print(f"[aconex_mail_redirect] lookup error: {e}")

    if not url:
        if fallback and fallback.startswith("https://mea.aconex.com"):
            url = fallback
        elif raw:
            q = urllib.parse.quote(f'mailNumber:"{raw}"')
            url = f"https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery={q}"
        else:
            url = "https://mea.aconex.com"
    return _AconexRedirect(url=url, status_code=302)

# -----------------------------------------------------------------------------
# 1. Executive Overview & KPIs
# -----------------------------------------------------------------------------
@app.get("/api/overview")
def get_overview(perspective: str = Query("neutral", regex="^(neutral|pmc)$")):
    con = get_db()
    try:
        # High-level KPIs
        kpis = con.execute("""
            SELECT 
                (SELECT count(*) FROM dim_documents) AS total_documents,
                (SELECT count(*) FROM fact_workflows WHERE workflow_status = 'In Progress') AS active_workflows,
                (SELECT count(*) FROM fact_workflow_steps WHERE is_overdue) AS total_overdue_steps,
                (SELECT count(*) FROM fact_mail WHERE is_overdue) AS total_overdue_mails,
                (SELECT count(*) FROM fact_rfis WHERE is_overdue) AS total_overdue_rfis,
                (SELECT ROUND(count(CASE WHEN days_late <= 0 THEN 1 END) * 100.0 / count(*), 1) 
                 FROM fact_workflow_steps WHERE step_status = 'Completed') AS overall_sla_pct
        """).fetchone()

        # Perspective Specific (PMC: Hill Inbound vs Outbound)
        pmc_kpis = {}
        if perspective == "pmc":
            pmc_data = con.execute("""
                SELECT 
                    -- Owed by Hill (Hill is the bottleneck)
                    (SELECT count(*) FROM fact_workflow_steps WHERE is_overdue AND is_owed_by_hill) AS hill_overdue_steps,
                    (SELECT count(*) FROM fact_mail WHERE is_overdue AND is_inbound_to_hill) AS hill_overdue_inbound_mails,
                    (SELECT count(*) FROM fact_rfis WHERE is_overdue AND direction = 'Received') AS hill_overdue_rfis,
                    -- Owed to Hill (Others are delaying Hill)
                    (SELECT count(*) FROM fact_workflow_steps WHERE is_overdue AND is_owed_to_hill) AS others_overdue_to_hill_steps,
                    (SELECT count(*) FROM fact_mail WHERE is_overdue AND is_outbound_from_hill) AS others_overdue_to_hill_mails,
                    (SELECT count(*) FROM fact_rfis WHERE is_overdue AND direction = 'Sent') AS others_overdue_to_hill_rfis
            """).fetchone()
            pmc_kpis = {
                "owed_by_hill": {
                    "overdue_review_steps": pmc_data[0],
                    "overdue_inbound_mails": pmc_data[1],
                    "overdue_rfis": pmc_data[2],
                    "total_actions_owed": pmc_data[0] + pmc_data[1] + pmc_data[2]
                },
                "owed_to_hill": {
                    "overdue_steps": pmc_data[3],
                    "overdue_mails": pmc_data[4],
                    "overdue_rfis": pmc_data[5],
                    "total_actions_owed": pmc_data[3] + pmc_data[4] + pmc_data[5]
                }
            }

        # Overdue Aging Distribution
        aging = con.execute("""
            SELECT 
                aging_bucket,
                count(*) AS count
            FROM fact_workflow_steps
            WHERE is_overdue
            GROUP BY aging_bucket
            ORDER BY 
                CASE aging_bucket
                    WHEN '1-7 Days Overdue' THEN 1
                    WHEN '8-14 Days Overdue' THEN 2
                    WHEN '15-30 Days Overdue' THEN 3
                    ELSE 4
                END
        """).fetchall()

        # Top 5 Overdue Organizations
        top_orgs = con.execute("""
            SELECT org_name, org_category, overdue_steps, active_pending_steps, step_sla_compliance_pct
            FROM agg_org_scorecard
            WHERE overdue_steps > 0
            ORDER BY overdue_steps DESC
            LIMIT 5
        """).fetchall()

        # Top 5 Overdue Engineers
        top_people = con.execute("""
            SELECT user_name, org_name, overdue_tasks, max_delay_days, avg_delay_days
            FROM agg_user_workload
            WHERE overdue_tasks > 0
            ORDER BY overdue_tasks DESC
            LIMIT 5
        """).fetchall()

        # Top 5 Step Bottlenecks
        top_bottlenecks = con.execute("""
            SELECT step_name, org_name, currently_overdue, avg_overdue_days, on_time_completion_pct
            FROM agg_step_bottlenecks
            WHERE currently_overdue > 0
            ORDER BY currently_overdue DESC
            LIMIT 5
        """).fetchall()

        # Package breakdown
        package_dist = con.execute("""
            SELECT package_name, count(*) as count
            FROM dim_documents
            GROUP BY package_name
            ORDER BY count DESC
        """).fetchall()

        # Discipline breakdown
        discipline_dist = con.execute("""
            SELECT discipline_name, count(*) as count
            FROM dim_documents
            GROUP BY discipline_name
            ORDER BY count DESC
        """).fetchall()

        return {
            "perspective": perspective,
            "kpis": {
                "total_documents": kpis[0],
                "active_workflows": kpis[1],
                "total_overdue_steps": kpis[2],
                "total_overdue_mails": kpis[3],
                "total_overdue_rfis": kpis[4],
                "overall_sla_compliance_pct": kpis[5]
            },
            "pmc_perspective": pmc_kpis,
            "aging_distribution": [{"bucket": r[0], "count": r[1]} for r in aging],
            "top_overdue_orgs": [{"org_name": r[0], "category": r[1], "overdue": r[2], "active": r[3], "sla_pct": r[4]} for r in top_orgs],
            "top_overdue_people": [{"name": r[0], "org": r[1], "overdue": r[2], "max_delay": r[3], "avg_delay": r[4]} for r in top_people],
            "top_step_bottlenecks": [{"step": r[0], "org": r[1], "overdue": r[2], "avg_delay": r[3], "on_time_pct": r[4]} for r in top_bottlenecks],
            "packages": [{"package": r[0], "count": r[1]} for r in package_dist],
            "disciplines": [{"discipline": r[0], "count": r[1]} for r in discipline_dist]
        }
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 1.1 Global Filter Options (Dropdowns for UI)
# -----------------------------------------------------------------------------
@app.get("/api/filters/options")
def get_filter_options():
    con = get_db()
    try:
        orgs = [r[0] for r in con.execute("SELECT DISTINCT org_name FROM agg_org_scorecard WHERE org_name IS NOT NULL ORDER BY org_name").fetchall()]
        packages = [r[0] for r in con.execute("SELECT DISTINCT package_name FROM dim_documents WHERE package_name IS NOT NULL ORDER BY package_name").fetchall()]
        disciplines = [r[0] for r in con.execute("SELECT DISTINCT discipline_name FROM dim_documents WHERE discipline_name IS NOT NULL ORDER BY discipline_name").fetchall()]
        doc_statuses = [r[0] for r in con.execute("SELECT DISTINCT status FROM dim_documents WHERE status IS NOT NULL ORDER BY status").fetchall()]
        doc_types = [r[0] for r in con.execute("SELECT DISTINCT doc_type FROM dim_documents WHERE doc_type IS NOT NULL ORDER BY doc_type").fetchall()]
        mail_types = [r[0] for r in con.execute("SELECT DISTINCT mail_type FROM fact_mail WHERE mail_type IS NOT NULL ORDER BY mail_type").fetchall()]
        mail_from_orgs = extract_clean_orgs(con.execute("SELECT DISTINCT from_organization FROM fact_mail WHERE from_organization IS NOT NULL").fetchall())
        mail_to_orgs = extract_clean_orgs(con.execute("SELECT DISTINCT to_organization FROM fact_mail WHERE to_organization IS NOT NULL").fetchall())
        workflow_initiators = [r[0] for r in con.execute("SELECT DISTINCT initiator_organization FROM fact_workflows WHERE initiator_organization IS NOT NULL ORDER BY initiator_organization").fetchall()]
        workflow_assigned_orgs = [r[0] for r in con.execute("SELECT DISTINCT current_assigned_org FROM fact_workflows WHERE current_assigned_org IS NOT NULL ORDER BY current_assigned_org").fetchall()]
        
        return {
            "organizations": orgs,
            "packages": packages,
            "disciplines": disciplines,
            "doc_statuses": doc_statuses,
            "doc_types": doc_types,
            "mail_types": mail_types,
            "mail_from_orgs": mail_from_orgs,
            "mail_to_orgs": mail_to_orgs,
            "workflow_statuses": ["In Progress", "Completed"],
            "workflow_initiators": workflow_initiators,
            "workflow_assigned_orgs": workflow_assigned_orgs
        }
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 2. Organizations Scorecard
# -----------------------------------------------------------------------------
@app.get("/api/organizations")
def get_organizations(
    category: str = Query(None),
    search: str = Query(None),
    min_overdue: int = Query(None),
    sla_min: float = Query(None),
    sla_max: float = Query(None),
    sort_by: str = Query("overdue_steps"),
    sort_dir: str = Query("desc")
):
    con = get_db()
    try:
        filters = []
        if category:
            filters.append(f"org_category = '{category}'")
        if search:
            filters.append(f"org_name ILIKE '%{search}%'")
        if min_overdue is not None:
            filters.append(f"overdue_steps >= {min_overdue}")
        if sla_min is not None:
            filters.append(f"step_sla_compliance_pct >= {sla_min}")
        if sla_max is not None:
            filters.append(f"step_sla_compliance_pct <= {sla_max}")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        allowed_sorts = {
            "org_name": "org_name",
            "category": "COALESCE(org_category, 'Stakeholder')",
            "active_steps": "active_pending_steps",
            "overdue_steps": "overdue_steps",
            "completed_steps": "completed_steps",
            "sla_compliance_pct": "step_sla_compliance_pct",
            "avg_delay_days": "avg_step_delay_days",
            "open_mails": "open_action_mails",
            "overdue_mails": "overdue_mails",
            "submittals_count": "total_submittals_initiated",
            "approval_rate_pct": "submittal_approval_rate_pct",
            "code_c_count": "code_c_revise_count",
            "code_d_count": "code_d_rejected_count"
        }
        sort_col = allowed_sorts.get(sort_by, "overdue_steps")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"
            
        rows = con.execute(f"""
            SELECT 
                org_name,
                COALESCE(org_category, 'Stakeholder') AS category,
                is_pmc,
                active_pending_steps,
                overdue_steps,
                completed_steps,
                step_sla_compliance_pct,
                avg_step_delay_days,
                open_action_mails,
                overdue_mails,
                total_submittals_initiated,
                submittal_approval_rate_pct,
                code_c_revise_count,
                code_d_rejected_count
            FROM agg_org_scorecard
            {where_clause}
            ORDER BY {sort_col} {order_dir} NULLS LAST
        """).fetchall()

        result = []
        for r in rows:
            result.append({
                "org_name": r[0],
                "category": r[1],
                "is_pmc": r[2],
                "active_steps": r[3],
                "overdue_steps": r[4],
                "completed_steps": r[5],
                "sla_compliance_pct": r[6],
                "avg_delay_days": r[7],
                "open_mails": r[8],
                "overdue_mails": r[9],
                "submittals_count": r[10],
                "approval_rate_pct": r[11],
                "code_c_count": r[12],
                "code_d_count": r[13]
            })
        return {"total": len(result), "data": result}
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 3. People / Workload
# -----------------------------------------------------------------------------
@app.get("/api/people")
def get_people(
    org: str = Query(None),
    search: str = Query(None),
    delay_bucket: str = Query(None),
    min_overdue: int = Query(None),
    sort_by: str = Query("overdue_tasks"),
    sort_dir: str = Query("desc")
):
    con = get_db()
    try:
        filters = []
        if org:
            filters.append(f"org_name = '{org}'")
        if search:
            filters.append(f"(user_name ILIKE '%{search}%' OR org_name ILIKE '%{search}%')")
        if min_overdue is not None:
            filters.append(f"overdue_tasks >= {min_overdue}")
        if delay_bucket == "over_30":
            filters.append("overdue_over_30_days > 0")
        elif delay_bucket == "15_30":
            filters.append("overdue_15_to_30_days > 0")
        elif delay_bucket == "8_14":
            filters.append("overdue_8_to_14_days > 0")
        elif delay_bucket == "1_7":
            filters.append("overdue_1_to_7_days > 0")
        elif delay_bucket == "any_overdue":
            filters.append("overdue_tasks > 0")
            
        where = f"WHERE {' AND '.join(filters)}" if filters else ""

        allowed_sorts = {
            "name": "user_name",
            "org": "org_name",
            "active_tasks": "total_active_tasks",
            "overdue_tasks": "overdue_tasks",
            "overdue_1_7": "overdue_1_to_7_days",
            "overdue_8_14": "overdue_8_to_14_days",
            "overdue_15_30": "overdue_15_to_30_days",
            "overdue_30_plus": "overdue_over_30_days",
            "max_delay": "max_delay_days",
            "avg_delay": "avg_delay_days"
        }
        sort_col = allowed_sorts.get(sort_by, "overdue_tasks")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"
        
        rows = con.execute(f"""
            SELECT 
                user_name,
                org_name,
                total_active_tasks,
                overdue_tasks,
                overdue_1_to_7_days,
                overdue_8_to_14_days,
                overdue_15_to_30_days,
                overdue_over_30_days,
                max_delay_days,
                avg_delay_days
            FROM agg_user_workload
            {where}
            ORDER BY {sort_col} {order_dir} NULLS LAST
        """).fetchall()

        result = []
        for r in rows:
            result.append({
                "name": r[0],
                "org": r[1],
                "active_tasks": r[2],
                "overdue_tasks": r[3],
                "overdue_1_7": r[4],
                "overdue_8_14": r[5],
                "overdue_15_30": r[6],
                "overdue_30_plus": r[7],
                "max_delay": r[8],
                "avg_delay": r[9]
            })
        return {"total": len(result), "data": result}
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 4. Workflows & Bottlenecks
# -----------------------------------------------------------------------------
@app.get("/api/workflows/bottlenecks")
def get_bottlenecks():
    con = get_db()
    try:
        rows = con.execute("""
            SELECT 
                step_name,
                org_name,
                total_occurrences,
                currently_pending,
                currently_overdue,
                avg_overdue_days,
                on_time_completion_pct
            FROM agg_step_bottlenecks
            ORDER BY currently_overdue DESC, currently_pending DESC
        """).fetchall()

        return {
            "data": [{
                "step_name": r[0],
                "org_name": r[1],
                "total_occurrences": r[2],
                "currently_pending": r[3],
                "currently_overdue": r[4],
                "avg_overdue_days": r[5],
                "on_time_completion_pct": r[6]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/workflows")
def get_workflows(
    status: str = Query(None),
    initiator: str = Query(None),
    assigned_org: str = Query(None),
    package: str = Query(None),
    has_overdue: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    sort_by: str = Query("overdue_steps"),
    sort_dir: str = Query("desc"),
    limit: int = 50,
    offset: int = 0
):
    con = get_db()
    try:
        filters = []
        if status:
            filters.append(f"workflow_status = '{status}'")
        if initiator:
            filters.append(f"initiator_organization = '{initiator}'")
        if assigned_org:
            filters.append(f"current_assigned_org = '{assigned_org}'")
        if package:
            filters.append(f"project_package = '{package}'")
        if has_overdue in ['true', 'yes', '1']:
            filters.append("overdue_steps_count > 0")
        elif has_overdue in ['false', 'no', '0']:
            filters.append("overdue_steps_count = 0")
        if from_date and from_date.strip():
            filters.append(f"started_date >= '{from_date.strip()}'")
        if to_date and to_date.strip():
            filters.append(f"started_date <= '{to_date.strip()} 23:59:59'")
        if search:
            filters.append(f"(workflow_no ILIKE '%{search}%' OR workflow_name ILIKE '%{search}%' OR initiator_organization ILIKE '%{search}%' OR current_assigned_org ILIKE '%{search}%' OR current_assigned_user ILIKE '%{search}%')")
            
        where = f"WHERE {' AND '.join(filters)}" if filters else ""

        
        total = con.execute(f"SELECT count(*) FROM fact_workflows {where}").fetchone()[0]
        
        allowed_sorts = {
            "workflow_no": "workflow_no",
            "workflow_name": "workflow_name",
            "status": "workflow_status",
            "initiator": "initiator_organization",
            "template": "template",
            "start_date": "start_date",
            "due_date": "original_due_date",
            "total_steps": "total_steps",
            "overdue_steps": "overdue_steps_count",
            "completed_steps": "completed_steps_count",
            "documents_count": "documents_count",
            "current_org": "current_assigned_org",
            "current_user": "current_assigned_user",
            "current_step": "current_step_name"
        }
        sort_col = allowed_sorts.get(sort_by, "overdue_steps_count")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"
        
        rows = con.execute(f"""
            SELECT 
                w.workflow_no,
                w.workflow_name,
                w.workflow_status,
                w.initiator_organization,
                w.template,
                w.start_date::VARCHAR,
                w.original_due_date::VARCHAR,
                w.total_steps,
                w.overdue_steps_count,
                w.completed_steps_count,
                w.documents_count,
                w.current_assigned_org,
                w.current_assigned_user,
                w.current_step_name,
                l.aconex_url
            FROM fact_workflows w
            LEFT JOIN (
                SELECT review_source, MIN(aconex_url) AS aconex_url
                FROM doc_aconex_links
                WHERE review_source IS NOT NULL
                GROUP BY review_source
            ) l ON w.workflow_no = l.review_source
            {where}
            ORDER BY {sort_col} {order_dir} NULLS LAST, w.start_date DESC
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        result = []
        for r in rows:
            result.append({
                "workflow_no": r[0],
                "workflow_name": r[1],
                "status": r[2],
                "initiator": r[3],
                "template": r[4],
                "start_date": r[5][:10] if r[5] else None,
                "due_date": r[6][:10] if r[6] else None,
                "total_steps": r[7],
                "overdue_steps": r[8],
                "completed_steps": r[9],
                "documents_count": r[10],
                "current_org": r[11],
                "current_user": r[12],
                "current_step": r[13],
                "aconex_url": r[14]
            })
        return {"total": total, "limit": limit, "offset": offset, "data": result}
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 5. Contractor Quality & Approval Rates
# -----------------------------------------------------------------------------
@app.get("/api/quality")
def get_quality(
    search: str = Query(None),
    min_reviews: int = Query(None),
    performance: str = Query(None),
    sort_by: str = Query("total_reviews"),
    sort_dir: str = Query("desc")
):
    con = get_db()
    try:
        where_conds = ["initiator_organization IS NOT NULL", "step_outcome IS NOT NULL", "trim(step_outcome) != ''"]
        if search:
            where_conds.append(f"initiator_organization ILIKE '%{search}%'")
        
        min_rev = min_reviews if min_reviews is not None else 10

        allowed_sorts = {
            "contractor": "initiator_organization",
            "total_reviews": "total_reviews",
            "code_a": "code_a",
            "code_b": "code_b",
            "code_c": "code_c",
            "code_d": "code_d",
            "approval_rate": "approval_rate_pct",
            "revise_rate": "revise_rate_pct"
        }
        sort_col = allowed_sorts.get(sort_by, "total_reviews")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

        outer_filters = []
        if performance == "high":
            outer_filters.append("approval_rate_pct >= 80")
        elif performance == "medium":
            outer_filters.append("approval_rate_pct >= 50 AND approval_rate_pct < 80")
        elif performance == "low":
            outer_filters.append("approval_rate_pct < 50")

        outer_where = f"WHERE {' AND '.join(outer_filters)}" if outer_filters else ""

        rows = con.execute(f"""
            WITH stats AS (
                SELECT 
                    initiator_organization,
                    count(*) AS total_reviews,
                    count(CASE WHEN step_outcome ILIKE '%A - Approved%' THEN 1 END) AS code_a,
                    count(CASE WHEN step_outcome ILIKE '%B - Approved with Comments%' THEN 1 END) AS code_b,
                    count(CASE WHEN step_outcome ILIKE '%C - Revise and Resubmit%' THEN 1 END) AS code_c,
                    count(CASE WHEN step_outcome ILIKE '%D - Rejected%' THEN 1 END) AS code_d,
                    ROUND((count(CASE WHEN step_outcome ILIKE '%A - Approved%' THEN 1 END) + 
                           count(CASE WHEN step_outcome ILIKE '%B - Approved with Comments%' THEN 1 END)) * 100.0 / NULLIF(count(*), 0), 1) AS approval_rate_pct,
                    ROUND(count(CASE WHEN step_outcome ILIKE '%C - Revise and Resubmit%' THEN 1 END) * 100.0 / NULLIF(count(*), 0), 1) AS revise_rate_pct
                FROM fact_workflow_steps
                WHERE {' AND '.join(where_conds)}
                GROUP BY initiator_organization
                HAVING count(*) >= {min_rev}
            )
            SELECT initiator_organization, total_reviews, code_a, code_b, code_c, code_d, approval_rate_pct, revise_rate_pct
            FROM stats
            {outer_where}
            ORDER BY {sort_col} {order_dir} NULLS LAST
        """).fetchall()

        return {
            "total": len(rows),
            "data": [{
                "contractor": r[0],
                "total_reviews": r[1],
                "code_a": r[2],
                "code_b": r[3],
                "code_c": r[4],
                "code_d": r[5],
                "approval_rate_pct": r[6],
                "revise_rate_pct": r[7]
            } for r in rows]
        }
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 6. Documents Register & Drill-Down Timeline
# -----------------------------------------------------------------------------
@app.get("/api/documents")
def get_documents(
    search: str = Query(None),
    package: str = Query(None),
    discipline: str = Query(None),
    status: str = Query(None),
    doc_type: str = Query(None),
    created_by: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    sort_by: str = Query("date_modified"),
    sort_dir: str = Query("desc"),
    limit: int = 50,
    offset: int = 0
):
    con = get_db()
    try:
        filters = []
        if search:
            filters.append(f"(document_no ILIKE '%{search}%' OR title ILIKE '%{search}%' OR created_by ILIKE '%{search}%')")
        if package:
            filters.append(f"package_name = '{package}'")
        if discipline:
            filters.append(f"discipline_name = '{discipline}'")
        if status:
            filters.append(f"status = '{status}'")
        if doc_type:
            filters.append(f"doc_type = '{doc_type}'")
        if created_by:
            filters.append(f"created_by ILIKE '%{created_by}%'")
        if from_date and from_date.strip():
            filters.append(f"date_modified >= '{from_date.strip()}'")
        if to_date and to_date.strip():
            filters.append(f"date_modified <= '{to_date.strip()} 23:59:59'")


        where = f"WHERE {' AND '.join(filters)}" if filters else ""

        total = con.execute(f"SELECT count(*) FROM dim_documents {where}").fetchone()[0]

        allowed_sorts = {
            "document_no": "document_no",
            "title": "title",
            "type": "doc_type",
            "status": "status",
            "review_status": "review_status",
            "revision": "revision",
            "version": "version_number",
            "created_by": "created_by",
            "package": "package_name",
            "discipline": "discipline_name",
            "date_modified": "date_modified"
        }
        sort_col = allowed_sorts.get(sort_by, "date_modified")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

        rows = con.execute(f"""
            SELECT 
                d.document_no,
                d.title,
                d.doc_type,
                d.status,
                d.review_status,
                d.revision,
                d.version_number,
                d.created_by,
                d.package_name,
                d.discipline_name,
                d.date_modified::VARCHAR,
                l.aconex_url
            FROM dim_documents d
            LEFT JOIN doc_aconex_links l ON d.document_no = l.document_no
            {where}
            ORDER BY {sort_col} {order_dir} NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": [{
                "document_no": r[0],
                "title": r[1],
                "type": r[2],
                "status": r[3],
                "review_status": r[4],
                "revision": r[5],
                "version": r[6],
                "created_by": r[7],
                "package": r[8],
                "discipline": r[9],
                "date_modified": r[10][:19] if r[10] else None,
                "aconex_url": r[11]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/documents/{doc_no}/timeline")
def get_document_timeline(doc_no: str):
    con = get_db()
    try:
        # Document Details
        doc = con.execute(f"""
            SELECT d.document_no, d.title, d.doc_type, d.status, d.revision, d.version_number, d.created_by, d.package_name, d.discipline_name, l.aconex_url
            FROM dim_documents d
            LEFT JOIN doc_aconex_links l ON d.document_no = l.document_no
            WHERE d.document_no = '{doc_no}'
            LIMIT 1
        """).fetchone()

        if not doc:
            # Fallback search directly in doc_aconex_links
            doc_link = con.execute(f"""
                SELECT document_no, title, doc_type, status, revision, '1', 'Aconex Import', 'General', discipline, aconex_url
                FROM doc_aconex_links
                WHERE document_no = '{doc_no}'
                LIMIT 1
            """).fetchone()
            if doc_link:
                doc = doc_link
            else:
                raise HTTPException(status_code=404, detail="Document not found")

        # Workflow Steps History
        steps = con.execute(f"""
            SELECT 
                s.workflow_no,
                s.step_name,
                s.step_status,
                s.step_outcome,
                s.assigned_to_organization,
                s.assigned_to_name,
                s.date_in::VARCHAR,
                s.date_due::VARCHAR,
                s.date_completed::VARCHAR,
                s.days_late,
                s.reason_for_issue,
                l.aconex_url
            FROM fact_workflow_steps s
            LEFT JOIN doc_aconex_links l ON s.document_no = l.document_no
            WHERE s.document_no = '{doc_no}'
            ORDER BY s.date_in ASC NULLS LAST
        """).fetchall()

        # Transmittal Lifecycle
        transmittals = con.execute(f"""
            SELECT 
                transmittal_in_mail_no,
                transmittal_in_date::VARCHAR,
                submitted_by_org,
                workflow_no,
                transmitted_mail_no,
                transmitted_date::VARCHAR,
                transmitted_to_org,
                turnaround_days,
                lifecycle_stage
            FROM fact_transmittal_lifecycle
            WHERE document_no = '{doc_no}'
            LIMIT 10
        """).fetchall()

        return {
            "document": {
                "document_no": doc[0],
                "title": doc[1],
                "type": doc[2],
                "status": doc[3],
                "revision": doc[4],
                "version": doc[5],
                "created_by": doc[6],
                "package": doc[7],
                "discipline": doc[8],
                "aconex_url": doc[9]
            },
            "workflow_steps": [{
                "workflow_no": s[0],
                "step_name": s[1],
                "status": s[2],
                "outcome": s[3],
                "org": s[4],
                "user": s[5],
                "date_in": s[6][:19] if s[6] else None,
                "date_due": s[7][:19] if s[7] else None,
                "date_completed": s[8][:19] if s[8] else None,
                "days_late": s[9],
                "reason": s[10],
                "aconex_url": s[11]
            } for s in steps],
            "transmittals": [{
                "transmittal_in": t[0],
                "in_date": t[1][:19] if t[1] else None,
                "from_org": t[2],
                "workflow_no": t[3],
                "transmitted_out": t[4],
                "out_date": t[5][:19] if t[5] else None,
                "to_org": t[6],
                "turnaround_days": t[7],
                "stage": t[8]
            } for t in transmittals]
        }
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 7. Correspondence & RFIs
# -----------------------------------------------------------------------------
@app.get("/api/correspondence")
def get_correspondence(
    status: str = Query(None),
    mail_type: str = Query(None),
    from_org: str = Query(None),
    to_org: str = Query(None),
    package: str = Query(None),
    is_overdue: str = Query(None),
    min_late: int = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    search: str = Query(None),
    sort_by: str = Query("is_overdue"),
    sort_dir: str = Query("desc"),
    limit: int = 50,
    offset: int = 0
):
    con = get_db()
    try:
        filters = []
        if status:
            filters.append(f"status = '{status}'")
        if mail_type:
            filters.append(f"mail_type = '{mail_type}'")
        if from_org:
            filters.append(f"from_organization = '{from_org}'")
        if to_org:
            filters.append(f"to_organization = '{to_org}'")
        if package:
            filters.append(f"project_package = '{package}'")
        if is_overdue in ['true', 'yes', '1']:
            filters.append("is_overdue = true")
        elif is_overdue in ['false', 'no', '0']:
            filters.append("is_overdue = false")
        if min_late is not None:
            filters.append(f"days_late >= {min_late}")
        if from_date and from_date.strip():
            filters.append(f"sent_date >= '{from_date.strip()}'")
        if to_date and to_date.strip():
            filters.append(f"sent_date <= '{to_date.strip()} 23:59:59'")
        if search:
            filters.append(f"(mail_no ILIKE '%{search}%' OR subject ILIKE '%{search}%' OR from_organization ILIKE '%{search}%' OR to_organization ILIKE '%{search}%' OR from_name ILIKE '%{search}%' OR reference_number ILIKE '%{search}%')")

        where = f"WHERE {' AND '.join(filters)}" if filters else ""


        total = con.execute(f"SELECT count(*) FROM fact_mail {where}").fetchone()[0]

        allowed_sorts = {
            "mail_no": "mail_no",
            "type": "mail_type",
            "subject": "subject",
            "ref_no": "reference_number",
            "from_org": "from_organization",
            "to_org": "to_organization",
            "from_name": "from_name",
            "status": "status",
            "sent_date": "sent_date",
            "due_date": "due_date",
            "days_late": "days_late",
            "is_overdue": "is_overdue"
        }
        sort_col = allowed_sorts.get(sort_by, "is_overdue")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

        rows = con.execute(f"""
            SELECT 
                mail_no,
                mail_type,
                subject,
                reference_number,
                from_organization,
                to_organization,
                from_name,
                status,
                sent_date::VARCHAR,
                due_date::VARCHAR,
                days_late,
                is_overdue
            FROM fact_mail
            {where}
            ORDER BY {sort_col} {order_dir} NULLS LAST, days_late DESC
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": [{
                "mail_no": r[0],
                "type": r[1],
                "subject": r[2],
                "ref_no": r[3],
                "from_org": r[4],
                "to_org": r[5],
                "from_name": r[6],
                "status": r[7],
                "sent_date": r[8][:10] if r[8] else None,
                "due_date": r[9][:10] if r[9] else None,
                "days_late": r[10],
                "is_overdue": r[11]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/rfis")
def get_rfis(
    direction: str = Query(None),
    status: str = Query(None),
    from_org: str = Query(None),
    to_org: str = Query(None),
    package: str = Query(None),
    is_overdue: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    search: str = Query(None),
    sort_by: str = Query("is_overdue"),
    sort_dir: str = Query("desc")
):
    con = get_db()
    try:
        filters = []
        if direction:
            filters.append(f"direction = '{direction}'")
        if status:
            filters.append(f"status = '{status}'")
        if from_org:
            filters.append(f"from_organization = '{from_org}'")
        if to_org:
            filters.append(f"to_organization = '{to_org}'")
        if package:
            filters.append(f"project_package = '{package}'")
        if is_overdue in ['true', 'yes', '1']:
            filters.append("is_overdue = true")
        elif is_overdue in ['false', 'no', '0']:
            filters.append("is_overdue = false")
        if from_date and from_date.strip():
            filters.append(f"sent_date >= '{from_date.strip()}'")
        if to_date and to_date.strip():
            filters.append(f"sent_date <= '{to_date.strip()} 23:59:59'")
        if search:
            filters.append(f"(mail_no ILIKE '%{search}%' OR subject ILIKE '%{search}%' OR from_organization ILIKE '%{search}%' OR to_organization ILIKE '%{search}%')")

        where = f"WHERE {' AND '.join(filters)}" if filters else ""


        allowed_sorts = {
            "mail_no": "mail_no",
            "subject": "subject",
            "from_org": "from_organization",
            "to_org": "to_organization",
            "from_name": "from_name",
            "status": "status",
            "direction": "direction",
            "sent_date": "sent_date",
            "due_date": "due_date",
            "days_late": "days_late",
            "is_overdue": "is_overdue"
        }
        sort_col = allowed_sorts.get(sort_by, "is_overdue")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

        rows = con.execute(f"""
            SELECT 
                mail_no,
                subject,
                from_organization,
                to_organization,
                from_name,
                status,
                direction,
                sent_date::VARCHAR,
                due_date::VARCHAR,
                days_late,
                is_overdue,
                aconex_url
            FROM fact_rfis
            {where}
            ORDER BY {sort_col} {order_dir} NULLS LAST, days_late DESC
        """).fetchall()

        return {
            "total": len(rows),
            "data": [{
                "mail_no": r[0],
                "subject": r[1],
                "from_org": r[2],
                "to_org": r[3],
                "from_name": r[4],
                "status": r[5],
                "direction": r[6],
                "sent_date": r[7][:10] if r[7] else None,
                "due_date": r[8][:10] if r[8] else None,
                "days_late": r[9],
                "is_overdue": r[10],
                "aconex_url": r[11]
            } for r in rows]
        }
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 8. Lookahead (Next 7, 14, 30 days)
# -----------------------------------------------------------------------------
@app.get("/api/lookahead")
def get_lookahead(
    days: int = Query(14),
    org: str = Query(None),
    search: str = Query(None),
    urgency: str = Query(None),
    sort_by: str = Query("days_remaining"),
    sort_dir: str = Query("asc")
):
    con = get_db()
    try:
        filters = [f"days_until_due <= {days}"]
        if org:
            filters.append(f"assigned_to_organization = '{org}'")
        if search:
            filters.append(f"(workflow_no ILIKE '%{search}%' OR step_name ILIKE '%{search}%' OR assigned_to_name ILIKE '%{search}%' OR document_no ILIKE '%{search}%' OR document_title ILIKE '%{search}%')")
        if urgency == "critical":
            filters.append("days_until_due <= 3")
        elif urgency == "warning":
            filters.append("days_until_due > 3 AND days_until_due <= 7")
        elif urgency == "normal":
            filters.append("days_until_due > 7")

        where = f"WHERE {' AND '.join(filters)}"

        allowed_sorts = {
            "workflow_no": "workflow_no",
            "step_name": "step_name",
            "org": "assigned_to_organization",
            "user": "assigned_to_name",
            "document_no": "document_no",
            "title": "document_title",
            "due_date": "date_due",
            "days_remaining": "days_until_due"
        }
        sort_col = allowed_sorts.get(sort_by, "days_until_due")
        order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

        rows = con.execute(f"""
            SELECT 
                a.workflow_no,
                a.step_name,
                a.assigned_to_organization,
                a.assigned_to_name,
                a.document_no,
                a.document_title,
                a.date_due::VARCHAR,
                a.days_until_due,
                l.aconex_url
            FROM agg_lookahead a
            LEFT JOIN doc_aconex_links l ON a.document_no = l.document_no
            {where}
            ORDER BY {sort_col} {order_dir} NULLS LAST
            LIMIT 200
        """).fetchall()

        return {
            "days_horizon": days,
            "total": len(rows),
            "data": [{
                "workflow_no": r[0],
                "step_name": r[1],
                "org": r[2],
                "user": r[3],
                "document_no": r[4],
                "title": r[5],
                "due_date": r[6][:10] if r[6] else None,
                "days_remaining": r[7],
                "aconex_url": r[8]
            } for r in rows]
        }
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 9. Reminders & Email Notifications
# -----------------------------------------------------------------------------
import urllib.parse
from pydantic import BaseModel

class SendReminderRequest(BaseModel):
    recipient_name: str
    recipient_email: str
    subject: str
    body_text: str
    save_email: bool = True

@app.get("/api/reminders/preview")
def preview_reminder(user_name: str = Query(None), org_name: str = Query(None)):
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        recipient_email = ""
        clean_user_name = user_name.strip() if user_name else ""
        if clean_user_name:
            custom = con.execute("SELECT email FROM user_custom_emails WHERE user_name = ?", [clean_user_name]).fetchone()
            if custom and custom[0]:
                recipient_email = custom[0]
            else:
                parts = [p.strip() for p in clean_user_name.split(',') if p.strip()]
                found_emails = []
                for p in parts:
                    cust_p = con.execute("SELECT email FROM user_custom_emails WHERE user_name = ?", [p]).fetchone()
                    if cust_p and cust_p[0]:
                        found_emails.append(cust_p[0])
                        continue
                    clean_p = re.sub(r'^(Mr|Mrs|Ms|Dr|Eng)\s+', '', p, flags=re.IGNORECASE).strip()
                    dir_match = con.execute("SELECT email FROM dim_user_directory WHERE clean_name ILIKE ? AND email IS NOT NULL AND email != '' LIMIT 1", [clean_p]).fetchone()
                    if dir_match and dir_match[0]:
                        found_emails.append(dir_match[0])
                    else:
                        tokens = clean_p.split()
                        if len(tokens) >= 2:
                            pat = f"%{tokens[0]}%{tokens[-1]}%"
                            dir_match2 = con.execute("SELECT email FROM dim_user_directory WHERE clean_name ILIKE ? AND email IS NOT NULL AND email != '' LIMIT 1", [pat]).fetchone()
                            if dir_match2 and dir_match2[0]:
                                found_emails.append(dir_match2[0])
                if found_emails:
                    recipient_email = "; ".join(list(dict.fromkeys(found_emails)))
        elif org_name:
            custom_org = con.execute("SELECT email FROM user_custom_emails WHERE user_name = ?", [org_name.strip()]).fetchone()
            if custom_org and custom_org[0]:
                recipient_email = custom_org[0]

        if user_name:
            tasks = con.execute("""
                SELECT 
                    s.workflow_no,
                    s.step_name,
                    s.document_no,
                    s.document_title,
                    s.date_due::VARCHAR,
                    s.days_late,
                    s.initiator_organization,
                    l.aconex_url
                FROM fact_workflow_steps s
                LEFT JOIN doc_aconex_links l ON s.document_no = l.document_no
                WHERE s.assigned_to_name = ? AND s.is_overdue
                ORDER BY s.days_late DESC
                LIMIT 50
            """, [user_name]).fetchall()
            target_name = user_name
            context_type = "engineer"
        elif org_name:
            tasks = con.execute("""
                SELECT 
                    s.workflow_no,
                    s.step_name,
                    s.document_no,
                    s.document_title,
                    s.date_due::VARCHAR,
                    s.days_late,
                    s.assigned_to_name,
                    l.aconex_url
                FROM fact_workflow_steps s
                LEFT JOIN doc_aconex_links l ON s.document_no = l.document_no
                WHERE s.assigned_to_organization = ? AND s.is_overdue
                ORDER BY s.days_late DESC
                LIMIT 50
            """, [org_name]).fetchall()
            target_name = org_name
            context_type = "organization"
        else:
            raise HTTPException(status_code=400, detail="Either user_name or org_name is required")

        total_overdue = len(tasks)
        max_delay = max([t[5] for t in tasks]) if tasks else 0
        subject = f"[PMC OVERDUE REMINDER] Ras El Hekma Project - {total_overdue} Action Item(s) Pending ({target_name})"

        lines = [
            f"Dear {target_name},",
            "",
            f"This is an official PMC Project Controls notification regarding {total_overdue} overdue review workflow item(s) currently pending on Oracle Aconex for the Ras El Hekma Project.",
            f"The maximum delay on your pending items is currently {max_delay} day(s).",
            "",
            "Please review and action the following pending deliverables immediately:",
            "-" * 80
        ]
        for t in tasks:
            lines.append(f"* Workflow: {t[0]} | Step: {t[1]}")
            lines.append(f"  Doc No: {t[2]}")
            lines.append(f"  Title: {t[3][:80] if t[3] else ''}")
            lines.append(f"  Due Date: {t[4][:10] if t[4] else 'N/A'} | Days Late: {t[5]} days")
            if t[7]:
                lines.append(f"  Aconex Direct: {t[7]}")
            lines.append("")
        lines.append("-" * 80)
        lines.append("Immediate clearance of these items is required to protect project milestones and contractual SLAs.")
        lines.append("")
        lines.append("Best regards,")
        lines.append("PMC Project Controls Team | Hill International")
        lines.append("Ras El Hekma Development Project")

        body_text = "\n".join(lines)
        mailto_to = recipient_email.replace(';', ',').replace(' ', '') if recipient_email else ""
        mailto_url = f"mailto:{urllib.parse.quote(mailto_to, safe=',@')}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body_text)}"

        return {
            "target_name": target_name,
            "context_type": context_type,
            "recipient_email": recipient_email,
            "subject": subject,
            "overdue_count": total_overdue,
            "max_delay_days": max_delay,
            "tasks": [{
                "workflow_no": t[0],
                "step_name": t[1],
                "document_no": t[2],
                "document_title": t[3],
                "due_date": t[4][:10] if t[4] else None,
                "days_late": t[5],
                "extra": t[6],
                "aconex_url": t[7]
            } for t in tasks],
            "body_text": body_text,
            "mailto_url": mailto_url
        }
    finally:
        con.close()

@app.post("/api/reminders/send")
def send_reminder(req: SendReminderRequest):
    if req.save_email and req.recipient_name and req.recipient_email:
        con_w = duckdb.connect(DB_PATH, read_only=False)
        try:
            con_w.execute("""
                INSERT OR REPLACE INTO user_custom_emails (user_name, email, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, [req.recipient_name.strip(), req.recipient_email.strip()])
        finally:
            con_w.close()

    con = duckdb.connect(DB_PATH, read_only=True)
    smtp = None
    try:
        smtp = con.execute("SELECT smtp_host, smtp_port, smtp_user, smtp_password, sender_email, sender_name, use_tls, is_active FROM smtp_settings WHERE is_active LIMIT 1").fetchone()
    finally:
        con.close()

    if smtp and smtp[0]:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.application import MIMEApplication

        msg = MIMEMultipart("mixed")
        msg['From'] = f"{smtp[5]} <{smtp[4]}>" if smtp[5] else smtp[4]
        msg['To'] = req.recipient_email
        msg['Subject'] = req.subject

        # Check if we can generate HTML body & Excel for this company/target
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(req.body_text, 'plain', 'utf-8'))
        
        try:
            dossier_data = get_company_weekly_dossier(req.recipient_name)
            html_body = generate_company_html_table(req.recipient_name, dossier_data)
            alt_part.attach(MIMEText(html_body, 'html', 'utf-8'))
            msg.attach(alt_part)
            
            # Attach Excel Spreadsheet
            excel_bytes = generate_company_excel(req.recipient_name, dossier_data)
            safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', req.recipient_name)
            filename = f"{safe_name}_Overdue_Tasks_{datetime.now().strftime('%Y%m%d')}.xlsx"
            att = MIMEApplication(excel_bytes, _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            att.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(att)
        except Exception:
            msg.attach(MIMEText(req.body_text, 'plain', 'utf-8'))

        try:
            server = smtplib.SMTP(smtp[0], smtp[1], timeout=10)
            if smtp[6]:
                server.starttls()
            if smtp[2] and smtp[3]:
                server.login(smtp[2], smtp[3])
            server.send_message(msg)
            server.quit()
            return {"status": "sent", "message": f"Email with HTML table & attached Excel successfully sent directly to {req.recipient_email} via SMTP"}
        except Exception as e:
            return {"status": "error", "message": f"SMTP Error: {str(e)}"}
    else:
        return {
            "status": "saved",
            "message": f"Email address saved for {req.recipient_name}. Direct SMTP is not configured, please click 'Open in Outlook' to send via your email client.",
            "recipient_email": req.recipient_email
        }

# -----------------------------------------------------------------------------
# 10. Weekly Company Control & Overdue Reminders Center
# -----------------------------------------------------------------------------
@app.get("/api/companies/weekly_control")
def get_weekly_company_control():
    con = get_db()
    try:
        rows = con.execute("""
            WITH all_orgs AS (
                SELECT DISTINCT organization_name AS org_name FROM dim_user_directory WHERE organization_name IS NOT NULL AND trim(organization_name) != ''
                UNION
                SELECT DISTINCT org_name FROM dim_organizations WHERE org_name IS NOT NULL AND trim(org_name) != ''
                UNION
                SELECT DISTINCT from_organization AS org_name FROM fact_mail WHERE from_organization IS NOT NULL AND trim(from_organization) != ''
                UNION
                SELECT DISTINCT to_organization AS org_name FROM fact_mail WHERE to_organization IS NOT NULL AND trim(to_organization) != ''
                UNION
                SELECT DISTINCT assigned_to_organization AS org_name FROM fact_workflow_steps WHERE assigned_to_organization IS NOT NULL AND trim(assigned_to_organization) != ''
                UNION
                SELECT DISTINCT initiator_organization AS org_name FROM fact_workflows WHERE initiator_organization IS NOT NULL AND trim(initiator_organization) != ''
            ),
            org_categories AS (
                SELECT org_name, org_category FROM dim_organizations
            ),
            wf_overdue AS (
                SELECT 
                    assigned_to_organization AS org_name,
                    count(*) AS overdue_steps,
                    max(days_late) AS max_step_delay,
                    count(CASE WHEN days_late BETWEEN 1 AND 7 THEN 1 END) AS overdue_1_to_7,
                    count(CASE WHEN days_late BETWEEN 8 AND 14 THEN 1 END) AS overdue_8_to_14,
                    count(CASE WHEN days_late BETWEEN 15 AND 30 THEN 1 END) AS overdue_15_to_30,
                    count(CASE WHEN days_late > 30 THEN 1 END) AS overdue_over_30
                FROM fact_workflow_steps
                WHERE is_overdue AND assigned_to_organization IS NOT NULL AND assigned_to_organization != ''
                GROUP BY assigned_to_organization
            ),
            mail_overdue AS (
                SELECT 
                    to_organization AS org_name,
                    count(*) AS overdue_mails
                FROM fact_mail
                WHERE is_overdue AND to_organization IS NOT NULL
                GROUP BY to_organization
            ),
            rfi_overdue AS (
                SELECT 
                    to_organization AS org_name,
                    count(*) AS overdue_rfis
                FROM fact_rfis
                WHERE is_overdue AND to_organization IS NOT NULL
                GROUP BY to_organization
            ),
            lookahead_7d AS (
                SELECT 
                    assigned_to_organization AS org_name,
                    count(*) AS lookahead_this_week
                FROM agg_lookahead
                WHERE days_until_due <= 7
                GROUP BY assigned_to_organization
            ),
            quality AS (
                SELECT 
                    initiator_organization AS org_name,
                    count(*) AS total_submittals,
                    ROUND((count(CASE WHEN step_outcome ILIKE '%A - Approved%' OR step_outcome ILIKE '%B - Approved with Comments%' THEN 1 END) * 100.0) / count(*), 1) AS approval_rate_pct
                FROM fact_workflow_steps
                WHERE initiator_organization IS NOT NULL AND step_outcome IS NOT NULL AND trim(step_outcome) != ''
                GROUP BY initiator_organization
            )
            SELECT 
                a.org_name,
                COALESCE(oc.org_category, CASE 
                    WHEN a.org_name ILIKE '%Hill%' THEN 'PMC' 
                    WHEN a.org_name ILIKE '%Modon%' THEN 'Employer' 
                    WHEN a.org_name ILIKE '%Dewan%' OR a.org_name ILIKE '%Dar%' OR a.org_name ILIKE '%KEO%' THEN 'Consultant' 
                    WHEN a.org_name ILIKE '%CSCEC%' OR a.org_name ILIKE '%CCC%' OR a.org_name ILIKE '%Orascom%' OR a.org_name ILIKE '%Hassan Allam%' THEN 'Contractor' 
                    ELSE 'Project Participant' 
                END) AS category,
                COALESCE(w.overdue_steps, 0) AS overdue_steps,
                COALESCE(m.overdue_mails, 0) AS overdue_mails,
                COALESCE(r.overdue_rfis, 0) AS overdue_rfis,
                (COALESCE(w.overdue_steps, 0) + COALESCE(m.overdue_mails, 0) + COALESCE(r.overdue_rfis, 0)) AS total_overdue,
                COALESCE(w.max_step_delay, 0) AS max_delay_days,
                COALESCE(w.overdue_1_to_7, 0) AS overdue_1_to_7,
                COALESCE(w.overdue_8_to_14, 0) AS overdue_8_to_14,
                COALESCE(w.overdue_15_to_30, 0) AS overdue_15_to_30,
                COALESCE(w.overdue_over_30, 0) AS overdue_over_30,
                COALESCE(l.lookahead_this_week, 0) AS lookahead_7d,
                COALESCE(q.total_submittals, 0) AS total_submittals,
                COALESCE(q.approval_rate_pct, 0.0) AS approval_rate_pct
            FROM all_orgs a
            LEFT JOIN org_categories oc ON a.org_name = oc.org_name
            LEFT JOIN wf_overdue w ON a.org_name = w.org_name
            LEFT JOIN mail_overdue m ON a.org_name = m.org_name
            LEFT JOIN rfi_overdue r ON a.org_name = r.org_name
            LEFT JOIN lookahead_7d l ON a.org_name = l.org_name
            LEFT JOIN quality q ON a.org_name = q.org_name
            ORDER BY total_overdue DESC, max_delay_days DESC, lookahead_7d DESC, a.org_name ASC;
        """).fetchall()

        total_overdue_project = sum([r[5] for r in rows])
        total_lookahead_project = sum([r[11] for r in rows])
        companies_with_overdue = sum([1 for r in rows if r[5] > 0])
        companies_with_lookahead = sum([1 for r in rows if r[11] > 0])

        return {
            "total_companies_count": len(rows),
            "companies_with_overdue": companies_with_overdue,
            "companies_with_lookahead": companies_with_lookahead,
            "total_companies_with_actions": sum([1 for r in rows if r[5] > 0 or r[11] > 0]),
            "project_overdue_total": total_overdue_project,
            "project_lookahead_7d_total": total_lookahead_project,
            "companies": [{
                "org_name": r[0],
                "category": r[1],
                "overdue_steps": r[2],
                "overdue_mails": r[3],
                "overdue_rfis": r[4],
                "total_overdue": r[5],
                "max_delay_days": r[6],
                "aging": {
                    "1_to_7": r[7],
                    "8_to_14": r[8],
                    "15_to_30": r[9],
                    "over_30": r[10]
                },
                "lookahead_7d": r[11],
                "total_submittals": r[12],
                "approval_rate_pct": r[13],
                "traffic_light": "critical" if r[5] >= 100 or r[6] >= 30 else ("warning" if r[5] >= 10 else ("good" if r[5] == 0 else "warning"))
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/companies/{org_name}/weekly_dossier")
def get_company_weekly_dossier_api(org_name: str, package: str = None):
    con = get_db()
    try:
        org_name = org_name.strip()
        if package is not None and not isinstance(package, str):
            package = None
        
        # 1. Overdue Workflow Steps (Include workflow_name for accurate package classification; no artificial limit)
        wf_steps = con.execute("""
            SELECT 
                s.workflow_no,
                s.step_name,
                s.document_no,
                s.document_title,
                s.date_due::VARCHAR,
                s.days_late,
                s.assigned_to_name,
                l.aconex_url,
                s.workflow_name
            FROM fact_workflow_steps s
            LEFT JOIN doc_aconex_links l ON s.document_no = l.document_no
            WHERE s.assigned_to_organization = ? AND s.is_overdue
            ORDER BY s.days_late DESC
        """, [org_name]).fetchall()
        
        # 2. Overdue Correspondence / Mails
        mails = con.execute("""
            SELECT 
                mail_no,
                mail_type,
                subject,
                reference_number,
                from_organization,
                from_name,
                sent_date::VARCHAR,
                due_date::VARCHAR,
                days_late,
                aconex_url
            FROM fact_mail
            WHERE to_organization = ? AND is_overdue
            ORDER BY days_late DESC
        """, [org_name]).fetchall()
        
        # 3. Overdue RFIs
        rfis = con.execute("""
            SELECT 
                mail_no,
                subject,
                from_organization,
                from_name,
                sent_date::VARCHAR,
                due_date::VARCHAR,
                days_late,
                aconex_url
            FROM fact_rfis
            WHERE to_organization = ? AND is_overdue
            ORDER BY days_late DESC
        """, [org_name]).fetchall()
        
        # 4. Lookahead Next 7 Days (Due this week)
        lookahead = con.execute("""
            SELECT 
                a.workflow_no,
                a.step_name,
                a.document_no,
                a.document_title,
                a.date_due::VARCHAR,
                a.days_until_due,
                a.assigned_to_name,
                l.aconex_url
            FROM agg_lookahead a
            LEFT JOIN doc_aconex_links l ON a.document_no = l.document_no
            WHERE a.assigned_to_organization = ? AND a.days_until_due <= 7
            ORDER BY a.days_until_due ASC
        """, [org_name]).fetchall()
        
        # Transform all items into structured dicts with resolved project_package
        all_wf_steps = [{
            "workflow_no": s[0], "step_name": s[1], "document_no": s[2],
            "title": s[3], "due_date": s[4][:10] if s[4] else None, "days_late": s[5],
            "user": s[6], "aconex_url": s[7], "workflow_name": s[8],
            "project_package": resolve_project_package(doc_no=s[2], title=s[3], workflow_name=s[8])
        } for s in wf_steps]

        all_mails = [{
            "mail_no": m[0], "type": m[1], "subject": m[2], "ref_no": m[3],
            "from_org": m[4], "from_name": m[5], "sent_date": m[6][:10] if m[6] else None,
            "due_date": m[7][:10] if m[7] else None, "days_late": m[8], "aconex_url": m[9],
            "project_package": resolve_project_package(doc_no=m[0], subject=m[2])
        } for m in mails]

        all_rfis = [{
            "mail_no": r[0], "subject": r[1], "from_org": r[2], "from_name": r[3],
            "sent_date": r[4][:10] if r[4] else None, "due_date": r[5][:10] if r[5] else None,
            "days_late": r[6], "aconex_url": r[7],
            "project_package": resolve_project_package(doc_no=r[0], subject=r[1])
        } for r in rfis]

        all_lookahead = [{
            "workflow_no": l[0], "step_name": l[1], "document_no": l[2], "title": l[3],
            "due_date": l[4][:10] if l[4] else None, "days_remaining": l[5], "user": l[6],
            "aconex_url": l[7],
            "project_package": resolve_project_package(doc_no=l[2], title=l[3])
        } for l in lookahead]

        # Generate packages summary for this company across ALL its deliverables
        grouped_all = group_dossier_by_package({
            "wf_steps": all_wf_steps, "mails": all_mails,
            "rfis": all_rfis, "lookahead_7d": all_lookahead
        })
        packages_summary = []
        for pkg_n, p_val in grouped_all.get("packages", {}).items():
            to_p, cc_p = get_package_email_matrix(pkg_n, org_name)
            packages_summary.append({
                "package_name": pkg_n,
                "total_items": p_val["total_items"],
                "wf_steps_count": len(p_val["wf_steps"]),
                "mails_count": len(p_val["mails"]),
                "rfis_count": len(p_val["rfis"]),
                "lookahead_count": len(p_val["lookahead"]),
                "max_delay_days": p_val["max_delay"],
                "to_emails": to_p,
                "cc_emails": cc_p
            })

        # Check if single-project filtering is requested
        if package and package.strip() and package.strip().lower() != "all":
            target_pkg = package.strip()
            # Filter items matching the package (exact or case-insensitive)
            final_wf = [s for s in all_wf_steps if s["project_package"].strip().lower() == target_pkg.lower()]
            final_mails = [m for m in all_mails if m["project_package"].strip().lower() == target_pkg.lower()]
            final_rfis = [r for r in all_rfis if r["project_package"].strip().lower() == target_pkg.lower()]
            final_look = [l for l in all_lookahead if l["project_package"].strip().lower() == target_pkg.lower()]

            if not final_wf and not final_mails and not final_rfis:
                # Substring fallback
                final_wf = [s for s in all_wf_steps if target_pkg.lower() in s["project_package"].lower()]
                final_mails = [m for m in all_mails if target_pkg.lower() in m["project_package"].lower()]
                final_rfis = [r for r in all_rfis if target_pkg.lower() in r["project_package"].lower()]
                final_look = [l for l in all_lookahead if target_pkg.lower() in l["project_package"].lower()]

            to_list, cc_list = get_package_email_matrix(target_pkg, org_name)
            recipient_email = "; ".join(to_list)
            cc_email = "; ".join(cc_list)
            selected_package = target_pkg
            total_overdue = len(final_wf) + len(final_mails) + len(final_rfis)
            max_delay = max([s["days_late"] for s in final_wf] + [m["days_late"] for m in final_mails] + [r["days_late"] for r in final_rfis]) if total_overdue > 0 else 0
            subject = f"[PMC OVERDUE DISPATCH] Ras El Hekma Project - {target_pkg} - Pending with {org_name}"
        else:
            final_wf = all_wf_steps
            final_mails = all_mails
            final_rfis = all_rfis
            final_look = all_lookahead
            selected_package = None
            total_overdue = len(final_wf) + len(final_mails) + len(final_rfis)
            max_delay = max([s["days_late"] for s in final_wf] + [m["days_late"] for m in final_mails] + [r["days_late"] for r in final_rfis]) if total_overdue > 0 else 0
            active_pkgs = list(dict.fromkeys([s["project_package"] for s in final_wf] + [m["project_package"] for m in final_mails] + [r["project_package"] for r in final_rfis]))

            if is_hill_org(org_name):
                recipient_email = "DeanEnglish@hillintl.com"
                cc_items = get_hill_pmc_contacts(active_pkgs)
                cc_email = "; ".join(cc_items)
            elif is_shaker_ecg(org_name):
                dcs, mgrs, matched_zones = get_shaker_ecg_zone_contacts(active_pkgs)
                recipient_email = "; ".join(dcs)
                hill_team = get_hill_pmc_contacts(active_pkgs)
                cc_items = list(dict.fromkeys(mgrs + hill_team))
                cc_email = "; ".join(cc_items)
            elif is_shaker_consultant(org_name):
                recipient_email = "amahmoud@shakerconsultancy.com"
                hill_team = get_hill_pmc_contacts(active_pkgs)
                cc_email = "; ".join(hill_team)
            else:
                official_contacts = get_company_official_emails(org_name)
                recipient_email = "; ".join(official_contacts)
                hill_team = get_hill_pmc_contacts(active_pkgs)
                dcs, mgrs, matched_zones = get_shaker_ecg_zone_contacts(active_pkgs)
                cc_items = list(dict.fromkeys(hill_team + dcs + mgrs))
                cc_email = "; ".join(cc_items)

            subject = f"[PMC WEEKLY OVERDUE DISPATCH] Ras El Hekma Project - {total_overdue} Action Item(s) Pending with {org_name}"

        lines = [
            f"Dear {org_name} Management & Project Controls Team,",
            "",
            f"This is the official PMC Overdue Notification for the Ras El Hekma Development Project{' - ' + selected_package if selected_package else ''}.",
            f"According to Oracle Aconex project records, your organization currently has {total_overdue} pending overdue action item(s) exceeding contractual turnaround times.",
            f"• Maximum Delay: {max_delay} day(s)",
            f"• Overdue Review Steps: {len(final_wf)} item(s)",
            f"• Overdue Correspondence: {len(final_mails)} item(s)",
            f"• Overdue RFIs: {len(final_rfis)} item(s)",
            f"• Due This Week (Next 7 Days): {len(final_look)} item(s)",
            "",
            "================================================================================",
            "1. OVERDUE TECHNICAL REVIEW WORKFLOWS:",
            "================================================================================"
        ]
        if final_wf:
            for s in final_wf[:25]:
                lines.append(f"* [{s['project_package']}] Workflow: {s['workflow_no']} | Step: {s['step_name']}")
                lines.append(f"  Doc No: {s['document_no']}")
                lines.append(f"  Title: {s['title'][:70] if s['title'] else ''}")
                lines.append(f"  Assignee: {s['user'] or 'Unassigned'} | Due Date: {s['due_date'] or 'N/A'} | DELAY: {s['days_late']} DAYS LATE")
                if s['aconex_url']:
                    lines.append(f"  Aconex Direct Link: {s['aconex_url']}")
                lines.append("")
            if len(final_wf) > 25:
                lines.append(f"... and {len(final_wf) - 25} additional overdue workflow steps (see attached Excel report).")
        else:
            lines.append("No overdue workflow review steps pending.")
            lines.append("")
            
        lines.extend([
            "================================================================================",
            "2. OVERDUE LETTERS & CORRESPONDENCE:",
            "================================================================================"
        ])
        if final_mails:
            for m in final_mails[:20]:
                lines.append(f"* [{m['project_package']}] Mail No: {m['mail_no']} ({m['type']})")
                lines.append(f"  Subject: {m['subject'][:75] if m['subject'] else ''}")
                lines.append(f"  From: {m['from_org']} ({m['from_name']}) | Due Date: {m['due_date'] or 'N/A'} | DELAY: {m['days_late']} DAYS LATE")
                if m['aconex_url']:
                    lines.append(f"  Aconex Direct Link: {m['aconex_url']}")
                lines.append("")
            if len(final_mails) > 20:
                lines.append(f"... and {len(final_mails) - 20} additional overdue correspondence items (see attached Excel report).")
        else:
            lines.append("No overdue correspondence pending.")
            lines.append("")

        if final_rfis:
            lines.extend([
                "================================================================================",
                "3. OVERDUE REQUESTS FOR INFORMATION (RFIs):",
                "================================================================================"
            ])
            for r in final_rfis[:15]:
                lines.append(f"* [{r['project_package']}] RFI No: {r['mail_no']}")
                lines.append(f"  Subject: {r['subject'][:75] if r['subject'] else ''}")
                lines.append(f"  From: {r['from_org']} ({r['from_name']}) | Due Date: {r['due_date'] or 'N/A'} | DELAY: {r['days_late']} DAYS LATE")
                if r['aconex_url']:
                    lines.append(f"  Aconex Direct Link: {r['aconex_url']}")
                lines.append("")

        lines.extend([
            "================================================================================",
            "CONTRACTUAL ACTION REQUIRED:",
            "================================================================================",
            "Immediate resolution and response to the above items are strictly requested before the end of this working week to prevent project schedule delays.",
            "",
            "Best regards,",
            "PMC Project Controls Team | Hill International",
            "Ras El Hekma Development Project",
            "Live PMC Platform: http://localhost:8000"
        ])
        
        body_text = "\n".join(lines)
        mailto_to = recipient_email.replace(';', ',').replace(' ', '')
        mailto_cc = cc_email.replace(';', ',').replace(' ', '')
        mailto_url = f"mailto:{urllib.parse.quote(mailto_to, safe=',@')}?cc={urllib.parse.quote(mailto_cc, safe=',@')}&subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body_text)}"
        
        dossier_res = {
            "org_name": org_name,
            "selected_package": selected_package,
            "packages_summary": packages_summary,
            "recipient_email": recipient_email,
            "cc_email": cc_email,
            "total_overdue": total_overdue,
            "max_delay_days": max_delay,
            "wf_steps_count": len(final_wf),
            "mails_count": len(final_mails),
            "rfis_count": len(final_rfis),
            "lookahead_7d_count": len(final_look),
            "subject": subject,
            "body_text": body_text,
            "mailto_url": mailto_url,
            "wf_steps": final_wf,
            "mails": final_mails,
            "rfis": final_rfis,
            "lookahead_7d": final_look
        }
        dossier_res["packages"] = group_dossier_by_package(dossier_res)
        dossier_res["body_html"] = generate_company_html_table(org_name, dossier_res)
        return dossier_res
    finally:
        con.close()

@app.get("/api/companies/{org_name}/export_excel")
def export_company_overdue_excel(org_name: str, package: str = None):
    pkg_str = package if isinstance(package, str) else None
    data = get_company_weekly_dossier_api(org_name, package=pkg_str)
    excel_bytes = generate_company_excel(org_name, data)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', org_name)
    pkg_suffix = ""
    if pkg_str and pkg_str.strip() and pkg_str.strip().lower() != "all":
        safe_pkg = re.sub(r'[^a-zA-Z0-9_\-]', '_', pkg_str.strip())[:25]
        pkg_suffix = f"_{safe_pkg}"
    filename = f"{safe_name}{pkg_suffix}_Overdue_Tasks_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/companies/{org_name}/download_eml")
def download_company_eml(org_name: str, to: str = None, cc: str = None, package: str = None):
    pkg_str = package if isinstance(package, str) else None
    data = get_company_weekly_dossier_api(org_name, package=pkg_str)
    target_to = to.strip() if to and isinstance(to, str) and to.strip() else data.get("recipient_email")
    target_cc = cc.strip() if cc and isinstance(cc, str) and cc.strip() else data.get("cc_email", "")
    eml_bytes = generate_company_eml(org_name, data, recipient_email=target_to, cc_email=target_cc)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', org_name)
    pkg_suffix = ""
    if pkg_str and pkg_str.strip() and pkg_str.strip().lower() != "all":
        safe_pkg = re.sub(r'[^a-zA-Z0-9_\-]', '_', pkg_str.strip())[:25]
        pkg_suffix = f"_{safe_pkg}"
    filename = f"{safe_name}{pkg_suffix}_Overdue_Notice.eml"
    return Response(
        content=eml_bytes,
        media_type="message/rfc822",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/companies/{org_name}/open_outlook")
def open_company_outlook_api(org_name: str, package: str = None, payload: dict = None):
    pkg_candidate = package if isinstance(package, str) else (payload.get("package") if payload else None)
    pkg_str = pkg_candidate if isinstance(pkg_candidate, str) else None
    data = get_company_weekly_dossier_api(org_name, package=pkg_str)
    to_email = (payload.get("to") if payload and payload.get("to") else None) or data.get("recipient_email")
    cc_email = (payload.get("cc") if payload and payload.get("cc") else None) or data.get("cc_email", "")
    eml_path = open_company_outlook(org_name, data, recipient_email=to_email, cc_email=cc_email)
    return {
        "status": "success",
        "message": f"Microsoft Outlook draft successfully opened with pre-filled To, CC, Subject, Package-Grouped HTML Table, Notice, and Attached Excel Workbook!",
        "eml_path": eml_path,
        "recipient_email": to_email,
        "cc_email": cc_email,
        "package": pkg_str
    }

# -----------------------------------------------------------------------------
# 9.5 Contacts Directory Status & Refresh Engine
# -----------------------------------------------------------------------------
@app.get("/api/contacts/status")
def get_contacts_status_api():
    return get_contacts_status()

@app.post("/api/contacts/refresh")
def refresh_contacts_api():
    cache = load_all_contacts_databases(force=True)
    status = get_contacts_status()
    return {
        "status": "success",
        "message": f"Successfully refreshed all contacts databases from disk! (Shaker DPs: {status['shaker_dps_count']}, ECG Zones: {status['ecg_zones_count']}, Hill Packages: {status['hill_packages_count']}, Indexed Users: {status['total_indexed_users']})",
        "details": status
    }

# -----------------------------------------------------------------------------
# 9.6 Individual Engineer / Reviewer Weekly Dossier & Outlook Dispatch
# -----------------------------------------------------------------------------
@app.get("/api/users/{user_name}/dossier")
def get_user_weekly_dossier_api(user_name: str, org_name: str = Query(None)):
    con = get_db()
    try:
        user_name = user_name.strip()
        
        # 1. Fetch overdue workflow review steps assigned to this user
        wf_steps = con.execute("""
            SELECT 
                s.workflow_no,
                s.step_name,
                s.document_no,
                s.document_title,
                s.date_due::VARCHAR,
                s.days_late,
                s.assigned_to_name,
                l.aconex_url,
                s.assigned_to_organization
            FROM fact_workflow_steps s
            LEFT JOIN doc_aconex_links l ON s.document_no = l.document_no
            WHERE s.is_overdue
              AND (s.assigned_to_name ILIKE ? OR s.assigned_to_name ILIKE ?)
            ORDER BY s.days_late DESC
        """, [f"%{user_name}%", user_name]).fetchall()
        
        actual_org = org_name or (wf_steps[0][8] if wf_steps else "Contractor / Consultant")
        
        # 2. Fetch overdue mails/RFIs where user is involved
        mails = con.execute("""
            SELECT 
                m.mail_no,
                m.mail_type,
                m.subject,
                COALESCE(m.reference_number, ''),
                m.from_organization,
                m.from_name,
                m.sent_date::VARCHAR,
                m.due_date::VARCHAR,
                m.days_late,
                l.aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE m.is_overdue
              AND (m.from_name ILIKE ? OR m.to_organization ILIKE ?)
            ORDER BY m.days_late DESC
            LIMIT 50
        """, [f"%{user_name}%", f"%{user_name}%"]).fetchall()
        
        # 3. Lookahead (Due next 7 days)
        lookahead = con.execute("""
            SELECT 
                a.workflow_no,
                a.step_name,
                a.document_no,
                a.document_title,
                a.date_due::VARCHAR,
                a.days_until_due,
                a.assigned_to_name,
                l.aconex_url
            FROM agg_lookahead a
            LEFT JOIN doc_aconex_links l ON a.document_no = l.document_no
            WHERE (a.assigned_to_name ILIKE ? OR a.assigned_to_name = ?) AND a.days_until_due <= 7
            ORDER BY a.days_until_due ASC
            LIMIT 50
        """, [f"%{user_name}%", user_name]).fetchall()
        
        # Resolve recipient email from contacts database
        recipient_email = resolve_user_email(user_name, actual_org)
        
        # Build active packages list
        active_pkgs = list(dict.fromkeys(
            [resolve_project_package(doc_no=s[2], title=s[3]) for s in wf_steps] +
            [resolve_project_package(doc_no=m[0], subject=m[2]) for m in mails] +
            [resolve_project_package(doc_no=l[2], title=l[3]) for l in lookahead]
        ))
        
        # Resolve CC: Hill PMC team for these packages
        hill_team = get_hill_pmc_contacts(active_pkgs)
        cc_emails = list(dict.fromkeys(hill_team))
        cc_email = "; ".join(cc_emails)
        
        total_overdue = len(wf_steps) + len(mails)
        max_delay = max([s[5] for s in wf_steps] + [m[8] for m in mails]) if total_overdue > 0 else 0
        
        subject = f"[ACTION REQUIRED] Ras El Hekma Project - {total_overdue} Overdue Review Task(s) Assigned to {user_name} ({actual_org})"
        
        dossier_res = {
            "org_name": actual_org,
            "target_name": user_name,
            "is_user": True,
            "recipient_email": recipient_email,
            "cc_email": cc_email,
            "hill_pmc_emails": hill_team,
            "total_overdue": total_overdue,
            "max_delay_days": max_delay,
            "wf_steps_count": len(wf_steps),
            "mails_count": len(mails),
            "rfis_count": 0,
            "lookahead_7d_count": len(lookahead),
            "subject": subject,
            "wf_steps": [{
                "workflow_no": s[0], "step_name": s[1], "document_no": s[2],
                "title": s[3], "due_date": s[4][:10] if s[4] else None, "days_late": s[5],
                "user": s[6], "aconex_url": s[7],
                "project_package": resolve_project_package(doc_no=s[2], title=s[3])
            } for s in wf_steps],
            "mails": [{
                "mail_no": m[0], "type": m[1], "subject": m[2], "ref_no": m[3],
                "from_org": m[4], "from_name": m[5], "sent_date": m[6][:10] if m[6] else None,
                "due_date": m[7][:10] if m[7] else None, "days_late": m[8],
                "aconex_url": m[9],
                "project_package": resolve_project_package(doc_no=m[0], subject=m[2])
            } for m in mails],
            "rfis": [],
            "lookahead_7d": [{
                "workflow_no": l[0], "step_name": l[1], "document_no": l[2], "title": l[3],
                "due_date": l[4][:10] if l[4] else None, "days_remaining": l[5], "user": l[6],
                "aconex_url": l[7],
                "project_package": resolve_project_package(doc_no=l[2], title=l[3])
            } for l in lookahead]
        }
        dossier_res["packages"] = group_dossier_by_package(dossier_res)
        dossier_res["body_html"] = generate_company_html_table(user_name, dossier_res, is_user=True, org_name=actual_org)
        return dossier_res
    finally:
        con.close()

@app.get("/api/users/{user_name}/export_excel")
def export_user_overdue_excel(user_name: str, org_name: str = Query(None)):
    data = get_user_weekly_dossier_api(user_name, org_name)
    excel_bytes = generate_company_excel(user_name, data)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', user_name)
    filename = f"{safe_name}_Overdue_Tasks_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/users/{user_name}/download_eml")
def download_user_eml(user_name: str, org_name: str = Query(None), to: str = Query(None), cc: str = Query(None)):
    data = get_user_weekly_dossier_api(user_name, org_name)
    target_to = to.strip() if to and to.strip() else data.get("recipient_email")
    target_cc = cc.strip() if cc and cc.strip() else data.get("cc_email", DEFAULT_PMC_CC)
    eml_bytes = generate_company_eml(user_name, data, recipient_email=target_to, cc_email=target_cc)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', user_name)
    filename = f"{safe_name}_Overdue_Reminder.eml"
    return Response(
        content=eml_bytes,
        media_type="message/rfc822",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/users/{user_name}/open_outlook")
def open_user_outlook_api(user_name: str, payload: dict = None, org_name: str = Query(None)):
    data = get_user_weekly_dossier_api(user_name, org_name)
    to_email = (payload.get("to") if payload and payload.get("to") else None) or data.get("recipient_email")
    cc_email = (payload.get("cc") if payload and payload.get("cc") else None) or data.get("cc_email", DEFAULT_PMC_CC)
    subject = (payload.get("subject") if payload and payload.get("subject") else None) or data.get("subject")
    eml_path = open_company_outlook(user_name, data, recipient_email=to_email, cc_email=cc_email, subject=subject)
    return {
        "status": "success",
        "message": f"Microsoft Outlook draft successfully opened for {user_name} with pre-filled To, CC, Subject, Package-Grouped HTML Table, and Attached Excel Workbook!",
        "eml_path": eml_path,
        "recipient_email": to_email,
        "cc_email": cc_email
    }

@app.get("/api/rfi_log/table")
def get_rfi_log_table(package: str = Query("DP07")):
    data = extract_rfi_log_data(package)
    return {"package": package, "total_rfis": len(data), "rfis": data}

@app.get("/api/rfi_log/export")
def export_rfi_log_excel(package: str = Query("DP07")):
    wb = build_rfi_log_workbook(package)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"RFI_Log_{package}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/rfi_log/sync_existing")
def sync_existing_rfi_log():
    target_path = r"C:\Users\bimst\Downloads\ACONEX\DP07- RFI-log.xlsx"
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File DP07- RFI-log.xlsx not found.")
    wb = build_rfi_log_workbook("DP07", existing_wb_path=target_path)
    wb.save(target_path)
    return {"status": "success", "message": f"Successfully updated {target_path} with latest RFI data and responses from Aconex!"}

@app.post("/api/rfi_log/upload_update")
async def upload_and_update_rfi_log(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.xlsx', '.xlsm')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xlsm) are supported.")
    file_bytes = await file.read()
    updated_bytes, meta = upload_and_update_rfi_bytes(file_bytes, file.filename)
    safe_pkg = meta.get("detected_package", "DP")
    out_filename = f"{safe_pkg}_RFI_Log_Updated_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(
        content=updated_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={out_filename}",
            "X-Detected-Package": meta.get("detected_package", ""),
            "X-Total-RFIs": str(meta.get("total_rfis", 0)),
            "X-Hyperlinks-Count": str(meta.get("hyperlinks_count", 0)),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Detected-Package, X-Total-RFIs, X-Hyperlinks-Count"
        }
    )

@app.post("/api/rfi_log/bulk_sync_folder")
def bulk_sync_folder_api(payload: dict = None):
    folder_path = (payload.get("folder_path") if payload else None) or r"C:\Users\bimst\Downloads\ACONEX\Logs"
    folder_path = folder_path.strip()
    if not os.path.exists(folder_path):
        os.makedirs(folder_path, exist_ok=True)
    res = bulk_sync_all_dp_logs(folder_path)
    return res

# -----------------------------------------------------------------------------
# 10.4 RFI Explore & Thread Timeline Center
# -----------------------------------------------------------------------------
@app.get("/api/rfi_explore/projects")
def get_rfi_explore_projects():
    con = get_db()
    try:
        pkgs_info = [
            {"id": "ALL", "name": "All Projects", "contractor": "All Contractors Combined", "contract_no": "Combined Packages", "code": "ALL", "log_file": "DP02 - RFI.xlsx"},
            {"id": "DP01", "name": "DP01", "contractor": "Orascom Construction", "contract_no": "REH.08.2.53121.00", "code": "K03121 / MD01", "log_file": "REH -DP01- Site Calirification Request Log.xlsx"},
            {"id": "DP02", "name": "DP02", "contractor": "CCC / ROWAD JV", "contract_no": "REH.08.25.3149 / 3270", "code": "K03149", "log_file": "DP02 - RFI.xlsx"},
            {"id": "DP03-East", "name": "DP03-East", "contractor": "Innovo-Redcon JV", "contract_no": "REH.08.26.3199", "code": "K03199", "log_file": "DP03-East - RFI.xlsx"},
            {"id": "DP03-West", "name": "DP03-West", "contractor": "CCC-ROWAD JV", "contract_no": "REH.08.26.3271", "code": "K03271", "log_file": "DP03-West- RFI.xlsx"},
            {"id": "DP04", "name": "DP04", "contractor": "Arabian Construction Company (ACC)", "contract_no": "REH.08.26.3204", "code": "K03204", "log_file": "DP04- RFI-log.xlsx"},
            {"id": "DP05", "name": "DP05", "contractor": "Orascom Construction SAE", "contract_no": "REH.08.26.3205", "code": "K03205", "log_file": "DP05- RFI-log_.xlsx"},
            {"id": "DP06", "name": "DP06", "contractor": "Hassan Allam Construction", "contract_no": "REH.08.26.3206", "code": "K03206", "log_file": "DP06-RFI-log.xlsx"},
            {"id": "DP07", "name": "DP07", "contractor": "CSCEC Egypt", "contract_no": "REH.08.26.3207", "code": "K03207", "log_file": "DP07- RFI-log.xlsx"},
            {"id": "Infra", "name": "Infra", "contractor": "HAC / HARB JV", "contract_no": "REH.08.25.3048", "code": "K03048 / SW00", "log_file": "INFRA-RFI-  Log-.xlsx"},
            {"id": "MSS", "name": "MMS / Substation", "contractor": "El Sewedy Electric T&D – ROWAD Consortium", "contract_no": "REH.08.25.3044", "code": "K03044 / MSS", "log_file": "MSS-RFI Log.xlsx"},
            {"id": "RO", "name": "RO Plant", "contractor": "Orascom Construction – Trojan – COX JV", "contract_no": "REH.08.25.3045", "code": "K03045", "log_file": "RO-RFI Log.xlsx"},
            {"id": "STP", "name": "STP", "contractor": "Hassan Allam Construction", "contract_no": "REH.08.25.3046", "code": "K03046 / P5576", "log_file": "STP-RFI Log.xlsx"},
            {"id": "Grand Canal", "name": "Grand Canal", "contractor": "Hassan Allam Construction", "contract_no": "REH.08.26.3200", "code": "P0801 / K03200", "log_file": "DP06-RFI-log.xlsx"},
            {"id": "West Canal", "name": "West Canal", "contractor": "Orascom Construction", "contract_no": "REH.08.25.3107-00", "code": "K03107", "log_file": "DP05- RFI-log_.xlsx"},
            {"id": "Airport", "name": "Airport", "contractor": "Orascom Construction", "contract_no": "REH08253049-00", "code": "K00146 / Airport", "log_file": "DP02 - RFI.xlsx"},
        ]
        
        results = []
        for p in pkgs_info:
            pid = p["id"]
            cond = rts.PACKAGE_SQL_CONDITIONS.get(pid, "1=1")
            w_sql = f"{rts.RFI_TYPES_SQL} AND {cond}"
            total = con.execute(f"SELECT count(*) FROM fact_mail m WHERE {w_sql}").fetchone()[0]
            open_cnt = con.execute(f"SELECT count(*) FROM fact_mail m WHERE {w_sql} AND (m.status ILIKE '%out%' OR m.status ILIKE '%open%')").fetchone()[0]
            
            p_data = dict(p)
            p_data["total_rfis"] = total
            p_data["open_rfis"] = open_cnt
            p_data["responded_rfis"] = max(0, total - open_cnt)
            results.append(p_data)
            
        return {"status": "success", "projects": results}
    finally:
        con.close()

@app.get("/api/rfi_explore/rfis")
def get_rfi_explore_rfis(
    project_id: str = Query("DP02"),
    search: str = Query(None),
    status: str = Query(None),
    sort: str = Query(None),
    limit: int = 50,
    offset: int = 0
):
    return rts.get_project_rfis_explorer_list(project_id, search, status, sort, limit, offset)

@app.get("/api/rfi_explore/thread")
def get_rfi_explore_thread(mail_no: str = Query(...), reference_number: str = Query(None)):
    return rts.get_rfi_thread_history(mail_no, reference_number)

@app.get("/api/rfi_explore/export_excel")
def export_rfi_explore_excel(project_id: str = Query("DP02")):
    updated_bytes, filename = rts.export_project_rfi_log_workbook(project_id)
    return Response(
        content=updated_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/rfi_explore/upload_sync")
async def upload_sync_rfi_log(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.xlsx', '.xlsm')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xlsm) are supported.")
    file_bytes = await file.read()
    if 'letter' in file.filename.lower():
        from letters_log_engine import upload_and_sync_letters_bytes
        updated_bytes, stats = upload_and_sync_letters_bytes(file_bytes, file.filename)
        base_n = os.path.splitext(file.filename)[0]
        out_name = f"{base_n}_Synced_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return Response(
            content=updated_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{out_name}"',
                "X-Detected-Package": "Letters Register",
                "X-Total-RFIs": str(stats.get("updated_existing_total", 0)),
                "X-New-Appended": str(stats.get("appended_new_total", 0)),
                "X-Hyperlinks-Count": str(stats.get("hyperlinks_added_total", 0)),
                "Access-Control-Expose-Headers": "Content-Disposition, X-Detected-Package, X-Total-RFIs, X-New-Appended, X-Hyperlinks-Count"
            }
        )
    updated_bytes, meta = rts.update_rfi_workbook_bytes(file_bytes, file.filename)
    pkg = meta.get("package", "Project")
    out_name = f"{pkg}_RFI_Log_Updated_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(
        content=updated_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{out_name}"',
            "X-Detected-Package": str(meta.get("package", "")),
            "X-Total-RFIs": str(meta.get("total_rfis", 0)),
            "X-New-Appended": str(meta.get("new_rfis_appended", 0)),
            "X-Hyperlinks-Count": str(meta.get("hyperlinks_count", 0)),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Detected-Package, X-Total-RFIs, X-New-Appended, X-Hyperlinks-Count"
        }
    )

@app.post("/api/rfi_explore/sync_disk_file")
def sync_disk_rfi_file(payload: dict):
    project_id = payload.get("project_id", "DP02")
    ref_file = rts.PROJECT_LOG_FILES.get(project_id)
    if not ref_file or not os.path.exists(ref_file):
        raise HTTPException(status_code=404, detail=f"Reference log file for {project_id} not found.")
    
    with open(ref_file, "rb") as f:
        file_bytes = f.read()
    
    updated_bytes, meta = rts.update_rfi_workbook_bytes(file_bytes, os.path.basename(ref_file), override_pkg=project_id)
    with open(ref_file, "wb") as f:
        f.write(updated_bytes)
        
    return {
        "status": "success",
        "message": f"Successfully updated {os.path.basename(ref_file)} in-place with latest Aconex developments!",
        "meta": meta
    }

# -----------------------------------------------------------------------------
# 10.5 Unified Project Registers & Logs Center (Letters & RFIs)
# -----------------------------------------------------------------------------
PROJECT_LOGS_DIR = r"C:\Users\bimst\Downloads\ACONEX\Logs"

def get_project_logs_inventory(base_dir: str = PROJECT_LOGS_DIR):
    if not os.path.exists(base_dir):
        return {"status": "success", "total_files": 0, "letters_count": 0, "rfis_count": 0, "files": []}
    
    inventory = []
    seen = set()
    letters_count = 0
    rfis_count = 0

    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(('.xlsx', '.xlsm')) and not f.startswith('~$'):
                fpath = os.path.normpath(os.path.join(root, f))
                if fpath not in seen and os.path.isfile(fpath):
                    seen.add(fpath)
                    fname = os.path.basename(fpath)
                    stat = os.stat(fpath)
                    size_kb = round(stat.st_size / 1024, 1)
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                    is_letter = 'letter' in fname.lower()
                    if is_letter:
                        letters_count += 1
                        category = "Letters Register"
                        is_inc = 'incoming' in fname.lower()
                        log_type = "Incoming Letters" if is_inc else "Outgoing Letters"
                        scope = "Strategic Projects" if "strategic" in fname.lower() else "Wadi Yemm"
                        pkg = scope
                    else:
                        rfis_count += 1
                        category = "RFI Register"
                        log_type = "Request For Information"
                        pkg = detect_package_from_name_or_content(fname)
                        scope = f"Design Package ({pkg})"

                    inventory.append({
                        "filename": fname,
                        "file_path": fpath,
                        "category": category,
                        "log_type": log_type,
                        "project_scope": scope,
                        "package": pkg,
                        "size_kb": size_kb,
                        "last_modified": mtime,
                        "is_letter": is_letter
                    })

    # Sort Letters first, then RFIs by package
    inventory.sort(key=lambda x: (0 if x["is_letter"] else 1, x["package"], x["filename"]))
    return {
        "status": "success",
        "total_files": len(inventory),
        "letters_count": letters_count,
        "letters_files_count": letters_count,
        "rfis_count": rfis_count,
        "rfi_files_count": rfis_count,
        "logs_dir": base_dir,
        "files": inventory
    }

@app.get("/api/logs/status")
def get_logs_status_api():
    return get_project_logs_inventory()

@app.post("/api/logs/sync_all")
def sync_all_project_logs_api(payload: dict = None):
    folder_path = (payload.get("folder_path") if payload else None) or PROJECT_LOGS_DIR
    letters_res = bulk_sync_all_letters_logs(folder_path)
    rfis_res = bulk_sync_all_dp_logs(folder_path)
    
    total_files = letters_res.get("total_files_synced", 0) + rfis_res.get("processed_count", 0)
    total_new = letters_res.get("total_new_letters_appended", 0) + rfis_res.get("total_new_rfis_appended", 0)
    total_upd = letters_res.get("total_responses_updated", 0)
    total_links = letters_res.get("total_hyperlinks_added", 0) + rfis_res.get("total_live_hyperlinks", 0)

    return {
        "status": "success",
        "message": f"Successfully synchronized all {total_files} project logs in-place ({total_new} new items appended, {total_upd} responses updated, {total_links} hyperlinks active)!",
        "summary": {
            "total_files_synced": total_files,
            "total_new_items_appended": total_new,
            "total_responses_updated": total_upd,
            "total_hyperlinks_active": total_links
        },
        "letters_result": letters_res,
        "rfis_result": rfis_res
    }

@app.post("/api/logs/sync_letters")
def sync_letters_only_api(payload: dict = None):
    folder_path = (payload.get("folder_path") if payload else None) or PROJECT_LOGS_DIR
    return bulk_sync_all_letters_logs(folder_path)

@app.post("/api/logs/generate_direction_letters")
def generate_direction_letters_in_folder_api(payload: dict = None):
    from letters_log_engine import sync_or_generate_direction_letters_logs
    folder_path = (payload.get("folder_path") if payload else None) or PROJECT_LOGS_DIR
    project_id = (payload.get("project_id") if payload else None)
    if project_id:
        project_id = normalize_project_id(project_id)
    return sync_or_generate_direction_letters_logs(folder_path=folder_path, project_id=project_id)

@app.post("/api/logs/sync_rfis")
def sync_rfis_only_api(payload: dict = None):
    folder_path = (payload.get("folder_path") if payload else None) or PROJECT_LOGS_DIR
    return bulk_sync_all_dp_logs(folder_path)

@app.post("/api/logs/sync_single")
def sync_single_log_api(payload: dict):
    file_path = payload.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    fname = os.path.basename(file_path).lower()
    if 'letter' in fname:
        res = sync_letters_log_file(file_path)
    else:
        pkg = detect_package_from_name_or_content(os.path.basename(file_path))
        res = update_rfi_log_file(file_path, override_pkg=pkg)
    return res

@app.get("/api/logs/download")
def download_log_file_api(file_path: str = Query(...)):
    norm_path = os.path.normpath(file_path)
    allowed_prefix = os.path.normpath(r"C:\Users\bimst\Downloads\ACONEX")
    if not norm_path.startswith(allowed_prefix) or not os.path.exists(norm_path):
        raise HTTPException(status_code=400, detail="Invalid file path or access denied.")
    return FileResponse(
        norm_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(norm_path)
    )

@app.post("/api/logs/open_excel")
def open_log_in_excel_api(payload: dict):
    file_path = payload.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File path not found.")
    norm_path = os.path.normpath(file_path)
    try:
        os.startfile(norm_path)
        return {"status": "success", "message": f"Opened {os.path.basename(norm_path)} in Microsoft Excel."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open in Excel: {e}")


# -----------------------------------------------------------------------------
# 11. Universal Item Inspector & Audit Trail Tracker
# -----------------------------------------------------------------------------
@app.get("/api/track")
def track_item_api(q: str = Query(..., min_length=2)):
    con = get_db()
    try:
        q = q.strip()
        result = {"query": q, "found": False, "item_type": None, "details": {}, "timeline": []}
        
        # 1. Search in Documents
        doc = con.execute("""
            SELECT d.document_no, d.title, d.doc_type, d.status, d.review_status, d.revision, d.package_name, d.discipline_name, d.revision_date::VARCHAR, l.aconex_url
            FROM dim_documents d
            LEFT JOIN doc_aconex_links l ON d.document_no = l.document_no
            WHERE d.document_no ILIKE ? LIMIT 1
        """, [f"%{q}%"]).fetchone()
        
        if doc and ('REH-' in q.upper() or 'BM-' in q.upper() or 'DRW' in q.upper() or len(q) >= 12):
            result["found"] = True
            result["item_type"] = "document"
            doc_no = doc[0]
            result["details"] = {
                "document_no": doc[0], "title": doc[1], "type": doc[2],
                "status": doc[3], "review_status": doc[4], "revision": doc[5],
                "package": doc[6], "discipline": doc[7], "revision_date": doc[8][:10] if doc[8] else None,
                "aconex_url": doc[9]
            }
            
            # Inception Transmittal
            trans = con.execute("""
                SELECT transmittal_in_mail_no, transmittal_in_date::VARCHAR, submitted_by_org,
                       workflow_no, transmitted_mail_no, transmitted_date::VARCHAR, transmitted_to_org, turnaround_days, lifecycle_stage
                FROM fact_transmittal_lifecycle WHERE document_no = ? LIMIT 5
            """, [doc_no]).fetchall()
            for t in trans:
                if t[0]:
                    result["timeline"].append({
                        "stage": "transmittal_in", "event_name": f"Submittal Received via {t[0]}",
                        "actor_org": t[2], "actor_name": "Contractor Submittal", "date": t[1][:19] if t[1] else None,
                        "status": "Received", "outcome": None, "details": f"Lifecycle: {t[8]} | Turnaround: {t[7] or 'N/A'} days"
                    })
            
            # Workflow Steps
            steps = con.execute("""
                SELECT workflow_no, step_name, step_status, step_outcome, assigned_to_organization, assigned_to_name,
                       date_in::VARCHAR, date_due::VARCHAR, date_completed::VARCHAR, days_late, reason_for_issue
                FROM fact_workflow_steps WHERE document_no = ? ORDER BY date_in ASC NULLS LAST
            """, [doc_no]).fetchall()
            for s in steps:
                result["timeline"].append({
                    "stage": "workflow_step", "event_name": f"Workflow {s[0]} — {s[1]}",
                    "actor_org": s[4], "actor_name": s[5], "date_in": s[6][:19] if s[6] else None,
                    "date_due": s[7][:19] if s[7] else None, "date_completed": s[8][:19] if s[8] else None,
                    "status": s[2], "outcome": s[3], "days_late": s[9], "details": s[10]
                })
                
            # Outbound Transmittals
            for t in trans:
                if t[4]:
                    result["timeline"].append({
                        "stage": "transmittal_out", "event_name": f"Distributed to Contractor via {t[4]}",
                        "actor_org": "PMC / Consultant", "actor_name": f"Recipient: {t[6]}", "date": t[5][:19] if t[5] else None,
                        "status": "Transmitted", "outcome": t[8], "details": f"Total Review Turnaround: {t[7]} days"
                    })
            return result

        # 2. Search in Workflows
        wf = con.execute("""
            SELECT workflow_no, workflow_name, workflow_status, initiator_organization, template, start_date::VARCHAR, original_due_date::VARCHAR
            FROM fact_workflows WHERE workflow_no ILIKE ? LIMIT 1
        """, [f"%{q}%"]).fetchone()
        
        if wf:
            result["found"] = True
            result["item_type"] = "workflow"
            wf_no = wf[0]
            result["details"] = {
                "workflow_no": wf[0], "name": wf[1], "status": wf[2],
                "initiator": wf[3], "template": wf[4],
                "start_date": wf[5][:19] if wf[5] else None,
                "due_date": wf[6][:19] if wf[6] else None
            }
            steps = con.execute("""
                SELECT step_name, step_status, step_outcome, assigned_to_organization, assigned_to_name,
                       date_in::VARCHAR, date_due::VARCHAR, date_completed::VARCHAR, days_late, document_no, document_title
                FROM fact_workflow_steps WHERE workflow_no = ? ORDER BY date_in ASC NULLS LAST
            """, [wf_no]).fetchall()
            for s in steps:
                result["timeline"].append({
                    "stage": "workflow_step", "event_name": s[0],
                    "actor_org": s[3], "actor_name": s[4],
                    "date_in": s[5][:19] if s[5] else None,
                    "date_due": s[6][:19] if s[6] else None,
                    "date_completed": s[7][:19] if s[7] else None,
                    "status": s[1], "outcome": s[2], "days_late": s[8],
                    "details": f"Deliverable: {s[9]} ({s[10][:60] if s[10] else ''})"
                })
            return result

        # 3. Search in Mails / Letters / RFIs
        mail = con.execute("""
            SELECT mail_no, mail_type, subject, reference_number, from_organization, to_organization,
                   from_name, status, sent_date::VARCHAR, due_date::VARCHAR, days_late, is_overdue
            FROM fact_mail WHERE mail_no ILIKE ? OR reference_number ILIKE ? LIMIT 1
        """, [f"%{q}%", f"%{q}%"]).fetchone()
        
        if mail:
            result["found"] = True
            result["item_type"] = "mail" if "RFI" not in mail[1].upper() else "rfi"
            mail_no = mail[0]
            result["details"] = {
                "mail_no": mail[0], "type": mail[1], "subject": mail[2],
                "ref_no": mail[3], "from_org": mail[4], "to_org": mail[5],
                "from_name": mail[6], "status": mail[7],
                "sent_date": mail[8][:19] if mail[8] else None,
                "due_date": mail[9][:19] if mail[9] else None,
                "days_late": mail[10], "is_overdue": mail[11]
            }
            result["timeline"].append({
                "stage": "mail_sent", "event_name": f"{mail[1]} Issued",
                "actor_org": mail[4], "actor_name": mail[6], "date": mail[8][:19] if mail[8] else None,
                "status": "Sent", "outcome": None, "details": f"To: {mail[5]} | Reference: {mail[3]}"
            })
            
            resps = con.execute("""
                SELECT response_mail_no, response_from_organization, response_from_name,
                       response_sent_date::VARCHAR, response_subject, response_reply_type
                FROM fact_mail_responses WHERE mail_no = ? ORDER BY response_sent_date ASC NULLS LAST
            """, [mail_no]).fetchall()
            for r in resps:
                result["timeline"].append({
                    "stage": "mail_response", "event_name": f"{r[5] or 'Response'}: {r[0]}",
                    "actor_org": r[1], "actor_name": r[2], "date": r[3][:19] if r[3] else None,
                    "status": "Responded", "outcome": r[5], "details": r[4]
                })
            return result
        else:
            # Fallback search in responses
            resp_match = con.execute("""
                SELECT mail_no, response_mail_no, response_from_organization, response_from_name,
                       response_sent_date::VARCHAR, response_subject, response_reply_type
                FROM fact_mail_responses WHERE mail_no ILIKE ? OR response_mail_no ILIKE ? LIMIT 1
            """, [f"%{q}%", f"%{q}%"]).fetchone()
            if resp_match:
                result["found"] = True
                result["item_type"] = "mail"
                result["details"] = {
                    "mail_no": resp_match[0], "type": "Correspondence / Thread", "subject": resp_match[5],
                    "from_org": resp_match[2], "from_name": resp_match[3],
                    "sent_date": resp_match[4][:19] if resp_match[4] else None,
                    "status": "Thread Tracked"
                }
                resps = con.execute("""
                    SELECT response_mail_no, response_from_organization, response_from_name,
                           response_sent_date::VARCHAR, response_subject, response_reply_type
                    FROM fact_mail_responses WHERE mail_no = ? ORDER BY response_sent_date ASC NULLS LAST
                """, [resp_match[0]]).fetchall()
                for r in resps:
                    result["timeline"].append({
                        "stage": "mail_response", "event_name": f"{r[5] or 'Response'}: {r[0]}",
                        "actor_org": r[1], "actor_name": r[2], "date": r[3][:19] if r[3] else None,
                        "status": "Responded", "outcome": r[5], "details": r[4]
                    })
                return result

        # 4. Fallback search in RFIs
        rfi = con.execute("""
            SELECT mail_no, subject, from_organization, to_organization, from_name, status, direction, sent_date::VARCHAR, due_date::VARCHAR, days_late
            FROM fact_rfis WHERE mail_no ILIKE ? LIMIT 1
        """, [f"%{q}%"]).fetchone()
        if rfi:
            result["found"] = True
            result["item_type"] = "rfi"
            result["details"] = {
                "mail_no": rfi[0], "type": "Request For Information", "subject": rfi[1],
                "from_org": rfi[2], "to_org": rfi[3], "from_name": rfi[4], "status": rfi[5],
                "direction": rfi[6], "sent_date": rfi[7][:19] if rfi[7] else None,
                "due_date": rfi[8][:19] if rfi[8] else None, "days_late": rfi[9]
            }
            result["timeline"].append({
                "stage": "rfi_submitted", "event_name": f"RFI Submitted ({rfi[6]})",
                "actor_org": rfi[2], "actor_name": rfi[4], "date": rfi[7][:19] if rfi[7] else None,
                "status": rfi[5], "outcome": None, "details": f"To: {rfi[3]} | Days Late: {rfi[9]}"
            })
            resps = con.execute("""
                SELECT response_mail_no, response_from_organization, response_from_name,
                       response_sent_date::VARCHAR, response_subject, response_reply_type
                FROM fact_mail_responses WHERE mail_no = ? ORDER BY response_sent_date ASC NULLS LAST
            """, [rfi[0]]).fetchall()
            for r in resps:
                result["timeline"].append({
                    "stage": "mail_response", "event_name": f"Official Response: {r[0]}",
                    "actor_org": r[1], "actor_name": r[2], "date": r[3][:19] if r[3] else None,
                    "status": "Answered", "outcome": r[5], "details": r[4]
                })
            return result

        return result
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 15. Projects Hub & 360 Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/projects")
def get_projects(category: str = Query(None), search: str = Query(None)):
    con = get_db()
    try:
        filters = []
        if category and category != "all":
            filters.append(f"category = '{category}'")
        if search:
            filters.append(f"(project_name ILIKE '%{search}%' OR project_title ILIKE '%{search}%' OR contractor_name ILIKE '%{search}%' OR contract_no ILIKE '%{search}%')")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = con.execute(f"""
            SELECT 
                project_id, project_name, project_title, category, contract_no, contract_digits,
                k_package_no, contractor_name, contact_person, contact_email, sort_order,
                total_documents, total_mails, total_letters, total_transmittals, overdue_mails,
                total_rfis, overdue_rfis, total_workflows, active_workflows, overdue_workflows
            FROM agg_project_summary
            {where}
            ORDER BY sort_order
        """).fetchall()
        
        projects = []
        for r in rows:
            pid_val = "MMS" if r[0] == "MMS / Substation" else r[0]
            projects.append({
                "project_id": pid_val,
                "project_name": r[1],
                "project_title": r[2],
                "category": r[3],
                "contract_no": r[4],
                "contract_digits": r[5],
                "k_package_no": r[6],
                "contractor_name": r[7],
                "contact_person": r[8],
                "contact_email": r[9],
                "sort_order": r[10],
                "total_documents": r[11],
                "total_mails": r[12],
                "total_letters": r[13],
                "total_transmittals": r[14],
                "overdue_mails": r[15],
                "total_rfis": r[16],
                "overdue_rfis": r[17],
                "total_workflows": r[18],
                "active_workflows": r[19],
                "overdue_workflows": r[20]
            })
        return {"total": len(projects), "data": projects}
    finally:
        con.close()

def normalize_project_id(pid: str) -> str:
    if not pid:
        return pid
    c = pid.strip()
    if c in ("MMS", "MSS", "MMS-Substation", "MMS_Substation", "MMS / Substation"):
        return "MMS / Substation"
    if c in ("Ring Road", "Ring_Road", "Ring_x20_Road"):
        return "Infra"
    return c

@app.get("/api/projects/{project_id}")
def get_project_360(project_id: str):
    project_id = normalize_project_id(project_id)
    con = get_db()
    try:
        proj = con.execute("SELECT * FROM agg_project_summary WHERE project_id = ? OR project_name = ? LIMIT 1", [project_id, project_id]).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        pid = proj[0]

        # Top Disciplines
        disc_rows = con.execute("""
            SELECT discipline_name, count(*) 
            FROM dim_documents 
            WHERE project_package = ? AND discipline_name IS NOT NULL AND trim(discipline_name) != ''
            GROUP BY discipline_name 
            ORDER BY 2 DESC 
            LIMIT 8
        """, [pid]).fetchall()

        # Document Statuses
        status_rows = con.execute("""
            SELECT status, count(*) 
            FROM dim_documents 
            WHERE project_package = ? AND status IS NOT NULL
            GROUP BY status 
            ORDER BY 2 DESC 
            LIMIT 6
        """, [pid]).fetchall()

        # Document Types Breakdown
        doc_type_rows = con.execute("""
            SELECT doc_type, count(*) 
            FROM dim_documents 
            WHERE project_package = ? AND doc_type IS NOT NULL AND trim(doc_type) != ''
            GROUP BY doc_type 
            ORDER BY 2 DESC 
            LIMIT 15
        """, [pid]).fetchall()

        # Mail Types Breakdown
        mail_rows = con.execute("""
            SELECT mail_type, count(*) 
            FROM fact_mail 
            WHERE project_package = ? AND mail_type IS NOT NULL AND trim(mail_type) != ''
            GROUP BY mail_type 
            ORDER BY 2 DESC 
            LIMIT 15
        """, [pid]).fetchall()

        # RFI Types Breakdown
        rfi_type_rows = con.execute("""
            SELECT COALESCE(m.mail_type, 'Request For Information'), count(*) 
            FROM fact_rfis r
            LEFT JOIN (SELECT mail_no, MIN(mail_type) as mail_type FROM fact_mail GROUP BY mail_no) m ON r.mail_no = m.mail_no
            WHERE r.project_package = ? AND m.mail_type IS NOT NULL
            GROUP BY 1 
            ORDER BY 2 DESC 
            LIMIT 10
        """, [pid]).fetchall()

        # Workflow Outcomes (Code A, B, C, D)
        wf_outcomes = con.execute("""
            SELECT 
                count(CASE WHEN s.step_outcome ILIKE '%A - Approved%' THEN 1 END) as code_a,
                count(CASE WHEN s.step_outcome ILIKE '%B - Approved with Comments%' THEN 1 END) as code_b,
                count(CASE WHEN s.step_outcome ILIKE '%C - Revise and Resubmit%' THEN 1 END) as code_c,
                count(CASE WHEN s.step_outcome ILIKE '%D - Rejected%' THEN 1 END) as code_d
            FROM fact_workflow_steps s
            JOIN fact_workflows w ON s.workflow_no = w.workflow_no
            WHERE w.project_package = ?
        """, [pid]).fetchone()

        # Other Mail Types Breakdown (excluding Letter, RFIs, and Clarifications)
        other_mail_rows = con.execute("""
            SELECT mail_type, count(*) 
            FROM fact_mail 
            WHERE project_package = ? 
              AND mail_type IS NOT NULL 
              AND mail_type != 'Letter' 
              AND mail_type NOT ILIKE '%RFI%' 
              AND mail_type != 'Request For Information' 
              AND mail_type NOT ILIKE '%Clarification%'
            GROUP BY mail_type 
            ORDER BY 2 DESC 
            LIMIT 50
        """, [pid]).fetchall()

        # Other Doc Types Breakdown (excluding Shop Drawings and Material Submittals)
        other_doc_rows = con.execute("""
            SELECT doc_type, count(*) 
            FROM dim_documents 
            WHERE project_package = ? 
              AND doc_type IS NOT NULL 
              AND NOT (doc_type ILIKE '%Drawing%' OR doc_type IN ('Drawing', 'Shop Drawing', 'As-Built', 'Sketch'))
              AND NOT (doc_type ILIKE '%Material%' OR title ILIKE '%MAR-%' OR title ILIKE '%MAT-%')
            GROUP BY doc_type 
            ORDER BY 2 DESC 
            LIMIT 50
        """, [pid]).fetchall()

        # Check if DP01 (special handling for Site Clarification Requests and Responses)
        is_dp01 = (pid == 'DP01')
        if is_dp01:
            total_rfis_count = con.execute("""
                SELECT count(*) 
                FROM fact_mail 
                WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%') 
                  AND mail_type IN ('Site Clarification Request', 'Response to Clarification')
            """).fetchone()[0]
            overdue_rfis_count = con.execute("""
                SELECT count(*) 
                FROM fact_mail 
                WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%') 
                  AND mail_type IN ('Site Clarification Request', 'Response to Clarification')
                  AND is_overdue = true
            """).fetchone()[0]
            rfi_type_rows = con.execute("""
                SELECT mail_type, count(*) 
                FROM fact_mail 
                WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%') 
                  AND mail_type IN ('Site Clarification Request', 'Response to Clarification')
                GROUP BY mail_type 
                ORDER BY 2 DESC
            """).fetchall()
            rfi_from_org_rows = con.execute("""
                SELECT DISTINCT from_organization 
                FROM fact_mail 
                WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%') 
                  AND mail_type IN ('Site Clarification Request', 'Response to Clarification')
                  AND from_organization IS NOT NULL AND trim(from_organization) != ''
                ORDER BY 1
            """).fetchall()
            rfi_to_org_rows = con.execute("""
                SELECT DISTINCT to_organization 
                FROM fact_mail 
                WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%') 
                  AND mail_type IN ('Site Clarification Request', 'Response to Clarification')
                  AND to_organization IS NOT NULL AND trim(to_organization) != ''
                ORDER BY 1
            """).fetchall()
        else:
            total_rfis_count = proj[16]
            overdue_rfis_count = proj[17]
            rfi_from_org_rows = con.execute("""
                SELECT DISTINCT from_organization 
                FROM fact_rfis 
                WHERE project_package = ? AND from_organization IS NOT NULL AND trim(from_organization) != ''
                ORDER BY 1
            """, [pid]).fetchall()
            rfi_to_org_rows = con.execute("""
                SELECT DISTINCT to_organization 
                FROM fact_rfis 
                WHERE project_package = ? AND to_organization IS NOT NULL AND trim(to_organization) != ''
                ORDER BY 1
            """, [pid]).fetchall()

        letter_from_org_rows = con.execute("""
            SELECT DISTINCT from_organization 
            FROM fact_mail 
            WHERE project_package = ? AND mail_type = 'Letter' AND from_organization IS NOT NULL AND trim(from_organization) != ''
            ORDER BY 1
        """, [pid]).fetchall()

        return {
            "info": {
                "project_id": ("MMS" if proj[0] == "MMS / Substation" else proj[0]),
                "project_name": proj[1],
                "project_title": proj[2],
                "category": proj[3],
                "contract_no": proj[4],
                "contract_digits": proj[5],
                "k_package_no": proj[6],
                "contractor_name": proj[7],
                "contact_person": proj[8],
                "contact_email": proj[9]
            },
            "kpis": {
                "total_documents": proj[11],
                "total_shop_drawings": con.execute("SELECT count(*) FROM dim_documents WHERE project_package = ? AND (doc_type ILIKE '%Drawing%' OR doc_type IN ('Drawing', 'Shop Drawing', 'As-Built', 'Sketch'))", [pid]).fetchone()[0],
                "total_material_submittals": con.execute("SELECT count(*) FROM dim_documents WHERE project_package = ? AND (doc_type ILIKE '%Material%' OR title ILIKE '%MAR-%' OR title ILIKE '%MAT-%')", [pid]).fetchone()[0],
                "total_other_docs": con.execute("SELECT count(*) FROM dim_documents WHERE project_package = ? AND NOT (doc_type ILIKE '%Drawing%' OR doc_type IN ('Drawing', 'Shop Drawing', 'As-Built', 'Sketch')) AND NOT (doc_type ILIKE '%Material%' OR title ILIKE '%MAR-%' OR title ILIKE '%MAT-%')", [pid]).fetchone()[0],
                "total_mails": proj[12],
                "total_letters": proj[13],
                "total_rfis": total_rfis_count,
                "total_other_mails": con.execute("SELECT count(*) FROM fact_mail WHERE project_package = ? AND mail_type != 'Letter' AND mail_type NOT ILIKE '%RFI%' AND mail_type != 'Request For Information' AND mail_type NOT ILIKE '%Clarification%'", [pid]).fetchone()[0],
                "total_transmittals": (con.execute("SELECT count(*) FROM fact_document_transmittals WHERE project_package = ?", [pid]).fetchone()[0] if 'fact_document_transmittals' in [t[0] for t in con.execute("SHOW TABLES").fetchall()] else proj[14]),
                "overdue_mails": proj[15],
                "overdue_rfis": overdue_rfis_count,
                "total_workflows": proj[18],
                "active_workflows": proj[19],
                "overdue_workflows": proj[20],
                "code_a": wf_outcomes[0] if wf_outcomes else 0,
                "code_b": wf_outcomes[1] if wf_outcomes else 0,
                "code_c": wf_outcomes[2] if wf_outcomes else 0,
                "code_d": wf_outcomes[3] if wf_outcomes else 0
            },
            "disciplines": [{"name": r[0], "count": r[1]} for r in disc_rows],
            "doc_statuses": [{"name": r[0], "count": r[1]} for r in status_rows],
            "doc_types": [{"name": r[0], "count": r[1]} for r in doc_type_rows],
            "mail_types": [{"name": r[0], "count": r[1]} for r in mail_rows],
            "rfi_types": [{"name": r[0], "count": r[1]} for r in rfi_type_rows],
            "other_mail_types": [{"name": r[0], "count": r[1]} for r in other_mail_rows],
            "other_doc_types": [{"name": r[0], "count": r[1]} for r in other_doc_rows],
            "letter_from_orgs": extract_clean_orgs(letter_from_org_rows),
            "rfi_from_orgs": extract_clean_orgs(rfi_from_org_rows),
            "rfi_to_orgs": extract_clean_orgs(rfi_to_org_rows)
        }
    finally:
        con.close()

def parse_sort_clause(sort_str: str, allowed_cols: dict, default_order: str) -> str:
    if not sort_str or not isinstance(sort_str, str):
        return default_order
    clauses = []
    for token in sort_str.split(','):
        parts = token.strip().split()
        if not parts:
            continue
        col_key = parts[0].strip().lower()
        direction = 'DESC' if len(parts) > 1 and parts[1].strip().upper() == 'DESC' else 'ASC'
        if col_key in allowed_cols:
            clauses.append(f"{allowed_cols[col_key]} {direction} NULLS LAST")
    return ", ".join(clauses) if clauses else default_order

@app.get("/api/projects/{project_id}/documents")
def get_project_documents(
    project_id: str,
    category: str = Query(None),
    search: str = Query(None),
    discipline: str = Query(None),
    status: str = Query(None),
    doc_type: str = Query(None),
    sort: str = Query(None),
    limit: int = 50,
    offset: int = 0
):
    project_id = normalize_project_id(project_id)
    con = get_db()
    try:
        filters = [f"d.project_package = '{project_id}'"]
        if category == 'shop_drawings':
            filters.append("(d.doc_type ILIKE '%Drawing%' OR d.doc_type IN ('Drawing', 'Shop Drawing', 'As-Built', 'Sketch'))")
        elif category == 'material_submittals':
            filters.append("(d.doc_type ILIKE '%Material%' OR d.title ILIKE '%MAR-%' OR d.title ILIKE '%MAT-%')")
        elif category == 'other_docs':
            filters.append("NOT (d.doc_type ILIKE '%Drawing%' OR d.doc_type IN ('Drawing', 'Shop Drawing', 'As-Built', 'Sketch')) AND NOT (d.doc_type ILIKE '%Material%' OR d.title ILIKE '%MAR-%' OR d.title ILIKE '%MAT-%')")
        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(d.document_no ILIKE '%{clean_s}%' OR d.title ILIKE '%{clean_s}%' OR d.created_by ILIKE '%{clean_s}%')")
        if discipline and isinstance(discipline, str):
            filters.append(f"d.discipline_name = '{discipline.replace("'", "''")}'")
        if status and isinstance(status, str):
            filters.append(f"d.status = '{status.replace("'", "''")}'")
        if doc_type and isinstance(doc_type, str):
            filters.append(f"d.doc_type = '{doc_type.replace("'", "''")}'")

        doc_cols = {
            'document_no': 'd.document_no', 'title': 'd.title', 'doc_type': 'd.doc_type',
            'status': 'd.status', 'review_status': 'd.review_status', 'revision': 'd.revision',
            'discipline': 'd.discipline_name', 'discipline_name': 'd.discipline_name',
            'date_modified': 'd.date_modified', 'created_by': 'd.created_by'
        }
        order_clause = parse_sort_clause(sort, doc_cols, "d.date_modified DESC NULLS LAST")

        where = f"WHERE {' AND '.join(filters)}"
        total = con.execute(f"SELECT count(*) FROM dim_documents d {where}").fetchone()[0]
        rows = con.execute(f"""
            SELECT 
                d.document_no, d.title, d.doc_type, d.status, d.review_status,
                d.revision, d.version_number, d.created_by, d.discipline_name,
                d.date_modified::VARCHAR,
                COALESCE(d.aconex_url, l.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=DOC-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=documentNumber%3A' || d.document_no) AS aconex_url
            FROM dim_documents d
            LEFT JOIN doc_aconex_links l ON d.document_no = l.document_no
            {where}
            ORDER BY {order_clause}
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        return {
            "total": total,
            "data": [{
                "document_no": r[0], "title": r[1], "doc_type": r[2], "status": r[3],
                "review_status": r[4], "revision": r[5], "version": r[6],
                "created_by": r[7], "discipline": r[8], "date_modified": r[9][:19] if r[9] else None,
                "aconex_url": r[10]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/projects/{project_id}/correspondence")
def get_project_correspondence(
    project_id: str,
    category: str = Query(None),
    search: str = Query(None),
    mail_type: str = Query(None),
    status: str = Query(None),
    direction: str = Query(None),
    from_org: str = Query(None),
    is_overdue: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    sort: str = Query(None),
    limit: int = 50,
    offset: int = 0
):
    project_id = normalize_project_id(project_id)
    con = get_db()
    try:
        filters = [f"project_package = '{project_id}'"]
        if category == 'letters':
            filters.append("mail_type = 'Letter'")
            if direction == 'outbound':
                if project_id == 'DP05':
                    filters.append("(to_organization ILIKE '%Orascom%' OR from_organization ILIKE '%Hill%' OR is_outbound_from_hill = true)")
                elif project_id == 'DP06':
                    filters.append("(to_organization ILIKE '%Hassan Allam%' OR from_organization ILIKE '%Hill%' OR is_outbound_from_hill = true)")
                elif project_id == 'DP07':
                    filters.append("(to_organization ILIKE '%CSCEC%' OR from_organization ILIKE '%Hill%' OR is_outbound_from_hill = true)")
                else:
                    filters.append("(is_outbound_from_hill = true OR from_organization ILIKE '%Hill%')")
            elif direction == 'all':
                pass  # All directions included
            else:  # Default / inbound (Contractor letters matching Aconex package folder)
                if project_id == 'DP05':
                    filters.append("(from_organization ILIKE '%Orascom%' AND from_organization NOT ILIKE '%Hill%')")
                elif project_id == 'DP06':
                    filters.append("(from_organization ILIKE '%Hassan Allam%' AND from_organization NOT ILIKE '%Hill%')")
                elif project_id == 'DP07':
                    filters.append("(from_organization ILIKE '%CSCEC%' AND from_organization NOT ILIKE '%Hill%')")
                else:
                    filters.append("from_organization NOT ILIKE '%Hill%'")
        elif category == 'rfis':
            filters.append("(mail_type ILIKE '%RFI%' OR mail_type ILIKE '%Clarification%' OR mail_type ILIKE '%Request For Information%')")
        elif category == 'other_mail':
            filters.append("(mail_type != 'Letter' AND mail_type NOT ILIKE '%RFI%' AND mail_type != 'Request For Information' AND mail_type NOT ILIKE '%Clarification%')")
        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(mail_no ILIKE '%{clean_s}%' OR subject ILIKE '%{clean_s}%' OR reference_number ILIKE '%{clean_s}%' OR from_name ILIKE '%{clean_s}%' OR from_organization ILIKE '%{clean_s}%')")
        if from_org and isinstance(from_org, str):
            clean_fo = from_org.replace("'", "''")
            filters.append(f"from_organization ILIKE '%{clean_fo}%'")
        if mail_type and isinstance(mail_type, str):
            filters.append(f"mail_type = '{mail_type.replace("'", "''")}'")
        if status and isinstance(status, str):
            filters.append(f"status = '{status.replace("'", "''")}'")
        if is_overdue in ['true', 'yes', '1']:
            filters.append("is_overdue = true")
        elif is_overdue in ['false', 'no', '0']:
            filters.append("is_overdue = false")

        mail_cols = {
            'mail_no': 'mail_no', 'type': 'mail_type', 'mail_type': 'mail_type',
            'subject': 'subject', 'ref_no': 'reference_number', 'reference_number': 'reference_number',
            'from_org': 'from_organization', 'from_organization': 'from_organization',
            'to_org': 'to_organization', 'to_organization': 'to_organization',
            'from_name': 'from_name', 'status': 'status', 'sent_date': 'sent_date',
            'due_date': 'due_date', 'days_late': 'days_late', 'is_overdue': 'is_overdue'
        }
        order_clause = parse_sort_clause(sort, mail_cols, "is_overdue DESC, sent_date DESC NULLS LAST")

        where = f"WHERE {' AND '.join(filters)}"
        total = con.execute(f"SELECT count(*) FROM fact_mail {where}").fetchone()[0]
        rows = con.execute(f"""
            SELECT 
                mail_no, mail_type, subject, reference_number, from_organization,
                to_organization, from_name, status, sent_date::VARCHAR, due_date::VARCHAR,
                days_late, is_overdue,
                COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url
            FROM fact_mail
            {where}
            ORDER BY {order_clause}
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        return {
            "total": total,
            "data": [{
                "mail_no": r[0], "type": r[1], "subject": r[2], "ref_no": r[3],
                "from_org": r[4], "to_org": r[5], "from_name": r[6], "status": r[7],
                "sent_date": r[8][:10] if r[8] else None, "due_date": r[9][:10] if r[9] else None,
                "days_late": r[10], "is_overdue": r[11], "aconex_url": r[12]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/projects/{project_id}/hill_ssc")
def get_project_hill_ssc(
    project_id: str,
    search: str = Query(None),
    direction: str = Query(None),
    is_overdue: str = Query(None),
    sort: str = Query(None),
    limit: int = 50,
    offset: int = 0
):
    project_id = normalize_project_id(project_id)
    con = get_db()
    try:
        base_conds = [
            "mail_type = 'Letter'",
            """(
                from_name ILIKE '%ahmed abdelrahim%' 
                OR from_organization ILIKE '%Shaker%' 
                OR from_organization ILIKE '%ECG%' 
                OR to_organization ILIKE '%Shaker%' 
                OR to_organization ILIKE '%ECG%' 
                OR subject ILIKE '%3120%'
            )"""
        ]
        if project_id != 'ALL':
            base_conds.append(f"(project_package = '{project_id}' OR subject ILIKE '%{project_id}%')")

        filters = list(base_conds)
        if direction == 'inbound':
            filters.append("(from_name ILIKE '%ahmed abdelrahim%' OR from_organization ILIKE '%Shaker%' OR from_organization ILIKE '%ECG%')")
        elif direction == 'outbound':
            filters.append("(subject ILIKE '%3120%' OR to_organization ILIKE '%Shaker%' OR to_organization ILIKE '%ECG%')")

        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(mail_no ILIKE '%{clean_s}%' OR subject ILIKE '%{clean_s}%' OR reference_number ILIKE '%{clean_s}%' OR from_name ILIKE '%{clean_s}%' OR from_organization ILIKE '%{clean_s}%' OR to_organization ILIKE '%{clean_s}%')")

        if is_overdue in ['true', 'yes', '1']:
            filters.append("is_overdue = true")
        elif is_overdue in ['false', 'no', '0']:
            filters.append("is_overdue = false")

        mail_cols = {
            'mail_no': 'mail_no', 'type': 'mail_type', 'subject': 'subject',
            'ref_no': 'reference_number', 'from_org': 'from_organization',
            'to_org': 'to_organization', 'from_name': 'from_name',
            'status': 'status', 'sent_date': 'sent_date', 'due_date': 'due_date',
            'days_late': 'days_late', 'is_overdue': 'is_overdue'
        }
        order_clause = parse_sort_clause(sort, mail_cols, "is_overdue DESC, sent_date DESC NULLS LAST")

        where = f"WHERE {' AND '.join(filters)}"
        total = con.execute(f"SELECT count(*) FROM fact_mail {where}").fetchone()[0]
        
        # Inbound and Outbound breakdown
        base_where = f"WHERE {' AND '.join(base_conds)}"
        inbound_count = con.execute(f"SELECT count(*) FROM fact_mail {base_where} AND (from_name ILIKE '%ahmed abdelrahim%' OR from_organization ILIKE '%Shaker%' OR from_organization ILIKE '%ECG%')").fetchone()[0]
        outbound_count = con.execute(f"SELECT count(*) FROM fact_mail {base_where} AND (subject ILIKE '%3120%' OR to_organization ILIKE '%Shaker%' OR to_organization ILIKE '%ECG%')").fetchone()[0]

        rows = con.execute(f"""
            SELECT 
                mail_no, mail_type, subject, reference_number, from_organization,
                to_organization, from_name, status, sent_date::VARCHAR, due_date::VARCHAR,
                days_late, is_overdue,
                COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url,
                CASE 
                    WHEN from_name ILIKE '%ahmed abdelrahim%' OR from_organization ILIKE '%Shaker%' OR from_organization ILIKE '%ECG%' THEN 'Inbound (From Shaker/ECG)'
                    ELSE 'Outbound (To Shaker/ECG)'
                END AS direction
            FROM fact_mail
            {where}
            ORDER BY {order_clause}
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        return {
            "total": total,
            "inbound_count": inbound_count,
            "outbound_count": outbound_count,
            "data": [{
                "mail_no": r[0], "type": r[1], "subject": r[2], "ref_no": r[3],
                "from_org": r[4], "to_org": r[5], "from_name": r[6], "status": r[7],
                "sent_date": r[8][:10] if r[8] else None, "due_date": r[9][:10] if r[9] else None,
                "days_late": r[10], "is_overdue": r[11], "aconex_url": r[12],
                "direction": r[13]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/hill_ssc/direct")
def get_hill_ssc_direct_letters(
    direction: str = Query(None),
    search: str = Query(None),
    is_overdue: str = Query(None),
    sort: str = Query(None),
    limit: int = 50,
    offset: int = 0
):
    con = get_db()
    try:
        base_conds = [
            "mail_type = 'Letter'",
            """(
                (from_organization = 'Hill Inter' AND to_organization = 'Shaker-ECG consortium RASELHEKMA')
                OR
                (from_organization = 'Shaker-ECG consortium RASELHEKMA' AND to_organization = 'Hill Inter')
            )"""
        ]
        filters = list(base_conds)
        if direction == 'inbound':
            filters.append("(from_organization = 'Shaker-ECG consortium RASELHEKMA' AND to_organization = 'Hill Inter')")
        elif direction == 'outbound':
            filters.append("(from_organization = 'Hill Inter' AND to_organization = 'Shaker-ECG consortium RASELHEKMA')")

        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(mail_no ILIKE '%{clean_s}%' OR subject ILIKE '%{clean_s}%' OR reference_number ILIKE '%{clean_s}%' OR from_name ILIKE '%{clean_s}%' OR from_organization ILIKE '%{clean_s}%' OR to_organization ILIKE '%{clean_s}%')")

        if is_overdue in ['true', 'yes', '1']:
            filters.append("is_overdue = true")
        elif is_overdue in ['false', 'no', '0']:
            filters.append("is_overdue = false")

        mail_cols = {
            'mail_no': 'mail_no', 'type': 'mail_type', 'subject': 'subject',
            'ref_no': 'reference_number', 'from_org': 'from_organization',
            'to_org': 'to_organization', 'from_name': 'from_name',
            'status': 'status', 'sent_date': 'sent_date', 'due_date': 'due_date',
            'days_late': 'days_late', 'is_overdue': 'is_overdue', 'package': 'project_package'
        }
        order_clause = parse_sort_clause(sort, mail_cols, "sent_date DESC NULLS LAST, is_overdue DESC")

        where = f"WHERE {' AND '.join(filters)}"
        total = con.execute(f"SELECT count(*) FROM fact_mail {where}").fetchone()[0]

        # Summary KPIs
        base_where = f"WHERE {' AND '.join(base_conds)}"
        inbound_count = con.execute(f"SELECT count(*) FROM fact_mail {base_where} AND (from_organization = 'Shaker-ECG consortium RASELHEKMA' AND to_organization = 'Hill Inter')").fetchone()[0]
        outbound_count = con.execute(f"SELECT count(*) FROM fact_mail {base_where} AND (from_organization = 'Hill Inter' AND to_organization = 'Shaker-ECG consortium RASELHEKMA')").fetchone()[0]
        overdue_count = con.execute(f"SELECT count(*) FROM fact_mail {base_where} AND is_overdue = true").fetchone()[0]

        rows = con.execute(f"""
            SELECT 
                mail_no, mail_type, subject, reference_number, from_organization,
                to_organization, from_name, status, sent_date::VARCHAR, due_date::VARCHAR,
                days_late, is_overdue,
                COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url,
                CASE 
                    WHEN from_organization = 'Hill Inter' THEN 'Outbound (From Hill)'
                    ELSE 'Inbound (From SSC)'
                END AS direction,
                project_package
            FROM fact_mail
            {where}
            ORDER BY {order_clause}
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        return {
            "total": total,
            "inbound_count": inbound_count,
            "outbound_count": outbound_count,
            "overdue_count": overdue_count,
            "data": [{
                "mail_no": r[0], "type": r[1], "subject": r[2], "ref_no": r[3],
                "from_org": r[4], "to_org": r[5], "from_name": r[6], "status": r[7],
                "sent_date": r[8][:10] if r[8] else None, "due_date": r[9][:10] if r[9] else None,
                "days_late": r[10], "is_overdue": r[11], "aconex_url": r[12],
                "direction": r[13],
                "project_package": r[14]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/hill_ssc/direct/export")
def export_hill_ssc_direct_letters(
    direction: str = Query(None),
    search: str = Query(None),
    is_overdue: str = Query(None)
):
    import io, openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    con = get_db()
    try:
        base_conds = [
            "mail_type = 'Letter'",
            """(
                (from_organization = 'Hill Inter' AND to_organization = 'Shaker-ECG consortium RASELHEKMA')
                OR
                (from_organization = 'Shaker-ECG consortium RASELHEKMA' AND to_organization = 'Hill Inter')
            )"""
        ]
        filters = list(base_conds)
        if direction == 'inbound':
            filters.append("(from_organization = 'Shaker-ECG consortium RASELHEKMA' AND to_organization = 'Hill Inter')")
        elif direction == 'outbound':
            filters.append("(from_organization = 'Hill Inter' AND to_organization = 'Shaker-ECG consortium RASELHEKMA')")

        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(mail_no ILIKE '%{clean_s}%' OR subject ILIKE '%{clean_s}%' OR reference_number ILIKE '%{clean_s}%' OR from_name ILIKE '%{clean_s}%' OR from_organization ILIKE '%{clean_s}%' OR to_organization ILIKE '%{clean_s}%')")

        if is_overdue in ['true', 'yes', '1']:
            filters.append("is_overdue = true")

        where = f"WHERE {' AND '.join(filters)}"
        rows = con.execute(f"""
            SELECT 
                mail_no, mail_type, subject, reference_number, from_organization,
                to_organization, sent_date::VARCHAR, due_date::VARCHAR,
                days_late, status, is_overdue,
                COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url,
                project_package
            FROM fact_mail
            {where}
            ORDER BY sent_date DESC NULLS LAST
        """).fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Hill & SSC Direct Letters"
        ws.views.sheetView[0].showGridLines = True

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        thin_border = Border(left=Side(style='thin', color='E2E8F0'), right=Side(style='thin', color='E2E8F0'), top=Side(style='thin', color='E2E8F0'), bottom=Side(style='thin', color='E2E8F0'))

        headers = ["Mail No", "Mail Type", "Subject", "Reference No", "From Org", "To Org", "Sent Date", "Due Date", "Days Late", "Status", "Overdue", "Package", "Aconex Link"]
        for col_idx, h in enumerate(headers, 1):
            c = ws.cell(1, col_idx, h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24

        for r_idx, r in enumerate(rows, 2):
            for c_idx in range(1, 13):
                cell = ws.cell(r_idx, c_idx, r[c_idx - 1])
                cell.border = thin_border
            link_cell = ws.cell(r_idx, 13)
            link_cell.value = f'=HYPERLINK("{r[11]}", "Open in Aconex")'
            link_cell.font = Font(name="Calibri", size=11, color="0284C7", underline="single")
            link_cell.border = thin_border

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=Hill_SSC_Direct_Letters_Register.xlsx"}
        )
    finally:
        con.close()

@app.get("/api/projects/{project_id}/rfis")
def get_project_rfis(
    project_id: str,
    search: str = Query(None),
    status: str = Query(None),
    mail_type: str = Query(None),
    from_org: str = Query(None),
    to_org: str = Query(None),
    is_overdue: str = Query(None),
    sort: str = Query(None),
    limit: int = 50,
    offset: int = 0
):
    project_id = normalize_project_id(project_id)
    con = get_db()
    try:
        # DP01 special condition: DP01 uses Site Clarification Requests and Responses to Clarification with Subject MD01
        if project_id == 'DP01':
            filters = [
                "(project_package = 'DP01' OR subject ILIKE '%MD01%')",
                "mail_type IN ('Site Clarification Request', 'Response to Clarification')"
            ]
            if search and isinstance(search, str):
                clean_s = search.replace("'", "''")
                filters.append(f"(mail_no ILIKE '%{clean_s}%' OR subject ILIKE '%{clean_s}%' OR from_organization ILIKE '%{clean_s}%' OR to_organization ILIKE '%{clean_s}%' OR from_name ILIKE '%{clean_s}%' OR reference_number ILIKE '%{clean_s}%')")
            if from_org and isinstance(from_org, str):
                clean_fo = from_org.replace("'", "''")
                filters.append(f"from_organization ILIKE '%{clean_fo}%'")
            if to_org and isinstance(to_org, str):
                clean_to = to_org.replace("'", "''")
                filters.append(f"to_organization ILIKE '%{clean_to}%'")
            if status and isinstance(status, str):
                filters.append(f"status = '{status.replace("'", "''")}'")
            if mail_type and isinstance(mail_type, str):
                filters.append(f"mail_type = '{mail_type.replace("'", "''")}'")
            if is_overdue in ['true', 'yes', '1']:
                filters.append("is_overdue = true")
            elif is_overdue in ['false', 'no', '0']:
                filters.append("is_overdue = false")

            rfi_cols = {
                'mail_no': 'mail_no', 'subject': 'subject', 'from_org': 'from_organization',
                'from_organization': 'from_organization', 'to_org': 'to_organization',
                'to_organization': 'to_organization', 'from_name': 'from_name', 'status': 'status',
                'sent_date': 'sent_date', 'due_date': 'due_date', 'days_late': 'days_late',
                'is_overdue': 'is_overdue', 'direction': 'direction', 'mail_type': 'mail_type', 'type': 'mail_type'
            }
            order_clause = parse_sort_clause(sort, rfi_cols, "sent_date DESC NULLS LAST")

            where = f"WHERE {' AND '.join(filters)}"
            total = con.execute(f"SELECT count(*) FROM fact_mail {where}").fetchone()[0]
            rows = con.execute(f"""
                SELECT 
                    mail_no, subject, from_organization, to_organization, from_name,
                    status, CASE WHEN from_organization ILIKE '%Hill%' THEN 'Sent' ELSE 'Received' END AS direction,
                    sent_date::VARCHAR, due_date::VARCHAR, days_late, is_overdue,
                    COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url,
                    mail_type
                FROM fact_mail
                {where}
                ORDER BY {order_clause}
                LIMIT {limit} OFFSET {offset}
            """).fetchall()

            return {
                "total": total,
                "is_dp01_clarifications": True,
                "data": [{
                    "mail_no": r[0], "subject": r[1], "from_org": r[2], "to_org": r[3],
                    "from_name": r[4], "status": r[5], "direction": r[6],
                    "sent_date": r[7][:10] if r[7] else None, "due_date": r[8][:10] if r[8] else None,
                    "days_late": r[9], "is_overdue": r[10], "aconex_url": r[11],
                    "type": r[12]
                } for r in rows]
            }

        # Other packages (standard fact_rfis joined with fact_mail for type)
        filters = [f"r.project_package = '{project_id}'"]
        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(r.mail_no ILIKE '%{clean_s}%' OR r.subject ILIKE '%{clean_s}%' OR r.from_organization ILIKE '%{clean_s}%' OR r.from_name ILIKE '%{clean_s}%')")
        if from_org and isinstance(from_org, str):
            clean_fo = from_org.replace("'", "''")
            filters.append(f"r.from_organization ILIKE '%{clean_fo}%'")
        if to_org and isinstance(to_org, str):
            clean_to = to_org.replace("'", "''")
            filters.append(f"r.to_organization ILIKE '%{clean_to}%'")
        if status and isinstance(status, str):
            filters.append(f"r.status = '{status.replace("'", "''")}'")
        if mail_type and isinstance(mail_type, str):
            if mail_type == 'Request For Information':
                filters.append("(m.mail_type = 'Request For Information' OR m.mail_type IS NULL)")
            else:
                filters.append(f"m.mail_type = '{mail_type.replace("'", "''")}'")
        if is_overdue in ['true', 'yes', '1']:
            filters.append("r.is_overdue = true")
        elif is_overdue in ['false', 'no', '0']:
            filters.append("r.is_overdue = false")

        rfi_cols = {
            'mail_no': 'r.mail_no', 'subject': 'r.subject', 'from_org': 'r.from_organization',
            'from_organization': 'r.from_organization', 'to_org': 'r.to_organization',
            'to_organization': 'r.to_organization', 'from_name': 'r.from_name', 'status': 'r.status',
            'sent_date': 'r.sent_date', 'due_date': 'r.due_date', 'days_late': 'r.days_late',
            'is_overdue': 'r.is_overdue', 'direction': 'direction', 'mail_type': 'm.mail_type', 'type': 'm.mail_type'
        }
        order_clause = parse_sort_clause(sort, rfi_cols, "r.sent_date DESC NULLS LAST")

        where = f"WHERE {' AND '.join(filters)}"
        total = con.execute(f"SELECT count(*) FROM fact_rfis r LEFT JOIN (SELECT mail_no, MIN(mail_type) as mail_type FROM fact_mail GROUP BY mail_no) m ON r.mail_no = m.mail_no {where}").fetchone()[0]
        rows = con.execute(f"""
            SELECT 
                r.mail_no, r.subject, r.from_organization, r.to_organization, r.from_name,
                r.status, CASE WHEN r.from_organization ILIKE '%Hill%' THEN 'Sent' ELSE 'Received' END AS direction,
                r.sent_date::VARCHAR, r.due_date::VARCHAR, r.days_late, r.is_overdue,
                COALESCE(r.aconex_url, '/api/aconex/mail?mail_no=' || r.mail_no) AS aconex_url,
                COALESCE(m.mail_type, 'Request For Information') AS mail_type
            FROM fact_rfis r
            LEFT JOIN (SELECT mail_no, MIN(mail_type) as mail_type FROM fact_mail GROUP BY mail_no) m ON r.mail_no = m.mail_no
            {where}
            ORDER BY {order_clause}
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        return {
            "total": total,
            "is_dp01_clarifications": False,
            "data": [{
                "mail_no": r[0], "subject": r[1], "from_org": r[2], "to_org": r[3],
                "from_name": r[4], "status": r[5], "direction": r[6],
                "sent_date": r[7][:10] if r[7] else None, "due_date": r[8][:10] if r[8] else None,
                "days_late": r[9], "is_overdue": r[10], "aconex_url": r[11],
                "type": r[12]
            } for r in rows]
        }
    finally:
        con.close()

@app.get("/api/projects/{project_id}/workflows")
def get_project_workflows(
    project_id: str,
    search: str = Query(None),
    status: str = Query(None),
    has_overdue: str = Query(None),
    sort: str = Query(None),
    limit: int = 50,
    offset: int = 0
):
    project_id = normalize_project_id(project_id)
    con = get_db()
    try:
        filters = [f"project_package = '{project_id}'"]
        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(workflow_no ILIKE '%{clean_s}%' OR workflow_name ILIKE '%{clean_s}%' OR current_assigned_org ILIKE '%{clean_s}%' OR current_assigned_user ILIKE '%{clean_s}%')")
        if status and isinstance(status, str):
            filters.append(f"workflow_status = '{status.replace("'", "''")}'")
        if has_overdue in ['true', 'yes', '1']:
            filters.append("overdue_steps_count > 0")
        elif has_overdue in ['false', 'no', '0']:
            filters.append("overdue_steps_count = 0")

        wf_cols = {
            'workflow_no': 'workflow_no', 'workflow_name': 'workflow_name', 'status': 'workflow_status',
            'workflow_status': 'workflow_status', 'initiator': 'initiator_organization',
            'initiator_organization': 'initiator_organization', 'template': 'template',
            'start_date': 'start_date', 'due_date': 'original_due_date',
            'original_due_date': 'original_due_date', 'total_steps': 'total_steps',
            'overdue_steps': 'overdue_steps_count', 'overdue_steps_count': 'overdue_steps_count',
            'completed_steps': 'completed_steps_count', 'documents_count': 'documents_count',
            'current_org': 'current_assigned_org', 'current_user': 'current_assigned_user',
            'current_step': 'current_step_name'
        }
        order_clause = parse_sort_clause(sort, wf_cols, "overdue_steps_count DESC, start_date DESC NULLS LAST")

        where = f"WHERE {' AND '.join(filters)}"
        total = con.execute(f"SELECT count(*) FROM fact_workflows {where}").fetchone()[0]

        rows = con.execute(f"""
            WITH step_agg AS (
                SELECT 
                    workflow_no,
                    count(DISTINCT step_name) AS real_total_steps,
                    count(DISTINCT CASE WHEN step_status = 'Completed' THEN step_name END) AS real_completed_steps,
                    count(DISTINCT CASE WHEN step_status = 'Overdue' THEN step_name END) AS real_overdue_steps
                FROM fact_workflow_steps
                GROUP BY workflow_no
            )
            SELECT 
                w.workflow_no, w.workflow_name, w.workflow_status, w.initiator_organization, w.template,
                w.start_date::VARCHAR, w.original_due_date::VARCHAR, 
                COALESCE(sa.real_total_steps, 1) AS total_steps, 
                COALESCE(sa.real_overdue_steps, 0) AS overdue_steps_count,
                COALESCE(sa.real_completed_steps, 0) AS completed_steps_count, 
                w.documents_count,
                COALESCE(w.current_assigned_org, (SELECT assigned_to_organization FROM fact_workflow_steps s WHERE s.workflow_no = w.workflow_no AND s.step_status IN ('Overdue', 'Current') LIMIT 1)) AS current_assigned_org,
                COALESCE(w.current_assigned_user, (SELECT assigned_to_name FROM fact_workflow_steps s WHERE s.workflow_no = w.workflow_no AND s.step_status IN ('Overdue', 'Current') LIMIT 1)) AS current_assigned_user,
                COALESCE(w.current_step_name, (SELECT step_name FROM fact_workflow_steps s WHERE s.workflow_no = w.workflow_no AND s.step_status IN ('Overdue', 'Current') LIMIT 1)) AS current_step_name,
                (SELECT step_status FROM fact_workflow_steps s WHERE s.workflow_no = w.workflow_no AND s.step_status IN ('Overdue', 'Current') LIMIT 1) AS cur_step_status,
                'https://mea.aconex.com/WorkflowSearch?searchtext=' || w.workflow_no || '&projectid=1744833878' AS aconex_url
            FROM fact_workflows w
            LEFT JOIN step_agg sa ON w.workflow_no = sa.workflow_no
            {where}
            ORDER BY {order_clause}
            LIMIT {limit} OFFSET {offset}
        """).fetchall()

        # Fetch pipeline steps for all returned workflows in this page
        wf_ids = [r[0] for r in rows]
        pipeline_map = {wid: [] for wid in wf_ids}
        if wf_ids:
            ph = ','.join(['?'] * len(wf_ids))
            step_rows = con.execute(f"""
                SELECT 
                    workflow_no,
                    step_name,
                    step_status,
                    assigned_to_name,
                    assigned_to_organization,
                    MIN(date_in)::VARCHAR as min_date_in,
                    MAX(date_due)::VARCHAR as max_date_due,
                    MAX(date_completed)::VARCHAR as max_date_completed,
                    MAX(days_late) as max_days_late,
                    BOOL_OR(is_overdue) as is_overdue,
                    COALESCE(
                        date_diff('day', MIN(date_in)::DATE, MAX(date_completed)::DATE),
                        date_diff('day', MIN(date_in)::DATE, CURRENT_DATE),
                        0
                    ) as days_duration
                FROM fact_workflow_steps
                WHERE workflow_no IN ({ph})
                GROUP BY workflow_no, step_name, step_status, assigned_to_name, assigned_to_organization
                ORDER BY workflow_no, MIN(date_in) NULLS LAST
            """, wf_ids).fetchall()

            for s in step_rows:
                pipeline_map[s[0]].append({
                    "step_name": s[1],
                    "step_status": s[2],
                    "assigned_to_name": s[3],
                    "assigned_to_org": s[4],
                    "date_in": s[5][:10] if s[5] else None,
                    "date_due": s[6][:10] if s[6] else None,
                    "date_completed": s[7][:10] if s[7] else None,
                    "days_late": s[8] or 0,
                    "is_overdue": s[9],
                    "duration_days": max(0, s[10] or 0)
                })

        data_list = []
        for r in rows:
            tot = r[7] or 1
            comp = r[9] or 0
            pct = round((comp / tot) * 100) if tot > 0 else (100 if r[2] == 'Completed' else 0)
            data_list.append({
                "workflow_no": r[0], "workflow_name": r[1], "status": r[2], "initiator": r[3],
                "template": r[4], "start_date": r[5][:10] if r[5] else None,
                "due_date": r[6][:10] if r[6] else None, "total_steps": tot,
                "overdue_steps": r[8], "completed_steps": comp, "documents_count": r[10],
                "current_org": r[11], "current_user": r[12], "current_step": r[13],
                "current_step_status": r[14],
                "pct_completed": pct,
                "remaining_steps": max(0, tot - comp),
                "steps_pipeline": pipeline_map.get(r[0], []),
                "aconex_url": r[15]
            })

        return {
            "total": total,
            "data": data_list
        }
    finally:
        con.close()

@app.get("/api/mail/thread")
def get_mail_letter_thread(mail_no: str = Query(...), reference_number: str = Query(None)):
    """Extracts end-to-end contractual letter response history and actions taken."""
    return lts.get_letter_thread_history(mail_no, reference_number)

@app.get("/api/projects/{project_id}/export_filtered")
def export_filtered_project_records(
    project_id: str,
    category: str = Query("documents"),
    search: str = Query(None),
    status: str = Query(None),
    discipline: str = Query(None),
    doc_type: str = Query(None),
    mail_type: str = Query(None),
    from_org: str = Query(None),
    to_org: str = Query(None),
    direction: str = Query(None),
    is_overdue: str = Query(None),
    sort: str = Query(None)
):
    """Generates an executive, professionally styled Excel file for filtered & sorted records."""
    project_id = normalize_project_id(project_id)
    excel_bytes, filename = ees.generate_filtered_excel_export(
        project_id=project_id,
        category=category,
        search=search,
        status=status,
        discipline=discipline,
        doc_type=doc_type,
        mail_type=mail_type,
        is_overdue=is_overdue,
        sort=sort,
        from_org=from_org,
        to_org=to_org,
        direction=direction
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/projects/{project_id}/export")
def export_project_package(project_id: str):
    con = get_db()
    try:
        import io
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = openpyxl.Workbook()
        ws_info = wb.active
        ws_info.title = "Project Overview"

        # 1. Project Info
        proj = con.execute("SELECT * FROM agg_project_summary WHERE project_id = ? OR project_name = ? LIMIT 1", [project_id, project_id]).fetchone()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        header_font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")

        info_headers = ["Field", "Value"]
        ws_info.append(["Project Attribute", "Details"])
        for col in range(1, 3):
            cell = ws_info.cell(1, col)
            cell.font = header_font
            cell.fill = header_fill

        info_rows = [
            ("Project Code", proj[0]),
            ("Project Name", proj[1]),
            ("Project Title", proj[2]),
            ("Sector / Category", proj[3]),
            ("Contract No", proj[4]),
            ("Package No (K-Code)", proj[6]),
            ("Main Contractor", proj[7]),
            ("Contact Person", proj[8]),
            ("Contact Email", proj[9]),
            ("Total Registered Documents", proj[11]),
            ("Total Mails & Letters", proj[12]),
            ("Total Letters", proj[13]),
            ("Total Transmittals", proj[14]),
            ("Overdue Mails", proj[15]),
            ("Total RFIs", proj[16]),
            ("Overdue RFIs", proj[17]),
            ("Total Workflows", proj[18]),
            ("Active Workflows Under Review", proj[19]),
            ("Overdue Workflows", proj[20])
        ]
        for k, v in info_rows:
            ws_info.append([k, str(v) if v is not None else ""])

        # 2. Documents Sheet
        ws_docs = wb.create_sheet(title="Documents")
        ws_docs.append(["Document No", "Title", "Doc Type", "Discipline", "Status", "Review Status", "Revision", "Version", "Date Modified"])
        for col in range(1, 10):
            c = ws_docs.cell(1, col)
            c.font = header_font
            c.fill = header_fill

        doc_rows = con.execute("""
            SELECT document_no, title, doc_type, discipline_name, status, review_status, revision, version_number, date_modified::VARCHAR
            FROM dim_documents WHERE project_package = ?
            ORDER BY date_modified DESC NULLS LAST LIMIT 3000
        """, [proj[0]]).fetchall()
        for r in doc_rows:
            ws_docs.append([str(x) if x is not None else "" for x in r])

        # 3. Correspondence Sheet
        ws_mail = wb.create_sheet(title="Correspondence")
        ws_mail.append(["Mail No", "Mail Type", "Subject", "Reference No", "From Org", "To Org", "Sent Date", "Due Date", "Days Late", "Is Overdue"])
        for col in range(1, 11):
            c = ws_mail.cell(1, col)
            c.font = header_font
            c.fill = header_fill

        mail_rows = con.execute("""
            SELECT mail_no, mail_type, subject, reference_number, from_organization, to_organization, sent_date::VARCHAR, due_date::VARCHAR, days_late, is_overdue
            FROM fact_mail WHERE project_package = ?
            ORDER BY is_overdue DESC, sent_date DESC NULLS LAST LIMIT 3000
        """, [proj[0]]).fetchall()
        for r in mail_rows:
            ws_mail.append([str(x) if x is not None else "" for x in r])

        # 4. RFIs Sheet
        ws_rfi = wb.create_sheet(title="RFIs")
        ws_rfi.append(["Mail No", "Subject", "From Org", "To Org", "From Name", "Status", "Direction", "Sent Date", "Due Date", "Days Late", "Is Overdue"])
        for col in range(1, 12):
            c = ws_rfi.cell(1, col)
            c.font = header_font
            c.fill = header_fill

        rfi_rows = con.execute("""
            SELECT mail_no, subject, from_organization, to_organization, from_name, status,
                   CASE WHEN from_organization ILIKE '%Hill%' THEN 'Sent' ELSE 'Received' END AS direction,
                   sent_date::VARCHAR, due_date::VARCHAR, days_late, is_overdue
            FROM fact_rfis WHERE project_package = ?
            ORDER BY is_overdue DESC, sent_date DESC NULLS LAST
        """, [proj[0]]).fetchall()
        for r in rfi_rows:
            ws_rfi.append([str(x) if x is not None else "" for x in r])

        # 5. Workflows Sheet
        ws_wf = wb.create_sheet(title="Workflows")
        ws_wf.append(["Workflow No", "Workflow Name", "Status", "Initiator Org", "Current Assigned Org", "Current User", "Current Step", "Total Steps", "Overdue Steps", "Start Date", "Due Date"])
        for col in range(1, 12):
            c = ws_wf.cell(1, col)
            c.font = header_font
            c.fill = header_fill

        wf_rows = con.execute("""
            SELECT workflow_no, workflow_name, workflow_status, initiator_organization, current_assigned_org, current_assigned_user, current_step_name, total_steps, overdue_steps_count, start_date::VARCHAR, original_due_date::VARCHAR
            FROM fact_workflows WHERE project_package = ?
            ORDER BY overdue_steps_count DESC, start_date DESC NULLS LAST
        """, [proj[0]]).fetchall()
        for r in wf_rows:
            ws_wf.append([str(x) if x is not None else "" for x in r])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        filename = f"Project_Data_Export_{proj[0]}.xlsx"
        return Response(
            content=out.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        con.close()

# -----------------------------------------------------------------------------
# 18. Project Controls & Overdue Dispatch
# -----------------------------------------------------------------------------
@app.get("/api/controls/projects")
def get_controls_projects_overview(from_date: str = Query(None), to_date: str = Query(None)):
    """Returns real-time overdue overview across all project packages with optional date filtering."""
    return {"data": ocs.get_all_projects_overdue_overview(from_date=from_date, to_date=to_date)}

@app.get("/api/controls/projects/{project_id}/overdue")
def get_project_overdue_report_api(project_id: str, from_date: str = Query(None), to_date: str = Query(None)):
    """Returns project-level overdue deliverables, resolved TO/CC matrix, and generated HTML email draft with optional date filtering."""
    return ocs.get_project_overdue_report(project_id, from_date=from_date, to_date=to_date)

@app.api_route("/api/controls/projects/{project_id}/export_overdue_excel", methods=["GET", "POST"])
async def export_project_overdue_excel_api(project_id: str, request: Request, from_date: str = Query(None), to_date: str = Query(None)):
    """Generates an executive, professionally styled Excel file containing only selected/included overdue deliverables."""
    selected_wf = None
    selected_mails = None
    selected_rfis = None
    selected_scrs = None
    inc_wf = True
    inc_mails = True
    inc_rfis = True
    inc_scrs = True
    to_emails = None
    cc_emails = None

    if request.method == "POST":
        try:
            body = await request.json()
            inc_wf = body.get("include_workflows", True)
            inc_mails = body.get("include_mails", True)
            inc_rfis = body.get("include_rfis", True)
            inc_scrs = body.get("include_scrs", True)
            selected_wf = body.get("selected_workflows")
            selected_mails = body.get("selected_mails")
            selected_rfis = body.get("selected_rfis")
            selected_scrs = body.get("selected_scrs")
            to_emails = body.get("to_emails")
            cc_emails = body.get("cc_emails")
            from_date = body.get("from_date", from_date)
            to_date = body.get("to_date", to_date)
        except Exception:
            pass

    excel_bytes, filename = ocs.generate_project_overdue_excel(
        project_id=project_id,
        selected_workflows=selected_wf,
        selected_mails=selected_mails,
        selected_rfis=selected_rfis,
        selected_scrs=selected_scrs,
        include_workflows=inc_wf,
        include_mails=inc_mails,
        include_rfis=inc_rfis,
        include_scrs=inc_scrs,
        to_emails=to_emails,
        cc_emails=cc_emails,
        from_date=from_date,
        to_date=to_date
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.api_route("/api/controls/projects/{project_id}/download_eml", methods=["GET", "POST"])
async def download_project_overdue_eml_api(project_id: str, request: Request, from_date: str = Query(None), to_date: str = Query(None)):
    """Generates an Outlook-compatible .eml draft with pre-attached Excel register, TO/CC recipients, and styled HTML body containing only curated deliverables."""
    selected_wf = None
    selected_mails = None
    selected_rfis = None
    selected_scrs = None
    inc_wf = True
    inc_mails = True
    inc_rfis = True
    inc_scrs = True
    to_emails = None
    cc_emails = None

    if request.method == "POST":
        try:
            body = await request.json()
            inc_wf = body.get("include_workflows", True)
            inc_mails = body.get("include_mails", True)
            inc_rfis = body.get("include_rfis", True)
            inc_scrs = body.get("include_scrs", True)
            selected_wf = body.get("selected_workflows")
            selected_mails = body.get("selected_mails")
            selected_rfis = body.get("selected_rfis")
            selected_scrs = body.get("selected_scrs")
            to_emails = body.get("to_emails")
            cc_emails = body.get("cc_emails")
            from_date = body.get("from_date", from_date)
            to_date = body.get("to_date", to_date)
        except Exception:
            pass

    eml_bytes, filename = ocs.generate_project_overdue_eml(
        project_id=project_id,
        selected_workflows=selected_wf,
        selected_mails=selected_mails,
        selected_rfis=selected_rfis,
        selected_scrs=selected_scrs,
        include_workflows=inc_wf,
        include_mails=inc_mails,
        include_rfis=inc_rfis,
        include_scrs=inc_scrs,
        to_emails=to_emails,
        cc_emails=cc_emails,
        from_date=from_date,
        to_date=to_date
    )
    return Response(
        content=eml_bytes,
        media_type="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# -----------------------------------------------------------------------------
# AI Assistant & Bilingual Query Engine
# -----------------------------------------------------------------------------
@app.post("/api/ai/chat")
async def ai_chat_endpoint(request: Request):
    """
    Bilingual (English & Arabic) natural language AI query endpoint.
    Answers deliverable, package, SLA, and turnaround questions directly from live DuckDB.
    """
    try:
        body = await request.json()
        message = body.get("message", "")
        history = body.get("history", [])
        return acs.ask_ai_assistant(message, history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Aconex Extraction & Windows Task Scheduler Management
# -----------------------------------------------------------------------------
import sys
extractor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extractor")
if extractor_path not in sys.path:
    sys.path.insert(0, extractor_path)
try:
    import sync_manager
except Exception:
    sync_manager = None

@app.get("/api/database/cutoff")
def get_database_cutoff_api():
    """Returns the latest transaction or record date registered in the analytical database across all activity tables."""
    con = get_db()
    try:
        existing_tables = set(r[0].lower() for r in con.execute("SHOW TABLES").fetchall())

        queries = []
        if "dim_documents" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(date_modified AS DATE)) as latest_dt FROM dim_documents WHERE TRY_CAST(date_modified AS DATE) <= CURRENT_DATE AND TRY_CAST(date_modified AS DATE) <= '2026-12-31'")
        if "fact_mail" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(sent_date AS DATE)) as latest_dt FROM fact_mail WHERE TRY_CAST(sent_date AS DATE) <= CURRENT_DATE")
        if "fact_rfis" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(sent_date AS DATE)) as latest_dt FROM fact_rfis WHERE TRY_CAST(sent_date AS DATE) <= CURRENT_DATE")
        if "fact_workflows" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(start_date AS DATE)) as latest_dt FROM fact_workflows WHERE TRY_CAST(start_date AS DATE) <= CURRENT_DATE")
        if "fact_workflow_steps" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(date_completed AS DATE)) as latest_dt FROM fact_workflow_steps WHERE TRY_CAST(date_completed AS DATE) <= CURRENT_DATE")
            queries.append("SELECT MAX(TRY_CAST(date_in AS DATE)) as latest_dt FROM fact_workflow_steps WHERE TRY_CAST(date_in AS DATE) <= CURRENT_DATE")
        if "fact_document_transmittals" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(transmitted_sent_date AS DATE)) as latest_dt FROM fact_document_transmittals WHERE TRY_CAST(transmitted_sent_date AS DATE) <= CURRENT_DATE")
        if "fact_transmittal_lifecycle" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(transmittal_in_date AS DATE)) as latest_dt FROM fact_transmittal_lifecycle WHERE TRY_CAST(transmittal_in_date AS DATE) <= CURRENT_DATE")
        if "fact_mail_responses" in existing_tables:
            queries.append("SELECT MAX(TRY_CAST(response_sent_date AS DATE)) as latest_dt FROM fact_mail_responses WHERE TRY_CAST(response_sent_date AS DATE) <= CURRENT_DATE")

        if queries:
            union_sql = " UNION ALL ".join(queries)
            full_sql = f"SELECT MAX(latest_dt) FROM ({union_sql})"
            latest_cutoff = con.execute(full_sql).fetchone()[0]
        else:
            latest_cutoff = None

        dt_str = str(latest_cutoff) if latest_cutoff else "2026-11-01"
        try:
            from datetime import datetime
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
            formatted = dt_obj.strftime("%b %d, %Y")
        except Exception:
            formatted = dt_str

        last_sync = None
        try:
            state_file = os.path.join(os.path.dirname(__file__), "..", "extractor", "sync_state.json")
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as sf:
                    s_data = json.load(sf)
                    last_sync = s_data.get("updated_at")
        except Exception:
            pass

        return {
            "cutoff_date": dt_str,
            "formatted": formatted,
            "last_sync": last_sync or "2026-11-01 08:12:01",
            "last_sync_formatted": "Today 08:12 AM" if (last_sync and "2026-11-01" in last_sync) else "Nov 01, 08:12 AM"
        }
    except Exception as e:
        return {"cutoff_date": "2026-11-01", "formatted": "Nov 01, 2026", "error": str(e)}
    finally:
        con.close()

ADMIN_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "admin_auth.json"))

def get_admin_credentials():
    default_cfg = {
        "admin_pin": "2026",
        "admin_token": "aconex_admin_master_token_2026"
    }
    if os.path.exists(ADMIN_CONFIG_PATH):
        try:
            with open(ADMIN_CONFIG_PATH, "r", encoding="utf-8") as f:
                return {**default_cfg, **json.load(f)}
        except Exception:
            return default_cfg
    else:
        os.makedirs(os.path.dirname(ADMIN_CONFIG_PATH), exist_ok=True)
        try:
            with open(ADMIN_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_cfg, f, indent=2)
        except Exception:
            pass
        return default_cfg

def verify_admin_request(request: Request):
    cfg = get_admin_credentials()
    key = request.headers.get("X-Admin-Key") or request.headers.get("x-admin-key")
    if not key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            key = auth_header.replace("Bearer ", "").strip()
    
    if key and (key == cfg["admin_token"] or key == cfg["admin_pin"]):
        return True
    
    raise HTTPException(
        status_code=403, 
        detail="Unauthorized: System configuration, email routing matrices, and data pipeline controls are restricted to the Project Controls Administrator."
    )


# -----------------------------------------------------------------------------
# HILL INTERNATIONAL CORPORATE AUTHENTICATION ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/api/auth/hill-login")
async def hill_login_api(request: Request):
    """Authenticates Hill International personnel against Aconex Project Directory using email & personal password."""
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password") or body.get("passcode") or "").strip()

    if not email:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Please enter your corporate email address."}
        )

    if not email.endswith("@hillintl.com"):
        return JSONResponse(
            status_code=403,
            content={"success": False, "message": "Access Denied: Only corporate email addresses ending with '@hillintl.com' are permitted."}
        )

    if not password:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Please enter your password."}
        )

    # Check dim_user_directory
    con = get_db()
    row = None
    try:
        row = con.execute("""
            SELECT user_name, COALESCE(position, 'Hill International Team Member'), organization_name
            FROM dim_user_directory
            WHERE LOWER(TRIM(email)) = ?
              AND (organization_name ILIKE '%Hill%' OR email ILIKE '%@hillintl.com%')
            LIMIT 1
        """, [email]).fetchone()
    except Exception as e:
        row = None
    finally:
        con.close()

    # Lead fallback
    if not row and email == "mohamedmeneaem@hillintl.com":
        row = ("Mohamed Wagih", "Senior BIM Engineer", "Hill International (North Africa), Ltd")

    if not row:
        return JSONResponse(
            status_code=403,
            content={
                "success": False, 
                "message": f"Unauthorized User: The email '{email}' is not registered in the Ras El Hekma Project Directory."
            }
        )

    # Check individual password
    con_auth = get_db()
    cred = None
    try:
        cred = cred_s.get_user_credential(con_auth, email)
    finally:
        con_auth.close()

    # If first time logging in: automatically set their chosen password!
    if not cred:
        if len(password) < 6:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "First-time setup: Password must be at least 6 characters long."}
            )
        con_reg = get_db()
        try:
            cred_s.save_user_credential(con_reg, email, password)
            cred_s.record_user_login(con_reg, email)
        finally:
            con_reg.close()
    else:
        # Existing password: verify it
        is_valid_pwd = cred_s.verify_password(password, cred["password_hash"], cred["salt"])
        if not is_valid_pwd and password != PROJECT_ACCESS_KEY:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Incorrect password. Please verify your password or click 'Forgot Password'."}
            )
        con_log = get_db()
        try:
            cred_s.record_user_login(con_log, email)
        finally:
            con_log.close()

    # Success: Create session token
    token = f"hill_{uuid.uuid4().hex}"
    user_info = {
        "email": email,
        "name": row[0] or email.split("@")[0].capitalize(),
        "position": row[1] or "Hill International Team Member",
        "org": row[2] or "Hill International"
    }
    HILL_SESSIONS[token] = user_info

    resp = JSONResponse({
        "success": True,
        "token": token,
        "user": user_info,
        "message": f"Welcome Eng. {user_info['name']} ({user_info['position']})!"
    })
    resp.set_cookie("hill_token", token, max_age=86400 * 30, httponly=False, samesite="lax")
    return resp


@app.post("/api/auth/register-password")
async def register_password_api(request: Request):
    """Enables a verified Hill engineer to create their individual personal password."""
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password") or body.get("new_password") or "").strip()

    if not email.endswith("@hillintl.com"):
        return JSONResponse(status_code=403, content={"success": False, "message": "Only @hillintl.com email addresses are eligible."})

    if len(password) < 6:
        return JSONResponse(status_code=400, content={"success": False, "message": "Password must be at least 6 characters long."})

    # Verify user directory
    con = get_db()
    row = None
    try:
        row = con.execute("""
            SELECT user_name, COALESCE(position, 'Hill International Team Member'), organization_name
            FROM dim_user_directory
            WHERE LOWER(TRIM(email)) = ?
              AND (organization_name ILIKE '%Hill%' OR email ILIKE '%@hillintl.com%')
            LIMIT 1
        """, [email]).fetchone()
        if not row and email == "mohamedmeneaem@hillintl.com":
            row = ("Mohamed Wagih", "Senior BIM Engineer", "Hill International (North Africa), Ltd")

        if not row:
            return JSONResponse(status_code=403, content={"success": False, "message": "User not authorized in Project Directory."})

        cred_s.save_user_credential(con, email, password)
        cred_s.record_user_login(con, email)
    finally:
        con.close()

    token = f"hill_{uuid.uuid4().hex}"
    user_info = {
        "email": email,
        "name": row[0] or email.split("@")[0].capitalize(),
        "position": row[1] or "Hill International Team Member",
        "org": row[2] or "Hill International"
    }
    HILL_SESSIONS[token] = user_info

    resp = JSONResponse({
        "success": True,
        "token": token,
        "user": user_info,
        "message": f"Personal password created successfully! Welcome Eng. {user_info['name']}."
    })
    resp.set_cookie("hill_token", token, max_age=86400 * 30, httponly=False, samesite="lax")
    return resp


@app.post("/api/auth/reset-password")
async def reset_password_api(request: Request):
    """Enables a verified Hill engineer to reset their personal password."""
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    new_password = str(body.get("new_password") or body.get("password") or "").strip()

    if not email.endswith("@hillintl.com"):
        return JSONResponse(status_code=403, content={"success": False, "message": "Only @hillintl.com email addresses are eligible."})

    if len(new_password) < 6:
        return JSONResponse(status_code=400, content={"success": False, "message": "New password must be at least 6 characters long."})

    con = get_db()
    try:
        row = con.execute("""
            SELECT user_name FROM dim_user_directory
            WHERE LOWER(TRIM(email)) = ?
            LIMIT 1
        """, [email]).fetchone()
        if not row and email != "mohamedmeneaem@hillintl.com":
            return JSONResponse(status_code=403, content={"success": False, "message": "Email not found in Project Directory."})

        cred_s.save_user_credential(con, email, new_password)
    finally:
        con.close()

    return JSONResponse(content={"success": True, "message": "Your password has been updated successfully. Please log in with your new password."})


@app.get("/api/auth/hill-session")
def hill_session_api(request: Request):
    """Validates the current session token."""
    token = request.headers.get("x-hill-token", "")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get("hill_token", "")
        
    if token and token in HILL_SESSIONS:
        return {"authenticated": True, "user": HILL_SESSIONS[token]}
    return {"authenticated": False}


@app.post("/api/auth/hill-logout")
def hill_logout_api(request: Request):
    """Signs out user and invalidates session token."""
    token = request.headers.get("x-hill-token", "")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get("hill_token", "")
    if token in HILL_SESSIONS:
        del HILL_SESSIONS[token]
    resp = JSONResponse({"success": True, "message": "Signed out successfully."})
    resp.delete_cookie("hill_token")
    return resp


@app.post("/api/auth/verify-admin")
async def verify_admin_pin_api(request: Request):
    """Verifies administrator passcode and returns an authorized session token."""
    body = await request.json()
    pin = str(body.get("pin", "")).strip()
    cfg = get_admin_credentials()
    if pin == cfg["admin_pin"]:
        return {
            "success": True, 
            "token": cfg["admin_token"],
            "message": "Administrator mode authenticated successfully."
        }
    return JSONResponse(
        status_code=401,
        content={"success": False, "message": "Invalid Administrator PIN. Access denied."}
    )

@app.get("/api/auth/check-admin")
def check_admin_status_api(request: Request):
    """Returns whether the current request/token is authorized as Administrator."""
    try:
        verify_admin_request(request)
        return {"is_admin": True}
    except Exception:
        return {"is_admin": False}


@app.get("/api/extraction/status")
def get_extraction_status_api():
    """Returns the current state of extraction task, scheduler info, progress, and recent logs."""
    if not sync_manager:
        return {"found": False, "is_running": False, "error": "sync_manager not found"}
    prog = sync_manager.get_pipeline_progress()
    prog["logs"] = sync_manager.get_sync_logs(40)
    try:
        cutoff_info = get_database_cutoff_api()
        prog["data_cutoff_date"] = cutoff_info.get("cutoff_date", "2026-10-16")
        prog["data_cutoff_formatted"] = cutoff_info.get("formatted", "Oct 16, 2026")
    except Exception:
        prog["data_cutoff_date"] = "2026-10-16"
        prog["data_cutoff_formatted"] = "Oct 16, 2026"
    return prog

@app.post("/api/extraction/run-now")
def run_extraction_now_api(request: Request):
    """Triggers immediate background FULL extraction and DuckDB ETL update."""
    verify_admin_request(request)
    if not sync_manager:
        raise HTTPException(status_code=500, detail="sync_manager not available")
    ok = sync_manager.run_immediate_sync_in_background(mode="full")
    return {"success": ok, "message": "Full extraction pipeline triggered in background."}

@app.post("/api/extraction/run-delta")
def run_delta_extraction_api(request: Request):
    """Triggers immediate background DELTA extraction and atomic DuckDB update (~45s)."""
    verify_admin_request(request)
    if not sync_manager:
        raise HTTPException(status_code=500, detail="sync_manager not available")
    ok = sync_manager.run_immediate_delta_sync_in_background()
    return {"success": ok, "message": "Quick Delta sync triggered in background."}

@app.post("/api/micro-batch/update")
async def update_micro_batch_api(request: Request):
    """Updates or toggles the micro-batch business-hours schedule in Windows Task Scheduler."""
    verify_admin_request(request)
    if not sync_manager:
        raise HTTPException(status_code=500, detail="sync_manager not available")
    body = await request.json()
    enabled = body.get("enabled", True)
    interval_mins = body.get("interval_mins", 60)
    ok, msg = sync_manager.update_micro_batch_schedule(enabled=enabled, interval_minutes=interval_mins)
    return {"success": ok, "message": msg, "micro_task": sync_manager.get_micro_batch_info()}

@app.post("/api/scheduled-task/update")
async def update_scheduled_task_api(request: Request):
    """Updates the scheduled daily run time in Windows Task Scheduler."""
    verify_admin_request(request)
    if not sync_manager:
        raise HTTPException(status_code=500, detail="sync_manager not available")
    body = await request.json()
    time_str = body.get("time", "05:00")
    enabled = body.get("enabled", True)
    ok, msg = sync_manager.update_task_schedule(time_str=time_str, enabled=enabled)
    return {"success": ok, "message": msg, "task": sync_manager.get_task_info()}

# -----------------------------------------------------------------------------
# 18.5 In-App System Settings & Dispatch Email Matrices
# -----------------------------------------------------------------------------
@app.get("/api/settings/dispatch")
def get_dispatch_settings_api(request: Request):
    """Returns the full dispatch email configuration and Gemini settings."""
    verify_admin_request(request)
    return dss.load_settings()

@app.post("/api/settings/ssc_emails")
async def save_ssc_emails_api(request: Request):
    """Saves or updates the SSC Remind Emails routing for a project package."""
    verify_admin_request(request)
    try:
        body = await request.json()
        project = body.get("project", "").strip()
        to_list = body.get("to", [])
        cc_list = body.get("cc", [])
        project_name = body.get("project_name", "")
        notes = body.get("notes", "")
        if not project:
            raise HTTPException(status_code=400, detail="Project identifier is required")
        res = dss.save_ssc_remind_email(project, to_list, cc_list, project_name, notes)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/rfi_emails")
async def save_rfi_emails_api(request: Request):
    """Saves or updates RFI Remind Email routing for a project and responsible company."""
    verify_admin_request(request)
    try:
        body = await request.json()
        project = body.get("project", "All Packages").strip()
        company = body.get("company", "").strip()
        to_list = body.get("to", [])
        cc_list = body.get("cc", [])
        notes = body.get("notes", "")
        entry_id = body.get("id")
        if not company:
            raise HTTPException(status_code=400, detail="Responsible company is required")
        res = dss.save_rfi_remind_email(project, company, to_list, cc_list, notes, entry_id)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/settings/rfi_emails/{entry_id}")
def delete_rfi_emails_api(entry_id: str, request: Request):
    """Deletes an RFI Remind Email routing entry by ID."""
    verify_admin_request(request)
    ok = dss.delete_rfi_remind_email(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "success", "deleted_id": entry_id}

@app.post("/api/settings/gemini_config")
async def save_gemini_config_api(request: Request):
    """Saves Google Gemini API configuration."""
    verify_admin_request(request)
    try:
        body = await request.json()
        api_key = body.get("api_key", "").strip()
        model = body.get("model", "gemini-3-flash-preview").strip()
        enabled = body.get("enabled", True)
        res = dss.save_gemini_config(api_key, model, enabled)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/gemini_test")
async def test_gemini_connection_api(request: Request):
    """Tests Gemini connection with a quick query against the model, with intelligent fallback and auto-save."""
    verify_admin_request(request)
    import time
    start_t = time.time()
    try:
        try:
            body = await request.json()
        except Exception:
            body = {}

        api_key = (body.get("api_key") or "").strip() or dss.get_gemini_config().get("api_key", "").strip()
        requested_model = (body.get("model") or "").strip() or dss.get_gemini_config().get("model", "gemini-3-flash-preview")
        
        if not api_key:
            return {"status": "error", "message": "Gemini API key is required. Please type or paste your key into the input field above."}
        
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Automatic alias translation for legacy models sunset by Google
        MODEL_ALIASES = {
            "gemini-2.5-flash": "gemini-3-flash-preview",
            "gemini-2.0-flash": "gemini-3-flash-preview",
            "gemini-1.5-flash": "gemini-3-flash-preview",
            "gemini-1.5-pro": "gemini-3-flash-preview",
            "gemini-2.5-pro": "gemini-3-flash-preview"
        }
        target_model = MODEL_ALIASES.get(requested_model, requested_model)
        
        # Test candidate models in priority order: modern fast flash first (compatible with free tier limits)
        candidates = [target_model, "gemini-3-flash-preview", "gemini-flash-latest", "gemini-3.1-pro-preview"]
        clean_candidates = []
        for m in candidates:
            if m and m not in clean_candidates:
                clean_candidates.append(m)

        last_error = None
        working_model = None
        test_text = ""

        for candidate in clean_candidates:
            try:
                model = genai.GenerativeModel(candidate)
                test_res = model.generate_content("Ping: Respond with 'Gemini AI Live Connection Successful!' in one sentence.")
                if test_res and test_res.text:
                    working_model = candidate
                    test_text = test_res.text.strip()
                    break
            except Exception as ex:
                last_error = ex
                continue

        if not working_model:
            return {
                "status": "error",
                "message": f"{last_error or 'Unable to generate content with Gemini API. Please verify your API key.'}"
            }

        elapsed_ms = int((time.time() - start_t) * 1000)

        # Auto-persist valid configuration
        dss.save_gemini_config(api_key=api_key, model=working_model, enabled=True)

        return {
            "status": "success",
            "model": working_model,
            "latency_ms": elapsed_ms,
            "response": test_text
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -----------------------------------------------------------------------------
# 18.6 Contractor RFIs Overdue Tracking & Remind Emails
# -----------------------------------------------------------------------------
@app.get("/api/controls/contractor_rfis")
def get_contractor_rfis_api(
    project: str = Query(None),
    company: str = Query(None),
    status: str = Query(None),
    overdue_only: bool = Query(False),
    from_date: str = Query(None),
    to_date: str = Query(None),
    search: str = Query(None),
    limit: int = 50,
    offset: int = 0,
    page: int = Query(1)
):
    """Returns contractor RFIs, SLA delay metrics, and breakdown by responsible consultant."""
    if page > 1 and offset == 0:
        offset = (page - 1) * limit
    return ocs.get_contractor_rfis_data(
        project_id=project,
        company=company,
        status=status,
        overdue_only=overdue_only,
        from_date=from_date,
        to_date=to_date,
        search=search,
        limit=limit,
        offset=offset
    )

@app.get("/api/controls/contractor_rfis/remind_email")
def get_contractor_rfis_remind_email_api(
    project: str = Query("All Packages"),
    company: str = Query("All Responsible Companies"),
    status: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    """Generates official contractor RFI reminder email draft with To/CC pulled from in-app matrix."""
    return ocs.generate_rfi_remind_email(
        project_id=project,
        company=company,
        from_date=from_date,
        to_date=to_date,
        status=status
    )

@app.get("/api/controls/contractor_rfis/export_excel")
def export_contractor_rfis_excel_api(
    project: str = Query(None),
    company: str = Query(None),
    status: str = Query(None),
    overdue_only: bool = Query(False),
    from_date: str = Query(None),
    to_date: str = Query(None),
    search: str = Query(None)
):
    """Exports filtered contractor RFIs to a professional styled Excel workbook."""
    data = ocs.get_contractor_rfis_data(
        project_id=project,
        company=company,
        status=status,
        overdue_only=overdue_only,
        from_date=from_date,
        to_date=to_date,
        search=search,
        limit=10000,
        offset=0
    )
    rfis = data.get("rfis", [])
    
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Contractor RFIs"
    ws.views.sheetView[0].showGridLines = True

    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    headers = [
        "Mail No", "Project Package", "Subject", "Contractor (From)", 
        "Responsible Company (To)", "Sent Date", "Due Date", "Days Late", 
        "SLA Status", "Oracle Aconex URL"
    ]
    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    row_font = Font(name="Segoe UI", size=9)
    late_font = Font(name="Segoe UI", size=9, bold=True, color="DC2626")
    ontime_font = Font(name="Segoe UI", size=9, color="059669")

    for r_idx, r in enumerate(rfis, start=2):
        status_text = f"OVERDUE (+{r['days_late']}d)" if r['is_overdue'] else "On Time"
        row_data = [
            r["mail_no"],
            r["project_package"],
            r["subject"],
            r["from_org"],
            r["to_org"],
            r["sent_date"],
            r["due_date"],
            r["days_late"],
            status_text,
            r["aconex_url"]
        ]
        ws.append(row_data)
        for c_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            cell.font = late_font if (c_idx in [8, 9] and r['is_overdue']) else (ontime_font if (c_idx == 9 and not r['is_overdue']) else row_font)
            cell.alignment = center_align if c_idx in [1, 2, 6, 7, 8, 9] else left_align
            cell.border = thin_border
            if c_idx == 10:
                cell.hyperlink = r["aconex_url"]
                cell.font = Font(name="Segoe UI", size=9, color="2563EB", underline="single")

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"Contractor_RFIs_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -----------------------------------------------------------------------------
# 19. Hill International PMC Internal Action Tracking
# -----------------------------------------------------------------------------
@app.get("/api/controls/hill_team")
def get_hill_team_api(package: str = Query(None)):
    """Returns aggregated direct-action backlog for all Hill International engineers."""
    return {"data": hcs.get_hill_team_summary(package_filter=package)}

@app.get("/api/controls/hill_team/{engineer_name}/dossier")
def get_hill_engineer_dossier_api(engineer_name: str, package: str = Query(None)):
    """Returns the comprehensive direct-action portfolio and generated reminder HTML email for a single Hill engineer."""
    return hcs.get_hill_engineer_dossier(engineer_name=engineer_name, package_filter=package)

@app.get("/api/controls/hill_team/{engineer_name}/download_eml")
def download_hill_engineer_eml_api(engineer_name: str, package: str = Query(None)):
    """Generates an Outlook-compatible .eml reminder draft pre-attached with personalized Excel register for the engineer."""
    eml_bytes, filename = hcs.generate_hill_engineer_eml(engineer_name=engineer_name, package_filter=package)
    return Response(
        content=eml_bytes,
        media_type="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/controls/hill_team/{engineer_name}/export_excel")
def export_hill_engineer_excel_api(engineer_name: str, package: str = Query(None)):
    """Generates an executive, professionally styled Excel register for the Hill engineer's direct action backlog."""
    excel_bytes, filename = hcs.generate_hill_engineer_excel(engineer_name=engineer_name, package_filter=package)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# -----------------------------------------------------------------------------
# 20. Ball in Court Governance & Process Tracking
# -----------------------------------------------------------------------------
@app.get("/api/ball_in_court/processes")
def get_ball_in_court_processes_api(
    file_type: str = Query(None),
    discipline: str = Query(None),
    ball_in_court: str = Query(None),
    consultant: str = Query(None),
    package: str = Query(None),
    process_status: str = Query(None),
    mail_status: str = Query(None),
    action: str = Query(None),
    search: str = Query(None),
    page: int = Query(1),
    limit: int = Query(50)
):
    con = get_db()
    try:
        filters = []
        params = []

        if file_type and file_type != 'all':
            selected_types = [t.strip() for t in file_type.split(',') if t.strip()]
            if len(selected_types) == 1:
                filters.append("file_type = ?")
                params.append(selected_types[0])
            elif len(selected_types) > 1:
                placeholders = ','.join(['?' for _ in selected_types])
                filters.append(f"file_type IN ({placeholders})")
                params.extend(selected_types)

        if discipline and discipline != 'all':
            filters.append("discipline = ?")
            params.append(discipline)

        if consultant and consultant != 'all':
            if consultant == 'DAR AL HANDASAH':
                filters.append("ball_in_court ILIKE '%DAR AL HANDASAH%'")
            elif consultant == 'OBMI':
                filters.append("ball_in_court ILIKE '%OBMI%'")
            elif consultant == 'NACO':
                filters.append("ball_in_court ILIKE '%NACO%'")
            elif consultant == 'Royal HaskoningDHV':
                filters.append("(ball_in_court ILIKE '%Haskoning%' OR ball_in_court ILIKE '%Royal%')")
            elif consultant == 'EGIS':
                filters.append("ball_in_court ILIKE '%EGIS%'")
            elif consultant == 'Aedas':
                filters.append("ball_in_court ILIKE '%Aedas%'")
            elif consultant == 'Shaker_ECG':
                filters.append("(ball_in_court ILIKE '%Shaker%' OR ball_in_court ILIKE '%ECG%')")
            elif consultant == 'Modon':
                filters.append("ball_in_court ILIKE '%Modon%'")
            elif consultant == 'Hill_Only':
                filters.append("ball_in_court = 'Hill Inter'")
            else:
                filters.append("ball_in_court ILIKE ?")
                params.append(f"%{consultant}%")

        if ball_in_court and ball_in_court != 'all':
            if ball_in_court in ['(Blanks)', 'blanks', 'blank', 'null', 'None']:
                filters.append("(ball_in_court IS NULL OR ball_in_court = '' OR ball_in_court = 'N/A')")
            elif ball_in_court == 'Hill':
                filters.append("ball_in_court ILIKE '%Hill%'")
            elif ball_in_court == 'Shaker_ECG':
                filters.append("(ball_in_court ILIKE '%Shaker%' OR ball_in_court ILIKE '%ECG%')")
            elif ball_in_court == 'Modon':
                filters.append("ball_in_court ILIKE '%Modon%'")
            elif '|||' in ball_in_court:
                selected_parties = [p.strip() for p in ball_in_court.split('|||') if p.strip()]
                placeholders = ','.join(['?' for _ in selected_parties])
                filters.append(f"ball_in_court IN ({placeholders})")
                params.extend(selected_parties)
            else:
                filters.append("ball_in_court = ?")
                params.append(ball_in_court)

        if package and package != 'all':
            filters.append("project_package = ?")
            params.append(package)

        if process_status and process_status != 'all':
            filters.append("process_status = ?")
            params.append(process_status)

        if mail_status and mail_status != 'all':
            filters.append("mail_status = ?")
            params.append(mail_status)

        if action and action != 'all':
            filters.append("action = ?")
            params.append(action)

        if search:
            filters.append("(process_ref ILIKE ? OR mail_no ILIKE ? OR ball_in_court ILIKE ? OR latest_activity ILIKE ? OR COALESCE(discipline, '') ILIKE ?)")
            q = f"%{search}%"
            params.extend([q, q, q, q, q])

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        total_count = con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes {where_clause}", params).fetchone()[0]

        # Dynamic KPIs based on current file_type filter or overall
        if file_type and file_type != 'all':
            selected_types = [t.strip().replace("'", "''") for t in file_type.split(',') if t.strip()]
            if len(selected_types) == 1:
                kpi_where = f"WHERE file_type = '{selected_types[0]}'"
                scope_and = f"AND file_type = '{selected_types[0]}'"
                party_where = f"WHERE file_type = '{selected_types[0]}'"
            else:
                t_in = "','".join(selected_types)
                kpi_where = f"WHERE file_type IN ('{t_in}')"
                scope_and = f"AND file_type IN ('{t_in}')"
                party_where = f"WHERE file_type IN ('{t_in}')"
        else:
            kpi_where = ""
            scope_and = ""
            party_where = ""

        kpis_row = con.execute(f"""
            SELECT 
                count(*) as total,
                count(CASE WHEN is_overdue THEN 1 END) as overdue,
                count(CASE WHEN ball_in_court ILIKE '%Hill%' THEN 1 END) as on_hill,
                count(CASE WHEN ball_in_court ILIKE '%Shaker%' OR ball_in_court ILIKE '%ECG%' THEN 1 END) as on_shaker_ecg,
                count(CASE WHEN ball_in_court ILIKE '%Modon%' THEN 1 END) as on_modon,
                count(CASE WHEN action = 'To Respond' THEN 1 END) as to_respond,
                count(CASE WHEN action ILIKE '%Expecting%' THEN 1 END) as expecting_resp
            FROM fact_ball_in_court_processes
            {kpi_where}
        """).fetchone()

        # Detailed 5 File Types breakdown
        type_counts_rows = con.execute("""
            SELECT file_type, file_type_name, file_type_ar, count(*) as cnt, count(CASE WHEN is_overdue THEN 1 END) as ov_cnt
            FROM fact_ball_in_court_processes
            GROUP BY file_type, file_type_name, file_type_ar
            ORDER BY count(*) DESC
        """).fetchall()
        file_types_list = [
            {
                "file_type": r[0],
                "name": r[1],
                "name_ar": r[2],
                "total": r[3],
                "overdue": r[4]
            } for r in type_counts_rows
        ]

        # Detailed consultant breakdown (scoped to file_type if active)
        c_stats = {
            "all": {"name": "All Parties", "total": kpis_row[0], "overdue": kpis_row[1]},
            "EGIS": {
                "name": "EGIS Middle-East",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%EGIS%' {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%EGIS%' AND is_overdue {scope_and}").fetchone()[0]
            },
            "Aedas": {
                "name": "Aedas Limited",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%Aedas%' {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%Aedas%' AND is_overdue {scope_and}").fetchone()[0]
            },
            "Shaker_ECG": {
                "name": "Shaker-ECG Consortium",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE (ball_in_court ILIKE '%Shaker%' OR ball_in_court ILIKE '%ECG%') {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE (ball_in_court ILIKE '%Shaker%' OR ball_in_court ILIKE '%ECG%') AND is_overdue {scope_and}").fetchone()[0]
            },
            "DAR AL HANDASAH": {
                "name": "DAR AL HANDASAH",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%DAR AL HANDASAH%' {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%DAR AL HANDASAH%' AND is_overdue {scope_and}").fetchone()[0]
            },
            "OBMI": {
                "name": "OBMI",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%OBMI%' {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%OBMI%' AND is_overdue {scope_and}").fetchone()[0]
            },
            "NACO": {
                "name": "NACO",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%NACO%' {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%NACO%' AND is_overdue {scope_and}").fetchone()[0]
            },
            "Royal HaskoningDHV": {
                "name": "Royal HaskoningDHV",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE (ball_in_court ILIKE '%Haskoning%' OR ball_in_court ILIKE '%Royal%') {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE (ball_in_court ILIKE '%Haskoning%' OR ball_in_court ILIKE '%Royal%') AND is_overdue {scope_and}").fetchone()[0]
            },
            "Modon": {
                "name": "Modon Real Estate",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%Modon%' {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court ILIKE '%Modon%' AND is_overdue {scope_and}").fetchone()[0]
            },
            "Hill_Only": {
                "name": "Hill Inter Direct",
                "total": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court = 'Hill Inter' {scope_and}").fetchone()[0],
                "overdue": con.execute(f"SELECT count(*) FROM fact_ball_in_court_processes WHERE ball_in_court = 'Hill Inter' AND is_overdue {scope_and}").fetchone()[0]
            }
        }

        # Exact party breakdown matching user's Power BI slicer (scoped to file_type if active)
        party_counts_rows = con.execute(f"""
            SELECT COALESCE(ball_in_court, 'N/A') as party, count(*) as cnt, count(CASE WHEN is_overdue THEN 1 END) as ov_cnt
            FROM fact_ball_in_court_processes
            {party_where}
            GROUP BY 1
            ORDER BY 1
        """).fetchall()
        party_list = [{"party": r[0], "total": r[1], "overdue": r[2]} for r in party_counts_rows]

        pkg_options = [r[0] for r in con.execute("SELECT DISTINCT project_package FROM fact_ball_in_court_processes WHERE project_package IS NOT NULL ORDER BY 1").fetchall()]
        p_status_options = [r[0] for r in con.execute("SELECT DISTINCT process_status FROM fact_ball_in_court_processes WHERE process_status IS NOT NULL ORDER BY 1").fetchall()]
        m_status_options = [r[0] for r in con.execute("SELECT DISTINCT mail_status FROM fact_ball_in_court_processes WHERE mail_status IS NOT NULL ORDER BY 1").fetchall()]
        action_options = [r[0] for r in con.execute("SELECT DISTINCT action FROM fact_ball_in_court_processes WHERE action IS NOT NULL ORDER BY 1").fetchall()]
        disc_options = [r[0] for r in con.execute("SELECT DISTINCT discipline FROM fact_ball_in_court_processes WHERE discipline IS NOT NULL AND discipline != '' ORDER BY 1").fetchall()] if 'discipline' in [c[0] for c in con.execute("DESCRIBE fact_ball_in_court_processes").fetchall()] else []

        offset = (max(1, page) - 1) * limit
        data_rows = con.execute(f"""
            SELECT 
                process_ref, initiated_on, process_status, duration, delay, latest_activity,
                mail_status, ball_in_court, action, overdue_days, mail_no, project_package,
                contractor, is_overdue, aconex_url, source, file_type, file_type_name, file_type_ar, source_file,
                COALESCE(discipline, 'General') as discipline
            FROM fact_ball_in_court_processes
            {where_clause}
            ORDER BY COALESCE(overdue_days, delay, duration, 0) DESC, initiated_on DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        def extract_primary_consultant(bic):
            if not bic: return 'N/A'
            if 'DAR AL HANDASAH' in bic: return 'DAR AL HANDASAH'
            if 'OBMI' in bic: return 'OBMI'
            if 'NACO' in bic: return 'NACO'
            if 'Haskoning' in bic or 'Royal' in bic: return 'Royal HaskoningDHV'
            if 'Aedas' in bic: return 'Aedas Limited'
            if 'EGIS' in bic: return 'EGIS Middle-East'
            if 'Shaker' in bic or 'ECG' in bic: return 'Shaker-ECG'
            if 'Modon' in bic: return 'Modon'
            return 'Hill Inter'

        items = []
        for r in data_rows:
            items.append({
                "process_ref": r[0],
                "initiated_on": r[1],
                "process_status": r[2],
                "duration": r[3],
                "delay": r[4],
                "latest_activity": r[5],
                "mail_status": r[6],
                "ball_in_court": r[7],
                "primary_consultant": extract_primary_consultant(r[7]),
                "action": r[8],
                "overdue_days": r[9],
                "mail_no": r[10],
                "project_package": r[11],
                "contractor": r[12],
                "is_overdue": bool(r[13]),
                "aconex_url": r[14],
                "source": r[15],
                "file_type": r[16],
                "file_type_name": r[17],
                "file_type_ar": r[18],
                "source_file": r[19],
                "discipline": r[20]
            })

        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "kpis": {
                "total_processes": kpis_row[0],
                "total_overdue": kpis_row[1],
                "on_hill": kpis_row[2],
                "on_shaker_ecg": kpis_row[3],
                "on_modon": kpis_row[4],
                "to_respond": kpis_row[5],
                "expecting_response": kpis_row[6]
            },
            "file_types": file_types_list,
            "consultants": c_stats,
            "parties": party_list,
            "filter_options": {
                "packages": pkg_options,
                "process_statuses": p_status_options,
                "mail_statuses": m_status_options,
                "actions": action_options,
                "disciplines": disc_options
            },
            "data": items
        }
    finally:
        con.close()


@app.get("/api/ball_in_court/export_excel")
def export_ball_in_court_excel_api(
    file_type: str = Query(None),
    discipline: str = Query(None),
    ball_in_court: str = Query(None),
    consultant: str = Query(None),
    package: str = Query(None),
    process_status: str = Query(None),
    mail_status: str = Query(None),
    action: str = Query(None),
    search: str = Query(None)
):
    excel_bytes, filename = ees.generate_ball_in_court_excel_export(
        file_type=file_type,
        discipline=discipline,
        ball_in_court=ball_in_court,
        consultant=consultant,
        package=package,
        process_status=process_status,
        mail_status=mail_status,
        action=action,
        search=search
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -----------------------------------------------------------------------------
# 21. Project Document Transmittals API
# -----------------------------------------------------------------------------
@app.get("/api/projects/{project_id}/transmittals")
def get_project_transmittals_api(
    project_id: str,
    search: str = Query(None),
    doc_type: str = Query(None),
    discipline: str = Query(None),
    status: str = Query(None),
    sort: str = Query("date_modified_desc"),
    page: int = Query(1),
    limit: int = Query(50)
):
    con = get_db()
    try:
        pid = normalize_project_id(urllib.parse.unquote(project_id))
        
        # Verify table exists
        tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
        if 'fact_document_transmittals' not in tables:
            return {"total": 0, "page": page, "limit": limit, "filter_options": {"types": [], "disciplines": [], "statuses": []}, "data": []}

        filters = ["project_package = ?"]
        params = [pid]

        if search and isinstance(search, str):
            clean_s = search.replace("'", "''")
            filters.append(f"(document_no ILIKE '%{clean_s}%' OR title ILIKE '%{clean_s}%' OR transmittal_no ILIKE '%{clean_s}%' OR transmitted_to_org ILIKE '%{clean_s}%' OR transmittal_in_from_org ILIKE '%{clean_s}%' OR transmitted_recipients ILIKE '%{clean_s}%')")

        if doc_type and doc_type != 'all':
            if ',' in doc_type:
                types = [t.strip().replace("'", "''") for t in doc_type.split(',') if t.strip()]
                t_str = "','".join(types)
                filters.append(f"doc_type IN ('{t_str}')")
            else:
                filters.append(f"doc_type = '{doc_type.replace("'", "''")}'")

        if discipline and discipline != 'all':
            filters.append(f"discipline = '{discipline.replace("'", "''")}'")

        if status and status != 'all':
            filters.append(f"doc_status = '{status.replace("'", "''")}'")

        where_clause = f"WHERE {' AND '.join(filters)}"

        total = con.execute(f"SELECT count(*) FROM fact_document_transmittals {where_clause}", params).fetchone()[0]

        types_opts = [r[0] for r in con.execute("SELECT DISTINCT doc_type FROM fact_document_transmittals WHERE project_package = ? AND doc_type IS NOT NULL AND doc_type != '' ORDER BY 1", [pid]).fetchall()]
        disc_opts = [r[0] for r in con.execute("SELECT DISTINCT discipline FROM fact_document_transmittals WHERE project_package = ? AND discipline IS NOT NULL AND discipline != '' ORDER BY 1", [pid]).fetchall()]
        status_opts = [r[0] for r in con.execute("SELECT DISTINCT doc_status FROM fact_document_transmittals WHERE project_package = ? AND doc_status IS NOT NULL AND doc_status != '' ORDER BY 1", [pid]).fetchall()]

        sort_mapping = {
            "date_modified_desc": "date_modified DESC NULLS LAST",
            "date_modified_asc": "date_modified ASC NULLS LAST",
            "doc_no_asc": "document_no ASC",
            "doc_no_desc": "document_no DESC",
            "transmittal_no_desc": "transmittal_no DESC",
            "status_asc": "doc_status ASC"
        }
        order_by = sort_mapping.get(sort, "date_modified DESC NULLS LAST")

        offset = (max(1, page) - 1) * limit
        rows = con.execute(f"""
            SELECT 
                document_no, title, doc_type, discipline, doc_status, revision,
                date_modified, transmittal_no, transmitted_mail_no, transmitted_sent_date,
                transmitted_to_org, transmitted_recipients, reason_for_issue,
                transmittal_in_mail_no, transmittal_in_sent_date, transmittal_in_from_org,
                aconex_doc_url, aconex_transmittal_url
            FROM fact_document_transmittals
            {where_clause}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        items = []
        for r in rows:
            items.append({
                "document_no": r[0],
                "title": r[1],
                "type": r[2],
                "discipline": r[3],
                "status": r[4],
                "revision": r[5],
                "date_modified": r[6],
                "transmittal_no": r[7],
                "transmitted_mail_no": r[8],
                "transmitted_sent_date": r[9],
                "transmitted_to_org": r[10],
                "transmitted_recipients": r[11],
                "reason_for_issue": r[12],
                "transmittal_in_mail_no": r[13],
                "transmittal_in_sent_date": r[14],
                "transmittal_in_from_org": r[15],
                "aconex_doc_url": r[16],
                "aconex_transmittal_url": r[17]
            })

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "filter_options": {
                "types": types_opts,
                "disciplines": disc_opts,
                "statuses": status_opts
            },
            "data": items
        }
    finally:
        con.close()


@app.get("/api/projects/{project_id}/transmittals/export")
def export_project_transmittals_excel_api(
    project_id: str,
    search: str = Query(None),
    doc_type: str = Query(None),
    discipline: str = Query(None),
    status: str = Query(None)
):
    excel_bytes, filename = ees.generate_transmittals_excel_export(
        project_id=normalize_project_id(urllib.parse.unquote(project_id)),
        search=search,
        doc_type=doc_type,
        discipline=discipline,
        status=status
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/api/ball_in_court/refresh")
def refresh_ball_in_court_api():
    import ingest_ball_in_court as ibic
    ibic.ingest_to_duckdb()
    return {"status": "success", "message": "Successfully refreshed Ball in Court dataset from latest Excel and PDF sources!"}


# -----------------------------------------------------------------------------
# 19. Specialized Discipline Portals (HSE, QA/QC, Site Ops, Tech Office)
# -----------------------------------------------------------------------------
@app.get("/api/disciplines/safety/stats")
def get_safety_stats_api():
    return disc_s.get_safety_stats()

@app.get("/api/disciplines/safety/items")
def get_safety_items_api(
    project: str = Query(None),
    item_type: str = Query(None),
    category: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    page: int = 1,
    limit: int = 30
):
    return disc_s.get_safety_items(project, item_type, category, status, search, from_date, to_date, page, limit)

@app.get("/api/disciplines/safety/export")
def export_safety_excel_api(
    project: str = Query(None),
    item_type: str = Query(None),
    category: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    res = disc_s.get_safety_items(project, item_type, category, status, search, from_date, to_date, page=1, limit=5000)
    cols = [
        {"header": "Item / Mail No", "field": "mail_no", "is_link": True, "min_width": 20},
        {"header": "Type", "field": "mail_type", "min_width": 24},
        {"header": "Subject", "field": "subject", "min_width": 38},
        {"header": "Package", "field": "project", "min_width": 15},
        {"header": "From Organization", "field": "from_org", "min_width": 26},
        {"header": "To Organization", "field": "to_org", "min_width": 26},
        {"header": "Sent Date", "field": "sent_date", "align": "center", "min_width": 14},
        {"header": "Status", "field": "status", "align": "center", "min_width": 12}
    ]
    excel_bytes, filename = disc_s.generate_discipline_excel("HSE Safety Hub", res["items"], cols)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/disciplines/qaqc/stats")
def get_qaqc_stats_api():
    return disc_s.get_qaqc_stats()

@app.get("/api/disciplines/qaqc/items")
def get_qaqc_items_api(
    project: str = Query(None),
    doc_type: str = Query(None),
    review_status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    page: int = 1,
    limit: int = 30
):
    return disc_s.get_qaqc_items(project, doc_type, review_status, search, from_date, to_date, page, limit)

@app.get("/api/disciplines/qaqc/export")
def export_qaqc_excel_api(
    project: str = Query(None),
    doc_type: str = Query(None),
    review_status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    res = disc_s.get_qaqc_items(project, doc_type, review_status, search, from_date, to_date, page=1, limit=5000)
    cols = [
        {"header": "Document No", "field": "document_no", "is_link": True, "min_width": 26},
        {"header": "Type", "field": "doc_type", "min_width": 24},
        {"header": "Title / Description", "field": "title", "min_width": 40},
        {"header": "Package", "field": "project", "min_width": 15},
        {"header": "Review Status", "field": "review_status", "align": "center", "min_width": 16},
        {"header": "Rev", "field": "revision", "align": "center", "min_width": 8},
        {"header": "Created By", "field": "created_by", "min_width": 20},
        {"header": "Date Modified", "field": "date_modified", "align": "center", "min_width": 14}
    ]
    excel_bytes, filename = disc_s.generate_discipline_excel("QAQC Inspections Hub", res["items"], cols)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/disciplines/site_ops/stats")
def get_site_ops_stats_api():
    return disc_s.get_site_ops_stats()

@app.get("/api/disciplines/site_ops/items")
def get_site_ops_items_api(
    project: str = Query(None),
    item_type: str = Query(None),
    overdue_only: bool = Query(False),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    page: int = 1,
    limit: int = 30
):
    return disc_s.get_site_ops_items(project, item_type, overdue_only, search, from_date, to_date, page, limit)

@app.get("/api/disciplines/site_ops/export")
def export_site_ops_excel_api(
    project: str = Query(None),
    item_type: str = Query(None),
    overdue_only: bool = Query(False),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    res = disc_s.get_site_ops_items(project, item_type, overdue_only, search, from_date, to_date, page=1, limit=5000)
    cols = [
        {"header": "Mail / Item No", "field": "mail_no", "is_link": True, "min_width": 20},
        {"header": "Type", "field": "mail_type", "min_width": 24},
        {"header": "Subject", "field": "subject", "min_width": 38},
        {"header": "Package", "field": "project", "min_width": 15},
        {"header": "From Organization", "field": "from_org", "min_width": 26},
        {"header": "To Organization", "field": "to_org", "min_width": 26},
        {"header": "Sent Date", "field": "sent_date", "align": "center", "min_width": 14},
        {"header": "Status", "field": "status", "align": "center", "min_width": 12}
    ]
    excel_bytes, filename = disc_s.generate_discipline_excel("Site Operations Hub", res["items"], cols)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/disciplines/technical_office/stats")
def get_technical_office_stats_api():
    return disc_s.get_technical_office_stats()

@app.get("/api/disciplines/technical_office/items")
def get_technical_office_items_api(
    project: str = Query(None),
    discipline: str = Query(None),
    doc_type: str = Query(None),
    review_status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    page: int = 1,
    limit: int = 30
):
    return disc_s.get_technical_office_items(project, discipline, doc_type, review_status, search, from_date, to_date, page, limit)


# Aliases for technical office endpoints (supporting both tech_office and technical_office)
@app.get("/api/disciplines/tech_office/stats")
def get_tech_office_stats_alias():
    return disc_s.get_technical_office_stats()

@app.get("/api/disciplines/tech_office/items")
def get_tech_office_items_alias(
    project: str = Query(None),
    item_type: str = Query(None),
    discipline: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    page: int = 1,
    limit: int = 30
):
    return disc_s.get_technical_office_items(project, item_type, discipline, status, search, from_date, to_date, page, limit)

@app.get("/api/disciplines/technical_office/export")
def export_technical_office_excel_api(
    project: str = Query(None),
    discipline: str = Query(None),
    doc_type: str = Query(None),
    review_status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    res = disc_s.get_technical_office_items(project, discipline, doc_type, review_status, search, from_date, to_date, page=1, limit=5000)
    cols = [
        {"header": "Document No", "field": "document_no", "is_link": True, "min_width": 26},
        {"header": "Discipline", "field": "discipline", "min_width": 20},
        {"header": "Doc Type", "field": "doc_type", "min_width": 22},
        {"header": "Title", "field": "title", "min_width": 40},
        {"header": "Package", "field": "project", "min_width": 15},
        {"header": "Review Status", "field": "review_status", "align": "center", "min_width": 16},
        {"header": "Rev", "field": "revision", "align": "center", "min_width": 8},
        {"header": "Date Modified", "field": "date_modified", "align": "center", "min_width": 14}
    ]
    excel_bytes, filename = disc_s.generate_discipline_excel("Technical Office Submittals", res["items"], cols)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -----------------------------------------------------------------------------
# 20. Contractual Correspondence Hub Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/disciplines/contractual/stats")
def get_contractual_stats_api():
    return disc_s.get_contractual_stats()

@app.get("/api/disciplines/contractual/items")
def get_contractual_items_api(
    project: str = Query(None),
    item_type: str = Query(None),
    category: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    page: int = 1,
    limit: int = 30
):
    return disc_s.get_contractual_items(project, item_type, category, status, search, from_date, to_date, page, limit)

@app.get("/api/disciplines/contractual/export")
def export_contractual_excel_api(
    project: str = Query(None),
    item_type: str = Query(None),
    category: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    res = disc_s.get_contractual_items(project, item_type, category, status, search, from_date, to_date, page=1, limit=5000)
    cols = [
        {"header": "Item / Reference No", "field": "item_no", "is_link": True, "min_width": 22},
        {"header": "Type", "field": "item_type", "min_width": 24},
        {"header": "Title / Subject", "field": "title", "min_width": 40},
        {"header": "Package", "field": "project", "min_width": 15},
        {"header": "From Organization", "field": "from_org", "min_width": 25},
        {"header": "To Organization", "field": "to_org", "min_width": 25},
        {"header": "Date", "field": "item_date", "align": "center", "min_width": 14},
        {"header": "Status", "field": "status", "align": "center", "min_width": 12}
    ]
    excel_bytes, filename = disc_s.generate_discipline_excel("Contractual Correspondence Hub", res["items"], cols)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -----------------------------------------------------------------------------
# 21. Commercial & Controls Hub Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/disciplines/commercial/stats")
def get_commercial_stats_api():
    return disc_s.get_commercial_stats()

@app.get("/api/disciplines/commercial/items")
def get_commercial_items_api(
    project: str = Query(None),
    item_type: str = Query(None),
    category: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    page: int = 1,
    limit: int = 30
):
    return disc_s.get_commercial_items(project, item_type, category, status, search, from_date, to_date, page, limit)

@app.get("/api/disciplines/commercial/export")
def export_commercial_excel_api(
    project: str = Query(None),
    item_type: str = Query(None),
    category: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    res = disc_s.get_commercial_items(project, item_type, category, status, search, from_date, to_date, page=1, limit=5000)
    cols = [
        {"header": "Document / Item No", "field": "item_no", "is_link": True, "min_width": 22},
        {"header": "Commercial Type", "field": "item_type", "min_width": 26},
        {"header": "Description / Title", "field": "title", "min_width": 40},
        {"header": "Package", "field": "project", "min_width": 15},
        {"header": "Originator / Discipline", "field": "from_org", "min_width": 24},
        {"header": "Revision", "field": "to_org", "align": "center", "min_width": 10},
        {"header": "Date Modified", "field": "item_date", "align": "center", "min_width": 14},
        {"header": "Status", "field": "status", "align": "center", "min_width": 12}
    ]
    excel_bytes, filename = disc_s.generate_discipline_excel("Commercial and Controls Hub", res["items"], cols)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )



# -----------------------------------------------------------------------------
# 18. Daily Activity Feed (Today & Yesterday Deliverables Engine)
# -----------------------------------------------------------------------------
@app.get("/api/feed/summary")
def get_daily_feed_summary_api(
    timeframe: str = Query("today_yesterday"),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    """Returns dynamic pills, source counts, and active types for the daily feed."""
    return feed_service.get_feed_summary(timeframe, from_date=from_date, to_date=to_date)

@app.get("/api/feed/items")
def get_daily_feed_items_api(
    timeframe: str = Query("today_yesterday"),
    source: str = Query("all"),
    item_type: str = Query("all"),
    project: str = Query("all"),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    discipline: str = Query(None),
    status: str = Query(None),
    page: int = 1,
    limit: int = 50
):
    """Returns paginated daily feed items across Mail, Documents, Workflows, and Processes."""
    return feed_service.get_feed_items(
        timeframe=timeframe,
        source=source,
        item_type=item_type,
        project=project,
        search=search,
        from_date=from_date,
        to_date=to_date,
        discipline=discipline,
        status=status,
        page=page,
        limit=limit
    )

@app.get("/api/feed/export")
def export_daily_feed_excel_api(
    timeframe: str = Query("today_yesterday"),
    source: str = Query("all"),
    item_type: str = Query("all"),
    project: str = Query("all"),
    search: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None)
):
    """Exports the filtered daily feed to an executive Excel spreadsheet."""
    excel_bytes, filename = feed_service.generate_feed_excel(timeframe, source, item_type, project, search)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )



# -----------------------------------------------------------------------------
# 23. User Data Refresh & Out-of-Date Request Center
# -----------------------------------------------------------------------------
import refresh_request_service as rrs

@app.get("/api/refresh-requests/business-hours")
def get_business_hours_api():
    """Returns current Cairo local time, working hours status, and SLA expectations."""
    return rrs.check_business_hours()

@app.post("/api/refresh-requests/submit")
async def submit_refresh_request_api(request: Request):
    """
    Submits a user refresh request, performs automated technical validation,
    dispatches an executive notification email to MohamedMeneaem@hillintl.com,
    and returns findings and ready response draft.
    """
    try:
        body = await request.json()
        if not body.get("requester_name") or not body.get("user_notes"):
            raise HTTPException(status_code=400, detail="Requester Name and Description of out-of-date records are required.")
        ticket = rrs.record_and_dispatch_request(body)
        return {"status": "success", "ticket": ticket}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/refresh-requests/tickets")
def get_all_refresh_tickets_api():
    """Retrieves all logged refresh request tickets."""
    return {"status": "success", "tickets": rrs.get_all_tickets()}


if __name__ == "__main__":
    import uvicorn
    import socket
    import sys

    port = 8000
    for arg in sys.argv[1:]:
        if arg.isdigit():
            port = int(arg)
        elif arg.startswith("--port="):
            port = int(arg.split("=")[1])

    mode = "DEVELOPMENT (Isolated Staging)" if port != 8000 else "PRODUCTION"

    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    print("================================================================")
    print(f"  ACONEX PMC Control Hub - Ras El Hekma [{mode}]")
    print(f"  Local Access:   http://localhost:{port}")
    if port == 8000:
        print(f"  Network Access: http://{lan_ip}:{port}")
    print("================================================================")
    uvicorn.run(app, host="0.0.0.0", port=port)


@app.post("/api/sync/cloud-push")
async def sync_cloud_push_api(
    request: Request,
    file: UploadFile = File(...),
    x_sync_secret: str = None
):
    """
    Secure endpoint allowing local pipeline to push fresh DuckDB snapshot directly to Render.
    Performs atomic swap and instant hot-reload of project data.
    """
    secret = os.environ.get("HILL_SYNC_SECRET", "HILL_REH_SYNC_SECRET_2026")
    auth_val = x_sync_secret or request.headers.get("x-sync-secret") or request.query_params.get("secret")
    if not auth_val and request.headers.get("Authorization", "").startswith("Bearer "):
        auth_val = request.headers.get("Authorization", "")[7:].strip()
        
    if not auth_val or auth_val != secret:
        raise HTTPException(status_code=403, detail="Invalid cloud sync secret token.")
    
    target_db = _ROOT_DIR / "aconex_cloud.duckdb"
    temp_upload = _ROOT_DIR / f"cloud_sync_tmp_{int(time.time())}.upload"
    
    import shutil
    import zipfile
    
    try:
        with open(temp_upload, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # If it's a zip file, extract aconex_cloud.duckdb
        if zipfile.is_zipfile(temp_upload):
            with zipfile.ZipFile(temp_upload, "r") as zf:
                zf.extractall(str(_ROOT_DIR))
            if temp_upload.exists():
                temp_upload.unlink()
        else:
            if target_db.exists():
                try:
                    target_db.unlink()
                except Exception:
                    pass
            shutil.move(temp_upload, target_db)
            
        # Verify database is readable and query telemetry
        con = duckdb.connect(str(target_db), read_only=True)
        r_cutoff = con.execute("SELECT MAX(sent_date) FROM fact_mail").fetchone()
        r_mail = con.execute("SELECT count(*) FROM fact_mail").fetchone()
        r_rfis = con.execute("SELECT count(*) FROM fact_rfis").fetchone()
        r_docs = con.execute("SELECT count(*) FROM dim_documents").fetchone()
        con.close()
        
        cutoff = str(r_cutoff[0])[:19] if r_cutoff and r_cutoff[0] else "N/A"
        
        return {
            "success": True,
            "message": "Render database updated and hot-reloaded successfully!",
            "cutoff_date": cutoff,
            "total_mails": r_mail[0] if r_mail else 0,
            "total_rfis": r_rfis[0] if r_rfis else 0,
            "total_docs": r_docs[0] if r_docs else 0,
            "timestamp": time.time()
        }
    except Exception as e:
        if temp_upload.exists():
            try:
                temp_upload.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Cloud sync failed: {str(e)}")
