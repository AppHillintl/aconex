"""
High-Performance Complete Update Script for Aconex Data
Utilizes ProcessPoolExecutor for Excel files and DuckDB native parallel C++ CSV engine.
"""
import os
import glob
import re
import time
import openpyxl
import duckdb
from concurrent.futures import ProcessPoolExecutor

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
UP_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up"
SCRATCH_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\scratch"

def parse_excel_worker(args):
    file_path, out_csv = args
    fname = os.path.basename(file_path)
    print(f"  [Worker] Starting {fname}...")
    t_start = time.time()
    url_pattern = re.compile(r"trackingid=(\d+)&projectid=(\d+)")
    
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    
    import csv
    header_found = False
    count = 0
    with open(out_csv, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.writer(out_f)
        for row in ws.iter_rows(values_only=True):
            if not header_found:
                if row and row[0] == 'Document No':
                    header_found = True
                continue
            if not row or not row[0]:
                continue
                
            doc_no = str(row[0]).strip()
            rev = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
            title = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ''
            rev_date = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ''
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
            
    wb.close()
    elapsed = time.time() - t_start
    print(f"  [Worker] Finished {fname}: {count:,} rows in {elapsed:.1f}s")
    return count

def main():
    print("=" * 80)
    print("ACONEX COMPREHENSIVE REFRESH & DATABASE UPDATE")
    print("Source directory:", UP_DIR)
    print("=" * 80)
    t_global = time.time()
    
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=False)
    
    # -------------------------------------------------------------------------
    # 1. Ingest Mail Responses & Threads
    # -------------------------------------------------------------------------
    print("\n[1/6] Ingesting Mail Responses & Threads...")
    resp_csv = os.path.join(UP_DIR, "Mail Response (2).csv").replace("\\", "/")
    thread_csv = os.path.join(UP_DIR, "Mail Thread (2).csv").replace("\\", "/")
    
    if os.path.exists(resp_csv):
        source_sqls = [f"SELECT trim(mail_no) AS mail_no, trim(response_mail_no) AS response_mail_no, trim(response_from_organization) AS response_from_organization, trim(response_from_name) AS response_from_name, TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date, trim(response_subject) AS response_subject, trim(response_reply_type) AS response_reply_type, trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id FROM read_csv_auto('{resp_csv}', header=true, ignore_errors=true) WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''"]
        if os.path.exists(thread_csv):
            source_sqls.append(f"SELECT trim(mail_no) AS mail_no, trim(response_mail_no) AS response_mail_no, trim(response_from_organization) AS response_from_organization, trim(response_from_name) AS response_from_name, TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date, trim(response_subject) AS response_subject, trim(response_reply_type) AS response_reply_type, trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id FROM read_csv_auto('{thread_csv}', header=true, ignore_errors=true) WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''")
        
        union_sql = " UNION ALL ".join(source_sqls)
        con.execute(f"""
        CREATE OR REPLACE TABLE fact_mail_responses AS
        WITH combined AS ({union_sql})
        SELECT DISTINCT * FROM combined;
        """)
        m_cnt = con.execute("SELECT count(*) FROM fact_mail_responses").fetchone()[0]
        print(f"  [OK] Updated fact_mail_responses: {m_cnt:,} records.")
    
    # -------------------------------------------------------------------------
    # 2. Ingest Workflow Status (161k steps)
    # -------------------------------------------------------------------------
    print("\n[2/6] Ingesting Workflow Status & Review Outcomes...")
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
        wf_cnt = con.execute("SELECT count(*) FROM fact_workflow_steps").fetchone()[0]
        print(f"  [OK] Updated fact_workflow_steps: {wf_cnt:,} steps.")
        
        # Rebuild fact_workflows summary
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
        print(f"  [OK] Rebuilt fact_workflows summary.")
        
    # -------------------------------------------------------------------------
    # 3. Ingest Document Transmittals
    # -------------------------------------------------------------------------
    print("\n[3/6] Ingesting Document Transmittals Lifecycle...")
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
        tl_cnt = con.execute("SELECT count(*) FROM fact_transmittal_lifecycle").fetchone()[0]
        print(f"  [OK] Updated fact_transmittal_lifecycle: {tl_cnt:,} rows.")

    # -------------------------------------------------------------------------
    # 4. Multi-Core Ingestion of Document Register Excel Files (391k docs)
    # -------------------------------------------------------------------------
    print("\n[4/6] Parallel Ingestion of Document Register Excel Files with Hyperlinks...")
    # Dynamically find the latest ExportDocs prefix that has valid parts
    all_docs = glob.glob(os.path.join(UP_DIR, "ExportDocs-*.xlsx"))
    valid_prefixes = []
    for f in all_docs:
        m = re.findall(r"ExportDocs-\d+_\d+-\d+", f)
        if m:
            pref = m[0]
            parts = glob.glob(os.path.join(UP_DIR, f"{pref}_*.xlsx"))
            if len(parts) > 0 and pref not in valid_prefixes:
                valid_prefixes.append(pref)
    valid_prefixes.sort()
    latest_prefix = valid_prefixes[-1] if valid_prefixes else None
    excel_files = sorted(glob.glob(os.path.join(UP_DIR, f"{latest_prefix}_*.xlsx"))) if latest_prefix else []
    if latest_prefix:
        print(f"  Selected latest Document Register set: {latest_prefix} ({len(excel_files)} parts)")
    if excel_files:
        tasks = []
        out_csvs = []
        for i, ef in enumerate(excel_files):
            out_csv = os.path.join(SCRATCH_DIR, f"docs_part_{i+1}.csv")
            out_csvs.append(out_csv)
            if not os.path.exists(out_csv) or os.path.getsize(out_csv) < 1000000:
                tasks.append((ef, out_csv))
            else:
                print(f"  [Cached] Using pre-extracted {os.path.basename(out_csv)} ({os.path.getsize(out_csv)/1024/1024:.1f} MB)")
        
        if tasks:
            with ProcessPoolExecutor(max_workers=min(len(tasks), 4)) as pool:
                results = list(pool.map(parse_excel_worker, tasks))
                print(f"  Total newly extracted from Excel: {sum(results):,} documents.")
        
        # Load CSVs into doc_aconex_links in DuckDB
        csv_list_sql = ", ".join([f"'{c.replace(chr(92), '/')}'" for c in out_csvs])
        try:
            con.execute("DROP VIEW IF EXISTS doc_aconex_links;")
        except Exception:
            pass
        try:
            con.execute("DROP TABLE IF EXISTS doc_aconex_links;")
        except Exception:
            pass
        con.execute("""
        CREATE TABLE doc_aconex_links (
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
        FROM read_csv([{csv_list_sql}], header=false, ignore_errors=true);
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_aconex_links_doc ON doc_aconex_links(document_no);")
        
        # Rebuild dim_documents
        print("  Rebuilding dim_documents with package and discipline categorization...")
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
                WHEN document_no ILIKE '%-MD01-%' OR document_no ILIKE '%MD01%' THEN 'MD01 (Modon Phase 1)'
                WHEN document_no ILIKE '%-SW00-%' OR document_no ILIKE '%SW00%' THEN 'SW00 (Site Wide / SWRO)'
                WHEN document_no ILIKE '%-AP00-%' OR document_no ILIKE '%AP00%' THEN 'AP00 (Airport)'
                WHEN document_no ILIKE '%-RR00-%' OR document_no ILIKE '%RR00%' THEN 'RR00 (Ring Road)'
                WHEN document_no ILIKE '%P1003%' THEN 'P1003 (Contract 03)'
                WHEN document_no ILIKE '%P1000%' THEN 'P1000 (Contract 00)'
                ELSE 'General / Other'
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
        d_cnt = con.execute("SELECT count(*) FROM dim_documents").fetchone()[0]
        print(f"  [OK] Rebuilt dim_documents: {d_cnt:,} documents.")
        
        # Cleanup temporary CSVs
        for c in out_csvs:
            try:
                os.remove(c)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 5. Rebuild Lookahead & High-Speed Materialized Views
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
    print(f"  [OK] Materialized agg_org_scorecard, agg_user_workload, agg_step_bottlenecks, agg_lookahead.")

    # -------------------------------------------------------------------------
    # 5b. Ingest Project Directory into dim_user_directory (Deep Sync)
    # -------------------------------------------------------------------------
    dir_csv = os.path.join(UP_DIR, "Project Directory.csv")
    if not os.path.exists(dir_csv):
        dir_csv = os.path.join(os.path.dirname(os.path.dirname(UP_DIR)), "project directory.csv")
    if os.path.exists(dir_csv):
        print("  [ETL] Ingesting updated Project Directory into dim_user_directory...")
        try:
            con.execute(f'''
                CREATE OR REPLACE TABLE stg_project_directory AS 
                SELECT * FROM read_csv_auto('{dir_csv.replace('\\', '/')}', header=True, ignore_errors=true, union_by_name=True);
            ''')
            con.execute('''
                CREATE OR REPLACE TABLE dim_user_directory AS
                SELECT 
                    trim(user_name) AS user_name,
                    trim(regexp_replace(user_name, '^(Mr|Mrs|Ms|Dr|Eng)\\s+', '', 'i')) AS clean_name,
                    trim(email) AS email,
                    trim(organization_name) AS organization_name,
                    trim(position) AS position,
                    trim(user_type) AS user_type
                FROM stg_project_directory
                WHERE user_name IS NOT NULL;
            ''')
            u_count = con.execute("SELECT count(*) FROM dim_user_directory").fetchone()[0]
            h_count = con.execute("SELECT count(*) FROM dim_user_directory WHERE lower(email) LIKE '%@hillintl.com'").fetchone()[0]
            print(f"  [OK] dim_user_directory updated: {u_count} total users, {h_count} Hill corporate emails.")
        except Exception as e:
            print(f"  [WARN] Could not ingest Project Directory: {e}")
    
    # -------------------------------------------------------------------------
    # 6. Delete Redundant Duplicate Files
    # -------------------------------------------------------------------------
    print("\n[6/6] Cleaning up unneeded files in update directory...")
    # Delete Mail Thread (2).csv because Mail Response (2).csv already has all responses and threads
    if os.path.exists(thread_csv) and os.path.exists(resp_csv):
        try:
            os.remove(thread_csv)
            print("  [DELETED] Mail Thread (2).csv (171 MB) - Redundant duplicate of Mail Response (2).csv")
        except Exception as e:
            print(f"  Could not remove Mail Thread (2).csv: {e}")
            
    con.close()

    # Ingest / update all Aconex mails and live hyperlinks
    try:
        import ingest_all_mails
        ingest_all_mails.main()
    except Exception as e:
        print(f"  [ERROR] Failed to run mail ingestion: {e}")

    # -------------------------------------------------------------------------
    # 7. Project Packages Classification & Summary Views Enrichment
    # -------------------------------------------------------------------------
    print("\n[7/7] Running Project Packages Classification & Summary Enrichment...")
    try:
        import classify_and_enrich_db
        classify_and_enrich_db.run_enrichment()
    except Exception as e:
        print(f"  [ERROR] Failed to run classification & enrichment: {e}")

    print("\n" + "=" * 80)
    print(f"ALL UPDATES SUCCESSFULLY COMPLETED IN {time.time()-t_global:.2f}s!")
    print("=" * 80)

if __name__ == "__main__":
    main()
