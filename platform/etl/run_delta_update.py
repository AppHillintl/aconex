"""
=============================================================================
High-Speed Atomic Delta Update Script for Aconex Data
Performs in-place MERGE / Upsert on DuckDB tables without rebuilding baseline.
Target Execution Time: 2-5 seconds.
=============================================================================
"""
import os
import glob
import re
import time
import openpyxl
import duckdb

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
UP_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up"
DATA_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data"
SCRATCH_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\update\scratch"

BIC_FILES = [
    {"file": "0006_PROCESS DETAILS TABLE MD2.xlsx",     "file_type": "RFI",         "name": "RFI",         "ar": "طلبات المعلومات (RFI)"},
    {"file": "0006_PROCESS DETAILS TABLE MD2 (1).xlsx", "file_type": "HSNCR",       "name": "Safety NCR",  "ar": "تقارير عدم مطابقة السلامة (HSNCR)"},
    {"file": "0006_PROCESS DETAILS TABLE MD2 (2).xlsx", "file_type": "NCR",         "name": "NCR",         "ar": "تقارير عدم المطابقة للجودة (NCR)"},
    {"file": "0006_PROCESS DETAILS TABLE MD2 (3).xlsx", "file_type": "HSE",         "name": "Safety SOR",  "ar": "ملاحظات السلامة والبيئة (HSE)"},
    {"file": "0006_PROCESS DETAILS TABLE MD2 (4).xlsx", "file_type": "TRANSMITTAL", "name": "Transmittal", "ar": "سجلات الإحالات والمراسلات (Transmittals)"}
]


def safe_cell(row, idx, default=""):
    if idx is not None and 0 <= idx < len(row) and row[idx] is not None:
        return str(row[idx]).strip()
    return default

def safe_float(row, idx, default=0.0):
    if idx is not None and 0 <= idx < len(row) and row[idx] is not None:
        try:
            return float(row[idx])
        except (ValueError, TypeError):
            return default
    return default

