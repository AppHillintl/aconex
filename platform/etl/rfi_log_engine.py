import os
import io
import re
import glob
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import duckdb

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")
DP07_ORIGINAL_PATH = r"C:\Users\bimst\Downloads\ACONEX\DP07- RFI-log.xlsx"

# Standard Design Packages in the Project
DESIGN_PACKAGES = ["DP01", "DP02", "DP03", "DP04", "DP05", "DP06", "DP07", "DP08"]

def get_mail_links_dict(con, mail_nos):
    """Fetches dictionary of mail_no -> aconex_url for given mail numbers."""
    if not mail_nos:
        return {}
    clean_mails = [str(m).strip() for m in mail_nos if m and isinstance(m, str) and '-' in m]
    if not clean_mails:
        return {}
    
    # Batch query in chunks of 500
    res = {}
    chunk_size = 500
    for i in range(0, len(clean_mails), chunk_size):
        chunk = clean_mails[i:i + chunk_size]
        placeholders = ','.join(['?'] * len(chunk))
        q = f"SELECT mail_no, aconex_url FROM mail_aconex_links WHERE mail_no IN ({placeholders})"
        rows = con.execute(q, chunk).fetchall()
        for m_no, url in rows:
            if url:
                res[m_no] = url
    return res

def detect_package_from_name_or_content(filename: str = "", wb: openpyxl.Workbook = None) -> str:
    """Detects Package identifier (DP01-DP08, INFRA, MSS, RO, STP, AIRPORT, CANAL) from filename or sheet title."""
    text = (filename or '').upper()
    if wb:
        try:
            ws = wb.active
            text += " " + str(ws.cell(1, 1).value or '').upper()
            text += " " + " ".join(wb.sheetnames).upper()
        except Exception:
            pass

    # Check strategic packages first
    if "INFRA" in text:
        return "INFRA"
    if "MSS" in text or "MPS" in text or "POWER" in text:
        return "MSS"
    if re.search(r'\bRO\b', text) or "RO PLANT" in text or "POTABLE" in text or "3045" in text:
        return "RO"
    if "STP" in text or "SEWAGE" in text:
        return "STP"
    if "REHIA" in text or "AIRPORT" in text:
        return "AIRPORT"
    if "CANAL" in text or "LAGOON" in text:
        return "CANAL"

    m = re.search(r'DP\s*-?\s*0?(\d+)', text, re.IGNORECASE)
    if m:
        return f"DP{int(m.group(1)):02d}"

    return "DP07"

