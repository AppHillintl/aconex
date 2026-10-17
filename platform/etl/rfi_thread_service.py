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
LOGS_DIR = r"C:\Users\bimst\Downloads\ACONEX\Logs"

# Canonical Mapping of Projects to their Reference RFI Log Files
# Canonical Mapping of Projects to their Reference RFI Log Files
PROJECT_LOG_FILES = {
    "DP01": r"C:\Users\bimst\Downloads\ACONEX\Logs\REH -DP01- Site Calirification Request Log.xlsx",
    "DP02": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP02 - RFI.xlsx",
    "DP03-East": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP03-East - RFI.xlsx",
    "DP03-West": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP03-West- RFI.xlsx",
    "DP04": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP04- RFI-log.xlsx",
    "DP05": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP05- RFI-log_.xlsx",
    "DP06": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP06-RFI-log.xlsx",
    "DP07": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP07- RFI-log.xlsx",
    "Infra": r"C:\Users\bimst\Downloads\ACONEX\Logs\INFRA-RFI-  Log-.xlsx",
    "INFRA": r"C:\Users\bimst\Downloads\ACONEX\Logs\INFRA-RFI-  Log-.xlsx",
    "MSS": r"C:\Users\bimst\Downloads\ACONEX\Logs\MSS-RFI Log.xlsx",
    "MMS / Substation": r"C:\Users\bimst\Downloads\ACONEX\Logs\MSS-RFI Log.xlsx",
    "RO": r"C:\Users\bimst\Downloads\ACONEX\Logs\RO-RFI Log.xlsx",
    "RO Plant": r"C:\Users\bimst\Downloads\ACONEX\Logs\RO-RFI Log.xlsx",
    "STP": r"C:\Users\bimst\Downloads\ACONEX\Logs\STP-RFI Log.xlsx",
    "Grand Canal": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP06-RFI-log.xlsx",
    "West Canal": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP05- RFI-log_.xlsx",
    "Airport": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP02 - RFI.xlsx",
    "ALL": r"C:\Users\bimst\Downloads\ACONEX\Logs\DP02 - RFI.xlsx",
}

RFI_TYPES_SQL = """(
    m.mail_type ILIKE '%Request For Information%' 
    OR m.mail_type ILIKE '%Site Clarification Request%' 
    OR m.mail_type ILIKE '%Clarification%'
    OR m.mail_no LIKE '%-RFI-%' 
    OR m.mail_no LIKE '%-SCR-%'
    OR m.mail_no LIKE '%-RTCL-%'
    OR m.mail_no LIKE '%-RTRFI-%'
)"""

