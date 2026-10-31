from typing import Optional, List, Dict, Any, Union, Tuple

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

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")

def get_db_connection():
    return duckdb.connect(DB_PATH, read_only=True)

CONTRACT_MAP = {
    '3121': 'DP01', '3180': 'DP01', 'MD01': 'DP01', 'P0155': 'DP01', 'K03121': 'DP01',
    '3149': 'DP02', '3270': 'DP02', 'P1003': 'DP02', 'K03149': 'DP02',
    '3199': 'DP03-East', 'K03199': 'DP03-East',
    '3271': 'DP03-West', 'K03271': 'DP03-West',
    '3204': 'DP04', 'K03204': 'DP04',
    '3205': 'DP05', 'K03205': 'DP05',
    '3206': 'DP06', 'K03206': 'DP06',
    '3207': 'DP07', 'K03207': 'DP07',
    '3200': 'Grand Canal', 'P0801': 'Grand Canal', 'K03200': 'Grand Canal',
    '3107': 'West Canal', 'P1201': 'West Canal', 'K03107': 'West Canal',
    '3048': 'Infra', 'SW00': 'Infra', 'K03048': 'Infra',
    '3044': 'MMS / Substation', 'MSS': 'MMS / Substation', 'K03044': 'MMS / Substation',
    '3045': 'RO Plant', 'K03045': 'RO Plant',
    '3046': 'STP', 'P5576': 'STP', 'K03046': 'STP',
    '3049': 'Airport', 'P0153': 'Airport', 'AR01': 'Airport', 'K00146': 'Airport',
    '3091': 'Ring Road', 'RR00': 'Ring Road', 'P0152': 'Ring Road', 'K03091': 'Ring Road',
    '3015': 'General Grading', 'REH.08.25.3015': 'General Grading',
}

KNOWN_CANONICAL_PACKAGES = set(CONTRACT_MAP.values()) | {
    'General Project Correspondence', 'Aedas Design Packages', 'Dar Consultancy Packages',
    'OBMI Consultancy Packages', 'DP08 - South Golf'
}

def resolve_canonical_package(subject: str = "", mail_no: str = "", from_org: str = "", to_org: str = "", default_pkg: str = "") -> str:
    """
    Multi-tiered precision package resolver across full project history:
    1. Contract number / K-code / P-code matches.
    2. Literal contract digits.
    3. Preserves valid canonical default_pkg.
    4. Package tokens (DP01-07, Infra, MSS, RO, STP, Canal, Airport, Ring Road, etc.).
    5. Contractor and Consultant signatures.
    """
    sub = (subject or "").upper()
    m_no = (mail_no or "").upper()
    f_org = (from_org or "").upper()
    t_org = (to_org or "").upper()
    combined = f"{sub} {m_no} {f_org} {t_org}"

    # Tier 1: Strict Contract Number / Package Code Pattern Match in Subject or Mail No
    for k, v in CONTRACT_MAP.items():
        pattern = r'(?:\b|K0?|P0?|REH[.\-_]|REH\.\d+\.\d+\.)' + re.escape(k) + r'(?:\b|[.\-_])'
        if re.search(pattern, sub) or re.search(pattern, m_no):
            return v

    # Tier 2: Literal Contract Digit substring in subject or mail_no
    for k in ['3271', '3199', '3204', '3205', '3206', '3207', '3149', '3270', '3121', '3180', '3200', '3107', '3048', '3044', '3045', '3046', '3049', '3091', '3015']:
        if k in sub or k in m_no:
            return CONTRACT_MAP[k]

    # Tier 3: If default_pkg is already a specific valid canonical package, preserve it
    if default_pkg and default_pkg in KNOWN_CANONICAL_PACKAGES and not any(g in default_pkg for g in ['General', 'Unknown', 'None']):
        return default_pkg

    # Tier 4: Explicit Package Names in Combined Text
    if 'DP03-EAST' in combined or 'DP03 EAST' in combined or 'DP3-EAST' in combined or 'DP3 EAST' in combined:
        return 'DP03-East'
    if 'DP03-WEST' in combined or 'DP03 WEST' in combined or 'DP3-WEST' in combined or 'DP3 WEST' in combined:
        return 'DP03-West'
    if re.search(r'\bDP-?0?1\b|\bMD-?0?1\b|AREA\s*1\b|SEA\s*TOWN', combined):
        return 'DP01'
    if re.search(r'\bDP-?0?2\b|\bMD-?0?2\b|AREA\s*2\b', combined):
        return 'DP02'
    if re.search(r'\bDP-?0?4\b|\bMD-?0?4\b', combined):
        return 'DP04'
    if re.search(r'\bDP-?0?5\b|\bMD-?0?5\b', combined):
        return 'DP05'
    if re.search(r'\bDP-?0?6\b|\bMD-?0?6\b|\bHYH\b', combined):
        return 'DP06'
    if re.search(r'\bDP-?0?7\b|\bMD-?0?7\b', combined):
        return 'DP07'
    if 'GRAND CANAL' in combined or 'LAGOON' in combined or 'ROYAL HASKONING' in combined or 'RHDHV' in combined or 'COASTLINE' in combined:
        return 'Grand Canal'
    if 'WEST CANAL' in combined:
        return 'West Canal'
    if 'RO PLANT' in combined or 'DESALINATION' in combined:
        return 'RO Plant'
    if 'SEWAGE TREATMENT' in combined or re.search(r'\bSTP\b', combined):
        return 'STP'
    if 'SUBSTATION' in combined or re.search(r'\bMSS\b|\bMSS1\b', combined):
        return 'MMS / Substation'
    if 'AIRPORT' in combined or 'AIR PORT' in combined or 'RUNWAY' in combined or 'NACO' in combined or 'ADB SAFEGATE' in combined or 'ADBSG' in combined or 'SMITHS DETECTION' in combined or 'SDME' in combined or 'AVDGS' in combined or 'ILS/DME' in combined:
        return 'Airport'
    if 'RING ROAD' in combined:
        return 'Ring Road'
    if 'INFRASTRUCTURE' in combined or re.search(r'\bINFRA\b|\bSW00\b', combined):
        return 'Infra'
    if 'SOUTH GOLF' in combined or 'DP08' in combined:
        return 'DP08 - South Golf'

    # Tier 5: Contractor / Originator / Target specific mappings
    if 'CCCEGY-RFI' in m_no or 'CCC / ROWAD' in combined or 'CONSOLIDATED CONTRACTORS' in combined:
        return 'DP02'
    if 'EETD-RME' in combined or 'ELSEWEDY' in combined:
        return 'MMS / Substation'
    if 'OTC-JV' in m_no or 'TROJAN' in combined:
        return 'RO Plant'
    if 'INNOVO' in combined or 'REDCON' in combined:
        return 'DP03-East'
    if 'ACC FOR ENGINEERING' in combined or 'ARABIAN CONSTRUCTION' in combined:
        return 'DP04'
    if 'CSCEC' in combined:
        return 'DP07'
    if 'DAR AL HANDASAH' in combined or 'DARR-' in m_no:
        return 'Dar Consultancy Packages'
    if 'AEDAS' in combined:
        return 'Aedas Design Packages'
    if 'OBMI' in combined:
        return 'OBMI Consultancy Packages'
    if 'DEWAN ARCHITECTS' in combined or 'DAE-' in m_no:
        return 'Dewan Consultancy Packages'
    if 'LOBB' in combined:
        return 'DP08 - South Golf'
    if 'AL AIN CONSULTING' in combined or 'ACE-UAE' in combined:
        return 'Al Ain Consultancy Packages'
    if 'ECG-AD' in m_no or 'ECG (RA01' in combined:
        return 'ECG Design Packages'
    if 'DO05' in combined or 'DO-05' in combined:
        return 'DP05'
    if 'STORM WATER' in combined:
        return 'Infra'

    return default_pkg if default_pkg else 'General Project Correspondence'

def resolve_pkg_by_contract(subject: str, default_pkg: str = "") -> str:
    """Backwards-compatibility alias for resolve_canonical_package."""
    return resolve_canonical_package(subject=subject, default_pkg=default_pkg)

import dispatch_settings_service as dss

def resolve_project_contacts(project_id: str, k_package_no: str = "", project_title: str = "") -> tuple[list, list]:
    """
    Resolves the exact recipient matrix.
    1. Checks user-customized in-app dispatch settings first (SSC Remind Emails Matrix).
    2. Falls back to Zone_DC_Manager_List_Shaker.xlsx, Zone_DC_Manager_List-ECG.xlsx, and Hill CC.xlsx.
    """
    # Check in-app customized SSC settings first
    to_custom, cc_custom = dss.resolve_ssc_contacts(project_id)
    if to_custom or cc_custom:
        return to_custom, cc_custom

    trigger_keys = [project_id]
    if k_package_no:
        trigger_keys.append(k_package_no)
    if project_title:
        trigger_keys.append(project_title)

    dcs, mgrs, zones = pr.get_shaker_ecg_zone_contacts(trigger_keys)
    hill_contacts = pr.get_hill_pmc_contacts(trigger_keys)

    # To: DCs only
    to_emails = list(dict.fromkeys(dcs))

    # CC: Shaker & ECG Managers/Engineers/Director + Hill PMC
    cc_combined = mgrs + hill_contacts
    # Ensure director Dean English is always present in CC
    if "DeanEnglish@hillintl.com" not in cc_combined:
        cc_combined.append("DeanEnglish@hillintl.com")
    cc_emails = list(dict.fromkeys([e for e in cc_combined if e not in to_emails]))

    return to_emails, cc_emails


