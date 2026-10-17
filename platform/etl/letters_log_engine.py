import os
import re
import glob
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side
import duckdb

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")

# Style definitions matching project logs
FONT_DATA = Font(name="Calibri", size=10)
FONT_BOLD = Font(name="Calibri", size=10, bold=True)
FONT_LINK = Font(name="Calibri", size=10, color="0000EE", underline="single")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
BORDER_THIN = Border(
    left=Side(style='thin', color='E2E8F0'),
    right=Side(style='thin', color='E2E8F0'),
    top=Side(style='thin', color='E2E8F0'),
    bottom=Side(style='thin', color='E2E8F0')
)

SHEET_PACKAGE_RULES = {
    # Wadi Yemm Packages
    "dp01 - basement": {"pkg": "DP01", "keywords": ["basement", "3121", "k03121", "b-01", "bsmt"]},
    "dp01 beasement": {"pkg": "DP01", "keywords": ["basement", "3121", "k03121", "b-01", "bsmt"]},
    "dp01 - superstructure": {"pkg": "DP01", "keywords": ["superstructure", "3180", "s-01"]},
    "dp01 str": {"pkg": "DP01", "keywords": ["superstructure", "3180", "s-01"]},
    "dp02": {"pkg": "DP02", "keywords": ["dp02", "dp2", "3149", "3270", "k03149", "area 2"]},
    "dp02 (sstr)": {"pkg": "DP02", "keywords": ["dp02", "dp2", "3270", "sstr"]},
    "dp03-east": {"pkg": "DP03_EAST", "keywords": ["dp03 east", "dp3 east", "3199", "k03199", "innovo"]},
    "dp03-west": {"pkg": "DP03_WEST", "keywords": ["dp03 west", "dp3 west", "3271", "k03271", "ccc-rowad"]},
    "dp04": {"pkg": "DP04", "keywords": ["dp04", "dp4", "3204", "acc"]},
    "dp05": {"pkg": "DP05", "keywords": ["dp05", "dp5", "3205", "k03205"]},
    "dp06": {"pkg": "DP06", "keywords": ["dp06", "dp6", "3206", "k03206", "hassan allam"]},
    "dp07": {"pkg": "DP07", "keywords": ["dp07", "dp7", "3207", "cscec"]},
    
    # Strategic Projects
    "grand canal": {"pkg": "GRAND_CANAL", "keywords": ["canal", "lagoon", "3200", "k03200"]},
    "west canal": {"pkg": "WEST_CANAL", "keywords": ["west canal", "3107", "k03107"]},
    "infra": {"pkg": "INFRA_EAST", "keywords": ["sw00", "primary infra", "utility", "3048", "k03048"]},
    "mms": {"pkg": "POWER_SUPPLY", "keywords": ["power supply", "substation", "3044", "k03044", "mps", "mms"]},
    "ro": {"pkg": "RO_PLANT", "keywords": ["ro plant", "potable water", "3045", "k03045"]},
    "stp": {"pkg": "STP", "keywords": ["sewage treatment", "stp", "3046", "k03046"]},
    "airport": {"pkg": "AIRPORT", "keywords": ["airport", "air port", "3049", "k00146"]}
}


def build_response_index(con, is_incoming: bool):
    """
    Builds a lightning-fast in-memory index of potential response letters.
    For Incoming letters to Hill -> Preloads Outbound responses from Hill.
    For Outgoing letters from Hill -> Preloads Inbound responses from Contractors.
    """
    direction_filter = "(m.from_organization ILIKE '%Hill%' OR m.is_outbound_from_hill)" if is_incoming else "(m.to_organization ILIKE '%Hill%' OR m.is_inbound_to_hill)"
    
    rows = con.execute(f"""
        SELECT m.mail_no, COALESCE(m.reference_number, ''), COALESCE(m.subject, ''), m.sent_date, l.aconex_url
        FROM fact_mail m
        LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
        WHERE {direction_filter}
    """).fetchall()

    lookup_by_ref = {}
    lookup_by_kw = {}

    for m_no, r_no, subj, dt, url in rows:
        entry = (m_no, r_no, dt, url)
        if r_no and len(r_no) >= 4:
            lookup_by_ref[r_no.strip().upper()] = entry
        if m_no:
            lookup_by_ref[m_no.strip().upper()] = entry

        # Extract letter numbers like CCCEGY-LETTER-000001 or REH.08.25.3149...
        for word in (subj + ' ' + r_no).split():
            clean_w = word.strip(',:;()[]"\'').upper()
            if ('LETTER' in clean_w or '-LT-' in clean_w or '-FL-' in clean_w or '3149' in clean_w or '3199' in clean_w) and len(clean_w) >= 6:
                if clean_w not in lookup_by_kw:
                    lookup_by_kw[clean_w] = entry

    return lookup_by_ref, lookup_by_kw


