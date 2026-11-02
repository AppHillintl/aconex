import io
import os
import re
import urllib.parse
from datetime import datetime
from email.message import EmailMessage
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import duckdb

import sys
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import package_resolver as pr

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

def get_db():
    return duckdb.connect(DB_PATH, read_only=True)

# Default EGIS Consultant Contacts
DEFAULT_EGIS_TO = [
    "buchr.barmada@egis-group.com",
    "dalia.fathy@egis-group.com",
    "asad.najajreh@egis-group.com"
]

DEFAULT_EGIS_CC = [
    "DeanEnglish@hillintl.com",
    "HossameldinSwaify@hillintl.com",
    "mohamedmeneaem@hillintl.com"
]

def get_egis_review_summary(package_filter: str = None) -> dict:
    """
    Returns high-level statistics and distinct workflow deliverables
    currently under technical review by EGIS consultants.
    """
    con = get_db()
    try:
        where_clause = "WHERE (s.assigned_to_organization ILIKE '%EGIS%' OR s.assigned_to_name ILIKE '%EGIS%')"
        params = []
        if package_filter and package_filter.lower() != 'all':
            where_clause += " AND w.project_package = ?"
            params.append(package_filter)

        # 1. KPIs
        kpis = con.execute(f"""
            SELECT 
                count(DISTINCT CASE WHEN s.is_overdue = true AND s.step_status != 'Completed' THEN s.workflow_no END) as overdue_workflows,
                count(DISTINCT CASE WHEN s.step_status = 'Current' THEN s.workflow_no END) as active_workflows,
                count(DISTINCT s.workflow_no) as total_workflows,
                MAX(CASE WHEN s.is_overdue = true AND s.step_status != 'Completed' THEN s.days_late ELSE 0 END) as max_days_late
            FROM fact_workflow_steps s
            JOIN fact_workflows w ON s.workflow_no = w.workflow_no
            {where_clause}
        """, params).fetchone()

        # 2. Distinct Deliverables Table (Grouped by Workflow No.)
        rows = con.execute(f"""
            SELECT 
                s.workflow_no,
                FIRST(s.step_name) as step_name,
                FIRST(s.document_no) as document_no,
                FIRST(s.document_title) as document_title,
                FIRST(s.assigned_to_organization) as assigned_org,
                STRING_AGG(DISTINCT s.assigned_to_name, ', ') as assigned_user,
                MIN(s.date_due)::VARCHAR as date_due,
                MAX(s.days_late) as days_late,
                FIRST(w.project_package) as project_package,
                FIRST(w.workflow_name) as workflow_name,
                FIRST(COALESCE(
                    CASE WHEN d.tracking_id IS NOT NULL THEN 'https://mea.aconex.com/ViewDoc?trackingid=' || d.tracking_id || '&projectid=1744833878' END,
                    d.aconex_url,
                    '/api/aconex/doc?doc_no=' || replace(s.document_no, chr(39), '')
                )) as aconex_url,
                BOOL_OR(s.is_overdue AND s.step_status != 'Completed') as is_overdue,
                FIRST(s.step_status) as step_status
            FROM fact_workflow_steps s
            JOIN fact_workflows w ON s.workflow_no = w.workflow_no
            LEFT JOIN dim_documents d ON trim(replace(s.document_no, chr(39), '')) = trim(replace(d.document_no, chr(39), ''))
            {where_clause}
            GROUP BY s.workflow_no
            ORDER BY MAX(CASE WHEN s.is_overdue AND s.step_status != 'Completed' THEN s.days_late ELSE -999 END) DESC, s.workflow_no ASC
        """, params).fetchall()

        items = []
        for r in rows:
            items.append({
                "workflow_no": r[0],
                "step_name": r[1] or "Consultant Review",
                "document_no": r[2] or "-",
                "document_title": r[3] or r[9] or "-",
                "assigned_org": r[4] or "EGIS",
                "assigned_user": r[5] or "EGIS Reviewer",
                "date_due": str(r[6])[:10] if r[6] else "-",
                "days_late": int(r[7] or 0),
                "project_package": r[8] or "General",
                "workflow_name": r[9] or "-",
                "aconex_url": r[10],
                "is_overdue": bool(r[11]),
                "step_status": r[12]
            })

        return {
            "overdue_workflows": kpis[0] or 0,
            "active_workflows": kpis[1] or 0,
            "total_workflows": kpis[2] or 0,
            "max_days_late": kpis[3] or 0,
            "deliverables": items,
            "to_emails": DEFAULT_EGIS_TO,
            "cc_emails": DEFAULT_EGIS_CC
        }
    finally:
        con.close()

