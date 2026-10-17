import duckdb
from collections import defaultdict

con = duckdb.connect('aconex.duckdb', read_only=True)

def test_overview(from_date=None):
    where_date_rfis = f"AND sent_date >= '{from_date}'" if from_date else ""
    where_date_mail = f"AND sent_date >= '{from_date}'" if from_date else ""

    # All overdue RFIs
    all_rfis = con.execute(f"""
        SELECT mail_no, project_package, subject, from_organization, to_organization, sent_date
        FROM fact_rfis 
        WHERE (is_overdue = true OR days_late > 0)
          {where_date_rfis}
          AND NOT (subject ILIKE '%SCR%' OR mail_no ILIKE '%SCR%')
    """).fetchall()

    print(f"\n--- Overview Test (from_date={from_date}) ---")
    print(f"Total Overdue RFIs found: {len(all_rfis)}")

    # Overdue letters
    all_mails = con.execute(f"""
        SELECT count(*) 
        FROM fact_mail 
        WHERE (is_overdue = true OR days_late > 0)
          {where_date_mail}
          AND NOT (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
    """).fetchone()[0]
    print(f"Total Overdue Mails found: {all_mails}")

    # Overdue workflows
    all_wf = con.execute("""
        SELECT count(*) 
        FROM fact_workflow_steps s 
        JOIN fact_workflows w ON s.workflow_no = w.workflow_no 
        WHERE s.is_overdue = true
    """).fetchone()[0]
    print(f"Total Overdue Workflows found: {all_wf}")

test_overview("2026-03-01")
test_overview(None)

con.close()
