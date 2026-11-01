import os
import glob
import re
import time
import openpyxl
import duckdb

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
UP_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up"

print("="*80)
print("STARTING FRESH DATA INGESTION FROM:", UP_DIR)
print("="*80)

t0 = time.time()
con = duckdb.connect(DB_PATH, read_only=False)

# -----------------------------------------------------------------------------
# 1. Ingest Mail Responses & Threads (Mail Response (2).csv & Mail Thread (2).csv)
# -----------------------------------------------------------------------------
resp_csv = os.path.join(UP_DIR, "Mail Response (2).csv").replace("\\", "/")
thread_csv = os.path.join(UP_DIR, "Mail Thread (2).csv").replace("\\", "/")

if os.path.exists(resp_csv) and os.path.exists(thread_csv):
    print("\n[1/3] Updating fact_mail_responses from Mail Response (2) & Mail Thread (2)...")
    con.execute(f"""
    CREATE OR REPLACE TABLE fact_mail_responses AS
    WITH combined AS (
        SELECT 
            trim(mail_no) AS mail_no,
            trim(response_mail_no) AS response_mail_no,
            trim(response_from_organization) AS response_from_organization,
            trim(response_from_name) AS response_from_name,
            TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date,
            trim(response_subject) AS response_subject,
            trim(response_reply_type) AS response_reply_type,
            trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id
        FROM read_csv_auto('{resp_csv}', header=True, ignore_errors=true)
        WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''
        UNION ALL
        SELECT 
            trim(mail_no) AS mail_no,
            trim(response_mail_no) AS response_mail_no,
            trim(response_from_organization) AS response_from_organization,
            trim(response_from_name) AS response_from_name,
            TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date,
            trim(response_subject) AS response_subject,
            trim(response_reply_type) AS response_reply_type,
            trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id
        FROM read_csv_auto('{thread_csv}', header=True, ignore_errors=true)
        WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''
    )
    SELECT DISTINCT * FROM combined;
    """)
    cnt = con.execute("SELECT count(*) FROM fact_mail_responses").fetchone()[0]
    print(f"  [OK] Updated fact_mail_responses: {cnt:,} response/thread relations.")

# -----------------------------------------------------------------------------
# 2. Ingest Workflow Review Steps & Status
# -----------------------------------------------------------------------------
wf_steps_csv = os.path.join(UP_DIR, "Workflow Documents Review Outcome (1).csv").replace("\\", "/")
wf_status_csv = os.path.join(UP_DIR, "Workflow Status (1).csv").replace("\\", "/")

if os.path.exists(wf_steps_csv):
    print("\n[2/3] Updating fact_workflow_steps from Workflow Documents Review Outcome (1)...")
    con.execute(f"""
    CREATE OR REPLACE TABLE fact_workflow_steps AS
    SELECT 
        trim(workflow_no) AS workflow_no,
        trim(workflow_name) AS workflow_name,
        trim(workflow_status) AS workflow_status,
        trim(template) AS template,
        trim(step_name) AS step_name,
        trim(step_status) AS step_status,
        trim(step_outcome) AS step_outcome,
        trim(initiator_organization) AS initiator_organization,
        trim(assigned_to_organization) AS assigned_to_organization,
        trim(assigned_to_name) AS assigned_to_name,
        trim(document_no) AS document_no,
        trim(document_revision) AS document_revision,
        trim(document_version) AS document_version,
        trim(document_title) AS document_title,
        trim(comments) AS reason_for_issue,
        TRY_CAST(date_in AS TIMESTAMP) AS date_in,
        TRY_CAST(date_due AS TIMESTAMP) AS date_due,
        TRY_CAST(original_due_date AS TIMESTAMP) AS original_due_date,
        TRY_CAST(date_completed AS TIMESTAMP) AS date_completed,
        COALESCE(TRY_CAST(days_late AS INTEGER), 0) AS days_late,
        CASE WHEN step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP THEN TRUE ELSE FALSE END AS is_overdue,
        CASE 
            WHEN step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP THEN
                CASE 
                    WHEN DATEDIFF('day', TRY_CAST(date_due AS TIMESTAMP), CURRENT_TIMESTAMP) <= 7 THEN '1-7 Days'
                    WHEN DATEDIFF('day', TRY_CAST(date_due AS TIMESTAMP), CURRENT_TIMESTAMP) <= 14 THEN '8-14 Days'
                    WHEN DATEDIFF('day', TRY_CAST(date_due AS TIMESTAMP), CURRENT_TIMESTAMP) <= 30 THEN '15-30 Days'
                    ELSE '> 30 Days'
                END
            ELSE 'On Track'
        END AS aging_bucket,
        CASE WHEN trim(assigned_to_organization) ILIKE '%Hill%' AND step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP THEN TRUE ELSE FALSE END AS is_owed_by_hill,
        CASE WHEN trim(assigned_to_organization) NOT ILIKE '%Hill%' AND step_status != 'Completed' AND TRY_CAST(date_due AS TIMESTAMP) < CURRENT_TIMESTAMP THEN TRUE ELSE FALSE END AS is_owed_to_hill
    FROM read_csv_auto('{wf_steps_csv}', header=True, ignore_errors=true)
    WHERE workflow_no IS NOT NULL AND trim(workflow_no) != '';
    """)
    wf_cnt = con.execute("SELECT count(*) FROM fact_workflow_steps").fetchone()[0]
    print(f"  [OK] Updated fact_workflow_steps: {wf_cnt:,} review steps.")

