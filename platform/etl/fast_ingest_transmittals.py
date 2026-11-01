import duckdb
import time

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
CSV_PATH = r"C:\Users\bimst\Downloads\ACONEX\Data\transmittal history by document (1).csv"

def fast_ingest():
    start_t = time.time()
    print("Connecting to DuckDB...")
    con = duckdb.connect(DB_PATH, read_only=False)

    print("Building fact_document_transmittals directly with DuckDB columnar engine...")
    csv_escaped = CSV_PATH.replace('\\', '/')
    
    con.execute(f"""
    CREATE OR REPLACE TABLE fact_document_transmittals AS
    WITH raw_csv AS (
        SELECT * FROM read_csv('{csv_escaped}', header=true, all_varchar=true, ignore_errors=true)
    ),
    doc_pkg AS (
        SELECT DISTINCT document_no, project_package 
        FROM dim_documents 
        WHERE project_package IS NOT NULL
    )
    SELECT
        COALESCE(
            d.project_package,
            CASE
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%MD01%' THEN 'DP01'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%K03149%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3270%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%MD02%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP02%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%CCCEGY%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%ROWAD%' THEN 'DP02'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3271%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP03-W%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP3-W%' THEN 'DP03-West'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3199%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP03-E%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%INNOVO%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%REDCON%' THEN 'DP03-East'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3204%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP04%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%ACCE%' THEN 'DP04'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3205%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP05%' THEN 'DP05'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3206%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP06%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%HAC-RFI%' THEN 'DP06'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3207%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP07%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%CSCEC%' THEN 'DP07'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3213%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%DP08%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%SSH%' THEN 'DP08 - South Golf'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3049%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%AR01%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%AIRPORT%' THEN 'Airport'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3048%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%SW00%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%INFRA%' THEN 'Infra'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3046%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%-STP-%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%SEWAGE%' THEN 'STP'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3044%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%MSS%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%MMS%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%SEWEDY%' THEN 'MMS / Substation'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3045%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%RO-RFI%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%RO PLANT%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%OTC-JV%' THEN 'RO Plant'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3200%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%GRAND CANAL%' THEN 'Grand Canal'
                WHEN upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%3107%' 
                  OR upper(r.document_no || ' ' || COALESCE(r.created_by, '') || ' ' || COALESCE(r.title, '')) LIKE '%WEST CANAL%' THEN 'West Canal'
                ELSE 'General Deliverables'
            END
        ) AS project_package,
        r.document_no,
        r.title,
        r.revision,
        TRY_CAST(r.version_number AS BIGINT) AS version_number,
        r.status AS doc_status,
        r.type AS doc_type,
        CASE
            WHEN r.discipline IS NOT NULL AND trim(r.discipline) != '' AND trim(r.discipline) != 'N/A' THEN trim(r.discipline)
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-STR-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%STRUCTURE%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%CONCRETE%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%STEEL%' THEN 'Structural'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-ARC-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%ARCHITECT%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%FACADE%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%INTERIOR%' THEN 'Architectural'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-MEP-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-ME-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%MECHANICAL%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%HVAC%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%PLUMBING%' THEN 'Mechanical / MEP'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-ELE-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%ELECTRICAL%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%LIGHTING%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%SUBSTATION%' THEN 'Electrical'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-CIV-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-CV-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%CIVIL%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%EARTHWORKS%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%ROAD%' THEN 'Civil / Earthworks'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-LND-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%LANDSCAPE%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%IRRIGATION%' THEN 'Landscape'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-INF-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%INFRA%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%UTILITIES%' THEN 'Infrastructure'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-HSE-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%SAFETY%' THEN 'Health & Safety'
            WHEN upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%-QA-%' 
              OR upper(COALESCE(r.document_no, '') || ' ' || COALESCE(r.title, '') || ' ' || COALESCE(r.type, '')) LIKE '%QUALITY%' THEN 'Quality Control'
            ELSE 'General'
        END AS discipline,
        COALESCE(NULLIF(r.transmitted_mail_no, ''), NULLIF(r.transmittal_in_mail_no, ''), NULLIF(r.transmitted, ''), NULLIF(r.transmittal_in, ''), 'N/A') AS transmittal_no,
        r.transmitted_mail_no,
        r.transmitted_sent_date,
        r.transmitted_to_organization AS transmitted_to_org,
        r.transmitted_recipients,
        r.transmitted_reason_for_issue AS reason_for_issue,
        r.transmittal_in_mail_no,
        r.transmittal_in_sent_date,
        r.transmittal_in_from_organization AS transmittal_in_from_org,
        r.transmittal_in_from_name,
        r.created_by,
        r.date_created,
        r.date_modified,
        '/api/aconex/doc?doc_no=' || r.document_no AS aconex_doc_url,
        '/api/aconex/mail?mail_no=' || COALESCE(NULLIF(r.transmitted_mail_no, ''), NULLIF(r.transmittal_in_mail_no, ''), 'N/A') AS aconex_transmittal_url
    FROM raw_csv r
    LEFT JOIN doc_pkg d ON r.document_no = d.document_no
    """)

    print("Creating indexes on fact_document_transmittals...")
    con.execute("CREATE INDEX idx_fdt_pkg ON fact_document_transmittals(project_package)")
    con.execute("CREATE INDEX idx_fdt_trans_no ON fact_document_transmittals(transmittal_no)")
    con.execute("CREATE INDEX idx_fdt_doc_no ON fact_document_transmittals(document_no)")

    cnt = con.execute("SELECT count(*) FROM fact_document_transmittals").fetchone()[0]
    dur = time.time() - start_t
    print(f"DONE in {dur:.2f} seconds! Total rows: {cnt}")

    print("\nPackage Distribution:")
    for r in con.execute("SELECT project_package, count(*) FROM fact_document_transmittals GROUP BY 1 ORDER BY 2 DESC LIMIT 15").fetchall():
        print(f"  {r[0]}: {r[1]:,}")

    con.close()

if __name__ == '__main__':
    fast_ingest()
