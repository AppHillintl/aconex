import io
import os
import duckdb
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")

def get_db():
    return duckdb.connect(DB_PATH, read_only=True)

# -----------------------------------------------------------------------------
# 1. HSE & SAFETY HUB SERVICE
# -----------------------------------------------------------------------------
def get_safety_stats() -> dict:
    con = get_db()
    try:
        row = con.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE mail_type = 'HSE Observation') as obs,
                COUNT(*) FILTER (WHERE mail_type = 'Observation Remedial Actions') as rem,
                COUNT(*) FILTER (WHERE mail_type = 'Accepted Observation Closure') as closed,
                COUNT(*) FILTER (WHERE mail_type = 'Rejected Observation Closure' OR (is_overdue = true AND mail_type LIKE '%Observation%')) as rejected,
                COUNT(*) FILTER (WHERE mail_type LIKE '%Health and Safety Non-Conformance Report%') as ncrs
            FROM fact_mail
        """).fetchone()

        trans_cnt = con.execute("""
            SELECT COUNT(*) 
            FROM fact_document_transmittals 
            WHERE lower(discipline) LIKE '%safety%' OR lower(discipline) LIKE '%hse%'
        """).fetchone()[0]

        return {
            "total_observations": row[0] or 0,
            "remedial_actions": row[1] or 0,
            "closed_observations": row[2] or 0,
            "rejected_or_overdue": row[3] or 0,
            "hse_ncrs": row[4] or 0,
            "hse_transmittals": trans_cnt or 0
        }
    finally:
        con.close()

def get_safety_items(
    project: str = None,
    item_type: str = None,
    status: str = None,
    search: str = None,
    from_date: str = None,
    to_date: str = None,
    page: int = 1,
    limit: int = 30
) -> dict:
    con = get_db()
    try:
        where_clauses = ["(lower(mail_type) LIKE '%hse%' OR lower(mail_type) LIKE '%safety%' OR lower(mail_type) LIKE '%observation%')"]
        params = []

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
        
        count_sql = f"SELECT COUNT(*) FROM fact_mail WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            SELECT 
                mail_no, mail_type, subject, from_organization, to_organization, 
                sent_date, status, is_overdue, project_package, aconex_url
            FROM fact_mail
            WHERE {where_sql}
            ORDER BY sent_date DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            sent_str = r[5].strftime("%Y-%m-%d") if isinstance(r[5], datetime) else (str(r[5])[:10] if r[5] else "-")
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
                "aconex_url": r[9] or ""
            })

        # Fetch distinct project list and types for filters
        projects = [p[0] for p in con.execute("""
            SELECT DISTINCT project_package FROM fact_mail 
            WHERE project_package IS NOT NULL AND (lower(mail_type) LIKE '%hse%' OR lower(mail_type) LIKE '%safety%' OR lower(mail_type) LIKE '%observation%')
            ORDER BY 1
        """).fetchall()]

        types = [t[0] for t in con.execute("""
            SELECT DISTINCT mail_type FROM fact_mail 
            WHERE lower(mail_type) LIKE '%hse%' OR lower(mail_type) LIKE '%safety%' OR lower(mail_type) LIKE '%observation%'
            ORDER BY 1
        """).fetchall()]

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
        where_clauses = ["doc_type IN ('Work Inspection Request', 'Material Inspection Request', 'Test Report', 'Audit Report')"]
        params = []

        if project and project != "all":
            where_clauses.append("project_package = ?")
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
        
        count_sql = f"SELECT COUNT(*) FROM dim_documents WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            SELECT 
                document_no, doc_type, title, review_status, revision, 
                created_by, date_modified, project_package, aconex_url
            FROM dim_documents
            WHERE {where_sql}
            ORDER BY date_modified DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            date_str = r[6].strftime("%Y-%m-%d") if isinstance(r[6], datetime) else (str(r[6])[:10] if r[6] else "-")
            items.append({
                "document_no": r[0],
                "doc_type": r[1],
                "title": r[2],
                "review_status": r[3] or "Pending",
                "revision": r[4] or "00",
                "created_by": r[5] or "-",
                "date_modified": date_str,
                "project": r[7] or "General",
                "aconex_url": r[8] or ""
            })

        projects = [p[0] for p in con.execute("""
            SELECT DISTINCT project_package FROM dim_documents 
            WHERE project_package IS NOT NULL AND doc_type IN ('Work Inspection Request', 'Material Inspection Request', 'Test Report', 'Audit Report')
            ORDER BY 1
        """).fetchall()]

        types = ['Work Inspection Request', 'Material Inspection Request', 'Test Report', 'Audit Report']

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
        where_clauses = ["mail_type IN ('Site Clarification Request', 'Site Instruction', 'Access Request')"]
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
        
        count_sql = f"SELECT COUNT(*) FROM fact_mail WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            SELECT 
                mail_no, mail_type, subject, from_organization, to_organization, 
                sent_date, status, is_overdue, project_package, aconex_url
            FROM fact_mail
            WHERE {where_sql}
            ORDER BY sent_date DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            sent_str = r[5].strftime("%Y-%m-%d") if isinstance(r[5], datetime) else (str(r[5])[:10] if r[5] else "-")
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
                "aconex_url": r[9] or ""
            })

        projects = [p[0] for p in con.execute("""
            SELECT DISTINCT project_package FROM fact_mail 
            WHERE project_package IS NOT NULL AND mail_type IN ('Site Clarification Request', 'Site Instruction', 'Access Request')
            ORDER BY 1
        """).fetchall()]

        types = ['Site Clarification Request', 'Site Instruction', 'Access Request']

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
        where_clauses = ["doc_type IN ('Shop Drawing', 'Material Submission', 'Comment Review Sheet', 'Design Calculation', 'Specifications')"]
        params = []

        if project and project != "all":
            where_clauses.append("project_package = ?")
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
        
        count_sql = f"SELECT COUNT(*) FROM dim_documents WHERE {where_sql}"
        total = con.execute(count_sql, params).fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_sql = f"""
            SELECT 
                document_no, doc_type, title, discipline_name, review_status, 
                revision, date_modified, project_package, aconex_url
            FROM dim_documents
            WHERE {where_sql}
            ORDER BY date_modified DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(data_sql, params).fetchall()

        items = []
        for r in rows:
            date_str = r[6].strftime("%Y-%m-%d") if isinstance(r[6], datetime) else (str(r[6])[:10] if r[6] else "-")
            items.append({
                "document_no": r[0],
                "doc_type": r[1],
                "title": r[2],
                "discipline": r[3] or "General",
                "review_status": r[4] or "Pending",
                "revision": r[5] or "00",
                "date_modified": date_str,
                "project": r[7] or "General",
                "aconex_url": r[8] or ""
            })

        projects = [p[0] for p in con.execute("""
            SELECT DISTINCT project_package FROM dim_documents 
            WHERE project_package IS NOT NULL AND doc_type IN ('Shop Drawing', 'Material Submission', 'Comment Review Sheet')
            ORDER BY 1
        """).fetchall()]

        disciplines = [d[0] for d in con.execute("""
            SELECT DISTINCT discipline_name FROM dim_documents 
            WHERE discipline_name IS NOT NULL AND discipline_name != ''
            GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 15
        """).fetchall()]

        types = ['Shop Drawing', 'Material Submission', 'Comment Review Sheet', 'Design Calculation', 'Specifications']

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
