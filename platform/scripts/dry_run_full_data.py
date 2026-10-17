import duckdb
from test_full_package_resolution import resolve_entity_package

con = duckdb.connect('aconex.duckdb', read_only=True)

# Test get_all_projects_overdue_overview logic with from_date=None (FULL DATA)
rows = con.execute("SELECT project_id, project_title, sort_order FROM dim_project_packages ORDER BY sort_order ASC").fetchall()

all_rfis = con.execute("""
    SELECT mail_no, project_package, subject, from_organization, to_organization
    FROM fact_rfis 
    WHERE (is_overdue = true OR days_late > 0)
      AND NOT (subject ILIKE '%SCR%' OR mail_no ILIKE '%SCR%')
""").fetchall()

from collections import defaultdict
rfi_counts = defaultdict(int)
for r in all_rfis:
    pkg = resolve_entity_package(r[2], r[0], r[3], r[4], r[1])
    rfi_counts[pkg] += 1

print("--- OVERDUE RFIs BY RESOLVED PACKAGE (FULL DATA) ---")
for pkg, cnt in sorted(rfi_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {pkg:<25}: {cnt}")

print("\n--- SAMPLE PROJECTS OVERDUE TOTALS (FULL DATA) ---")
for r in rows[:10]:
    pid = r[0]
    ov_wf = con.execute("SELECT count(*) FROM fact_workflow_steps s JOIN fact_workflows w ON s.workflow_no = w.workflow_no WHERE w.project_package = ? AND s.is_overdue = true", [pid]).fetchone()[0]
    ov_mail = con.execute("SELECT count(*) FROM fact_mail WHERE project_package = ? AND (is_overdue = true OR days_late > 0) AND NOT (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')", [pid]).fetchone()[0]
    ov_rfi = rfi_counts.get(pid, 0)
    print(f"  {pid:<15}: Workflows={ov_wf:<4} | Mails={ov_mail:<4} | RFIs={ov_rfi:<4} | Total={ov_wf+ov_mail+ov_rfi}")

con.close()
