import urllib.parse
import io
import os
import duckdb
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from pathlib import Path as _Path
_SRV_ROOT = _Path(__file__).resolve().parent.parent.parent
_SRV_CLOUD_DB = _SRV_ROOT / "aconex_cloud.duckdb"
_SRV_LOCAL_DB = _SRV_ROOT / "aconex.duckdb"

if _SRV_LOCAL_DB.exists():
    DB_PATH = str(_SRV_LOCAL_DB).replace("\\", "/")
elif _SRV_CLOUD_DB.exists():
    DB_PATH = str(_SRV_CLOUD_DB).replace("\\", "/")
else:
    DB_PATH = str(_SRV_LOCAL_DB).replace("\\", "/")

def _to_authoritative_aconex_doc_url(raw_doc_no):
    clean = str(raw_doc_no or "").strip().strip("'").strip('"').strip()
    q = urllib.parse.quote(f'documentNumber:"{clean}"')
    return f"https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=DOC-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery={q}"

def _to_authoritative_aconex_mail_url(raw_mail_no):
    clean = str(raw_mail_no or "").strip().strip("'").strip('"').strip()
    q = urllib.parse.quote(f'mailNumber:"{clean}"')
    return f"https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery={q}"

def get_db():
    return duckdb.connect(DB_PATH, read_only=True)

