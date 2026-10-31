import os
import json
import uuid
import datetime
import duckdb
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")
REQUESTS_STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "refresh_requests.json")
DEFAULT_TARGET_EMAIL = "MohamedMeneaem@hillintl.com"

# Ensure config directory exists
os.makedirs(os.path.dirname(REQUESTS_STORAGE_PATH), exist_ok=True)

def get_cairo_time():
    """Returns the current Cairo local time (UTC+2 standard)."""
    # UTC + 2 hours
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    cairo_now = utc_now + datetime.timedelta(hours=2)
    return cairo_now

def check_business_hours(dt=None):
    """
    Checks if given datetime is within official working hours:
    Sunday (6) through Thursday (3), 08:00 to 18:00 (Cairo time).
    Friday (4) and Saturday (5) are weekend.
    """
    if dt is None:
        dt = get_cairo_time()
    
    weekday = dt.weekday() # Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    is_workday = weekday in (6, 0, 1, 2, 3)
    hour = dt.hour
    minute = dt.minute
    time_float = hour + (minute / 60.0)
    is_workhours = (8.0 <= time_float < 18.0)
    
    is_in_hours = is_workday and is_workhours

    # Calculate next business day opening
    if is_in_hours:
        sla_text = "Live Processing (Typical response: within 30-45 minutes)"
        status_label = "WITHIN_BUSINESS_HOURS"
    else:
        status_label = "AFTER_HOURS_QUEUED"
        # Determine next business day
        days_ahead = 1
        check_day = (weekday + 1) % 7
        while check_day not in (6, 0, 1, 2, 3):
            days_ahead += 1
            check_day = (check_day + 1) % 7
        
        target_date = dt.date() + datetime.timedelta(days=days_ahead)
        day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][target_date.weekday()]
        sla_text = f"Queued for next business day: {day_name} at 08:00 AM Cairo Time"

    return {
        "is_in_hours": is_in_hours,
        "status_label": status_label,
        "cairo_time_str": dt.strftime("%A, %Y-%m-%d %H:%M:%S"),
        "sla_text": sla_text
    }

