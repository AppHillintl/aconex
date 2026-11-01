import os
import json
import uuid
import threading
from typing import Dict, List, Optional, Tuple

SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "dispatch_settings.json"))
_lock = threading.Lock()

DEFAULT_FALLBACK_SETTINGS = {
    "ssc_remind_emails": {
        "DP01": {
            "project_name": "DP01 - Area 1 Basement & Superstructure",
            "to": ["Ahmed-Tawfik@shakeregypt.com", "Khaled-Moawad@shakeregypt.com"],
            "cc": ["Moataz-Abdelraouf@shakeregypt.com", "mohamed.wageh@ecgsa.com", "DeanEnglish@hillintl.com", "HossameldinSwaify@hillintl.com", "MohamedEweis@hillintl.com"],
            "notes": "Zone DC: Ahmed Tawfik / Khaled Moawad (Shaker-ECG)"
        }
    },
    "rfi_remind_emails": [
        {
            "id": "rfi_dp03w_dar",
            "project": "DP03-West",
            "company": "DAR AL HANDASAH",
            "to": ["rfi.dar@dargroup.com", "ahmed.dar@dargroup.com"],
            "cc": ["DeanEnglish@hillintl.com", "MohamedEweis@hillintl.com", "HossameldinSwaify@hillintl.com"],
            "notes": "DP03-West Detailed Design Engineering determinations"
        }
    ],
    "gemini_config": {
        "api_key": "",
        "model": "gemini-3-flash-preview",
        "enabled": True
    }

}

def load_settings() -> dict:
    with _lock:
        if not os.path.exists(SETTINGS_PATH):
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_FALLBACK_SETTINGS, f, indent=2, ensure_ascii=False)
            return json.loads(json.dumps(DEFAULT_FALLBACK_SETTINGS))
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[dispatch_settings_service] Error reading settings: {e}")
            return json.loads(json.dumps(DEFAULT_FALLBACK_SETTINGS))

def save_settings(data: dict) -> bool:
    with _lock:
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            temp_path = SETTINGS_PATH + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, SETTINGS_PATH)
            return True
        except Exception as e:
            print(f"[dispatch_settings_service] Error saving settings: {e}")
            return False

def get_ssc_remind_emails() -> dict:
    data = load_settings()
    return data.get("ssc_remind_emails", {})

def save_ssc_remind_email(project: str, to_list: List[str], cc_list: List[str], project_name: str = "", notes: str = "") -> dict:
    data = load_settings()
    if "ssc_remind_emails" not in data:
        data["ssc_remind_emails"] = {}
    
    clean_to = [e.strip() for e in to_list if e.strip() and "@" in e]
    clean_cc = [e.strip() for e in cc_list if e.strip() and "@" in e]
    
    data["ssc_remind_emails"][project] = {
        "project_name": project_name or data["ssc_remind_emails"].get(project, {}).get("project_name", project),
        "to": clean_to,
        "cc": clean_cc,
        "notes": notes or data["ssc_remind_emails"].get(project, {}).get("notes", "")
    }
    save_settings(data)
    return data["ssc_remind_emails"][project]

def get_rfi_remind_emails() -> list:
    data = load_settings()
    return data.get("rfi_remind_emails", [])

def save_rfi_remind_email(project: str, company: str, to_list: List[str], cc_list: List[str], notes: str = "", entry_id: Optional[str] = None) -> dict:
    data = load_settings()
    if "rfi_remind_emails" not in data:
        data["rfi_remind_emails"] = []

    clean_to = [e.strip() for e in to_list if e.strip() and "@" in e]
    clean_cc = [e.strip() for e in cc_list if e.strip() and "@" in e]

    if not entry_id:
        entry_id = f"rfi_{uuid.uuid4().hex[:8]}"
        new_entry = {
            "id": entry_id,
            "project": project,
            "company": company,
            "to": clean_to,
            "cc": clean_cc,
            "notes": notes
        }
        data["rfi_remind_emails"].append(new_entry)
        save_settings(data)
        return new_entry
    else:
        found = False
        target_entry = None
        for item in data["rfi_remind_emails"]:
            if item.get("id") == entry_id:
                item["project"] = project
                item["company"] = company
                item["to"] = clean_to
                item["cc"] = clean_cc
                item["notes"] = notes
                target_entry = item
                found = True
                break
        if not found:
            target_entry = {
                "id": entry_id,
                "project": project,
                "company": company,
                "to": clean_to,
                "cc": clean_cc,
                "notes": notes
            }
            data["rfi_remind_emails"].append(target_entry)
        save_settings(data)
        return target_entry