def parse_original_dp07_excel(con):
    """
    Parses existing DP07- RFI-log.xlsx to maintain 100% fidelity with historical records,
    enriching all cells with live Aconex URLs.
    """
    if not os.path.exists(DP07_ORIGINAL_PATH):
        return []
    
    wb = openpyxl.load_workbook(DP07_ORIGINAL_PATH, data_only=True)
    all_rows = []
    needed_mails = set()
    
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for r in range(5, ws.max_row + 1):
            mail_col1 = ws.cell(r, 1).value
            mail_col2 = ws.cell(r, 2).value
            rev = ws.cell(r, 3).value or 0
            rfi_no = ws.cell(r, 4).value
            subject = ws.cell(r, 5).value
            sent_date = ws.cell(r, 6).value
            h_c_mail = ws.cell(r, 7).value
            h_c_date = ws.cell(r, 8).value
            c_h_mail = ws.cell(r, 9).value
            c_h_date = ws.cell(r, 10).value
            h_cont_mail = ws.cell(r, 11).value
            h_cont_date = ws.cell(r, 12).value
            dewan_mail = ws.cell(r, 13).value
            dewan_date = ws.cell(r, 14).value
            ccc_mail = ws.cell(r, 15).value
            ccc_date = ws.cell(r, 16).value
            status = ws.cell(r, 17).value
            
            if not any([mail_col1, mail_col2, rfi_no, subject]):
                continue
                
            main_mail = mail_col2 or mail_col1 or rfi_no
            item = {
                "sheet": sheet_name,
                "acc_mail": str(mail_col1).strip() if mail_col1 else None,
                "cscec_mail": str(mail_col2).strip() if mail_col2 else None,
                "mail_no": str(main_mail).strip() if main_mail else "",
                "rev": rev,
                "rfi_no": str(rfi_no).strip() if rfi_no else str(main_mail).strip(),
                "subject": str(subject).strip() if subject else "",
                "from_org": "CSCEC EGYPT" if mail_col2 else ("Consolidated Contractors Group S.A.L. (Offshore) (CCC)" if mail_col1 else "Contractor"),
                "to_org": "Hill Inter",
                "sent_date": sent_date,
                "status": "Response" if str(status).strip().lower() == "response" or h_cont_mail else "Open",
                "days_late": 0,
                "hill_to_consultant_mail": str(h_c_mail).strip() if h_c_mail else None,
                "hill_to_consultant_date": h_c_date,
                "consultant_to_hill_mail": str(c_h_mail).strip() if c_h_mail else None,
                "consultant_to_hill_date": c_h_date,
                "hill_to_contractor_mail": str(h_cont_mail).strip() if h_cont_mail else None,
                "hill_to_contractor_date": h_cont_date,
                "dewan_mail": str(dewan_mail).strip() if dewan_mail else None,
                "dewan_date": dewan_date,
                "ccc_mail": str(ccc_mail).strip() if ccc_mail else None,
                "ccc_date": ccc_date,
            }
            all_rows.append(item)
            
            for m in [mail_col1, mail_col2, h_c_mail, c_h_mail, h_cont_mail, dewan_mail, ccc_mail]:
                if m and isinstance(m, str) and '-' in m:
                    needed_mails.add(m.strip())
                    
    # Lookup URLs
    url_map = get_mail_links_dict(con, list(needed_mails))
    for item in all_rows:
        item["acc_mail_url"] = url_map.get(item["acc_mail"])
        item["cscec_mail_url"] = url_map.get(item["cscec_mail"])
        item["aconex_url"] = url_map.get(item["mail_no"])
        item["hill_to_consultant_url"] = url_map.get(item["hill_to_consultant_mail"])
        item["consultant_to_hill_url"] = url_map.get(item["consultant_to_hill_mail"])
        item["hill_to_contractor_url"] = url_map.get(item["hill_to_contractor_mail"])
        item["dewan_url"] = url_map.get(item["dewan_mail"])
        item["ccc_url"] = url_map.get(item["ccc_mail"])
        
    return all_rows

