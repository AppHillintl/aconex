import os
import glob
import re
import time
import openpyxl
import duckdb

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
DATA_DIR = r"C:\Users\bimst\Downloads\ACONEX\Data\ExportDocs-20261007_14-56"

def ingest():
    t0 = time.time()
    print(f"Starting Aconex Direct Hyperlinks ingestion into {DB_PATH}...")
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.xlsx")))
    if not files:
        print(f"Error: No Excel files found in {DATA_DIR}")
        return

    print(f"Found {len(files)} Excel files to ingest: {[os.path.basename(f) for f in files]}")

    con = duckdb.connect(DB_PATH)

    # Create table
    con.execute("DROP TABLE IF EXISTS doc_aconex_links")
    con.execute("""
        CREATE TABLE doc_aconex_links (
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
        )
    """)

    total_inserted = 0
    tid_pattern = re.compile(r'trackingid=(\d+)')
    pid_pattern = re.compile(r'projectid=(\d+)')

    for file_idx, fpath in enumerate(files, 1):
        f_t0 = time.time()
        print(f"\nProcessing [{file_idx}/{len(files)}] {os.path.basename(fpath)}...")
        wb = openpyxl.load_workbook(fpath, read_only=True)
        ws = wb.active

        batch = []
        file_count = 0

        for row_idx, r in enumerate(ws.iter_rows(values_only=True)):
            # Row index in 0-based: row 10 (11th row) is header, row 11+ is data
            if row_idx <= 9 or not r[0]:
                continue

            doc_no = str(r[0]).strip()
            revision = str(r[1]).strip() if r[1] is not None else None
            title = str(r[2]).strip() if r[2] is not None else None
            rev_date = r[3] if hasattr(r[3], 'strftime') else None
            review_src = str(r[4]).strip() if r[4] is not None else None
            dtype = str(r[5]).strip() if r[5] is not None else None
            status = str(r[6]).strip() if r[6] is not None else None
            discipline = str(r[7]).strip() if r[7] is not None else None
            url = str(r[8]).strip() if r[8] is not None else None

            tracking_id = None
            project_id = None
            if url:
                m_tid = tid_pattern.search(url)
                if m_tid:
                    tracking_id = m_tid.group(1)
                m_pid = pid_pattern.search(url)
                if m_pid:
                    project_id = m_pid.group(1)

            batch.append((
                doc_no,
                revision,
                title,
                rev_date,
                review_src,
                dtype,
                status,
                discipline,
                tracking_id,
                project_id,
                url
            ))
            file_count += 1

            if len(batch) >= 20000:
                con.executemany("""
                    INSERT INTO doc_aconex_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                batch.clear()

        if batch:
            con.executemany("""
                INSERT INTO doc_aconex_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            batch.clear()

        wb.close()
        total_inserted += file_count
        print(f"Done file {file_idx}: {file_count:,} rows loaded in {time.time()-f_t0:.1f}s (Running total: {total_inserted:,})")

    print("\nCreating database indexes for instant lookups...")
    idx_t0 = time.time()
    con.execute("CREATE INDEX idx_doc_aconex_document_no ON doc_aconex_links (document_no)")
    con.execute("CREATE INDEX idx_doc_aconex_review_source ON doc_aconex_links (review_source)")
    print(f"Indexes created in {time.time()-idx_t0:.2f}s")

    # Verification query
    count_docs = con.execute("SELECT count(*), count(distinct document_no), count(distinct review_source) FROM doc_aconex_links").fetchone()
    sample = con.execute("SELECT document_no, revision, review_source, tracking_id, aconex_url FROM doc_aconex_links LIMIT 3").fetchall()

    con.close()
    print(f"\n==========================================")
    print(f"Ingestion Finished Successfully in {time.time()-t0:.1f}s")
    print(f"Total Rows: {count_docs[0]:,}")
    print(f"Unique Documents: {count_docs[1]:,}")
    print(f"Workflows/Transmittals Linked: {count_docs[2]:,}")
    print("Sample records:")
    for s in sample:
        print(f"  {s}")
    print(f"==========================================")

if __name__ == "__main__":
    ingest()
