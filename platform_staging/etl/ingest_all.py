"""
ACONEX Data Platform - Complete ETL Pipeline
Builds Star Schema and Analytical Materialized Views in DuckDB
"""

import duckdb
import os
import sys
import time
import re

DATA_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data".replace("\\", "/")
DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")

print("="*80)
print(f"Starting ACONEX ETL Pipeline...")
print(f"Source Data: {DATA_DIR}")
print(f"DuckDB Path: {DB_PATH}")
print("="*80)

con = duckdb.connect(DB_PATH)

# Enable memory optimizations
con.execute("PRAGMA threads=4;")
con.execute("PRAGMA memory_limit='6GB';")

# -----------------------------------------------------------------------------
# STEP 1: Ingest Raw CSVs into Stage Tables
# -----------------------------------------------------------------------------
print("\n[1/6] Ingesting CSV Files into Staging Tables...")

def load_stage(table_name, csv_filename):
    t0 = time.time()
    csv_path = f"{DATA_DIR}/{csv_filename}"
    if not os.path.exists(csv_path.replace("/", "\\")):
        print(f"  Warning: {csv_filename} not found, skipping.")
        return
    print(f"  Loading {csv_filename} -> {table_name}...")
    con.execute(f"""
        CREATE OR REPLACE TABLE {table_name} AS 
        SELECT * FROM read_csv_auto('{csv_path}', header=True, ignore_errors=true, union_by_name=True);
    """)
    cnt = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
    print(f"  Loaded {table_name}: {cnt:,} rows in {time.time()-t0:.2f}s")

load_stage("stg_documents", "document status.csv")
load_stage("stg_transmittal_workflow", "document transmittal workflow.csv")
load_stage("stg_workflow_status", "workflow status.csv")
load_stage("stg_workflow_review_outcome", "workflow documents review outcome.csv")
load_stage("stg_workflow_insights", "workflow documents - insights.csv")
load_stage("stg_mail_status", "mail status (1).csv")
load_stage("stg_mail_days_late", "mail days late (1).csv")
load_stage("stg_rfi_received", "rfi received.csv")
load_stage("stg_rfi_sent", "rfi sent.csv")
load_stage("stg_transmittal_by_doc", "transmittal history by document.csv")
load_stage("stg_transmittal_by_org", "transmittal history by organization.csv")

# -----------------------------------------------------------------------------
# STEP 2: Helper SQL Functions & Dimensions
# -----------------------------------------------------------------------------
print("\n[2/6] Building Dimension Tables (Organizations, Users, Documents)...")

# 2.1 Organizations Master
con.execute("""
CREATE OR REPLACE TABLE dim_organizations AS
WITH raw_orgs AS (
    SELECT DISTINCT trim(created_by) AS org_name FROM stg_documents WHERE created_by IS NOT NULL AND trim(created_by) != ''
    UNION
    SELECT DISTINCT trim(initiator_organization) FROM stg_workflow_status WHERE initiator_organization IS NOT NULL AND trim(initiator_organization) != ''
    UNION
    SELECT DISTINCT trim(assigned_to_organization) FROM stg_workflow_status WHERE assigned_to_organization IS NOT NULL AND trim(assigned_to_organization) != ''
    UNION
    SELECT DISTINCT trim(from_organization) FROM stg_mail_status WHERE from_organization IS NOT NULL AND trim(from_organization) != ''
    UNION
    SELECT DISTINCT trim(to_organization) FROM stg_mail_status WHERE to_organization IS NOT NULL AND trim(to_organization) != ''
)
SELECT 
    ROW_NUMBER() OVER (ORDER BY org_name) AS org_id,
    org_name,
    CASE 
        WHEN org_name ILIKE '%Hill Inter%' THEN 'PMC'
        WHEN org_name ILIKE '%Modon%' THEN 'Employer / Client'
        WHEN org_name ILIKE '%Shaker%' OR org_name ILIKE '%ECG%' OR org_name ILIKE '%EGIS%' 
             OR org_name ILIKE '%Dar%' OR org_name ILIKE '%Aedas%' OR org_name ILIKE '%Dewan%' 
             OR org_name ILIKE '%OBMI%' OR org_name ILIKE '%ICON%' THEN 'Consultant / Engineer'
        WHEN org_name ILIKE '%Orascom%' OR org_name ILIKE '%Hassan Allam%' OR org_name ILIKE '%Consolidated Contractors%' 
             OR org_name ILIKE '%CCC%' OR org_name ILIKE '%innovo%' OR org_name ILIKE '%redcon%' 
             OR org_name ILIKE '%CSCEC%' OR org_name ILIKE '%ELSEWEDY%' OR org_name ILIKE '%ROWAD%' 
             OR org_name ILIKE '%Horema%' THEN 'Main Contractor'
        ELSE 'Stakeholder / Other'
    END AS org_category,
    CASE WHEN org_name ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_pmc
FROM raw_orgs
WHERE org_name IS NOT NULL AND length(org_name) > 1;
""")
print(f"  Created dim_organizations: {con.execute('SELECT count(*) FROM dim_organizations').fetchone()[0]} organizations.")

