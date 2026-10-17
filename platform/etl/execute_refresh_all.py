r"""
High-Speed Complete Ingestion Pipeline for Aconex Update Files
Utilizes python-calamine (Rust-powered Excel parser) and DuckDB parallel C++ engine.
Ingests all 15 official project export files in C:\Users\bimst\Downloads\ACONEX\Data\update\Up.
"""
import os
import glob
import re
import csv
import time
import sys
from datetime import datetime
from python_calamine import CalamineWorkbook
import duckdb

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
UP_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up"
SCRATCH_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\scratch"

def parse_date_val(val):
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

def process_mail_file(fpath, out_csv):
    fname = os.path.basename(fpath)
    t0 = time.time()
    wb = CalamineWorkbook.from_path(fpath)
    sheet = wb.get_sheet_by_name(wb.sheet_names[0])
    rows = sheet.to_python()
    
    header_found = False
    count = 0
    with open(out_csv, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.writer(out_f)
        for row in rows:
            if not header_found:
                if row and len(row) > 1 and row[1] == 'Mail No':
                    header_found = True
                continue
            if not row or len(row) <= 1 or not row[1] or str(row[1]).strip() == 'Mail No':
                continue
                
            mail_no = str(row[1]).strip()
            subject = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ''
            sent_date = parse_date_val(row[3]) if len(row) > 3 else ''
            from_name = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ''
            from_org = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ''
            to_org = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ''
            recipients = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ''
            status = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ''
            mail_type = str(row[9]).strip() if len(row) > 9 and row[9] is not None else ''
            response_status = str(row[10]).strip() if len(row) > 10 and row[10] is not None else ''
            ref_no = str(row[14]).strip() if len(row) > 14 and row[14] is not None else ''
            aconex_url = str(row[21]).strip() if len(row) > 21 and row[21] is not None else ''
            due_date = parse_date_val(row[48]) if len(row) > 48 else ''
            
            writer.writerow([
                mail_no, subject, sent_date, from_name, from_org,
                to_org, recipients, status, mail_type, response_status,
                ref_no, aconex_url, due_date
            ])
            count += 1
            
    print(f"  [Mail] Processed {fname}: {count:,} mails in {time.time()-t0:.2f}s")
    return count

def process_doc_file(fpath, out_csv):
    fname = os.path.basename(fpath)
    t0 = time.time()
    url_pattern = re.compile(r"trackingid=(\d+)&projectid=(\d+)")
    
    wb = CalamineWorkbook.from_path(fpath)
    sheet = wb.get_sheet_by_name(wb.sheet_names[0])
    rows = sheet.to_python()
    
    header_found = False
    count = 0
    with open(out_csv, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.writer(out_f)
        for row in rows:
            if not header_found:
                if row and row[0] == 'Document No':
                    header_found = True
                continue
            if not row or not row[0] or str(row[0]).strip() == 'Document No':
                continue
                
            doc_no = str(row[0]).strip()
            rev = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
            title = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ''
            rev_date = parse_date_val(row[3]) if len(row) > 3 and row[3] is not None else ''
            rev_source = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ''
            doc_type = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ''
            status = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ''
            discipline = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ''
            hyperlink = str(row[22]).strip() if len(row) > 22 and row[22] is not None else ''
            
            tracking_id, project_id = '', ''
            if hyperlink:
                m = url_pattern.search(hyperlink)
                if m:
                    tracking_id = m.group(1)
                    project_id = m.group(2)
            
            writer.writerow([doc_no, rev, title, rev_date, rev_source, doc_type, status, discipline, tracking_id, project_id, hyperlink])
            count += 1
            
    print(f"  [Doc] Processed {fname}: {count:,} documents in {time.time()-t0:.2f}s")
    return count

def run_pipeline():
    print("=" * 80)
    print("ACONEX COMPREHENSIVE REFRESH & DATABASE UPDATE")
    print("Source directory:", UP_DIR)
    print("Target Database:", DB_PATH)
    print("Started at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)
    t_global = time.time()
    
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=False)
    con.execute("PRAGMA threads=8;")
    con.execute("PRAGMA memory_limit='6GB';")
    
    # -------------------------------------------------------------------------
    # 1. Ingest Mail Excel Files (6 files)
    # -------------------------------------------------------------------------
    print("\n[1/6] Ingesting All ExportMailAll-*.xlsx Files...")
    mail_files = sorted(glob.glob(os.path.join(UP_DIR, "ExportMailAll-*.xlsx")))
    mail_csvs = []
    total_mails = 0
    for i, mf in enumerate(mail_files):
        out_csv = os.path.join(SCRATCH_DIR, f"mail_calamine_{i+1}.csv")
        mail_csvs.append(out_csv)
        total_mails += process_mail_file(mf, out_csv)
        
    print(f"  Total extracted mails: {total_mails:,}")
    mail_csv_list_sql = ", ".join([f"'{c.replace(chr(92), '/')}'" for c in mail_csvs])
    
    con.execute("""
    CREATE OR REPLACE TABLE mail_aconex_links (
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
    FROM read_csv([{mail_csv_list_sql}], header=false, ignore_errors=true);
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_mail_links_no ON mail_aconex_links(mail_no);")
    m_count = con.execute("SELECT count(*) FROM mail_aconex_links").fetchone()[0]
    print(f"  [OK] mail_aconex_links populated: {m_count:,} records.")
    
    # Rebuild fact_mail & fact_rfis
    con.execute("""
    CREATE OR REPLACE TABLE fact_mail AS
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
        due_date,
        CASE 
            WHEN status = 'Outstanding' AND due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP
            THEN DATEDIFF('day', due_date, CURRENT_TIMESTAMP)
            ELSE 0
        END AS days_late,
        CASE 
            WHEN status = 'Outstanding' AND due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP THEN TRUE
            ELSE FALSE 
        END AS is_overdue,
        CASE WHEN to_organization ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_inbound_to_hill,
        CASE WHEN from_organization ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_outbound_from_hill,
        aconex_url
    FROM mail_aconex_links;
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_mail_no ON fact_mail(mail_no);")
    
    con.execute("""
    CREATE OR REPLACE TABLE fact_rfis AS
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
        CASE 
            WHEN status = 'Outstanding' AND due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP THEN TRUE
            ELSE FALSE 
        END AS is_overdue,
        aconex_url
    FROM mail_aconex_links
    WHERE mail_type ILIKE '%Request for Information%' OR mail_type ILIKE '%RFI%' OR mail_no ILIKE '%RFI%';
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_fact_rfis_no ON fact_rfis(mail_no);")
    print(f"  [OK] Rebuilt fact_mail ({con.execute('SELECT count(*) FROM fact_mail').fetchone()[0]:,}) and fact_rfis ({con.execute('SELECT count(*) FROM fact_rfis').fetchone()[0]:,}).")
    
    # -------------------------------------------------------------------------
    # 2. Ingest Document Registers (4 files)
    # -------------------------------------------------------------------------
    print("\n[2/6] Ingesting All ExportDocs-*.xlsx Files...")
    doc_files = sorted(glob.glob(os.path.join(UP_DIR, "ExportDocs-*.xlsx")))
    doc_csvs = []
    total_docs = 0
    for i, df in enumerate(doc_files):
        out_csv = os.path.join(SCRATCH_DIR, f"docs_calamine_{i+1}.csv")
        doc_csvs.append(out_csv)
        total_docs += process_doc_file(df, out_csv)
        
    print(f"  Total extracted documents: {total_docs:,}")
    doc_csv_list_sql = ", ".join([f"'{c.replace(chr(92), '/')}'" for c in doc_csvs])
    
    con.execute("""
    CREATE OR REPLACE TABLE doc_aconex_links (
        document_no VARCHAR,
        revision VARCHAR,
        title VARCHAR,
        revision_date TIMESTAMP,
        review_source VARCHAR,
        doc_type VARCHAR,
        status VARCHAR,
        discipline VARCHAR,
        tracking_id VARCHAR,
        project_id VARCHAR,
        aconex_url VARCHAR
    );
    """)
    con.execute(f"""
    INSERT INTO doc_aconex_links
    SELECT 
        column00 AS document_no,
        column01 AS revision,
        column02 AS title,
        TRY_CAST(column03 AS TIMESTAMP) AS revision_date,
        column04 AS review_source,
        column05 AS doc_type,
        column06 AS status,
        column07 AS discipline,
        column08 AS tracking_id,
        column09 AS project_id,
        column10 AS aconex_url
    FROM read_csv([{doc_csv_list_sql}], header=false, ignore_errors=true);
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_aconex_links_doc ON doc_aconex_links(document_no);")
    
    # Rebuild dim_documents
    con.execute("""
    CREATE OR REPLACE TABLE dim_documents AS
    SELECT 
        document_no,
        title,
        doc_type,
        status,
        review_source AS review_status,
        revision,
        CAST(NULL AS VARCHAR) AS version_number,
        CAST(NULL AS VARCHAR) AS created_by,
        revision_date AS date_modified,
        revision_date,
        discipline AS raw_discipline,
        tracking_id,
        project_id,
        aconex_url,
        CASE 
            WHEN document_no ILIKE '%-MD01-%' OR document_no ILIKE '%MD01%' THEN 'DP01 - Area 1 Basement & Superstructure'
            WHEN document_no ILIKE '%-MD02-%' OR document_no ILIKE '%MD02%' THEN 'DP02 - Area 2 Basement & Superstructure'
            WHEN document_no ILIKE '%-MD03-%' OR document_no ILIKE '%MD03%' THEN 'DP03 - Buildings & Infrastructure'
            WHEN document_no ILIKE '%-MD04-%' OR document_no ILIKE '%MD04%' THEN 'DP04 - Buildings & Infrastructure'
            WHEN document_no ILIKE '%-MD05-%' OR document_no ILIKE '%MD05%' THEN 'DP05 - Buildings & Infrastructure'
            WHEN document_no ILIKE '%-MD06-%' OR document_no ILIKE '%MD06%' THEN 'DP06 - Buildings & Infrastructure'
            WHEN document_no ILIKE '%-MD07-%' OR document_no ILIKE '%MD07%' THEN 'DP07 - Buildings & Infrastructure'
            WHEN document_no ILIKE '%-SW00-%' OR document_no ILIKE '%SW00%' THEN 'Primary Infrastructure & Utility (Package A)'
            WHEN document_no ILIKE '%-AP00-%' OR document_no ILIKE '%AP00%' THEN 'VVIP Airport & Airside Development'
            WHEN document_no ILIKE '%-RR00-%' OR document_no ILIKE '%RR00%' THEN 'Ring Road Infrastructure'
            ELSE 'General Project Deliverables'
        END AS package_name,
        CASE 
            WHEN discipline IS NOT NULL AND length(trim(discipline)) > 0 THEN discipline
            WHEN document_no ILIKE '%-ST-%' OR document_no ILIKE '%-STR-%' OR title ILIKE '%Structure%' OR title ILIKE '%Reinforcement%' THEN 'Structural'
            WHEN document_no ILIKE '%-AR-%' OR document_no ILIKE '%-ARC-%' OR title ILIKE '%Architectural%' THEN 'Architectural'
            WHEN document_no ILIKE '%-ME-%' OR document_no ILIKE '%-MEC-%' OR title ILIKE '%Mechanical%' OR title ILIKE '%HVAC%' OR title ILIKE '%Plumbing%' THEN 'Mechanical'
            WHEN document_no ILIKE '%-EL-%' OR document_no ILIKE '%-ELE-%' OR title ILIKE '%Electrical%' THEN 'Electrical'
            WHEN document_no ILIKE '%-CV-%' OR document_no ILIKE '%-CIV-%' OR title ILIKE '%Civil%' THEN 'Civil'
            WHEN document_no ILIKE '%-ID-%' OR title ILIKE '%Interior%' THEN 'Interior Design'
            WHEN document_no ILIKE '%-BM-%' OR document_no ILIKE '%-BIM-%' OR title ILIKE '%BIM%' THEN 'BIM'
            WHEN document_no ILIKE '%-BR-%' OR title ILIKE '%Bridge%' THEN 'Bridges'
            WHEN document_no ILIKE '%-HS-%' OR document_no ILIKE '%-HSE-%' OR title ILIKE '%Safety%' OR title ILIKE '%HSE%' THEN 'HSE / Safety'
            WHEN document_no ILIKE '%-FS-%' OR title ILIKE '%Fire%' THEN 'Fire & Life Safety'
            ELSE 'Multi-Disciplinary / Other'
        END AS discipline_name
    FROM doc_aconex_links;
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_dim_doc_no ON dim_documents(document_no);")
    print(f"  [OK] Rebuilt dim_documents: {con.execute('SELECT count(*) FROM dim_documents').fetchone()[0]:,} records.")
    
    # -------------------------------------------------------------------------
    # 3. Ingest Workflow Status CSV & Summaries
    # -------------------------------------------------------------------------
    print("\n[3/6] Ingesting Workflow Status (1).csv...")
    wf_status_csv = os.path.join(UP_DIR, "Workflow Status (1).csv").replace("\\", "/")
    if os.path.exists(wf_status_csv):
        con.execute(f"""
        CREATE OR REPLACE TABLE fact_workflow_steps AS
        SELECT 
            trim(COALESCE(workflow_number, workflow_no)) AS workflow_no,
            trim(workflow_name) AS workflow_name,
            trim(workflow_status) AS workflow_status,
            trim(template) AS template,
            trim(step_name) AS step_name,
            trim(step_status) AS step_status,
            trim(step_outcome) AS step_outcome,
            trim(initiator_organization) AS initiator_organization,
            trim(assigned_to_organization) AS assigned_to_organization,
            trim(assigned_to_name) AS assigned_to_name,
            trim(CAST(document_no AS VARCHAR)) AS document_no,
            trim(CAST(document_revision AS VARCHAR)) AS document_revision,
            trim(CAST(document_version AS VARCHAR)) AS document_version,
            trim(CAST(document_title AS VARCHAR)) AS document_title,
            trim(CAST(reason_for_issue AS VARCHAR)) AS reason_for_issue,
            TRY_CAST(date_in AS TIMESTAMP) AS date_in,
            TRY_CAST(date_due AS TIMESTAMP) AS date_due,
            TRY_CAST(original_due_date AS TIMESTAMP) AS original_due_date,
            TRY_CAST(date_completed AS TIMESTAMP) AS date_completed,
            COALESCE(TRY_CAST(days_late AS INTEGER), 0) AS days_late,
            CASE WHEN step_status = 'Overdue' OR (step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP) THEN TRUE ELSE FALSE END AS is_overdue,
            CASE 
                WHEN step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP THEN
                    CASE 
                        WHEN DATEDIFF('day', TRY_CAST(date_due AS TIMESTAMP), CURRENT_TIMESTAMP) <= 7 THEN '1-7 Days Overdue'
                        WHEN DATEDIFF('day', TRY_CAST(date_due AS TIMESTAMP), CURRENT_TIMESTAMP) <= 14 THEN '8-14 Days Overdue'
                        WHEN DATEDIFF('day', TRY_CAST(date_due AS TIMESTAMP), CURRENT_TIMESTAMP) <= 30 THEN '15-30 Days Overdue'
                        ELSE '> 30 Days Overdue'
                    END
                ELSE 'On Time'
            END AS aging_bucket,
            CASE WHEN assigned_to_organization ILIKE '%Hill Inter%' AND (step_status = 'Overdue' OR (step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP)) THEN TRUE ELSE FALSE END AS is_owed_by_hill,
            CASE WHEN (NOT (assigned_to_organization ILIKE '%Hill Inter%')) AND (step_status = 'Overdue' OR (step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP)) THEN TRUE ELSE FALSE END AS is_owed_to_hill
        FROM read_csv_auto('{wf_status_csv}', header=true, ignore_errors=true)
        WHERE COALESCE(workflow_number, workflow_no) IS NOT NULL AND trim(COALESCE(workflow_number, workflow_no)) != '';
        """)
        print(f"  [OK] fact_workflow_steps updated: {con.execute('SELECT count(*) FROM fact_workflow_steps').fetchone()[0]:,} steps.")
        
        con.execute("""
        CREATE OR REPLACE TABLE fact_workflows AS
        SELECT 
            workflow_no,
            FIRST(workflow_name) AS workflow_name,
            FIRST(workflow_status) AS workflow_status,
            FIRST(initiator_organization) AS initiator_organization,
            FIRST(template) AS template,
            MIN(date_in) AS start_date,
            MAX(original_due_date) AS original_due_date,
            COUNT(*) AS total_steps,
            COUNT(CASE WHEN is_overdue THEN 1 END) AS overdue_steps_count,
            COUNT(CASE WHEN step_status = 'Completed' THEN 1 END) AS completed_steps_count,
            COUNT(DISTINCT document_no) AS documents_count,
            FIRST(CASE WHEN step_status IN ('Current', 'Overdue') THEN assigned_to_organization END) AS current_assigned_org,
            FIRST(CASE WHEN step_status IN ('Current', 'Overdue') THEN assigned_to_name END) AS current_assigned_user,
            FIRST(CASE WHEN step_status IN ('Current', 'Overdue') THEN step_name END) AS current_step_name
        FROM fact_workflow_steps
        GROUP BY workflow_no;
        """)
        print("  [OK] Rebuilt fact_workflows summary.")
        
    # -------------------------------------------------------------------------
    # 4. Ingest Transmittals & Responses
    # -------------------------------------------------------------------------
    print("\n[4/6] Ingesting Document Transmittals & Responses/Threads...")
    dt_csv = os.path.join(UP_DIR, "Document Transmittal Workflow (1).csv").replace("\\", "/")
    if os.path.exists(dt_csv):
        con.execute(f"""
        CREATE OR REPLACE TABLE fact_transmittal_lifecycle AS
        SELECT 
            trim(CAST(document_no AS VARCHAR)) AS document_no,
            trim(CAST(title AS VARCHAR)) AS document_title,
            trim(CAST(revision AS VARCHAR)) AS revision,
            trim(CAST(version_number AS VARCHAR)) AS version_number,
            trim(CAST(status AS VARCHAR)) AS doc_status,
            trim(transmittal_in_mail_no) AS transmittal_in_mail_no,
            TRY_CAST(transmittal_in_sent_date AS TIMESTAMP) AS transmittal_in_date,
            trim(transmittal_in_from_organization) AS submitted_by_org,
            trim(workflow_no) AS workflow_no,
            trim(workflow_status) AS workflow_status,
            trim(step_outcome) AS step_outcome,
            trim(transmitted_mail_no) AS transmitted_mail_no,
            TRY_CAST(transmitted_sent_date AS TIMESTAMP) AS transmitted_date,
            trim(transmitted_to_organization) AS transmitted_to_org,
            CASE 
                WHEN transmitted_sent_date IS NOT NULL AND transmittal_in_sent_date IS NOT NULL 
                THEN DATE_DIFF('day', TRY_CAST(transmittal_in_sent_date AS TIMESTAMP), TRY_CAST(transmitted_sent_date AS TIMESTAMP))
                ELSE NULL 
            END AS turnaround_days,
            CASE 
                WHEN transmitted_mail_no IS NOT NULL AND trim(transmitted_mail_no) != '' THEN 'Completed & Distributed'
                WHEN workflow_no IS NOT NULL THEN 'In Review Workflow'
                ELSE 'Received / Pending Action'
            END AS lifecycle_stage
        FROM read_csv_auto('{dt_csv}', header=true, ignore_errors=true)
        WHERE document_no IS NOT NULL;
        """)
        print(f"  [OK] fact_transmittal_lifecycle updated: {con.execute('SELECT count(*) FROM fact_transmittal_lifecycle').fetchone()[0]:,} rows.")
        
    resp_csv = os.path.join(UP_DIR, "Mail Response (2).csv").replace("\\", "/")
    thread_csv = os.path.join(UP_DIR, "Mail Thread (2).csv").replace("\\", "/")
    source_sqls = []
    if os.path.exists(resp_csv):
        source_sqls.append(f"SELECT trim(mail_no) AS mail_no, trim(response_mail_no) AS response_mail_no, trim(response_from_organization) AS response_from_organization, trim(response_from_name) AS response_from_name, TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date, trim(response_subject) AS response_subject, trim(response_reply_type) AS response_reply_type, trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id FROM read_csv_auto('{resp_csv}', header=true, ignore_errors=true) WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''")
    if os.path.exists(thread_csv):
        source_sqls.append(f"SELECT trim(mail_no) AS mail_no, trim(response_mail_no) AS response_mail_no, trim(response_from_organization) AS response_from_organization, trim(response_from_name) AS response_from_name, TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date, trim(response_subject) AS response_subject, trim(response_reply_type) AS response_reply_type, trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id FROM read_csv_auto('{thread_csv}', header=true, ignore_errors=true) WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''")
    
    if source_sqls:
        union_sql = " UNION ALL ".join(source_sqls)
        con.execute(f"""
        CREATE OR REPLACE TABLE fact_mail_responses AS
        WITH combined AS ({union_sql})
        SELECT DISTINCT * FROM combined;
        """)
        print(f"  [OK] fact_mail_responses updated: {con.execute('SELECT count(*) FROM fact_mail_responses').fetchone()[0]:,} responses.")

    # -------------------------------------------------------------------------
    # 5. Rebuild Materialized Analytics Views
    # -------------------------------------------------------------------------
    print("\n[5/6] Refreshing Lookahead & Aggregated Performance Views...")
    con.execute("""
    CREATE OR REPLACE TABLE agg_lookahead AS
    SELECT 
        workflow_no,
        step_name,
        document_no,
        document_title,
        assigned_to_organization,
        assigned_to_name,
        date_due,
        DATEDIFF('day', CURRENT_TIMESTAMP, date_due) AS days_until_due
    FROM fact_workflow_steps
    WHERE step_status != 'Completed' AND date_due >= CURRENT_TIMESTAMP
    ORDER BY date_due ASC;
    """)
    
    con.execute("""
    CREATE OR REPLACE TABLE agg_user_workload AS
    SELECT 
        assigned_to_organization AS org_name,
        assigned_to_name AS user_name,
        COUNT(CASE WHEN step_status IN ('Current', 'Overdue') THEN 1 END) AS total_active_tasks,
        COUNT(CASE WHEN is_overdue THEN 1 END) AS overdue_tasks,
        COUNT(CASE WHEN is_overdue AND aging_bucket = '1-7 Days Overdue' THEN 1 END) AS overdue_1_to_7_days,
        COUNT(CASE WHEN is_overdue AND aging_bucket = '8-14 Days Overdue' THEN 1 END) AS overdue_8_to_14_days,
        COUNT(CASE WHEN is_overdue AND aging_bucket = '15-30 Days Overdue' THEN 1 END) AS overdue_15_to_30_days,
        COUNT(CASE WHEN is_overdue AND aging_bucket = '> 30 Days Overdue' THEN 1 END) AS overdue_over_30_days,
        MAX(days_late) AS max_delay_days,
        ROUND(AVG(CASE WHEN is_overdue THEN days_late ELSE NULL END), 1) AS avg_delay_days
    FROM fact_workflow_steps
    WHERE assigned_to_name IS NOT NULL AND trim(assigned_to_name) != ''
    GROUP BY assigned_to_organization, assigned_to_name
    ORDER BY overdue_tasks DESC;
    """)
    
    con.execute("""
    CREATE OR REPLACE TABLE agg_step_bottlenecks AS
    SELECT 
        step_name,
        assigned_to_organization AS org_name,
        COUNT(*) AS total_occurrences,
        COUNT(CASE WHEN step_status IN ('Current', 'Overdue') THEN 1 END) AS currently_pending,
        COUNT(CASE WHEN is_overdue THEN 1 END) AS currently_overdue,
        ROUND(AVG(CASE WHEN is_overdue THEN days_late ELSE NULL END), 1) AS avg_overdue_days,
        ROUND(COUNT(CASE WHEN step_status = 'Completed' AND days_late <= 0 THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN step_status = 'Completed' THEN 1 END), 0), 1) AS on_time_completion_pct
    FROM fact_workflow_steps
    WHERE step_name IS NOT NULL
    GROUP BY step_name, assigned_to_organization
    ORDER BY currently_overdue DESC;
    """)
    
    con.execute("""
    CREATE OR REPLACE TABLE agg_org_scorecard AS
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
    print("  [OK] Materialized agg_org_scorecard, agg_user_workload, agg_step_bottlenecks, agg_lookahead.")

    # -------------------------------------------------------------------------
    # 6. Cleanup Temporary Scratch CSVs
    # -------------------------------------------------------------------------
    print("\n[6/6] Cleaning up scratch CSV cache...")
    for c in mail_csvs + doc_csvs:
        try:
            if os.path.exists(c):
                os.remove(c)
        except Exception:
            pass
            
    con.close()
    elapsed = time.time() - t_global
    print("\n" + "=" * 80)
    print(f"DATABASE UPDATE FINISHED SUCCESSFULLY IN {elapsed:.2f} SECONDS!")
    print("=" * 80)

if __name__ == "__main__":
    run_pipeline()