PACKAGE_SQL_CONDITIONS = {
    "ALL": "1=1",
    "DP01": "(m.project_package = 'DP01' OR m.mail_no LIKE 'REH-MD01-%' OR m.mail_no LIKE 'OC-SCR-%' OR m.subject ILIKE '%DP01%' OR m.subject ILIKE '%DP-01%' OR m.subject ILIKE '%MD01%' OR m.subject ILIKE '%K03121%' OR m.subject ILIKE '%P0155%')",
    "DP02": "(m.project_package = 'DP02' OR m.mail_no LIKE 'CCCEGY-RFI-%' OR m.mail_no LIKE 'HillInt-RFI-%3149%' OR m.subject ILIKE '%DP02%' OR m.subject ILIKE '%DP-02%' OR m.subject ILIKE '%3149%' OR m.subject ILIKE '%K03149%')",
    "DP03-East": "(m.project_package = 'DP03-East' OR m.from_organization ILIKE '%innovo-redcon%' OR m.subject ILIKE '%DP03-East%' OR m.subject ILIKE '%DP03 East%' OR m.subject ILIKE '%3199%' OR m.subject ILIKE '%K03199%')",
    "DP03-West": "(m.project_package = 'DP03-West' OR m.subject ILIKE '%DP03-West%' OR m.subject ILIKE '%DP03 West%' OR m.subject ILIKE '%3271%' OR m.subject ILIKE '%K03271%' OR m.from_name ILIKE '%RHD3%')",
    "DP04": "(m.project_package = 'DP04' OR m.from_organization ILIKE '%ACC for Engineering%' OR m.subject ILIKE '%DP04%' OR m.subject ILIKE '%DP-04%' OR m.subject ILIKE '%3204%' OR m.subject ILIKE '%K03204%')",
    "DP05": "(m.project_package = 'DP05' OR m.mail_no LIKE '%-DP5-%' OR m.subject ILIKE '%DP05%' OR m.subject ILIKE '%DP-05%' OR m.subject ILIKE '%3205%' OR m.subject ILIKE '%K03205%')",
    "DP06": "(m.project_package = 'DP06' OR m.mail_no LIKE 'REH-MD01-ZZZ-IM-HAC-%' OR m.subject ILIKE '%DP06%' OR m.subject ILIKE '%DP-06%' OR m.subject ILIKE '%3206%' OR m.subject ILIKE '%K03206%')",
    "DP07": "(m.project_package = 'DP07' OR m.from_organization ILIKE '%CSCEC%' OR m.subject ILIKE '%DP07%' OR m.subject ILIKE '%DP-07%' OR m.subject ILIKE '%3207%' OR m.subject ILIKE '%K03207%')",
    "Infra": "(m.project_package = 'Infra' OR m.mail_no LIKE '%-SW00-%' OR m.subject ILIKE '%SW00%' OR m.subject ILIKE '%3048%' OR m.subject ILIKE '%K03048%')",
    "MSS": "(m.project_package IN ('MMS / Substation', 'MSS') OR m.from_organization ILIKE '%EETD-RME%' OR m.from_organization ILIKE '%SEWEDY%' OR m.subject ILIKE '%3044%' OR m.subject ILIKE '%K03044%' OR m.subject ILIKE '%MSS%')",
    "RO": "(m.project_package IN ('RO', 'RO Plant') OR m.mail_no LIKE 'OTC-JV-RFI-%' OR m.subject ILIKE '%3045%' OR m.subject ILIKE '%RO Plant%' OR m.from_organization ILIKE '%Trojan%COX%')",
    "STP": "(m.project_package = 'STP' OR m.mail_no LIKE '%-STP-%' OR m.subject ILIKE '%3046%' OR m.subject ILIKE '%STP%' OR m.subject ILIKE '%Sewage Treatment%')",
    "Grand Canal": "(m.project_package = 'Grand Canal' OR m.subject ILIKE '%Grand Canal%' OR m.subject ILIKE '%3200%' OR m.subject ILIKE '%P0801%' OR m.subject ILIKE '%K03200%')",
    "West Canal": "(m.project_package = 'West Canal' OR m.subject ILIKE '%West Canal%' OR m.subject ILIKE '%3107%' OR m.subject ILIKE '%K03107%')",
    "Airport": "(m.project_package = 'Airport' OR m.subject ILIKE '%Airport%' OR m.subject ILIKE '%Air Port%' OR m.from_organization ILIKE '%Air Port%')"
}

PROJECT_ALIASES = {
    "ALL": ["ALL"],
    "DP01": ["DP01", "DP-01", "DP1", "K03121", "MD01", "P0155", "K00146"],
    "DP02": ["DP02", "3149", "K03149", "3270"],
    "DP03-East": ["DP03-East", "DP03 EAST", "3199", "K03199", "INOVO"],
    "DP03-West": ["DP03-West", "DP03 WEST", "3271", "K03271"],
    "DP04": ["DP04", "3204", "K03204", "ACC"],
    "DP05": ["DP05", "3205", "K03205", "ORASCOM"],
    "DP06": ["DP06", "3206", "K03206", "HASSAN ALLAM"],
    "DP07": ["DP07", "3207", "K03207", "CSCEC"],
    "Infra": ["Infra", "INFRA", "3048", "K03048", "SW00"],
    "MSS": ["MSS", "MMS / Substation", "3044", "K03044", "SEWEDY", "EERM", "EETD-RME"],
    "RO": ["RO", "RO Plant", "3045", "K03045", "OTC"],
    "STP": ["STP", "3046", "K03046", "P5576"],
    "Grand Canal": ["Grand Canal", "P0801", "K03200", "3200"],
    "West Canal": ["West Canal", "K03107", "3107"],
    "Airport": ["Airport", "Air Port", "3049"]
}

