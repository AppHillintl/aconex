"""
AI Chat Engine & Intelligent Query Service for Ras El Hekma PMC Platform.
Provides bilingual (Arabic & English) natural language understanding, database search,
KPI synthesis, table rendering, and Aconex deep-linking.
"""

import json
import os
import re
import urllib.parse
from datetime import datetime
from collections import defaultdict
import duckdb
import dispatch_settings_service as dss

try:
    import google.generativeai as genai
    HAS_GENAI = True
except Exception:
    HAS_GENAI = False


from pathlib import Path as _Path
_SRV_ROOT = _Path(__file__).resolve().parent.parent.parent
_SRV_CLOUD_DB = _SRV_ROOT / "aconex_cloud.duckdb"
_SRV_LOCAL_DB = _SRV_ROOT / "aconex.duckdb"

if _SRV_LOCAL_DB.exists():
    DB_PATH = str(_SRV_LOCAL_DB).replace("\\", "/")
elif _SRV_CLOUD_DB.exists():
    DB_PATH = str(_SRV_CLOUD_DB).replace("\\", "/")
else:
    DB_PATH = str(_SRV_LOCAL_DB).replace("\\", "/")

def get_db_connection():
    return duckdb.connect(DB_PATH, read_only=True)

# -----------------------------------------------------------------------------
# 1. Project & Contract Knowledge Base
# -----------------------------------------------------------------------------
CONTRACT_MAP = {
    '3121': 'DP01', '3180': 'DP01', 'MD01': 'DP01',
    '3149': 'DP02', '3270': 'DP02', 'P1003': 'DP02',
    '3199': 'DP03-East',
    '3271': 'DP03-West',
    '3204': 'DP04',
    '3205': 'DP05',
    '3206': 'DP06',
    '3207': 'DP07',
    '3200': 'Grand Canal', 'P0801': 'Grand Canal',
    '3107': 'West Canal', 'P1201': 'West Canal',
    '3048': 'Infra', 'SW00': 'Infra',
    '3044': 'MMS / Substation', 'MSS': 'MMS / Substation',
    '3045': 'RO Plant',
    '3046': 'STP', 'P5576': 'STP',
    '3049': 'Airport', 'P0153': 'Airport', 'AR01': 'Airport',
    '3091': 'Ring Road', 'RR00': 'Ring Road',
}

PROJECT_ALIASES = {
    'DP01': ['DP01', 'DP1', 'MD01', 'MDU', '3121', '3180', 'دي بي 1', 'دي بي 01', 'مارينا 1'],
    'DP02': ['DP02', 'DP2', '3149', '3270', 'P1003', 'K03149', 'دي بي 2', 'دي بي 02'],
    'DP03-East': ['DP03-EAST', 'DP03 EAST', 'DP3-EAST', 'DP3 EAST', '3199', 'K03199', 'INN-RED', 'INNRED', 'شرق', 'دي بي 3 شرق'],
    'DP03-West': ['DP03-WEST', 'DP03 WEST', 'DP3-WEST', 'DP3 WEST', '3271', 'K03271', 'RHD3', 'غرب', 'دي بي 3 غرب'],
    'DP04': ['DP04', 'DP4', '3204', 'K03204', 'ACCE', 'دي بي 4', 'دي بي 04'],
    'DP05': ['DP05', 'DP5', '3205', 'K03205', 'دي بي 5', 'دي بي 05'],
    'DP06': ['DP06', 'DP6', '3206', 'K03206', 'دي بي 6', 'دي بي 06'],
    'DP07': ['DP07', 'DP7', '3207', 'K03207', 'دي بي 7', 'دي بي 07'],
    'Grand Canal': ['GRAND CANAL', 'GRAND LAGOON', '3200', 'K03200', 'P0801', 'القناة الكبرى', 'جراند كانال'],
    'West Canal': ['WEST CANAL', '3107', 'K03107', 'P1201', 'القناة الغربية', 'ويست كانال'],
    'Infra': ['INFRA', 'INFRASTRUCTURE', '3048', 'K03048', 'SW00', 'البنية التحتية', 'البنيه التحتيه', 'انفرا'],
    'Airport': ['AIRPORT', 'AIR PORT', '3049', 'K00146', 'P0153', 'AR01', 'المطار', 'مطار'],
    'RO Plant': ['RO PLANT', 'RO', '3045', 'K03045', 'DESALINATION', 'تحلية', 'التحلية', 'محطة التحلية'],
    'STP': ['STP', '3046', 'K03046', 'P5576', 'SEWAGE', 'محطة الصرف', 'صرف', 'معالجة الصرف'],
    'MMS / Substation': ['MMS', 'MSS', '3044', 'K03044', 'SUBSTATION', 'محطة الكهرباء', 'محولات', 'كهرباء'],
    'Ring Road': ['RING ROAD', '3091', 'K03091', 'RR00', 'الدائري', 'طريق دائري', 'الطريق الدائري'],
    'Aedas Design Packages': ['AEDAS', 'AED-RFI', '3002', 'إيداس', 'ايداس'],
    'DP08 - South Golf': ['DP08', 'SOUTH GOLF', '3213', 'سوث جولف', 'دي بي 8']
}

CONSULTANT_KEYWORDS = {
    'Shaker-ECG': ['SHAKER', 'ECG', 'CONSOR', 'شاكر', 'اي سي جي', 'إي سي جي', 'الكونسورتيوم'],
    'Aedas': ['AEDAS', 'ايداس', 'إيداس'],
    'Hill': ['HILL', 'PMC', 'هيل']
}