def validate_refresh_claim(package_id: str, category: str, reference_no: str, user_notes: str):
    """
    Performs automated technical verification against DuckDB:
    - Checks latest records for the given package
    - Checks if the reference number exists and what its status/date is
    - Synthesizes an automated validation finding & recommended action
    """
    findings = {
        "package_found": False,
        "package_title": package_id,
        "current_db_cutoff": "N/A",
        "total_letters": 0,
        "total_rfis": 0,
        "total_docs": 0,
        "ref_item_found": False,
        "ref_item_details": None,
        "verdict": "GENERAL_REFRESH_REQUESTED",
        "verdict_title": "General Package Refresh Request",
        "recommended_action": "Execute Quick Delta Sync (30-45s) to pull recent updates."
    }

    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        # 1. Check Package Summary
        proj = con.execute("""
            SELECT project_id, project_title, contractor_name, contract_no,
                   total_letters, total_rfis, total_documents
            FROM agg_project_summary 
            WHERE project_id = ? OR project_name = ?
            LIMIT 1
        """, [package_id, package_id]).fetchone()

        if proj:
            findings["package_found"] = True
            findings["package_title"] = proj[1] or proj[0]
            findings["contractor"] = proj[2] or "N/A"
            findings["contract_no"] = proj[3] or "-"
            findings["total_letters"] = proj[4] or 0
            findings["total_rfis"] = proj[5] or 0
            findings["total_docs"] = proj[6] or 0

        # Check cutoff date
        try:
            cutoff_row = con.execute("SELECT MAX(sent_date) FROM fact_mail").fetchone()
            if cutoff_row and cutoff_row[0]:
                findings["current_db_cutoff"] = str(cutoff_row[0])[:10]
        except Exception:
            pass

        # 2. Check Reference Number if provided
        clean_ref = (reference_no or "").strip()
        if clean_ref:
            # Check fact_mails
            try:
                mail_match = con.execute("""
                    SELECT mail_no, subject, mail_type, sent_date, from_organization, to_organization, status, project_package
                    FROM fact_mail
                    WHERE mail_no ILIKE ? OR subject ILIKE ?
                    ORDER BY sent_date DESC LIMIT 1
                """, [f"%{clean_ref}%", f"%{clean_ref}%"]).fetchone()

                if mail_match:
                    findings["ref_item_found"] = True
                    findings["ref_item_details"] = {
                        "type": "Mail / Correspondence",
                        "mail_number": mail_match[0],
                        "subject": mail_match[1],
                        "mail_type": mail_match[2],
                        "mail_date": str(mail_match[3])[:10] if mail_match[3] else "N/A",
                        "sender": mail_match[4],
                        "recipient": mail_match[5],
                        "status": mail_match[6],
                        "response_status": mail_match[7]
                    }
                    findings["verdict"] = "RECORD_ALREADY_PRESENT"
                    findings["verdict_title"] = "Record Already Present in Database"
                    findings["recommended_action"] = f"Record '{mail_match[0]}' exists in analytical DB (Date: {mail_match[3]}, Status: {mail_match[6]}). Verify if user refers to a newer revision/reply not yet exported."
            except Exception as e:
                pass

            # If not in mail, check documents
            if not findings["ref_item_found"]:
                try:
                    doc_match = con.execute("""
                        SELECT document_no, title, revision, status, discipline_name, date_modified
                        FROM dim_documents
                        WHERE document_no ILIKE ? OR title ILIKE ?
                        ORDER BY date_modified DESC LIMIT 1
                    """, [f"%{clean_ref}%", f"%{clean_ref}%"]).fetchone()

                    if doc_match:
                        findings["ref_item_found"] = True
                        findings["ref_item_details"] = {
                            "type": "Document / Drawing",
                            "doc_number": doc_match[0],
                            "title": doc_match[1],
                            "revision": doc_match[2],
                            "status": doc_match[3],
                            "discipline": doc_match[4],
                            "date_modified": str(doc_match[5])[:10] if doc_match[5] else "N/A"
                        }
                        findings["verdict"] = "RECORD_ALREADY_PRESENT"
                        findings["verdict_title"] = "Document Already Present in Database"
                        findings["recommended_action"] = f"Document '{doc_match[0]}' exists (Rev: {doc_match[2]}, Status: {doc_match[3]}). Check if a newer revision was submitted after cutoff {findings['current_db_cutoff']}."
                except Exception as e:
                    pass

            if not findings["ref_item_found"]:
                findings["verdict"] = "CONFIRMED_NEED_REFRESH"
                findings["verdict_title"] = "Item Not Found in Current Database (Delta Sync Required)"
                findings["recommended_action"] = f"Reference '{clean_ref}' is NOT in local DuckDB as of cutoff {findings['current_db_cutoff']}. Recommended: Run Quick Delta Sync to pull latest Aconex package."

        con.close()
    except Exception as e:
        findings["error"] = str(e)

    return findings

def format_official_response_draft(ticket: dict) -> str:
    """Formats an executive reply message on behalf of Mohamed Meneaem."""
    name = ticket.get("requester_name", "Valued Colleague")
    pkg = ticket.get("package_id", "Project Package")
    ref = ticket.get("reference_no", "")
    findings = ticket.get("validation_findings", {})
    verdict = findings.get("verdict_title", "Refresh Request Processed")
    rec_action = findings.get("recommended_action", "Data refresh initiated.")
    cutoff = findings.get("current_db_cutoff", "Current Cutoff")

    ref_mention = f" regarding reference item '{ref}'" if ref else ""

    draft = (
        f"Dear {name},\n\n"
        f"Thank you for contacting the Hill International Project Controls Desk regarding package [{pkg}]{ref_mention}.\n\n"
        f"We have received and logged your data verification request under Ticket ID: #{ticket.get('ticket_id')}.\n\n"
        f"Technical Assessment & Action Taken:\n"
        f"• Validation Result: {verdict}\n"
        f"• Current Analytical Database Cutoff: {cutoff}\n"
        f"• Action Taken: {rec_action}\n\n"
        f"Our automated delta extraction routines run during official business hours (Sunday to Thursday, 08:00 AM - 06:00 PM). "
        f"The dashboard analytics for your requested items are being updated accordingly.\n\n"
        f"Please do not hesitate to contact our Project Controls team if you need any additional clarification.\n\n"
        f"Best regards,\n\n"
        f"Mohamed Meneaem\n"
        f"Project Controls & Document Management\n"
        f"Hill International, Inc. - Ras El Hekma Project\n"
        f"Email: MohamedMeneaem@hillintl.com"
    )
    return draft