def delete_rfi_remind_email(entry_id: str) -> bool:
    data = load_settings()
    if "rfi_remind_emails" not in data:
        return False
    orig_len = len(data["rfi_remind_emails"])
    data["rfi_remind_emails"] = [e for e in data["rfi_remind_emails"] if e.get("id") != entry_id]
    if len(data["rfi_remind_emails"]) < orig_len:
        save_settings(data)
        return True
    return False

def resolve_ssc_contacts(project_id: str) -> Tuple[List[str], List[str]]:
    """
    Returns (to_emails, cc_emails) for SSC reminders for a project.
    Checks saved in-app settings first, otherwise returns empty lists.
    """
    ssc_map = get_ssc_remind_emails()
    # Direct match or case-insensitive match
    for k, v in ssc_map.items():
        if k.upper() == project_id.upper() or (project_id.upper() in k.upper()):
            return v.get("to", []), v.get("cc", [])
    return [], []

def resolve_rfi_contacts(project_id: str, company_name: str) -> Tuple[List[str], List[str]]:
    """
    Returns (to_emails, cc_emails) for an RFI reminder for a given project and responsible company.
    1. Exact match on both project and company.
    2. Company match with project == 'All Packages'.
    3. Project match with company == 'All Companies'.
    4. Fallback defaults.
    """
    rfi_list = get_rfi_remind_emails()
    pid_norm = (project_id or "").strip().lower()
    comp_norm = (company_name or "").strip().lower()

    # 1. Exact match
    for item in rfi_list:
        p = item.get("project", "").strip().lower()
        c = item.get("company", "").strip().lower()
        if (p == pid_norm or pid_norm in p) and (c == comp_norm or comp_norm in c):
            return item.get("to", []), item.get("cc", [])

    # 2. Company match with 'All Packages'
    for item in rfi_list:
        p = item.get("project", "").strip().lower()
        c = item.get("company", "").strip().lower()
        if (p in ["all packages", "all", "all projects", "*"]) and (c == comp_norm or comp_norm in c):
            return item.get("to", []), item.get("cc", [])

    # 3. Project match with 'All Companies'
    for item in rfi_list:
        p = item.get("project", "").strip().lower()
        c = item.get("company", "").strip().lower()
        if (p == pid_norm or pid_norm in p) and (c in ["all companies", "all", "*"]):
            return item.get("to", []), item.get("cc", [])

    # Default fallback: Dean English & PMC
    return ["DeanEnglish@hillintl.com"], ["MohamedEweis@hillintl.com", "HossameldinSwaify@hillintl.com"]

def get_gemini_config() -> dict:
    data = load_settings()
    cfg = data.get("gemini_config", {})
    # Also support environment variable if not in JSON
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if not cfg.get("api_key") and env_key:
        cfg["api_key"] = env_key
    return cfg

def save_gemini_config(api_key: str, model: str = "gemini-3-flash-preview", enabled: bool = True) -> dict:
    data = load_settings()
    data["gemini_config"] = {
        "api_key": api_key.strip(),
        "model": model.strip() or "gemini-3-flash-preview",
        "enabled": enabled
    }
    save_settings(data)
    # Also set in os.environ for current runtime session
    if api_key.strip():
        os.environ["GEMINI_API_KEY"] = api_key.strip()
    return data["gemini_config"]
