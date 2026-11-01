import re

# Official Project Packages and Contractor Directory
# Extracted from Key of Packages.xlsx & Project Packages Data
PACKAGE_DEFINITIONS = [
    {
        "id": "DP01",
        "name": "DP01 - Area 1 Basement & Superstructure",
        "k_code": "K03121",
        "contracts": ["3121", "3180", "REH.08.25.3121", "REH.08.25.3180"],
        "patterns": [r"K03121", r"3121", r"3180", r"P0155", r"Sea\s*Town", r"\bDP-?0?1\b", r"\bMD-?0?1\b", r"Wadi\s*Yemm.*Area\s*1"],
        "contractor": "Orascom Construction SAE",
        "org_aliases": ["orascom", "oc", "orascom construction"],
        "emails": ["ihab.mehawed@orascom.com"]
    },
    {
        "id": "DP02",
        "name": "DP02 - Area 2 Basement & Superstructure",
        "k_code": "K03149",
        "contracts": ["3149", "3270", "REH.08.25.3149", "REH.08.26.3270"],
        "patterns": [r"K03149", r"3149", r"3270", r"\bDP-?0?2\b", r"\bMD-?0?2\b", r"Area\s*2\s*Basement"],
        "contractor": "CCC / ROWAD JV",
        "org_aliases": ["ccc", "rowad", "crj", "ccc / rowad", "consolidated contractors", "rowad modern engineering"],
        "emails": ["mtarek@ccc.net"]
    },
    {
        "id": "DP03_EAST",
        "name": "DP03 East - Buildings & Infrastructure",
        "k_code": "K03199",
        "contracts": ["3199", "REH.08.26.3199"],
        "patterns": [r"K03199", r"3199", r"DP-?0?3\s*East", r"DP3\s*East"],
        "contractor": "Innovo-Redcon JV",
        "org_aliases": ["innovo", "redcon", "innovo-redcon", "innovo build", "redcon construction"],
        "emails": ["mohamed.gamal@innovogroup.com", "michael.sidhom@innovogroup.com", "oelgamal@redconcon.com", "eman.salah@redconcon.com"]
    },
    {
        "id": "DP03_WEST",
        "name": "DP03 West - Buildings & Infrastructure",
        "k_code": "K03271",
        "contracts": ["3271", "REH.08.26.3271"],
        "patterns": [r"K03271", r"3271", r"DP-?0?3\s*West", r"DP3\s*West"],
        "contractor": "CCC-ROWAD JV",
        "org_aliases": ["ccc-rowad", "ccc / rowad jv", "ccc", "rowad"],
        "emails": ["mtarek@ccc.net"]
    },
    {
        "id": "DP03_GEN",
        "name": "DP03 - Buildings & Infrastructure",
        "k_code": "",
        "contracts": [],
        "patterns": [r"\bDP-?0?3\b", r"\bMD-?0?3\b"],
        "contractor": "Innovo / CCC-Rowad",
        "org_aliases": ["innovo", "redcon", "ccc", "rowad"],
        "emails": ["mohamed.gamal@innovogroup.com", "mtarek@ccc.net"]
    },
    {
        "id": "DP04",
        "name": "DP04 - Buildings & Infrastructure",
        "k_code": "",
        "contracts": ["3204", "REH.08.26.3204"],
        "patterns": [r"3204", r"\bDP-?0?4\b", r"\bMD-?0?4\b"],
        "contractor": "Arabian Construction Company (ACC)",
        "org_aliases": ["acc", "arabian construction"],
        "emails": ["maher@accsal.com"]
    },
    {
        "id": "DP05",
        "name": "DP05 - Buildings & Infrastructure",
        "k_code": "",
        "contracts": ["3205", "REH.08.26.3205"],
        "patterns": [r"3205", r"K03205", r"\bDP-?0?5\b", r"\bMD-?0?5\b"],
        "contractor": "Orascom Construction SAE",
        "org_aliases": ["orascom", "oc"],
        "emails": ["ihab.mehawed@orascom.com"]
    },
    {
        "id": "DP06",
        "name": "DP06 - Buildings & Infrastructure",
        "k_code": "",
        "contracts": ["3206", "REH.08.26.3206"],
        "patterns": [r"3206", r"K03206", r"\bDP-?0?6\b", r"REH/DP6", r"\bHYH\b"],
        "contractor": "Hassan Allam Construction",
        "org_aliases": ["hassan allam", "hac"],
        "emails": ["mohamed.elgozamy@hassanallam.com"]
    },
    {
        "id": "DP07",
        "name": "DP07 - Buildings & Infrastructure",
        "k_code": "",
        "contracts": ["3207", "REH.08.26.3207"],
        "patterns": [r"3207", r"K03207", r"\bDP-?0?7\b"],
        "contractor": "CSCEC Egypt",
        "org_aliases": ["cscec", "china state"],
        "emails": ["wei_jianxun@cscecos.com"]
    },
    {
        "id": "GRAND_CANAL",
        "name": "Grand Canal & Lagoon Excavation",
        "k_code": "K03200",
        "contracts": ["3200", "REH.08.26.3200"],
        "patterns": [r"K03200", r"3200", r"P0801", r"\bMD-?0?7\b", r"Grand\s*Canal", r"Grand\s*Lagoon"],
        "contractor": "Hassan Allam Construction",
        "org_aliases": ["hassan allam", "hac"],
        "emails": ["mohamed.elgozamy@hassanallam.com"]
    },
    {
        "id": "WEST_CANAL",
        "name": "West Canal Excavation",
        "k_code": "K03107",
        "contracts": ["3107", "REH.08.25.3107"],
        "patterns": [r"K03107", r"3107", r"P1201", r"West\s*Canal"],
        "contractor": "Orascom Construction SAE",
        "org_aliases": ["orascom", "oc"],
        "emails": ["ihab.mehawed@orascom.com"]
    },
    {
        "id": "INFRA_EAST",
        "name": "Primary Infrastructure & Utility (Package A)",
        "k_code": "K03048",
        "contracts": ["3048", "REH.08.25.3048"],
        "patterns": [r"K03048", r"3048", r"\bSW00\b", r"Primary\s*Infra", r"Utility\s*Dist"],
        "contractor": "HAC / HARB JV",
        "org_aliases": ["hac", "harb", "hassan allam"],
        "emails": ["mohamed.elgozamy@hassanallam.com"]
    },
    {
        "id": "AIRPORT",
        "name": "VVIP Airport & Airside Development",
        "k_code": "K03049",
        "contracts": ["3049", "REH.08.25.3049"],
        "patterns": [r"K03049", r"3049", r"P0153", r"\bAR01\b", r"\bAP0?0?\b", r"Airport", r"Air\s*Port", r"VVIP\s*Terminal", r"REHIA"],
        "contractor": "Orascom Construction SAE",
        "org_aliases": ["orascom", "oc"],
        "emails": ["ihab.mehawed@orascom.com"]
    },
    {
        "id": "RING_ROAD",
        "name": "Phase 1A Ring Road Project",
        "k_code": "K03091",
        "contracts": ["3091", "REH.08.25.3091"],
        "patterns": [r"K03091", r"3091", r"\bRR0?0?\b", r"Ring\s*Road", r"Horema"],
        "contractor": "Al Horema / Orascom",
        "org_aliases": ["horema", "al horema"],
        "emails": ["ihab.mehawed@orascom.com"]
    },
    {
        "id": "RO_PLANT",
        "name": "Potable Water RO Plant",
        "k_code": "K03045",
        "contracts": ["3045", "REH08.25.3045", "REH.08.25.3045"],
        "patterns": [r"K03045", r"3045", r"RO\s*Plant", r"Potable\s*Water", r"\bRO\b", r"Desalination"],
        "contractor": "Orascom-Trojan-Cox JV",
        "org_aliases": ["trojan", "cox", "orascom"],
        "emails": ["ihab.mehawed@orascom.com"]
    },
    {
        "id": "POWER_SUPPLY",
        "name": "Main Power Supply Infrastructure (PS)",
        "k_code": "K03044",
        "contracts": ["3044", "REH08.25.3044", "REH.08.25.3044"],
        "patterns": [r"K03044", r"3044", r"Power\s*Supply", r"Substation", r"\bMPS\b"],
        "contractor": "El Sewedy Electric T&D – ROWAD Consortium",
        "org_aliases": ["elsewedy", "sewedy", "rowad", "eetd-rme"],
        "emails": ["hani.shehati@elsewedy.com", "yelsaadany@rowad-rem.com"]
    },
    {
        "id": "STP",
        "name": "Sewage Treatment Plant (STP)",
        "k_code": "K03046",
        "contracts": ["3046", "REH08.25.3046", "REH.08.25.3046"],
        "patterns": [r"K03046", r"3046", r"\bSTP\b", r"Sewage\s*Treatment", r"Sewage"],
        "contractor": "Hassan Allam Construction",
        "org_aliases": ["hassan allam", "hac"],
        "emails": ["Mohamed.eldahshoury@hassanallam.com"]
    },
    {
        "id": "MARINE",
        "name": "Marine Works & Coastal Protection",
        "k_code": "K03050",
        "contracts": ["3050", "REH.08.25.3050"],
        "patterns": [r"K03050", r"3050", r"Marine", r"Coastal"],
        "contractor": "Marine Contractor",
        "org_aliases": ["marine"],
        "emails": []
    },
    {
        "id": "GRADING",
        "name": "General Grading & Earth Works Phase 1A",
        "k_code": "",
        "contracts": ["3015", "REH.08.25.3015"],
        "patterns": [r"3015", r"General\s*Grading"],
        "contractor": "Orascom Construction SAE",
        "org_aliases": ["orascom", "oc"],
        "emails": ["ihab.mehawed@orascom.com"]
    }
]

