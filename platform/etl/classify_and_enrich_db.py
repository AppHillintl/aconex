import duckdb
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"

def run_enrichment():
    print(f"Connecting to DuckDB: {DB_PATH}")
    con = duckdb.connect(DB_PATH, read_only=False)

    print("\n--- 1. Updating dim_project_packages reference table ---")
    con.execute("""
    CREATE OR REPLACE TABLE dim_project_packages (
        project_id VARCHAR PRIMARY KEY,
        project_name VARCHAR,
        project_title VARCHAR,
        category VARCHAR,
        contract_no VARCHAR,
        contract_digits VARCHAR,
        k_package_no VARCHAR,
        contractor_name VARCHAR,
        contact_person VARCHAR,
        contact_email VARCHAR,
        sort_order INT
    );
    """)

    projects_metadata = [
        ('DP01', 'DP01', 'DP01 - Area 1 Basement & Superstructure', 'Wadi Yemm', 'REH.08.25.3121 / 3180', '3121', 'K03121', 'Orascom Construction SAE', 'Mr. Ihab Mehawed', 'ihab.mehawed@orascom.com', 1),
        ('DP02', 'DP02', 'DP02 - Area 2 Basement & Superstructure', 'Wadi Yemm', 'REH.08.25.3149 / 3270', '3149', 'K03149', 'CCC / ROWAD JV', 'Mr. Mohamed Tarek', 'mtarek@ccc.net', 2),
        ('DP03-East', 'DP03-East', 'DP03 East - Buildings & Infrastructure', 'Wadi Yemm', 'REH.08.26.3199', '3199', 'K03199', 'Innovo-Redcon JV', 'Mr. Mohamad Gamal / Mr. Omar ElGamal', 'mohamed.gamal@innovogroup.com; oelgamal@redconcon.com', 3),
        ('DP03-West', 'DP03-West', 'DP03 West - Buildings & Infrastructure', 'Wadi Yemm', 'REH.08.26.3271', '3271', 'K03271', 'CCC-ROWAD JV', 'Mr. Mohamed Tarek', 'mtarek@ccc.net', 4),
        ('DP04', 'DP04', 'DP04 - Buildings & Infrastructure', 'Wadi Yemm', 'REH.08.26.3204', '3204', 'K03204', 'Arabian Construction Company (ACC)', 'Mr. Maher Ali Ghassan Marahabi', 'maher@accsal.com', 5),
        ('DP05', 'DP05', 'DP05 - Buildings & Infrastructure', 'Wadi Yemm', 'REH.08.26.3205', '3205', 'K03205', 'Orascom Construction SAE', 'Mr. Ihab Mehawed', 'ihab.mehawed@orascom.com', 6),
        ('DP06', 'DP06', 'DP06 - Buildings & Infrastructure', 'Wadi Yemm', 'REH.08.26.3206', '3206', 'K03206', 'Hassan Allam Construction', 'Mr. Mohamed El Gozamy', 'mohamed.elgozamy@hassanallam.com', 7),
        ('DP07', 'DP07', 'DP07 - Buildings & Infrastructure', 'Wadi Yemm', 'REH.08.26.3207', '3207', 'K03207', 'CSCEC Egypt', 'Mr. WEI Jianxun', 'wei_jianxun@cscecos.com', 8),
        ('Grand Canal', 'Grand Canal', 'Grand Canal & Lagoon Excavation', 'Infrastructure & Strategic Projects', 'REH.08.26.3200', '3200', 'K03200 / P0801', 'Hassan Allam Construction', 'Mr. Mohamed El Gozamy', 'mohamed.elgozamy@hassanallam.com', 9),
        ('West Canal', 'West Canal', 'West Canal Excavation', 'Infrastructure & Strategic Projects', 'REH.08.25.3107', '3107', 'K03107 / P1201', 'Orascom Construction SAE', 'Mr. Ihab Mehawed', 'ihab.mehawed@orascom.com', 10),
        ('Infra', 'Infra', 'Primary Infrastructure & Utility (Package A East)', 'Infrastructure & Strategic Projects', 'REH.08.25.3048', '3048', 'K03048 / SW00', 'HAC / HARB JV', 'Mr. Mohamed El Gozamy', 'mohamed.elgozamy@hassanallam.com', 11),
        ('MMS / Substation', 'MMS / Substation', 'Main Power Supply Infrastructure & Substations (MMS)', 'Infrastructure & Strategic Projects', 'REH.08.25.3044', '3044', 'K03044 / MSS', 'El Sewedy Electric T&D – ROWAD Consortium', 'Eng. Hani Shehata / Mr. Mohamed Mahlab', 'hani.shehati@elsewedy.com; yelsaadany@rowad-rem.com', 12),
        ('RO Plant', 'RO Plant', 'Potable Water RO Desalination Plant', 'Infrastructure & Strategic Projects', 'REH.08.25.3045', '3045', 'K03045', 'Orascom-Trojan-Cox JV', 'Mr. Ihab Mehawed', 'ihab.mehawed@orascom.com', 13),
        ('STP', 'STP', 'Sewage Treatment Plant (STP)', 'Infrastructure & Strategic Projects', 'REH.08.25.3046', '3046', 'K03046 / P5576', 'Hassan Allam Construction', 'Mr. Mohamed Yousseff Eldahshoury', 'Mohamed.eldahshoury@hassanallam.com', 14),
        ('Airport', 'Airport', 'VVIP Airport & Airside Development', 'Infrastructure & Strategic Projects', 'REH.08.25.3049', '3049', 'K00146 / P0153', 'Orascom Construction SAE', 'Mr. Ihab Mehawed', 'ihab.mehawed@orascom.com', 15),
        ('Ring Road', 'Ring Road', 'Phase 1A Ring Road Project', 'Infrastructure & Strategic Projects', 'REH.04.25.3091', '3091', 'K03091 / RR00', 'Al Horema / Orascom', 'Al Horema Project Office', 'info@horema.com', 16),
        ('General Grading', 'General Grading', 'General Grading & Earth Works Phase 1A', 'Infrastructure & Strategic Projects', 'REH.08.25.3015', '3015', '', 'Orascom Construction SAE', 'Mr. Ihab Mehawed', 'ihab.mehawed@orascom.com', 17),
        ('Aedas Design Packages', 'Aedas Design Packages', 'Aedas Design Consultancy Services', 'Design Consultancy', 'REH0125300200', '3002', '', 'Aedas Limited', 'Aedas Ras El Hekma Team', 'aedas.raselhekma@aedas.com', 18),
        ('DP08 - South Golf', 'DP08 - South Golf', 'DP08 - South Golf Design Consultancy', 'Design Consultancy', 'REH0126321300', '3213', '', 'Dar SSH International', 'Dar SSH Team', 'info@darssh.com', 19),
        ('General Project Correspondence', 'General', 'General Project Deliverables & Multi-Package', 'General', '', '', '', 'PMC / Consortium', 'Hill International', 'DeanEnglish@hillintl.com', 20)
    ]

    con.executemany("""
    INSERT INTO dim_project_packages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, projects_metadata)
    print("dim_project_packages initialized with 20 project definitions.")

    # Helper function to add column if not exists
    def add_col_if_missing(table, col, col_type):
        cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table}')").fetchall()]
        if col not in cols:
            con.execute(f"ALTER TABLE \"{table}\" ADD COLUMN {col} {col_type};")
            print(f"Added column {col} to {table}")

    print("\n--- 2. Enriching fact_workflows (Exact Contract & Logics Hierarchy) ---")
    # Load / Refresh map_workflow_template_project from Templete.xlsx if available
    try:
        import openpyxl, re
        tpl_path = r"C:\Users\bimst\Downloads\ACONEX\Data\database\Templete.xlsx"
        if os.path.exists(tpl_path):
            wb = openpyxl.load_workbook(tpl_path, data_only=True)
            sheet = wb.active
            pkg_norm = {
                'DP01': 'DP01', 'DP02': 'DP02', 'DP03 East': 'DP03-East', 'DP03 West': 'DP03-West',
                'DP4': 'DP04', 'DP04': 'DP04', 'DP5': 'DP05', 'DP6': 'DP06', 'DP7': 'DP07',
                'Infra': 'Infra', 'RO': 'RO Plant', 'STP': 'STP', 'West Canal': 'West Canal',
                'Grand Canal': 'Grand Canal', 'Air Port': 'Airport', 'MSS': 'MMS / Substation'
            }
            con.execute("CREATE OR REPLACE TABLE map_workflow_template_project (template_name VARCHAR, norm_template VARCHAR, contract_number VARCHAR, contractor VARCHAR, source_project VARCHAR, canonical_package VARCHAR);")
            rows = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row and row[0]:
                    raw_tpl = str(row[0]).strip()
                    s_norm = re.sub(r'[\s\.\-]+', ' ', re.sub(r'\s+rev\s*\d+', '', raw_tpl.lower())).strip()
                    c_proj = pkg_norm.get(str(row[3]).strip() if row[3] else '', str(row[3]).strip() if row[3] else '')
                    rows.append((raw_tpl, s_norm, str(row[1] or ''), str(row[2] or ''), str(row[3] or ''), c_proj))
            con.executemany("INSERT INTO map_workflow_template_project VALUES (?, ?, ?, ?, ?, ?)", rows)
            con.execute("""
                UPDATE fact_workflows
                SET project_package = m.canonical_package
                FROM map_workflow_template_project m
                WHERE fact_workflows.template = m.template_name AND m.canonical_package IS NOT NULL AND m.canonical_package != '';
            """)
            print(f"Loaded {len(rows)} template mappings from Templete.xlsx.")
    except Exception as e:
        print(f"Template loading notice: {e}")
    add_col_if_missing("fact_workflows", "project_package", "VARCHAR")
    add_col_if_missing("fact_workflows", "project_category", "VARCHAR")

    t0 = time.time()
    con.execute(r"""
    UPDATE fact_workflows
    SET 
        project_package = CASE
            -- 1. Contract 3048 / Infra (HAC) - Highest priority for 3048, SW00, P000
            WHEN regexp_matches(workflow_name, '(?i)(3048|K03048|SW00|P000)') THEN 'Infra'
            WHEN initiator_organization ILIKE '%Hassan Allam%' AND regexp_matches(workflow_name, '(?i)(SW00|P000|Infra)') THEN 'Infra'

            -- 2. Contract 3200 / Grand Canal (HAC)
            WHEN regexp_matches(workflow_name, '(?i)(3200|K03200|P0801|Grand\s*Canal|Grand\s*Lagoon)') THEN 'Grand Canal'
            WHEN initiator_organization ILIKE '%Hassan Allam%' AND regexp_matches(workflow_name, '(?i)(md07|p0801|k03200)') THEN 'Grand Canal'

            -- 3. Contract 3107 / West Canal (Orascom)
            WHEN regexp_matches(workflow_name, '(?i)(3107|K03107|P1201|West\s*Canal)') THEN 'West Canal'

            -- 4. Contract 3046 / STP (HAC)
            WHEN regexp_matches(workflow_name, '(?i)(3046|K03046|P5576|Sewage\s*Treatment|\bSTP\b)') THEN 'STP'

            -- 5. Contract 3045 / RO Plant (Orascom/Trojan/Cox)
            WHEN regexp_matches(workflow_name, '(?i)(3045|K03045|Trojan|COX\s*JV|RO\s*Plant|Desalination|\bOTC\b)') THEN 'RO Plant'

            -- 6. Contract 3044 / MMS (Sewedy)
            WHEN regexp_matches(workflow_name, '(?i)(3044|K03044|EETD|\bMMS\b|Substation)') THEN 'MMS / Substation'

            -- 7. Contract 3049 / Airport (Orascom)
            WHEN regexp_matches(workflow_name, '(?i)(3049|K00146|P0153|Air\s*Port|Airport|Michael\s*Medhat|\bAR01\b|VVIP)') THEN 'Airport'

            -- 8. Contract 3121 / DP01 (Orascom)
            WHEN regexp_matches(workflow_name, '(?i)(3121|3180|K03121|DP-?0?1|MD-?0?1|Area\s*1\s*Basement|Hany\s*Youssef)') THEN 'DP01'

            -- 9. Contract 3271 / DP03-West (CCC-Rowad) - Precedes DP02 / CRJ generic match!
            WHEN regexp_matches(workflow_name, '(?i)(3271|K03271|RHD3|1301-RHD3|DP0?3-?West|DP3-?West)') THEN 'DP03-West'

            -- 10. Contract 3149 / DP02 (CCC-Rowad)
            WHEN regexp_matches(workflow_name, '(?i)(3149|3270|K03149|DP-?0?2|MD-?0?2|RHBW|1296-RHBW|Area\s*2\s*Basement)') THEN 'DP02'
            WHEN regexp_matches(workflow_name, '(?i)\bCRJ\b') AND NOT regexp_matches(workflow_name, '(?i)(3271|3199)') THEN 'DP02'

            -- 11. Contract 3199 / DP03-East (Innovo-Redcon) - Word boundaries for INR & INNRED!
            WHEN regexp_matches(workflow_name, '(?i)(3199|K03199|\bINR\b|\bINNRED\b|innovo-redcon|Michael\s*Kolta)') THEN 'DP03-East'

            -- 12. Generic DP03 Disambiguation
            WHEN regexp_matches(workflow_name, '(?i)(DP-?0?3|MD-?0?3)') AND initiator_organization ILIKE '%innovo%' THEN 'DP03-East'
            WHEN regexp_matches(workflow_name, '(?i)(DP-?0?3|MD-?0?3)') AND (initiator_organization ILIKE '%ccc%' OR initiator_organization ILIKE '%rowad%') THEN 'DP03-West'
            WHEN regexp_matches(workflow_name, '(?i)(DP0?3-?East|DP3-?East)') AND NOT regexp_matches(workflow_name, '(?i)(3271|K03271|RHD3)') THEN 'DP03-East'
            WHEN regexp_matches(workflow_name, '(?i)(DP-?0?3|MD-?0?3)') THEN 'DP03-West'

            -- 13. Other DP Packages
            WHEN regexp_matches(workflow_name, '(?i)(3204|K03204|DP-?0?4|MD-?0?4)') THEN 'DP04'
            WHEN regexp_matches(workflow_name, '(?i)(3205|K03205|DP-?0?5|MD-?0?5)') THEN 'DP05'
            WHEN regexp_matches(workflow_name, '(?i)(3206|K03206|DP-?0?6|MD-?0?6)') THEN 'DP06'
            WHEN regexp_matches(workflow_name, '(?i)(3207|K03207|DP-?0?7|MD-?0?7)') THEN 'DP07'

            -- 14. Infrastructure & Strategic
            WHEN regexp_matches(workflow_name, '(?i)(Ring\s*Road|Al\s*Horema|Horema)') THEN 'Ring Road'
            WHEN regexp_matches(workflow_name, '(?i)(3015|General\s*Grading)') THEN 'General Grading'

            ELSE 'General Workflows'
        END,
        project_category = CASE
            WHEN regexp_matches(workflow_name, '(?i)(3121|3180|3149|3270|3199|3271|3204|3205|3206|3207|DP-?0?[1-7]|MD-?0?[1-7]|RHBW|RHD3|\bINR\b|\bINNRED\b)') THEN 'Wadi Yemm'
            WHEN regexp_matches(workflow_name, '(?i)(3200|3107|3048|3044|3045|3046|3049|3091|3015|Canal|Infra|Airport|Substation|\bMMS\b|RO\s*Plant|\bSTP\b|Ring\s*Road)') THEN 'Infrastructure & Strategic Projects'
            ELSE 'General'
        END;
    """)
    print(f"fact_workflows enriched in {time.time() - t0:.2f} seconds!")

    print("\n--- 3. Enriching fact_mail (Exact Contract & Logics Hierarchy) ---")
    add_col_if_missing("fact_mail", "project_package", "VARCHAR")
    add_col_if_missing("fact_mail", "project_category", "VARCHAR")

    t0 = time.time()
    con.execute(r"""
    UPDATE fact_mail
    SET 
        project_package = CASE
            -- 1. Consultancies
            WHEN from_organization ILIKE '%Aedas%' OR recipients ILIKE '%Aedas%' OR mail_no LIKE 'AED-%' THEN 'Aedas Design Packages'
            WHEN from_organization ILIKE '%SSH%' OR mail_no LIKE 'SSH-%' OR regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(DP-?0?8|3213|South\s*Golf)') THEN 'DP08 - South Golf'

            -- 2. Specific Wadi Yemm Packages: DP07, DP06, DP05, DP04
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3207|K03207|DP-?0?7)') OR mail_no LIKE 'CSCECI-%' THEN 'DP07'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3206|K03206|DP-?0?6|REH/DP6|HYH)') THEN 'DP06'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3205|K03205|DP-?0?5)') THEN 'DP05'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(P1000)') AND NOT regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3205|DP-?0?5)') THEN 'DP06'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3204|K03204|DP-?0?4|MD-?0?4)') OR mail_no LIKE 'ACCE-%' THEN 'DP04'

            -- 3. Contract 3271 / DP03-West & Contract 3199 / DP03-East
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no || ' ' || from_organization, '(?i)(3271|K03271|RHD3|DCG\s*RHD3|1301-RHD3|DP0?3-?West|DP3-?West)') THEN 'DP03-West'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no || ' ' || from_organization, '(?i)(3199|K03199|\bINR\b|\bINNRED\b|innovo-redcon)') THEN 'DP03-East'
            WHEN from_name ILIKE '%Michael Kolta%' THEN 'DP03-East'

            -- 4. Generic DP03 Disambiguation
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(DP-?0?3|MD-?0?3)') AND (from_organization ILIKE '%innovo%' OR recipients ILIKE '%innovo%') THEN 'DP03-East'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(DP-?0?3|MD-?0?3)') AND (from_organization ILIKE '%ccc%' OR from_organization ILIKE '%rowad%') THEN 'DP03-West'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(DP0?3-?East|DP3-?East)') AND NOT regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3271|K03271|RHD3)') THEN 'DP03-East'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(DP-?0?3|MD-?0?3)') THEN 'DP03-West'

            -- 5. Contract 3149 / DP02
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no || ' ' || from_organization, '(?i)(3149|3270|K03149|DP-?0?2|MD-?0?2|RHBW|DCG\s*RHBW|Area\s*2\s*Basement)') THEN 'DP02'

            -- 6. Contract 3121 / DP01
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3121|3180|K03121|P0155|Sea\s*Town|DP-?0?1|MD-?0?1|Area\s*1\s*Basement)') THEN 'DP01'
            WHEN from_name ILIKE '%Hany Youssef%' THEN 'DP01'

            -- 7. Specialized Plants: RO Plant (3045, OTC, Trojan), STP (3046), MMS (3044)
            WHEN (regexp_matches(subject || ' ' || reference_number || ' ' || mail_no || ' ' || from_organization, '(?i)(3045|K03045|Trojan|COX\s*JV|RO\s*Plant|Desalination|\bOTC\b)') OR mail_no LIKE 'OTC-%')
                 AND NOT regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3049|Airport)') THEN 'RO Plant'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no || ' ' || from_organization, '(?i)(3044|K03044|EETD|\bMMS\b|Substation|Sewedy)') OR mail_no LIKE 'EERM-%' THEN 'MMS / Substation'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3046|K03046|P5576|Sewage\s*Treatment|\bSTP\b)') THEN 'STP'
            WHEN from_organization ILIKE '%Hassan Allam%' AND (recipients ILIKE '%Ayman Elsherif%' OR from_name ILIKE '%Ayman Elsherif%') AND subject ILIKE '%3046%' THEN 'STP'

            -- 8. Contract 3107 / West Canal (Orascom): 3107, P1201, Beshoy Ashraf
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3107|K03107|P1201|West\s*Canal)') THEN 'West Canal'
            WHEN from_name ILIKE '%Beshoy Ashraf%' AND NOT regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3205|DP-?0?5)') THEN 'West Canal'

            -- 9. Contract 3200 / Grand Canal (HAC): P0801, K03200, 3200, md07
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3200|K03200|P0801|MD-?0?7|Grand\s*Canal|Grand\s*Lagoon)') THEN 'Grand Canal'
            WHEN from_organization ILIKE '%Hassan Allam%' AND regexp_matches(subject || ' ' || reference_number, '(?i)(md07|p0801|k03200)') THEN 'Grand Canal'

            -- 10. Contract 3049 / Airport: 3049, P0153, AR01, Michael Medhat
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3049|K03049|P0153|Air\s*Port|Airport|\bAR01\b|VVIP)') 
                 AND NOT regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(P0155|Sea\s*Town|Wadi\s*Yemm|DP-?0?1|MD-?0?1)') THEN 'Airport'
            WHEN from_name ILIKE '%Michael Medhat%' THEN 'Airport'

            -- 11. Contract 3048 / Infra (HAC): SW00, P000, 3048
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3048|K03048|P000)') THEN 'Infra'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(\bSW00\b)') 
                 AND NOT regexp_matches(subject || ' ' || reference_number || ' ' || mail_no || ' ' || from_organization, '(?i)(OTC|Trojan|COX|3045|3046|STP|3044|MMS)') THEN 'Infra'
            WHEN from_organization ILIKE '%Hassan Allam%' AND regexp_matches(subject, '(?i)(SW00|P000|Infra)') THEN 'Infra'

            -- 12. Strategic / Roads
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(Ring\s*Road|Al\s*Horema|Horema)') THEN 'Ring Road'
            WHEN regexp_matches(subject || ' ' || reference_number, '(?i)(3015|General\s*Grading)') THEN 'General Grading'

            ELSE 'General Project Correspondence'
        END,
        project_category = CASE
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || from_organization || ' ' || recipients || ' ' || mail_no, '(?i)(3121|3180|3149|3270|3199|3271|3204|3205|3206|3207|DP-?0?[1-7]|MD-?0?[1-7]|RHBW|RHD3|\bINR\b|\bINNRED\b)') THEN 'Wadi Yemm'
            WHEN regexp_matches(subject || ' ' || reference_number || ' ' || mail_no, '(?i)(3200|3107|3048|3044|3045|3046|3049|3091|3015|Canal|Infra|Airport|Substation|\bMMS\b|\bMSS\b|RO\s*Plant|\bSTP\b|Ring\s*Road)') THEN 'Infrastructure & Strategic Projects'
            WHEN from_organization ILIKE '%Aedas%' OR from_organization ILIKE '%SSH%' THEN 'Design Consultancy'
            ELSE 'General'
        END;
    """)
    print(f"fact_mail enriched in {time.time() - t0:.2f} seconds!")

    print("\n--- 3.1 Applying Contractual 14-Day Overdue Rule for Letters ---")
    t_let = time.time()
    con.execute("""
    UPDATE fact_mail
    SET 
        due_date = COALESCE(due_date, sent_date + INTERVAL 14 DAY),
        is_overdue = CASE 
            WHEN status IN ('Closed-Out', 'Responded') THEN FALSE
            WHEN mail_no IN (SELECT mail_no FROM fact_mail_responses) THEN FALSE
            WHEN COALESCE(due_date, sent_date + INTERVAL 14 DAY) < CURRENT_TIMESTAMP THEN TRUE
            ELSE FALSE
        END,
        days_late = CASE 
            WHEN status IN ('Closed-Out', 'Responded') THEN 0
            WHEN mail_no IN (SELECT mail_no FROM fact_mail_responses) THEN 0
            WHEN COALESCE(due_date, sent_date + INTERVAL 14 DAY) < CURRENT_TIMESTAMP 
                THEN DATEDIFF('day', COALESCE(due_date, sent_date + INTERVAL 14 DAY), CURRENT_TIMESTAMP)
            ELSE 0
        END
    WHERE mail_type = 'Letter';
    """)
    ov_cnt = con.execute("SELECT count(*) FROM fact_mail WHERE mail_type = 'Letter' AND is_overdue = TRUE").fetchone()[0]
    print(f"14-Day SLA Overdue rule applied to all letters ({ov_cnt:,} overdue letters) in {time.time() - t_let:.2f}s!")

    print("\n--- 4. Enriching dim_documents (Exact Contract & Logics Hierarchy) ---")
    add_col_if_missing("dim_documents", "project_package", "VARCHAR")
    add_col_if_missing("dim_documents", "project_category", "VARCHAR")

    t0 = time.time()
    con.execute(r"""
    UPDATE dim_documents
    SET 
        project_package = CASE
            -- 1. Consultancies
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(DP08|3213|South\s*Golf)') THEN 'DP08 - South Golf'

            -- 2. Specific Wadi Yemm Packages: DP07, DP06, DP05, DP04
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3207|K03207|DP-?0?7)') THEN 'DP07'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3206|K03206|DP-?0?6|REH/DP6|HYH)') THEN 'DP06'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3205|K03205|DP-?0?5)') THEN 'DP05'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(P1000)') AND NOT regexp_matches(document_no || ' ' || title, '(?i)(3205|DP-?0?5)') THEN 'DP06'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3204|K03204|DP-?0?4|MD-?0?4)') THEN 'DP04'

            -- 3. Contract 3271 / DP03-West & Contract 3199 / DP03-East
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3271|K03271|RHD3|DP0?3-?West|DP3-?West)') THEN 'DP03-West'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3199|K03199|DP0?3-?East|DP3-?East|\bINR\b|\bINNRED\b)') THEN 'DP03-East'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(DP-?0?3|MD-?0?3)') THEN 'DP03-West'

            -- 4. Contract 3149 / DP02: K03149, 3149, RHBW, Area 2 Basement
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3149|3270|K03149|DP-?0?2|MD-?0?2|RHBW|Area\s*2\s*Basement)') THEN 'DP02'

            -- 5. Contract 3121 / DP01: 3121, MD01, Area 1 Basement, P0155, Sea Town
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3121|3180|K03121|P0155|Sea\s*Town|DP-?0?1|MD-?0?1|Area\s*1\s*Basement)') THEN 'DP01'

            -- 6. Specialized Plants: RO Plant (3045), STP (3046), MMS (3044)
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3045|K03045|RO\s*Plant|Potable\s*Water|\bOTC\b)') THEN 'RO Plant'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3044|K03044|Power\s*Supply|Substation|\bMSS\b|\bMMS\b|\bMPS\b)') THEN 'MMS / Substation'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3046|K03046|P5576|\bSTP\b|Sewage)') THEN 'STP'

            -- 7. Contract 3107 / West Canal (Orascom): 3107, P1201
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3107|K03107|P1201|West\s*Canal)') THEN 'West Canal'

            -- 8. Contract 3200 / Grand Canal (HAC): P0801, K03200, 3200, MD07
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3200|K03200|P0801|MD-?0?7|Grand\s*Canal|Grand\s*Lagoon)') THEN 'Grand Canal'

            -- 9. Contract 3049 / Airport: 3049, P0153, Airport
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3049|K03049|P0153|Airport|Air\s*Port|\bAR01\b|VVIP)')
                 AND NOT regexp_matches(document_no || ' ' || title, '(?i)(P0155|Sea\s*Town|Wadi\s*Yemm|DP-?0?1|MD-?0?1)') THEN 'Airport'

            -- 10. Contract 3048 / Infra (HAC): SW00, P000, 3048
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3048|K03048|P000|Primary\s*Infra)') THEN 'Infra'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(\bSW00\b)')
                 AND NOT regexp_matches(document_no || ' ' || title, '(?i)(OTC|Trojan|COX|3045|3046|STP|3044|MMS)') THEN 'Infra'

            -- 11. Infrastructure & Strategic
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3091|K03091|Ring\s*Road|Horema)') THEN 'Ring Road'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3015|General\s*Grading)') THEN 'General Grading'

            ELSE 'General Project Deliverables'
        END,
        project_category = CASE
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3121|3180|3149|3270|3199|3271|3204|3205|3206|3207|DP-?0?[1-7]|MD-?0?[1-7]|RHBW|RHD3|\bINR\b|\bINNRED\b)') THEN 'Wadi Yemm'
            WHEN regexp_matches(document_no || ' ' || title, '(?i)(3200|3107|3048|3044|3045|3046|3049|3091|3015|Canal|Infra|Airport|Substation|\bMMS\b|\bMSS\b|RO\s*Plant|\bSTP\b|Ring\s*Road)') THEN 'Infrastructure & Strategic Projects'
            ELSE 'General'
        END;
    """)
    con.execute("UPDATE dim_documents SET package_name = project_package WHERE project_package IS NOT NULL;")
    print(f"dim_documents enriched in {time.time() - t0:.2f} seconds!")

    print("\n--- 5. Enriching fact_rfis (Exact Contract & Logics Hierarchy) ---")
    add_col_if_missing("fact_rfis", "project_package", "VARCHAR")
    add_col_if_missing("fact_rfis", "project_category", "VARCHAR")

    t0 = time.time()
    con.execute(r"""
    UPDATE fact_rfis
    SET 
        project_package = CASE
            -- 1. Consultancies
            WHEN from_organization ILIKE '%Aedas%' OR recipients ILIKE '%Aedas%' OR mail_no LIKE 'AED-%' THEN 'Aedas Design Packages'
            WHEN from_organization ILIKE '%SSH%' OR mail_no LIKE 'SSH-%' OR regexp_matches(subject || ' ' || mail_no, '(?i)(DP-?0?8|3213|South\s*Golf)') THEN 'DP08 - South Golf'

            -- 2. Specific Wadi Yemm Packages: DP07, DP06, DP05, DP04
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3207|K03207|DP-?0?7)') OR mail_no LIKE 'CSCECI-%' THEN 'DP07'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3206|K03206|DP-?0?6|REH/DP6|HYH)') THEN 'DP06'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3205|K03205|DP-?0?5)') THEN 'DP05'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(P1000)') AND NOT regexp_matches(subject || ' ' || mail_no, '(?i)(3205|DP-?0?5)') THEN 'DP06'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3204|K03204|DP-?0?4|MD-?0?4)') OR mail_no LIKE 'ACCE-%' THEN 'DP04'

            -- 3. Contract 3271 / DP03-West & Contract 3199 / DP03-East
            WHEN regexp_matches(subject || ' ' || mail_no || ' ' || from_organization, '(?i)(3271|K03271|RHD3|DCG\s*RHD3|1301-RHD3|DP0?3-?West|DP3-?West)') THEN 'DP03-West'
            WHEN regexp_matches(subject || ' ' || mail_no || ' ' || from_organization, '(?i)(3199|K03199|\bINR\b|\bINNRED\b|innovo-redcon)') THEN 'DP03-East'
            WHEN from_name ILIKE '%Michael Kolta%' THEN 'DP03-East'

            -- 4. Generic DP03 Disambiguation
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(DP-?0?3|MD-?0?3)') AND (from_organization ILIKE '%innovo%' OR recipients ILIKE '%innovo%') THEN 'DP03-East'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(DP-?0?3|MD-?0?3)') AND (from_organization ILIKE '%ccc%' OR from_organization ILIKE '%rowad%') THEN 'DP03-West'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(DP0?3-?East|DP3-?East)') AND NOT regexp_matches(subject || ' ' || mail_no, '(?i)(3271|K03271|RHD3)') THEN 'DP03-East'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(DP-?0?3|MD-?0?3)') THEN 'DP03-West'

            -- 5. Contract 3149 / DP02
            WHEN regexp_matches(subject || ' ' || mail_no || ' ' || from_organization, '(?i)(3149|3270|K03149|DP-?0?2|MD-?0?2|RHBW|DCG\s*RHBW|Area\s*2\s*Basement)') THEN 'DP02'

            -- 6. Contract 3121 / DP01
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3121|3180|K03121|P0155|Sea\s*Town|DP-?0?1|MD-?0?1|Area\s*1\s*Basement)') THEN 'DP01'
            WHEN from_name ILIKE '%Hany Youssef%' THEN 'DP01'

            -- 7. Specialized Plants: RO Plant (3045, OTC, Trojan), STP (3046), MMS (3044)
            WHEN regexp_matches(subject || ' ' || mail_no || ' ' || from_organization, '(?i)(3045|K03045|Trojan|COX\s*JV|RO\s*Plant|Desalination|\bOTC\b)') OR mail_no LIKE 'OTC-%' THEN 'RO Plant'
            WHEN regexp_matches(subject || ' ' || mail_no || ' ' || from_organization, '(?i)(3044|K03044|EETD|\bMMS\b|Substation|Sewedy)') OR mail_no LIKE 'EERM-%' THEN 'MMS / Substation'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3046|K03046|P5576|Sewage\s*Treatment|\bSTP\b)') THEN 'STP'
            WHEN from_organization ILIKE '%Hassan Allam%' AND subject ILIKE '%3046%' THEN 'STP'

            -- 8. Contract 3107 / West Canal (Orascom): 3107, P1201, Beshoy Ashraf
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3107|K03107|P1201|West\s*Canal)') THEN 'West Canal'
            WHEN from_name ILIKE '%Beshoy Ashraf%' AND NOT regexp_matches(subject || ' ' || mail_no, '(?i)(3205|DP-?0?5)') THEN 'West Canal'

            -- 9. Contract 3200 / Grand Canal (HAC): P0801, K03200, 3200, md07
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3200|K03200|P0801|MD-?0?7|Grand\s*Canal|Grand\s*Lagoon)') THEN 'Grand Canal'
            WHEN from_organization ILIKE '%Hassan Allam%' AND regexp_matches(subject, '(?i)(md07|p0801|k03200)') THEN 'Grand Canal'

            -- 10. Contract 3049 / Airport: 3049, P0153, AR01, Michael Medhat
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3049|K03049|P0153|Air\s*Port|Airport|\bAR01\b|VVIP)')
                 AND NOT regexp_matches(subject || ' ' || mail_no, '(?i)(P0155|Sea\s*Town|Wadi\s*Yemm|DP-?0?1|MD-?0?1)') THEN 'Airport'
            WHEN from_name ILIKE '%Michael Medhat%' THEN 'Airport'

            -- 11. Contract 3048 / Infra (HAC): SW00, P000, 3048
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3048|K03048|P000)') THEN 'Infra'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(\bSW00\b)')
                 AND NOT regexp_matches(subject || ' ' || mail_no || ' ' || from_organization, '(?i)(OTC|Trojan|COX|3045|3046|STP|3044|MMS)') THEN 'Infra'
            WHEN from_organization ILIKE '%Hassan Allam%' AND regexp_matches(subject, '(?i)(SW00|P000|Infra)') THEN 'Infra'

            -- 12. Strategic / Roads
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(Ring\s*Road|Al\s*Horema|Horema)') THEN 'Ring Road'

            ELSE 'General RFIs'
        END,
        project_category = CASE
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3121|3180|3149|3270|3199|3271|3204|3205|3206|3207|DP-?0?[1-7]|MD-?0?[1-7]|RHBW|RHD3|\bINR\b|\bINNRED\b)') THEN 'Wadi Yemm'
            WHEN regexp_matches(subject || ' ' || mail_no, '(?i)(3200|3107|3048|3044|3045|3046|3049|3091|3015|Canal|Infra|Airport|Substation|\bMMS\b|\bMSS\b|RO\s*Plant|\bSTP\b|Ring\s*Road)') THEN 'Infrastructure & Strategic Projects'
            ELSE 'General'
        END;
    """)
    print(f"fact_rfis enriched in {time.time() - t0:.2f} seconds!")

    print("\n--- 6. Materializing agg_project_summary Table ---")
    con.execute("""
    CREATE OR REPLACE TABLE agg_project_summary AS
    WITH doc_counts AS (
        SELECT project_package, count(*) AS total_documents
        FROM dim_documents
        GROUP BY project_package
    ),
    mail_counts AS (
        SELECT 
            project_package, 
            count(*) AS total_mails,
            count(CASE WHEN is_overdue THEN 1 END) AS overdue_mails,
            count(CASE WHEN mail_type ILIKE '%Letter%' AND from_organization NOT ILIKE '%Hill Inter%' THEN 1 END) AS total_letters,
            count(CASE WHEN mail_type ILIKE '%Transmittal%' THEN 1 END) AS total_transmittals
        FROM fact_mail
        GROUP BY project_package
    ),
    rfi_counts AS (
        SELECT 
            project_package, 
            count(*) AS total_rfis,
            count(CASE WHEN is_overdue THEN 1 END) AS overdue_rfis
        FROM fact_rfis
        GROUP BY project_package
    ),
    wf_counts AS (
        SELECT 
            project_package, 
            count(*) AS total_workflows,
            count(CASE WHEN workflow_status = 'In Progress' OR workflow_status = 'Active' THEN 1 END) AS active_workflows,
            count(CASE WHEN overdue_steps_count > 0 THEN 1 END) AS overdue_workflows
        FROM fact_workflows
        GROUP BY project_package
    )
    SELECT 
        p.project_id,
        p.project_name,
        p.project_title,
        p.category,
        p.contract_no,
        p.contract_digits,
        p.k_package_no,
        p.contractor_name,
        p.contact_person,
        p.contact_email,
        p.sort_order,
        COALESCE(d.total_documents, 0) AS total_documents,
        COALESCE(m.total_mails, 0) AS total_mails,
        COALESCE(m.total_letters, 0) AS total_letters,
        COALESCE(m.total_transmittals, 0) AS total_transmittals,
        COALESCE(m.overdue_mails, 0) AS overdue_mails,
        COALESCE(r.total_rfis, 0) AS total_rfis,
        COALESCE(r.overdue_rfis, 0) AS overdue_rfis,
        COALESCE(w.total_workflows, 0) AS total_workflows,
        COALESCE(w.active_workflows, 0) AS active_workflows,
        COALESCE(w.overdue_workflows, 0) AS overdue_workflows
    FROM dim_project_packages p
    LEFT JOIN doc_counts d ON p.project_id = d.project_package
    LEFT JOIN mail_counts m ON p.project_id = m.project_package
    LEFT JOIN rfi_counts r ON p.project_id = r.project_package
    LEFT JOIN wf_counts w ON p.project_id = w.project_package
    ORDER BY p.sort_order;
    """)
    print("agg_project_summary materialized successfully!")

    print("\nVerification of agg_project_summary:")
    res = con.execute("""
        SELECT project_id, project_name, category, contractor_name, total_documents, total_mails, total_rfis, total_workflows
        FROM agg_project_summary
        ORDER BY sort_order;
    """).fetchall()
    for row in res:
        print(f"[{row[0]:12}] {row[1]:20} | Docs: {row[4]:7,d} | Mails: {row[5]:7,d} | RFIs: {row[6]:5,d} | WFs: {row[7]:5,d}")

    con.close()
    print("\nDatabase classification & enrichment completed 100% successfully!")

if __name__ == "__main__":
    run_enrichment()