# 2.2 Documents Register with Extracted Packages & Disciplines
con.execute("""
CREATE OR REPLACE TABLE dim_documents AS
WITH clean_docs AS (
    SELECT 
        trim(document_no) AS document_no,
        trim(title) AS title,
        trim(type) AS doc_type,
        trim(status) AS status,
        trim(review_status) AS review_status,
        trim(revision) AS revision,
        CAST(version_number AS VARCHAR) AS version_number,
        trim(created_by) AS created_by,
        CAST(date_modified AS TIMESTAMP) AS date_modified,
        CAST(revision_date AS TIMESTAMP) AS revision_date,
        -- Package Extraction
        CASE 
            WHEN document_no ILIKE '%-MD01-%' OR document_no ILIKE '%MD01%' THEN 'MD01 (Modon Phase 1)'
            WHEN document_no ILIKE '%-SW00-%' OR document_no ILIKE '%SW00%' THEN 'SW00 (Site Wide / SWRO)'
            WHEN document_no ILIKE '%-AP00-%' OR document_no ILIKE '%AP00%' THEN 'AP00 (Airport)'
            WHEN document_no ILIKE '%-RR00-%' OR document_no ILIKE '%RR00%' THEN 'RR00 (Ring Road)'
            WHEN document_no ILIKE '%P1003%' THEN 'P1003 (Contract 03)'
            WHEN document_no ILIKE '%P1000%' THEN 'P1000 (Contract 00)'
            ELSE 'General / Other'
        END AS package_name,
        -- Discipline Extraction
        CASE 
            WHEN document_no ILIKE '%-ST-%' OR document_no ILIKE '%-STR-%' OR title ILIKE '%Structure%' OR title ILIKE '%Reinforcement%' THEN 'Structural (ST)'
            WHEN document_no ILIKE '%-AR-%' OR document_no ILIKE '%-ARC-%' OR title ILIKE '%Architectural%' THEN 'Architectural (AR)'
            WHEN document_no ILIKE '%-ME-%' OR document_no ILIKE '%-MEC-%' OR title ILIKE '%Mechanical%' OR title ILIKE '%HVAC%' OR title ILIKE '%Plumbing%' THEN 'Mechanical (ME)'
            WHEN document_no ILIKE '%-EL-%' OR document_no ILIKE '%-ELE-%' OR title ILIKE '%Electrical%' THEN 'Electrical (EL)'
            WHEN document_no ILIKE '%-CV-%' OR document_no ILIKE '%-CIV-%' OR title ILIKE '%Civil%' THEN 'Civil (CV)'
            WHEN document_no ILIKE '%-ID-%' OR title ILIKE '%Interior%' THEN 'Interior Design (ID)'
            WHEN document_no ILIKE '%-BM-%' OR document_no ILIKE '%-BIM-%' OR title ILIKE '%BIM%' THEN 'BIM'
            WHEN document_no ILIKE '%-BR-%' OR title ILIKE '%Bridge%' THEN 'Bridges (BR)'
            WHEN document_no ILIKE '%-HS-%' OR document_no ILIKE '%-HSE-%' OR title ILIKE '%Safety%' OR title ILIKE '%HSE%' THEN 'HSE / Safety'
            WHEN document_no ILIKE '%-FS-%' OR title ILIKE '%Fire%' THEN 'Fire & Life Safety'
            ELSE 'Multi-Disciplinary / Other'
        END AS discipline_name
    FROM stg_documents
    WHERE document_no IS NOT NULL AND trim(document_no) != ''
)
SELECT * FROM clean_docs;
""")
print(f"  Created dim_documents: {con.execute('SELECT count(*) FROM dim_documents').fetchone()[0]} document entries.")