def generate_egis_excel(package_filter: str = None) -> bytes:
    """Generates an executive-styled Excel workbook containing EGIS review deliverables with live Aconex links."""
    data = get_egis_review_summary(package_filter)
    items = data["deliverables"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "EGIS Review Register"

    font_title = Font(name="Calibri", size=14, bold=True, color="003366")
    font_head = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_norm = Font(name="Calibri", size=10)
    font_link = Font(name="Calibri", size=10, color="004B87", underline="single")
    font_red = Font(name="Calibri", size=10, bold=True, color="C00000")

    fill_head = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
    fill_zebra = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")

    ws.cell(1, 1, "RAS EL HEKMA PROJECT — EGIS CONSULTANT REVIEW REGISTER").font = font_title
    ws.cell(2, 1, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total Deliverables: {len(items)} | Overdue: {data['overdue_workflows']}").font = font_bold

    headers = [
        "Workflow No", "Document Number", "Document Title", "Package",
        "Step Name", "Assigned EGIS User", "Due Date", "Days Late", "Status", "Aconex Direct Link"
    ]
    for col_idx, h in enumerate(headers, start=1):
        c = ws.cell(4, col_idx, h)
        c.font = font_head
        c.fill = fill_head
        c.alignment = Alignment(horizontal="center", vertical="center")

    row_idx = 5
    for item in items:
        ws.cell(row_idx, 1, item["workflow_no"]).font = font_bold
        ws.cell(row_idx, 2, item["document_no"]).font = font_bold
        ws.cell(row_idx, 3, item["document_title"]).font = font_norm
        ws.cell(row_idx, 4, item["project_package"]).font = font_norm
        ws.cell(row_idx, 5, item["step_name"]).font = font_norm
        ws.cell(row_idx, 6, item["assigned_user"]).font = font_norm
        ws.cell(row_idx, 7, item["date_due"]).font = font_norm
        
        c_late = ws.cell(row_idx, 8, item["days_late"])
        if item["is_overdue"]:
            c_late.font = font_red
        else:
            c_late.font = font_norm
            
        ws.cell(row_idx, 9, "Overdue" if item["is_overdue"] else item["step_status"]).font = font_bold
        
        c_link = ws.cell(row_idx, 10, "Open in Aconex ↗")
        c_link.font = font_link
        c_link.hyperlink = item["aconex_url"]
        
        if row_idx % 2 == 0:
            for col in range(1, 11):
                ws.cell(row_idx, col).fill = fill_zebra
        row_idx += 1

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def generate_egis_eml(package_filter: str = None) -> tuple[bytes, str]:
    """Generates an Outlook-compatible .eml draft pre-attached with Excel for EGIS consultants."""
    data = get_egis_review_summary(package_filter)
    excel_bytes = generate_egis_excel(package_filter)
    fname = f"EGIS_Consultant_Review_{datetime.now().strftime('%Y%m%d')}.xlsx"

    msg = EmailMessage()
    msg['From'] = "Ras El Hekma Project Controls <controls@raselhekma.gov.ae>"
    msg['To'] = ", ".join(data["to_emails"])
    msg['Cc'] = ", ".join(data["cc_emails"])
    msg['Subject'] = f"ACTION REQUIRED: Ras El Hekma - EGIS Review Deliverables Backlog ({data['overdue_workflows']} Overdue)"

    html_content = f"""
    <html>
    <head><style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; background: #f8fafc; margin: 0; padding: 20px; }}
        .card {{ background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 24px; max-width: 900px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        .header {{ border-bottom: 2px solid #0284c7; padding-bottom: 16px; margin-bottom: 20px; }}
        .title {{ font-size: 20px; font-weight: 800; color: #0f172a; margin: 0; }}
        .kpi-row {{ display: flex; gap: 12px; margin-bottom: 20px; }}
        .kpi {{ flex: 1; padding: 12px; border-radius: 8px; background: #f1f5f9; text-align: center; }}
        .kpi-val {{ font-size: 22px; font-weight: 900; }}
        .kpi-lbl {{ font-size: 11px; color: #64748b; font-weight: 700; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 16px; }}
        th {{ background: #0f172a; color: #ffffff; text-align: left; padding: 10px; font-weight: 700; }}
        td {{ padding: 9px 10px; border-bottom: 1px solid #e2e8f0; }}
        tr:nth-child(even) {{ background: #f8fafc; }}
        .badge-overdue {{ background: #fee2e2; color: #b91c1c; font-weight: 800; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }}
        .link-btn {{ color: #0284c7; font-weight: 700; text-decoration: none; }}
        .footer {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; }}
    </style></head>
    <body>
        <div class="card">
            <div class="header">
                <h1 class="title">EGIS Consultant Review &amp; Approval Backlog</h1>
                <p style="font-size: 12px; color: #64748b; margin: 4px 0 0;">Ras El Hekma Master Development • Oracle Aconex Automated Tracking</p>
            </div>
            <div class="kpi-row">
                <div class="kpi"><div class="kpi-val" style="color:#b91c1c;">{data['overdue_workflows']}</div><div class="kpi-lbl">Overdue Review Steps</div></div>
                <div class="kpi"><div class="kpi-val" style="color:#0284c7;">{data['active_workflows']}</div><div class="kpi-lbl">Current In-Review</div></div>
                <div class="kpi"><div class="kpi-val" style="color:#334155;">{data['total_workflows']}</div><div class="kpi-lbl">Total Workflows</div></div>
                <div class="kpi"><div class="kpi-val" style="color:#ea580c;">+{data['max_days_late']}d</div><div class="kpi-lbl">Max SLA Delay</div></div>
            </div>
            <p style="font-size: 13px; line-height: 1.5;">Dear EGIS Engineering Team,<br><br>Please find itemized below technical submittals and review workflow steps currently assigned to EGIS exceeding or approaching contractual turnaround dates. Direct 1-click Aconex links are provided for immediate action:</p>
            <table>
                <thead>
                    <tr>
                        <th>Workflow No</th>
                        <th>Document No</th>
                        <th>Title / Submittal</th>
                        <th>Step</th>
                        <th>Due Date</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
    """
    for item in data["deliverables"][:50]:
        badge = f'<span class="badge-overdue">+{item["days_late"]}d Late</span>' if item["is_overdue"] else f'<span style="color:#0284c7; font-weight:700;">{item["step_status"]}</span>'
        html_content += f"""
                    <tr>
                        <td><strong>{item["workflow_no"]}</strong></td>
                        <td>{item["document_no"]}</td>
                        <td>{item["document_title"][:55]}</td>
                        <td>{item["step_name"]}</td>
                        <td>{item["date_due"]}</td>
                        <td>{badge}</td>
                        <td><a href="{item['aconex_url']}" class="link-btn" target="_blank">Open in Aconex ↗</a></td>
                    </tr>
        """
    html_content += f"""
                </tbody>
            </table>
            <div class="footer">
                <p>The complete register with all active submittals and historical package details is attached as an Excel spreadsheet: <strong>{fname}</strong>.</p>
                <p>Please take immediate review action in Oracle Aconex before the end of this business week.</p>
            </div>
        </div>
    </body>
    </html>
    """
    msg.set_content(html_content, subtype='html')
    msg.add_attachment(excel_bytes, maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=fname)

    eml_bytes = msg.as_bytes()
    eml_fname = f"EGIS_Review_Reminder_{datetime.now().strftime('%Y%m%d')}.eml"
    return eml_bytes, eml_fname
