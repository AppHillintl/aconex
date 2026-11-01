import openpyxl
import duckdb
import os
import re

DB_PATH = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb"
KEY_PACKAGES_PATH = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up\database\Key of Packages.xlsx"
PACKAGES_DATA_PATH = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up\database\Project Packages Data (002) (003).xlsx"

def populate_dim_project_packages():
    print("Building dim_project_packages from database workbooks...")
    
    # 1. Read Key of Packages
    wb1 = openpyxl.load_workbook(KEY_PACKAGES_PATH, data_only=True)
    ws1 = wb1['projecrt']
    packages_map = {}
    for r in range(2, ws1.max_row + 1):
        pkg_no = str(ws1.cell(r, 1).value or '').strip()
        contract_no = str(ws1.cell(r, 2).value or '').strip()
        pkg_name = str(ws1.cell(r, 3).value or '').strip()
        contractor = str(ws1.cell(r, 4).value or '').strip()
        project = str(ws1.cell(r, 5).value or '').strip()
        if project:
            clean_digits = re.findall(r'\d{4}', contract_no)
            digits = clean_digits[0] if clean_digits else ''
            packages_map[project.upper()] = {
                'project_name': project,
                'pkg_no': pkg_no,
                'contract_no': contract_no,
                'pkg_name': pkg_name,
                'contractor': contractor,
                'contract_digits': digits
            }
            
    # 2. Read Project Packages Data (Sheet2)
    wb2 = openpyxl.load_workbook(PACKAGES_DATA_PATH, data_only=True)
    ws2 = wb2['Sheet2']
    contacts = []
    for r in range(2, ws2.max_row + 1):
        name = str(ws2.cell(r, 1).value or '').strip()
        contract_no = str(ws2.cell(r, 2).value or '').strip()
        title = str(ws2.cell(r, 3).value or '').strip()
        type_ = str(ws2.cell(r, 4).value or '').strip()
        contractor = str(ws2.cell(r, 5).value or '').strip()
        person = str(ws2.cell(r, 6).value or '').strip()
        raw_email = str(ws2.cell(r, 7).value or '').strip().lstrip(':').strip()
        
        if contractor or raw_email or name:
            clean_digits = re.findall(r'\d{4}', contract_no)
            digits = clean_digits[0] if clean_digits else ''
            
            # Match with key packages
            matched_k = ''
            for k_proj, k_data in packages_map.items():
                if digits and digits == k_data['contract_digits']:
                    matched_k = k_data['pkg_no']
                    break
                if name and name.upper() in k_proj:
                    matched_k = k_data['pkg_no']
                    break
                    
            clean_emails = [em.strip() for em in re.split(r'[\n;, ]+', raw_email) if '@' in em]
            contact_email = "; ".join(clean_emails)
            
            contacts.append((
                name or f"Package {digits}",
                matched_k,
                contract_no,
                digits,
                title,
                contractor,
                person,
                contact_email
            ))

    print(f"Parsed {len(contacts)} package records with official contacts.")
    
    con = duckdb.connect(DB_PATH, read_only=False)
    
    con.execute("""
    CREATE OR REPLACE TABLE dim_project_packages (
        package_name VARCHAR,
        k_package_no VARCHAR,
        contract_no VARCHAR,
        contract_digits VARCHAR,
        package_title VARCHAR,
        contractor_name VARCHAR,
        contact_person VARCHAR,
        contact_email VARCHAR
    );
    """)
    
    con.executemany("""
    INSERT INTO dim_project_packages VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, contacts)
    
    print("Populating user_custom_emails defaults from dim_project_packages...")
    # Seed user_custom_emails with primary contractor emails
    con.execute("""
    CREATE TABLE IF NOT EXISTS user_custom_emails (
        user_name VARCHAR PRIMARY KEY,
        email VARCHAR,
        organization VARCHAR,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Specific mappings for the exact Aconex organization names
    org_email_seed = [
        ('Orascom Construction SAE', 'ihab.mehawed@orascom.com', 'Orascom Construction'),
        ('Orascom Construction', 'ihab.mehawed@orascom.com', 'Orascom Construction'),
        ('Orascom Construction – Trojan – COX JV', 'ihab.mehawed@orascom.com', 'Orascom Construction'),
        ('Consolidated Contractors Group S.A.L. (Offshore) (CCC)', 'mtarek@ccc.net', 'CCC'),
        ('Rowad Modern Engineering', 'mtarek@ccc.net; yelsaadany@rowad-rem.com', 'Rowad'),
        ('CCC / ROWAD JV', 'mtarek@ccc.net', 'CCC / ROWAD JV'),
        ('Hassan Allam Construction', 'mohamed.elgozamy@hassanallam.com; Mohamed.eldahshoury@hassanallam.com', 'Hassan Allam Construction'),
        ('innovo-redcon', 'mohamed.gamal@innovogroup.com; michael.sidhom@innovogroup.com; oelgamal@redconcon.com; eman.salah@redconcon.com', 'innovo-redcon'),
        ('Innovo Build', 'mohamed.gamal@innovogroup.com', 'Innovo Build'),
        ('Redcon Construction', 'oelgamal@redconcon.com; eman.salah@redconcon.com', 'Redcon Construction'),
        ('Arabian Construction Company (ACC)', 'maher@accsal.com', 'Arabian Construction Company (ACC)'),
        ('ACC for Engineering Development Company', 'maher@accsal.com', 'ACC'),
        ('CSCEC EGYPT', 'wei_jianxun@cscecos.com', 'CSCEC EGYPT'),
        ('China State Construction Engineering Corporation Limited', 'wei_jianxun@cscecos.com', 'CSCEC EGYPT'),
        ('EETD-RME | Consortium ELSEWEDY & ROWAD', 'hani.shehati@elsewedy.com; yelsaadany@rowad-rem.com', 'Elsewedy & Rowad'),
        ('El Sewedy Electric for Trading and Distribution S.A.E', 'hani.shehati@elsewedy.com', 'Elsewedy'),
        ('Shaker-ECG consortium RASELHEKMA', 'amahmoud@shakerconsultancy.com', 'Shaker-ECG'),
        ('SHAKER CONSULTANCY GROUP', 'amahmoud@shakerconsultancy.com', 'Shaker'),
        ('ENGINEERING CONSULTANTS GROUP S.A.', 'amahmoud@shakerconsultancy.com', 'ECG'),
        ('Engineering Consultants Group (ECG)', 'amahmoud@shakerconsultancy.com', 'ECG'),
        ('Aedas', 'aedas.raselhekma@aedas.com', 'Aedas'),
        ('Aedas Limited', 'aedas.raselhekma@aedas.com', 'Aedas'),
        ('Hill International', 'pmc-controls@hillintl.com', 'Hill International'),
        ('Hill International (North Africa) Ltd.', 'pmc-controls@hillintl.com', 'Hill International'),
        ('Modon', 'controls-reh@modon.ae', 'Modon')
    ]
    
    for u_name, email, org in org_email_seed:
        con.execute("""
        INSERT OR REPLACE INTO user_custom_emails (user_name, email, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP);
        """, [u_name, email])
        
    con.close()
    print("dim_project_packages and user_custom_emails populated successfully!")

if __name__ == "__main__":
    populate_dim_project_packages()