import os
import openpyxl

# Known Consultants & PMC Contacts (Strictly verified contacts from project database)
CONSULTANT_CONTACTS = {
    "shaker egypt": ["amahmoud@shakerconsultancy.com"],
    "shaker consultancy group": ["amahmoud@shakerconsultancy.com"],
    "shaker consultancy": ["amahmoud@shakerconsultancy.com"],
    "shaker": ["amahmoud@shakerconsultancy.com"],
    "aedas": ["aedas.raselhekma@aedas.com"],
    "aedas limited": ["aedas.raselhekma@aedas.com"],
    "hill": ["DeanEnglish@hillintl.com"],
    "hill international": ["DeanEnglish@hillintl.com"],
    "hill inter": ["DeanEnglish@hillintl.com"]
}

import datetime
import duckdb

DB_DIR_PRIMARY = r"C:\Users\bimst\Downloads\ACONEX\Data\database"
DB_DIR_FALLBACK = r"C:\Users\bimst\Downloads\ACONEX\Data\update\Up\database"
DB_DIR = DB_DIR_PRIMARY if os.path.exists(DB_DIR_PRIMARY) else DB_DIR_FALLBACK
SHAKER_LIST_PATH = os.path.join(DB_DIR, "Zone_DC_Manager_List_Shaker.xlsx")
ECG_LIST_PATH = os.path.join(DB_DIR, "Zone_DC_Manager_List-ECG.xlsx")
HILL_CC_PATH = os.path.join(DB_DIR, "Hill CC.xlsx")
ZONE_LIST_PATH = os.path.join(DB_DIR, "Zone_DC_Manager_List.xlsx")
DEFAULT_PMC_CC = ""