def format_notification_email_html(ticket: dict) -> str:
    """Generates the executive HTML notification email sent to Mohamed Meneaem."""
    tid = ticket.get("ticket_id")
    name = ticket.get("requester_name")
    email = ticket.get("requester_email")
    pkg = ticket.get("package_id")
    cat = ticket.get("category")
    ref = ticket.get("reference_no") or "None specified"
    notes = ticket.get("user_notes")
    cairo_time = ticket.get("cairo_time_str")
    in_hours = ticket.get("is_in_hours")
    sla = ticket.get("sla_text")
    findings = ticket.get("validation_findings", {})
    draft = ticket.get("official_response_draft", "")

    badge_hours = (
        '<span style="background-color: #10b981; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px;">Within Business Hours</span>'
        if in_hours else
        '<span style="background-color: #f59e0b; color: #000000; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px;">After-Hours (Queued for 08:00 AM Next Day)</span>'
    )

    ref_details_html = ""
    if findings.get("ref_item_found") and findings.get("ref_item_details"):
        d = findings["ref_item_details"]
        ref_details_html = f"""
        <div style="background-color: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 12px; color: #cbd5e1;">
            <strong style="color: #38bdf8;">Found Record in Analytical DB:</strong><br/>
            • <b>Type:</b> {d.get('type')}<br/>
            • <b>Identifier:</b> {d.get('mail_number') or d.get('doc_number')}<br/>
            • <b>Subject/Title:</b> {d.get('subject') or d.get('title')}<br/>
            • <b>Date:</b> {d.get('mail_date') or d.get('date_modified')}<br/>
            • <b>Status:</b> {d.get('status')}
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Data Refresh Request #{tid}</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0b1120; color: #f1f5f9; margin: 0; padding: 24px;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #1e293b; border-radius: 14px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0284c7 0%, #1e1b4b 100%); padding: 22px 26px; border-bottom: 2px solid #38bdf8;">
                <div style="font-size: 11px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: #bae6fd;">Ras El Hekma Project Controls • Hill International</div>
                <h2 style="margin: 6px 0 0 0; font-size: 20px; color: #ffffff;">User Data Refresh & Out-of-Date Report</h2>
                <div style="margin-top: 6px; font-size: 12px; color: #e0f2fe;">Ticket ID: <b>#{tid}</b> &nbsp;|&nbsp; {badge_hours}</div>
            </div>

            <!-- Content Body -->
            <div style="padding: 24px;">

                <!-- 1. Requester Information -->
                <div style="background-color: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 14px 18px; margin-bottom: 18px;">
                    <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #94a3b8; margin-bottom: 8px;">Requester Information</div>
                    <table style="width: 100%; font-size: 13px; color: #f1f5f9; border-collapse: collapse;">
                        <tr><td style="width: 130px; color: #94a3b8; padding: 3px 0;">Name:</td><td><b>{name}</b></td></tr>
                        <tr><td style="color: #94a3b8; padding: 3px 0;">Email:</td><td><a href="mailto:{email}" style="color: #38bdf8; text-decoration: none;">{email}</a></td></tr>
                        <tr><td style="color: #94a3b8; padding: 3px 0;">Package / Scope:</td><td><b>{pkg}</b></td></tr>
                        <tr><td style="color: #94a3b8; padding: 3px 0;">Module Category:</td><td><span style="background: #334155; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{cat}</span></td></tr>
                        <tr><td style="color: #94a3b8; padding: 3px 0;">Item Reference:</td><td style="font-family: monospace; color: #facc15;">{ref}</td></tr>
                        <tr><td style="color: #94a3b8; padding: 3px 0;">Timestamp:</td><td style="font-size: 11px; color: #94a3b8;">{cairo_time}</td></tr>
                        <tr><td style="color: #94a3b8; padding: 3px 0;">SLA Processing:</td><td style="color: #34d399; font-weight: bold; font-size: 12px;">{sla}</td></tr>
                    </table>
                </div>

                <!-- 2. What User Found Out-of-Date -->
                <div style="background-color: #1e1b4b; border-left: 4px solid #818cf8; border-radius: 8px; padding: 14px 18px; margin-bottom: 18px;">
                    <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #c7d2fe; margin-bottom: 6px;">Reported Out-of-Date Discrepancy</div>
                    <div style="font-size: 13px; line-height: 1.5; color: #ffffff; white-space: pre-wrap;">{notes}</div>
                </div>

                <!-- 3. Automated Technical AI & DB Validation -->
                <div style="background-color: #0b1120; border: 1px solid #0284c7; border-radius: 10px; padding: 16px 18px; margin-bottom: 18px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #38bdf8;">Automated Analytical Engine Validation</span>
                        <span style="font-size: 11px; font-weight: bold; background: rgba(14,165,233,0.15); color: #38bdf8; border: 1px solid rgba(14,165,233,0.3); padding: 2px 8px; border-radius: 4px;">Cutoff: {findings.get('current_db_cutoff')}</span>
                    </div>

                    <div style="font-size: 13px; color: #f1f5f9; margin-bottom: 6px;">
                        <b>Assessment Verdict:</b> <span style="color: #facc15; font-weight: bold;">{findings.get('verdict_title')}</span>
                    </div>

                    <div style="font-size: 12.5px; color: #cbd5e1; line-height: 1.4; margin-bottom: 6px;">
                        <b>Recommended Action:</b> {findings.get('recommended_action')}
                    </div>

                    {ref_details_html}
                </div>

                <!-- 4. Ready-to-Send Official Response Draft on Behalf of Mohamed Meneaem -->
                <div style="background-color: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 14px 18px;">
                    <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #94a3b8; margin-bottom: 8px;">
                        Pre-Composed Official Response Draft (On behalf of Mohamed Meneaem)
                    </div>
                    <div style="background-color: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 12px; font-size: 12px; font-family: monospace; color: #e2e8f0; white-space: pre-wrap; line-height: 1.4;">{draft}</div>
                    <div style="margin-top: 10px; text-align: right;">
                        <a href="mailto:{email}?subject=RE: Refresh Request %23{tid} - {pkg}&body={urllib_quote(draft)}" 
                           style="display: inline-block; background-color: #0284c7; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 8px; box-shadow: 0 4px 10px rgba(2,132,199,0.3);">
                            ✉️ Click to Reply to Requester in Outlook
                        </a>
                    </div>
                </div>

            </div>

            <!-- Footer -->
            <div style="background-color: #0f172a; padding: 14px 24px; border-top: 1px solid #334155; font-size: 11px; color: #64748b; text-align: center;">
                Aconex PMC Control Platform • Ras El Hekma Project Controls<br/>
                Operating Schedule: Sunday – Thursday (08:00 AM – 06:00 PM Cairo Time)
            </div>

        </div>
    </body>
    </html>
    """
    return html