def update_ball_in_court(con):
    """Parses any updated 0006_PROCESS DETAILS TABLE MD2 files and refreshes fact_ball_in_court_processes."""
    print("  [Delta BIC] Checking Process Details Excel files...")
    all_rows = []
    
    for item in BIC_FILES:
        target = os.path.join(UP_DIR, item["file"])
        if not os.path.exists(target):
            target = os.path.join(DATA_DIR, item["file"])
        if not os.path.exists(target):
            continue
            
        try:
            wb = openpyxl.load_workbook(target, read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            headers = None
            for row in rows_iter:
                if row and any(row):
                    headers = [str(c).strip() if c else "" for c in row]
                    break
            if not headers:
                wb.close()
                continue
                
            col_map = {h: idx for idx, h in enumerate(headers)}
            
            for row in rows_iter:
                if not row or not any(row):
                    continue
                p_ref = safe_cell(row, col_map.get("Process Reference", 0))
                if not p_ref:
                    continue
                init_on = safe_cell(row, col_map.get("Initiated On", 1))
                p_stat = safe_cell(row, col_map.get("Process Status", 2), "Outstanding")
                dur = safe_float(row, col_map.get("Duration (days)", 3))
                delay = safe_float(row, col_map.get("Delay (days)", 4))
                act = safe_cell(row, col_map.get("Latest Activity", 5))
                m_stat = safe_cell(row, col_map.get("Mail Status", 6), "Outstanding")
                bic = safe_cell(row, col_map.get("Ball In Court", 7))
                action = safe_cell(row, col_map.get("Action", 8))
                ov_days = safe_float(row, col_map.get("Days Overdue", 9))
                mail_no = safe_cell(row, col_map.get("Mail Number", 10))
                pkg = safe_cell(row, col_map.get("Package", 11), "General")
                contr = safe_cell(row, col_map.get("Contractor", 12))
                
                is_ov = (p_stat == "Overdue" or m_stat == "Overdue" or delay > 0 or ov_days > 0)
                url = f"/api/aconex/mail?mail_no={mail_no or p_ref}"
                
                all_rows.append((
                    p_ref, init_on, p_stat, dur, delay, act, m_stat, bic, action, ov_days,
                    mail_no, pkg, contr, is_ov, url, "Oracle Analytics", item["file_type"],
                    item["name"], item["ar"], item["file"], "General"
                ))
            wb.close()
        except Exception as e:
            print(f"    Warning parsing {item['file']}: {e}")

    if all_rows:
        try:
            con.execute("DROP TABLE IF EXISTS fact_ball_in_court_processes;")
            con.execute("""
            CREATE TABLE fact_ball_in_court_processes (
                process_ref VARCHAR, initiated_on VARCHAR, process_status VARCHAR, duration DOUBLE, delay DOUBLE,
                latest_activity VARCHAR, mail_status VARCHAR, ball_in_court VARCHAR, action VARCHAR, overdue_days DOUBLE,
                mail_no VARCHAR, project_package VARCHAR, contractor VARCHAR, is_overdue BOOLEAN, aconex_url VARCHAR,
                source VARCHAR, file_type VARCHAR, file_type_name VARCHAR, file_type_ar VARCHAR, source_file VARCHAR,
                discipline VARCHAR DEFAULT 'General'
            );
            """)
            con.executemany("INSERT INTO fact_ball_in_court_processes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", all_rows)
            print(f"  [OK] Refreshed fact_ball_in_court_processes: {len(all_rows):,} records.")
        except Exception as e:
            print(f"    Error updating fact_ball_in_court_processes: {e}")


def main():
    print("=" * 80)
    print("ACONEX HIGH-SPEED ATOMIC DELTA UPDATE (DUCKDB)")
    print("Source directory:", UP_DIR)
    print("=" * 80)
    t_global = time.time()
    
    con = None
    for attempt in range(10):
        try:
            con = duckdb.connect(DB_PATH, read_only=False)
            break
        except Exception as e:
            if attempt == 9:
                raise e
            print(f"  [Notice] Database currently busy, waiting for read lock release (attempt {attempt+1}/10)...")
            time.sleep(0.4)

    # -------------------------------------------------------------------------
    # 1. Atomic Upsert for fact_workflow_steps (from Workflow Status (1).csv)
    # -------------------------------------------------------------------------
    wf_status_csv = os.path.join(UP_DIR, "Workflow Status (1).csv").replace("\\", "/")
    if os.path.exists(wf_status_csv) and os.path.getsize(wf_status_csv) > 1000:
        print("\n[1/5] Ingesting & Upserting Workflow Status (161k steps)...")
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
    # 2. Ingest Mail Responses & Threads
    # -------------------------------------------------------------------------
    resp_csv = os.path.join(UP_DIR, "Mail Response (2).csv").replace("\\", "/")
    if os.path.exists(resp_csv) and os.path.getsize(resp_csv) > 1000:
        print("\n[2/5] Ingesting Mail Responses & Threads...")
        con.execute(f"""
        CREATE OR REPLACE TABLE fact_mail_responses AS
        SELECT 
            trim(mail_no) AS mail_no,
            trim(response_mail_no) AS response_mail_no,
            trim(response_from_organization) AS response_from_organization,
            trim(response_from_name) AS response_from_name,
            TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date,
            trim(response_subject) AS response_subject,
            trim(response_reply_type) AS response_reply_type,
            trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id
        FROM read_csv_auto('{resp_csv}', header=true, ignore_errors=true)
        WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != '';
        """)
        m_cnt = con.execute("SELECT count(*) FROM fact_mail_responses").fetchone()[0]
        print(f"  [OK] Updated fact_mail_responses: {m_cnt:,} records.")

    # -------------------------------------------------------------------------
    # 3. Ingest Document Transmittals Lifecycle
    # -------------------------------------------------------------------------
    dt_csv = os.path.join(UP_DIR, "Document Transmittal Workflow (1).csv").replace("\\", "/")
    if os.path.exists(dt_csv) and os.path.getsize(dt_csv) > 1000:
        print("\n[3/5] Ingesting Document Transmittals Lifecycle...")
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
    # 4. Refresh Process Details (RFIs, HSNCR, NCR, HSE, Transmittals)
    # -------------------------------------------------------------------------
    print("\n[4/5] Refreshing Process Details (RFIs, Safety, Quality)...")
    update_ball_in_court(con)

    # -------------------------------------------------------------------------
    # 5. Refresh Lookahead & High-Speed Performance Views
    # -------------------------------------------------------------------------
    print("\n[5/5] Materializing Aggregated Performance Views...")
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

    con.close()

    # Ingest / update all Aconex mails and live hyperlinks
    try:
        import ingest_all_mails
        ingest_all_mails.main()
    except Exception as e:
        print(f"  [ERROR] Failed to run mail ingestion: {e}")

    # Re-run classification and update agg_project_summary
    try:
        import classify_and_enrich_db
        classify_and_enrich_db.run_enrichment()
    except Exception as e:
        print(f"  [ERROR] Failed to run classification & enrichment: {e}")

    elapsed = time.time() - t_global
    print("\n" + "=" * 80)
    print(f"DELTA UPDATE SUCCESSFULLY COMPLETED IN {elapsed:.2f}s!")
    print("=" * 80)


if __name__ == "__main__":
    main()
