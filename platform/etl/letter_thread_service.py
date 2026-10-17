import os
import re
from datetime import datetime
import duckdb

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")

def get_db_connection():
    return duckdb.connect(DB_PATH, read_only=True)

def get_letter_thread_history(mail_no: str, reference_number: str = None) -> dict:
    """
    Extracts the complete chronological communication thread for a contractual Letter or Correspondence.
    Tracks each letter issued, actions taken at each step, involved organizations, references, and live Aconex hyperlinks.
    """
    con = get_db_connection()
    try:
        clean_m_no = (mail_no or '').strip()
        clean_ref = (reference_number or '').strip()

        # 1. Fetch initiator letter record
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

        m_key = init_row[0] if init_row else clean_m_no
        ref_key = init_row[2] if init_row else clean_ref
        subj_key = init_row[3] if init_row else ""

        # 2. Extract thread steps combining direct responses, reference_number matches, and thread tables
        query = """
            SELECT DISTINCT 
                m.mail_no, m.mail_type, m.from_organization, m.to_organization, m.from_name,
                m.sent_date, m.subject, m.status, COALESCE(m.reference_number, m.mail_no) as ref_no,
                COALESCE(l.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A' || m.mail_no) as aconex_url
            FROM fact_mail m
            LEFT JOIN mail_aconex_links l ON m.mail_no = l.mail_no
            WHERE m.mail_no = ?
               OR (m.reference_number = ? AND LENGTH(?) >= 4)
               OR (m.reference_number = ? AND LENGTH(?) >= 4)
               OR m.mail_no IN (
                   SELECT response_mail_no FROM fact_mail_threads 
                   WHERE mail_no = ? AND response_mail_no IS NOT NULL
               )
               OR m.mail_no IN (
                   SELECT mail_no FROM fact_mail_threads 
                   WHERE response_mail_no = ? AND response_mail_no IS NOT NULL
               )
            ORDER BY m.sent_date ASC NULLS LAST, m.mail_no ASC
        """
        raw_events = con.execute(query, [
            m_key, m_key, m_key, ref_key, ref_key, m_key, m_key
        ]).fetchall()

        if not raw_events and init_row:
            raw_events = [(
                init_row[0], init_row[1], init_row[4], init_row[5], init_row[6],
                init_row[7], init_row[3], init_row[9], init_row[2], init_row[11]
            )]

        # Classify each step's action and role in the contractual correspondence lifecycle
        thread_steps = []
        seen_mails = set()
        first_date = None
        latest_date = None
        has_official_response = False
        orgs_involved = set()

        for idx, ev in enumerate(raw_events, 1):
            e_mail, e_type, e_from, e_to, e_name, e_date, e_subj, e_st, e_ref, e_url = ev
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

            # Determine action taken & lifecycle phase
            action_taken = "Correspondence Logged"
            badge_color = "slate"
            icon = "mail"

            is_first_letter = (idx == 1) or (e_mail == m_key)
            is_hill_sender = "hill" in f_lower
            is_contractor_sender = any(c in f_lower for c in ["ccc", "orascom", "hassan allam", "acc", "innovo", "cscec", "sewedy", "trojan"])
            is_client_involved = any(c in t_lower or c in f_lower for c in ["modon", "employer", "client"])
            is_consultant = any(c in t_lower or c in f_lower for c in ["shaker", "ecg", "obmi", "dar", "egis", "aedas", "dewan"])

            if is_first_letter:
                if is_contractor_sender:
                    action_taken = "Contractor Formal Letter Issued"
                    badge_color = "sky"
                    icon = "send"
                elif is_hill_sender:
                    action_taken = "PMC Instruction / Notice Issued"
                    badge_color = "purple"
                    icon = "file-text"
                else:
                    action_taken = "Initial Letter Issued"
                    badge_color = "sky"
                    icon = "send"
            elif is_hill_sender and is_client_involved:
                action_taken = "Transmitted to Employer / Client"
                badge_color = "indigo"
                icon = "share-2"
            elif is_hill_sender and is_consultant:
                action_taken = "Forwarded to Consultant for Review"
                badge_color = "purple"
                icon = "forward"
            elif is_consultant and "hill" in t_lower:
                action_taken = "Consultant Technical Review / Advice"
                badge_color = "amber"
                icon = "help-circle"
            elif is_hill_sender and is_contractor_sender:
                action_taken = "Official PMC Response / Determination"
                badge_color = "emerald"
                icon = "check-circle-2"
                has_official_response = True
            elif "re:" in subj_lower or "response" in subj_lower or "reply" in subj_lower:
                action_taken = "Formal Reply / Counter Letter Issued"
                badge_color = "emerald"
                icon = "corner-down-left"
                has_official_response = True
            elif e_from == e_to or not e_to or e_to == '-':
                action_taken = "Internal PMC Review / Action Item"
                badge_color = "slate"
                icon = "clipboard-check"
            else:
                action_taken = "Follow-up Coordination"
                badge_color = "slate"
                icon = "mail"

            days_from_start = 0
            if first_date and e_date:
                try:
                    delta = (e_date - first_date).days
                    days_from_start = max(0, delta)
                except Exception:
                    pass

            thread_steps.append({
                "step_number": len(thread_steps) + 1,
                "mail_no": e_mail,
                "mail_type": e_type or "Letter",
                "reference_number": e_ref or e_mail,
                "from_org": e_from or "-",
                "to_org": e_to or "-",
                "from_name": e_name or "",
                "sent_date": str(e_date)[:10] if e_date else "-",
                "sent_timestamp": str(e_date) if e_date else None,
                "subject": e_subj or "-",
                "status": e_st or ("Closed" if has_official_response else "Open"),
                "action_taken": action_taken,
                "badge_color": badge_color,
                "icon": icon,
                "days_from_start": days_from_start,
                "aconex_url": e_url
            })

        turnaround_days = 0
        if first_date and latest_date:
            try:
                turnaround_days = max(0, (latest_date - first_date).days)
            except Exception:
                pass

        overall_status = "Responded" if has_official_response else ("Open" if not init_row or init_row[9] == 'Outstanding' else (init_row[9] or "Open"))

        return {
            "mail_no": m_key,
            "reference_number": ref_key or m_key,
            "mail_type": init_row[1] if init_row else "Letter",
            "subject": init_row[3] if init_row else (thread_steps[0]["subject"] if thread_steps else ""),
            "originator_org": init_row[4] if init_row else (thread_steps[0]["from_org"] if thread_steps else ""),
            "recipient_org": init_row[5] if init_row else (thread_steps[0]["to_org"] if thread_steps else ""),
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