# -----------------------------------------------------------------------------
# STEP 3: Fact Tables
# -----------------------------------------------------------------------------
print("\n[3/6] Building Fact Tables (Workflows, Steps, Transmittals, Mail, RFIs)...")

# 3.1 Fact Workflows & Fact Workflow Steps
con.execute("""
CREATE OR REPLACE TABLE fact_workflow_steps AS
SELECT 
    trim(workflow_number) AS workflow_no,
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
    CASE WHEN step_status = 'Overdue' THEN TRUE ELSE FALSE END AS is_overdue,
    CASE 
        WHEN COALESCE(TRY_CAST(days_late AS INTEGER), 0) <= 0 THEN 'On Time'
        WHEN TRY_CAST(days_late AS INTEGER) BETWEEN 1 AND 7 THEN '1-7 Days Overdue'
        WHEN TRY_CAST(days_late AS INTEGER) BETWEEN 8 AND 14 THEN '8-14 Days Overdue'
        WHEN TRY_CAST(days_late AS INTEGER) BETWEEN 15 AND 30 THEN '15-30 Days Overdue'
        ELSE '> 30 Days Overdue'
    END AS aging_bucket,
    -- Perspective Flags
    CASE WHEN assigned_to_organization ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_owed_by_hill,
    CASE WHEN initiator_organization ILIKE '%Hill Inter%' AND NOT (assigned_to_organization ILIKE '%Hill Inter%') THEN TRUE ELSE FALSE END AS is_owed_to_hill
FROM stg_workflow_status
WHERE workflow_number IS NOT NULL;
""")
print(f"  Created fact_workflow_steps: {con.execute('SELECT count(*) FROM fact_workflow_steps').fetchone()[0]} steps.")

# 3.2 Fact Workflows Summary
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
print(f"  Created fact_workflows: {con.execute('SELECT count(*) FROM fact_workflows').fetchone()[0]} workflows.")

# 3.3 Fact Transmittal Lifecycle (End-to-End Cycle)
con.execute("""
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
    -- Turnaround Days Calculation
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
FROM stg_transmittal_workflow
WHERE document_no IS NOT NULL;
""")
print(f"  Created fact_transmittal_lifecycle: {con.execute('SELECT count(*) FROM fact_transmittal_lifecycle').fetchone()[0]} lifecycle rows.")

# 3.4 Fact Correspondence (Mail Status & Days Late)
con.execute("""
CREATE OR REPLACE TABLE fact_mail AS
SELECT 
    trim(mail_no) AS mail_no,
    trim(mail_type) AS mail_type,
    trim(subject) AS subject,
    trim(reference_number) AS reference_number,
    trim(from_name) AS from_name,
    trim(from_organization) AS from_organization,
    trim(to_organization) AS to_organization,
    trim(recipients) AS recipients,
    trim(status) AS status,
    trim(mail_box) AS mail_box,
    TRY_CAST(sent_date AS TIMESTAMP) AS sent_date,
    TRY_CAST(due AS TIMESTAMP) AS due_date,
    COALESCE(TRY_CAST(days_late AS INTEGER), 0) AS days_late,
    CASE WHEN status = 'Overdue' THEN TRUE ELSE FALSE END AS is_overdue,
    -- Perspective Flags
    CASE WHEN to_organization ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_inbound_to_hill,
    CASE WHEN from_organization ILIKE '%Hill Inter%' THEN TRUE ELSE FALSE END AS is_outbound_from_hill
FROM stg_mail_status
WHERE mail_no IS NOT NULL;
""")
print(f"  Created fact_mail: {con.execute('SELECT count(*) FROM fact_mail').fetchone()[0]} mail items.")

