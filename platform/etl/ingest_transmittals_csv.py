import csv
import os
import re
import duckdb
from datetime import datetime

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
CSV_PATH = r"C:\Users\bimst\Downloads\ACONEX\Data\transmittal history by document (1).csv"

def run_ingest():
    print(f"Connecting to {DB_PATH}...")
    con = duckdb.connect(DB_PATH, read_only=False)

    # 1. Load document-to-package mappings from dim_documents
    print("Loading dim_documents package map...")
    doc_pkg_map = dict(con.execute("SELECT document_no, project_package FROM dim_documents WHERE project_package IS NOT NULL").fetchall())
    print(f"Loaded {len(doc_pkg_map)} document-to-package mappings.")

    def resolve_pkg(doc_no, created_by, title):
        if doc_no in doc_pkg_map:
            return doc_pkg_map[doc_no]
        
        t = f"{doc_no or ''} {created_by or ''} {title or ''}".upper()
        if 'MD01' in t:
            return 'DP01'
        if any(k in t for k in ['K03149', '3270', 'MD02', 'DP02', 'CCCEGY', 'ROWAD']):
            return 'DP02'
        if any(k in t for k in ['3271', 'DP03-W', 'DP3-W', 'DP03W']):
            return 'DP03-West'
        if any(k in t for k in ['3199', 'DP03-E', 'DP3-E', 'DP03E', 'INNOVO', 'REDCON']):
            return 'DP03-East'
        if any(k in t for k in ['3204', 'DP04', 'ACCE']):
            return 'DP04'
        if any(k in t for k in ['3205', 'DP05', '-DP5-']):
            return 'DP05'
        if any(k in t for k in ['3206', 'DP06', 'REH/DP6', 'HAC-RFI']):
            return 'DP06'
        if any(k in t for k in ['3207', 'DP07', 'CSCEC']):
            return 'DP07'
        if any(k in t for k in ['3213', 'DP08', 'SSH']):
            return 'DP08 - South Golf'
        if any(k in t for k in ['3049', 'AR01', 'AIRPORT']):
            return 'Airport'
        if any(k in t for k in ['3048', 'SW00', 'INFRA']):
            return 'Infra'
        if any(k in t for k in ['3046', '-STP-', 'SEWAGE']):
            return 'STP'
        if any(k in t for k in ['3044', 'MSS', 'MMS', 'SEWEDY']):
            return 'MMS / Substation'
        if any(k in t for k in ['3045', 'RO-RFI', 'RO PLANT', 'OTC-JV']):
            return 'RO Plant'
        if any(k in t for k in ['3200', 'P0801', 'GRAND CANAL', 'GRAND LAGOON']):
            return 'Grand Canal'
        if any(k in t for k in ['3107', 'P1201', 'WEST CANAL']):
            return 'West Canal'
        
        return 'General Deliverables'

    def resolve_discipline(raw_disc, doc_no, title, doc_type):
        if raw_disc and raw_disc.strip() and raw_disc.strip() != 'N/A':
            return raw_disc.strip()
        
        t = f"{doc_no or ''} {title or ''} {doc_type or ''}".upper()
        if any(k in t for k in ['-STR-', '-ST-', 'STRUCTURE', 'SUPER STRUCTURE', 'CONCRETE', 'STEEL']):
            return 'Structural'
        if any(k in t for k in ['-ARC-', '-AR-', 'ARCHITECT', 'INTERIOR', 'FACADE']):
            return 'Architectural'
        if any(k in t for k in ['-MEP-', '-ME-', '-MEC-', 'MECHANICAL', 'HVAC', 'PLUMBING', 'DRAINAGE', 'PUMP']):
            return 'Mechanical / MEP'
        if any(k in t for k in ['-ELE-', '-EL-', 'ELECTRICAL', 'LIGHTING', 'POWER', 'SUBSTATION']):
            return 'Electrical'
        if any(k in t for k in ['-CIV-', '-CV-', '-CW-', 'CIVIL', 'EARTHWORKS', 'EXCAVATION', 'GRADING', 'ROAD']):
            return 'Civil / Earthworks'
        if any(k in t for k in ['-LND-', '-LA-', 'LANDSCAPE', 'IRRIGATION']):
            return 'Landscape'
        if any(k in t for k in ['-INF-', 'INFRA', 'UTILITIES', 'PIPELINE']):
            return 'Infrastructure'
        if any(k in t for k in ['-HSE-', 'SAFETY', 'HEALTH']):
            return 'Health & Safety'
        if any(k in t for k in ['-QA-', '-QC-', 'QUALITY', 'INSPECTION']):
            return 'Quality Control'
        return 'General'

    # Create table fact_document_transmittals
    con.execute("DROP TABLE IF EXISTS fact_document_transmittals")
    con.execute("""
    CREATE TABLE fact_document_transmittals (
        project_package VARCHAR,
        document_no VARCHAR,
        title VARCHAR,
        revision VARCHAR,
        version_number BIGINT,
        doc_status VARCHAR,
        doc_type VARCHAR,
        discipline VARCHAR,
        transmittal_no VARCHAR,
        transmitted_mail_no VARCHAR,
        transmitted_sent_date VARCHAR,
        transmitted_to_org VARCHAR,
        transmitted_recipients VARCHAR,
        reason_for_issue VARCHAR,
        transmittal_in_mail_no VARCHAR,
        transmittal_in_sent_date VARCHAR,
        transmittal_in_from_org VARCHAR,
        transmittal_in_from_name VARCHAR,
        created_by VARCHAR,
        date_created VARCHAR,
        date_modified VARCHAR,
        aconex_doc_url VARCHAR,
        aconex_transmittal_url VARCHAR
    );
    """)

    print(f"Reading and parsing CSV: {CSV_PATH}...")
    batch = []
    total_inserted = 0
    BATCH_SIZE = 50000

    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for row in reader:
            if len(row) < 20:
                continue
            
            created_by = row[7].strip()
            revision = row[8].strip()
            try:
                version_number = int(row[9].strip()) if row[9].strip().isdigit() else None
            except:
                version_number = None
            date_modified = row[10].strip()
            doc_status = row[11].strip()
            doc_type = row[12].strip()
            raw_discipline = row[15].strip()
            document_no = row[16].strip()
            title = row[17].strip()
            
            trans_in = row[18].strip()
            trans_out = row[19].strip()
            trans_out_mail_no = row[20].strip()
            trans_out_date = row[21].strip()
            trans_out_org = row[22].strip()
            trans_out_recipients = row[23].strip()
            trans_out_reason = row[24].strip()
            
            trans_in_date = row[28].strip() if len(row) > 28 else ""
            trans_in_mail_no = row[29].strip() if len(row) > 29 else ""
            trans_in_org = row[30].strip() if len(row) > 30 else ""
            trans_in_name = row[31].strip() if len(row) > 31 else ""
            
            # Primary transmittal number
            transmittal_no = trans_out_mail_no or trans_in_mail_no or trans_out or trans_in or "N/A"
            if transmittal_no == "" or transmittal_no == "N/A":
                # Check other columns
                if len(row) > 25 and row[25].strip():
                    transmittal_no = row[25].strip()
                elif len(row) > 32 and row[32].strip():
                    transmittal_no = row[32].strip()

            pkg = resolve_pkg(document_no, created_by, title)
            disc = resolve_discipline(raw_discipline, document_no, title, doc_type)

            doc_url = f"https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=DOC-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=documentNo%3A{document_no}" if document_no else ""
            trans_url = f"https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A{transmittal_no}" if transmittal_no and transmittal_no != "N/A" else ""

            batch.append((
                pkg,
                document_no,
                title,
                revision,
                version_number,
                doc_status,
                doc_type,
                disc,
                transmittal_no,
                trans_out_mail_no,
                trans_out_date,
                trans_out_org,
                trans_out_recipients,
                trans_out_reason,
                trans_in_mail_no,
                trans_in_date,
                trans_in_org,
                trans_in_name,
                created_by,
                row[6].strip() if len(row) > 6 else "",
                date_modified,
                doc_url,
                trans_url
            ))

            if len(batch) >= BATCH_SIZE:
                con.executemany("INSERT INTO fact_document_transmittals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
                total_inserted += len(batch)
                print(f"  Inserted {total_inserted} rows...")
                batch = []

        if batch:
            con.executemany("INSERT INTO fact_document_transmittals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
            total_inserted += len(batch)
            print(f"  Inserted final batch. Total: {total_inserted} rows.")

    # Create indexes for high performance
    print("Creating indexes on fact_document_transmittals...")
    con.execute("CREATE INDEX idx_fdt_pkg ON fact_document_transmittals(project_package)")
    con.execute("CREATE INDEX idx_fdt_trans_no ON fact_document_transmittals(transmittal_no)")
    con.execute("CREATE INDEX idx_fdt_doc_no ON fact_document_transmittals(document_no)")

    # 2. Add / Update discipline column in fact_ball_in_court_processes
    print("\nUpdating fact_ball_in_court_processes with discipline column...")
    cols = [c[0] for c in con.execute("DESCRIBE fact_ball_in_court_processes").fetchall()]
    if 'discipline' not in cols:
        con.execute("ALTER TABLE fact_ball_in_court_processes ADD COLUMN discipline VARCHAR DEFAULT 'General'")

    # Load subjects from fact_mail for RFI lookup
    mail_subjects = dict(con.execute("SELECT mail_no, subject FROM fact_mail WHERE subject IS NOT NULL").fetchall())

    bic_rows = con.execute("SELECT rowid, file_type, process_ref, mail_no FROM fact_ball_in_court_processes").fetchall()
    updates = []
    for rid, ftype, pref, mno in bic_rows:
        subj = mail_subjects.get(mno) or mail_subjects.get(pref) or ""
        t = f"{ftype or ''} {pref or ''} {mno or ''} {subj}".upper()
        
        if ftype in ['HSNCR', 'HSE'] or 'HSE' in t or 'SAFETY' in t:
            d = 'Health & Safety'
        elif ftype == 'NCR' or 'NCR' in t or 'NON-CONFORMANCE' in t:
            d = 'Quality Management'
        elif any(k in t for k in ['-STR-', '-ST-', 'STRUCTURE', 'SUPER STRUCTURE', 'CONCRETE', 'STEEL']):
            d = 'Structural'
        elif any(k in t for k in ['-ARC-', '-AR-', 'ARCHITECT', 'FACADE', 'VILLAS', 'INTERIOR', 'ALUMINUM']):
            d = 'Architectural'
        elif any(k in t for k in ['-MEP-', '-ME-', '-MEC-', 'DRAINAGE', 'PLUMBING', 'HVAC', 'STORM', 'WASTE', 'RISER', 'FIRE PROTECTION']):
            d = 'Mechanical / MEP'
        elif any(k in t for k in ['-ELE-', '-EL-', 'ELECTRICAL', 'LIGHTING', 'POWER', 'SUBSTATION']):
            d = 'Electrical'
        elif any(k in t for k in ['-CW-', '-CIV-', '-CV-', 'CIVIL', 'EARTHWORKS', 'EXCAVATION', 'GRADING', 'ROAD']):
            d = 'Civil / Earthworks'
        elif any(k in t for k in ['-LA-', '-LND-', 'LANDSCAPE', 'IRRIGATION']):
            d = 'Landscape'
        elif any(k in t for k in ['-INF-', 'INFRA', 'UTILITIES']):
            d = 'Infrastructure'
        elif ftype == 'TRANSMITTAL':
            d = 'General Deliverables'
        else:
            d = 'General'
        
        updates.append((d, rid))

    con.executemany("UPDATE fact_ball_in_court_processes SET discipline = ? WHERE rowid = ?", updates)
    print(f"Updated discipline for {len(updates)} Ball in Court rows.")

    # Print summary
    print("\n--- Ball in Court Disciplines Summary ---")
    for r in con.execute("SELECT discipline, count(*) FROM fact_ball_in_court_processes GROUP BY 1 ORDER BY 2 DESC").fetchall():
        print(" ", r)

    print("\n--- Document Transmittals Package Summary ---")
    for r in con.execute("SELECT project_package, count(*) FROM fact_document_transmittals GROUP BY 1 ORDER BY 2 DESC LIMIT 15").fetchall():
        print(" ", r)

    con.close()
    print("\nAll done successfully!")

if __name__ == '__main__':
    run_ingest()