def get_mail_aconex_urls(con, mail_numbers):
    """Batch resolves live Aconex direct URLs for mail numbers."""
    if not mail_numbers:
        return {}
    clean = [str(m).strip() for m in mail_numbers if m and isinstance(m, str) and len(m) >= 4]
    if not clean:
        return {}
    res = {}
    chunk_size = 500
    for i in range(0, len(clean), chunk_size):
        chunk = clean[i:i + chunk_size]
        placeholders = ','.join(['?'] * len(chunk))
        q = f"SELECT mail_no, aconex_url FROM mail_aconex_links WHERE mail_no IN ({placeholders})"
        for m_no, url in con.execute(q, chunk).fetchall():
            if url:
                res[m_no.strip().upper()] = url
    return res


def sync_letters_sheet(con, ws, resp_index, is_incoming=True):
    """
    Synchronizes an individual Letter log sheet in-place using O(1) in-memory index:
    1. Finds header row and maps columns.
    2. Updates status and response dates for existing letters that received new responses.
    3. Adds direct Aconex hyperlinks to existing rows.
    4. Appends newly issued letters from Aconex at the bottom.
    """
    sheet_name_clean = ws.title.strip().lower()
    if 'dash' in sheet_name_clean:
        return {"updated_existing": 0, "appended_new": 0, "hyperlinks_added": 0}

    # Find sheet rule
    matched_rule = None
    for rule_name, rule_data in SHEET_PACKAGE_RULES.items():
        if rule_name in sheet_name_clean or sheet_name_clean in rule_name:
            matched_rule = rule_data
            break

    # Locate header row (search first 15 rows)
    header_row = None
    for r in range(1, min(15, ws.max_row + 1)):
        row_vals = [str(ws.cell(r, c).value or '').strip().lower() for c in range(1, ws.max_column + 1)]
        if any('aconex mail' in v or 'mail no' in v for v in row_vals):
            header_row = r
            break

    if not header_row:
        return {"updated_existing": 0, "appended_new": 0, "hyperlinks_added": 0}

    # Map column headers
    col_map = {}
    for c in range(1, ws.max_column + 1):
        val = str(ws.cell(header_row, c).value or '').strip().lower()
        if 'mail no' in val or 'aconex' in val:
            col_map['mail_no'] = c
        elif 'corresp' in val or 'ref' in val:
            col_map['ref_no'] = c
        elif 'subject' in val:
            col_map['subject'] = c
        elif 'received' in val or ('date' in val and 'sent' not in val and 'resp' not in val and 'target' not in val):
            col_map['date'] = c
        elif 'date sent' in val:
            col_map['date'] = c
        elif 'target' in val:
            col_map['target_date'] = c
        elif val == 'from' or 'from' in val:
            col_map['from'] = c
        elif val == 'to' or 'to' in val:
            col_map['to'] = c
        elif 'type' in val:
            col_map['type'] = c
        elif 'status' in val and 'due' not in val:
            col_map['status'] = c
        elif 'responsibility' in val:
            col_map['responsibility'] = c
        elif 'due status' in val:
            col_map['due_status'] = c
        elif 'date respond' in val or ('date' in val and 'resp' in val):
            col_map['resp_date'] = c
        elif 'response ref' in val or ('response' in val and 'date' not in val):
            col_map['resp_ref'] = c
        elif 'priority' in val:
            col_map['priority'] = c
        elif 'notes' in val:
            col_map['notes'] = c

    mail_col = col_map.get('mail_no', 1)
    ref_col = col_map.get('ref_no', 2)
    subj_col = col_map.get('subject', 3)
    date_col = col_map.get('date', 4)
    target_date_col = col_map.get('target_date')
    from_col = col_map.get('from', 6)
    to_col = col_map.get('to', 7)
    type_col = col_map.get('type', 8)
    status_col = col_map.get('status', 9)
    due_status_col = col_map.get('due_status')
    resp_date_col = col_map.get('resp_date', 12)
    resp_ref_col = col_map.get('resp_ref', 13)

    lookup_by_ref, lookup_by_kw = resp_index

    # 1. Inspect existing rows
    existing_mails = set()
    mails_to_check = []
    
    for r in range(header_row + 1, ws.max_row + 1):
        m_val = str(ws.cell(r, mail_col).value or '').strip()
        ref_val = str(ws.cell(r, ref_col).value or '').strip() if ref_col else ''
        if m_val and m_val != 'N/A':
            existing_mails.add(m_val.upper())
            mails_to_check.append((r, m_val, ref_val))

    # Resolve URLs for existing mail numbers
    all_needed_nos = [m[1] for m in mails_to_check]
    url_map = get_mail_aconex_urls(con, all_needed_nos)

    updated_existing = 0
    hyperlinks_added = 0

    for r, m_no, ref_no in mails_to_check:
        cell_mail = ws.cell(r, mail_col)
        m_upper = m_no.upper()
        if not cell_mail.hyperlink and m_upper in url_map:
            cell_mail.hyperlink = url_map[m_upper]
            cell_mail.font = FONT_LINK
            hyperlinks_added += 1

        cur_status = str(ws.cell(r, status_col).value or '').strip().upper() if status_col else ''
        cur_resp_date = ws.cell(r, resp_date_col).value if resp_date_col else None

        # Check for response if open or missing response date
        if cur_status not in ['CLS', 'CLOSED', 'NAR'] or not cur_resp_date:
            resp_match = lookup_by_ref.get(m_upper) or lookup_by_ref.get(ref_no.upper()) or lookup_by_kw.get(m_upper) or lookup_by_kw.get(ref_no.upper())
            if resp_match and resp_match[0] != m_no:
                resp_no, r_ref, r_date, r_url = resp_match
                if status_col:
                    ws.cell(r, status_col).value = 'CLS'
                if resp_date_col and r_date:
                    ws.cell(r, resp_date_col).value = r_date.strftime('%Y-%m-%d')
                if resp_ref_col:
                    resp_display = r_ref if r_ref and r_ref != 'N/A' and len(r_ref) >= 5 else resp_no
                    c_resp = ws.cell(r, resp_ref_col)
                    c_resp.value = resp_display
                    if r_url:
                        c_resp.hyperlink = r_url
                        c_resp.font = FONT_LINK
                        hyperlinks_added += 1
                if due_status_col:
                    ws.cell(r, due_status_col).value = 'Closed'
                updated_existing += 1

    # 2. Append newly issued letters in Aconex for this sheet
    appended_new = 0
    if matched_rule:
        kw_conditions = []
        kw_params = []
        for kw in matched_rule["keywords"]:
            kw_conditions.append("m.subject ILIKE ? OR m.reference_number ILIKE ? OR m.mail_no ILIKE ?")
            kw_params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
        
        kw_sql = " OR ".join(kw_conditions)
        direction_sql = "(m.to_organization ILIKE '%Hill%' OR m.is_inbound_to_hill)" if is_incoming else "(m.from_organization ILIKE '%Hill%' OR m.is_outbound_from_hill)"
        
        query_new = f"""
            SELECT m.mail_no, m.reference_number, m.subject, m.sent_date, m.from_organization, m.to_organization, m.mail_type, m.status, l.aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE m.mail_type ILIKE '%Letter%'
              AND {direction_sql}
              AND ({kw_sql})
            ORDER BY m.sent_date ASC
        """
        new_letters = con.execute(query_new, kw_params).fetchall()
        
        cur_row = ws.max_row + 1
        for row in new_letters:
            nl_mail_no, nl_ref_no, nl_subj, nl_date, nl_from, nl_to, nl_type, nl_stat, nl_url = row
            if nl_mail_no and nl_mail_no.upper() not in existing_mails:
                # Add new row
                c_m = ws.cell(cur_row, mail_col, nl_mail_no)
                c_m.font = FONT_BOLD
                c_m.alignment = ALIGN_CENTER
                c_m.border = BORDER_THIN
                if nl_url:
                    c_m.hyperlink = nl_url
                    c_m.font = FONT_LINK
                    hyperlinks_added += 1

                if ref_col:
                    c_ref = ws.cell(cur_row, ref_col, nl_ref_no or nl_mail_no)
                    c_ref.font = FONT_DATA
                    c_ref.border = BORDER_THIN

                if subj_col:
                    c_sub = ws.cell(cur_row, subj_col, nl_subj)
                    c_sub.font = FONT_DATA
                    c_sub.border = BORDER_THIN

                if date_col:
                    c_dt = ws.cell(cur_row, date_col, nl_date.strftime('%Y-%m-%d') if nl_date else '')
                    c_dt.alignment = ALIGN_CENTER
                    c_dt.font = FONT_DATA
                    c_dt.border = BORDER_THIN

                if target_date_col and nl_date:
                    tgt = nl_date + timedelta(days=14)
                    c_tgt = ws.cell(cur_row, target_date_col, tgt.strftime('%Y-%m-%d'))
                    c_tgt.alignment = ALIGN_CENTER
                    c_tgt.font = FONT_DATA
                    c_tgt.border = BORDER_THIN

                if from_col:
                    c_from = ws.cell(cur_row, from_col, nl_from or '')
                    c_from.font = FONT_DATA
                    c_from.border = BORDER_THIN

                if to_col:
                    c_to = ws.cell(cur_row, to_col, nl_to or '')
                    c_to.font = FONT_DATA
                    c_to.border = BORDER_THIN

                if type_col:
                    c_type = ws.cell(cur_row, type_col, nl_type or 'Letter')
                    c_type.font = FONT_DATA
                    c_type.border = BORDER_THIN

                # Check if already responded
                nl_upper = nl_mail_no.upper()
                nl_ref_upper = (nl_ref_no or '').upper()
                resp_match = lookup_by_ref.get(nl_upper) or lookup_by_ref.get(nl_ref_upper) or lookup_by_kw.get(nl_upper)
                if resp_match and resp_match[0] != nl_mail_no:
                    if status_col:
                        ws.cell(cur_row, status_col, 'CLS').border = BORDER_THIN
                    if resp_date_col and resp_match[2]:
                        c_rd = ws.cell(cur_row, resp_date_col, resp_match[2].strftime('%Y-%m-%d'))
                        c_rd.alignment = ALIGN_CENTER
                        c_rd.border = BORDER_THIN
                    if resp_ref_col:
                        resp_display = resp_match[1] if resp_match[1] and len(resp_match[1]) >= 5 else resp_match[0]
                        c_rr = ws.cell(cur_row, resp_ref_col, resp_display)
                        c_rr.border = BORDER_THIN
                        if resp_match[3]:
                            c_rr.hyperlink = resp_match[3]
                            c_rr.font = FONT_LINK
                    if due_status_col:
                        ws.cell(cur_row, due_status_col, 'Closed').border = BORDER_THIN
                else:
                    if status_col:
                        ws.cell(cur_row, status_col, 'OPN').border = BORDER_THIN
                    if due_status_col:
                        ws.cell(cur_row, due_status_col, 'Pending Review').border = BORDER_THIN

                existing_mails.add(nl_upper)
                appended_new += 1
                cur_row += 1

    return {
        "updated_existing": updated_existing,
        "appended_new": appended_new,
        "hyperlinks_added": hyperlinks_added
    }


