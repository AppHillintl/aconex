"""
High-Performance Ingestion Script for All Aconex Mail Files (with Live Hyperlinks)
Extracts Mail No, Subject, Dates, Orgs, Status, Type, and exact Aconex Hyperlink
from ExportMailAll-*.xlsx into DuckDB mail_aconex_links, fact_mail, fact_rfis, and fact_mail_threads.
"""
import os
import glob
import re
import csv
import time
import openpyxl
import duckdb
from concurrent.futures import ProcessPoolExecutor

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
UP_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up"
SCRATCH_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\scratch"

def safe_drop(con, name):
    try:
        con.execute(f"DROP VIEW IF EXISTS {name}")
    except Exception:
        pass
    try:
        con.execute(f"DROP TABLE IF EXISTS {name}")
    except Exception:
        pass

def parse_date_str(val):
    if not val:
        return ''
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    s = str(val).strip()
    if '/' in s:
        parts = s.split('/')
        if len(parts) == 3:
            day, month, year = parts[0].zfill(2), parts[1].zfill(2), parts[2]
            return f"{year}-{month}-{day}"
    return s

def parse_mail_worker(args):
    file_path, out_csv = args
    fname = os.path.basename(file_path)
    print(f"  [Worker] Starting {fname}...")
    t0 = time.time()
    
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    
    count = 0
    header_found = False
    col_map = {}
    with open(out_csv, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.writer(out_f)
        for row in ws.iter_rows(values_only=True):
            if not header_found:
                if row and any(c and 'Mail No' in str(c) for c in row):
                    header_found = True
                    for c_i, c_val in enumerate(row):
                        if c_val:
                            col_map[str(c_val).strip()] = c_i
                continue
            
            mail_col = col_map.get('Mail No', 1)
            if not row or len(row) <= mail_col or not row[mail_col] or str(row[mail_col]).strip() == 'Mail No':
                continue
                
            mail_no = str(row[mail_col]).strip()
            
            def get_cell(col_name, fallback_idx=None, default=''):
                idx = col_map.get(col_name, fallback_idx)
                if idx is not None and 0 <= idx < len(row) and row[idx] is not None:
                    return str(row[idx]).strip()
                return default

            subject = get_cell('Subject', 2)
            
            date_idx = col_map.get('Date', 3)
            sent_date = parse_date_str(row[date_idx]) if date_idx is not None and date_idx < len(row) else ''
            
            from_name = get_cell('From', 4)
            from_org = get_cell('From Organization', 5)
            to_org = get_cell('To Organization', 6)
            recipients = get_cell('Recipients', 7)
            status = get_cell('Status', 8)
            mail_type = get_cell('Type', 9)
            response_status = get_cell('Response', 10) or get_cell('Response Status')
            ref_no = get_cell('Reference Number', 14)
            aconex_url = get_cell('Hyperlink', 21)
            if not aconex_url:
                aconex_url = f"/api/aconex/mail?mail_no={mail_no}"
                
            due_idx = col_map.get('Due', 48)
            due_date = parse_date_str(row[due_idx]) if due_idx is not None and due_idx < len(row) else ''
            
            writer.writerow([
                mail_no, subject, sent_date, from_name, from_org,
                to_org, recipients, status, mail_type, response_status,
                ref_no, aconex_url, due_date
            ])
            count += 1
            
    wb.close()
    elapsed = time.time() - t0
    print(f"  [Worker] Finished {fname}: {count:,} mails in {elapsed:.1f}s")
    return count

def main():
    print("=" * 80)
    print("INGESTING ALL ACONEX MAILS & LIVE HYPERLINKS")
    print("=" * 80)
    t_global = time.time()
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    
    mail_files = sorted(glob.glob(os.path.join(UP_DIR, "ExportMailAll-*.xlsx")))
    print(f"Found {len(mail_files)} Mail Excel files:")
    for mf in mail_files:
        print(f"  - {os.path.basename(mf)} ({os.path.getsize(mf)/1024/1024:.2f} MB)")
    if not mail_files:
        print("[SKIP] No ExportMailAll-*.xlsx files present. Keeping existing mail tables.")
        return
        
    tasks = []
    out_csvs = []
    for i, mf in enumerate(mail_files):
        out_csv = os.path.join(SCRATCH_DIR, f"mail_part_{i+1}.csv")
        out_csvs.append(out_csv)
        if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0 or os.path.getmtime(out_csv) < os.path.getmtime(mf):
            tasks.append((mf, out_csv))
        
    if tasks:
        print(f"Parsing {len(tasks)} updated mail Excel files...")
        with ProcessPoolExecutor(max_workers=min(len(tasks), 6)) as pool:
            results = list(pool.map(parse_mail_worker, tasks))
        print(f"\n[OK] Extracted {sum(results):,} total mails across {len(tasks)} files.")
    else:
        print(f"[OK] All {len(mail_files)} parsed CSV files exist in scratch. Skipping Excel re-parse.")
    
    con = duckdb.connect(DB_PATH, read_only=False)
    
    print("\nLoading parsed mails into DuckDB mail_aconex_links...")
    csv_list_sql = ", ".join([f"'{c.replace(chr(92), '/')}'" for c in out_csvs])
    safe_drop(con, "mail_aconex_links")
    con.execute("""
    CREATE TABLE mail_aconex_links (
        mail_no VARCHAR,
        subject VARCHAR,
        sent_date TIMESTAMP,
        from_name VARCHAR,
        from_organization VARCHAR,
        to_organization VARCHAR,
        recipients VARCHAR,
        status VARCHAR,
        mail_type VARCHAR,
        response_status VARCHAR,
        reference_number VARCHAR,
        aconex_url VARCHAR,
        due_date TIMESTAMP
    );
    """)
    con.execute(f"""
    INSERT INTO mail_aconex_links
    SELECT DISTINCT
        column00 AS mail_no,
        column01 AS subject,
        TRY_CAST(column02 AS TIMESTAMP) AS sent_date,
        column03 AS from_name,
        column04 AS from_organization,
        column05 AS to_organization,
        column06 AS recipients,
        column07 AS status,
        column08 AS mail_type,
        column09 AS response_status,
        column10 AS reference_number,
        column11 AS aconex_url,
        TRY_CAST(column12 AS TIMESTAMP) AS due_date
    FROM read_csv([{csv_list_sql}], header=false, ignore_errors=true);
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_mail_links_no ON mail_aconex_links(mail_no);")
    cnt_links = con.execute("SELECT count(*) FROM mail_aconex_links").fetchone()[0]
    print(f"  [OK] mail_aconex_links populated with {cnt_links:,} distinct mails with hyperlinks.")
    
    # -------------------------------------------------------------------------
    # Rebuild fact_mail with Live Hyperlinks
    # -------------------------------------------------------------------------
    print("\nRebuilding fact_mail with Live Hyperlinks & Aging Metrics...")
    safe_drop(con, "fact_mail")
    con.execute("""
    CREATE TABLE fact_mail AS
    SELECT 
        mail_no,
        mail_type,
        subject,
        reference_number,
        from_name,
        from_organization,
        to_organization,
        recipients,
        status,
        'Inbox' AS mail_box,
        sent_date,
        CASE 
            WHEN mail_type = 'Letter' AND due_date IS NULL THEN sent_date + INTERVAL 14 DAY
            ELSE due_date
        END AS due_date,
        CASE 
            WHEN mail_type = 'Letter' AND status NOT IN ('Closed-Out', 'Closed', 'Responded', 'Closed Out')
                 AND COALESCE(due_date, sent_date + INTERVAL 14 DAY) < CURRENT_TIMESTAMP
            THEN DATEDIFF('day', COALESCE(due_date, sent_date + INTERVAL 14 DAY), CURRENT_TIMESTAMP)
            WHEN status = 'Outstanding' AND due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP
            THEN DATEDIFF('day', due_date, CURRENT_TIMESTAMP)
            ELSE 0
        END AS days_late,
        CASE 
            WHEN mail_type = 'Letter' AND status NOT IN ('Closed-Out', 'Closed', 'Responded', 'Closed Out')
                 AND COALESCE(due_date, sent_date + INTERVAL 14 DAY) < CURRENT_TIMESTAMP THEN TRUE
            WHEN status = 'Outstanding' AND due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP THEN TRUE
            ELSE FALSE 
        END AS is_overdue,
        CASE WHEN to_organization ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_inbound_to_hill,
        CASE WHEN from_organization ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_outbound_from_hill,
        aconex_url
    FROM mail_aconex_links;
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_mail_no ON fact_mail(mail_no);")
    print(f"  [OK] fact_mail updated: {con.execute('SELECT count(*) FROM fact_mail').fetchone()[0]:,} mails.")
    
    # -------------------------------------------------------------------------
    # Rebuild fact_rfis with Live Hyperlinks
    # -------------------------------------------------------------------------
    print("\nRebuilding fact_rfis with Live Hyperlinks...")
    safe_drop(con, "fact_rfis")
    con.execute("""
    CREATE TABLE fact_rfis AS
    WITH ranked AS (
        SELECT 
            mail_no,
            subject,
            from_organization,
            to_organization,
            from_name,
            recipients,
            status,
            sent_date,
            due_date,
            CASE 
                WHEN status = 'Outstanding' AND due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP
                THEN DATEDIFF('day', due_date, CURRENT_TIMESTAMP)
                ELSE 0
            END AS days_late,
            CASE WHEN from_organization ILIKE '%Hill Inter%' THEN 'Sent' ELSE 'Received' END AS direction,
            CASE 
                WHEN status = 'Outstanding' AND due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP THEN TRUE
                ELSE FALSE 
            END AS is_overdue,
            aconex_url,
            ROW_NUMBER() OVER (
                PARTITION BY mail_no 
                ORDER BY CASE WHEN aconex_url LIKE '%MiniURL%' THEN 1 ELSE 2 END, sent_date DESC NULLS LAST
            ) as rn
        FROM mail_aconex_links
        WHERE (mail_type ILIKE '%Request for Information%' OR mail_no ILIKE '%-RFI-%') AND from_organization NOT ILIKE '%Hill Inter%'
    )
    SELECT 
        mail_no, subject, from_organization, to_organization, from_name,
        recipients, status, sent_date, due_date, days_late, direction, is_overdue, aconex_url
    FROM ranked WHERE rn = 1;
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_rfis_no ON fact_rfis(mail_no);")
    print(f"  [OK] fact_rfis updated: {con.execute('SELECT count(*) FROM fact_rfis').fetchone()[0]:,} RFIs.")
    
    # -------------------------------------------------------------------------
    # Ingest Mail Thread (2).csv
    # -------------------------------------------------------------------------
    thread_csv = os.path.join(UP_DIR, "Mail Thread (2).csv").replace("\\", "/")
    if os.path.exists(thread_csv):
        print("\nIngesting Mail Thread (2).csv into fact_mail_threads & fact_mail_responses...")
        safe_drop(con, "fact_mail_threads")
        con.execute(f"""
        CREATE TABLE fact_mail_threads AS
        SELECT 
            trim(mail_no) AS mail_no,
            trim(from_organization) AS from_organization,
            trim(to_organization) AS to_organization,
            trim(response_mail_no) AS response_mail_no,
            trim(response_from_organization) AS response_from_organization,
            trim(response_to_organization) AS response_to_organization,
            TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date,
            trim(response_subject) AS response_subject,
            trim(response_reply_type) AS response_reply_type,
            trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id
        FROM read_csv_auto('{thread_csv}', header=true, ignore_errors=true)
        WHERE mail_no IS NOT NULL;
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_thread_mail_no ON fact_mail_threads(mail_no);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_thread_resp_mail_no ON fact_mail_threads(response_mail_no);")
        
        # Also refresh fact_mail_responses
        safe_drop(con, "fact_mail_responses")
        con.execute("""
        CREATE TABLE fact_mail_responses AS
        SELECT DISTINCT
            mail_no,
            response_mail_no,
            response_from_organization,
            '' AS response_from_name,
            response_sent_date,
            response_subject,
            response_reply_type,
            parent_mail_id
        FROM fact_mail_threads
        WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != '';
        """)
        print(f"  [OK] fact_mail_threads: {con.execute('SELECT count(*) FROM fact_mail_threads').fetchone()[0]:,} thread relations.")
        
    # -------------------------------------------------------------------------
    # Ensure agg_lookahead has aconex_url directly
    # -------------------------------------------------------------------------
    print("\nEnsuring agg_lookahead has direct Aconex Hyperlinks...")
    safe_drop(con, "agg_lookahead")
    con.execute("""
    CREATE TABLE agg_lookahead AS
    SELECT 
        s.workflow_no,
        s.step_name,
        s.document_no,
        s.document_title,
        s.assigned_to_organization,
        s.assigned_to_name,
        s.date_due,
        DATEDIFF('day', CURRENT_TIMESTAMP, s.date_due) AS days_until_due,
        l.aconex_url
    FROM fact_workflow_steps s
    LEFT JOIN doc_aconex_links l ON s.document_no = l.document_no
    WHERE s.step_status != 'Completed' AND s.date_due >= CURRENT_TIMESTAMP
    ORDER BY s.date_due ASC;
    """)
    print("  [OK] agg_lookahead rebuilt with direct Aconex URLs.")
    
    # -------------------------------------------------------------------------
    # Refresh agg_org_scorecard
    # -------------------------------------------------------------------------
    print("\nRefreshing agg_org_scorecard with updated correspondence...")
    safe_drop(con, "agg_org_scorecard")
    con.execute("""
    CREATE TABLE agg_org_scorecard AS
    WITH wf_agg AS (
        SELECT 
            assigned_to_organization AS org_name,
            COUNT(*) AS total_review_steps,
            COUNT(CASE WHEN step_status = 'Completed' THEN 1 END) AS completed_steps,
            COUNT(CASE WHEN is_overdue THEN 1 END) AS overdue_steps,
            COUNT(CASE WHEN step_status IN ('Current', 'Overdue') THEN 1 END) AS active_pending_steps,
            ROUND(AVG(CASE WHEN step_status = 'Completed' THEN days_late ELSE NULL END), 1) AS avg_completed_delay_days,
            ROUND(AVG(CASE WHEN is_overdue THEN days_late ELSE NULL END), 1) AS avg_overdue_delay_days,
            ROUND(COUNT(CASE WHEN step_status = 'Completed' AND days_late <= 0 THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN step_status = 'Completed' THEN 1 END), 0), 1) AS step_sla_compliance_pct
        FROM fact_workflow_steps
        WHERE assigned_to_organization IS NOT NULL AND assigned_to_organization != ''
        GROUP BY assigned_to_organization
    ),
    mail_agg AS (
        SELECT 
            to_organization AS org_name,
            COUNT(*) AS open_action_mails,
            COUNT(CASE WHEN is_overdue THEN 1 END) AS overdue_mails,
            ROUND(AVG(CASE WHEN is_overdue THEN days_late ELSE NULL END), 1) AS avg_mail_delay_days
        FROM fact_mail
        WHERE to_organization IS NOT NULL
        GROUP BY to_organization
    ),
    contractor_quality AS (
        SELECT 
            initiator_organization AS org_name,
            COUNT(*) AS total_submittals,
            COUNT(CASE WHEN step_outcome ILIKE '%A - Approved%' THEN 1 END) AS code_a_count,
            COUNT(CASE WHEN step_outcome ILIKE '%B - Approved with Comments%' THEN 1 END) AS code_b_count,
            COUNT(CASE WHEN step_outcome ILIKE '%C - Revise and Resubmit%' THEN 1 END) AS code_c_count,
            COUNT(CASE WHEN step_outcome ILIKE '%D - Rejected%' THEN 1 END) AS code_d_count,
            ROUND((COUNT(CASE WHEN step_outcome ILIKE '%A - Approved%' THEN 1 END) + COUNT(CASE WHEN step_outcome ILIKE '%B - Approved with Comments%' THEN 1 END)) * 100.0 / NULLIF(COUNT(*), 0), 1) AS approval_rate_pct
        FROM fact_workflow_steps
        WHERE initiator_organization IS NOT NULL AND step_outcome IS NOT NULL AND trim(step_outcome) != ''
        GROUP BY initiator_organization
    )
    SELECT 
        COALESCE(w.org_name, m.org_name, q.org_name) AS org_name,
        o.org_category,
        o.is_pmc,
        COALESCE(w.active_pending_steps, 0) AS active_pending_steps,
        COALESCE(w.overdue_steps, 0) AS overdue_steps,
        COALESCE(w.completed_steps, 0) AS completed_steps,
        COALESCE(w.step_sla_compliance_pct, 0.0) AS step_sla_compliance_pct,
        COALESCE(w.avg_overdue_delay_days, 0.0) AS avg_step_delay_days,
        COALESCE(m.open_action_mails, 0) AS open_action_mails,
        COALESCE(m.overdue_mails, 0) AS overdue_mails,
        COALESCE(q.total_submittals, 0) AS total_submittals_initiated,
        COALESCE(q.approval_rate_pct, 0.0) AS submittal_approval_rate_pct,
        COALESCE(q.code_c_count, 0) AS code_c_revise_count,
        COALESCE(q.code_d_count, 0) AS code_d_rejected_count
    FROM wf_agg w
    FULL OUTER JOIN mail_agg m ON w.org_name = m.org_name
    FULL OUTER JOIN contractor_quality q ON COALESCE(w.org_name, m.org_name) = q.org_name
    LEFT JOIN dim_organizations o ON COALESCE(w.org_name, m.org_name, q.org_name) = o.org_name
    ORDER BY overdue_steps DESC;
    """)
    print("  [OK] agg_org_scorecard refreshed.")
    
    con.close()
    
    # Cached scratch CSVs preserved for fast incremental updates
        
    print("\n" + "=" * 80)
    print(f"MAIL INGESTION & HYPERLINK INTEGRATION COMPLETED IN {time.time()-t_global:.2f}s!")
    print("=" * 80)

if __name__ == "__main__":
    main()