# -----------------------------------------------------------------------------
# 1. HSE & SAFETY HUB SERVICE (Unified: Observations, Remedial, Closures, Near Misses, Incidents, MOMs)
# -----------------------------------------------------------------------------
def get_safety_stats() -> dict:
    con = get_db()
    try:
        row = con.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE mail_type = 'HSE Observation') as obs,
                COUNT(*) FILTER (WHERE mail_type = 'Observation Remedial Actions') as rem,
                COUNT(*) FILTER (WHERE mail_type = 'Accepted Observation Closure') as closed,
                COUNT(*) FILTER (WHERE mail_type LIKE '%Health and Safety Non-Conformance Report%' OR mail_type LIKE '%Environmental Non Conformance Report%') as ncrs,
                COUNT(*) FILTER (WHERE lower(mail_type) LIKE '%near miss%') as near_misses,
                COUNT(*) FILTER (WHERE lower(mail_type) LIKE '%incident%' OR lower(mail_type) LIKE '%accident%' OR lower(mail_type) LIKE '%stop work%') as incidents,
                COUNT(*) FILTER (WHERE lower(mail_type) LIKE '%meeting%') as mom_mails
            FROM fact_mail
        """).fetchone()

        mom_docs = con.execute("""
            SELECT COUNT(*) 
            FROM dim_documents 
            WHERE lower(doc_type) LIKE '%meeting%'
        """).fetchone()[0]

        total_moms = (row[6] or 0) + (mom_docs or 0)
        total_near_miss_incidents = (row[4] or 0) + (row[5] or 0)

        return {
            "total_observations": row[0] or 0,
            "remedial_actions": row[1] or 0,
            "closed_observations": row[2] or 0,
            "hse_ncrs": row[3] or 0,
            "near_misses": row[4] or 0,
            "incidents": row[5] or 0,
            "total_near_miss_incidents": total_near_miss_incidents,
            "meeting_minutes": total_moms,
            "mom_docs": mom_docs,
            "mom_mails": row[6] or 0
        }
    finally:
        con.close()

def get_safety_items(
    project: str = None,
    item_type: str = None,
    category: str = None,
    status: str = None,
    search: str = None,
    from_date: str = None,
    to_date: str = None,
    page: int = 1,
    limit: int = 30
) -> dict:
    con = get_db()
    try:
        where_clauses = ["1=1"]
        params = []

        if category == "near_miss":
            where_clauses.append("(lower(mail_type) LIKE '%near miss%' OR lower(mail_type) LIKE '%incident%' OR lower(mail_type) LIKE '%accident%' OR lower(mail_type) LIKE '%stop work%')")
        elif category == "mom":
            where_clauses.append("(lower(mail_type) LIKE '%meeting%')")
        elif category == "observations":
            where_clauses.append("(lower(mail_type) LIKE '%observation%')")
        elif category == "ncrs":
            where_clauses.append("(lower(mail_type) LIKE '%non-conformance%' OR lower(mail_type) LIKE '%non conformance%')")

        if project and project != "all":
            where_clauses.append("project_package = ?")
            params.append(project)
        if item_type and item_type != "all":
            where_clauses.append("mail_type = ?")
            params.append(item_type)
        if status and status != "all":
            if status.lower() == "overdue":
                where_clauses.append("is_overdue = true")
            else:
                where_clauses.append("status = ?")
                params.append(status)
        if search:
            where_clauses.append("(lower(item_no) LIKE ? OR lower(title) LIKE ? OR lower(org_from) LIKE ? OR lower(org_to) LIKE ?)")
            q = f"%{search.strip().lower()}%"
            params.extend([q, q, q, q])
        if from_date:
            where_clauses.append("item_date >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("item_date <= ?")
            params.append(to_date)

        where_sql = " AND ".join(where_clauses)

        base_cte = """
            WITH unified_safety AS (
                SELECT 
                    mail_no AS item_no,
                    mail_type,
                    subject AS title,
                    from_organization AS org_from,
                    to_organization AS org_to,
                    sent_date AS item_date,
                    status,
                    is_overdue,
                    project_package,
                    aconex_url,
                    'Mail' AS source_type
                FROM fact_mail
                WHERE lower(mail_type) LIKE '%hse%' 
                   OR lower(mail_type) LIKE '%safety%' 
                   OR lower(mail_type) LIKE '%observation%'
                   OR lower(mail_type) LIKE '%near miss%'
                   OR lower(mail_type) LIKE '%incident%'
                   OR lower(mail_type) LIKE '%accident%'
                   OR lower(mail_type) LIKE '%stop work%'
                   OR lower(mail_type) LIKE '%meeting%'
                UNION ALL
                SELECT 
                    document_no AS item_no,
                    doc_type AS mail_type,
                    title,
                    discipline_name AS org_from,
                    revision AS org_to,
                    date_modified AS item_date,
                    'Registered' AS status,
                    false AS is_overdue,
                    project_package,
                    aconex_url,
                    'Document' AS source_type
                FROM dim_documents
                WHERE lower(doc_type) LIKE '%meeting%'
            )
        """

        count_sql = f"{base_cte} SELECT COUNT(*) FROM unified_safety WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            {base_cte}
            SELECT 
                item_no, mail_type, title, org_from, org_to, 
                item_date, status, is_overdue, project_package, aconex_url, source_type
            FROM unified_safety
            WHERE {where_sql}
            ORDER BY CASE WHEN TRY_CAST(item_date AS DATE) <= CURRENT_DATE + INTERVAL 30 DAY THEN item_date ELSE NULL END DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            date_str = r[5].strftime("%Y-%m-%d") if isinstance(r[5], datetime) else (str(r[5])[:10] if r[5] else "-")
            url = r[9] or ""
            if not url.startswith("http"):
                if r[10] == "Document":
                    url = _to_authoritative_aconex_doc_url(r[0])
                else:
                    url = _to_authoritative_aconex_mail_url(r[0])
            items.append({
                "mail_no": r[0],
                "mail_type": r[1],
                "subject": r[2],
                "from_org": r[3] or "-",
                "to_org": r[4] or "-",
                "sent_date": date_str,
                "status": r[6] or "Active",
                "is_overdue": bool(r[7]),
                "project": r[8] or "General",
                "aconex_url": url,
                "source_type": r[10]
            })

        # Distinct projects and types for dropdown filters
        projects = [p[0] for p in con.execute(f"{base_cte} SELECT DISTINCT project_package FROM unified_safety WHERE project_package IS NOT NULL ORDER BY 1").fetchall()]
        types = [t[0] for t in con.execute(f"{base_cte} SELECT DISTINCT mail_type FROM unified_safety ORDER BY 1").fetchall()]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "projects": projects,
            "types": types,
            "items": items
        }
    finally:
        con.close()

# 2. QA/QC & INSPECTIONS HUB SERVICE
# -----------------------------------------------------------------------------
def get_qaqc_stats() -> dict:
    con = get_db()
    try:
        wir_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Work Inspection Request'").fetchone()[0]
        mir_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Material Inspection Request'").fetchone()[0]
        test_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Test Report'").fetchone()[0]
        audit_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Audit Report'").fetchone()[0]
        
        ncr_cnt = con.execute("""
            SELECT COUNT(*) FROM fact_mail 
            WHERE lower(mail_type) LIKE '%quality%' OR lower(mail_type) LIKE '%conformance%' OR lower(mail_type) LIKE '%ncr%'
        """).fetchone()[0]

        return {
            "total_wir": wir_cnt or 0,
            "total_mir": mir_cnt or 0,
            "total_ncrs": ncr_cnt or 0,
            "total_tests": test_cnt or 0,
            "total_audits": audit_cnt or 0
        }
    finally:
        con.close()

def get_qaqc_items(
    project: str = None,
    doc_type: str = None,
    review_status: str = None,
    search: str = None,
    from_date: str = None,
    to_date: str = None,
    page: int = 1,
    limit: int = 30
) -> dict:
    con = get_db()
    try:
        where_clauses = ["1=1"]
        params = []

        if project and project != "all":
            where_clauses.append("package_name = ?")
            params.append(project)
        if doc_type and doc_type != "all":
            where_clauses.append("doc_type = ?")
            params.append(doc_type)
        if review_status and review_status != "all":
            where_clauses.append("review_status = ?")
            params.append(review_status)
        if search:
            where_clauses.append("(lower(document_no) LIKE ? OR lower(title) LIKE ? OR lower(created_by) LIKE ?)")
            q = f"%{search.strip().lower()}%"
            params.extend([q, q, q])
        if from_date:
            where_clauses.append("date_modified >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("date_modified <= ?")
            params.append(to_date)

        where_sql = " AND ".join(where_clauses)
        
        base_cte = """
            WITH unified_qaqc AS (
                SELECT 
                    document_no,
                    doc_type,
                    title,
                    review_status,
                    revision,
                    created_by,
                    date_modified,
                    package_name,
                    aconex_url,
                    'Document' AS source_type
                FROM dim_documents
                WHERE doc_type IN ('Work Inspection Request', 'Material Inspection Request', 'Test Report', 'Audit Report', 'Comment Review Sheet', 'Inspection Test Plan', 'Method Statement', 'Pre-qualification', 'Material Sample', 'Procedure')
                UNION ALL
                SELECT 
                    mail_no AS document_no,
                    mail_type AS doc_type,
                    subject AS title,
                    status AS review_status,
                    '00' AS revision,
                    from_organization AS created_by,
                    sent_date AS date_modified,
                    project_package AS package_name,
                    aconex_url,
                    'Mail' AS source_type
                FROM fact_mail
                WHERE lower(mail_type) LIKE '%quality%' 
                   OR lower(mail_type) LIKE '%conformance%' 
                   OR lower(mail_type) LIKE '%corrective%' 
                   OR lower(mail_type) LIKE '%ncr%'
            )
        """

        count_sql = f"{base_cte} SELECT COUNT(*) FROM unified_qaqc WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            {base_cte}
            SELECT 
                document_no, doc_type, title, review_status, revision, 
                created_by, date_modified, package_name, aconex_url, source_type
            FROM unified_qaqc
            WHERE {where_sql}
            ORDER BY CASE WHEN TRY_CAST(date_modified AS DATE) <= CURRENT_DATE + INTERVAL 30 DAY THEN date_modified ELSE NULL END DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            date_str = r[6].strftime("%Y-%m-%d") if isinstance(r[6], datetime) else (str(r[6])[:10] if r[6] else "-")
            url = r[8] or ""
            if not url.startswith("http"):
                if r[9] == "Mail":
                    url = _to_authoritative_aconex_mail_url(r[0])
                else:
                    url = _to_authoritative_aconex_doc_url(r[0])
            items.append({
                "document_no": r[0],
                "doc_type": r[1],
                "title": r[2],
                "review_status": r[3] or "Pending",
                "revision": r[4] or "00",
                "created_by": r[5] or "-",
                "date_modified": date_str,
                "project": r[7] or "General",
                "aconex_url": url,
                "source_type": r[9]
            })

        projects = [p[0] for p in con.execute(f"{base_cte} SELECT DISTINCT package_name FROM unified_qaqc WHERE package_name IS NOT NULL ORDER BY 1").fetchall()]
        types = [t[0] for t in con.execute(f"{base_cte} SELECT DISTINCT doc_type FROM unified_qaqc ORDER BY 1").fetchall()]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "projects": projects,
            "types": types,
            "items": items
        }
    finally:
        con.close()


# -----------------------------------------------------------------------------
# 3. SITE OPERATIONS & SUPERVISION HUB SERVICE
# -----------------------------------------------------------------------------
def get_site_ops_stats() -> dict:
    con = get_db()
    try:
        scr_row = con.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_overdue = true) as overdue
            FROM fact_mail 
            WHERE mail_type = 'Site Clarification Request'
        """).fetchone()

        si_cnt = con.execute("SELECT COUNT(*) FROM fact_mail WHERE mail_type = 'Site Instruction'").fetchone()[0]
        access_cnt = con.execute("SELECT COUNT(*) FROM fact_mail WHERE mail_type = 'Access Request'").fetchone()[0]
        daily_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Daily Report'").fetchone()[0]
        weekly_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Weekly Report'").fetchone()[0]

        return {
            "total_scr": scr_row[0] or 0,
            "overdue_scr": scr_row[1] or 0,
            "total_si": si_cnt or 0,
            "total_access": access_cnt or 0,
            "daily_reports": daily_cnt or 0,
            "weekly_reports": weekly_cnt or 0
        }
    finally:
        con.close()

def get_site_ops_items(
    project: str = None,
    item_type: str = None,
    overdue_only: bool = False,
    search: str = None,
    from_date: str = None,
    to_date: str = None,
    page: int = 1,
    limit: int = 30
) -> dict:
    con = get_db()
    try:
        where_clauses = ["1=1"]
        params = []

        if project and project != "all":
            where_clauses.append("project_package = ?")
            params.append(project)
        if item_type and item_type != "all":
            where_clauses.append("mail_type = ?")
            params.append(item_type)
        if overdue_only:
            where_clauses.append("is_overdue = true")
        if search:
            where_clauses.append("(lower(mail_no) LIKE ? OR lower(subject) LIKE ? OR lower(from_organization) LIKE ? OR lower(to_organization) LIKE ?)")
            q = f"%{search.strip().lower()}%"
            params.extend([q, q, q, q])
        if from_date:
            where_clauses.append("sent_date >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("sent_date <= ?")
            params.append(to_date)

        where_sql = " AND ".join(where_clauses)
        
        base_cte = """
            WITH unified_site AS (
                SELECT 
                    mail_no,
                    mail_type,
                    subject,
                    from_organization,
                    to_organization,
                    sent_date,
                    status,
                    is_overdue,
                    project_package,
                    aconex_url,
                    'Mail' AS source_type
                FROM fact_mail
                WHERE mail_type IN ('Site Clarification Request', 'Response to Clarification', 'Site Instruction', 'Response to Site Instruction', 'Access Request', 'Response to Site Observation')
                UNION ALL
                SELECT 
                    document_no AS mail_no,
                    doc_type AS mail_type,
                    title AS subject,
                    discipline_name AS from_organization,
                    revision AS to_organization,
                    date_modified AS sent_date,
                    review_status AS status,
                    false AS is_overdue,
                    package_name AS project_package,
                    aconex_url,
                    'Document' AS source_type
                FROM dim_documents
                WHERE doc_type IN ('Daily Report', 'Weekly Report', 'Authority Approval & Permit', 'Plan')
            )
        """

        count_sql = f"{base_cte} SELECT COUNT(*) FROM unified_site WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            {base_cte}
            SELECT 
                mail_no, mail_type, subject, from_organization, to_organization, 
                sent_date, status, is_overdue, project_package, aconex_url, source_type
            FROM unified_site
            WHERE {where_sql}
            ORDER BY CASE WHEN TRY_CAST(sent_date AS DATE) <= CURRENT_DATE + INTERVAL 30 DAY THEN sent_date ELSE NULL END DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            sent_str = r[5].strftime("%Y-%m-%d") if isinstance(r[5], datetime) else (str(r[5])[:10] if r[5] else "-")
            url = r[9] or ""
            if not url.startswith("http"):
                if r[10] == "Document":
                    url = _to_authoritative_aconex_doc_url(r[0])
                else:
                    url = _to_authoritative_aconex_mail_url(r[0])
            items.append({
                "mail_no": r[0],
                "mail_type": r[1],
                "subject": r[2],
                "from_org": r[3] or "-",
                "to_org": r[4] or "-",
                "sent_date": sent_str,
                "status": r[6] or "Active",
                "is_overdue": bool(r[7]),
                "project": r[8] or "General",
                "aconex_url": url,
                "source_type": r[10]
            })

        projects = [p[0] for p in con.execute(f"{base_cte} SELECT DISTINCT project_package FROM unified_site WHERE project_package IS NOT NULL ORDER BY 1").fetchall()]
        types = [t[0] for t in con.execute(f"{base_cte} SELECT DISTINCT mail_type FROM unified_site ORDER BY 1").fetchall()]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "projects": projects,
            "types": types,
            "items": items
        }
    finally:
        con.close()


# -----------------------------------------------------------------------------
# 4. TECHNICAL OFFICE & SUBMITTALS HUB SERVICE
# -----------------------------------------------------------------------------
def get_technical_office_stats() -> dict:
    con = get_db()
    try:
        sd_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Shop Drawing'").fetchone()[0]
        mat_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Material Submission'").fetchone()[0]
        crs_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type = 'Comment Review Sheet'").fetchone()[0]
        calc_cnt = con.execute("SELECT COUNT(*) FROM dim_documents WHERE doc_type IN ('Design Calculation', 'Calculation Notes', 'Specifications')").fetchone()[0]

        # Top Disciplines Breakdown
        disciplines = con.execute("""
            SELECT discipline_name, COUNT(*) as cnt
            FROM dim_documents
            WHERE doc_type IN ('Shop Drawing', 'Material Submission', 'Comment Review Sheet')
              AND discipline_name IS NOT NULL AND discipline_name != ''
            GROUP BY 1
            ORDER BY cnt DESC
            LIMIT 8
        """).fetchall()

        return {
            "total_shop_drawings": sd_cnt or 0,
            "total_materials": mat_cnt or 0,
            "total_crs": crs_cnt or 0,
            "total_calculations": calc_cnt or 0,
            "disciplines_breakdown": [{"discipline": d[0], "count": d[1]} for d in disciplines]
        }
    finally:
        con.close()