CONTRACTOR_KEYWORDS = {
    'CCC': ['CCC', 'CONSOLIDATED CONTRACTORS', 'سي سي سي'],
    'Redcon / Innovo': ['REDCON', 'INNOVO', 'INN-RED', 'ريدكون', 'انوفو'],
    'ACC': ['ACC', 'ARABIAN CONSTRUCTION', 'اي سي سي'],
    'Hassan Allam': ['HASSAN ALLAM', 'HAC', 'حسن علام', 'علام']
}

def is_arabic(text: str) -> bool:
    return bool(re.search(r'[\u0600-\u06FF]', text))

def resolve_pkg_by_contract(subject: str, default_pkg: str = "") -> str:
    sub = (subject or "").upper()
    for k, v in CONTRACT_MAP.items():
        if re.search(r'(?:\b|K0?|P0?|REH[.\-_]|REH\.\d+\.\d+\.)' + re.escape(k) + r'(?:\b|[.\-_])', sub):
            return v
    for k in ['3271', '3199', '3204', '3205', '3206', '3207', '3149', '3270', '3121', '3180', '3200', '3107', '3048', '3044', '3045', '3046', '3049', '3091']:
        if k in sub:
            return CONTRACT_MAP[k]
    return default_pkg

def detect_project(text: str) -> str | None:
    t = text.upper()
    # Check exact contract numbers first
    for contract, pkg in CONTRACT_MAP.items():
        if re.search(r'\b' + re.escape(contract) + r'\b', t):
            return pkg
    for pkg, aliases in PROJECT_ALIASES.items():
        for a in aliases:
            if a.upper() in t:
                return pkg
    return None

def detect_date(text: str) -> str | None:
    # ISO date YYYY-MM-DD
    m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if m:
        return m.group(1)
    # DD/MM/YYYY or DD-MM-YYYY
    m = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})', text)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # Month in text (English & Arabic)
    if re.search(r'\b(شهر 3|مارس|march)\b', text, re.I):
        return '2026-03-01'
    if re.search(r'\b(شهر 4|أبريل|ابريل|april)\b', text, re.I):
        return '2026-04-01'
    if re.search(r'\b(شهر 5|مايو|may)\b', text, re.I):
        return '2026-05-01'
    if re.search(r'\b(شهر 6|يونيو|june)\b', text, re.I):
        return '2026-06-01'
    if re.search(r'\b(شهر 7|يوليو|july)\b', text, re.I):
        return '2026-07-01'
    if re.search(r'\b(شهر 8|أغسطس|اغسطس|august)\b', text, re.I):
        return '2026-08-01'
    if re.search(r'\b(شهر 9|سبتمبر|september)\b', text, re.I):
        return '2026-09-01'
    if re.search(r'\b(شهر 10|أكتوبر|اكتوبر|october)\b', text, re.I):
        return '2026-10-01'
    return None

def detect_deliverable_type(text: str) -> str:
    t = text.lower()
    if re.search(r'\b(scr|site clarification|توضيح|توضيحات|طلب توضيح)\b', t):
        return 'SCR'
    if re.search(r'\b(rfi|rfis|طلب معلومات|طلبات معلومات|استفسار|استفسارات)\b', t):
        return 'RFI'
    if re.search(r'\b(workflow|workflows|اعتماد|مراجعة|مراجعات|submittal|submittals)\b', t):
        return 'WORKFLOW'
    if re.search(r'\b(letter|letters|خطاب|خطابات|مراسلات|mail)\b', t):
        return 'LETTER'
    if re.search(r'\b(ball in court|bic|استشاري|موقف المراجعات)\b', t):
        return 'BIC'
    return 'ANY'

def detect_overdue_flag(text: str) -> bool:
    t = text.lower()
    return bool(re.search(r'\b(overdue|late|delayed|delay|متأخر|متاخر|متاخرات|متأخرات|تأخير|تاخير)\b', t))

