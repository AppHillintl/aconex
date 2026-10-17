import duckdb
import time

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
RESP_CSV = r"C:\Users\bimst\Downloads\ACONEX\Data\mail response (1).csv".replace("\\", "/")
THREAD_CSV = r"C:\Users\bimst\Downloads\ACONEX\Data\mail thread (1).csv".replace("\\", "/")

print("="*80)
print("Building comprehensive fact_mail_responses from both Response and Thread CSVs...")
print("="*80)

t0 = time.time()
con = duckdb.connect(DB_PATH, read_only=False)

con.execute(f"""
CREATE OR REPLACE TABLE fact_mail_responses AS
WITH combined AS (
    SELECT 
        trim(mail_no) AS mail_no,
        trim(response_mail_no) AS response_mail_no,
        trim(response_from_organization) AS response_from_organization,
        trim(response_from_name) AS response_from_name,
        TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date,
        trim(response_subject) AS response_subject,
        trim(response_reply_type) AS response_reply_type,
        trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id
    FROM read_csv_auto('{RESP_CSV}', header=True, ignore_errors=true)
    WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''
    UNION ALL
    SELECT 
        trim(mail_no) AS mail_no,
        trim(response_mail_no) AS response_mail_no,
        trim(response_from_organization) AS response_from_organization,
        trim(response_from_name) AS response_from_name,
        TRY_CAST(response_sent_date AS TIMESTAMP) AS response_sent_date,
        trim(response_subject) AS response_subject,
        trim(response_reply_type) AS response_reply_type,
        trim(CAST(parent_mail_id AS VARCHAR)) AS parent_mail_id
    FROM read_csv_auto('{THREAD_CSV}', header=True, ignore_errors=true)
    WHERE response_mail_no IS NOT NULL AND trim(response_mail_no) != ''
)
SELECT DISTINCT * FROM combined;
""")

con.execute("CREATE INDEX IF NOT EXISTS idx_mail_resp_mail_no ON fact_mail_responses(mail_no);")
con.execute("CREATE INDEX IF NOT EXISTS idx_mail_resp_resp_no ON fact_mail_responses(response_mail_no);")

cnt = con.execute("SELECT count(*) FROM fact_mail_responses").fetchone()[0]
print(f"Total distinct thread/response relations captured: {cnt:,} in {time.time()-t0:.2f}s")
con.close()