def extract_rfi_log_data(package_filter="DP07"):
    """
    Extracts RFI multi-party lifecycle chain from DuckDB and/or existing logs:
    Contractor -> Hill -> Consultant -> Hill -> Contractor
    """
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        norm_pkg = (package_filter or "DP07").strip().upper()
        
        # If DP07, start with the official baseline
        existing_data = []
        existing_rfis_set = set()
        if norm_pkg in ["DP07", "ALL"]:
            existing_data = parse_original_dp07_excel(con)
            for item in existing_data:
                if item.get("rfi_no"):
                    existing_rfis_set.add(item["rfi_no"].lower())
                if item.get("mail_no"):
                    existing_rfis_set.add(item["mail_no"].lower())
        
        # Search DuckDB for RFIs
        pkg_term = f"%{norm_pkg}%" if norm_pkg != "ALL" else "%"
        
        query_base = """
        SELECT DISTINCT 
            m.mail_no,
            COALESCE(m.reference_number, m.mail_no) as reference_number,
            m.subject,
            m.from_organization,
            m.to_organization,
            m.sent_date,
            m.status,
            m.days_late,
            COALESCE(
                CASE WHEN m.aconex_url LIKE '%MiniURL%' THEN m.aconex_url END,
                CASE WHEN l.aconex_url LIKE '%MiniURL%' THEN l.aconex_url END,
                l.aconex_url,
                m.aconex_url
            ) as aconex_url
        FROM fact_mail m
        LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
        WHERE (m.mail_type = 'Request For Information' OR m.mail_no LIKE '%-RFI-%')
          AND (
            ? = '%' OR 
            m.subject ILIKE ? OR 
            COALESCE(m.reference_number, '') ILIKE ? OR
            m.mail_no ILIKE ?
          )
        ORDER BY m.sent_date DESC
        """
        base_rows = con.execute(query_base, [pkg_term, pkg_term, pkg_term, pkg_term]).fetchall()
        
        new_items = []
        for r in base_rows:
            m_no, ref_no, subj, f_org, t_org, s_dt, st, d_late, aconex_url = r
            
            if (m_no and m_no.lower() in existing_rfis_set) or (ref_no and ref_no.lower() in existing_rfis_set):
                continue
                
            chain_query = """
            SELECT DISTINCT 
                m.mail_no,
                m.mail_type,
                m.from_organization,
                m.to_organization,
                m.sent_date,
                COALESCE(
                    CASE WHEN m.aconex_url LIKE '%MiniURL%' THEN m.aconex_url END,
                    CASE WHEN l.aconex_url LIKE '%MiniURL%' THEN l.aconex_url END,
                    l.aconex_url,
                    m.aconex_url
                ) as aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE (m.reference_number = ? AND m.reference_number IS NOT NULL AND m.reference_number != '')
               OR (m.subject ILIKE ? AND LENGTH(?) >= 8)
               OR m.mail_no IN (
                    SELECT response_mail_no FROM fact_mail_threads WHERE mail_no = ? AND response_mail_no IS NOT NULL
                  )
            ORDER BY m.sent_date ASC
            """
            chain_rows = con.execute(chain_query, [ref_no or m_no, f"%{m_no}%", m_no, m_no]).fetchall()
            
            item = {
                "sheet": "GEN",
                "acc_mail": m_no if "ccc" in (f_org or "").lower() else None,
                "acc_mail_url": aconex_url if "ccc" in (f_org or "").lower() else None,
                "cscec_mail": m_no if "ccc" not in (f_org or "").lower() else None,
                "cscec_mail_url": aconex_url if "ccc" not in (f_org or "").lower() else None,
                "mail_no": m_no,
                "aconex_url": aconex_url,
                "rev": 0,
                "rfi_no": ref_no or m_no,
                "subject": subj or "",
                "from_org": f_org or "",
                "to_org": t_org or "",
                "sent_date": s_dt,
                "status": "Open",
                "days_late": d_late or 0,
                "hill_to_consultant_mail": None,
                "hill_to_consultant_url": None,
                "hill_to_consultant_date": None,
                "consultant_to_hill_mail": None,
                "consultant_to_hill_url": None,
                "consultant_to_hill_date": None,
                "hill_to_contractor_mail": None,
                "hill_to_contractor_url": None,
                "hill_to_contractor_date": None,
                "dewan_mail": None,
                "dewan_url": None,
                "dewan_date": None,
                "ccc_mail": None,
                "ccc_url": None,
                "ccc_date": None,
            }
            
            for cm in chain_rows:
                cm_no, cm_type, cm_from, cm_to, cm_date, cm_url = cm
                cm_from_l = (cm_from or "").lower()
                cm_to_l = (cm_to or "").lower()
                
                if cm_no == m_no:
                    continue
                    
                if "hill" in cm_from_l and any(c in cm_to_l for c in ["obmi", "shaker", "ecg", "consultant", "dar", "egis"]):
                    if not item["hill_to_consultant_mail"]:
                        item["hill_to_consultant_mail"] = cm_no
                        item["hill_to_consultant_url"] = cm_url
                        item["hill_to_consultant_date"] = cm_date
                elif any(c in cm_from_l for c in ["obmi", "shaker", "ecg", "dar", "egis"]) and "hill" in cm_to_l:
                    if not item["consultant_to_hill_mail"]:
                        item["consultant_to_hill_mail"] = cm_no
                        item["consultant_to_hill_url"] = cm_url
                        item["consultant_to_hill_date"] = cm_date
                elif "hill" in cm_from_l and any(c in cm_to_l for c in ["cscec", "ccc", "contractor", "hassan", "orascom"]):
                    if not item["hill_to_contractor_mail"]:
                        item["hill_to_contractor_mail"] = cm_no
                        item["hill_to_contractor_url"] = cm_url
                        item["hill_to_contractor_date"] = cm_date
                elif "dewan" in cm_from_l:
                    if not item["dewan_mail"]:
                        item["dewan_mail"] = cm_no
                        item["dewan_url"] = cm_url
                        item["dewan_date"] = cm_date
                elif "hill" in cm_from_l and "ccc" in cm_to_l:
                    if not item["ccc_mail"]:
                        item["ccc_mail"] = cm_no
                        item["ccc_url"] = cm_url
                        item["ccc_date"] = cm_date
            
            if item["hill_to_contractor_mail"] or item["ccc_mail"] or (st and st.lower() == "closed"):
                item["status"] = "Response"
            else:
                item["status"] = "Open"
                
            new_items.append(item)
            
        combined_result = existing_data + new_items
        return combined_result
    finally:
        con.close()

