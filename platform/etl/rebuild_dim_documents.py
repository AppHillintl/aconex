"""
Rebuild dim_documents and finalize doc_aconex_links in DuckDB
"""
import duckdb
import time

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"

print("="*80)
print("Rebuilding dim_documents from doc_aconex_links...")
print("="*80)

t0 = time.time()
con = duckdb.connect(DB_PATH, read_only=False)

# 1. Clean header rows if present
con.execute("DELETE FROM doc_aconex_links WHERE document_no = 'Document No';")
total_links = con.execute("SELECT count(*) FROM doc_aconex_links").fetchone()[0]
print(f"Total valid document records in doc_aconex_links: {total_links:,}")

# 2. Create index on doc_aconex_links
con.execute("CREATE INDEX IF NOT EXISTS idx_aconex_links_doc ON doc_aconex_links(document_no);")

# 3. Create dim_documents with all columns expected by main.py
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
    -- Standardized Discipline Extraction
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

# 4. Create index
con.execute("CREATE INDEX IF NOT EXISTS idx_dim_doc_no ON dim_documents(document_no);")

total_docs = con.execute("SELECT count(*) FROM dim_documents").fetchone()[0]
sample = con.execute("SELECT document_no, title, revision, status, package_name, discipline_name, aconex_url FROM dim_documents LIMIT 3").fetchall()

print(f"\nSUCCESS! dim_documents rebuilt successfully with {total_docs:,} documents in {time.time()-t0:.2f}s!")
print("\nSample records:")
for s in sample:
    print(f"  {s[0]} (Rev {s[1]}): {s[2]} | {s[3]} | {s[4]} | {s[5]} | URL: {s[6][:60]}...")

con.close()
