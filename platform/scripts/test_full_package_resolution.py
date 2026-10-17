import duckdb
import re

con = duckdb.connect('aconex.duckdb', read_only=True)

CONTRACT_MAP = {
    '3121': 'DP01', '3180': 'DP01', 'MD01': 'DP01', 'P0155': 'DP01', 'K03121': 'DP01',
    '3149': 'DP02', '3270': 'DP02', 'P1003': 'DP02', 'K03149': 'DP02',
    '3199': 'DP03-East', 'K03199': 'DP03-East',
    '3271': 'DP03-West', 'K03271': 'DP03-West',
    '3204': 'DP04', 'K03204': 'DP04',
    '3205': 'DP05', 'K03205': 'DP05',
    '3206': 'DP06', 'K03206': 'DP06',
    '3207': 'DP07', 'K03207': 'DP07',
    '3200': 'Grand Canal', 'P0801': 'Grand Canal', 'K03200': 'Grand Canal',
    '3107': 'West Canal', 'P1201': 'West Canal', 'K03107': 'West Canal',
    '3048': 'Infra', 'SW00': 'Infra', 'K03048': 'Infra',
    '3044': 'MMS / Substation', 'MSS': 'MMS / Substation', 'K03044': 'MMS / Substation',
    '3045': 'RO Plant', 'K03045': 'RO Plant',
    '3046': 'STP', 'P5576': 'STP', 'K03046': 'STP',
    '3049': 'Airport', 'P0153': 'Airport', 'AR01': 'Airport', 'K00146': 'Airport',
    '3091': 'Ring Road', 'RR00': 'Ring Road', 'P0152': 'Ring Road', 'K03091': 'Ring Road',
    '3015': 'General Grading', 'REH.08.25.3015': 'General Grading',
}

KNOWN_PACKAGES = set(CONTRACT_MAP.values()) | {
    'General Project Correspondence', 'Aedas Design Packages', 'Dar Consultancy Packages',
    'OBMI Consultancy Packages', 'DP08 - South Golf'
}

def resolve_entity_package(subject: str = "", mail_no: str = "", from_org: str = "", to_org: str = "", default_pkg: str = "") -> str:
    sub = (subject or "").upper()
    m_no = (mail_no or "").upper()
    f_org = (from_org or "").upper()
    t_org = (to_org or "").upper()
    combined = f"{sub} {m_no} {f_org} {t_org}"

    # Tier 1: Strict Contract Number / Package Code Pattern Match in Subject or Mail No
    for k, v in CONTRACT_MAP.items():
        pattern = r'(?:\b|K0?|P0?|REH[.\-_]|REH\.\d+\.\d+\.)' + re.escape(k) + r'(?:\b|[.\-_])'
        if re.search(pattern, sub) or re.search(pattern, m_no):
            return v

    # Tier 2: Literal Contract Digit substring in subject or mail_no
    for k in ['3271', '3199', '3204', '3205', '3206', '3207', '3149', '3270', '3121', '3180', '3200', '3107', '3048', '3044', '3045', '3046', '3049', '3091', '3015']:
        if k in sub or k in m_no:
            return CONTRACT_MAP[k]

    # Tier 3: If default_pkg is already a specific valid package (not General), preserve it
    if default_pkg and default_pkg in KNOWN_PACKAGES and not any(g in default_pkg for g in ['General', 'Unknown', 'None']):
        return default_pkg

    # Tier 4: Explicit Package Names in Text
    if 'DP03-EAST' in combined or 'DP03 EAST' in combined or 'DP3-EAST' in combined or 'DP3 EAST' in combined:
        return 'DP03-East'
    if 'DP03-WEST' in combined or 'DP03 WEST' in combined or 'DP3-WEST' in combined or 'DP3 WEST' in combined:
        return 'DP03-West'
    if re.search(r'\bDP-?0?1\b|\bMD-?0?1\b|AREA\s*1\b|SEA\s*TOWN', combined):
        return 'DP01'
    if re.search(r'\bDP-?0?2\b|\bMD-?0?2\b|AREA\s*2\b', combined):
        return 'DP02'
    if re.search(r'\bDP-?0?4\b|\bMD-?0?4\b', combined):
        return 'DP04'
    if re.search(r'\bDP-?0?5\b|\bMD-?0?5\b', combined):
        return 'DP05'
    if re.search(r'\bDP-?0?6\b|\bMD-?0?6\b|\bHYH\b', combined):
        return 'DP06'
    if re.search(r'\bDP-?0?7\b|\bMD-?0?7\b', combined):
        return 'DP07'
    if 'GRAND CANAL' in combined or 'LAGOON' in combined:
        return 'Grand Canal'
    if 'WEST CANAL' in combined:
        return 'West Canal'
    if 'RO PLANT' in combined or 'DESALINATION' in combined:
        return 'RO Plant'
    if 'SEWAGE TREATMENT' in combined or re.search(r'\bSTP\b', combined):
        return 'STP'
    if 'SUBSTATION' in combined or re.search(r'\bMSS\b|\bMSS1\b', combined):
        return 'MMS / Substation'
    if 'AIRPORT' in combined or 'AIR PORT' in combined or 'RUNWAY' in combined:
        return 'Airport'
    if 'RING ROAD' in combined:
        return 'Ring Road'
    if 'INFRASTRUCTURE' in combined or re.search(r'\bINFRA\b|\bSW00\b', combined):
        return 'Infra'
    if 'SOUTH GOLF' in combined or 'DP08' in combined:
        return 'DP08 - South Golf'

    # Tier 5: Contractor / Originator / Target specific mappings
    if 'CCCEGY-RFI' in m_no or 'CCC / ROWAD' in combined or 'CONSOLIDATED CONTRACTORS' in combined:
        return 'DP02'
    if 'EETD-RME' in combined or 'ELSEWEDY' in combined:
        return 'MMS / Substation'
    if 'OTC-JV' in m_no or 'TROJAN' in combined:
        return 'RO Plant'
    if 'INNOVO' in combined or 'REDCON' in combined:
        return 'DP03-East'
    if 'ACC FOR ENGINEERING' in combined or 'ARABIAN CONSTRUCTION' in combined:
        return 'DP04'
    if 'CSCEC' in combined:
        return 'DP07'
    if 'DAR AL HANDASAH' in combined or 'DARR-' in m_no:
        return 'Dar Consultancy Packages'
    if 'AEDAS' in combined:
        return 'Aedas Design Packages'
    if 'OBMI' in combined:
        return 'OBMI Consultancy Packages'

    return default_pkg if default_pkg else 'General Project Correspondence'

# Test across all RFIs
all_rfis = con.execute("SELECT mail_no, subject, from_organization, to_organization, project_package FROM fact_rfis").fetchall()
rfi_dist = {}
for r in all_rfis:
    p = resolve_entity_package(r[1], r[0], r[2], r[3], r[4])
    rfi_dist[p] = rfi_dist.get(p, 0) + 1

print("--- FULL RFIs Package Distribution (6,026 items) ---")
for p, c in sorted(rfi_dist.items(), key=lambda x: x[1], reverse=True):
    print(f"  {p:<30}: {c:,}")

con.close()