# -----------------------------------------------------------------------------
# 3. Ingest ExportDocs-20261011_13-48_*.xlsx (Document Register with Hyperlinks)
# -----------------------------------------------------------------------------
doc_files = sorted(glob.glob(os.path.join(UP_DIR, "ExportDocs-20261011_13-48_*.xlsx")))
if doc_files:
    print(f"\n[3/3] Ingesting {len(doc_files)} Document Register Excel files with Hyperlinks...")
    url_pattern = re.compile(r"trackingid=(\d+)&projectid=(\d+)")
    
    # Staging temp table
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
    
    total_docs = 0
    for f in doc_files:
        fname = os.path.basename(f)
        print(f"  Reading {fname}...")
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb.active
        
        batch = []
        header_found = False
        for row in ws.iter_rows(values_only=True):
            if not header_found:
                if row and row[0] == 'Document No':
                    header_found = True
                continue
            if not row or not row[0]:
                continue
                
            doc_no = str(row[0]).strip()
            rev = str(row[1]).strip() if row[1] is not None else None
            title = str(row[2]).strip() if row[2] is not None else None
            rev_date = str(row[4]).strip() if len(row) > 4 and row[4] else None
            dtype = str(row[6]).strip() if len(row) > 6 and row[6] else None
            status = str(row[7]).strip() if len(row) > 7 and row[7] else None
            discipline = str(row[8]).strip() if len(row) > 8 and row[8] else None
            hyperlink = str(row[43]).strip() if len(row) > 43 and row[43] else None
            
            tracking_id, project_id = None, None
            if hyperlink:
                m = url_pattern.search(hyperlink)
                if m:
                    tracking_id = m.group(1)
                    project_id = m.group(2)
                    
            batch.append((doc_no, rev, title, rev_date, None, dtype, status, discipline, tracking_id, project_id, hyperlink))
            if len(batch) >= 10000:
                con.executemany("INSERT INTO doc_aconex_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
                total_docs += len(batch)
                batch = []
        if batch:
            con.executemany("INSERT INTO doc_aconex_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
            total_docs += len(batch)
            
    print(f"  [OK] Ingested doc_aconex_links: {total_docs:,} documents.")
    
    # Update dim_documents
    con.execute("""
    CREATE OR REPLACE TABLE dim_documents AS
    SELECT 
        d.document_no,
        d.title,
        d.doc_type,
        d.discipline AS discipline_name,
        d.status,
        d.status AS review_status,
        d.revision,
        d.revision_date,
        'Active' AS package_name,
        l.aconex_url
    FROM doc_aconex_links d
    LEFT JOIN doc_aconex_links l ON d.document_no = l.document_no;
    """)

# -----------------------------------------------------------------------------
# 4. Rebuild Lookahead & Summary Indexes
# -----------------------------------------------------------------------------
print("\nRebuilding Lookahead Aggregations...")
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

con.close()
print("\n" + "="*80)
print(f"DATABASE UPDATE COMPLETED IN {time.time()-t0:.2f}s!")
print("="*80)
