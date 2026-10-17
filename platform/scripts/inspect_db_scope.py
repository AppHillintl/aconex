import duckdb

con = duckdb.connect('aconex.duckdb', read_only=True)

tables_to_check = [
    'fact_mail',
    'fact_rfis',
    'dim_documents',
    'fact_document_transmittals',
    'dim_project_packages',
    'fact_ball_in_court_processes'
]

for tbl in tables_to_check:
    print(f"\n{'='*30} {tbl} {'='*30}")
    cols = con.execute(f"DESCRIBE {tbl}").fetchall()
    col_names = [c[0] for c in cols]
    print("Columns:", col_names)
    
    # Check date column if exists
    for d in ['sent_date', 'date', 'created_date', 'revision_date', 'registered_date']:
        if d in col_names:
            r = con.execute(f"SELECT MIN({d}), MAX({d}), COUNT(*) FROM {tbl}").fetchone()
            pre = con.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {d} < '2026-03-01'").fetchone()[0]
            post = con.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {d} >= '2026-03-01'").fetchone()[0]
            print(f"Date [{d}]: Min={r[0]}, Max={r[1]}, Total={r[2]:,} | Pre-Mar2026={pre:,}, Post-Mar2026={post:,}")
            break

    # Check project column
    for p in ['project_id', 'project_name', 'package_name', 'package', 'project_package']:
        if p in col_names:
            distinct_p = con.execute(f"SELECT {p}, COUNT(*) FROM {tbl} GROUP BY 1 ORDER BY 2 DESC LIMIT 10").fetchall()
            print(f"Top 10 [{p}]:", distinct_p)
            break

con.close()