def get_technical_office_items(
    project: str = None,
    discipline: str = None,
    doc_type: str = None,
    review_status: str = None,
    search: str = None,
    from_date: str = None,
    to_date: str = None,
    page: int = 1,
    limit: int = 30
) -> dict:
    con = get_db()
    try:
        where_clauses = ["1=1"]
        params = []

        if project and project != "all":
            where_clauses.append("package_name = ?")
            params.append(project)
        if discipline and discipline != "all":
            where_clauses.append("discipline_name = ?")
            params.append(discipline)
        if doc_type and doc_type != "all":
            where_clauses.append("doc_type = ?")
            params.append(doc_type)
        if review_status and review_status != "all":
            where_clauses.append("review_status = ?")
            params.append(review_status)
        if search:
            where_clauses.append("(lower(document_no) LIKE ? OR lower(title) LIKE ?)")
            q = f"%{search.strip().lower()}%"
            params.extend([q, q])
        if from_date:
            where_clauses.append("date_modified >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("date_modified <= ?")
            params.append(to_date)

        where_sql = " AND ".join(where_clauses)
        
        base_cte = """
            WITH unified_tech AS (
                SELECT 
                    document_no,
                    doc_type,
                    title,
                    discipline_name,
                    review_status,
                    revision,
                    date_modified,
                    package_name,
                    aconex_url,
                    'Document' AS source_type
                FROM dim_documents
                WHERE doc_type IN ('Drawing', 'Shop Drawing', '3D Model', 'BIM Model', 'Model', '2D Model', 'Calculation Notes', 'Design Calculation', 'Specifications', 'Material Submission', 'Comment Review Sheet', 'Presentation')
                UNION ALL
                SELECT 
                    mail_no AS document_no,
                    mail_type AS doc_type,
                    subject AS title,
                    from_organization AS discipline_name,
                    status AS review_status,
                    '00' AS revision,
                    sent_date AS date_modified,
                    project_package AS package_name,
                    aconex_url,
                    'Mail' AS source_type
                FROM fact_mail
                WHERE mail_type IN ('Request For Information', 'Response to RFI', 'Transmittal', 'Document Control Action', 'Response to Document Control Action', 'Document Number Request')
            )
        """

        count_sql = f"{base_cte} SELECT COUNT(*) FROM unified_tech WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            {base_cte}
            SELECT 
                document_no, doc_type, title, discipline_name, review_status, 
                revision, date_modified, package_name, aconex_url, source_type
            FROM unified_tech
            WHERE {where_sql}
            ORDER BY CASE WHEN TRY_CAST(date_modified AS DATE) <= CURRENT_DATE + INTERVAL 30 DAY THEN date_modified ELSE NULL END DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            date_str = r[6].strftime("%Y-%m-%d") if isinstance(r[6], datetime) else (str(r[6])[:10] if r[6] else "-")
            url = r[8] or ""
            if not url.startswith("http"):
                if r[9] == "Mail":
                    url = _to_authoritative_aconex_mail_url(r[0])
                else:
                    url = _to_authoritative_aconex_doc_url(r[0])
            items.append({
                "document_no": r[0],
                "doc_type": r[1],
                "title": r[2],
                "discipline": r[3] or "General",
                "review_status": r[4] or "Pending",
                "revision": r[5] or "00",
                "date_modified": date_str,
                "project": r[7] or "General",
                "aconex_url": url,
                "source_type": r[9]
            })

        projects = [p[0] for p in con.execute(f"{base_cte} SELECT DISTINCT package_name FROM unified_tech WHERE package_name IS NOT NULL ORDER BY 1").fetchall()]
        disciplines = [d[0] for d in con.execute(f"{base_cte} SELECT DISTINCT discipline_name FROM unified_tech WHERE discipline_name IS NOT NULL AND discipline_name != '' GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 15").fetchall()]
        types = [t[0] for t in con.execute(f"{base_cte} SELECT DISTINCT doc_type FROM unified_tech ORDER BY 1").fetchall()]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "projects": projects,
            "disciplines": disciplines,
            "types": types,
            "items": items
        }
    finally:
        con.close()