def get_all_projects_overdue_overview(from_date: Optional[str] = None, to_date: Optional[str] = None) -> list:
    """
    Returns an executive inventory of all projects with real-time overdue counts and delay severity,
    applying multi-tiered contract-first resolution across full project history or filtered by date.
    """
    con = get_db_connection()
    try:
        rows = con.execute("""
            SELECT 
                p.project_id,
                p.project_name,
                p.project_title,
                p.category,
                p.contract_no,
                p.contract_digits,
                p.k_package_no,
                p.contractor_name,
                p.sort_order
            FROM dim_project_packages p
            ORDER BY p.sort_order ASC
        """).fetchall()

        rfi_date_clause = ""
        rfi_params = []
        mail_date_clause = ""
        mail_params = []

        if from_date and from_date.strip() and from_date.strip().lower() != 'all':
            rfi_date_clause += " AND sent_date >= ?"
            rfi_params.append(from_date.strip())
            mail_date_clause += " AND sent_date >= ?"
            mail_params.append(from_date.strip())
        if to_date and to_date.strip():
            rfi_date_clause += " AND sent_date <= ?"
            rfi_params.append(f"{to_date.strip()} 23:59:59")
            mail_date_clause += " AND sent_date <= ?"
            mail_params.append(f"{to_date.strip()} 23:59:59")

        # Contract-resolved RFIs count across full dataset (or date-filtered) excluding SCRs
        all_rfis = con.execute(f"""
            SELECT mail_no, project_package, subject, from_organization, to_organization 
            FROM fact_rfis 
            WHERE (is_overdue = true OR days_late > 0) 
              {rfi_date_clause}
              AND NOT (subject ILIKE '%SCR%' OR mail_no ILIKE '%SCR%')
        """, rfi_params).fetchall()
        from collections import defaultdict
        rfi_counts = defaultdict(int)
        for r in all_rfis:
            pkg = resolve_canonical_package(subject=r[2], mail_no=r[0], from_org=r[3], to_org=r[4], default_pkg=r[1])
            rfi_counts[pkg] += 1

        projects = []
        for r in rows:
            pid = r[0]
            k_code = r[6] or ""
            p_title = r[2] or r[1] or pid

            # Overdue workflows focusing on Shaker-ECG when present
            ov_wf = con.execute("""
                SELECT count(*) 
                FROM fact_workflow_steps s 
                JOIN fact_workflows w ON s.workflow_no = w.workflow_no 
                WHERE w.project_package = ? AND s.is_overdue = true
                  AND (s.assigned_to_organization ILIKE '%shaker%' OR s.assigned_to_organization ILIKE '%ecg%'
                       OR NOT EXISTS (
                           SELECT 1 FROM fact_workflow_steps s2 
                           JOIN fact_workflows w2 ON s2.workflow_no = w2.workflow_no 
                           WHERE w2.project_package = ? AND s2.is_overdue = true 
                             AND (s2.assigned_to_organization ILIKE '%shaker%' OR s2.assigned_to_organization ILIKE '%ecg%')
                       ))
            """, [pid, pid]).fetchone()[0]

            # Overdue letters (excluding SCRs)
            ov_mail = con.execute(f"""
                SELECT count(*) 
                FROM fact_mail 
                WHERE project_package = ? AND (is_overdue = true OR days_late > 0)
                  AND NOT (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
                  {mail_date_clause}
            """, [pid] + mail_params).fetchone()[0]

            ov_rfi = rfi_counts.get(pid, 0)

            # SCRs (Site Clarification Requests across all projects)
            if pid == 'DP01':
                ov_scr = con.execute(f"""
                    SELECT count(*) 
                    FROM fact_mail 
                    WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%' OR (project_package = 'Aedas Design Packages' AND subject ILIKE '%SCR%')) 
                      AND (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
                      AND (is_overdue = true OR days_late > 0)
                      {mail_date_clause}
                """, mail_params).fetchone()[0]
            else:
                ov_scr = con.execute(f"""
                    SELECT count(*) 
                    FROM fact_mail 
                    WHERE project_package = ?
                      AND (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
                      AND (is_overdue = true OR days_late > 0)
                      {mail_date_clause}
                """, [pid] + mail_params).fetchone()[0]

            tot_ov = ov_wf + ov_mail + ov_rfi + ov_scr

            to_list, cc_list = resolve_project_contacts(pid, k_code, p_title)

            # Max delay calculation
            delays = con.execute(f"""
                SELECT 
                    GREATEST(
                        COALESCE((SELECT MAX(s.days_late) FROM fact_workflow_steps s JOIN fact_workflows w ON s.workflow_no = w.workflow_no WHERE w.project_package = ? AND s.is_overdue = true), 0),
                        COALESCE((SELECT MAX(days_late) FROM fact_mail WHERE project_package = ? AND (is_overdue = true OR days_late > 0) {mail_date_clause}), 0),
                        COALESCE((SELECT MAX(days_late) FROM fact_rfis WHERE project_package = ? AND (is_overdue = true OR days_late > 0) {rfi_date_clause}), 0),
                        COALESCE((SELECT MAX(days_late) FROM fact_mail WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%') AND (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%') AND (is_overdue = true OR days_late > 0) AND ? = 'DP01' {mail_date_clause}), 0)
                    )
            """, [pid, pid] + mail_params + [pid] + rfi_params + [pid] + mail_params).fetchone()[0]
            max_delay = int(delays) if delays else 0

            projects.append({
                "project_id": pid,
                "project_name": r[1],
                "project_title": p_title,
                "category": r[3],
                "contract_no": r[4],
                "k_package_no": k_code,
                "contractor_name": r[7] or "PMC / Consultant",
                "to_emails": to_list,
                "cc_emails": cc_list,
                "to_count": len(to_list),
                "cc_count": len(cc_list),
                "overdue_workflows": ov_wf,
                "overdue_mails": ov_mail,
                "overdue_rfis": ov_rfi,
                "overdue_scrs": ov_scr,
                "total_overdue": tot_ov,
                "max_delay_days": max_delay,
                "sort_order": r[8]
            })

        return projects
    finally:
        con.close()