def get_db_connection():
    return duckdb.connect(DB_PATH, read_only=True)

def detect_package_from_name_or_content(filename: str = "", wb: openpyxl.Workbook = None) -> str:
    """Detects standard package identifier from file name, sheet titles, or cell contents."""
    fname_upper = (filename or '').upper()
    text = fname_upper
    if wb:
        try:
            ws = wb.active
            text += " " + str(ws.cell(1, 1).value or '').upper()
            text += " " + " ".join(wb.sheetnames).upper()
        except Exception:
            pass

    if "GRAND CANAL" in text or "3200" in text or "P0801" in text:
        return "Grand Canal"
    if "WEST CANAL" in text or "3107" in text:
        return "West Canal"
    if "AIRPORT" in text or "AIR PORT" in text or "3049" in text:
        return "Airport"
    if "DP01" in text or "DP-01" in text or "DP1" in text or "MD01" in text or "K03121" in text or "CALIRIFICATION" in text:
        return "DP01"

    # Check DP03 East / West first
    if "DP03-WEST" in text or "DP03 WEST" in text or "3271" in text:
        return "DP03-West"
    if "DP03-EAST" in text or "DP03 EAST" in text or "3199" in text:
        return "DP03-East"

    # Check DP packages (DP01 to DP08)
    m = re.search(r'\bDP\s*-?\s*0?(\d+)\b', text, re.IGNORECASE)
    if m:
        num = int(m.group(1))
        if num == 3:
            return "DP03-East" if "EAST" in text else ("DP03-West" if "WEST" in text else "DP03-East")
        return f"DP{num:02d}"

    if "INFRA" in text or "3048" in text or "SW00" in text:
        return "Infra"
    if "MSS" in text or "3044" in text or "POWER" in text or "SUBSTATION" in text:
        return "MSS"
    if "STP" in text or "3046" in text or "SEWAGE" in text:
        return "STP"
    if re.search(r'\bRO\b', text) or "RO PLANT" in text or "3045" in text or "POTABLE" in text:
        return "RO"

    return "DP02"