def build_rfi_log_workbook(package_name="DP07", existing_wb_path=None):
    """
    Builds or updates an Excel workbook adhering 100% to DP07- RFI-log.xlsx formatting,
    with clickable native hyperlinks to Aconex for all mail cells.
    """
    if existing_wb_path and os.path.exists(existing_wb_path):
        wb = openpyxl.load_workbook(existing_wb_path)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "GEN"
    
    data = extract_rfi_log_data(package_name)
    
    font_title = Font(name="Calibri", size=14, bold=True, color="1F497D")
    font_group = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_sub = Font(name="Calibri", size=9, bold=True, color="000000")
    font_data = Font(name="Calibri", size=9)
    font_link = Font(name="Calibri", size=9, color="0000FF", underline="single")
    font_bold = Font(name="Calibri", size=9, bold=True)
    
    fill_group_acc = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    fill_group_cscec = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    fill_group_hill_obmi = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    fill_group_obmi_hill = PatternFill(start_color="95B3D7", end_color="95B3D7", fill_type="solid")
    fill_group_hill_cscec = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    fill_sub = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    fill_open = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    fill_closed = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    
    thin_border = Border(
        left=Side(style='thin', color='B8CCE4'),
        right=Side(style='thin', color='B8CCE4'),
        top=Side(style='thin', color='B8CCE4'),
        bottom=Side(style='thin', color='B8CCE4')
    )
    
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    
    title_text = f"Request For Information Log For Design Package {package_name}"
    ws.cell(1, 1, title_text).font = font_title
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[3].height = 24
    ws.row_dimensions[4].height = 20
    
    groups = [
        (1, 2, "ACC TO HILL", fill_group_acc),
        (3, 6, "CSCEC to Hill", fill_group_cscec),
        (7, 8, "Hill to Consultant", fill_group_hill_obmi),
        (9, 10, "Consultant to Hill", fill_group_obmi_hill),
        (11, 12, "Hill to Contractor", fill_group_hill_cscec),
        (13, 14, "Dewan to Hill", fill_group_hill_obmi),
        (15, 16, "Hill to CCC", fill_group_hill_cscec),
        (17, 17, "Status", fill_group_cscec)
    ]
    
    for start_col, end_col, title, fill in groups:
        if start_col != end_col:
            ws.merge_cells(start_row=3, start_column=start_col, end_row=3, end_column=end_col)
        c = ws.cell(3, start_col, title)
        c.font = font_group
        c.fill = fill
        c.alignment = align_center
        c.border = thin_border
        
    subheaders = [
        (1, "Mail No"), (2, "Mail No"), (3, "REV"), (4, "RFI No"),
        (5, "Subject"), (6, "Date"), (7, "Mail No"), (8, "Date"),
        (9, "Mail No"), (10, "Date"), (11, "Mail No"), (12, "Date"),
        (13, "Mail No"), (14, "Date"), (15, "Mail No"), (16, "Date"),
        (17, "Open/Closed")
    ]
    
    for col_idx, sub in subheaders:
        c = ws.cell(4, col_idx, sub)
        c.font = font_sub
        c.fill = fill_sub
        c.alignment = align_center
        c.border = thin_border

    current_row = 5
    for item in data:
        ws.row_dimensions[current_row].height = 20
        
        # Col 1: ACC Mail No
        c1 = ws.cell(current_row, 1)
        if item.get("acc_mail"):
            c1.value = item["acc_mail"]
            if item.get("acc_mail_url"):
                c1.hyperlink = item["acc_mail_url"]
                c1.font = font_link
            else:
                c1.font = font_data
        else:
            c1.value = None
            c1.font = font_data
            
        # Col 2: CSCEC Mail No
        c2 = ws.cell(current_row, 2)
        if item.get("cscec_mail"):
            c2.value = item["cscec_mail"]
            if item.get("cscec_mail_url"):
                c2.hyperlink = item["cscec_mail_url"]
                c2.font = font_link
            else:
                c2.font = font_data
        else:
            c2.value = None
            c2.font = font_data
            
        # Col 3: REV
        c3 = ws.cell(current_row, 3, item.get("rev") or 0)
        c3.font = font_data
        
        # Col 4: RFI No
        c4 = ws.cell(current_row, 4, item.get("rfi_no") or "")
        c4.font = font_bold
        
        # Col 5: Subject
        c5 = ws.cell(current_row, 5, item.get("subject") or "")
        c5.font = font_data
        
        # Col 6: Date
        c6 = ws.cell(current_row, 6)
        s_date = item.get("sent_date")
        c6.value = str(s_date)[:10] if s_date else ""
        c6.font = font_data
        
        # Col 7-8: Hill to Consultant
        c7 = ws.cell(current_row, 7)
        if item.get("hill_to_consultant_mail"):
            c7.value = item["hill_to_consultant_mail"]
            if item.get("hill_to_consultant_url"):
                c7.hyperlink = item["hill_to_consultant_url"]
                c7.font = font_link
            else:
                c7.font = font_data
        c8 = ws.cell(current_row, 8)
        dt = item.get("hill_to_consultant_date")
        c8.value = str(dt)[:10] if dt else ""
        c8.font = font_data
        
        # Col 9-10: Consultant to Hill
        c9 = ws.cell(current_row, 9)
        if item.get("consultant_to_hill_mail"):
            c9.value = item["consultant_to_hill_mail"]
            if item.get("consultant_to_hill_url"):
                c9.hyperlink = item["consultant_to_hill_url"]
                c9.font = font_link
            else:
                c9.font = font_data
        c10 = ws.cell(current_row, 10)
        dt = item.get("consultant_to_hill_date")
        c10.value = str(dt)[:10] if dt else ""
        c10.font = font_data
        
        # Col 11-12: Hill to Contractor
        c11 = ws.cell(current_row, 11)
        if item.get("hill_to_contractor_mail"):
            c11.value = item["hill_to_contractor_mail"]
            if item.get("hill_to_contractor_url"):
                c11.hyperlink = item["hill_to_contractor_url"]
                c11.font = font_link
            else:
                c11.font = font_data
        c12 = ws.cell(current_row, 12)
        dt = item.get("hill_to_contractor_date")
        c12.value = str(dt)[:10] if dt else ""
        c12.font = font_data
        
        # Col 13-14: Dewan to Hill
        c13 = ws.cell(current_row, 13)
        if item.get("dewan_mail"):
            c13.value = item["dewan_mail"]
            if item.get("dewan_url"):
                c13.hyperlink = item["dewan_url"]
                c13.font = font_link
            else:
                c13.font = font_data
        c14 = ws.cell(current_row, 14)
        dt = item.get("dewan_date")
        c14.value = str(dt)[:10] if dt else ""
        c14.font = font_data
        
        # Col 15-16: Hill to CCC
        c15 = ws.cell(current_row, 15)
        if item.get("ccc_mail"):
            c15.value = item["ccc_mail"]
            if item.get("ccc_url"):
                c15.hyperlink = item["ccc_url"]
                c15.font = font_link
            else:
                c15.font = font_data
        c16 = ws.cell(current_row, 16)
        dt = item.get("ccc_date")
        c16.value = str(dt)[:10] if dt else ""
        c16.font = font_data
        
        # Col 17: Status
        status_val = item.get("status") or "Open"
        c17 = ws.cell(current_row, 17, status_val)
        c17.font = font_bold
        c17.fill = fill_closed if status_val.lower() == "response" else fill_open
        
        for col_idx in range(1, 18):
            cell = ws.cell(current_row, col_idx)
            cell.border = thin_border
            if col_idx in [1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]:
                cell.alignment = align_center
            else:
                cell.alignment = align_left
                
        current_row += 1

    column_widths = {
        1: 22, 2: 22, 3: 8, 4: 44, 5: 58, 6: 14,
        7: 22, 8: 14, 9: 22, 10: 14, 11: 22, 12: 14,
        13: 22, 14: 14, 15: 22, 16: 14, 17: 15
    }
    for col, width in column_widths.items():
        ws.column_dimensions[get_column_letter(col)].width = width
        
    return wb

