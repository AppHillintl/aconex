import duckdb
import os
import re

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")
con = duckdb.connect(DB_PATH, read_only=True)

print("Checking contractor RFIs query with date filter...")
where_clauses = ["r.sent_date >= TIMESTAMP '2026-03-01'"]
params = []

# Exclude SCR
where_clauses.append("NOT (r.subject ILIKE '%SCR%' OR r.mail_no ILIKE '%SCR%')")

where_str = " AND ".join(where_clauses)
rows = con.execute(f"""
    SELECT 
        r.mail_no,
        r.subject,
        r.from_organization,
        r.to_organization,
        r.from_name,
        r.sent_date::VARCHAR,
        r.due_date::VARCHAR,
        r.days_late,
        r.is_overdue,
        r.project_package,
        COALESCE(r.aconex_url, 'https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A' || r.mail_no) AS aconex_url
    FROM fact_rfis r
    WHERE {where_str}
    ORDER BY r.days_late DESC, r.sent_date DESC NULLS LAST
    LIMIT 10
""").fetchall()

print(f"Sample RFIs: {len(rows)}")
for r in rows:
    print(r[0], "|", r[9], "|", r[3], "| Late:", r[7], "| Overdue:", r[8])