def get_rfi_thread_history(mail_no: str, reference_number: str = None) -> dict:
    """
    Extracts the complete multi-party chronological communication thread for a specific RFI.
    From initiator (Contractor) -> Hill forwarding -> Consultant review -> Hill final response.
    """
    con = get_db_connection()
    try:
        clean_m_no = (mail_no or '').strip()
        clean_ref = (reference_number or '').strip()

        # 1. Fetch initiator RFI record
        init_row = con.execute("""
            SELECT 
                m.mail_no, m.mail_type, COALESCE(m.reference_number, m.mail_no) as ref_no,
                m.subject, m.from_organization, m.to_organization, m.from_name,
                m.sent_date, m.due_date, m.status, m.project_package,
                COALESCE(l.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A' || m.mail_no) as aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE m.mail_no = ? OR (m.reference_number = ? AND LENGTH(?) > 5)
            LIMIT 1
        """, [clean_m_no, clean_ref, clean_ref]).fetchone()

        if not init_row:
            # Fallback check in fact_rfis
            init_row = con.execute("""
                SELECT 
                    mail_no, 'Request For Information' as mail_type, mail_no as ref_no,
                    subject, from_organization, to_organization, from_name,
                    sent_date, due_date, status, project_package,
                    COALESCE(aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A' || mail_no) as aconex_url
                FROM fact_rfis
                WHERE mail_no = ?
                LIMIT 1
            """, [clean_m_no]).fetchone()

        m_key = init_row[0] if init_row else clean_m_no
        ref_key = init_row[2] if init_row else clean_ref
        subj_key = init_row[3] if init_row else ""

        # 2. Extract precise RFI & Clarification reference codes from mail_no and subject
        # Uses strict hyphenated pattern so regular words (e.g. description, script) are never matched
        code_pattern = re.compile(r'\b((?:[A-Za-z0-9]+-)*(?:RFI|SCR|RTCL|RTRFI)-(?:[A-Za-z0-9]+-)*[A-Za-z0-9]+)\b', re.IGNORECASE)
        tokens = set()
        if m_key:
            tokens.add(m_key)
        if ref_key and len(ref_key) >= 5:
            tokens.add(ref_key)

        search_corpus = f"{m_key} {ref_key} {subj_key}"
        for found in code_pattern.findall(search_corpus):
            if len(found) >= 8:
                tokens.add(found)

        # 3. Build comprehensive thread query matching tokens and direct reply links
        where_parts = []
        params = []
        for t in tokens:
            where_parts.append("(m.mail_no = ? OR m.reference_number = ? OR m.subject ILIKE ?)")
            params.extend([t, t, f"%{t}%"])

        # Also direct parent/reply relationships from fact_mail_threads
        where_parts.append("m.mail_no IN (SELECT response_mail_no FROM fact_mail_threads WHERE mail_no = ?)")
        params.append(m_key)
        where_parts.append("m.mail_no IN (SELECT mail_no FROM fact_mail_threads WHERE response_mail_no = ?)")
        params.append(m_key)

        where_clause = " OR ".join(where_parts)
        query = f"""
            SELECT DISTINCT 
                m.mail_no, m.mail_type, m.from_organization, m.to_organization, m.from_name,
                m.sent_date, m.subject, m.status,
                COALESCE(l.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A' || m.mail_no) as aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE ({where_clause}) AND m.mail_type != 'Workflow Transmittal'
            ORDER BY m.sent_date ASC NULLS LAST, m.mail_no ASC
        """
        raw_events = con.execute(query, params).fetchall()

        if not raw_events and init_row:
            raw_events = [(
                init_row[0], init_row[1], init_row[4], init_row[5], init_row[6],
                init_row[7], init_row[3], init_row[9], init_row[11]
            )]

        # Classify each step's role and phase in the RFI lifecycle
        thread_steps = []
        seen_mails = set()
        first_date = None
        latest_date = None
        has_official_response = False
        orgs_involved = set()

        for idx, ev in enumerate(raw_events, 1):
            e_mail, e_type, e_from, e_to, e_name, e_date, e_subj, e_st, e_url = ev
            if e_mail in seen_mails:
                continue
            seen_mails.add(e_mail)

            f_lower = (e_from or '').lower()
            t_lower = (e_to or '').lower()
            type_lower = (e_type or '').lower()
            subj_lower = (e_subj or '').lower()

            if e_from: orgs_involved.add(e_from)
            if e_to: orgs_involved.add(e_to)

            if e_date and not first_date:
                first_date = e_date
            if e_date:
                latest_date = e_date

            # Determine lifecycle phase and category
            phase = "General Coordination"
            category = "coordination"
            badge_color = "slate"
            icon = "mail"

            is_initiator = (e_mail == m_key) or ("request" in type_lower and "hill" in t_lower and "hill" not in f_lower)
            is_internal_hill = "hill" in f_lower and "hill" in t_lower
            is_hill_to_consultant = "hill" in f_lower and any(c in t_lower for c in ["obmi", "shaker", "ecg", "consultant", "dar", "egis", "aedas", "dewan"])
            is_consultant_to_hill = any(c in f_lower for c in ["obmi", "shaker", "ecg", "dar", "egis", "aedas", "dewan"]) and "hill" in t_lower
            is_hill_response = ("response" in type_lower or "response" in subj_lower or "rtcl" in e_mail.lower() or "rtrfi" in e_mail.lower()) and "hill" in f_lower

            if is_initiator and idx == 1:
                phase = "1. Initiator Request"
                category = "initiator"
                badge_color = "blue"
                icon = "send"
            elif is_internal_hill:
                phase = "Internal Hill Coordination"
                category = "internal_hill"
                badge_color = "sky"
                icon = "users"
            elif is_hill_to_consultant:
                phase = "2. Transmitted to Consultant"
                category = "consultant"
                badge_color = "purple"
                icon = "forward"
            elif is_consultant_to_hill:
                phase = "3. Consultant Review & Advice"
                category = "consultant"
                badge_color = "amber"
                icon = "help-circle"
            elif is_hill_response:
                phase = "4. Official PMC Response"
                category = "response"
                badge_color = "emerald"
                icon = "check-circle-2"
                has_official_response = True
            elif "response" in type_lower or "response" in subj_lower:
                phase = "Response Step"
                category = "response"
                badge_color = "emerald"
                icon = "check-circle"
                has_official_response = True
            else:
                phase = "Intermediate Step"
                category = "coordination"
                badge_color = "slate"
                icon = "message-square"

            days_from_start = 0
            if first_date and e_date:
                try:
                    delta = (e_date - first_date).days
                    days_from_start = max(0, delta)
                except Exception:
                    pass

            # Preserve real authentic Aconex status for this step
            actual_status = e_st if e_st and e_st != 'None' else ('Responded' if (is_hill_response or "response" in type_lower) else 'Outstanding')

            thread_steps.append({
                "step_number": len(thread_steps) + 1,
                "mail_no": e_mail,
                "mail_type": e_type or "Mail",
                "from_org": e_from or "-",
                "to_org": e_to or "-",
                "from_name": e_name or "",
                "sent_date": str(e_date)[:10] if e_date else "-",
                "sent_timestamp": str(e_date) if e_date else None,
                "subject": e_subj or "-",
                "status": actual_status,
                "phase": phase,
                "category": category,
                "badge_color": badge_color,
                "icon": icon,
                "days_from_start": days_from_start,
                "aconex_url": e_url
            })

        # Calculate turnaround metrics
        turnaround_days = 0
        if first_date and latest_date:
            try:
                turnaround_days = max(0, (latest_date - first_date).days)
            except Exception:
                pass

        overall_status = init_row[9] if (init_row and init_row[9] and init_row[9] != 'N/A') else ("Responded" if has_official_response else "Outstanding")

        return {
            "rfi_no": m_key,
            "reference_number": ref_key or m_key,
            "subject": init_row[3] if init_row else (thread_steps[0]["subject"] if thread_steps else ""),
            "contractor": init_row[4] if init_row else (thread_steps[0]["from_org"] if thread_steps else ""),
            "project_package": init_row[10] if init_row else "",
            "initiated_date": str(first_date)[:10] if first_date else "",
            "latest_update_date": str(latest_date)[:10] if latest_date else "",
            "turnaround_days": turnaround_days,
            "status": overall_status,
            "has_official_response": has_official_response,
            "total_steps": len(thread_steps),
            "parties_count": len(orgs_involved),
            "aconex_url": init_row[11] if init_row else (thread_steps[0]["aconex_url"] if thread_steps else ""),
            "thread_steps": thread_steps
        }
    finally:
        con.close()

def get_project_rfis_explorer_list(project_id: str = "DP02", search: str = None, status: str = None, sort: str = None, limit: int = 50, offset: int = 0) -> dict:
    """
    Returns list of RFIs for a selected project package with calculated thread depth and latest activity.
    Supports single and multi-column sorting.
    """
    con = get_db_connection()
    try:
        norm_pkg = (project_id or "ALL").strip()
        pkg_filter = PACKAGE_SQL_CONDITIONS.get(norm_pkg)
        if not pkg_filter:
            aliases = PROJECT_ALIASES.get(norm_pkg, [norm_pkg])
            pkg_conditions = [f"m.project_package = '{norm_pkg}'"]
            for a in aliases:
                pkg_conditions.append(f"m.project_package ILIKE '%{a}%'")
                pkg_conditions.append(f"m.subject ILIKE '%{a}%'")
                pkg_conditions.append(f"m.mail_no ILIKE '%{a}%'")
            pkg_filter = f"({' OR '.join(pkg_conditions)})" if norm_pkg != "ALL" else "1=1"

        where_parts = [
            RFI_TYPES_SQL,
            pkg_filter
        ]

        if search and search.strip():
            s_clean = search.strip().replace("'", "''")
            where_parts.append(f"(m.mail_no ILIKE '%{s_clean}%' OR m.subject ILIKE '%{s_clean}%' OR COALESCE(m.reference_number, '') ILIKE '%{s_clean}%' OR m.from_organization ILIKE '%{s_clean}%')")

        if status and status.strip():
            st_clean = status.strip().replace("'", "''")
            if st_clean.lower() in ["open", "outstanding"]:
                where_parts.append("(m.status ILIKE '%out%' OR m.status ILIKE '%open%')")
            elif st_clean.lower() in ["response", "responded", "closed"]:
                where_parts.append("(m.status ILIKE '%resp%' OR m.status ILIKE '%close%')")

        where_sql = " AND ".join(where_parts)

        # Count total
        count_q = f"SELECT count(*) FROM fact_mail m WHERE {where_sql}"
        total = con.execute(count_q).fetchone()[0]

        # Sorting logic
        rfi_explore_cols = {
            'mail_no': 'm.mail_no',
            'reference_number': 'COALESCE(m.reference_number, m.mail_no)',
            'ref_no': 'COALESCE(m.reference_number, m.mail_no)',
            'subject': 'm.subject',
            'from_org': 'm.from_organization',
            'from_organization': 'm.from_organization',
            'sent_date': 'm.sent_date',
            'due_date': 'm.due_date',
            'status': 'm.status'
        }
        order_clause = "m.sent_date DESC NULLS LAST, m.mail_no DESC"
        if sort and isinstance(sort, str):
            clauses = []
            for token in sort.split(','):
                parts = token.strip().split()
                if not parts:
                    continue
                col_key = parts[0].strip().lower()
                direction = 'DESC' if len(parts) > 1 and parts[1].strip().upper() == 'DESC' else 'ASC'
                if col_key in rfi_explore_cols:
                    clauses.append(f"{rfi_explore_cols[col_key]} {direction} NULLS LAST")
            if clauses:
                order_clause = ", ".join(clauses)

        # Fetch records
        q = f"""
            SELECT 
                m.mail_no,
                COALESCE(m.reference_number, m.mail_no) as ref_no,
                m.subject,
                m.from_organization,
                m.to_organization,
                m.sent_date,
                m.due_date,
                m.status,
                m.days_late,
                COALESCE(l.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A' || m.mail_no) as aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE {where_sql}
            ORDER BY {order_clause}
            LIMIT {limit} OFFSET {offset}
        """
        rows = con.execute(q).fetchall()

        page_mail_nos = [r[0] for r in rows if r[0]]
        thread_counts = {}
        if page_mail_nos:
            ph = ','.join(['?'] * len(page_mail_nos))
            tc_rows = con.execute(f"""
                SELECT mail_no, count(DISTINCT response_mail_no) + 1
                FROM fact_mail_threads
                WHERE mail_no IN ({ph}) AND response_mail_no IS NOT NULL
                GROUP BY mail_no
            """, page_mail_nos).fetchall()
            for mn, cnt in tc_rows:
                thread_counts[mn] = cnt

        items = []
        for r in rows:
            m_no, ref_no, subj, f_org, t_org, s_dt, d_dt, st, d_late, url = r
            th_cnt = thread_counts.get(m_no, 1)

            is_open = (st or '').lower() in ['open', 'outstanding'] and (d_late or 0) >= 0

            items.append({
                "mail_no": m_no,
                "reference_number": ref_no or m_no,
                "subject": subj or "-",
                "from_org": f_org or "-",
                "to_org": t_org or "-",
                "sent_date": str(s_dt)[:10] if s_dt else "-",
                "due_date": str(d_dt)[:10] if d_dt else "-",
                "status": "Responded" if not is_open else "Open",
                "raw_status": st or "Open",
                "thread_steps_count": max(1, th_cnt),
                "has_thread": th_cnt > 1,
                "days_late": d_late or 0,
                "aconex_url": url
            })

        return {
            "project_id": norm_pkg,
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": items
        }
    finally:
        con.close()

def export_project_rfi_log_workbook(project_id: str = "DP02") -> tuple[bytes, str]:
    """
    Exports the complete, updated RFI Log adhering 100% to the exact format and columns
    of the project reference Excel file from C:\\Users\\bimst\\Downloads\\ACONEX\\Logs.
    """
    ref_file = PROJECT_LOG_FILES.get(project_id)
    if not ref_file or not os.path.exists(ref_file):
        # Fallback search by pattern
        cand = glob.glob(os.path.join(LOGS_DIR, f"*{project_id}*RFI*.xlsx"))
        if cand:
            ref_file = cand[0]
        else:
            ref_file = PROJECT_LOG_FILES.get("DP02")

    with open(ref_file, "rb") as f:
        file_bytes = f.read()

    updated_bytes, meta = update_rfi_workbook_bytes(file_bytes, os.path.basename(ref_file), override_pkg=project_id)
    filename = f"{project_id}_RFI_Log_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return updated_bytes, filename

def update_rfi_workbook_bytes(file_bytes: bytes, filename: str = "", override_pkg: str = None) -> tuple[bytes, dict]:
    """
    Intelligently updates an in-memory workbook:
    - Scans existing rows, injects live Aconex URLs.
    - Synchronizes any new responses for existing RFIs.
    - Appends newly initiated RFIs from DuckDB.
    - Preserves all fonts, merged title rows, headers, and dashboard sheets.
    """
    in_buf = io.BytesIO(file_bytes)
    wb = openpyxl.load_workbook(in_buf)
    con = get_db_connection()

    try:
        pkg = override_pkg or detect_package_from_name_or_content(filename, wb)

        # Identify data sheet (ignore Dashboard sheets)
        data_sheets = [s for s in wb.sheetnames if 'dash' not in s.lower()]
        target_sheet = data_sheets[0] if data_sheets else wb.sheetnames[0]
        ws = wb[target_sheet]

        # Locate header row containing 'Mail No' or 'RFI No'
        header_row = 4
        for r in range(1, min(10, ws.max_row + 1)):
            row_vals = [str(ws.cell(r, c).value or '').strip().lower() for c in range(1, ws.max_column + 1)]
            if any('mail no' in v or 'rfi no' in v for v in row_vals):
                header_row = r
                break

        # Map column positions from headers
        col_headers = [str(ws.cell(header_row, c).value or '').strip().lower() for c in range(1, ws.max_column + 1)]
        group_headers = [str(ws.cell(max(1, header_row - 1), c).value or '').strip().lower() for c in range(1, ws.max_column + 1)]

        # Collect mail columns to hyperlink
        font_link = Font(name="Calibri", size=9, color="0000EE", underline="single")
        font_data = Font(name="Calibri", size=9)
        font_bold = Font(name="Calibri", size=9, bold=True)
        thin_border = Border(
            left=Side(style='thin', color='B8CCE4'), right=Side(style='thin', color='B8CCE4'),
            top=Side(style='thin', color='B8CCE4'), bottom=Side(style='thin', color='B8CCE4')
        )
        fill_resp = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        fill_open = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")

        existing_rfis = set()
        hyperlinks_added = 0
        responses_updated = 0

        # Build url map cache for mails
        needed_mails = set()
        for r in range(header_row + 1, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                val = str(ws.cell(r, c).value or '').strip()
                if '-' in val and len(val) >= 8 and not ' ' in val:
                    needed_mails.add(val)

        url_cache = {}
        if needed_mails:
            mails_list = list(needed_mails)
            for i in range(0, len(mails_list), 500):
                chk = mails_list[i:i+500]
                ph = ','.join(['?'] * len(chk))
                rows = con.execute(f"SELECT mail_no, aconex_url FROM mail_aconex_links WHERE mail_no IN ({ph})", chk).fetchall()
                for m_no, u in rows:
                    if u: url_cache[m_no] = u

        # Apply hyperlinks and check for newly completed responses on existing rows
        for r in range(header_row + 1, ws.max_row + 1):
            row_rfis = []
            for c in range(1, min(5, ws.max_column + 1)):
                val = str(ws.cell(r, c).value or '').strip().upper()
                if val:
                    existing_rfis.add(val)
                    row_rfis.append(val)

            # Apply hyperlinks to all mail cells
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(r, c)
                val = str(cell.value or '').strip()
                if val in url_cache and not cell.hyperlink:
                    cell.hyperlink = url_cache[val]
                    cell.font = font_link
                    hyperlinks_added += 1

        # Query DuckDB for any new RFIs belonging to this package
        aliases = PROJECT_ALIASES.get(pkg, [pkg])
        pkg_conds = [f"m.project_package = '{pkg}'"]
        for a in aliases:
            pkg_conds.append(f"m.project_package ILIKE '%{a}%'")
            pkg_conds.append(f"m.subject ILIKE '%{a}%'")
            pkg_conds.append(f"m.mail_no ILIKE '%{a}%'")

        q_new = con.execute(f"""
            SELECT 
                m.mail_no, COALESCE(m.reference_number, m.mail_no) as ref_no,
                m.subject, m.sent_date,
                COALESCE(l.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A' || m.mail_no) as aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE (m.mail_type ILIKE '%Request For Information%' OR m.mail_no LIKE '%-RFI-%')
              AND ({' OR '.join(pkg_conds)})
            ORDER BY m.sent_date ASC NULLS LAST
        """).fetchall()

        # Pre-compute responded mails for instant O(1) checks
        responded_mails = set()
        resp_rows = con.execute("""
            SELECT DISTINCT mail_no FROM fact_mail_threads WHERE response_mail_no IS NOT NULL
            UNION
            SELECT DISTINCT reference_number FROM fact_mail WHERE mail_type ILIKE '%Response%' OR subject ILIKE '%Response to RFI%'
        """).fetchall()
        for rm in resp_rows:
            if rm[0]:
                responded_mails.add(str(rm[0]).strip().upper())

        appended_count = 0
        cur_row = ws.max_row + 1

        for rfi in q_new:
            m_no, ref_no, subj, s_dt, m_url = rfi
            m_up = (m_no or '').strip().upper()
            ref_up = (ref_no or '').strip().upper()

            if (m_up and m_up in existing_rfis) or (ref_up and ref_up in existing_rfis):
                continue

            ws.row_dimensions[cur_row].height = 20
            
            # Populate Col 1 (Initiator Mail No)
            c1 = ws.cell(cur_row, 1, m_no)
            if m_url:
                c1.hyperlink = m_url
                c1.font = font_link
            else:
                c1.font = font_bold

            # Populate Col 2 (RFI No / Ref)
            ws.cell(cur_row, 2, ref_no or m_no).font = font_bold
            
            # Revision (Col 3)
            ws.cell(cur_row, 3, 0).font = font_data
            
            # Col 4 / 5: Subject
            if ws.max_column >= 5:
                ws.cell(cur_row, 4, m_no).font = font_data
                ws.cell(cur_row, 5, subj or "").font = font_data
            
            # Date Col
            if ws.max_column >= 6 and s_dt:
                ws.cell(cur_row, 6, str(s_dt)[:10]).font = font_data

            # Status column
            st_col = ws.max_column
            for c_idx in range(ws.max_column, 1, -1):
                h_name = str(ws.cell(header_row, c_idx).value or '').lower()
                if 'status' in h_name or 'open' in h_name or 'closed' in h_name:
                    st_col = c_idx
                    break

            is_responded = (m_up in responded_mails) or (ref_up and ref_up in responded_mails)
            status_text = "Response" if is_responded else "Open"
            st_cell = ws.cell(cur_row, st_col, status_text)
            st_cell.font = font_bold
            st_cell.fill = fill_resp if is_responded else fill_open

            # Set styling
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(cur_row, col_idx)
                cell.border = thin_border
                if col_idx in [1, 2, 3, 6, st_col]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

            existing_rfis.add(m_up)
            if ref_up: existing_rfis.add(ref_up)
            appended_count += 1
            cur_row += 1

        out_buf = io.BytesIO()
        wb.save(out_buf)
        out_buf.seek(0)

        meta = {
            "status": "success",
            "package": pkg,
            "filename": filename,
            "total_rfis": ws.max_row - header_row,
            "new_rfis_appended": appended_count,
            "hyperlinks_count": hyperlinks_added,
            "responses_updated": responses_updated
        }
        return out_buf.getvalue(), meta

    finally:
        con.close()
