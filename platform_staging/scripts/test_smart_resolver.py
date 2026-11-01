import duckdb
import re

con = duckdb.connect('aconex.duckdb', read_only=True)

# Test classifying all 140 "General RFIs" using a smart multi-tiered resolver
general_rfis = con.execute("""
    SELECT mail_no, subject, from_organization, to_organization, sent_date 
    FROM fact_rfis 
    WHERE project_package IS NULL OR project_package ILIKE '%General%' OR project_package = ''
""").fetchall()

print(f"Total 'General' RFIs to resolve: {len(general_rfis)}")

def smart_resolve_rfi(mail_no, subject, from_org, to_org):
    txt = f"{mail_no} {subject} {from_org} {to_org}".upper()

    # 1. DP01
    if any(k in txt for k in ['K03121', '3121', '3180', 'MD01', 'MD-01', 'P0155', 'PACKAGE 01', 'PACKAGE 1', 'SEA TOWN', 'AREA 1']):
        return 'DP01'
    # 2. DP02
    if any(k in txt for k in ['K03149', '3149', '3270', 'MD02', 'MD-02', 'P1003', 'PACKAGE 02', 'PACKAGE 2', 'AREA 2', 'CCCEGY-RFI']):
        return 'DP02'
    # 3. DP03-East
    if any(k in txt for k in ['K03199', '3199', 'DP03-EAST', 'DP03 EAST', 'DP3-EAST', 'DP3 EAST', 'INNOVO']):
        return 'DP03-East'
    # 4. DP03-West
    if any(k in txt for k in ['K03271', '3271', 'DP03-WEST', 'DP03 WEST', 'DP3-WEST', 'DP3 WEST', 'RHD3']):
        return 'DP03-West'
    # 5. DP04
    if any(k in txt for k in ['K03204', '3204', 'DP04', 'DP-04', 'DP4', 'ACC FOR ENGINEERING', 'ARABIAN CONSTRUCTION']):
        return 'DP04'
    # 6. DP05
    if any(k in txt for k in ['K03205', '3205', 'DP05', 'DP-05', 'DP5']):
        return 'DP05'
    # 7. DP06
    if any(k in txt for k in ['K03206', '3206', 'DP06', 'DP-06', 'DP6', 'HASSAN ALLAM', 'HAC-']):
        return 'DP06'
    # 8. DP07
    if any(k in txt for k in ['K03207', '3207', 'DP07', 'DP-07', 'DP7', 'CSCEC']):
        return 'DP07'
    # 9. Infra
    if any(k in txt for k in ['K03048', '3048', 'SW00', 'SW-00', 'INFRA', 'INFRASTRUCTURE', 'ROADS & UTILITIES']):
        return 'Infra'
    # 10. MMS / Substation
    if any(k in txt for k in ['K03044', '3044', 'MSS', 'SUBSTATION', 'ELSEWEDY', 'EETD']):
        return 'MMS / Substation'
    # 11. RO Plant
    if any(k in txt for k in ['K03045', '3045', 'RO PLANT', 'DESALINATION', 'OTC-JV', 'TROJAN']):
        return 'RO Plant'
    # 12. STP
    if any(k in txt for k in ['K03046', '3046', 'STP', 'SEWAGE TREATMENT', 'P5576']):
        return 'STP'
    # 13. Grand Canal
    if any(k in txt for k in ['K03200', '3200', 'GRAND CANAL', 'P0801', 'LAGOON']):
        return 'Grand Canal'
    # 14. West Canal
    if any(k in txt for k in ['K03107', '3107', 'WEST CANAL', 'P1201']):
        return 'West Canal'
    # 15. Airport
    if any(k in txt for k in ['K03049', '3049', 'AIRPORT', 'AIR PORT', 'P0153', 'AR01', 'RUNWAY', 'TAXIWAY']):
        return 'Airport'
    # 16. Ring Road
    if any(k in txt for k in ['K03091', '3091', 'RING ROAD', 'RR00', 'P0152']):
        return 'Ring Road'
    # 17. Consultancies
    if 'DAR AL HANDASAH' in txt or 'DARR-' in txt:
        return 'Dar Consultancy Packages'
    if 'AEDAS' in txt:
        return 'Aedas Design Packages'
    if 'OBMI' in txt:
        return 'OBMI Consultancy Packages'
    if 'ECG' in txt:
        return 'ECG Design Packages'

    return 'General Project Correspondence'

resolved_counts = {}
for r in general_rfis:
    pkg = smart_resolve_rfi(r[0], r[1], r[2], r[3])
    resolved_counts[pkg] = resolved_counts.get(pkg, 0) + 1

print("\nResolution results for the 140 'General' RFIs:")
for p, c in sorted(resolved_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  -> {p:<30}: {c}")

con.close()