# Dynamic in-memory cache tracking file modification timestamps
_CONTACTS_CACHE = {
    "shaker": {},
    "ecg": {},
    "hill": {},
    "all_users": {},
    "mtimes": {},
    "last_loaded": None
}

def load_all_contacts_databases(force: bool = False) -> dict:
    """
    Dynamically loads and parses contacts from:
    1. Zone_DC_Manager_List_Shaker.xlsx (DP01, DP05, DP06, DP07)
    2. Zone_DC_Manager_List-ECG.xlsx (DP2, DP3-East & West, DP4)
    3. Hill CC.xlsx (Contract Project Managers, Admins, Directors)
    4. Zone_DC_Manager_List.xlsx (Consortium baseline)

    Automatically re-parses when any file's modification timestamp (mtime) changes,
    or immediately when force=True is passed via the refresh API.
    """
    global _CONTACTS_CACHE
    files_to_check = [SHAKER_LIST_PATH, ECG_LIST_PATH, HILL_CC_PATH, ZONE_LIST_PATH]
    current_mtimes = {}
    mtime_changed = False

    for fpath in files_to_check:
        if os.path.exists(fpath):
            mt = os.path.getmtime(fpath)
            current_mtimes[fpath] = mt
            if _CONTACTS_CACHE["mtimes"].get(fpath) != mt:
                mtime_changed = True
        else:
            current_mtimes[fpath] = 0

    if not force and not mtime_changed and _CONTACTS_CACHE["last_loaded"] is not None:
        return _CONTACTS_CACHE

    shaker_map = {}
    ecg_map = {}
    hill_map = {}
    all_users = {}

    # 1. Parse Shaker List
    if os.path.exists(SHAKER_LIST_PATH):
        try:
            wb = openpyxl.load_workbook(SHAKER_LIST_PATH, data_only=True)
            ws = wb.active
            cur_dp = None
            for r in range(1, ws.max_row + 1):
                c1, c2, c3 = ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value
                if c1 and str(c1).strip().upper().startswith("DP"):
                    cur_dp = str(c1).strip().upper().replace(" ", "")
                    if cur_dp not in shaker_map:
                        shaker_map[cur_dp] = {"dcs": [], "engineers": []}
                    continue
                if cur_dp and c3 and "@" in str(c3):
                    em = str(c3).strip()
                    title = str(c2).strip() if c2 else ""
                    name = str(c1).strip() if c1 else ""
                    item = {"name": name, "title": title, "email": em}
                    if "controller" in title.lower():
                        shaker_map[cur_dp]["dcs"].append(item)
                    else:
                        shaker_map[cur_dp]["engineers"].append(item)
                    if name:
                        all_users[name.lower()] = em
                        for part in name.split():
                            if len(part) >= 4 and part.lower() not in all_users:
                                all_users[part.lower()] = em
        except Exception as e:
            print(f"Warning parsing Shaker list ({e})")

    # 2. Parse ECG List
    if os.path.exists(ECG_LIST_PATH):
        try:
            wb = openpyxl.load_workbook(ECG_LIST_PATH, data_only=True)
            ws = wb['Zone Responsibility'] if 'Zone Responsibility' in wb.sheetnames else wb.active
            cur_zone = None
            for r in range(2, ws.max_row + 1):
                z, dc_n, dc_e, mg_n, mg_e = ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 4).value, ws.cell(r, 5).value, ws.cell(r, 6).value
                if z and str(z).strip():
                    cur_zone = str(z).strip().upper().replace(" ", "")
                if cur_zone and (dc_e or mg_e):
                    if cur_zone not in ecg_map:
                        ecg_map[cur_zone] = {"dcs": [], "managers": []}
                    if dc_e and "@" in str(dc_e):
                        em = str(dc_e).strip().replace(" ", "")
                        nm = str(dc_n).strip() if dc_n else ""
                        ecg_map[cur_zone]["dcs"].append({"name": nm, "email": em})
                        if nm:
                            all_users[nm.lower()] = em
                    if mg_e and "@" in str(mg_e):
                        em = str(mg_e).strip().replace(" ", "")
                        nm = str(mg_n).strip() if mg_n else ""
                        ecg_map[cur_zone]["managers"].append({"name": nm, "email": em})
                        if nm:
                            all_users[nm.lower()] = em
        except Exception as e:
            print(f"Warning parsing ECG list ({e})")

    # 3. Parse Hill CC List
    if os.path.exists(HILL_CC_PATH):
        try:
            wb = openpyxl.load_workbook(HILL_CC_PATH, data_only=True)
            ws = wb.active
            for r in range(3, ws.max_row + 1):
                pkg, admin, pm, director = ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 4).value, ws.cell(r, 5).value
                if pkg:
                    pkg_str = str(pkg).strip().replace("'", "").replace(",", ".")
                    m = re.search(r"(\d{4})", pkg_str)
                    key = m.group(1) if m else pkg_str.upper()
                    admin_e = str(admin).strip() if admin else None
                    pm_e = str(pm).strip() if pm else None
                    dir_e = str(director).strip() if director else None
                    hill_map[key] = {
                        "pkg_raw": pkg_str,
                        "admin": admin_e,
                        "pm": pm_e,
                        "director": dir_e
                    }
                    for em in [admin_e, pm_e, dir_e]:
                        if em and "@" in em:
                            prefix = em.split("@")[0].lower()
                            all_users[prefix] = em
        except Exception as e:
            print(f"Warning parsing Hill CC list ({e})")

    _CONTACTS_CACHE = {
        "shaker": shaker_map,
        "ecg": ecg_map,
        "hill": hill_map,
        "all_users": all_users,
        "mtimes": current_mtimes,
        "last_loaded": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return _CONTACTS_CACHE


def get_contacts_status() -> dict:
    """Returns real-time inventory and last-modified metadata of all contacts databases."""
    cache = load_all_contacts_databases(force=False)
    files_info = []
    for fpath in [SHAKER_LIST_PATH, ECG_LIST_PATH, HILL_CC_PATH, ZONE_LIST_PATH]:
        exists = os.path.exists(fpath)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S") if exists else None
        size_kb = round(os.path.getsize(fpath) / 1024, 1) if exists else 0
        files_info.append({
            "filename": os.path.basename(fpath),
            "file_path": fpath,
            "exists": exists,
            "size_kb": size_kb,
            "last_modified": mtime
        })
    return {
        "status": "success",
        "last_reloaded": cache.get("last_loaded"),
        "shaker_dps_count": len(cache.get("shaker", {})),
        "ecg_zones_count": len(cache.get("ecg", {})),
        "hill_packages_count": len(cache.get("hill", {})),
        "total_indexed_users": len(cache.get("all_users", {})),
        "files": files_info
    }


def is_shaker_ecg(org_name: str) -> bool:
    """
    Identifies whether the organization is Shaker-ECG consortium RASELHEKMA
    (Site Supervision Consultant for Wadi Yemm).
    """
    if not org_name:
        return False
    o = org_name.strip().lower().replace("–", "-")
    return ("shaker" in o and "ecg" in o) or "shaker-ecg" in o or "shaker - ecg" in o


def is_shaker_consultant(org_name: str) -> bool:
    """
    Identifies whether the organization is Shaker Egypt / Shaker Consultancy Group
    (strictly a Design / Technical Consultant, NOT the Wadi Yemm SSC Consortium).
    """
    if not org_name:
        return False
    o = org_name.strip().lower().replace("–", "-")
    return "shaker" in o and not is_shaker_ecg(org_name)


def get_shaker_ecg_zone_contacts(active_packages: list) -> tuple:
    """
    Resolves the exact Document Controller (DC) emails (for To:) and Direct Manager / Director
    emails (for Cc:) strictly based on the Design / Project packages present in the overdue report.
    Uses Zone_DC_Manager_List_Shaker.xlsx for DP01, DP05, DP06, DP07
    and Zone_DC_Manager_List-ECG.xlsx for DP02, DP03, DP04.
    """
    cache = load_all_contacts_databases(force=False)
    shaker_map = cache.get("shaker", {})
    ecg_map = cache.get("ecg", {})

    matched_dcs = []
    matched_managers = []
    matched_zones = set()

    for pkg in active_packages:
        u_pkg = str(pkg).upper()
        # DP01 (Shaker)
        if "DP01" in u_pkg or "DP-01" in u_pkg or "DP1" in u_pkg or "3121" in u_pkg or "3180" in u_pkg:
            matched_zones.add("DP01")
            for item in shaker_map.get("DP01", {}).get("dcs", []):
                matched_dcs.append(item["email"])
            for item in shaker_map.get("DP01", {}).get("engineers", []):
                matched_managers.append(item["email"])

        # DP02 (ECG)
        if "DP02" in u_pkg or "DP-02" in u_pkg or "DP2" in u_pkg or "3149" in u_pkg or "3270" in u_pkg:
            matched_zones.add("DP02")
            for item in ecg_map.get("DP2", {}).get("dcs", []):
                matched_dcs.append(item["email"])
            for item in ecg_map.get("DP2", {}).get("managers", []):
                matched_managers.append(item["email"])

        # DP03 East & West (ECG)
        if "DP03" in u_pkg or "DP-03" in u_pkg or "DP3" in u_pkg or "3199" in u_pkg or "3271" in u_pkg:
            matched_zones.add("DP03")
            for item in ecg_map.get("DP3-EAST&WEST", {}).get("dcs", []):
                matched_dcs.append(item["email"])
            for item in ecg_map.get("DP3-EAST&WEST", {}).get("managers", []):
                matched_managers.append(item["email"])

        # DP04 (ECG)
        if "DP04" in u_pkg or "DP-04" in u_pkg or "DP4" in u_pkg or "3204" in u_pkg:
            matched_zones.add("DP04")
            for item in ecg_map.get("DP4", {}).get("dcs", []):
                matched_dcs.append(item["email"])
            for item in ecg_map.get("DP4", {}).get("managers", []):
                matched_managers.append(item["email"])

        # DP05 (Shaker)
        if "DP05" in u_pkg or "DP-05" in u_pkg or "DP5" in u_pkg or "3205" in u_pkg:
            matched_zones.add("DP05")
            for item in shaker_map.get("DP05", {}).get("dcs", []):
                matched_dcs.append(item["email"])
            for item in shaker_map.get("DP05", {}).get("engineers", []):
                matched_managers.append(item["email"])

        # DP06 (Shaker)
        if "DP06" in u_pkg or "DP-06" in u_pkg or "DP6" in u_pkg or "3206" in u_pkg:
            matched_zones.add("DP06")
            for item in shaker_map.get("DP06", {}).get("dcs", []):
                matched_dcs.append(item["email"])
            for item in shaker_map.get("DP06", {}).get("engineers", []):
                matched_managers.append(item["email"])

        # DP07 (Shaker)
        if "DP07" in u_pkg or "DP-07" in u_pkg or "DP7" in u_pkg or "3207" in u_pkg:
            matched_zones.add("DP07")
            for item in shaker_map.get("DP07", {}).get("dcs", []):
                matched_dcs.append(item["email"])
            for item in shaker_map.get("DP07", {}).get("engineers", []):
                matched_managers.append(item["email"])

    # Non-Wadi Yemm packages (Infrastructure, Airport, Strategic, Design Consultancy)
    if not matched_zones:
        # Check if it's Infrastructure / Airport / Strategic / Plants
        is_strategic_infra = any(kw in " ".join(str(p).upper() for p in active_packages) for kw in [
            "INFRA", "SW00", "AIRPORT", "STP", "RO", "3048", "3049", "3046", "3045", "3044", "3091", "3200", "3107", "MARINE"
        ])
        if is_strategic_infra:
            matched_dcs.append("ahmedelnasseh@hillintl.com")
        return list(dict.fromkeys(matched_dcs)), list(dict.fromkeys(matched_managers)), list(matched_zones)

    # Consortium General Director is included in CC for Wadi Yemm packages
    matched_managers.append("mohamed.wageh@ecgsa.com")

    # Deduplicate while preserving order
    dedup_dcs = list(dict.fromkeys(matched_dcs))
    dedup_mgrs = list(dict.fromkeys(matched_managers))

    return dedup_dcs, dedup_mgrs, list(matched_zones)


ORDERED_HILL_CHECKS = [
    ("3207", ["DP07", "DP-07", "DP7", "3207", "MD07", "OBMI"]),
    ("3206", ["DP06", "DP-06", "DP6", "3206", "MD06"]),
    ("3205", ["DP05", "DP-05", "DP5", "3205", "MD05"]),
    ("3204", ["DP04", "DP-04", "DP4", "3204", "MD04"]),
    ("3271", ["DP03 WEST", "DP03-WEST", "DP03_WEST", "DP3 WEST", "DP3-WEST", "3271"]),
    ("3199", ["DP03 EAST", "DP03-EAST", "DP03_EAST", "DP3 EAST", "DP3-EAST", "3199", "INR"]),
    ("3149", ["DP02", "DP-02", "DP2", "3149", "3270", "MD02", "CRJ"]),
    ("3121", ["DP01", "DP-01", "DP1", "3121", "3180", "MD01"]),
    ("3200", ["GRAND CANAL", "GRAND LAGOON", "3200"]),
    ("3107", ["WEST CANAL", "3107"]),
    ("3045", ["RO PLANT", "POTABLE WATER", "3045", "RO"]),
    ("3046", ["STP", "SEWAGE", "3046"]),
    ("3044", ["POWER SUPPLY", "SUBSTATION", "MPS", "3044"]),
    ("AIRPORT", ["AIRPORT", "AIR PORT", "VVIP", "AP00", "3049", "REHIA"]),
    ("MARINE", ["MARINE", "COASTAL"]),
    ("3091", ["RING ROAD", "3091", "RR00", "HOREMA"]),
    ("3048", ["PRIMARY INFRA", "UTILITY DIST", "SW00", "3048", "INFRASTRUCTURE", "INFRA"])
]


def get_hill_pmc_contacts(active_packages: list) -> list:
    """
    Extracts Hill PMC emails (Project Managers, Administrators, Directors)
    specifically matching the active contracts and design packages from Hill CC.xlsx.
    ZERO fake or assumed emails.
    """
    cache = load_all_contacts_databases(force=False)
    hill_map = cache.get("hill", {})
    matched_emails = []

    for pkg in active_packages:
        u_pkg = str(pkg).upper()
        for hill_key, triggers in ORDERED_HILL_CHECKS:
            if any(t in u_pkg for t in triggers):
                entry = hill_map.get(hill_key)
                if entry:
                    if entry.get("pm") and entry["pm"] not in matched_emails:
                        matched_emails.append(entry["pm"])
                    if entry.get("admin") and entry["admin"] not in matched_emails:
                        matched_emails.append(entry["admin"])
                    if entry.get("director") and entry["director"] not in matched_emails:
                        matched_emails.append(entry["director"])
                break

    # Director Dean English is always included as PMC oversight
    if "DeanEnglish@hillintl.com" not in matched_emails:
        matched_emails.append("DeanEnglish@hillintl.com")

    return list(dict.fromkeys(matched_emails))


def is_hill_org(org_name: str) -> bool:
    if not org_name:
        return False
    o = org_name.strip().lower()
    return "hill" in o or "hill inter" in o


def get_package_email_matrix(package_name: str, org_name: str) -> tuple:
    """
    Resolves the exact (To, CC) email addresses for a specific project package
    and target organization.
    Uses ONLY verified emails from Hill CC.xlsx, Zone_DC_Manager_List_Shaker.xlsx,
    Zone_DC_Manager_List-ECG.xlsx, and Project Packages Data.
    ZERO fake emails.
    """
    cache = load_all_contacts_databases(force=False)
    hill_map = cache.get("hill", {})
    u_pkg = (package_name or "").upper()

    hill_entry = None
    for hill_key, triggers in ORDERED_HILL_CHECKS:
        if any(t in u_pkg for t in triggers):
            hill_entry = hill_map.get(hill_key)
            if hill_entry:
                break

    to_emails = []
    cc_emails = []

    # 1. Organization is Hill International
    if is_hill_org(org_name):
        if hill_entry:
            if hill_entry.get("pm"):
                to_emails.append(hill_entry["pm"])
            if hill_entry.get("admin"):
                to_emails.append(hill_entry["admin"])
            if hill_entry.get("director"):
                cc_emails.append(hill_entry["director"])
            else:
                cc_emails.append("DeanEnglish@hillintl.com")
        else:
            to_emails.append("DeanEnglish@hillintl.com")
        return list(dict.fromkeys(to_emails)), list(dict.fromkeys(cc_emails))

    # 2. Organization is Shaker-ECG Consortium (Wadi Yemm SSC)
    if is_shaker_ecg(org_name):
        dcs, mgrs, zones = get_shaker_ecg_zone_contacts([package_name])
        to_emails.extend(dcs)
        cc_emails.extend(mgrs)
        if hill_entry:
            if hill_entry.get("pm"):
                cc_emails.append(hill_entry["pm"])
            if hill_entry.get("admin"):
                cc_emails.append(hill_entry["admin"])
            if hill_entry.get("director"):
                cc_emails.append(hill_entry["director"])
        if "DeanEnglish@hillintl.com" not in cc_emails:
            cc_emails.append("DeanEnglish@hillintl.com")
        return list(dict.fromkeys(to_emails)), list(dict.fromkeys(cc_emails))

    # 3. Organization is Shaker Consultant (Design Consultant)
    if is_shaker_consultant(org_name):
        to_emails.append("amahmoud@shakerconsultancy.com")
        if hill_entry:
            if hill_entry.get("pm"):
                cc_emails.append(hill_entry["pm"])
            if hill_entry.get("admin"):
                cc_emails.append(hill_entry["admin"])
            if hill_entry.get("director"):
                cc_emails.append(hill_entry["director"])
        if "DeanEnglish@hillintl.com" not in cc_emails:
            cc_emails.append("DeanEnglish@hillintl.com")
        return list(dict.fromkeys(to_emails)), list(dict.fromkeys(cc_emails))

    # 4. Organization is Contractor (e.g. Orascom, HAC, CCC/Rowad, CSCEC, etc.)
    official_contacts = get_company_official_emails(org_name)
    to_emails.extend(official_contacts)
    if hill_entry:
        if hill_entry.get("pm"):
            cc_emails.append(hill_entry["pm"])
        if hill_entry.get("admin"):
            cc_emails.append(hill_entry["admin"])
        if hill_entry.get("director"):
            cc_emails.append(hill_entry["director"])
    if "DeanEnglish@hillintl.com" not in cc_emails:
        cc_emails.append("DeanEnglish@hillintl.com")
    dcs, mgrs, zones = get_shaker_ecg_zone_contacts([package_name])
    cc_emails.extend(dcs + mgrs)
    return list(dict.fromkeys(to_emails)), list(dict.fromkeys(cc_emails))


def resolve_user_email(user_name: str, org_name: str = "") -> str:
    """
    Resolves the email address of an individual engineer/reviewer.
    Checks:
    1. Saved overrides in user_custom_emails DuckDB table
    2. Parsed database contacts (Shaker, ECG, Hill CC)
    3. dim_user_directory in DuckDB
    4. Heuristic inference based on organization
    """
    if not user_name:
        return ""
    
    clean_name = str(user_name).strip()
    clean_lower = clean_name.lower().replace("mr ", "").replace("ms ", "").replace("eng ", "").strip()

    # 1. Check user_custom_emails in DuckDB
    try:
        db_path = r"C:\Users\bimst\Downloads\ACONEX\aconex.duckdb".replace("\\", "/")
        con = duckdb.connect(db_path, read_only=True)
        try:
            m = con.execute("SELECT email FROM user_custom_emails WHERE user_name ILIKE ? LIMIT 1", [f"%{clean_lower}%"]).fetchone()
            if m and m[0]:
                return m[0].strip()
            
            # Check dim_user_directory
            d = con.execute("SELECT email FROM dim_user_directory WHERE user_name ILIKE ? AND email IS NOT NULL LIMIT 1", [f"%{clean_lower}%"]).fetchone()
            if d and d[0]:
                return d[0].strip()
        finally:
            con.close()
    except Exception:
        pass

    # 2. Check in-memory indexed contacts
    cache = load_all_contacts_databases(force=False)
    all_users = cache.get("all_users", {})

    if clean_lower in all_users:
        return all_users[clean_lower]

    for k, email in all_users.items():
        if k in clean_lower or clean_lower in k:
            return email

    # 3. Known key project personas
    persona_map = {
        "hossam": "HossameldinSwaify@hillintl.com",
        "swefy": "HossameldinSwaify@hillintl.com",
        "swaify": "HossameldinSwaify@hillintl.com",
        "biok": "AdhemBiok@hillintl.com",
        "adhem": "AdhemBiok@hillintl.com",
        "abdellatif": "KhaledAbdellatif@hillintl.com",
        "elghannam": "AymanElghannam@hillintl.com",
        "dean": "DeanEnglish@hillintl.com",
        "english": "DeanEnglish@hillintl.com",
        "wageh": "mohamed.wageh@ecgsa.com",
        "tawfik": "Ahmed-Tawfik@shakeregypt.com",
        "moawad": "Khaled-Moawad@shakeregypt.com",
        "hendam": "Hany.Ezzeldin@ecgsa.com",
        "klay": "Ahmed.Klay@ecgsa.com",
        "thabit": "Ayman.Thabit@ecgsa.com",
        "ezzat": "Beshoy.Ezzat@ecgsa.com",
        "kattar": "Waleed.MKattar@ecgsa.com",
        "mohsen": "Tarek.Mohsen@ecgsa.com",
        "mehawed": "ihab.mehawed@orascom.com",
        "gamal": "mohamed.gamal@innovogroup.com",
        "tarek": "mtarek@ccc.net",
        "maher": "maher@accsal.com"
    }
    for kw, em in persona_map.items():
        if kw in clean_lower:
            return em

    return ""


def resolve_project_package(doc_no: str = "", title: str = "", subject: str = "", workflow_name: str = "") -> str:
    """
    Classifies a deliverable, document, or mail into its exact Project / Package
    based on Contract numbers, K-package numbers, Sector codes, or descriptive keywords.
    Order of precedence is strictly maintained: specific DP / facility matches
    are evaluated before generic infrastructure substrings.
    """
    text = f"{doc_no or ''} {title or ''} {subject or ''} {workflow_name or ''}".strip()
    if not text:
        return "General Project Deliverables"

    # 1. Exact K-package check (Highest specificity)
    for pkg in PACKAGE_DEFINITIONS:
        k = pkg.get("k_code")
        if k and k.upper() in text.upper():
            return pkg["name"]

    # 2. Exact Contract number check
    for pkg in PACKAGE_DEFINITIONS:
        for c in pkg.get("contracts", []):
            if c.upper() in text.upper():
                return pkg["name"]

    # 3. Specific Ordered Pattern Check (Specific DPs & facilities evaluated before generic Infra)
    ORDERED_PATTERNS = [
        ("DP07 - Buildings & Infrastructure", [r"\bDP-?0?7\b", r"\bMD-?0?7\b", r"\bOBMI\b", r"3207"]),
        ("DP06 - Buildings & Infrastructure", [r"\bDP-?0?6\b", r"\bMD-?0?6\b", r"3206"]),
        ("DP05 - Buildings & Infrastructure", [r"\bDP-?0?5\b", r"\bMD-?0?5\b", r"3205"]),
        ("DP04 - Buildings & Infrastructure", [r"\bDP-?0?4\b", r"\bMD-?0?4\b", r"3204"]),
        ("DP03 West - Buildings & Infrastructure", [r"DP-?0?3\s*West", r"DP3\s*West", r"3271"]),
        ("DP03 East - Buildings & Infrastructure", [r"DP-?0?3\s*East", r"DP3\s*East", r"\bINR\b", r"3199"]),
        ("DP03 - Buildings & Infrastructure", [r"\bDP-?0?3\b", r"\bMD-?0?3\b"]),
        ("DP02 - Area 2 Basement & Superstructure", [r"\bDP-?0?2\b", r"\bMD-?0?2\b", r"\bCRJ\b", r"Area\s*2\s*Basement", r"3149", r"3270"]),
        ("DP01 - Area 1 Basement & Superstructure", [r"\bDP-?0?1\b", r"\bMD-?0?1\b", r"Wadi\s*Yemm.*Area\s*1", r"3121", r"3180"]),
        ("Potable Water RO Plant", [r"RO\s*Plant", r"Potable\s*Water", r"\bRO\b", r"Desalination", r"3045"]),
        ("Sewage Treatment Plant (STP)", [r"\bSTP\b", r"Sewage\s*Treatment", r"Sewage", r"3046"]),
        ("VVIP Airport & Airside Development", [r"\bAP0?0?\b", r"Airport", r"Air\s*Port", r"VVIP\s*Terminal", r"REHIA", r"3049"]),
        ("Phase 1A Ring Road Project", [r"\bRR0?0?\b", r"Ring\s*Road", r"Horema", r"3091"]),
        ("Grand Canal & Lagoon Excavation", [r"Grand\s*Canal", r"Grand\s*Lagoon", r"3200"]),
        ("West Canal Excavation", [r"West\s*Canal", r"3107"]),
        ("Main Power Supply Infrastructure (PS)", [r"Power\s*Supply", r"Substation", r"\bMPS\b", r"3044"]),
        ("Marine Works & Coastal Protection", [r"Marine", r"Coastal", r"3050"]),
        ("Primary Infrastructure & Utility (Package A)", [r"\bSW00\b", r"Primary\s*Infra", r"Utility\s*Dist", r"Infrastructure", r"Infra", r"3048"])
    ]

    for pkg_name, patterns in ORDERED_PATTERNS:
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return pkg_name

    # 4. Fallback keyword checks
    u_text = text.upper()
    if "CANAL" in u_text or "LAGOON" in u_text:
        return "Grand Canal & Lagoon Excavation"
    if "AIRPORT" in u_text or "AIR PORT" in u_text:
        return "VVIP Airport & Airside Development"
    if "RO PLANT" in u_text or "POTABLE" in u_text:
        return "Potable Water RO Plant"
    if "STP" in u_text or "SEWAGE" in u_text:
        return "Sewage Treatment Plant (STP)"
    if "RING ROAD" in u_text:
        return "Phase 1A Ring Road Project"
    if "INFRA" in u_text:
        return "Primary Infrastructure & Utility (Package A)"

    return "General Project Deliverables"


def get_company_official_emails(org_name: str) -> list:
    """
    Resolves official DC / Managing Director emails for an organization name.
    Strictly separates Shaker Consultant from Shaker-ECG Wadi Yemm SSC Consortium.
    """
    if not org_name:
        return []

    # Shaker-ECG consortium is handled dynamically based on active package zones
    if is_shaker_ecg(org_name):
        return []

    # Shaker Egypt / Shaker Consultancy Group is strictly a Consultant
    if is_shaker_consultant(org_name):
        return ["amahmoud@shakerconsultancy.com"]

    clean_org = org_name.strip().lower()

    # Check consultant dictionary
    for k, emails in CONSULTANT_CONTACTS.items():
        if k in clean_org:
            return emails

    # Check package contractor definitions
    matched_emails = []
    for pkg in PACKAGE_DEFINITIONS:
        for alias in pkg["org_aliases"]:
            if alias in clean_org:
                for em in pkg["emails"]:
                    if em and em not in matched_emails:
                        matched_emails.append(em)

    return matched_emails


def group_dossier_by_package(dossier_data: dict) -> dict:
    """
    Groups all overdue workflow steps, mails, rfis, and lookahead items
    by their resolved Project Package name.
    Returns:
    {
        "packages": {
            "DP01 — Area 1 Basement & Superstructure": {
                "name": "...",
                "wf_steps": [...],
                "mails": [...],
                "rfis": [...],
                "lookahead": [...],
                "total_items": int,
                "max_delay": int
            }, ...
        },
        "package_order": ["DP01...", "DP02...", ...]
    }
    """
    packages = {}

    def ensure_pkg(pkg_name):
        if pkg_name not in packages:
            packages[pkg_name] = {
                "name": pkg_name,
                "wf_steps": [],
                "mails": [],
                "rfis": [],
                "lookahead": [],
                "total_items": 0,
                "max_delay": 0
            }
        return packages[pkg_name]

    # 1. Workflow steps
    for s in dossier_data.get("wf_steps", []):
        pkg_name = resolve_project_package(
            doc_no=s.get("document_no", ""),
            title=s.get("title", ""),
            workflow_name=s.get("workflow_name", "")
        )
        s["project_package"] = pkg_name
        p = ensure_pkg(pkg_name)
        p["wf_steps"].append(s)
        p["total_items"] += 1
        p["max_delay"] = max(p["max_delay"], s.get("days_late", 0))

    # 2. Mails
    for m in dossier_data.get("mails", []):
        pkg_name = resolve_project_package(
            doc_no=m.get("mail_no", ""),
            subject=m.get("subject", "")
        )
        m["project_package"] = pkg_name
        p = ensure_pkg(pkg_name)
        p["mails"].append(m)
        p["total_items"] += 1
        p["max_delay"] = max(p["max_delay"], m.get("days_late", 0))

    # 3. RFIs
    for r in dossier_data.get("rfis", []):
        pkg_name = resolve_project_package(
            doc_no=r.get("mail_no", ""),
            subject=r.get("subject", "")
        )
        r["project_package"] = pkg_name
        p = ensure_pkg(pkg_name)
        p["rfis"].append(r)
        p["total_items"] += 1
        p["max_delay"] = max(p["max_delay"], r.get("days_late", 0))

    # 4. Lookahead
    for l in dossier_data.get("lookahead_7d", []):
        pkg_name = resolve_project_package(
            doc_no=l.get("document_no", ""),
            title=l.get("title", ""),
            workflow_name=l.get("workflow_name", "")
        )
        l["project_package"] = pkg_name
        p = ensure_pkg(pkg_name)
        p["lookahead"].append(l)

    # Sort packages by total overdue descending, keeping General last
    def sort_key(item):
        name, data = item
        if name == "General Project Deliverables":
            return -999999
        return data["total_items"]

    sorted_pkgs = sorted(packages.items(), key=sort_key, reverse=True)
    ordered_dict = {k: v for k, v in sorted_pkgs}

    return {
        "packages": ordered_dict,
        "package_order": list(ordered_dict.keys())
    }