def urllib_quote(text: str) -> str:
    import urllib.parse
    return urllib.parse.quote(text)

def record_and_dispatch_request(data: dict):
    """
    Logs the user refresh request, performs validation, saves to store,
    and dispatches executive email to Mohamed Meneaem.
    """
    cairo_now = get_cairo_time()
    bh_info = check_business_hours(cairo_now)
    ticket_id = f"REF-{cairo_now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"

    package_id = (data.get("package_id") or "General").strip()
    category = (data.get("category") or "General Refresh").strip()
    reference_no = (data.get("reference_no") or "").strip()
    user_notes = (data.get("user_notes") or "").strip()
    requester_name = (data.get("requester_name") or "Platform User").strip()
    requester_email = (data.get("requester_email") or "").strip()

    # Perform automated validation
    findings = validate_refresh_claim(package_id, category, reference_no, user_notes)

    ticket = {
        "ticket_id": ticket_id,
        "created_at": cairo_now.isoformat(),
        "cairo_time_str": bh_info["cairo_time_str"],
        "is_in_hours": bh_info["is_in_hours"],
        "sla_text": bh_info["sla_text"],
        "status": "PROCESSED_IN_HOURS" if bh_info["is_in_hours"] else "QUEUED_AFTER_HOURS",
        "requester_name": requester_name,
        "requester_email": requester_email,
        "package_id": package_id,
        "category": category,
        "reference_no": reference_no,
        "user_notes": user_notes,
        "validation_findings": findings,
        "official_response_draft": ""
    }

    ticket["official_response_draft"] = format_official_response_draft(ticket)

    # 1. Save ticket to JSON store
    tickets = []
    if os.path.exists(REQUESTS_STORAGE_PATH):
        try:
            with open(REQUESTS_STORAGE_PATH, "r", encoding="utf-8") as f:
                tickets = json.load(f)
        except Exception:
            tickets = []
    
    tickets.insert(0, ticket)
    # Keep last 200 tickets
    tickets = tickets[:200]
    with open(REQUESTS_STORAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2, ensure_ascii=False)

    # 2. Save ticket in DuckDB table if available
    try:
        con_w = duckdb.connect(DB_PATH, read_only=False)
        con_w.execute("""
            CREATE TABLE IF NOT EXISTS user_refresh_requests (
                ticket_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMP,
                requester_name VARCHAR,
                requester_email VARCHAR,
                package_id VARCHAR,
                category VARCHAR,
                reference_no VARCHAR,
                user_notes VARCHAR,
                is_in_hours BOOLEAN,
                status VARCHAR,
                verdict VARCHAR,
                recommended_action VARCHAR
            )
        """)
        con_w.execute("""
            INSERT OR REPLACE INTO user_refresh_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ticket["ticket_id"],
            cairo_now.replace(tzinfo=None),
            ticket["requester_name"],
            ticket["requester_email"],
            ticket["package_id"],
            ticket["category"],
            ticket["reference_no"],
            ticket["user_notes"],
            ticket["is_in_hours"],
            ticket["status"],
            findings.get("verdict_title", ""),
            findings.get("recommended_action", "")
        ])
        con_w.close()
    except Exception as e:
        print("Warning: Could not write to user_refresh_requests DuckDB table:", e)

    # 3. Dispatch Email to MohamedMeneaem@hillintl.com
    email_html = format_notification_email_html(ticket)
    dispatch_status = dispatch_email_notification(
        to_email=DEFAULT_TARGET_EMAIL,
        subject=f"[PMC Controls Refresh Request] Ticket #{ticket_id}: {package_id} ({bh_info['status_label']})",
        html_body=email_html,
        requester_email=requester_email
    )
    ticket["dispatch_status"] = dispatch_status

    return ticket

def dispatch_email_notification(to_email: str, subject: str, html_body: str, requester_email: str = None) -> dict:
    """
    Attempts direct SMTP delivery if configured, and saves an .eml draft file for Outlook.
    """
    result = {"status": "pending", "method": "none", "details": ""}
    
    # Check if SMTP is configured in DuckDB
    smtp_info = None
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        smtp_info = con.execute("SELECT smtp_host, smtp_port, smtp_user, smtp_password, sender_email, sender_name, use_tls, is_active FROM smtp_settings WHERE is_active LIMIT 1").fetchone()
        con.close()
    except Exception:
        pass

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = to_email
    if requester_email:
        msg["Cc"] = requester_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Attempt SMTP
    if smtp_info and smtp_info[0]:
        try:
            msg["From"] = f"{smtp_info[5]} <{smtp_info[4]}>" if smtp_info[5] else smtp_info[4]
            server = smtplib.SMTP(smtp_info[0], smtp_info[1], timeout=10)
            if smtp_info[6]:
                server.starttls()
            if smtp_info[2] and smtp_info[3]:
                server.login(smtp_info[2], smtp_info[3])
            server.send_message(msg)
            server.quit()
            result = {"status": "sent", "method": "SMTP", "details": f"Dispatched directly via SMTP to {to_email}"}
            return result
        except Exception as e:
            result["details"] = f"SMTP Attempt Failed: {str(e)}. Fallback activated."

    # Save to disk as .eml / outgoing queue draft
    try:
        drafts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "email_queue")
        os.makedirs(drafts_dir, exist_ok=True)
        eml_filename = f"email_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.eml"
        eml_path = os.path.join(drafts_dir, eml_filename)
        with open(eml_path, "w", encoding="utf-8") as f:
            f.write(msg.as_string())
        result["status"] = "queued_eml"
        result["method"] = "DiskQueue & Outlook Draft"
        result["details"] = f"Email draft queued successfully at {eml_filename} for {to_email}"
    except Exception as e:
        result["status"] = "error"
        result["details"] = str(e)

    return result

def get_all_tickets():
    """Retrieves all logged refresh request tickets."""
    if os.path.exists(REQUESTS_STORAGE_PATH):
        try:
            with open(REQUESTS_STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []
