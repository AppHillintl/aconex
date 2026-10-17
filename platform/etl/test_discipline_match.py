import duckdb
import re

con = duckdb.connect('aconex.duckdb', read_only=True)

# Test matching BIC RFI with fact_mail
rfi_matches = con.execute("""
    SELECT 
        b.process_ref, 
        b.mail_no, 
        m.subject,
        m.project_package
    FROM fact_ball_in_court_processes b
    LEFT JOIN fact_mail m ON b.mail_no = m.mail_no OR b.process_ref = m.mail_no
    WHERE b.file_type = 'RFI'
    LIMIT 20
""").fetchall()

print("Sample RFI matches with fact_mail:")
for r in rfi_matches[:10]:
    print(" ", r)

# Test matching BIC Transmittal with transmittals CSV / doc
trans_matches = con.execute("""
    SELECT 
        b.process_ref,
        b.mail_no,
        t.discipline,
        t.type,
        t.title
    FROM fact_ball_in_court_processes b
    LEFT JOIN stg_transmittal_by_doc t ON (b.mail_no = t.transmitted_mail_no OR b.mail_no = t.transmittal_in_mail_no OR b.process_ref = t.transmitted_mail_no)
    WHERE b.file_type = 'TRANSMITTAL' AND t.discipline IS NOT NULL AND t.discipline != ''
    LIMIT 10
""").fetchall()

print("\nSample Transmittal matches with stg_transmittal_by_doc:")
for r in trans_matches[:5]:
    print(" ", r)
