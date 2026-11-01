import duckdb

con = duckdb.connect('aconex.duckdb', read_only=True)

print("=== FACT_WORKFLOWS: project_package breakdown (ALL TIME) ===")
wf_pkgs = con.execute("""
    SELECT project_package, count(*) 
    FROM fact_workflows 
    GROUP BY 1 
    ORDER BY 2 DESC
""").fetchall()
for p, c in wf_pkgs:
    print(f"  {p:<30}: {c:,}")

print("\n=== DIM_DOCUMENTS: project_package breakdown (ALL TIME) ===")
doc_pkgs = con.execute("""
    SELECT project_package, count(*) 
    FROM dim_documents 
    GROUP BY 1 
    ORDER BY 2 DESC LIMIT 15
""").fetchall()
for p, c in doc_pkgs:
    print(f"  {p:<30}: {c:,}")

con.close()
