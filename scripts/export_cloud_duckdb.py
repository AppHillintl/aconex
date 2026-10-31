import os
import sys
import time
import shutil
import zipfile
from pathlib import Path
import duckdb

ROOT_DIR = Path(__file__).resolve().parent.parent

CLOUD_TABLES = [
    "agg_lookahead",
    "agg_org_scorecard",
    "agg_project_summary",
    "agg_step_bottlenecks",
    "agg_user_workload",
    "dim_documents",
    "dim_organizations",
    "dim_project_packages",
    "dim_user_directory",
    "fact_ball_in_court_processes",
    "fact_mail",
    "fact_rfis",
    "fact_workflow_steps",
    "fact_workflows",
    "user_custom_emails",
    "user_refresh_requests"
]

def build_cloud_database_and_zip(source_db_path=None, target_db_path=None, target_zip_path=None):
    """
    Exports dashboard tables from master local aconex.duckdb to a clean, compacted cloud DuckDB file,
    and compresses it into aconex_cloud.duckdb.zip for instant cloud upload.
    """
    t0 = time.time()
    source_db = Path(source_db_path) if source_db_path else ROOT_DIR / "aconex.duckdb"
    target_db = Path(target_db_path) if target_db_path else ROOT_DIR / "aconex_cloud_export.duckdb"
    target_zip = Path(target_zip_path) if target_zip_path else ROOT_DIR / "aconex_cloud.duckdb.zip"

    if not source_db.exists():
        raise FileNotFoundError(f"Source database '{source_db}' does not exist.")

    if target_db.exists():
        try:
            target_db.unlink()
        except Exception:
            pass

    # Create new clean target DuckDB
    con = duckdb.connect(str(target_db))
    con.execute(f"ATTACH '{str(source_db).replace('\\', '/')}' AS src (READ_ONLY)")

    # Query list of tables in src
    existing_tables = set(r[0] for r in con.execute("SELECT table_name FROM duckdb_tables() WHERE database_name = 'src'").fetchall())

    copied = 0
    for table in CLOUD_TABLES:
        try:
            if table in existing_tables:
                con.execute(f"CREATE TABLE {table} AS SELECT * FROM src.{table}")
                copied += 1
        except Exception as e:
            print(f"Warning: could not export table {table}: {e}")

    con.execute("DETACH src")
    con.close()

    raw_mb = target_db.stat().st_size / (1024 * 1024)
    print(f"[EXPORT] Successfully exported {copied} tables into {raw_mb:.2f} MB clean DuckDB ({time.time()-t0:.2f}s).")

    # Compress into zip
    tz0 = time.time()
    with zipfile.ZipFile(target_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(target_db, arcname="aconex_cloud.duckdb")

    zip_mb = target_zip.stat().st_size / (1024 * 1024)
    print(f"[ZIP] Compressed into {zip_mb:.2f} MB zip archive ({time.time()-tz0:.2f}s).")

    # Cleanup temporary uncompressed export
    if target_db.exists():
        target_db.unlink()

    return target_zip

if __name__ == "__main__":
    build_cloud_database_and_zip()