def get_project_overdue_report(project_id: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
    """
    Extracts all overdue deliverables for the given project package,
    resolves contacts, and generates both an executive HTML email template and mailto parameters.
    Applies multi-tiered contract resolution across full project history or filtered by date.
    """
    con = get_db_connection()
    try:
        # 1. Project Info
        p_row = con.execute("""
            SELECT project_id, project_title, category, contract_no, k_package_no, contractor_name 
            FROM dim_project_packages 
            WHERE project_id = ? 
            LIMIT 1
        """, [project_id]).fetchone()

        if not p_row:
            p_row = (project_id, project_id, "Wadi Yemm", "-", project_id, "-")

        pid, title, category, contract_no, k_code, contractor = p_row

        # Build dynamic date filters
        mail_date_clause = ""
        mail_params = []
        rfi_date_clause = ""
        rfi_params = []

        if from_date and from_date.strip() and from_date.strip().lower() != 'all':
            mail_date_clause += " AND sent_date >= ?"
            mail_params.append(from_date.strip())
            rfi_date_clause += " AND r.sent_date >= ?"
            rfi_params.append(from_date.strip())
        if to_date and to_date.strip():
            mail_date_clause += " AND sent_date <= ?"
            mail_params.append(f"{to_date.strip()} 23:59:59")
            rfi_date_clause += " AND r.sent_date <= ?"
            rfi_params.append(f"{to_date.strip()} 23:59:59")

        # 2. Resolve Contacts
        to_emails, cc_emails = resolve_project_contacts(pid, k_code or "", title or "")

        # 3. Overdue Workflows (Focusing on Shaker-ECG when present)
        wf_steps = con.execute("""
            SELECT 
                s.workflow_no,
                s.step_name,
                s.document_no,
                s.document_title,
                s.assigned_to_organization,
                s.assigned_to_name,
                s.date_due::VARCHAR,
                s.days_late,
                'https://mea.aconex.com/WorkflowSearch?searchtext=' || s.workflow_no || '&projectid=1744833878' AS aconex_url,
                w.workflow_name,
                CASE 
                    WHEN d.document_id IS NOT NULL AND LENGTH(TRIM(d.document_id)) > 3 AND d.document_id != 'None'
                    THEN 'https://mea.aconex.com/ViewDoc?trackingid=' || d.document_id || '&projectid=1744833878&docno=' || s.document_no || '&username=aabdelrahim4&action=ViewDocumentSummary'
                    ELSE 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=DOC-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=documentNumber%3A%22' || COALESCE(s.document_no, '') || '%22'
                END AS doc_aconex_url
            FROM fact_workflow_steps s
            JOIN fact_workflows w ON s.workflow_no = w.workflow_no
            LEFT JOIN (SELECT document_no, MAX(tracking_id) as document_id, MAX(aconex_url) as doc_direct_url FROM dim_documents GROUP BY document_no) d ON s.document_no = d.document_no
            WHERE w.project_package = ?
              AND s.is_overdue = true
              AND (s.assigned_to_organization ILIKE '%shaker%' OR s.assigned_to_organization ILIKE '%ecg%'
                   OR NOT EXISTS (
                       SELECT 1 FROM fact_workflow_steps s2 
                       JOIN fact_workflows w2 ON s2.workflow_no = w2.workflow_no 
                       WHERE w2.project_package = ? AND s2.is_overdue = true 
                         AND (s2.assigned_to_organization ILIKE '%shaker%' OR s2.assigned_to_organization ILIKE '%ecg%')
                   ))
            ORDER BY s.days_late DESC, s.workflow_no ASC
        """, [pid, pid]).fetchall()

        overdue_workflows = []
        for w in wf_steps:
            overdue_workflows.append({
                "category": "Workflow Step",
                "type": "Workflow",
                "workflow_no": w[0],
                "step_name": w[1] or "Review",
                "document_no": w[2] or "-",
                "document_title": w[3] or w[9] or "-",
                "assigned_org": w[4] or "Shaker-ECG consortium",
                "assigned_user": w[5] or "-",
                "step_info": f"{w[1] or 'Review'} ({w[4] or 'Shaker-ECG consortium'})",
                "date_due": str(w[6])[:10] if w[6] else "-",
                "due_date": str(w[6])[:10] if w[6] else "-",
                "days_late": int(w[7] or 0),
                "aconex_url": w[8],
                "doc_aconex_url": w[10] if len(w) > 10 else w[8]
            })

        # 4. Overdue Letters & Correspondence (Excluding SCRs)
        mail_rows = con.execute(f"""
            SELECT 
                mail_no, mail_type, subject, reference_number,
                from_organization, to_organization, from_name,
                sent_date::VARCHAR, due_date::VARCHAR, days_late,
                COALESCE(aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A%22' || mail_no || '%22') AS aconex_url
            FROM fact_mail
            WHERE project_package = ?
              AND (is_overdue = true OR days_late > 0)
              AND NOT (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
              {mail_date_clause}
            ORDER BY days_late DESC, sent_date DESC NULLS LAST
        """, [pid] + mail_params).fetchall()

        overdue_mails = []
        for m in mail_rows:
            overdue_mails.append({
                "category": "Correspondence",
                "type": m[1] or "Letter",
                "mail_no": m[0],
                "mail_type": m[1] or "Letter",
                "subject": m[2] or "-",
                "reference_number": m[3] or m[0],
                "from_org": m[4] or "-",
                "to_org": m[5] or "-",
                "from_name": m[6] or "",
                "step_info": f"From {m[4] or '-'} to {m[5] or '-'} (Response Pending)",
                "sent_date": str(m[7])[:10] if m[7] else "-",
                "due_date": str(m[8])[:10] if m[8] else "-",
                "days_late": int(m[9] or 0),
                "aconex_url": m[10]
            })

        # 5. Overdue RFIs (Contract-First Resolved, excluding SCRs)
        rfi_all = con.execute(f"""
            SELECT 
                r.mail_no, r.subject, COALESCE(m.reference_number, r.mail_no) as ref_no,
                r.from_organization, r.to_organization, r.from_name,
                r.sent_date::VARCHAR, r.due_date::VARCHAR, r.days_late,
                COALESCE(r.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A%22' || r.mail_no || '%22') AS aconex_url,
                COALESCE(m.mail_type, 'Request For Information') as mail_type,
                r.project_package
            FROM fact_rfis r
            LEFT JOIN fact_mail m ON r.mail_no = m.mail_no
            WHERE (r.is_overdue = true OR r.days_late > 0)
              {rfi_date_clause}
              AND NOT (r.subject ILIKE '%SCR%' OR r.mail_no ILIKE '%SCR%')
            ORDER BY r.days_late DESC, r.sent_date DESC NULLS LAST
        """, rfi_params).fetchall()

        overdue_rfis = []
        for r in rfi_all:
            resolved_pkg = resolve_canonical_package(subject=r[1], mail_no=r[0], from_org=r[3], to_org=r[4], default_pkg=r[11])
            if resolved_pkg == pid:
                to_consultant = r[4] if r[4] and "Hill" not in r[4] else "Shaker-ECG consortium"
                overdue_rfis.append({
                    "category": "RFI",
                    "type": "RFI",
                    "mail_no": r[0],
                    "rfi_no": r[0],
                    "mail_type": r[10] or "Request For Information",
                    "subject": r[1] or "-",
                    "reference_number": r[2] or r[0],
                    "from_org": r[3] or "-",
                    "to_org": to_consultant,
                    "from_name": r[5] or "",
                    "step_info": f"To Consultant: {to_consultant} (Response Pending)",
                    "sent_date": str(r[6])[:10] if r[6] else "-",
                    "due_date": str(r[7])[:10] if r[7] else "-",
                    "days_late": int(r[8] or 0),
                    "aconex_url": r[9]
                })

        # 6. Overdue Site Clarifications (SCR) across all packages
        overdue_scrs = []
        if pid == 'DP01':
            scr_sql = f"""
                SELECT 
                    mail_no, subject, COALESCE(reference_number, mail_no) as ref_no,
                    from_organization, to_organization, from_name,
                    sent_date::VARCHAR, due_date::VARCHAR, days_late,
                    COALESCE(aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A%22' || mail_no || '%22') AS aconex_url,
                    mail_type
                FROM fact_mail
                WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%' OR (project_package = 'Aedas Design Packages' AND subject ILIKE '%SCR%'))
                  AND (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
                  AND (is_overdue = true OR days_late > 0)
                  {mail_date_clause}
                ORDER BY days_late DESC, sent_date DESC NULLS LAST
            """
            scr_rows = con.execute(scr_sql, mail_params).fetchall()
        else:
            scr_sql = f"""
                SELECT 
                    mail_no, subject, COALESCE(reference_number, mail_no) as ref_no,
                    from_organization, to_organization, from_name,
                    sent_date::VARCHAR, due_date::VARCHAR, days_late,
                    COALESCE(aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A%22' || mail_no || '%22') AS aconex_url,
                    mail_type
                FROM fact_mail
                WHERE project_package = ?
                  AND (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
                  AND (is_overdue = true OR days_late > 0)
                  {mail_date_clause}
                ORDER BY days_late DESC, sent_date DESC NULLS LAST
            """
            scr_rows = con.execute(scr_sql, [pid] + mail_params).fetchall()

        for r in scr_rows:
            to_consultant = r[4] or "ECG"
            overdue_scrs.append({
                "category": "Site Clarification",
                "type": "SCR",
                "mail_no": r[0],
                "mail_type": r[10] or "Site Clarification Request",
                "subject": r[1] or "-",
                "reference_number": r[2] or r[0],
                "from_org": r[3] or "-",
                "to_org": to_consultant,
                "from_name": r[5] or "",
                "step_info": f"To Consultant: {to_consultant} (Response Pending)",
                "sent_date": str(r[6])[:10] if r[6] else "-",
                "due_date": str(r[7])[:10] if r[7] else "-",
                "days_late": int(r[8] or 0),
                "aconex_url": r[9]
            })

        total_overdue = len(overdue_workflows) + len(overdue_mails) + len(overdue_rfis) + len(overdue_scrs)
        all_delays = (
            [w["days_late"] for w in overdue_workflows] + 
            [m["days_late"] for m in overdue_mails] + 
            [r["days_late"] for r in overdue_rfis] +
            [s["days_late"] for s in overdue_scrs]
        )
        max_delay = max(all_delays) if all_delays else 0

        # Generate Executive HTML Email and Plain Text Summary
        html_email = generate_project_overdue_html(
            project_id=pid,
            project_title=title,
            k_package_no=k_code or pid,
            contractor_name=contractor,
            to_emails=to_emails,
            cc_emails=cc_emails,
            overdue_workflows=overdue_workflows,
            overdue_mails=overdue_mails,
            overdue_rfis=overdue_rfis,
            max_delay=max_delay,
            overdue_scrs=overdue_scrs
        )

        email_subject = f"OVERDUE NOTICE: {title} ({k_code or pid}) - {total_overdue} Items Exceeding Turnaround"

        # Build clean plain-text mailto URL
        body_lines = [
            f"Dear Document Control & Project Teams,",
            "",
            f"Please review the official list of overdue deliverables for project package: {title} ({k_code or pid}).",
            f"• Total Overdue Deliverables: {total_overdue}",
            f"• Maximum Turnaround Delay: +{max_delay} Days",
            f"• Technical Review Workflows: {len(overdue_workflows)}",
            f"• Letters & Correspondence: {len(overdue_mails)}",
            f"• Requests For Information (RFIs): {len(overdue_rfis)}",
            f"• Site Clarifications (SCR): {len(overdue_scrs)}",
            "",
            "Contractual Action Notice:",
            "Immediate resolution and close-out in Oracle Aconex are requested before the end of the working week to prevent project schedule delays.",
            "",
            "Best regards,",
            "PMC Project Controls Team | Hill International",
            "Ras El Hekma Development Project",
            "Live Controls Platform: http://localhost:8000"
        ]
        body_text = "\n".join(body_lines)

        mailto_to = ",".join(to_emails)
        mailto_cc = ",".join(cc_emails)
        mailto_url = f"mailto:{urllib.parse.quote(mailto_to, safe=',@')}?cc={urllib.parse.quote(mailto_cc, safe=',@')}&subject={urllib.parse.quote(email_subject)}&body={urllib.parse.quote(body_text)}"

        return {
            "project_id": pid,
            "project_title": title,
            "category": category,
            "contract_no": contract_no,
            "k_package_no": k_code or pid,
            "contractor_name": contractor,
            "to_emails": to_emails,
            "cc_emails": cc_emails,
            "total_overdue": total_overdue,
            "max_delay_days": max_delay,
            "workflows_count": len(overdue_workflows),
            "mails_count": len(overdue_mails),
            "rfis_count": len(overdue_rfis),
            "scrs_count": len(overdue_scrs),
            "workflows": overdue_workflows,
            "mails": overdue_mails,
            "rfis": overdue_rfis,
            "scrs": overdue_scrs,
            "email_subject": email_subject,
            "html_email": html_email,
            "mailto_url": mailto_url
        }
    finally:
        con.close()

def generate_project_overdue_html(
    project_id: str,
    project_title: str,
    k_package_no: str,
    contractor_name: str,
    to_emails: list,
    cc_emails: list,
    overdue_workflows: list,
    overdue_mails: list,
    overdue_rfis: list,
    max_delay: int,
    overdue_scrs: list | None = None
) -> str:
    """
    Renders a responsive, executive HTML email draft with dark-navy styling,
    itemized tables with working Aconex hyperlinks, and contractual closeout notice.
    """
    scrs = overdue_scrs or []
    total_overdue = len(overdue_workflows) + len(overdue_mails) + len(overdue_rfis) + len(scrs)
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")

    to_str = ", ".join(to_emails) if to_emails else "Document Controllers (DC)"
    cc_str = ", ".join(cc_emails) if cc_emails else "Management & Hill PMC"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Official PMC Overdue Notice - {project_title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; background-color: #f1f5f9; color: #0f172a; line-height: 1.5; }}
        .email-card {{ max-width: 960px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #cbd5e1; overflow: hidden; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08); }}
        .header-banner {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 26px 32px; color: #ffffff; }}
        .header-meta {{ font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 6px; }}
        .header-title {{ margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.3px; }}
        .header-sub {{ margin-top: 6px; font-size: 13px; color: #94a3b8; font-weight: 500; }}
        
        .routing-box {{ background: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 14px 32px; font-size: 12px; }}
        .routing-row {{ display: flex; margin-bottom: 4px; }}
        .routing-lbl {{ font-weight: 700; color: #475569; width: 60px; flex-shrink: 0; }}
        .routing-val {{ color: #0f172a; font-family: monospace; word-break: break-all; }}
        
        .kpi-grid {{ display: table; width: 100%; border-bottom: 2px solid #e2e8f0; background: #f8fafc; }}
        .kpi-cell {{ display: table-cell; width: 20%; padding: 16px 12px; text-align: center; border-right: 1px solid #e2e8f0; }}
        .kpi-cell:last-child {{ border-right: none; }}
        .kpi-num {{ font-size: 24px; font-weight: 800; color: #0f172a; font-family: monospace; }}
        .kpi-num-red {{ font-size: 24px; font-weight: 800; color: #dc2626; font-family: monospace; }}
        .kpi-lbl {{ font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
        
        .email-body {{ padding: 28px 32px; }}
        .intro-p {{ font-size: 13px; color: #334155; margin-top: 0; margin-bottom: 20px; line-height: 1.6; }}
        
        .section-header {{ background: #0f172a; color: #ffffff; padding: 10px 16px; border-radius: 6px; font-size: 13px; font-weight: 700; display: flex; justify-content: space-between; align-items: center; margin-top: 24px; margin-bottom: 10px; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 18px; }}
        .data-table th {{ background: #1e293b; color: #f8fafc; text-align: left; padding: 8px 10px; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.3px; }}
        .data-table td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
        .data-table tr:nth-child(even) {{ background: #f8fafc; }}
        .data-table tr:hover {{ background: #f1f5f9; }}
        
        .tag-late {{ background: #fef2f2; color: #b91c1c; font-weight: 700; padding: 2px 7px; border-radius: 4px; border: 1px solid #fecaca; font-size: 11px; white-space: nowrap; font-family: monospace; }}
        .link-aconex {{ color: #0284c7; font-weight: 700; text-decoration: none; font-family: monospace; }}
        .link-aconex:hover {{ text-decoration: underline; color: #0369a1; }}
        
        .notice-box {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 16px 20px; font-size: 12px; color: #92400e; margin-top: 28px; line-height: 1.6; }}
        .footer-box {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; font-size: 11px; color: #64748b; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="email-card">
        <!-- Header Banner -->
        <div class="header-banner">
            <div class="header-meta">Ras El Hekma Project Controls &amp; Governance</div>
            <h1 class="header-title">OFFICIAL OVERDUE DELIVERABLES NOTICE</h1>
            <div class="header-sub">
                Project Package: <strong style="color: #ffffff;">{project_title}</strong> ({k_package_no}) &bull; Contractor: <strong style="color: #ffffff;">{contractor_name}</strong>
            </div>
        </div>

        <!-- Email Routing -->
        <div class="routing-box">
            <div class="routing-row">
                <span class="routing-lbl">TO:</span>
                <span class="routing-val">{to_str}</span>
            </div>
            <div class="routing-row" style="margin-bottom: 0;">
                <span class="routing-lbl">CC:</span>
                <span class="routing-val">{cc_str}</span>
            </div>
        </div>

        <!-- KPI Metrics Grid -->
        <div class="kpi-grid">
            <div class="kpi-cell">
                <div class="kpi-num-red">{total_overdue}</div>
                <div class="kpi-lbl">Total Overdue</div>
            </div>
            <div class="kpi-cell">
                <div class="kpi-num-red">+{max_delay}d</div>
                <div class="kpi-lbl">Max Delay Recorded</div>
            </div>
            <div class="kpi-cell">
                <div class="kpi-num">{len(overdue_workflows)}</div>
                <div class="kpi-lbl">Review Workflows</div>
            </div>
            <div class="kpi-cell">
                <div class="kpi-num">{len(overdue_mails)}</div>
                <div class="kpi-lbl">Letters Pending</div>
            </div>
            <div class="kpi-cell">
                <div class="kpi-num">{len(scrs) if scrs else len(overdue_rfis)}</div>
                <div class="kpi-lbl">{'Site Clarifications (SCR)' if scrs else 'Overdue RFIs'}</div>
            </div>
        </div>

        <!-- Body Content -->
        <div class="email-body">
            <p class="intro-p">
                Dear <strong>Document Control &amp; Project Management Teams</strong>,<br><br>
                According to official Oracle Aconex project controls records generated on <strong>{now_str}</strong>, the following deliverables for <strong>{project_title} ({k_package_no})</strong> have exceeded contractual turnaround limits and require immediate action.
                All records include direct 1-click Aconex hyperlinks for rapid access.
            </p>
    """

    # Table 1: Workflows
    if overdue_workflows:
        wf_display = overdue_workflows[:50]
        html += f"""
            <div class="section-header">
                <span>1. Overdue Technical Review Workflows ({len(overdue_workflows)} Total)</span>
                <span style="font-size: 11px; font-weight: normal; color: #cbd5e1;">Oracle Aconex Workflows</span>
            </div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 16%;">Workflow No</th>
                        <th style="width: 18%;">Document No</th>
                        <th style="width: 30%;">Title / Step</th>
                        <th style="width: 18%;">Assigned To</th>
                        <th style="width: 10%;">Due Date</th>
                        <th style="width: 8%; text-align: center;">Delay</th>
                    </tr>
                </thead>
                <tbody>
        """
        for w in wf_display:
            html += f"""
                <tr>
                    <td><a href="{w['aconex_url']}" target="_blank" class="link-aconex">{w['workflow_no']}</a></td>
                    <td style="font-family: monospace; font-size: 11px;"><a href="{w.get('doc_aconex_url', w['aconex_url'])}" target="_blank" class="link-aconex">{w['document_no']}</a></td>
                    <td>
                        <div style="font-weight: 600; color: #0f172a;">{w['document_title']}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Step: <strong>{w['step_name']}</strong></div>
                    </td>
                    <td>
                        <div style="font-weight: 600;">{w['assigned_org']}</div>
                        <div style="font-size: 10px; color: #64748b;">{w['assigned_user']}</div>
                    </td>
                    <td style="font-family: monospace; font-size: 11px; white-space: nowrap;">{w['due_date']}</td>
                    <td style="text-align: center;"><span class="tag-late">+{w['days_late']}d</span></td>
                </tr>
            """
        html += "</tbody></table>"
        if len(overdue_workflows) > 50:
            html += f"""<div style="text-align: center; font-size: 11px; color: #64748b; margin-top: -10px; margin-bottom: 20px; font-style: italic;">
                Showing top 50 most delayed review workflows. {len(overdue_workflows) - 50} additional overdue items are cataloged in the attached Excel workbook and live dashboard.
            </div>"""

    # Table 2: Letters & Correspondence
    if overdue_mails:
        mail_display = overdue_mails[:50]
        html += f"""
            <div class="section-header">
                <span>2. Overdue Letters &amp; Contractual Correspondence ({len(overdue_mails)} Total)</span>
                <span style="font-size: 11px; font-weight: normal; color: #cbd5e1;">Pending Determination</span>
            </div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 18%;">Mail No</th>
                        <th style="width: 12%;">Type / Ref</th>
                        <th style="width: 34%;">Subject</th>
                        <th style="width: 18%;">From / To</th>
                        <th style="width: 10%;">Due Date</th>
                        <th style="width: 8%; text-align: center;">Delay</th>
                    </tr>
                </thead>
                <tbody>
        """
        for m in mail_display:
            html += f"""
                <tr>
                    <td><a href="{m['aconex_url']}" target="_blank" class="link-aconex">{m['mail_no']}</a></td>
                    <td>
                        <div style="font-weight: 600;">{m['mail_type']}</div>
                        <div style="font-size: 10px; font-family: monospace; color: #64748b;">{m['reference_number']}</div>
                    </td>
                    <td style="color: #1e293b; font-weight: 500;">{m['subject']}</td>
                    <td>
                        <div style="font-size: 11px;">From: <strong>{m['from_org']}</strong></div>
                        <div style="font-size: 11px; color: #64748b;">To: <strong>{m['to_org']}</strong></div>
                    </td>
                    <td style="font-family: monospace; font-size: 11px; white-space: nowrap;">{m['due_date']}</td>
                    <td style="text-align: center;"><span class="tag-late">+{m['days_late']}d</span></td>
                </tr>
            """
        html += "</tbody></table>"
        if len(overdue_mails) > 50:
            html += f"""<div style="text-align: center; font-size: 11px; color: #64748b; margin-top: -10px; margin-bottom: 20px; font-style: italic;">
                Showing top 50 most delayed correspondence items. {len(overdue_mails) - 50} additional overdue items are cataloged in the attached Excel workbook and live dashboard.
            </div>"""

    # Table 3: RFIs
    if overdue_rfis:
        rfi_display = overdue_rfis[:50]
        html += f"""
            <div class="section-header">
                <span>3. Overdue Requests For Information (RFIs) ({len(overdue_rfis)} Total)</span>
                <span style="font-size: 11px; font-weight: normal; color: #cbd5e1;">Pending Consultant Response</span>
            </div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 18%;">RFI No</th>
                        <th style="width: 14%;">Reference</th>
                        <th style="width: 32%;">Subject</th>
                        <th style="width: 18%;">Contractor / Consultant</th>
                        <th style="width: 10%;">Due Date</th>
                        <th style="width: 8%; text-align: center;">Delay</th>
                    </tr>
                </thead>
                <tbody>
        """
        for r in rfi_display:
            html += f"""
                <tr>
                    <td><a href="{r['aconex_url']}" target="_blank" class="link-aconex">{r['mail_no']}</a></td>
                    <td style="font-family: monospace; font-size: 11px;">{r['reference_number']}</td>
                    <td style="color: #1e293b; font-weight: 500;">{r['subject']}</td>
                    <td>
                        <div style="font-weight: 600;">{r['from_org']}</div>
                        <div style="font-size: 10px; color: #64748b;">Pending: <strong>{r['to_org']}</strong></div>
                    </td>
                    <td style="font-family: monospace; font-size: 11px; white-space: nowrap;">{r['due_date']}</td>
                    <td style="text-align: center;"><span class="tag-late">+{r['days_late']}d</span></td>
                </tr>
            """
        html += "</tbody></table>"
        if len(overdue_rfis) > 50:
            html += f"""<div style="text-align: center; font-size: 11px; color: #64748b; margin-top: -10px; margin-bottom: 20px; font-style: italic;">
                Showing top 50 most delayed RFIs. {len(overdue_rfis) - 50} additional overdue RFIs are cataloged in the attached Excel workbook and live dashboard.
            </div>"""

    # Table 4: SCRs (Site Clarification Requests)
    if scrs:
        scr_display = scrs[:50]
        sec_num = "4" if overdue_rfis else "3"
        html += f"""
            <div class="section-header">
                <span>{sec_num}. Overdue Site Clarifications (SCR) ({len(scrs)} Total)</span>
                <span style="font-size: 11px; font-weight: normal; color: #cbd5e1;">Site Technical Clarifications</span>
            </div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 18%;">SCR No</th>
                        <th style="width: 16%;">Reference</th>
                        <th style="width: 32%;">Subject</th>
                        <th style="width: 16%;">Assigned Consultant</th>
                        <th style="width: 10%;">Due Date</th>
                        <th style="width: 8%; text-align: center;">Delay</th>
                    </tr>
                </thead>
                <tbody>
        """
        for s in scr_display:
            html += f"""
                <tr>
                    <td><a href="{s['aconex_url']}" target="_blank" class="link-aconex">{s['mail_no']}</a></td>
                    <td style="font-family: monospace; font-size: 11px;">{s['reference_number']}</td>
                    <td style="color: #1e293b; font-weight: 500;">{s['subject']}</td>
                    <td>
                        <div style="font-weight: 600;">{s['to_org']}</div>
                        <div style="font-size: 10px; color: #64748b;">Response Pending</div>
                    </td>
                    <td style="font-family: monospace; font-size: 11px; white-space: nowrap;">{s['due_date']}</td>
                    <td style="text-align: center;"><span class="tag-late">+{s['days_late']}d</span></td>
                </tr>
            """
        html += "</tbody></table>"
        if len(scrs) > 50:
            html += f"""<div style="text-align: center; font-size: 11px; color: #64748b; margin-top: -10px; margin-bottom: 20px; font-style: italic;">
                Showing top 50 most delayed SCRs. {len(scrs) - 50} additional overdue SCRs are cataloged in the attached Excel workbook and live dashboard.
            </div>"""

    # Contractual Notice & Signature
    html += f"""
            <div class="notice-box">
                <strong>CONTRACTUAL ACTION REQUIRED:</strong><br>
                All concerned parties are requested to prioritize the review, determination, and response to the deliverables above in Oracle Aconex before the close of this working week. Delayed submittal and review turnarounds directly jeopardize project milestones and site works execution.
            </div>
        </div>

        <!-- Footer -->
        <div class="footer-box">
            <div><strong>Ras El Hekma Project Management &amp; Controls Team</strong></div>
            <div>Hill International PMC in consortium with Shaker-ECG Supervision Consultants</div>
            <div style="margin-top: 4px; color: #94a3b8;">This automated notification is generated directly from Oracle Aconex Enterprise Project Controls Data.</div>
        </div>
    </div>
</body>
</html>
    """
    return html

def generate_project_overdue_excel(
    project_id: str,
    selected_workflows: list | None = None,
    selected_mails: list | None = None,
    selected_rfis: list | None = None,
    selected_scrs: list | None = None,
    include_workflows: bool = True,
    include_mails: bool = True,
    include_rfis: bool = True,
    include_scrs: bool = True,
    to_emails: list | None = None,
    cc_emails: list | None = None,
    from_date: str | None = None,
    to_date: str | None = None
) -> tuple[bytes, str]:
    """
    Generates a formatted multi-sheet Excel workbook containing only the overdue deliverables for this project package.
    Supports section inclusion/exclusion and item-level selection.
    """
    report = get_project_overdue_report(project_id, from_date=from_date, to_date=to_date)
    if to_emails is not None:
        report["to_emails"] = to_emails
    if cc_emails is not None:
        report["cc_emails"] = cc_emails

    # Filter workflows
    if not include_workflows:
        report["workflows"] = []
    elif selected_workflows is not None:
        sel_wf_set = set(selected_workflows)
        report["workflows"] = [w for w in report["workflows"] if w["workflow_no"] in sel_wf_set]

    # Filter mails
    if not include_mails:
        report["mails"] = []
    elif selected_mails is not None:
        sel_mail_set = set(selected_mails)
        report["mails"] = [m for m in report["mails"] if m["mail_no"] in sel_mail_set]

    # Filter rfis
    if not include_rfis:
        report["rfis"] = []
    elif selected_rfis is not None:
        sel_rfi_set = set(selected_rfis)
        report["rfis"] = [r for r in report["rfis"] if r.get("rfi_no") in sel_rfi_set or r.get("mail_no") in sel_rfi_set]

    # Filter scrs
    if not include_scrs:
        report["scrs"] = []
    elif selected_scrs is not None:
        sel_scr_set = set(selected_scrs)
        report["scrs"] = [s for s in report.get("scrs", []) if s.get("mail_no") in sel_scr_set]

    scrs_list = report.get("scrs", [])
    report["total_overdue"] = len(report["workflows"]) + len(report["mails"]) + len(report["rfis"]) + len(scrs_list)
    report["workflows_count"] = len(report["workflows"])
    report["mails_count"] = len(report["mails"])
    report["rfis_count"] = len(report["rfis"])
    report["scrs_count"] = len(scrs_list)
    all_delays = (
        [w["days_late"] for w in report["workflows"]] + 
        [m["days_late"] for m in report["mails"]] + 
        [r["days_late"] for r in report["rfis"]] + 
        [s["days_late"] for s in scrs_list]
    )
    report["max_delay_days"] = max(all_delays) if all_delays else 0

    wb = openpyxl.Workbook()
    
    # 1. Sheet 1: Summary & Recipients
    ws_sum = wb.active
    ws_sum.title = "Overdue Summary"
    ws_sum.views.sheetView[0].showGridLines = True

    # Styling definitions
    title_font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    title_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sub_font = Font(name="Calibri", size=10, italic=True, color="94A3B8")
    sub_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    regular_font = Font(name="Calibri", size=10, color="0F172A")
    bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
    link_font = Font(name="Calibri", size=10, bold=True, color="0284C7", underline="single")

    late_font = Font(name="Calibri", size=10, bold=True, color="991B1B")
    late_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # Title Banner
    ws_sum.merge_cells("A1:F1")
    c1 = ws_sum.cell(1, 1, f"RAS EL HEKMA PROJECT CONTROLS - OVERDUE DELIVERABLES REPORT")
    c1.font = title_font
    c1.fill = title_fill
    c1.alignment = Alignment(horizontal="center", vertical="center")
    ws_sum.row_dimensions[1].height = 36

    ws_sum.merge_cells("A2:F2")
    c2 = ws_sum.cell(2, 1, f"Project: {report['project_title']} ({report['k_package_no']}) | Contractor: {report['contractor_name']} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c2.font = sub_font
    c2.fill = sub_fill
    c2.alignment = Alignment(horizontal="center", vertical="center")
    ws_sum.row_dimensions[2].height = 20

    # Summary KPIs
    ws_sum.cell(4, 1, "Metric").font = header_font
    ws_sum.cell(4, 1).fill = header_fill
    ws_sum.cell(4, 2, "Value").font = header_font
    ws_sum.cell(4, 2).fill = header_fill

    summary_rows = [
        ("Total Overdue Deliverables", report["total_overdue"]),
        ("Maximum Turnaround Delay", f"+{report['max_delay_days']} Days"),
        ("Overdue Technical Review Workflows", report["workflows_count"]),
        ("Overdue Letters & Correspondence", report["mails_count"]),
        ("Overdue Requests For Information (RFIs)", report["rfis_count"]),
    ]
    if report["scrs_count"] > 0:
        summary_rows.append(("Overdue Site Clarifications (SCR)", report["scrs_count"]))
    summary_rows.extend([
        ("Assigned Document Controllers (TO:)", ", ".join(report["to_emails"]) or "N/A"),
        ("Management & PMC Team (CC:)", ", ".join(report["cc_emails"]) or "N/A")
    ])

    for idx, (lbl, val) in enumerate(summary_rows, 5):
        c_lbl = ws_sum.cell(idx, 1, lbl)
        c_lbl.font = bold_font
        c_lbl.border = thin_border
        c_val = ws_sum.cell(idx, 2, str(val))
        c_val.font = regular_font
        c_val.border = thin_border

    ws_sum.column_dimensions['A'].width = 36
    ws_sum.column_dimensions['B'].width = 80

    # 2. Sheet 2: Workflows
    if report["workflows"]:
        ws_wf = wb.create_sheet(title="Overdue Workflows")
        ws_wf.views.sheetView[0].showGridLines = True
        headers = ["Workflow No", "Document No", "Document Title", "Current Step", "Assigned Organization", "Assignee Name", "Due Date", "Days Late"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws_wf.cell(1, col_idx, h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_wf.row_dimensions[1].height = 24

        for r_idx, w in enumerate(report["workflows"], 2):
            c_link = ws_wf.cell(r_idx, 1)
            c_link.value = f'=HYPERLINK("{w["aconex_url"]}", "{w["workflow_no"]}")'
            c_link.font = link_font
            c_link.border = thin_border

            c_doc = ws_wf.cell(r_idx, 2)
            if w.get("document_no") and w.get("document_no") != "-":
                c_doc.value = f'=HYPERLINK("{w.get("doc_aconex_url", w["aconex_url"])}", "{w["document_no"]}")'
                c_doc.font = link_font
            else:
                c_doc.value = w.get("document_no", "-")
                c_doc.font = regular_font
            ws_wf.cell(r_idx, 3, w["document_title"]).font = regular_font
            ws_wf.cell(r_idx, 4, w["step_name"]).font = bold_font
            ws_wf.cell(r_idx, 5, w["assigned_org"]).font = regular_font
            ws_wf.cell(r_idx, 6, w["assigned_user"]).font = regular_font
            ws_wf.cell(r_idx, 7, w["due_date"]).font = regular_font
            
            c_late = ws_wf.cell(r_idx, 8, f"+{w['days_late']}d")
            c_late.font = late_font
            c_late.fill = late_fill
            c_late.alignment = Alignment(horizontal="center")
            for c in range(2, 8):
                ws_wf.cell(r_idx, c).border = thin_border
            ws_wf.cell(r_idx, 8).border = thin_border

        for col in ws_wf.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_wf.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # 3. Sheet 3: Letters
    if report["mails"]:
        ws_mail = wb.create_sheet(title="Overdue Letters")
        ws_mail.views.sheetView[0].showGridLines = True
        headers = ["Mail No", "Mail Type", "Reference No", "Subject", "From Organization", "To Organization", "Due Date", "Days Late"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws_mail.cell(1, col_idx, h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_mail.row_dimensions[1].height = 24

        for r_idx, m in enumerate(report["mails"], 2):
            c_link = ws_mail.cell(r_idx, 1)
            c_link.value = f'=HYPERLINK("{m["aconex_url"]}", "{m["mail_no"]}")'
            c_link.font = link_font
            c_link.border = thin_border

            ws_mail.cell(r_idx, 2, m["mail_type"]).font = regular_font
            ws_mail.cell(r_idx, 3, m["reference_number"]).font = regular_font
            ws_mail.cell(r_idx, 4, m["subject"]).font = regular_font
            ws_mail.cell(r_idx, 5, m["from_org"]).font = regular_font
            ws_mail.cell(r_idx, 6, m["to_org"]).font = regular_font
            ws_mail.cell(r_idx, 7, m["due_date"]).font = regular_font

            c_late = ws_mail.cell(r_idx, 8, f"+{m['days_late']}d")
            c_late.font = late_font
            c_late.fill = late_fill
            c_late.alignment = Alignment(horizontal="center")
            for c in range(2, 8):
                ws_mail.cell(r_idx, c).border = thin_border
            ws_mail.cell(r_idx, 8).border = thin_border

        for col in ws_mail.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_mail.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # 4. Sheet 4: RFIs
    if report["rfis"]:
        ws_rfi = wb.create_sheet(title="Overdue RFIs")
        ws_rfi.views.sheetView[0].showGridLines = True
        headers = ["RFI No", "Reference No", "Subject", "From Organization", "To Organization", "Due Date", "Days Late"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws_rfi.cell(1, col_idx, h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_rfi.row_dimensions[1].height = 24

        for r_idx, r in enumerate(report["rfis"], 2):
            c_link = ws_rfi.cell(r_idx, 1)
            c_link.value = f'=HYPERLINK("{r["aconex_url"]}", "{r["mail_no"]}")'
            c_link.font = link_font
            c_link.border = thin_border

            ws_rfi.cell(r_idx, 2, r["reference_number"]).font = regular_font
            ws_rfi.cell(r_idx, 3, r["subject"]).font = regular_font
            ws_rfi.cell(r_idx, 4, r["from_org"]).font = regular_font
            ws_rfi.cell(r_idx, 5, r["to_org"]).font = regular_font
            ws_rfi.cell(r_idx, 6, r["due_date"]).font = regular_font

            c_late = ws_rfi.cell(r_idx, 7, f"+{r['days_late']}d")
            c_late.font = late_font
            c_late.fill = late_fill
            c_late.alignment = Alignment(horizontal="center")
            for c in range(2, 7):
                ws_rfi.cell(r_idx, c).border = thin_border
            ws_rfi.cell(r_idx, 7).border = thin_border

        for col in ws_rfi.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_rfi.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # 5. Sheet 5: Site Clarifications (SCR)
    if scrs_list:
        ws_scr = wb.create_sheet(title="Overdue Site Clarifications (SCR)")
        ws_scr.views.sheetView[0].showGridLines = True
        headers = ["SCR No", "Reference No", "Subject", "Originator", "Consultant (Action By)", "Due Date", "Days Late"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws_scr.cell(1, col_idx, h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_scr.row_dimensions[1].height = 24

        for r_idx, s in enumerate(scrs_list, 2):
            c_link = ws_scr.cell(r_idx, 1)
            c_link.value = f'=HYPERLINK("{s["aconex_url"]}", "{s["mail_no"]}")'
            c_link.font = link_font
            c_link.border = thin_border

            ws_scr.cell(r_idx, 2, s["reference_number"]).font = regular_font
            ws_scr.cell(r_idx, 3, s["subject"]).font = regular_font
            ws_scr.cell(r_idx, 4, s["from_org"]).font = regular_font
            ws_scr.cell(r_idx, 5, s["to_org"]).font = regular_font
            ws_scr.cell(r_idx, 6, s["due_date"]).font = regular_font

            c_late = ws_scr.cell(r_idx, 7, f"+{s['days_late']}d")
            c_late.font = late_font
            c_late.fill = late_fill
            c_late.alignment = Alignment(horizontal="center")
            for c in range(2, 7):
                ws_scr.cell(r_idx, c).border = thin_border
            ws_scr.cell(r_idx, 7).border = thin_border

        for col in ws_scr.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_scr.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"{re.sub(r'[^a-zA-Z0-9_\-]', '_', project_id)}_Overdue_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return stream.getvalue(), filename

def generate_project_overdue_eml(
    project_id: str,
    selected_workflows: list | None = None,
    selected_mails: list | None = None,
    selected_rfis: list | None = None,
    selected_scrs: list | None = None,
    include_workflows: bool = True,
    include_mails: bool = True,
    include_rfis: bool = True,
    include_scrs: bool = True,
    to_emails: list | None = None,
    cc_emails: list | None = None,
    from_date: str | None = None,
    to_date: str | None = None
) -> tuple[bytes, str]:
    """
    Generates an RFC-822 .eml draft message with:
    - X-Unsent: 1 (Opens in Microsoft Outlook / Apple Mail / Windows Mail directly as an editable draft ready to send)
    - TO recipients (Document Controllers)
    - CC recipients (Supervision Managers & Hill PMC)
    - Subject line
    - Multipart alternative with plain text summary and executive HTML body containing only curated deliverables
    - Attached curated Excel report (.xlsx) with active hyperlinks
    """
    report = get_project_overdue_report(project_id, from_date=from_date, to_date=to_date)
    if to_emails is not None:
        report["to_emails"] = to_emails
    if cc_emails is not None:
        report["cc_emails"] = cc_emails

    # Filter workflows
    if not include_workflows:
        report["workflows"] = []
    elif selected_workflows is not None:
        sel_wf_set = set(selected_workflows)
        report["workflows"] = [w for w in report["workflows"] if w["workflow_no"] in sel_wf_set]

    # Filter mails
    if not include_mails:
        report["mails"] = []
    elif selected_mails is not None:
        sel_mail_set = set(selected_mails)
        report["mails"] = [m for m in report["mails"] if m["mail_no"] in sel_mail_set]

    # Filter rfis
    if not include_rfis:
        report["rfis"] = []
    elif selected_rfis is not None:
        sel_rfi_set = set(selected_rfis)
        report["rfis"] = [r for r in report["rfis"] if r.get("rfi_no") in sel_rfi_set or r.get("mail_no") in sel_rfi_set]

    # Filter scrs
    if not include_scrs:
        report["scrs"] = []
    elif selected_scrs is not None:
        sel_scr_set = set(selected_scrs)
        report["scrs"] = [s for s in report.get("scrs", []) if s.get("mail_no") in sel_scr_set]

    scrs_list = report.get("scrs", [])
    report["total_overdue"] = len(report["workflows"]) + len(report["mails"]) + len(report["rfis"]) + len(scrs_list)
    report["workflows_count"] = len(report["workflows"])
    report["mails_count"] = len(report["mails"])
    report["rfis_count"] = len(report["rfis"])
    report["scrs_count"] = len(scrs_list)
    all_delays = (
        [w["days_late"] for w in report["workflows"]] + 
        [m["days_late"] for m in report["mails"]] + 
        [r["days_late"] for r in report["rfis"]] + 
        [s["days_late"] for s in scrs_list]
    )
    report["max_delay_days"] = max(all_delays) if all_delays else 0

    # Generate matching curated HTML
    curated_html = generate_project_overdue_html(
        project_id=report["project_id"],
        project_title=report["project_title"],
        k_package_no=report["k_package_no"],
        contractor_name=report["contractor_name"],
        to_emails=report["to_emails"],
        cc_emails=report["cc_emails"],
        overdue_workflows=report["workflows"],
        overdue_mails=report["mails"],
        overdue_rfis=report["rfis"],
        max_delay=report["max_delay_days"],
        overdue_scrs=scrs_list
    )

    # Generate matching curated Excel
    excel_bytes, excel_filename = generate_project_overdue_excel(
        project_id=project_id,
        selected_workflows=selected_workflows,
        selected_mails=selected_mails,
        selected_rfis=selected_rfis,
        selected_scrs=selected_scrs,
        include_workflows=include_workflows,
        include_mails=include_mails,
        include_rfis=include_rfis,
        include_scrs=include_scrs,
        to_emails=report["to_emails"],
        cc_emails=report["cc_emails"]
    )

    msg = EmailMessage()
    email_subject = f"OVERDUE NOTICE: {report['project_title']} ({report['k_package_no']}) - {report['total_overdue']} Items Exceeding Turnaround"
    msg['Subject'] = email_subject
    msg['From'] = 'Ras El Hekma PMC Project Controls <pmc-controls@raselhekma.com>'
    if report['to_emails']:
        msg['To'] = ", ".join(report['to_emails'])
    if report['cc_emails']:
        msg['Cc'] = ", ".join(report['cc_emails'])
    msg['X-Unsent'] = '1'

    plain_body = f"""Dear Document Control & Project Teams,

Please review the curated list of overdue deliverables for project package:
{report['project_title']} ({report['k_package_no']})

Summary of Dispatched Overdue Deliverables:
• Total Overdue Deliverables Included: {report['total_overdue']}
• Maximum Turnaround Delay: +{report['max_delay_days']} Days
• Technical Review Workflows: {report['workflows_count']}
• Official Letters & Mails: {report['mails_count']}
• Requests For Information (RFIs): {report['rfis_count']}
"""
    if report['scrs_count'] > 0:
        plain_body += f"• Site Clarifications (SCR): {report['scrs_count']}\n"

    plain_body += f"""
Action Notice:
The attached Excel file ({excel_filename}) contains the filtered register with active Oracle Aconex hyperlinks for each item.
Immediate resolution and closeout in Oracle Aconex are requested before the end of the working week to prevent project schedule delays.

Best regards,
PMC Project Controls Team | Hill International
Ras El Hekma Development Project
Platform: http://localhost:8000
"""
    msg.set_content(plain_body)
    msg.add_alternative(curated_html, subtype='html')

    # Add the generated Excel file as an attachment
    msg.add_attachment(
        excel_bytes,
        maintype='application',
        subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename=excel_filename
    )

    clean_pid = re.sub(r'[^a-zA-Z0-9_\-]', '_', project_id)
    eml_filename = f"{clean_pid}_Overdue_Notice_Draft_{datetime.now().strftime('%Y%m%d_%H%M')}.eml"
    return msg.as_bytes(), eml_filename


# =============================================================================
# Contractor RFIs Overview & Direct Remind Email Dispatch
# =============================================================================

def get_contractor_rfis_data(
    project_id: Optional[str] = None,
    company: Optional[str] = None,
    status: Optional[str] = None,
    overdue_only: bool = False,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> dict:
    """
    Retrieves contractor RFIs since 2026-03-01 baseline, with contract-first resolution,
    grouping by project and responsible consultant company, and SLA turnaround metrics.
    Strictly differentiates between ECG (Design Consultant) and Shaker-ECG Consortium (SSC).
    """
    con = get_db_connection()
    try:
        where_clauses = ["1=1"]
        params = []

        # Filter by date only if from_date is provided and not 'all'
        if from_date and from_date.strip() and from_date.strip().lower() != 'all':
            where_clauses.append("r.sent_date >= ?")
            params.append(from_date.strip())

        if to_date and to_date.strip():
            where_clauses.append("r.sent_date <= ?")
            params.append(f"{to_date.strip()} 23:59:59")

        # Exclude SCRs
        where_clauses.append("NOT (r.subject ILIKE '%SCR%' OR r.mail_no ILIKE '%SCR%')")

        if company and company.strip() and company.lower() != "all":
            c_clean = company.strip()
            # Strict separation between ECG (Design Consultant) and Shaker-ECG consortium (SSC)
            if c_clean.upper() == "ECG":
                where_clauses.append("LOWER(TRIM(r.to_organization)) = 'ecg'")
            elif "shaker-ecg" in c_clean.lower():
                where_clauses.append("r.to_organization ILIKE '%shaker-ecg%'")
            else:
                where_clauses.append("r.to_organization ILIKE ?")
                params.append(f"%{c_clean}%")

        if search and search.strip():
            s = f"%{search.strip()}%"
            where_clauses.append("(r.mail_no ILIKE ? OR r.subject ILIKE ? OR r.from_organization ILIKE ? OR r.to_organization ILIKE ?)")
            params.extend([s, s, s, s])

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT 
                r.mail_no,
                r.subject,
                r.from_organization,
                r.to_organization,
                r.from_name,
                r.sent_date::VARCHAR,
                r.due_date::VARCHAR,
                r.days_late,
                r.is_overdue,
                r.project_package,
                COALESCE(r.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A%22' || r.mail_no || '%22') AS aconex_url
            FROM fact_rfis r
            WHERE {where_sql}
            ORDER BY r.days_late DESC, r.sent_date DESC NULLS LAST
        """

        raw_rows = con.execute(query, params).fetchall()

        # Multi-tiered canonical project resolution & memory filtering for project_id
        all_rfis = []
        company_counts = {}
        project_counts = {}
        total_overdue = 0
        max_delay = 0

        target_pid = project_id.strip() if project_id and project_id.strip() and project_id.lower() != "all" else None

        for r in raw_rows:
            resolved_pkg = resolve_canonical_package(subject=r[1], mail_no=r[0], from_org=r[2], to_org=r[3], default_pkg=r[9] or "")
            if target_pid and resolved_pkg != target_pid:
                continue

            days_late = int(r[7] or 0)
            is_ov = bool(r[8] or days_late > 0)
            if is_ov:
                total_overdue += 1
                if days_late > max_delay:
                    max_delay = days_late

            to_org = r[3] or "Supervision Consultant"
            company_counts[to_org] = company_counts.get(to_org, 0) + 1
            project_counts[resolved_pkg] = project_counts.get(resolved_pkg, 0) + 1

            all_rfis.append({
                "mail_no": r[0],
                "subject": r[1] or "-",
                "from_org": r[2] or "-",
                "to_org": to_org,
                "from_name": r[4] or "-",
                "sent_date": str(r[5])[:10] if r[5] else "-",
                "due_date": str(r[6])[:10] if r[6] else "-",
                "days_late": days_late,
                "is_overdue": is_ov,
                "project_package": resolved_pkg,
                "mail_type": "Request For Information",
                "aconex_url": r[10]
            })

        # If target_pid is DP01 or All packages, incorporate Site Clarification Requests (SCRs)
        if not target_pid or target_pid == 'DP01':
            scr_where = [
                "(project_package = 'DP01' OR subject ILIKE '%MD01%' OR (project_package = 'Aedas Design Packages' AND subject ILIKE '%SCR%'))",
                "(mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')"
            ]
            scr_params = []
            if from_date and from_date.strip() and from_date.strip().lower() != 'all':
                scr_where.append("sent_date >= ?")
                scr_params.append(from_date.strip())
            if to_date and to_date.strip():
                scr_where.append("sent_date <= ?")
                scr_params.append(f"{to_date.strip()} 23:59:59")
            if overdue_only:
                scr_where.append("(is_overdue = true OR days_late > 0)")
            if company and company.strip() and company.lower() != "all":
                c_clean = company.strip()
                if c_clean.upper() == "ECG":
                    scr_where.append("LOWER(TRIM(to_organization)) = 'ecg'")
                elif "shaker-ecg" in c_clean.lower():
                    scr_where.append("to_organization ILIKE '%shaker-ecg%'")
                else:
                    scr_where.append("LOWER(TRIM(to_organization)) = LOWER(TRIM(?))")
                    scr_params.append(f"%{c_clean}%")
            if search and search.strip():
                s = f"%{search.strip()}%"
                scr_where.append("(mail_no ILIKE ? OR subject ILIKE ? OR from_organization ILIKE ? OR to_organization ILIKE ?)")
                scr_params.extend([s, s, s, s])

            scr_sql = f"""
                SELECT 
                    mail_no,
                    subject,
                    from_organization,
                    to_organization,
                    from_name,
                    sent_date::VARCHAR,
                    due_date::VARCHAR,
                    days_late,
                    is_overdue,
                    'DP01' as project_package,
                    COALESCE(aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A%22' || mail_no || '%22') AS aconex_url,
                    mail_type
                FROM fact_mail
                WHERE {' AND '.join(scr_where)}
                ORDER BY days_late DESC, sent_date DESC NULLS LAST
            """
            scr_rows = con.execute(scr_sql, scr_params).fetchall()
            for r in scr_rows:
                days_late = int(r[7] or 0)
                is_ov = bool(r[8] or days_late > 0)
                if is_ov:
                    total_overdue += 1
                    if days_late > max_delay:
                        max_delay = days_late

                to_org = r[3] or "Supervision Consultant"
                company_counts[to_org] = company_counts.get(to_org, 0) + 1
                project_counts['DP01'] = project_counts.get('DP01', 0) + 1

                all_rfis.append({
                    "mail_no": r[0],
                    "subject": r[1] or "-",
                    "from_org": r[2] or "-",
                    "to_org": to_org,
                    "from_name": r[4] or "-",
                    "sent_date": str(r[5])[:10] if r[5] else "-",
                    "due_date": str(r[6])[:10] if r[6] else "-",
                    "days_late": days_late,
                    "is_overdue": is_ov,
                    "project_package": "DP01",
                    "mail_type": r[11] or "Site Clarification Request",
                    "aconex_url": r[10]
                })

        # Sort all combined items by days_late DESC, sent_date DESC
        all_rfis.sort(key=lambda x: (x["days_late"], x["sent_date"]), reverse=True)

        # Filter all_rfis for table presentation based on SLA status
        eff_status = (status or "").strip().lower()
        if eff_status == "overdue" or overdue_only:
            filtered_rfis = [item for item in all_rfis if item["is_overdue"]]
        elif eff_status == "ontime":
            filtered_rfis = [item for item in all_rfis if not item["is_overdue"]]
        else:
            filtered_rfis = all_rfis

        total_filtered = len(filtered_rfis)
        paginated_rfis = filtered_rfis[offset: offset + limit]

        # Fetch master distinct companies list directly from fact_rfis
        master_comp_where = ["to_organization IS NOT NULL AND to_organization != ''"]
        master_comp_params = []
        if from_date and from_date.strip() and from_date.strip().lower() != 'all':
            master_comp_where.append("sent_date >= ?")
            master_comp_params.append(from_date.strip())
        master_companies_rows = con.execute(f"""
            SELECT DISTINCT to_organization 
            FROM fact_rfis 
            WHERE {' AND '.join(master_comp_where)}
            ORDER BY 1
        """, master_comp_params).fetchall()
        if target_pid:
            # When a specific project is selected (e.g. DP01), ONLY list companies that are relevant responding entities for that project!
            active_comps = set(extract_clean_orgs(list(company_counts.keys())))
            if target_pid == 'DP01':
                DP01_ALLOWED = {'Aedas Limited', 'ECG', 'Hill Inter', 'Modon Real Estate', 'Shaker Egypt', 'Shaker-ECG consortium RASELHEKMA'}
                active_comps = {c for c in active_comps if c in DP01_ALLOWED}
        else:
            # Overall master list across all projects
            active_comps = set(extract_clean_orgs(list(company_counts.keys())))
            active_comps.update(extract_clean_orgs(master_companies_rows))
        
        # Exclude contractors (senders) and non-responder entities so user only sees actual answering consultants/PMC/Client
        CONTRACTOR_KEYWORDS = ['orascom', 'hassan allam', 'ccc', 'innovo', 'redcon', 'cscec', 'trojan', 'metito', 'acc for engineering', 'consolidated', 'safegate', 'horema']
        filtered_comps = []
        for org in active_comps:
            low = org.lower()
            if any(k in low for k in CONTRACTOR_KEYWORDS):
                continue
            if len(org.strip()) > 1:
                filtered_comps.append(org.strip())
        master_companies = sorted(filtered_comps)

        pkg_rows = con.execute("SELECT project_id FROM dim_project_packages ORDER BY sort_order ASC").fetchall()
        all_pkg_ids = [p[0] for p in pkg_rows if p[0]]
        distinct_projects = [p for p in all_pkg_ids if p in project_counts or p == 'DP01'] + [p for p in sorted(list(project_counts.keys())) if p not in all_pkg_ids]

        return {
            "kpis": {
                "total_rfis": len(all_rfis),
                "overdue_rfis": total_overdue,
                "on_time_rfis": len(all_rfis) - total_overdue,
                "max_delay_days": max_delay
            },
            "rfis": paginated_rfis,
            "total_count": total_filtered,
            "limit": limit,
            "offset": offset,
            "available_companies": master_companies,
            "available_projects": distinct_projects
        }
    finally:
        con.close()

def generate_contractor_rfi_html(
    project_id: str,
    company: str,
    to_emails: list,
    cc_emails: list,
    items_to_report: list,
    overdue_count: int,
    max_delay: int
) -> str:
    """
    Renders an executive, responsive HTML email draft for Contractor RFIs and SCRs
    with dark-navy styling, KPI cards, colored delay badges, working Aconex hyperlinks,
    and contractual closeout notice.
    """
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")
    display_pkg = project_id if project_id and project_id.lower() != 'all' else 'All Active Packages'
    display_comp = company if company and company.lower() != 'all' else 'Responsible Consultant'

    to_str = ", ".join(to_emails) if to_emails else f"Engineering Team & Project Controls ({display_comp})"
    cc_str = ", ".join(cc_emails) if cc_emails else "Hill PMC & Supervision Management"

    total_items = len(items_to_report)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Official Contractual Notice: Contractor RFIs - {display_pkg}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; background-color: #f1f5f9; color: #0f172a; line-height: 1.5; }}
        .email-card {{ max-width: 980px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #cbd5e1; overflow: hidden; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08); }}
        .header-banner {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 26px 32px; color: #ffffff; }}
        .header-meta {{ font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 6px; }}
        .header-title {{ margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.3px; }}
        .header-sub {{ margin-top: 6px; font-size: 13px; color: #94a3b8; font-weight: 500; }}
        
        .routing-box {{ background: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 14px 32px; font-size: 12px; }}
        .routing-row {{ display: flex; margin-bottom: 4px; }}
        .routing-lbl {{ font-weight: 700; color: #475569; width: 60px; flex-shrink: 0; }}
        .routing-val {{ color: #0f172a; font-family: monospace; word-break: break-all; }}
        
        .kpi-grid {{ display: table; width: 100%; border-bottom: 2px solid #e2e8f0; background: #f8fafc; }}
        .kpi-cell {{ display: table-cell; width: 25%; padding: 16px 12px; text-align: center; border-right: 1px solid #e2e8f0; }}
        .kpi-cell:last-child {{ border-right: none; }}
        .kpi-num {{ font-size: 24px; font-weight: 800; color: #0f172a; font-family: monospace; }}
        .kpi-num-red {{ font-size: 24px; font-weight: 800; color: #dc2626; font-family: monospace; }}
        .kpi-lbl {{ font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
        
        .email-body {{ padding: 28px 32px; }}
        .intro-p {{ font-size: 13px; color: #334155; margin-top: 0; margin-bottom: 20px; line-height: 1.6; }}
        
        .section-header {{ background: #0f172a; color: #ffffff; padding: 10px 16px; border-radius: 6px; font-size: 13px; font-weight: 700; display: flex; justify-content: space-between; align-items: center; margin-top: 20px; margin-bottom: 10px; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 18px; }}
        .data-table th {{ background: #1e293b; color: #f8fafc; text-align: left; padding: 8px 10px; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.3px; }}
        .data-table td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
        .data-table tr:nth-child(even) {{ background: #f8fafc; }}
        .data-table tr:hover {{ background: #f1f5f9; }}
        
        .tag-late {{ background: #fef2f2; color: #b91c1c; font-weight: 700; padding: 2px 7px; border-radius: 4px; border: 1px solid #fecaca; font-size: 11px; white-space: nowrap; font-family: monospace; }}
        .tag-ok {{ background: #ecfdf5; color: #047857; font-weight: 700; padding: 2px 7px; border-radius: 4px; border: 1px solid #a7f3d0; font-size: 11px; white-space: nowrap; font-family: monospace; }}
        .tag-type {{ background: #e0f2fe; color: #0369a1; font-weight: 700; padding: 2px 6px; border-radius: 4px; border: 1px solid #bae6fd; font-size: 10px; font-family: monospace; }}
        .link-aconex {{ color: #0284c7; font-weight: 700; text-decoration: none; font-family: monospace; }}
        .link-aconex:hover {{ text-decoration: underline; color: #0369a1; }}
        
        .notice-box {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 16px 20px; font-size: 12px; color: #92400e; margin-top: 28px; line-height: 1.6; }}
        .footer-box {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; font-size: 11px; color: #64748b; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="email-card">
        <!-- Header Banner -->
        <div class="header-banner">
            <div class="header-meta">Ras El Hekma Project Controls &amp; Governance</div>
            <h1 class="header-title">CONTRACTOR RFI &amp; TECHNICAL CLARIFICATION NOTICE</h1>
            <div class="header-sub">
                Project Package: <strong style="color: #ffffff;">{display_pkg}</strong> &bull; Responsible Consultant: <strong style="color: #ffffff;">{display_comp}</strong>
            </div>
        </div>

        <!-- Email Routing -->
        <div class="routing-box">
            <div class="routing-row">
                <span class="routing-lbl">TO:</span>
                <span class="routing-val">{to_str}</span>
            </div>
            <div class="routing-row" style="margin-bottom: 0;">
                <span class="routing-lbl">CC:</span>
                <span class="routing-val">{cc_str}</span>
            </div>
        </div>

        <!-- KPI Metrics Grid -->
        <div class="kpi-grid">
            <div class="kpi-cell">
                <div class="kpi-num">{total_items}</div>
                <div class="kpi-lbl">Pending Submissions</div>
            </div>
            <div class="kpi-cell">
                <div class="kpi-num-red">{overdue_count}</div>
                <div class="kpi-lbl">Overdue Items</div>
            </div>
            <div class="kpi-cell">
                <div class="kpi-num-red">+{max_delay}d</div>
                <div class="kpi-lbl">Max Delay Recorded</div>
            </div>
            <div class="kpi-cell">
                <div class="kpi-num" style="font-size: 16px; font-weight: 700; color: #0284c7; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{display_comp}</div>
                <div class="kpi-lbl">Action Entity</div>
            </div>
        </div>

        <!-- Body Content -->
        <div class="email-body">
            <p class="intro-p">
                Dear <strong>{display_comp} Project &amp; Engineering Teams</strong>,<br><br>
                According to official Oracle Aconex project controls records generated on <strong>{now_str}</strong>, the following Contractor Requests For Information (RFIs) and Technical Clarifications for <strong>{display_pkg}</strong> require immediate review and technical response determination.
                All records include direct 1-click Aconex hyperlinks for rapid access.
            </p>

            <div class="section-header">
                <span>Contractor RFIs &amp; Clarification Register ({total_items} Total)</span>
                <span style="font-size: 11px; font-weight: normal; color: #cbd5e1;">Oracle Aconex Live Register</span>
            </div>

            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 20%;">RFI / SCR No</th>
                        <th style="width: 34%;">Subject</th>
                        <th style="width: 22%;">Originator &rarr; Target</th>
                        <th style="width: 12%;">Due Date</th>
                        <th style="width: 12%; text-align: center;">Status</th>
                    </tr>
                </thead>
                <tbody>
    """

    for r in items_to_report[:50]:
        days_late = r.get("days_late", 0)
        is_ov = r.get("is_overdue") or days_late > 0
        if is_ov:
            status_badge = f'<span class="tag-late">+{days_late}d Overdue</span>'
        else:
            status_badge = '<span class="tag-ok">Within SLA</span>'

        doc_type = r.get("mail_type", "RFI")
        type_pill = f'<span class="tag-type">{doc_type}</span> ' if "SCR" in str(doc_type) or "SCR" in str(r.get("mail_no", "")) else ''

        html += f"""
                    <tr>
                        <td>
                            {type_pill}
                            <a href="{r.get('aconex_url', '#')}" target="_blank" class="link-aconex">{r.get('mail_no', '-')}</a>
                            <div style="font-size: 10px; color: #64748b; font-family: monospace; margin-top: 2px;">Pkg: {r.get('project_package', display_pkg)}</div>
                        </td>
                        <td style="color: #1e293b; font-weight: 500;">
                            {r.get('subject', '-')}
                        </td>
                        <td>
                            <div style="font-weight: 600; font-size: 11px;">{r.get('from_org', '-')}</div>
                            <div style="font-size: 10px; color: #64748b; margin-top: 1px;">&rarr; <strong>{r.get('to_org', display_comp)}</strong></div>
                        </td>
                        <td style="font-family: monospace; font-size: 11px; white-space: nowrap;">
                            <div>{r.get('due_date', '-')}</div>
                            <div style="font-size: 10px; color: #94a3b8;">Sent: {r.get('sent_date', '-')}</div>
                        </td>
                        <td style="text-align: center;">{status_badge}</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
    """

    if len(items_to_report) > 50:
        html += f"""
            <div style="text-align: center; font-size: 11px; color: #64748b; margin-top: -10px; margin-bottom: 20px; font-style: italic;">
                Showing top 50 prioritized RFIs. {len(items_to_report) - 50} additional items are tracked in the live Oracle Aconex database.
            </div>
        """

    html += f"""
            <div class="notice-box">
                <strong>CONTRACTUAL ACTION REQUIRED:</strong><br>
                Contractors have submitted these technical queries for urgent site execution. Immediate review, determination, and formal reply submission via Oracle Aconex are requested before the close of this working week to mitigate schedule impacts, delay claims, and site work interruption.
            </div>
        </div>

        <!-- Footer -->
        <div class="footer-box">
            <div><strong>Ras El Hekma Project Management &amp; Controls Team</strong></div>
            <div>Hill International (PMC) &bull; Project Controls &amp; Engineering Supervision Oversight</div>
            <div style="margin-top: 4px; color: #94a3b8;">This automated notification is generated directly from Oracle Aconex Enterprise Project Controls Data.</div>
        </div>
    </div>
</body>
</html>
    """
    return html

def generate_rfi_remind_email(project_id: str, company: str, from_date: Optional[str] = None, to_date: Optional[str] = None, status: Optional[str] = None) -> dict:
    """
    Generates an official contractual reminder email for contractor RFIs addressed to a specific company
    for a given project package, pre-populating To and CC from the in-app RFI Remind Emails Matrix.
    """
    data = get_contractor_rfis_data(
        project_id=project_id,
        company=company,
        status=status,
        overdue_only=False,
        from_date=from_date,
        to_date=to_date,
        limit=200,
        offset=0
    )

    rfis = data.get("rfis", [])
    if status == 'overdue':
        items_to_report = [r for r in rfis if r["is_overdue"] or r["days_late"] > 0]
    elif status == 'ontime':
        items_to_report = [r for r in rfis if not r["is_overdue"] and r["days_late"] <= 0]
    else:
        overdue_rfis = [r for r in rfis if r["is_overdue"] or r["days_late"] > 0]
        items_to_report = overdue_rfis if overdue_rfis else rfis

    # Resolve To / CC from in-app matrix
    to_emails, cc_emails = dss.resolve_rfi_contacts(project_id, company)

    display_pkg = project_id if project_id and project_id.lower() != 'all' else 'All Active Packages'
    display_comp = company if company and company.lower() != 'all' else 'Responsible Consultant'

    subject = f"CONTRACTUAL NOTICE: Contractor RFIs Pending Determination - {display_pkg} - Action by {display_comp}"

    # Build plain text email body
    body_lines = [
        f"Dear {display_comp} Project & Engineering Team,",
        "",
        f"According to Oracle Aconex project controls tracking for Ras El Hekma Development ({display_pkg}), the following Contractor Request For Information (RFI) submissions require immediate technical resolution:",
        "",
        f"• Project Package: {display_pkg}",
        f"• Responsible Entity: {display_comp}",
        f"• Total Pending RFIs: {len(items_to_report)}",
        f"• Maximum Turnaround Delay: +{data['kpis']['max_delay_days']} Days",
        "",
        "Pending Deliverables Register:"
    ]

    for idx, r in enumerate(items_to_report[:30], 1):
        late_badge = f"[+{r['days_late']}d OVERDUE]" if r['days_late'] > 0 else "[Within SLA]"
        doc_type = r.get("mail_type", "RFI")
        type_prefix = f"[{doc_type}] " if "SCR" in str(doc_type) else ""
        body_lines.append(f"{idx}. {type_prefix}{r['mail_no']} | {r['from_org']} -> {r['to_org']} | {late_badge}")
        body_lines.append(f"   Subject: {r['subject']}")
        body_lines.append(f"   Sent: {r['sent_date']} | Due: {r['due_date']}")
        body_lines.append(f"   Aconex Link: {r['aconex_url']}")
        body_lines.append("")

    if len(items_to_report) > 30:
        body_lines.append(f"... and {len(items_to_report) - 30} additional RFIs recorded in live Oracle Aconex database.")
        body_lines.append("")

    body_lines.extend([
        "Contractual Action Notice:",
        "Contractors have highlighted these pending queries for site progression. Immediate determination and formal response submission via Oracle Aconex are requested before the close of this working week to mitigate schedule impacts and contractual claims.",
        "",
        "Best regards,",
        "PMC Project Controls Team | Hill International",
        "Ras El Hekma Development Project",
        "Live Controls Dashboard: http://localhost:8000"
    ])

    plain_body = "\n".join(body_lines)

    # Generate executive colored HTML email with hyperlinks
    html_email = generate_contractor_rfi_html(
        project_id=project_id,
        company=company,
        to_emails=to_emails,
        cc_emails=cc_emails,
        items_to_report=items_to_report,
        overdue_count=len(overdue_rfis),
        max_delay=data['kpis']['max_delay_days']
    )

    to_str = ",".join(to_emails)
    cc_str = ",".join(cc_emails)
    params = {}
    if cc_str:
        params['cc'] = cc_str
    params['subject'] = subject
    params['body'] = plain_body
    mailto_url = f"mailto:{to_str}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

    return {
        "project": display_pkg,
        "company": display_comp,
        "to_emails": to_emails,
        "cc_emails": cc_emails,
        "subject": subject,
        "body": plain_body,
        "body_html": html_email,
        "mailto_url": mailto_url,
        "rfis_count": len(items_to_report),
        "overdue_count": len(overdue_rfis),
        "max_delay_days": data['kpis']['max_delay_days']
    }

