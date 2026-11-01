"""
Ingest latest ExportDocs-*.xlsx with direct Hyperlinks and rebuild dim_documents
"""
import openpyxl
import glob
import re
import os
import duckdb
import time

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
EXPORT_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\ExportDocs-20261007_16-43"

print("="*80)
print(f"Ingesting latest Document Register with Hyperlinks from {EXPORT_DIR}")
print("="*80)

t0 = time.time()
files = sorted(glob.glob(os.path.join(EXPORT_DIR, "*.xlsx")))
print(f"Found {len(files)} Excel files:")
for f in files:
    print(f"  - {os.path.basename(f)}")

con = duckdb.connect(DB_PATH, read_only=False)

# Create or replace staging table
con.execute("""
CREATE OR REPLACE TABLE doc_aconex_links (
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

url_pattern = re.compile(r"trackingid=(\d+)&projectid=(\d+)")

total_loaded = 0

for file_path in files:
    fname = os.path.basename(file_path)
    print(f"\nProcessing {fname}...")
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    
    rows_batch = []
    header_found = False
    
    for row in ws.iter_rows(values_only=True):
        if not header_found:
            if row and row[0] == 'Document No':
                header_found = True
            continue
        
        doc_no = str(row[0]).strip() if row[0] is not None else None
        if not doc_no:
            continue
        
        revision = str(row[1]).strip() if row[1] is not None else ''
        title = str(row[2]).strip() if row[2] is not None else ''
        rev_date = row[3] if len(row) > 3 else None
        rev_source = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ''
        doc_type = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ''
        status = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ''
        discipline = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ''
        url = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ''
        
        tracking_id = None
        project_id = None
        if url:
            m = url_pattern.search(url)
            if m:
                tracking_id = m.group(1)
                project_id = m.group(2)
        
        rows_batch.append((
            doc_no, revision, title, rev_date, rev_source,
            doc_type, status, discipline, tracking_id, project_id, url
        ))
        
        if len(rows_batch) >= 20000:
            con.executemany("INSERT INTO doc_aconex_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows_batch)
            total_loaded += len(rows_batch)
            rows_batch = []
            print(f"  Inserted {total_loaded:,} records so far...")
    
    if rows_batch:
        con.executemany("INSERT INTO doc_aconex_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows_batch)
        total_loaded += len(rows_batch)
        print(f"  Finished {fname}, total: {total_loaded:,}")
        
    wb.close()

# Create indices on doc_aconex_links
print("\nCreating indices on doc_aconex_links...")
con.execute("CREATE INDEX IF NOT EXISTS idx_aconex_links_doc ON doc_aconex_links(document_no);")

# Rebuild dim_documents from doc_aconex_links to cover all 387k documents
print("\nRebuilding dim_documents to contain all documents with packages and disciplines...")
con.execute("""
CREATE OR REPLACE TABLE dim_documents AS
SELECT 
    document_no,
    title,
    doc_type,
    status,
    revision,
    review_source AS review_status,
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

con.execute("CREATE INDEX IF NOT EXISTS idx_dim_doc_no ON dim_documents(document_no);")

total_docs = con.execute("SELECT count(*) FROM dim_documents").fetchone()[0]
print(f"\nDone! Total documents in dim_documents: {total_docs:,} (Time elapsed: {time.time()-t0:.2f}s)")
con.close()
