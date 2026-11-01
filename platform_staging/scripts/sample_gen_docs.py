import duckdb

con = duckdb.connect('aconex.duckdb', read_only=True)

docs_gen = con.execute("""
    SELECT document_no, title, doc_type, raw_discipline, package_name 
    FROM dim_documents 
    WHERE project_package = 'General Project Deliverables' OR project_package IS NULL
    LIMIT 20
""").fetchall()

print(f"Sample of General Project Deliverables ({len(docs_gen)} shown):")
for d in docs_gen:
    print(" ", d)

con.close()