# -----------------------------------------------------------------------------
# 5. EXCEL EXPORT GENERATORS
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# 5. CONTRACTUAL CORRESPONDENCE SERVICE
# -----------------------------------------------------------------------------
def get_contractual_stats() -> dict:
    con = get_db()
    try:
        mail_row = con.execute("""
            SELECT 
                COUNT(*) as total_mail,
                COUNT(*) FILTER (WHERE mail_type = 'Letter') as letters,
                COUNT(*) FILTER (WHERE mail_type = 'General Correspondence') as gen_corr,
                COUNT(*) FILTER (WHERE is_overdue = true) as overdue,
                COUNT(*) FILTER (WHERE status IN ('Outstanding', 'Active') OR is_overdue = true) as pending
            FROM fact_mail
            WHERE mail_type IN ('Letter', 'General Correspondence', 'Memorandum', 'Email', 'Acknowledgement', 'Confirmation of Information', 'Request for Additional Information')
        """).fetchone()

        doc_row = con.execute("""
            SELECT 
                COUNT(*) as total_docs,
                COUNT(*) FILTER (WHERE doc_type IN ('Formal Letter', 'Letter')) as formal_letters,
                COUNT(*) FILTER (WHERE doc_type LIKE '%Instruction%' OR doc_type = 'Early Warning') as instructions
            FROM dim_documents
            WHERE doc_type IN ('Formal Letter', 'Letter', 'Client Instruction', 'Engineers Instruction', 'Confirmation of Verbal Instruction', 'Early Warning')
        """).fetchone()

        total_all = (mail_row[0] or 0) + (doc_row[0] or 0)
        total_letters = (mail_row[1] or 0) + (doc_row[1] or 0)

        return {
            "total_correspondence": total_all,
            "letters": total_letters,
            "general_correspondence": mail_row[2] or 0,
            "instructions": doc_row[2] or 0,
            "overdue": mail_row[3] or 0,
            "pending_action": mail_row[4] or 0
        }
    finally:
        con.close()


def get_contractual_items(
    project: str = None,
    item_type: str = None,
    category: str = None,
    status: str = None,
    search: str = None,
    from_date: str = None,
    to_date: str = None,
    page: int = 1,
    limit: int = 30
) -> dict:
    con = get_db()
    try:
        where_clauses = ["1=1"]
        params = []

        if category == "letters":
            where_clauses.append("(item_type LIKE '%Letter%')")
        elif category == "general":
            where_clauses.append("(item_type = 'General Correspondence')")
        elif category == "instructions":
            where_clauses.append("(item_type LIKE '%Instruction%' OR item_type = 'Early Warning')")
        elif category == "notices":
            where_clauses.append("(item_type IN ('Memorandum', 'Confirmation of Information', 'Acknowledgement', 'Request for Additional Information', 'Email'))")

        if project and project != "all":
            where_clauses.append("project_package = ?")
            params.append(project)
        if item_type and item_type != "all":
            where_clauses.append("item_type = ?")
            params.append(item_type)
        if status and status != "all":
            if status.lower() == "overdue":
                where_clauses.append("is_overdue = true")
            else:
                where_clauses.append("status = ?")
                params.append(status)
        if search:
            where_clauses.append("(lower(item_no) LIKE ? OR lower(title) LIKE ? OR lower(org_from) LIKE ? OR lower(org_to) LIKE ?)")
            q = f"%{search.strip().lower()}%"
            params.extend([q, q, q, q])
        if from_date:
            where_clauses.append("item_date >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("item_date <= ?")
            params.append(to_date)

        where_sql = " AND ".join(where_clauses)

        base_cte = """
            WITH unified_corr AS (
                SELECT 
                    mail_no AS item_no,
                    mail_type AS item_type,
                    subject AS title,
                    from_organization AS org_from,
                    to_organization AS org_to,
                    sent_date AS item_date,
                    status,
                    is_overdue,
                    project_package,
                    aconex_url,
                    'Mail' AS source_type
                FROM fact_mail
                WHERE mail_type IN ('Letter', 'General Correspondence', 'Memorandum', 'Email', 'Acknowledgement', 'Confirmation of Information', 'Request for Additional Information')
                UNION ALL
                SELECT 
                    document_no AS item_no,
                    doc_type AS item_type,
                    title,
                    discipline_name AS org_from,
                    revision AS org_to,
                    date_modified AS item_date,
                    'Registered' AS status,
                    false AS is_overdue,
                    project_package,
                    aconex_url,
                    'Document' AS source_type
                FROM dim_documents
                WHERE doc_type IN ('Formal Letter', 'Letter', 'Client Instruction', 'Engineers Instruction', 'Confirmation of Verbal Instruction', 'Early Warning')
            )
        """

        count_sql = f"{base_cte} SELECT COUNT(*) FROM unified_corr WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            {base_cte}
            SELECT 
                item_no, item_type, title, org_from, org_to, 
                item_date, status, is_overdue, project_package, aconex_url, source_type
            FROM unified_corr
            WHERE {where_sql}
            ORDER BY CASE WHEN TRY_CAST(item_date AS DATE) <= CURRENT_DATE + INTERVAL 30 DAY THEN item_date ELSE NULL END DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            date_str = r[5].strftime("%Y-%m-%d") if isinstance(r[5], datetime) else (str(r[5])[:10] if r[5] else "-")
            url = r[9] or ""
            if not url.startswith("http"):
                if r[10] == "Document":
                    url = _to_authoritative_aconex_doc_url(r[0])
                else:
                    url = _to_authoritative_aconex_mail_url(r[0])
            items.append({
                "item_no": r[0],
                "item_type": r[1],
                "title": r[2],
                "from_org": r[3] or "-",
                "to_org": r[4] or "-",
                "item_date": date_str,
                "status": r[6] or "Active",
                "is_overdue": bool(r[7]),
                "project": r[8] or "General",
                "aconex_url": url,
                "source_type": r[10]
            })

        projects = [p[0] for p in con.execute(f"{base_cte} SELECT DISTINCT project_package FROM unified_corr WHERE project_package IS NOT NULL ORDER BY 1").fetchall()]
        types = [t[0] for t in con.execute(f"{base_cte} SELECT DISTINCT item_type FROM unified_corr ORDER BY 1").fetchall()]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "projects": projects,
            "types": types,
            "items": items
        }
    finally:
        con.close()


