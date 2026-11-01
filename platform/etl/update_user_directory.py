import os
from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent

DB_PATH = os.environ.get("DUCKDB_PATH") or os.environ.get("DB_PATH") or str(ROOT_DIR / "aconex.duckdb")
con = duckdb.connect(DB_PATH, read_only=False)

print(f"Ingesting project directory into {DB_PATH}...")

csv_path = ROOT_DIR / "Data" / "update" / "Up" / "Project Directory.csv"
if not csv_path.exists():
    csv_path = ROOT_DIR / "Data" / "project directory.csv"

if not csv_path.exists():
    print(f"Error: {csv_path} does not exist!")
    con.close()
    exit(1)

print(f"Reading from {csv_path}...")
csv_str = str(csv_path).replace("\\", "/")

con.execute(f"""
    CREATE OR REPLACE TABLE stg_project_directory AS 
    SELECT * FROM read_csv_auto('{csv_str}', header=True, ignore_errors=true, union_by_name=True);
""")

con.execute("""
    CREATE OR REPLACE TABLE dim_user_directory AS
    SELECT 
        trim(user_name) AS user_name,
        trim(regexp_replace(user_name, '^(Mr|Mrs|Ms|Dr|Eng)\\s+', '', 'i')) AS clean_name,
        trim(email) AS email,
        trim(organization_name) AS organization_name,
        trim(position) AS position,
        trim(user_type) AS user_type
    FROM stg_project_directory
    WHERE user_name IS NOT NULL;
""")

con.execute("""
    CREATE TABLE IF NOT EXISTS user_custom_emails (
        user_name VARCHAR PRIMARY KEY,
        email VARCHAR,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

con.execute("""
    CREATE TABLE IF NOT EXISTS smtp_settings (
        id INTEGER PRIMARY KEY,
        smtp_host VARCHAR,
        smtp_port INTEGER,
        smtp_user VARCHAR,
        smtp_password VARCHAR,
        sender_email VARCHAR,
        sender_name VARCHAR,
        use_tls BOOLEAN DEFAULT TRUE,
        is_active BOOLEAN DEFAULT FALSE
    );
""")

total = con.execute("SELECT count(*) FROM dim_user_directory").fetchone()[0]
with_email = con.execute("SELECT count(*) FROM dim_user_directory WHERE email IS NOT NULL AND email != ''").fetchone()[0]
hill_emails = con.execute("SELECT count(*) FROM dim_user_directory WHERE lower(email) LIKE '%@hillintl.com'").fetchone()[0]
print(f"[SUCCESS] dim_user_directory updated: {total} users, {with_email} with email, {hill_emails} Hill corporate emails.")

con.close()
print("DuckDB user directory update complete.")