def call_gemini_model(query: str, base_result: dict, is_ar: bool) -> str:
    """
    Calls Google Gemini API using configured key or environment variable.
    Grounded with live DuckDB facts and KPIs for authoritative, concise executive synthesis.
    """
    cfg = dss.get_gemini_config()
    api_key = cfg.get("api_key", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    
    if not api_key or not HAS_GENAI:
        # Graceful fallback: return SQL ground truth with helpful Gemini guidance
        return base_result.get("text", "")
    
    try:
        genai.configure(api_key=api_key)
        preferred_model = cfg.get("model", "gemini-3-flash-preview") or "gemini-3-flash-preview"
        MODEL_ALIASES = {
            "gemini-2.5-flash": "gemini-3-flash-preview",
            "gemini-2.0-flash": "gemini-3-flash-preview",
            "gemini-1.5-flash": "gemini-3-flash-preview",
            "gemini-1.5-pro": "gemini-3-flash-preview",
            "gemini-2.5-pro": "gemini-3-flash-preview"
        }
        target_model = MODEL_ALIASES.get(preferred_model, preferred_model)
        candidates = [target_model, "gemini-3-flash-preview", "gemini-flash-latest", "gemini-3.1-pro-preview"]
        
        prompt = f"""
You are the official Ras El Hekma Project Controls AI Copilot (Hill Copilot) - approved by Hill International (PMC) and powered by live Oracle Aconex database.
User Query: "{query}"

Live Verified Project Controls Ground Truth from Oracle Aconex DuckDB:
{base_result.get('text', '')}

Key Performance Indicators (KPIs):
{json.dumps(base_result.get('kpis', {}), ensure_ascii=False, indent=2)}

Instructions:
1. Provide an executive, professional response in {"Arabic" if is_ar else "English"}.
2. Explicitly adhere to Hill International Project Controls standards and methodologies.
3. Use markdown formatting with bolding on key numbers, SLAs, and package names.
4. Be clear and direct for senior management and project controls engineers.
5. Keep the response concise, informative, and actionable.
"""
        for cand in candidates:
            try:
                model = genai.GenerativeModel(cand)
                response = model.generate_content(prompt)
                if response and response.text and response.text.strip():
                    return response.text.strip()
            except Exception as e_inner:
                continue
    except Exception as e:
        print(f"[Gemini API Call Notice]: {e}")
        return base_result.get("text", "")
    
    return base_result.get("text", "")

def ask_ai_assistant(query: str, history: list = None) -> dict:
    """
    Main entry point for Gemini AI Assistant.
    Parses natural language, queries DuckDB, grounds facts, and synthesizes bilingual response.
    """
    q = (query or "").strip()
    if not q:
        return {
            "text": "Please enter a question or instruction." if not is_arabic(q) else "يرجى كتابة سؤالك أو طلبك.",
            "kpis": {},
            "table_headers": [],
            "table_rows": [],
            "suggested_queries": []
        }

    is_ar = is_arabic(q)
    project_pkg = detect_project(q)
    since_date = detect_date(q)
    deliv_type = detect_deliverable_type(q)
    is_overdue = detect_overdue_flag(q)

    con = get_db_connection()
    try:
        # Default date if not specified: March 1, 2026 per mandatory contract naming
        effective_date = since_date or "2026-03-01"

        res = None
        # Case 1: SCRs (Site Clarification Requests)
        if deliv_type == 'SCR' or (project_pkg == 'DP01' and deliv_type in ('RFI', 'ANY') and ('SCR' in q.upper() or 'توضيح' in q or 'CLARIFICATION' in q.upper())):
            res = handle_scr_query(con, q, project_pkg or 'DP01', effective_date, is_overdue, is_ar)

        # Case 2: RFIs
        elif deliv_type == 'RFI':
            res = handle_rfi_query(con, q, project_pkg, effective_date, is_overdue, is_ar)

        # Case 3: Workflows
        elif deliv_type == 'WORKFLOW':
            res = handle_workflow_query(con, q, project_pkg, is_overdue, is_ar)

        # Case 4: Letters & Correspondence
        elif deliv_type == 'LETTER':
            res = handle_letter_query(con, q, project_pkg, effective_date, is_overdue, is_ar)

        # Case 5: Ball in Court
        elif deliv_type == 'BIC':
            res = handle_bic_query(con, q, project_pkg, is_ar)

        # Case 6: General Package Summary or Mixed Query
        else:
            if project_pkg:
                res = handle_project_summary_query(con, q, project_pkg, effective_date, is_overdue, is_ar)
            else:
                res = handle_global_overview_query(con, q, effective_date, is_overdue, is_ar)

        if res and isinstance(res, dict):
            res["text"] = call_gemini_model(q, res, is_ar)
            return res
        return res

    finally:
        con.close()


# -----------------------------------------------------------------------------
# Handlers for Specific Deliverables
# -----------------------------------------------------------------------------
def handle_rfi_query(con, q: str, pkg: str | None, since_date: str, is_overdue: bool, is_ar: bool) -> dict:
    sql = """
        SELECT 
            mail_no, subject, from_organization, to_organization, 
            sent_date::VARCHAR, due_date::VARCHAR, days_late, is_overdue, 
            COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url,
            project_package
        FROM fact_rfis
        WHERE sent_date >= ?
    """
    params = [since_date]
    if is_overdue:
        sql += " AND (is_overdue = true OR days_late > 0)"

    rows = con.execute(sql, params).fetchall()

    # Re-apply contract-level mapping per user requirement
    mapped_rows = []
    for r in rows:
        resolved = resolve_pkg_by_contract(r[1], r[9])
        if pkg is None or resolved == pkg:
            mapped_rows.append({
                "mail_no": r[0],
                "subject": r[1],
                "from_org": r[2],
                "to_org": r[3] if r[3] and "Hill" not in r[3] else "Shaker-ECG consortium",
                "sent_date": str(r[4])[:10] if r[4] else "-",
                "due_date": str(r[5])[:10] if r[5] else "-",
                "days_late": int(r[6] or 0),
                "is_overdue": bool(r[7] or (r[6] and r[6] > 0)),
                "aconex_url": r[8],
                "package": resolved
            })

    mapped_rows.sort(key=lambda x: (x["is_overdue"], x["days_late"]), reverse=True)

    total_count = len(mapped_rows)
    overdue_count = sum(1 for x in mapped_rows if x["is_overdue"])
    max_late = max([x["days_late"] for x in mapped_rows] + [0])

    target_title = pkg or ("All Packages" if not is_ar else "جميع الحزم")
    date_display = since_date

    if is_ar:
        text = f"### تقرير طلبات المعلومات (RFIs) - {target_title}\n\n"
        if total_count == 0:
            text += f"لم يتم العثور على طلبات معلومات (RFI) مسجلة في **{target_title}** منذ تاريخ **{date_display}**.\n"
        else:
            text += f"تم العثور على **{total_count}** طلب معلومات (RFI) منذ تاريخ **{date_display}**.\n"
            if overdue_count > 0:
                text += f"- **المتأخرات على الاستشاري:** يوجد **{overdue_count}** طلب متأخر تجاوز مدة الرد التعاقدية (الحد الأقصى للتأخير: **+{max_late} يوم**).\n"
                text += f"- الاستشاري المسؤول عن المراجعة والرد هو **Shaker-ECG consortium** بالتنسيق مع مهندسي الموقع.\n"
            else:
                text += f"- جميع الطلبات ضمن المدد الزمنية المعتمدة ولا توجد متأخرات حرجة.\n"
    else:
        text = f"### Requests For Information (RFIs) Report - {target_title}\n\n"
        if total_count == 0:
            text += f"No RFIs found matching criteria in **{target_title}** since **{date_display}**.\n"
        else:
            text += f"Found **{total_count}** RFIs since **{date_display}** in **{target_title}**.\n"
            if overdue_count > 0:
                text += f"- **Consultant Overdue Bottlenecks:** **{overdue_count}** RFIs have exceeded contractual turnaround (Max Delay: **+{max_late} days**).\n"
                text += f"- Action is currently pending on **Shaker-ECG consortium** supervision engineers.\n"
            else:
                text += f"- All RFIs are currently within contractual turnaround SLAs.\n"

    headers = [
        "RFI No", "Package", "Subject / Scope", "Originator (Contractor)", 
        "Assigned Consultant", "Sent Date", "Due Date", "Days Late", "Aconex Link"
    ]
    rows_data = []
    for r in mapped_rows[:50]:
        rows_data.append([
            r["mail_no"],
            r["package"],
            r["subject"][:65] + ("..." if len(r["subject"]) > 65 else ""),
            r["from_org"],
            r["to_org"],
            r["sent_date"],
            r["due_date"],
            f"+{r['days_late']}d" if r["days_late"] > 0 else "0d",
            r["aconex_url"]
        ])

    kpis = {
        "Total Found": total_count,
        "Overdue Pending": overdue_count,
        "Max Delay": f"+{max_late}d",
        "Target Package": target_title
    }

    suggested = [
        ("عرض المتأخرات فقط" if is_ar else "Show Overdue Only"),
        ("ما هي المتأخرات في DP03-West؟" if is_ar else "What is overdue in DP03-West?"),
        ("توضيحات DP01 (SCR)" if is_ar else "View DP01 SCR Clarifications"),
        ("موقف استشاري شاكر وإي سي جي" if is_ar else "Shaker-ECG Bottlenecks")
    ]

    return {
        "text": text,
        "kpis": kpis,
        "table_headers": headers,
        "table_rows": rows_data,
        "suggested_queries": suggested
    }

def handle_scr_query(con, q: str, pkg: str, since_date: str, is_overdue: bool, is_ar: bool) -> dict:
    sql = """
        SELECT 
            mail_no, subject, from_organization, to_organization, 
            sent_date::VARCHAR, due_date::VARCHAR, days_late, is_overdue, 
            COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url,
            COALESCE(reference_number, mail_no) AS ref_no
        FROM fact_mail
        WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%')
          AND (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
          AND sent_date >= ?
    """
    params = [since_date]
    if is_overdue:
        sql += " AND (is_overdue = true OR days_late > 0)"

    sql += " ORDER BY days_late DESC, sent_date DESC"
    rows = con.execute(sql, params).fetchall()

    total_count = len(rows)
    overdue_count = sum(1 for r in rows if r[7] or (r[6] and r[6] > 0))
    max_late = max([r[6] for r in rows if r[6]] + [0])

    # Breakdown by consultant
    consultant_counts = defaultdict(int)
    for r in rows:
        to_c = r[3] or "Consultant"
        consultant_counts[to_c] += 1

    consultant_summary = ", ".join([f"{k} ({v})" for k, v in consultant_counts.items()])

    if is_ar:
        text = f"### طلبات التوضيح بالموقع (SCR) - مشروع DP01 (مارينا 1)\n\n"
        text += f"في مشروع **DP01**، يتم استخدام نظام طلبات التوضيح **SCR (Site Clarification Request)** بدلاً من الـ RFI التقليدي، طبقاً لكود العقد `REH-MD01-MDU-*-Hil-*-SCR`.\n\n"
        text += f"- **إجمالي طلبات SCR:** **{total_count}** طلب منذ **{since_date}**.\n"
        text += f"- **المتأخرات على الاستشاري:** **{overdue_count}** طلب متأخر قيد انتظار رد الاستشاريين (**{consultant_summary}**).\n"
        text += f"- **الحد الأقصى للتأخير:** **+{max_late} يوم**.\n"
    else:
        text = f"### Site Clarification Requests (SCR) - Package DP01\n\n"
        text += f"In package **DP01**, deliverables are governed via **SCR (Site Clarification Request)** protocol per mandatory format `REH-MD01-MDU-*-Hil-*-SCR`.\n\n"
        text += f"- **Total SCR Submittals:** **{total_count}** since **{since_date}**.\n"
        text += f"- **Overdue on Consultants:** **{overdue_count}** items pending technical determination (**{consultant_summary}**).\n"
        text += f"- **Maximum Delay:** **+{max_late} days**.\n"

    headers = [
        "SCR No", "Reference Code", "Subject", "Originator", 
        "Assigned Consultant", "Due Date", "Days Late", "Aconex Link"
    ]
    rows_data = []
    for r in rows[:50]:
        rows_data.append([
            r[0],
            r[9],
            r[1][:65] + ("..." if len(r[1]) > 65 else ""),
            r[2],
            f"To: {r[3]} (Pending)",
            str(r[5])[:10] if r[5] else "-",
            f"+{r[6]}d" if r[6] else "0d",
            r[8]
        ])

    kpis = {
        "Total SCRs": total_count,
        "Overdue Pending": overdue_count,
        "Pending on Consultants": consultant_summary or "None",
        "Package": "DP01"
    }

    suggested = [
        ("المتأخرات على Aedas Limited" if is_ar else "Overdue on Aedas Limited"),
        ("المتأخرات على ECG" if is_ar else "Overdue on ECG"),
        ("مقارنة مع مشاريع DP02 و DP03" if is_ar else "Compare with DP02 & DP03"),
        ("فتح تاب Controls & Overdue" if is_ar else "Go to Controls Dispatch")
    ]

    return {
        "text": text,
        "kpis": kpis,
        "table_headers": headers,
        "table_rows": rows_data,
        "suggested_queries": suggested
    }

def handle_workflow_query(con, q: str, pkg: str | None, is_overdue: bool, is_ar: bool) -> dict:
    sql = """
        SELECT 
            s.workflow_no, s.step_name, s.document_no, s.document_title,
            s.assigned_to_organization, s.assigned_to_name,
            s.date_due::VARCHAR, s.days_late, s.is_overdue,
            '/api/aconex/doc?doc_no=' || replace(document_no, chr(39), '') AS aconex_url,
            w.project_package
        FROM fact_workflow_steps s
        JOIN fact_workflows w ON s.workflow_no = w.workflow_no
        WHERE 1=1
    """
    params = []
    if pkg:
        sql += " AND w.project_package = ?"
        params.append(pkg)
    if is_overdue:
        sql += " AND s.is_overdue = true"
    
    # Priority on Shaker-ECG if mentioned or default in review context
    if "shaker" in q.lower() or "ecg" in q.lower() or "شاكر" in q or "اي سي جي" in q:
        sql += " AND (s.assigned_to_organization ILIKE '%shaker%' OR s.assigned_to_organization ILIKE '%ecg%')"

    sql += " ORDER BY s.days_late DESC, s.date_due ASC LIMIT 60"
    rows = con.execute(sql, params).fetchall()

    total_count = len(rows)
    overdue_count = sum(1 for r in rows if r[8])
    max_late = max([r[7] for r in rows if r[7]] + [0])

    target_title = pkg or ("All Packages" if not is_ar else "كافة المشاريع")

    if is_ar:
        text = f"### تقرير مراجعات وتدفقات العمل (Workflows) - {target_title}\n\n"
        text += f"- **عدد خطوات المراجعة:** **{total_count}** خطوة.\n"
        if overdue_count > 0:
            text += f"- **المتأخرات على فرق المراجعة:** **{overdue_count}** خطوة متأخرة تجاوزت موعد الاستحقاق (أقصى تأخير: **+{max_late} يوم**).\n"
            text += f"- التركيز الأكبر لخطوات المراجعة يقع على **Shaker-ECG consortium RASELHEKMA**.\n"
        else:
            text += f"- لا توجد خطوات متأخرة مطابقة لشروط البحث.\n"
    else:
        text = f"### Technical Review Workflows Report - {target_title}\n\n"
        text += f"- **Workflow Steps Count:** **{total_count}** steps.\n"
        if overdue_count > 0:
            text += f"- **Overdue Review Steps:** **{overdue_count}** overdue steps (Max Turnaround Delay: **+{max_late} days**).\n"
            text += f"- Primary review bottlenecks reside with **Shaker-ECG consortium RASELHEKMA**.\n"
        else:
            text += f"- No overdue workflow review steps found for given criteria.\n"

    headers = [
        "Workflow No", "Package", "Document No", "Document Title / Scope", 
        "Current Step", "Assigned Organization", "Due Date", "Days Late", "Aconex Link"
    ]
    rows_data = []
    for r in rows:
        rows_data.append([
            r[0],
            r[10],
            r[2] or "-",
            (r[3] or "-")[:60] + ("..." if len(r[3] or "") > 60 else ""),
            r[1] or "Review",
            r[4] or "Shaker-ECG consortium",
            str(r[6])[:10] if r[6] else "-",
            f"+{r[7]}d" if r[7] else "0d",
            r[9]
        ])

    kpis = {
        "Workflows Found": total_count,
        "Overdue Steps": overdue_count,
        "Max Delay": f"+{max_late}d",
        "Scope": target_title
    }

    suggested = [
        ("المتأخرات على Shaker-ECG فقط" if is_ar else "Shaker-ECG Overdue Only"),
        ("عرض طلبات المعلومات RFIs" if is_ar else "View RFIs for this Package"),
        ("تصدير إلى إكسيل" if is_ar else "Export to Excel Register")
    ]

    return {
        "text": text,
        "kpis": kpis,
        "table_headers": headers,
        "table_rows": rows_data,
        "suggested_queries": suggested
    }

def handle_letter_query(con, q: str, pkg: str | None, since_date: str, is_overdue: bool, is_ar: bool) -> dict:
    sql = """
        SELECT 
            mail_no, mail_type, subject, reference_number,
            from_organization, to_organization, sent_date::VARCHAR, due_date::VARCHAR,
            days_late, is_overdue,
            COALESCE(aconex_url, '/api/aconex/mail?mail_no=' || mail_no) AS aconex_url,
            project_package
        FROM fact_mail
        WHERE sent_date >= ?
          AND NOT (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
    """
    params = [since_date]
    if pkg:
        sql += " AND project_package = ?"
        params.append(pkg)
    if is_overdue:
        sql += " AND (is_overdue = true OR days_late > 0)"

    sql += " ORDER BY days_late DESC, sent_date DESC LIMIT 50"
    rows = con.execute(sql, params).fetchall()

    total_count = len(rows)
    overdue_count = sum(1 for r in rows if r[9] or (r[8] and r[8] > 0))
    max_late = max([r[8] for r in rows if r[8]] + [0])

    target_title = pkg or ("All Packages" if not is_ar else "جميع المشاريع")

    if is_ar:
        text = f"### تقرير الخطابات والمراسلات التعاقدية - {target_title}\n\n"
        text += f"- **إجمالي الخطابات:** **{total_count}** خطاب منذ **{since_date}**.\n"
        if overdue_count > 0:
            text += f"- **المراسلات المتأخرة قيد الرد:** **{overdue_count}** خطاب تجاوز مدة الرد (أقصى تأخير: **+{max_late} يوم**).\n"
        else:
            text += f"- لا توجد خطابات متأخرة مطابقة للبحث.\n"
    else:
        text = f"### Contractual Letters & Correspondence - {target_title}\n\n"
        text += f"- **Total Letters:** **{total_count}** letters since **{since_date}**.\n"
        if overdue_count > 0:
            text += f"- **Overdue Correspondence:** **{overdue_count}** letters pending contractual response (Max Delay: **+{max_late} days**).\n"
        else:
            text += f"- No overdue correspondence matching search criteria.\n"

    headers = [
        "Mail No", "Package", "Type", "Reference", "Subject", 
        "From", "To", "Due Date", "Days Late", "Aconex Link"
    ]
    rows_data = []
    for r in rows:
        rows_data.append([
            r[0],
            r[11],
            r[1] or "Letter",
            r[3] or "-",
            (r[2] or "-")[:60] + ("..." if len(r[2] or "") > 60 else ""),
            r[4] or "-",
            r[5] or "-",
            str(r[7])[:10] if r[7] else "-",
            f"+{r[8]}d" if r[8] else "0d",
            r[10]
        ])

    kpis = {
        "Letters Found": total_count,
        "Overdue Responses": overdue_count,
        "Max Delay": f"+{max_late}d",
        "Scope": target_title
    }

    suggested = [
        ("خطابات Hill و SSC المباشرة" if is_ar else "Hill & SSC Direct Letters"),
        ("طلبات المعلومات RFIs" if is_ar else "Show RFIs for this Package"),
        ("عرض شاشة Controls & Overdue" if is_ar else "Controls Dispatch Center")
    ]

    return {
        "text": text,
        "kpis": kpis,
        "table_headers": headers,
        "table_rows": rows_data,
        "suggested_queries": suggested
    }

def handle_bic_query(con, q: str, pkg: str | None, is_ar: bool) -> dict:
    sql = """
        SELECT 
            COALESCE(b.process_ref, b.mail_no, '-') as process_ref,
            COALESCE(b.project_package, '-') as project_package,
            COALESCE(b.mail_no, b.process_ref, '-') as doc_title,
            COALESCE(b.ball_in_court, '-') as ball_in_court_party,
            COALESCE(b.contractor, '-') as contractor,
            COALESCE(b.overdue_days, b.delay, b.duration, 0) as days_held,
            CASE WHEN b.is_overdue = true OR b.overdue_days > 0 THEN 'Overdue' ELSE 'Active' END as sla_status,
            COALESCE(b.action, b.process_status, 'Action Required') as action_status,
            COALESCE(b.aconex_url, '#') as aconex_url
        FROM fact_ball_in_court_processes b
        WHERE 1=1
    """
    params = []
    if pkg:
        sql += " AND b.project_package = ?"
        params.append(pkg)
        
    q_lower = q.lower()
    if "overdue" in q_lower or "متأخر" in q or "sla" in q_lower or "تأخير" in q:
        sql += " AND (b.is_overdue = true OR b.overdue_days > 0)"
        
    if "شاكر" in q or "shaker" in q_lower or "ecg" in q_lower:
        sql += " AND (b.ball_in_court ILIKE '%Shaker%' OR b.ball_in_court ILIKE '%ECG%')"
    elif "مقاول" in q or "contractor" in q_lower:
        sql += " AND (b.ball_in_court NOT ILIKE '%Shaker%' AND b.ball_in_court NOT ILIKE '%ECG%' AND b.ball_in_court NOT ILIKE '%Hill%')"

    sql += " ORDER BY b.overdue_days DESC, b.delay DESC LIMIT 50"
    rows = con.execute(sql, params).fetchall()

    total_count = len(rows)
    overdue_count = sum(1 for r in rows if r[6] == 'Overdue')
    max_days = int(max([r[5] for r in rows if r[5]] + [0]))

    target_title = pkg or ("All Packages" if not is_ar else "كافة المشاريع")

    if is_ar:
        text = f"### تقرير موقف الكرة في الملعب (Ball in Court) - {target_title}\n\n"
        text += f"- **إجمالي العمليات المعلقة:** **{total_count}** عملية مراجعة واستجابة.\n"
        text += f"- **العمليات المتجاوزة لـ SLA:** **{overdue_count}** عملية تجاوزت الوقت التعاقدي المحدد (أقصى تأخير: **+{max_days} يوم**).\n"
        if "شاكر" in q or "shaker" in q_lower or "ecg" in q_lower:
            text += f"- تم تصفية العمليات لتوضيح المعلقات على استشاري الإشراف **(Shaker-ECG Consortium)**.\n"
    else:
        text = f"### Ball in Court (BIC) Governance Report - {target_title}\n\n"
        text += f"- **Active Processes Held:** **{total_count}** deliverables.\n"
        text += f"- **SLA Overdue Bottlenecks:** **{overdue_count}** deliverables exceeded SLA (Max Delay: **+{max_days} days**).\n"
        if "shaker" in q_lower or "ecg" in q_lower:
            text += f"- Filtered to highlight bottlenecks on Supervision Consultant **(Shaker-ECG Consortium)**.\n"

    headers = [
        "Process Ref / Deliverable", "Package", "Title / Mail No", "Ball in Court Party", 
        "Contractor", "Days Held", "SLA Status", "Action / Status", "Aconex URL"
    ]
    rows_data = []
    for r in rows:
        late_val = int(r[5]) if r[5] else 0
        rows_data.append([
            r[0],
            r[1],
            (r[2] or "-")[:55] + ("..." if len(r[2] or "") > 55 else ""),
            r[3] or "-",
            r[4] or "-",
            f"+{late_val}d" if late_val > 0 else "0d",
            r[6] or "Active",
            r[7] or "Pending",
            r[8] or "#"
        ])

    kpis = {
        "Total Held": total_count,
        "SLA Overdue": overdue_count,
        "Max Delay": f"+{max_days}d" if max_days > 0 else "0d",
        "Target": target_title
    }

    suggested = [
        ("موقف استشاري الإشراف Shaker-ECG" if is_ar else "Shaker-ECG Held Items"),
        ("المتأخرات على المقاولين" if is_ar else "Contractor Held Items"),
        ("فتح تاب Ball in Court" if is_ar else "Go to Ball in Court Tab"),
        ("طلبات المعلومات المتأخرة في DP03-West" if is_ar else "Overdue RFIs in DP03-West")
    ]

    return {
        "text": text,
        "kpis": kpis,
        "table_headers": headers,
        "table_rows": rows_data,
        "suggested_queries": suggested
    }

def handle_project_summary_query(con, q: str, pkg: str, since_date: str, is_overdue: bool, is_ar: bool) -> dict:
    # 1. Project details
    p_row = con.execute("""
        SELECT project_id, project_title, category, contract_no, k_package_no, contractor_name
        FROM dim_project_packages
        WHERE project_id = ?
        LIMIT 1
    """, [pkg]).fetchone()

    p_title = p_row[1] if p_row else pkg
    p_contract = p_row[3] if p_row else "-"
    p_contractor = p_row[5] if p_row else "-"

    # 2. Overdue counts
    wf_count = con.execute("""
        SELECT count(*) FROM fact_workflow_steps s 
        JOIN fact_workflows w ON s.workflow_no = w.workflow_no 
        WHERE w.project_package = ? AND s.is_overdue = true
          AND (s.assigned_to_organization ILIKE '%shaker%' OR s.assigned_to_organization ILIKE '%ecg%'
               OR NOT EXISTS (
                   SELECT 1 FROM fact_workflow_steps s2 
                   JOIN fact_workflows w2 ON s2.workflow_no = w2.workflow_no 
                   WHERE w2.project_package = ? AND s2.is_overdue = true 
                     AND (s2.assigned_to_organization ILIKE '%shaker%' OR s2.assigned_to_organization ILIKE '%ecg%')
               ))
    """, [pkg, pkg]).fetchone()[0]

    mail_count = con.execute("""
        SELECT count(*) FROM fact_mail 
        WHERE project_package = ? AND (is_overdue = true OR days_late > 0)
          AND NOT (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
          AND sent_date >= ?
    """, [pkg, since_date]).fetchone()[0]

    # RFIs contract-resolved
    all_rfis = con.execute("""
        SELECT mail_no, subject FROM fact_rfis 
        WHERE (is_overdue = true OR days_late > 0) AND sent_date >= ?
    """, [since_date]).fetchall()
    rfi_count = sum(1 for r in all_rfis if resolve_pkg_by_contract(r[1]) == pkg)

    # SCR count for DP01
    scr_count = 0
    if pkg == 'DP01':
        scr_count = con.execute("""
            SELECT count(*) FROM fact_mail 
            WHERE (project_package = 'DP01' OR subject ILIKE '%MD01%')
              AND (mail_type IN ('Site Clarification Request', 'Response to Clarification') OR subject ILIKE '%SCR%')
              AND (is_overdue = true OR days_late > 0)
              AND sent_date >= ?
        """, [since_date]).fetchone()[0]

    tot_overdue = wf_count + mail_count + rfi_count + scr_count

    if is_ar:
        text = f"### ملخص مشروع: {p_title} ({pkg})\n\n"
        text += f"- **المقاول الرئيسي:** {p_contractor} | **رقم العقد:** `{p_contract}`\n"
        text += f"- **إجمالي المتأخرات المسجلة:** **{tot_overdue}** بند قيد المراجعة والرد.\n\n"
        text += f"#### التوزيع التفصيلي للمتأخرات:\n"
        text += f"1. **مراجعات وتدفقات العمل (Workflows):** **{wf_count}** خطوة متأخرة على استشاري الإشراف (Shaker-ECG).\n"
        text += f"2. **الخطابات والمراسلات (Letters):** **{mail_count}** خطاب متأخر قيد الرد.\n"
        if pkg == 'DP01':
            text += f"3. **طلبات التوضيح بالموقع (SCR):** **{scr_count}** طلب متأخر قيد انتظار رد الاستشاريين (ECG / Aedas).\n"
        else:
            text += f"3. **طلبات المعلومات (RFIs):** **{rfi_count}** طلب متأخر قيد انتظار رد الاستشاري (Shaker-ECG).\n"
    else:
        text = f"### Executive Controls Summary: {p_title} ({pkg})\n\n"
        text += f"- **Main Contractor:** {p_contractor} | **Contract Code:** `{p_contract}`\n"
        text += f"- **Total Overdue Deliverables:** **{tot_overdue}** items exceeding SLA.\n\n"
        text += f"#### Overdue Breakdown:\n"
        text += f"1. **Technical Workflows:** **{wf_count}** review steps pending on Supervision Consultants (Shaker-ECG).\n"
        text += f"2. **Official Letters:** **{mail_count}** correspondence items pending response.\n"
        if pkg == 'DP01':
            text += f"3. **Site Clarifications (SCR):** **{scr_count}** SCRs pending consultant determination (ECG / Aedas).\n"
        else:
            text += f"3. **Requests For Information (RFIs):** **{rfi_count}** RFIs pending consultant response (Shaker-ECG).\n"

    kpis = {
        "Package": pkg,
        "Total Overdue": tot_overdue,
        "Workflows Late": wf_count,
        "RFIs/SCRs Late": scr_count if pkg == 'DP01' else rfi_count
    }

    # Pull top 10 overdue items across categories for table
    return handle_rfi_query(con, q, pkg, since_date, is_overdue=True, is_ar=is_ar) if (rfi_count > 0 or scr_count > 0) else handle_workflow_query(con, q, pkg, is_overdue=True, is_ar=is_ar)

def handle_global_overview_query(con, q: str, since_date: str, is_overdue: bool, is_ar: bool) -> dict:
    # High-level aggregate across project
    total_docs = con.execute("SELECT count(*) FROM dim_documents").fetchone()[0]
    total_wf = con.execute("SELECT count(*) FROM fact_workflows WHERE workflow_status = 'In Progress'").fetchone()[0]
    overdue_wf = con.execute("SELECT count(*) FROM fact_workflow_steps WHERE is_overdue = true").fetchone()[0]
    overdue_rfis = con.execute("SELECT count(*) FROM fact_rfis WHERE (is_overdue = true OR days_late > 0) AND sent_date >= '2026-03-01'").fetchone()[0]
    overdue_mails = con.execute("SELECT count(*) FROM fact_mail WHERE (is_overdue = true OR days_late > 0) AND sent_date >= '2026-03-01'").fetchone()[0]

    if is_ar:
        text = f"### نظرة عامة شاملة لمشروع رأس الحكمة (Oracle Aconex Live Controls)\n\n"
        text += f"- **إجمالي الوثائق والمخططات:** **{total_docs:,}** وثيقة.\n"
        text += f"- **تدفقات العمل النشطة:** **{total_wf:,}** تدفق قيد المراجعة والاعتماد.\n"
        text += f"- **المتأخرات على استشاري الإشراف (Shaker-ECG):** **{overdue_wf:,}** خطوة مراجعة متأخرة.\n"
        text += f"- **طلبات المعلومات (RFIs) المتأخرة:** **{overdue_rfis}** طلب متأخر منذ تطبيق نظام التسمية الإلزامي (مارس 2026).\n"
        text += f"- **الخطابات المتأخرة:** **{overdue_mails}** خطاب قيد الرد.\n\n"
        text += f"💡 *يمكنك سؤالي عن أي حزمة معينة مثل: 'طلعلي كل ال RFI في مشروع DP03-West' أو 'ما هي طلبات التوضيح SCR في DP01؟'.*"
    else:
        text = f"### Global Ras El Hekma Project Controls Overview (Oracle Aconex Live)\n\n"
        text += f"- **Total Documents & Drawings:** **{total_docs:,}** controlled documents.\n"
        text += f"- **Active Review Workflows:** **{total_wf:,}** workflows in progress.\n"
        text += f"- **Supervision Review Bottlenecks (Shaker-ECG):** **{overdue_wf:,}** overdue steps.\n"
        text += f"- **Overdue Contractor RFIs:** **{overdue_rfis}** RFIs pending consultant response since March 2026.\n"
        text += f"- **Overdue Contractual Letters:** **{overdue_mails}** letters pending reply.\n\n"
        text += f"💡 *You can ask specific questions like: 'Show all RFIs in DP03-West since 2026-06-01' or 'Show SCR clarifications in DP01'.*"

    kpis = {
        "Total Controlled Documents": f"{total_docs:,}",
        "Active Workflows": f"{total_wf:,}",
        "Overdue Workflow Steps": f"{overdue_wf:,}",
        "Contract-Mapped Overdue RFIs": overdue_rfis
    }

    suggested = [
        ("طلعلي كل ال RFI في مشروع DP03-West من يوم 2026-06-01" if is_ar else "Show all RFIs in DP03-West since 2026-06-01"),
        ("طلبات التوضيح SCR في مشروع DP01" if is_ar else "Site Clarification Requests in DP01"),
        ("ما هي المتأخرات على استشاري شاكر وإي سي جي؟" if is_ar else "Overdue review steps on Shaker-ECG"),
        ("ملخص مشروع البنية التحتية Infra" if is_ar else "Summary of Infra Package")
    ]

    return {
        "text": text,
        "kpis": kpis,
        "table_headers": ["Category", "Metric", "Value", "Status"],
        "table_rows": [
            ["Documents", "Total Master Documents", f"{total_docs:,}", "Controlled"],
            ["Workflows", "Active In-Progress Workflows", f"{total_wf:,}", "Active"],
            ["Controls", "Overdue Review Steps (Shaker-ECG)", f"{overdue_wf:,}", "Action Required"],
            ["RFIs", "Overdue Technical RFIs", f"{overdue_rfis}", "Consultant Action"],
            ["Letters", "Overdue Contractual Letters", f"{overdue_mails}", "Pending Response"]
        ],
        "suggested_queries": suggested
    }