def update_rfi_log_file(file_path: str, override_pkg: str = None) -> dict:
    """
    Safely updates an existing RFI log file on disk with latest thread responses,
    new RFIs, and live Aconex hyperlinks without breaking merged header cells.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    pkg = override_pkg or detect_package_from_name_or_content(os.path.basename(file_path))
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        wb = openpyxl.load_workbook(file_path)
        data_sheets = [s for s in wb.sheetnames if 'dash' not in s.lower()]
        target_sheet_name = data_sheets[0] if data_sheets else wb.sheetnames[0]
        ws = wb[target_sheet_name]

        header_row = 4
        for r in range(1, min(10, ws.max_row + 1)):
            row_vals = [str(ws.cell(r, c).value or '').strip().lower() for c in range(1, ws.max_column + 1)]
            if any('mail no' in v or 'rfi no' in v or 'ref' in v for v in row_vals):
                header_row = r
                break

        existing_rfis = set()
        hyperlinks_added = 0
        for r in range(header_row + 1, ws.max_row + 1):
            m_no = ws.cell(r, 1).value
            r_no = ws.cell(r, 2).value or ws.cell(r, 4).value
            if m_no:
                existing_rfis.add(str(m_no).strip().upper())
                c1 = ws.cell(r, 1)
                if not c1.hyperlink:
                    url_match = con.execute("SELECT aconex_url FROM mail_aconex_links WHERE mail_no = ?", [str(m_no).strip()]).fetchone()
                    if url_match and url_match[0]:
                        c1.hyperlink = url_match[0]
                        c1.font = Font(name="Calibri", size=10, color="0000EE", underline="single")
                        hyperlinks_added += 1
            if r_no:
                existing_rfis.add(str(r_no).strip().upper())

        # Extract latest RFIs from DuckDB for this package
        pkg_term = f"%{pkg}%"
        if pkg == "INFRA":
            sql_kw = "(m.subject ILIKE '%3048%' OR m.subject ILIKE '%K03048%' OR m.subject ILIKE '%SW00%' OR m.mail_no ILIKE '%HA-HI-RW-RFI%')"
            kw_args = []
        elif pkg == "MSS":
            sql_kw = "(m.subject ILIKE '%3044%' OR m.subject ILIKE '%K03044%' OR m.subject ILIKE '%MPS%' OR m.mail_no ILIKE '%EERM-RFI%')"
            kw_args = []
        elif pkg == "RO":
            sql_kw = "(m.subject ILIKE '%3045%' OR m.subject ILIKE '%K03045%' OR m.subject ILIKE '%RO%Plant%')"
            kw_args = []
        elif pkg == "STP":
            sql_kw = "(m.subject ILIKE '%3046%' OR m.subject ILIKE '%K03046%' OR m.subject ILIKE '%STP%')"
            kw_args = []
        elif pkg == "AIRPORT":
            sql_kw = "(m.subject ILIKE '%3049%' OR m.subject ILIKE '%K00146%' OR m.subject ILIKE '%Airport%')"
            kw_args = []
        elif pkg == "CANAL":
            sql_kw = "(m.subject ILIKE '%3200%' OR m.subject ILIKE '%K03200%' OR m.subject ILIKE '%Canal%')"
            kw_args = []
        else:
            sql_kw = "(m.subject ILIKE ? OR m.mail_no ILIKE ? OR m.reference_number ILIKE ?)"
            kw_args = [pkg_term, pkg_term, pkg_term]

        q_rfis = con.execute(f"""
            SELECT m.mail_no, COALESCE(m.reference_number, m.mail_no), m.subject, m.sent_date, l.aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE (m.mail_type ILIKE '%Request For Information%' OR m.mail_no LIKE '%-RFI-%')
              AND {sql_kw}
            ORDER BY m.sent_date ASC
        """, kw_args).fetchall()

        appended_count = 0
        cur_row = ws.max_row + 1
        for row in q_rfis:
            m_val, r_val, s_val, dt_val, url_val = row
            m_u = (m_val or '').upper()
            r_u = (r_val or '').upper()
            if (m_u and m_u not in existing_rfis) and (r_u and r_u not in existing_rfis):
                ws.cell(cur_row, 1, m_val)
                ws.cell(cur_row, 2, r_val)
                ws.cell(cur_row, 4, r_val)
                ws.cell(cur_row, 5, s_val)
                if dt_val:
                    ws.cell(cur_row, 6, dt_val.strftime('%Y-%m-%d'))
                if url_val:
                    c = ws.cell(cur_row, 1)
                    c.hyperlink = url_val
                    c.font = Font(name="Calibri", size=10, color="0000EE", underline="single")
                    hyperlinks_added += 1
                existing_rfis.add(m_u)
                appended_count += 1
                cur_row += 1

        wb.save(file_path)
        return {
            "status": "success",
            "package": pkg,
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "total_rfis": ws.max_row - header_row,
            "new_rfis_appended": appended_count,
            "hyperlinks_count": hyperlinks_added
        }
    finally:
        con.close()

def bulk_sync_all_dp_logs(folder_path: str = r"C:\Users\bimst\Downloads\ACONEX\Logs") -> dict:
    """
    Scans folder for all existing RFI log files, updates them in-place safely,
    and returns comprehensive sync statistics.
    """
    os.makedirs(folder_path, exist_ok=True)
    results = []
    
    # Check all excel files matching RFI or DP (including subfolders)
    rfi_files = (
        glob.glob(os.path.join(folder_path, "*RFI*.xlsx")) +
        glob.glob(os.path.join(folder_path, "*DP*.xlsx")) +
        glob.glob(os.path.join(folder_path, "*", "*RFI*.xlsx")) +
        glob.glob(os.path.join(folder_path, "*", "*DP*.xlsx"))
    )
    seen_files = set()
    
    for target_file in rfi_files:
        f_norm = os.path.normpath(target_file)
        if f_norm not in seen_files and os.path.isfile(f_norm) and not os.path.basename(f_norm).startswith("~$"):
            seen_files.add(f_norm)
            pkg = detect_package_from_name_or_content(os.path.basename(f_norm))
            try:
                res = update_rfi_log_file(f_norm, override_pkg=pkg)
                res["action"] = "updated_existing"
                results.append(res)
            except Exception as e:
                print(f"Error updating {f_norm}: {e}")
            
    total_rfis = sum(r.get("total_rfis", 0) for r in results)
    total_new = sum(r.get("new_rfis_appended", 0) for r in results)
    total_links = sum(r.get("hyperlinks_count", 0) for r in results)
    
    return {
        "status": "success",
        "target_folder": folder_path,
        "processed_count": len(results),
        "total_rfis_tracked": total_rfis,
        "total_new_rfis_appended": total_new,
        "total_live_hyperlinks": total_links,
        "packages": results
    }

def upload_and_update_rfi_bytes(file_bytes: bytes, filename: str) -> tuple[bytes, dict]:
    """
    Processes an uploaded workbook in-memory, detects its DP, updates threads/hyperlinks,
    and returns updated workbook bytes and metadata.
    """
    in_buf = io.BytesIO(file_bytes)
    wb = openpyxl.load_workbook(in_buf)
    pkg = detect_package_from_name_or_content(filename, wb)
    
    updated_wb = build_rfi_log_workbook(package_name=pkg)
    out_buf = io.BytesIO()
    updated_wb.save(out_buf)
    out_buf.seek(0)
    
    ws = updated_wb.active
    h_count = sum(1 for r in range(5, ws.max_row + 1) for c in [1, 2, 7, 9, 11, 13, 15] if ws.cell(r, c).hyperlink)
    
    meta = {
        "status": "success",
        "detected_package": pkg,
        "original_filename": filename,
        "total_rfis": ws.max_row - 4,
        "hyperlinks_count": h_count
    }
    return out_buf.getvalue(), meta

if __name__ == "__main__":
    out_dir = r"C:\Users\bimst\Downloads\ACONEX\Exports"
    os.makedirs(out_dir, exist_ok=True)
    bulk_res = bulk_sync_all_dp_logs(out_dir)
    print(f"Bulk sync complete for {bulk_res['processed_count']} packages: {bulk_res['total_live_hyperlinks']} total links.")
