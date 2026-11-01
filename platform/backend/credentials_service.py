import os
import json
import time
import secrets
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CREDENTIALS_JSON = ROOT_DIR / "user_credentials.json"
BACKUP_JSON = ROOT_DIR / "Data" / "database" / "user_credentials.json"

def _load_json_credentials() -> Dict[str, dict]:
    """Loads credentials mapping from disk JSON file."""
    for path in [CREDENTIALS_JSON, BACKUP_JSON]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def _save_json_credentials(data: Dict[str, dict]):
    """Persists credentials mapping to disk JSON files for cloud resilience."""
    try:
        with open(CREDENTIALS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
    try:
        BACKUP_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(BACKUP_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Cryptographically hashes password with PBKDF2-HMAC-SHA256 (100k rounds) + unique salt."""
    if not salt:
        salt = secrets.token_hex(16)
    pwd_bytes = password.strip().encode("utf-8")
    salt_bytes = bytes.fromhex(salt)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, 100000).hex()
    return pwd_hash, salt

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Constant-time verification of password against stored hash."""
    if not password or not stored_hash or not salt:
        return False
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)

def _get_write_db(db_path=None):
    """Returns a writeable DuckDB connection."""
    import main as backend_main
    path = db_path or getattr(backend_main, 'DB_PATH', 'aconex.duckdb')
    import duckdb
    return duckdb.connect(path, read_only=False)

def ensure_credentials_table(con=None):
    """Creates user_credentials table in DuckDB if not present and syncs with JSON."""
    own_con = False
    if con is None:
        try:
            con = _get_write_db()
            own_con = True
        except Exception:
            return
    try:
        # Check if table exists
        has_table = con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'user_credentials'").fetchone()[0] > 0
        if not has_table:
            # Need writeable connection to create table
            con_w = _get_write_db()
            con_w.execute("""
                CREATE TABLE IF NOT EXISTS user_credentials (
                    email VARCHAR PRIMARY KEY,
                    password_hash VARCHAR NOT NULL,
                    salt VARCHAR NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                );
            """)
            con_w.close()

        # If DB table is empty but JSON has records, sync DB from JSON
        count = con.execute("SELECT count(*) FROM user_credentials").fetchone()[0]
        json_data = _load_json_credentials()
        if count == 0 and json_data:
            con_w = _get_write_db()
            for email, cred in json_data.items():
                con_w.execute("""
                    INSERT OR REPLACE INTO user_credentials (email, password_hash, salt, created_at, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, [email.lower().strip(), cred["password_hash"], cred["salt"]])
            con_w.close()
    except Exception as e:
        pass
    finally:
        if own_con:
            con.close()

def get_user_credential(con, email: str) -> Optional[dict]:
    """Retrieves user password hash and salt from DuckDB or JSON fallback."""
    clean_email = email.lower().strip()
    # Check DuckDB
    try:
        ensure_credentials_table(con)
        row = con.execute("SELECT password_hash, salt FROM user_credentials WHERE LOWER(email) = ?", [clean_email]).fetchone()
        if row:
            return {"password_hash": row[0], "salt": row[1]}
    except Exception:
        pass

    # Check JSON fallback
    json_data = _load_json_credentials()
    if clean_email in json_data:
        return json_data[clean_email]

    return None

def save_user_credential(con, email: str, password: str) -> bool:
    """Hashes and saves a user's personal password to both DuckDB and persistent JSON."""
    clean_email = email.lower().strip()
    pwd_hash, salt = hash_password(password)

    # 1. Save to JSON
    json_data = _load_json_credentials()
    json_data[clean_email] = {
        "password_hash": pwd_hash,
        "salt": salt,
        "updated_at": time.time()
    }
    _save_json_credentials(json_data)

    # 2. Save to DuckDB
    try:
        ensure_credentials_table()
        con_w = _get_write_db()
        con_w.execute("""
            INSERT OR REPLACE INTO user_credentials (email, password_hash, salt, created_at, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, [clean_email, pwd_hash, salt])
        con_w.close()
    except Exception as e:
        print(f"Warning: could not write credential to DuckDB: {e}")

    return True

def record_user_login(con, email: str):
    """Updates last_login timestamp."""
    try:
        con_w = _get_write_db()
        con_w.execute("UPDATE user_credentials SET last_login = CURRENT_TIMESTAMP WHERE LOWER(email) = ?", [email.lower().strip()])
        con_w.close()
    except Exception:
        pass