# -----------------------------------------------------------------------------
# 6. COMMERCIAL & CONTROLS SERVICE
# -----------------------------------------------------------------------------
def get_commercial_stats() -> dict:
    con = get_db()
    try:
        row = con.execute("""
            SELECT 
                COUNT(*) as total_items,
                COUNT(*) FILTER (WHERE doc_type = 'Bill of Quantities') as boqs,
                COUNT(*) FILTER (WHERE doc_type IN ('Invoice', 'Payment Application')) as pay_apps_invoices,
                COUNT(*) FILTER (WHERE doc_type IN ('Variation Order', 'Claim')) as vos_claims,
                COUNT(*) FILTER (WHERE doc_type IN ('Proposal', 'Request for Proposal', 'Tender', 'Technical Bid Evaluation')) as proposals_tenders,
                COUNT(*) FILTER (WHERE doc_type IN ('Insurance Certificates and Bond', 'Contract', 'Asset Register', 'Cost Report', 'Budget Report', 'Scope of Works')) as bonds_costs
            FROM dim_documents
            WHERE doc_type IN ('Bill of Quantities', 'Invoice', 'Payment Application', 'Variation Order', 'Insurance Certificates and Bond', 'Request for Proposal', 'Cost Report', 'Budget Report', 'Tender', 'Technical Bid Evaluation', 'Contract', 'Claim', 'Scope of Works', 'Proposal', 'Asset Register')
        """).fetchone()

        tender_trans = con.execute("SELECT COUNT(*) FROM fact_mail WHERE mail_type = 'Tender Transmittal'").fetchone()[0]

        total_all = (row[0] or 0) + (tender_trans or 0)
        total_proposals = (row[4] or 0) + (tender_trans or 0)

        return {
            "total_commercial": total_all,
            "boqs": row[1] or 0,
            "payment_apps_invoices": row[2] or 0,
            "variation_orders_claims": row[3] or 0,
            "proposals_tenders": total_proposals,
            "bonds_contracts_costs": row[5] or 0
        }
    finally:
        con.close()