# 3.5 Fact RFIs (Received & Sent)
con.execute("""
CREATE OR REPLACE TABLE fact_rfis AS
SELECT 
    trim(mail_no) AS mail_no,
    trim(subject) AS subject,
    trim(from_organization) AS from_organization,
    trim(to_organization) AS to_organization,
    trim(from_name) AS from_name,
    trim(recipients) AS recipients,
    trim(status) AS status,
    TRY_CAST(sent_date AS TIMESTAMP) AS sent_date,
    TRY_CAST(due AS TIMESTAMP) AS due_date,
    COALESCE(TRY_CAST(days_late AS INTEGER), 0) AS days_late,
    'Received' AS direction,
    CASE WHEN status = 'Overdue' THEN TRUE ELSE FALSE END AS is_overdue
FROM stg_rfi_received
WHERE mail_no IS NOT NULL
UNION ALL
SELECT 
    trim(mail_no) AS mail_no,
    trim(subject) AS subject,
    'Hill Inter' AS from_organization,
    trim(to_organization) AS to_organization,
    trim(from_name) AS from_name,
    trim(recipients) AS recipients,
    trim(status) AS status,
    TRY_CAST(sent_date AS TIMESTAMP) AS sent_date,
    TRY_CAST(due AS TIMESTAMP) AS due_date,
    COALESCE(TRY_CAST(days_late AS INTEGER), 0) AS days_late,
    'Sent' AS direction,
    CASE WHEN status = 'Overdue' THEN TRUE ELSE FALSE END AS is_overdue
FROM stg_rfi_sent
WHERE mail_no IS NOT NULL;
""")
print(f"  Created fact_rfis: {con.execute('SELECT count(*) FROM fact_rfis').fetchone()[0]} RFIs.")

# -----------------------------------------------------------------------------
# STEP 4: Materialized Aggregated Views for Instant UI Querying (<20ms)
# -----------------------------------------------------------------------------
print("\n[4/6] Creating Materialized Summary Tables for Lightning-Fast Dashboard...")

# 4.1 Organization Performance Scorecard
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
print(f"  Created agg_org_scorecard: {con.execute('SELECT count(*) FROM agg_org_scorecard').fetchone()[0]} rows.")

# 4.2 Individual User Workload & Overdue Task Aging
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
print(f"  Created agg_user_workload: {con.execute('SELECT count(*) FROM agg_user_workload').fetchone()[0]} engineers.")

# 4.3 Workflow Step Bottleneck Identification
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
print(f"  Created agg_step_bottlenecks.")

# 4.4 Lookahead Tasks (Due in the next 7 / 14 / 30 days)
con.execute("""
CREATE OR REPLACE TABLE agg_lookahead AS
SELECT 
    workflow_no,
    step_name,
    assigned_to_organization,
    assigned_to_name,
    document_no,
    document_title,
    date_due,
    DATE_DIFF('day', CURRENT_DATE, date_due::DATE) AS days_until_due
FROM fact_workflow_steps
WHERE step_status IN ('Current', 'Forecast') 
  AND date_due IS NOT NULL 
  AND date_due::DATE >= CURRENT_DATE
ORDER BY date_due ASC;
""")
print(f"  Created agg_lookahead.")

# -----------------------------------------------------------------------------
# STEP 5: Create Indexes for Sub-Millisecond Search
# -----------------------------------------------------------------------------
print("\n[5/6] Creating Indices on Primary Search Keys...")
con.execute("CREATE INDEX idx_doc_no ON dim_documents(document_no);")
con.execute("CREATE INDEX idx_wf_steps_no ON fact_workflow_steps(workflow_no);")
con.execute("CREATE INDEX idx_wf_steps_doc ON fact_workflow_steps(document_no);")
con.execute("CREATE INDEX idx_mail_no ON fact_mail(mail_no);")
con.execute("CREATE INDEX idx_transmittal_doc ON fact_transmittal_lifecycle(document_no);")

# -----------------------------------------------------------------------------
# STEP 6: Summary Verification
# -----------------------------------------------------------------------------
print("\n[6/6] Pipeline Verification & Stats Summary:")
stats = con.execute("""
SELECT 
    (SELECT count(*) FROM dim_documents) AS total_documents,
    (SELECT count(*) FROM fact_workflows) AS total_workflows,
    (SELECT count(*) FROM fact_workflow_steps WHERE is_overdue) AS total_overdue_steps,
    (SELECT count(*) FROM fact_mail WHERE is_overdue) AS total_overdue_mails,
    (SELECT count(*) FROM fact_rfis WHERE is_overdue) AS total_overdue_rfis;
""").fetchone()

print(f"  Total Registered Documents : {stats[0]:,}")
print(f"  Total Workflows Captured  : {stats[1]:,}")
print(f"  Total Overdue Review Steps : {stats[2]:,}")
print(f"  Total Overdue Mails        : {stats[3]:,}")
print(f"  Total Overdue RFIs         : {stats[4]:,}")

con.close()
print("\n" + "="*80)
print("ETL Pipeline completed successfully! Database is ready for FastAPI Backend.")
print("="*80)