def sync_letters_log_file(file_path: str) -> dict:
    """
    Synchronizes an existing Letters Log workbook in-place:
    Preserves all sheets, formulas, custom notes, and formatting.
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    fname = os.path.basename(file_path)
    is_incoming = 'incoming' in fname.lower()
    
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        resp_index = build_response_index(con, is_incoming=is_incoming)
        wb = openpyxl.load_workbook(file_path)
        stats = {
            "filename": fname,
            "is_incoming": is_incoming,
            "total_sheets": len(wb.sheetnames),
            "updated_existing_total": 0,
            "appended_new_total": 0,
            "hyperlinks_added_total": 0,
            "sheet_details": {}
        }

        for sname in wb.sheetnames:
            ws = wb[sname]
            s_res = sync_letters_sheet(con, ws, resp_index, is_incoming=is_incoming)
            if s_res["updated_existing"] > 0 or s_res["appended_new"] > 0 or s_res["hyperlinks_added"] > 0:
                stats["sheet_details"][sname] = s_res
                stats["updated_existing_total"] += s_res["updated_existing"]
                stats["appended_new_total"] += s_res["appended_new"]
                stats["hyperlinks_added_total"] += s_res["hyperlinks_added"]

        wb.save(file_path)
        stats["status"] = "success"
        stats["message"] = f"Updated {fname} in-place ({stats['updated_existing_total']} responses updated, {stats['appended_new_total']} new letters added, {stats['hyperlinks_added_total']} hyperlinks active)"
        return stats
    finally:
        con.close()


def bulk_sync_all_letters_logs(base_dir: str = r"C:\Users\bimst\Downloads\ACONEX\Logs") -> dict:
    """
    Finds and updates all 4 Letters Log files in-place:
    - Wadi Yemm Incoming Letters
    - Wadi Yemm Outgoing Letters
    - Strategic Projects Incoming Letters
    - Strategic Projects Outgoing Letters
    """
    results = []
    patterns = [
        os.path.join(base_dir, "*letter*.xlsx"),
        os.path.join(base_dir, "*", "*letter*.xlsx"),
        os.path.join(base_dir, "*letters*.xlsx"),
        os.path.join(base_dir, "*", "*letters*.xlsx"),
    ]
    seen_files = set()
    for pat in patterns:
        for f in glob.glob(pat):
            f_norm = os.path.normpath(f)
            if f_norm not in seen_files and os.path.isfile(f_norm) and not os.path.basename(f_norm).startswith("~$"):
                seen_files.add(f_norm)
                res = sync_letters_log_file(f_norm)
                results.append(res)

    total_upd = sum(r.get("updated_existing_total", 0) for r in results)
    total_app = sum(r.get("appended_new_total", 0) for r in results)
    total_links = sum(r.get("hyperlinks_added_total", 0) for r in results)

    return {
        "status": "success",
        "total_files_synced": len(results),
        "total_responses_updated": total_upd,
        "total_new_letters_appended": total_app,
        "total_hyperlinks_added": total_links,
        "files": results
    }
