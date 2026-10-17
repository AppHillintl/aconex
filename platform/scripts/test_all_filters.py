import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(name, path, params=None):
    url = f"{BASE_URL}{path}"
    if params:
        url += f"?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FilterAudit/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            data = json.loads(resp.read().decode('utf-8'))
            return True, status, data
    except Exception as e:
        return False, str(e), None

endpoints_to_test = [
    # 1. Contractor RFIs & Field Inquiries Filters
    ("Contractor RFIs (Default)", "/api/controls/contractor_rfis", {}),
    ("Contractor RFIs (ECG strict)", "/api/controls/contractor_rfis", {"company": "ECG", "status": "all"}),
    ("Contractor RFIs (Shaker-ECG)", "/api/controls/contractor_rfis", {"company": "Shaker-ECG consortium RASELHEKMA", "status": "all"}),
    ("Contractor RFIs (Overdue SLA)", "/api/controls/contractor_rfis", {"status": "overdue"}),
    ("Contractor RFIs (On Time SLA)", "/api/controls/contractor_rfis", {"status": "ontime"}),
    ("Contractor RFIs (Search CCC)", "/api/controls/contractor_rfis", {"search": "CCC"}),
    ("Contractor RFIs (Date Range)", "/api/controls/contractor_rfis", {"from_date": "2026-03-01", "to_date": "2026-10-16"}),

    # 2. Controls / SSC Reviews Filters
    ("SSC Projects", "/api/controls/projects", {}),
    ("SSC Category All", "/api/controls/projects", {"category": "all"}),
    ("SSC Category Infrastructure", "/api/controls/projects", {"category": "Infrastructure"}),
    
    # 3. Ball-in-Court Filters
    ("Ball in Court (Default)", "/api/ball_in_court/processes", {}),
    ("Ball in Court (Discipline Civil)", "/api/ball_in_court/processes", {"discipline": "Civil"}),
    ("Ball in Court (Status Overdue)", "/api/ball_in_court/processes", {"status": "overdue"}),
    ("Ball in Court (Party Contractor)", "/api/ball_in_court/processes", {"party": "contractor"}),
    ("Ball in Court (Search RFI)", "/api/ball_in_court/processes", {"search": "RFI"}),

    # 4. Discipline Portals Filters
    ("Safety Items (Default)", "/api/disciplines/safety/items", {}),
    ("Safety Items (Search Safety)", "/api/disciplines/safety/items", {"search": "Safety"}),
    ("Safety Stats", "/api/disciplines/safety/stats", {}),
    
    ("QA/QC Items (Default)", "/api/disciplines/qaqc/items", {}),
    ("QA/QC Items (Search NCR)", "/api/disciplines/qaqc/items", {"search": "NCR"}),
    ("QA/QC Stats", "/api/disciplines/qaqc/stats", {}),

    ("Site Works Items (Default)", "/api/disciplines/site_ops/items", {}),
    ("Site Works Items (Overdue Only)", "/api/disciplines/site_ops/items", {"overdue_only": "true"}),
    ("Site Works Stats", "/api/disciplines/site_ops/stats", {}),

    ("Tech Office Items (Default)", "/api/disciplines/technical_office/items", {}),
    ("Tech Office Items (Discipline Arch)", "/api/disciplines/technical_office/items", {"discipline": "Architectural"}),
    ("Tech Office Stats", "/api/disciplines/technical_office/stats", {}),

    # 5. Hill Directory / Users Filters
    ("Hill Team Backlog", "/api/controls/hill_team", {}),
    ("Hill Team Package Filter", "/api/controls/hill_team", {"package": "Package 1"}),

    # 6. Overview & Project Summary Filters
    ("Summary Health", "/api/overview", {}),
    ("Summary Projects List", "/api/projects", {})
]

print("=" * 85)
print(f"{'TEST NAME':<38} | {'STATUS':<10} | {'RECORDS / INFO'}")
print("=" * 85)

passed = 0
failed = 0

for name, path, params in endpoints_to_test:
    ok, status, data = test_endpoint(name, path, params)
    if ok:
        passed += 1
        info = ""
        if isinstance(data, dict):
            if "total_count" in data:
                info = f"Total: {data['total_count']}"
            elif "total" in data:
                info = f"Total: {data['total']}"
            elif "count" in data:
                info = f"Count: {data['count']}"
            elif "rfis" in data:
                info = f"RFIs: {len(data['rfis'])}"
            elif "projects" in data:
                info = f"Projects: {len(data['projects'])}"
            elif "items" in data:
                info = f"Items: {len(data['items'])}"
            elif "data" in data and isinstance(data['data'], list):
                info = f"Data rows: {len(data['data'])}"
            elif "processes" in data:
                info = f"Processes: {len(data['processes'])}"
            else:
                info = f"Keys: {list(data.keys())[:3]}"
        elif isinstance(data, list):
            info = f"List len: {len(data)}"
        print(f"{name:<38} | OK ({status})  | {info}")
    else:
        failed += 1
        print(f"{name:<38} | FAILED     | Error: {status}")

print("=" * 85)
print(f"Results: {passed} Passed, {failed} Failed out of {len(endpoints_to_test)} tests.")