def get_commercial_items(
    project: str = None,
    item_type: str = None,
    category: str = None,
    status: str = None,
    search: str = None,
    from_date: str = None,
    to_date: str = None,
    page: int = 1,
    limit: int = 30
) -> dict:
    con = get_db()
    try:
        where_clauses = ["1=1"]
        params = []

        if category == "boqs":
            where_clauses.append("(item_type = 'Bill of Quantities')")
        elif category == "payments":
            where_clauses.append("(item_type IN ('Invoice', 'Payment Application'))")
        elif category == "variations":
            where_clauses.append("(item_type IN ('Variation Order', 'Claim'))")
        elif category == "proposals":
            where_clauses.append("(item_type IN ('Proposal', 'Request for Proposal', 'Tender', 'Technical Bid Evaluation', 'Tender Transmittal'))")
        elif category == "bonds":
            where_clauses.append("(item_type IN ('Insurance Certificates and Bond', 'Contract', 'Asset Register', 'Cost Report', 'Budget Report', 'Scope of Works'))")

        if project and project != "all":
            where_clauses.append("project_package = ?")
            params.append(project)
        if item_type and item_type != "all":
            where_clauses.append("item_type = ?")
            params.append(item_type)
        if status and status != "all":
            where_clauses.append("status = ?")
            params.append(status)
        if search:
            where_clauses.append("(lower(item_no) LIKE ? OR lower(title) LIKE ? OR lower(org_from) LIKE ? OR lower(org_to) LIKE ?)")
            q = f"%{search.strip().lower()}%"
            params.extend([q, q, q, q])
        if from_date:
            where_clauses.append("item_date >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("item_date <= ?")
            params.append(to_date)

        where_sql = " AND ".join(where_clauses)

        base_cte = """
            WITH unified_comm AS (
                SELECT 
                    document_no AS item_no,
                    doc_type AS item_type,
                    title,
                    discipline_name AS org_from,
                    revision AS org_to,
                    date_modified AS item_date,
                    'Registered' AS status,
                    false AS is_overdue,
                    project_package,
                    aconex_url,
                    'Document' AS source_type
                FROM dim_documents
                WHERE doc_type IN ('Bill of Quantities', 'Invoice', 'Payment Application', 'Variation Order', 'Insurance Certificates and Bond', 'Request for Proposal', 'Cost Report', 'Budget Report', 'Tender', 'Technical Bid Evaluation', 'Contract', 'Claim', 'Scope of Works', 'Proposal', 'Asset Register')
                UNION ALL
                SELECT 
                    mail_no AS item_no,
                    mail_type AS item_type,
                    subject AS title,
                    from_organization AS org_from,
                    to_organization AS org_to,
                    sent_date AS item_date,
                    status,
                    is_overdue,
                    project_package,
                    aconex_url,
                    'Mail' AS source_type
                FROM fact_mail
                WHERE mail_type IN ('Tender Transmittal')
            )
        """

        count_sql = f"{base_cte} SELECT COUNT(*) FROM unified_comm WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            {base_cte}
            SELECT 
                item_no, item_type, title, org_from, org_to, 
                item_date, status, is_overdue, project_package, aconex_url, source_type
            FROM unified_comm
            WHERE {where_sql}
            ORDER BY CASE WHEN TRY_CAST(item_date AS DATE) <= CURRENT_DATE + INTERVAL 30 DAY THEN item_date ELSE NULL END DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            date_str = r[5].strftime("%Y-%m-%d") if isinstance(r[5], datetime) else (str(r[5])[:10] if r[5] else "-")
            url = r[9] or ""
            if not url.startswith("http"):
                if r[10] == "Document":
                    url = _to_authoritative_aconex_doc_url(r[0])
                else:
                    url = _to_authoritative_aconex_mail_url(r[0])
            items.append({
                "item_no": r[0],
                "item_type": r[1],
                "title": r[2],
                "from_org": r[3] or "-",
                "to_org": r[4] or "-",
                "item_date": date_str,
                "status": r[6] or "Active",
                "is_overdue": bool(r[7]),
                "project": r[8] or "General",
                "aconex_url": url,
                "source_type": r[10]
            })

        projects = [p[0] for p in con.execute(f"{base_cte} SELECT DISTINCT project_package FROM unified_comm WHERE project_package IS NOT NULL ORDER BY 1").fetchall()]
        types = [t[0] for t in con.execute(f"{base_cte} SELECT DISTINCT item_type FROM unified_comm ORDER BY 1").fetchall()]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "projects": projects,
            "types": types,
            "items": items
        }
    finally:
        con.close()


def generate_discipline_excel(hub_name: str, rows_data: list, columns_spec: list) -> tuple[bytes, str]:
    """Generates an executive styled Excel sheet for any of the 4 discipline hubs."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = hub_name[:30]
    ws.views.sheetView[0].showGridLines = True

    # Styling definitions
    title_font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    title_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    
    regular_font = Font(name="Calibri", size=9, color="0F172A")
    link_font = Font(name="Calibri", size=9, bold=True, color="0284C7", underline="single")
    
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # Title Banner (Row 1-2)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns_spec))
    top_cell = ws.cell(row=1, column=1, value=f"Ras El Hekma Project Controls — {hub_name}")
    top_cell.font = title_font
    top_cell.fill = title_fill
    top_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns_spec))
    sub_cell = ws.cell(row=2, column=1, value=f"Exported from Oracle Aconex DuckDB Data Warehouse • Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    sub_cell.font = Font(name="Calibri", size=9, italic=True, color="94A3B8")
    sub_cell.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    sub_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 18

    # Blank Row 3
    ws.row_dimensions[3].height = 8

    # Table Headers (Row 4)
    ws.row_dimensions[4].height = 24
    for col_idx, col in enumerate(columns_spec, 1):
        cell = ws.cell(row=4, column=col_idx, value=col["header"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal=col.get("align", "left"), vertical="center")
        cell.border = thin_border

    # Data Rows
    current_row = 5
    for item in rows_data:
        ws.row_dimensions[current_row].height = 20
        row_fill = PatternFill(start_color="F8FAFC" if current_row % 2 == 0 else "FFFFFF", fill_type="solid")
        
        for col_idx, col in enumerate(columns_spec, 1):
            val = item.get(col["field"], "")
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.font = regular_font
            cell.fill = row_fill
            cell.alignment = Alignment(horizontal=col.get("align", "left"), vertical="center")
            cell.border = thin_border

            if col.get("is_link") and item.get("aconex_url"):
                cell.font = link_font
                cell.hyperlink = item.get("aconex_url")

        current_row += 1

    # Auto-fit column widths
    for col_idx, col in enumerate(columns_spec, 1):
        col_letter = get_column_letter(col_idx)
        max_len = max(len(str(col["header"])), col.get("min_width", 12))
        ws.column_dimensions[col_letter].width = min(max_len + 3, 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"{hub_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return buf.getvalue(), filename
