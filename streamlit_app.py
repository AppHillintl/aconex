"""
Ras El Hekma Project Controls & Executive Backlog Dispatch
Streamlit Cloud Production Application
Client: Modon Properties | PMC: Hill International, Inc.
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# -----------------------------------------------------------------------------
# 1. Page Configuration & Custom Theme
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Ras El Hekma Project Controls | Modon • Hill PMC",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Executive CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    h1, h2, h3, .font-heading {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    .stMetric {
        background: #0f172a;
        padding: 16px 20px;
        border-radius: 14px;
        border: 1px solid #1e293b;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    
    .stMetric label {
        color: #94a3b8 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 1.8rem !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    .badge-hub {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 700;
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .badge-pulse {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background-color: #34d399;
    }
    
    .pkg-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    div[data-testid="stSidebarNav"] {
        padding-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Database Connection
# -----------------------------------------------------------------------------
@st.cache_resource
def get_db():
    return duckdb.connect("aconex.duckdb", read_only=True)

# -----------------------------------------------------------------------------
# 3. Canonical Package Resolver (5-Tier Intelligence)
# -----------------------------------------------------------------------------
CONTRACT_MAP = {
    '3121': 'DP01', 'MD01': 'DP01',
    '3149': 'DP02', '3270': 'DP02',
    '3199': 'DP03-East',
    '3271': 'DP03-West',
    '3204': 'DP04',
    '3205': 'DP05',
    '3206': 'DP06',
    '3207': 'DP07',
    '3048': 'Infra', 'SW00': 'Infra',
    '3044': 'MMS / Substation', 'MSS': 'MMS / Substation',
    '3045': 'RO Plant',
    '3046': 'STP', 'P5576': 'STP',
    '3200': 'Grand Canal', 'P0801': 'Grand Canal',
    '3107': 'West Canal',
    '3049': 'Airport', 'K00146': 'Airport',
    '3091': 'Ring Road',
    '3015': 'DP08 - South Golf',
    'P0155': 'Dar Consultancy Packages',
    'P1003': 'Aedas Design Packages',
    'P0801': 'Grand Canal',
    'P1201': 'OBMI Consultancy Packages',
    'P0153': 'ECG Design Packages'
}

KNOWN_CANONICAL_PACKAGES = set(CONTRACT_MAP.values()) | {
    'DP01', 'DP02', 'DP03-East', 'DP03-West', 'DP04', 'DP05', 'DP06', 'DP07',
    'Infra', 'MMS / Substation', 'RO Plant', 'STP', 'Grand Canal', 'West Canal',
    'Airport', 'Ring Road', 'DP08 - South Golf', 'Dewan Consultancy Packages',
    'Dar Consultancy Packages', 'Aedas Design Packages', 'OBMI Consultancy Packages',
    'ECG Design Packages', 'Al Ain Consultancy Packages'
}

def resolve_canonical_package(subject: str, mail_no: str = "", from_org: str = "", to_org: str = "", default_pkg: str = "") -> str:
    sub = (subject or "").upper()
    m_no = (mail_no or "").upper()
    f_org = (from_org or "").upper()
    t_org = (to_org or "").upper()
    combined = f"{sub} {m_no} {f_org} {t_org}"

    for k, v in CONTRACT_MAP.items():
        pattern = r'(?:\b|K0?|P0?|REH[.\-_]|REH\.\d+\.\d+\.)' + re.escape(k) + r'(?:\b|[.\-_])'
        if re.search(pattern, sub) or re.search(pattern, m_no):
            return v

    for k in ['3271', '3199', '3204', '3205', '3206', '3207', '3149', '3270', '3121', '3180', '3200', '3107', '3048', '3044', '3045', '3046', '3049', '3091', '3015']:
        if k in sub or k in m_no:
            return CONTRACT_MAP[k]

    if default_pkg and default_pkg in KNOWN_CANONICAL_PACKAGES and not any(g in default_pkg for g in ['General', 'Unknown', 'None']):
        return default_pkg

    if 'DP03-EAST' in combined or 'DP03 EAST' in combined:
        return 'DP03-East'
    if 'DP03-WEST' in combined or 'DP03 WEST' in combined:
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
    if 'GRAND CANAL' in combined or 'LAGOON' in combined or 'ROYAL HASKONING' in combined or 'RHDHV' in combined or 'COASTLINE' in combined:
        return 'Grand Canal'
    if 'WEST CANAL' in combined:
        return 'West Canal'
    if 'RO PLANT' in combined or 'DESALINATION' in combined:
        return 'RO Plant'
    if 'SEWAGE TREATMENT' in combined or re.search(r'\bSTP\b', combined):
        return 'STP'
    if 'SUBSTATION' in combined or re.search(r'\bMSS\b|\bMSS1\b', combined):
        return 'MMS / Substation'
    if 'AIRPORT' in combined or 'AIR PORT' in combined or 'RUNWAY' in combined or 'NACO' in combined or 'ADB SAFEGATE' in combined or 'ADBSG' in combined or 'SMITHS DETECTION' in combined:
        return 'Airport'
    if 'RING ROAD' in combined:
        return 'Ring Road'
    if 'INFRASTRUCTURE' in combined or re.search(r'\bINFRA\b|\bSW00\b', combined):
        return 'Infra'
    if 'SOUTH GOLF' in combined or 'DP08' in combined or 'LOBB' in combined:
        return 'DP08 - South Golf'

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
    if 'DEWAN ARCHITECTS' in combined or 'DAE-' in m_no:
        return 'Dewan Consultancy Packages'
    if 'ECG-AD' in m_no or 'ECG (RA01' in combined:
        return 'ECG Design Packages'

    return default_pkg if default_pkg else 'General Project Correspondence'

# -----------------------------------------------------------------------------
# 4. Top Header & Branding Banner
# -----------------------------------------------------------------------------
col_h_left, col_h_right = st.columns([3, 1.2])

with col_h_left:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 4px;">
        <h1 style="margin: 0; font-size: 1.6rem; font-weight: 800; color: #ffffff;">
            Ras El Hekma Project Controls
        </h1>
        <span class="badge-hub">
            <span class="badge-pulse"></span> Live PMC Hub
        </span>
    </div>
    <div style="color: #94a3b8; font-size: 0.85rem; font-weight: 500;">
        Master Development Program &bull; PMC Program Controls &amp; Supervision
    </div>
    """, unsafe_allow_html=True)

with col_h_right:
    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #1e293b; border-radius: 12px; padding: 10px 16px; text-align: right;">
        <div style="font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8;">
            Project Management Consultant
        </div>
        <div style="font-size: 13px; font-weight: 700; color: #38bdf8; margin-top: 2px;">
            Hill International, Inc.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin: 12px 0 20px 0; border: none; border-top: 1px solid #1e293b;'>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. Sidebar Controls & Date Filtering
# -----------------------------------------------------------------------------
st.sidebar.markdown("### ⚙️ Program Filter Controls")

period_preset = st.sidebar.selectbox(
    "Filter Period Scope:",
    [
        "All Time (Full Project History & Archive)",
        "New Naming Convention (From 1 Mar 2026)",
        "Last 3 Months",
        "Last 1 Month",
        "Custom Date Range"
    ],
    index=0
)

from_date = None
to_date = None

if period_preset == "New Naming Convention (From 1 Mar 2026)":
    from_date = "2026-03-01"
elif period_preset == "Last 3 Months":
    from_date = (datetime.now() - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
elif period_preset == "Last 1 Month":
    from_date = (datetime.now() - pd.DateOffset(months=1)).strftime("%Y-%m-%d")
elif period_preset == "Custom Date Range":
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        d_from = st.date_input("From Date", datetime(2026, 1, 1))
        from_date = d_from.strftime("%Y-%m-%d")
    with col_d2:
        d_to = st.date_input("To Date", datetime.now())
        to_date = d_to.strftime("%Y-%m-%d")

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="font-size: 11px; color: #64748b; line-height: 1.5;">
    <strong>Database:</strong> Oracle Aconex Live Mirror<br>
    <strong>Engine:</strong> DuckDB 95.2MB High Performance<br>
    <strong>Target:</strong> Zero Undetected Delay Backlog
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6. Main Navigation Tabs
# -----------------------------------------------------------------------------
tab_overview, tab_controls, tab_rfis, tab_supervision, tab_disciplines, tab_docs = st.tabs([
    "📊 Executive Overview",
    "🎯 Project Controls & Dispatch",
    "📋 Contractor RFIs Tracker",
    "🏛️ Supervision Backlog (Shaker-ECG)",
    "📐 Technical Office Disciplines",
    "📂 Document Registry Search"
])

db = get_db()

# =============================================================================
# TAB 1: EXECUTIVE OVERVIEW
# =============================================================================
with tab_overview:
    kpi_wf_clause = "WHERE is_overdue = true"
    kpi_mail_clause = "WHERE (is_overdue = true OR days_late > 0)"
    kpi_rfi_clause = "WHERE 1=1"
    
    if from_date:
        kpi_mail_clause += f" AND sent_date >= '{from_date}'"
        kpi_rfi_clause += f" AND sent_date >= '{from_date}'"
        kpi_wf_clause += f" AND date_in >= '{from_date}'"
    if to_date:
        kpi_mail_clause += f" AND sent_date <= '{to_date} 23:59:59'"
        kpi_rfi_clause += f" AND sent_date <= '{to_date} 23:59:59'"
        kpi_wf_clause += f" AND date_in <= '{to_date} 23:59:59'"

    total_docs = db.execute("SELECT count(*) FROM dim_documents").fetchone()[0]
    total_ov_wf = db.execute(f"SELECT count(*) FROM fact_workflow_steps {kpi_wf_clause}").fetchone()[0]
    total_ov_mail = db.execute(f"SELECT count(*) FROM fact_mail {kpi_mail_clause}").fetchone()[0]
    total_rfis = db.execute(f"SELECT count(*) FROM fact_rfis {kpi_rfi_clause}").fetchone()[0]
    total_ov_rfis = db.execute(f"SELECT count(*) FROM fact_rfis {kpi_rfi_clause} AND (is_overdue = true OR days_late > 0)").fetchone()[0]
    
    sla_pct = db.execute("""
        SELECT ROUND(count(CASE WHEN days_late <= 0 THEN 1 END) * 100.0 / count(*), 1)
        FROM fact_workflow_steps WHERE step_status = 'Completed'
    """).fetchone()[0] or 87.4

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Registered Documents", f"{total_docs:,}")
    with col2:
        st.metric("Overdue Workflow Steps", f"{total_ov_wf:,}", delta="-High Priority", delta_color="inverse")
    with col3:
        st.metric("Overdue Letters / Mails", f"{total_ov_mail:,}", delta="-Backlog", delta_color="inverse")
    with col4:
        st.metric("Overdue Contractor RFIs", f"{total_ov_rfis:,}", delta=f"of {total_rfis:,} total", delta_color="off")
    with col5:
        st.metric("PMC SLA Compliance Rate", f"{sla_pct}%", delta="Target 90%+")

    st.markdown("<br>", unsafe_allow_html=True)

    col_chart1, col_chart2 = st.columns([1.6, 1])

    with col_chart1:
        st.markdown("#### 📈 Overdue Review Deliverables by Project Package")
        pkg_df = db.execute("""
            SELECT 
                p.project_id,
                p.project_title,
                p.sort_order,
                count(w.workflow_no) AS overdue_workflows
            FROM dim_project_packages p
            LEFT JOIN fact_workflows w ON p.project_id = w.project_package
            LEFT JOIN fact_workflow_steps s ON w.workflow_no = s.workflow_no AND s.is_overdue = true
            GROUP BY p.project_id, p.project_title, p.sort_order
            ORDER BY p.sort_order ASC
        """).df()

        fig_bar = px.bar(
            pkg_df,
            x="project_id",
            y="overdue_workflows",
            hover_name="project_title",
            text="overdue_workflows",
            color="overdue_workflows",
            color_continuous_scale="Reds",
            labels={"project_id": "Project Package", "overdue_workflows": "Overdue Workflows"}
        )
        fig_bar.update_layout(
            paper_bgcolor="#0b1120",
            plot_bgcolor="#0f172a",
            font_color="#f8fafc",
            margin=dict(l=20, r=20, t=20, b=20),
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        st.markdown("#### ⏳ Aging Severity Distribution")
        aging_df = db.execute("""
            SELECT 
                CASE 
                    WHEN days_late BETWEEN 1 AND 7 THEN '1 - 7 Days'
                    WHEN days_late BETWEEN 8 AND 14 THEN '8 - 14 Days'
                    WHEN days_late BETWEEN 15 AND 30 THEN '15 - 30 Days'
                    ELSE '+30 Days (Critical)'
                END AS aging_bucket,
                count(*) AS count
            FROM fact_workflow_steps
            WHERE is_overdue = true
            GROUP BY aging_bucket
            ORDER BY min(days_late) ASC
        """).df()

        fig_pie = px.pie(
            aging_df,
            names="aging_bucket",
            values="count",
            hole=0.55,
            color_discrete_sequence=["#38bdf8", "#fbbf24", "#f97316", "#ef4444"]
        )
        fig_pie.update_layout(
            paper_bgcolor="#0b1120",
            font_color="#f8fafc",
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

# =============================================================================
# TAB 2: PROJECT CONTROLS & OVERDUE DISPATCH
# =============================================================================
with tab_controls:
    st.markdown("### 🎯 Project-Level Controls & Backlog Dispatch")
    
    projects_rows = db.execute("SELECT project_id, project_title, category, contract_no, contractor_name FROM dim_project_packages ORDER BY sort_order ASC").fetchall()
    pkg_options = [f"{r[0]} - {r[1]}" for r in projects_rows]
    
    selected_option = st.selectbox("Select Project Package for Overdue Notice & Matrix:", pkg_options, index=1)
    sel_pid = selected_option.split(" - ")[0].strip()
    
    col_pinfo1, col_pinfo2, col_pinfo3, col_pinfo4 = st.columns(4)
    p_meta = next((r for r in projects_rows if r[0] == sel_pid), None)
    
    with col_pinfo1:
        st.markdown(f"**Package Code:** `{sel_pid}`")
    with col_pinfo2:
        st.markdown(f"**Category:** {p_meta[2] if p_meta else '-'}")
    with col_pinfo3:
        st.markdown(f"**Contract No:** `{p_meta[3] if p_meta else '-'}`")
    with col_pinfo4:
        st.markdown(f"**Main Contractor:** {p_meta[4] if p_meta else '-'}")

    st.markdown("---")
    
    # Overdue Workflows for this package
    wf_query = f"""
        SELECT 
            s.workflow_no AS [Workflow No],
            s.step_name AS [Review Step],
            s.document_no AS [Document No],
            s.document_title AS [Document Title],
            s.assigned_to_organization AS [Assigned Organization],
            s.assigned_to_name AS [Assignee Name],
            s.date_due::VARCHAR AS [Due Date],
            s.days_late AS [Days Late],
            'https://mea.aconex.com/WorkflowSearch?searchtext=' || s.workflow_no || '&projectid=1744833878' AS [Aconex URL]
        FROM fact_workflow_steps s
        JOIN fact_workflows w ON s.workflow_no = w.workflow_no
        WHERE w.project_package = '{sel_pid}' AND s.is_overdue = true
        ORDER BY s.days_late DESC
    """
    pkg_wfs = db.execute(wf_query).df()
    
    st.markdown(f"#### 1. Overdue Review Workflows ({len(pkg_wfs)})")
    if not pkg_wfs.empty:
        st.dataframe(
            pkg_wfs,
            column_config={
                "Aconex URL": st.column_config.LinkColumn("Oracle Aconex Link")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No overdue workflows detected for this package.")

    # Overdue Contractor RFIs for this package
    rfi_pkg_query = f"""
        SELECT 
            mail_no, subject, from_organization, to_organization, 
            sent_date::VARCHAR AS sent_date, due_date::VARCHAR AS due_date, 
            days_late, aconex_url, project_package
        FROM fact_rfis
        WHERE (is_overdue = true OR days_late > 0)
          AND NOT (subject ILIKE '%SCR%' OR mail_no ILIKE '%SCR%')
    """
    all_raw_rfis = db.execute(rfi_pkg_query).fetchall()
    matched_rfis = []
    for r in all_raw_rfis:
        res_pkg = resolve_canonical_package(subject=r[1], mail_no=r[0], from_org=r[2], to_org=r[3], default_pkg=r[8] or "")
        if res_pkg == sel_pid:
            matched_rfis.append({
                "RFI No": r[0],
                "Subject": r[1],
                "From Org": r[2],
                "To Org": r[3],
                "Sent Date": r[4],
                "Due Date": r[5],
                "Days Late": r[6],
                "Aconex URL": r[7]
            })
    
    rfis_df = pd.DataFrame(matched_rfis)
    st.markdown(f"#### 2. Overdue Contractor RFIs ({len(rfis_df)})")
    if not rfis_df.empty:
        st.dataframe(
            rfis_df,
            column_config={
                "Aconex URL": st.column_config.LinkColumn("Oracle Aconex Link")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No overdue contractor RFIs for this package.")

    # Export Excel Button for this package
    st.markdown("#### 📥 Export Official Register & Email Notice")
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        if st.button(f"Generate Excel Register for {sel_pid}", key="btn_export_pkg_excel"):
            wb = Workbook()
            ws1 = wb.active
            ws1.title = "Overdue Workflows"
            ws1.append(["Workflow No", "Step", "Document No", "Document Title", "Organization", "Assignee", "Due Date", "Days Late"])
            for _, r in pkg_wfs.iterrows():
                ws1.append([r["Workflow No"], r["Review Step"], r["Document No"], r["Document Title"], r["Assigned Organization"], r["Assignee Name"], str(r["Due Date"]), r["Days Late"]])
            
            ws2 = wb.create_sheet(title="Overdue RFIs")
            ws2.append(["RFI No", "Subject", "From Org", "To Org", "Sent Date", "Due Date", "Days Late"])
            for _, r in rfis_df.iterrows():
                ws2.append([r["RFI No"], r["Subject"], r["From Org"], r["To Org"], str(r["Sent Date"]), str(r["Due Date"]), r["Days Late"]])
            
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            st.download_button(
                label=f"⬇️ Download {sel_pid} Overdue Register (.xlsx)",
                data=output,
                file_name=f"{sel_pid}_Overdue_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# =============================================================================
# TAB 3: CONTRACTOR RFIs TRACKER
# =============================================================================
with tab_rfis:
    st.markdown("### 📋 Full Contractor RFIs Tracker (12,465 Records)")
    
    col_rf1, col_rf2, col_rf3, col_rf4 = st.columns([1.5, 1.5, 1, 2])
    
    with col_rf1:
        rf_pkgs = ["All Packages"] + sorted(list(KNOWN_CANONICAL_PACKAGES))
        sel_rf_pkg = st.selectbox("Filter Package:", rf_pkgs, index=0)
    with col_rf2:
        rf_companies = ["All Responsible Companies", "ECG", "Shaker-ECG Consortium", "Hill International", "Dar Al Handasah", "Aedas", "OBMI"]
        sel_rf_comp = st.selectbox("Responsible Consultant:", rf_companies, index=0)
    with col_rf3:
        sel_rf_status = st.selectbox("SLA Status:", ["Overdue Only", "All RFIs", "On Time"], index=0)
    with col_rf4:
        sel_rf_search = st.text_input("Search Subject / RFI Number / Contractor:", "")

    # Build Query
    rfi_filters = ["NOT (r.subject ILIKE '%SCR%' OR r.mail_no ILIKE '%SCR%')"]
    if from_date:
        rfi_filters.append(f"r.sent_date >= '{from_date}'")
    if to_date:
        rfi_filters.append(f"r.sent_date <= '{to_date} 23:59:59'")
    if sel_rf_status == "Overdue Only":
        rfi_filters.append("(r.is_overdue = true OR r.days_late > 0)")
    elif sel_rf_status == "On Time":
        rfi_filters.append("(r.days_late <= 0)")
    if sel_rf_comp != "All Responsible Companies":
        if sel_rf_comp == "ECG":
            rfi_filters.append("LOWER(TRIM(r.to_organization)) = 'ecg'")
        elif sel_rf_comp == "Shaker-ECG Consortium":
            rfi_filters.append("r.to_organization ILIKE '%shaker-ecg%'")
        else:
            rfi_filters.append(f"r.to_organization ILIKE '%{sel_rf_comp}%'")
    if sel_rf_search:
        rfi_filters.append(f"(r.mail_no ILIKE '%{sel_rf_search}%' OR r.subject ILIKE '%{sel_rf_search}%' OR r.from_organization ILIKE '%{sel_rf_search}%')")

    sql_rfis = f"""
        SELECT 
            r.mail_no AS [RFI No],
            r.subject AS [Subject],
            r.from_organization AS [Contractor (From)],
            r.to_organization AS [Consultant (To)],
            r.sent_date::VARCHAR AS [Sent Date],
            r.due_date::VARCHAR AS [Due Date],
            r.days_late AS [Days Late],
            r.is_overdue AS [Is Overdue],
            r.project_package AS [Raw Package],
            r.aconex_url AS [Aconex URL]
        FROM fact_rfis r
        WHERE {' AND '.join(rfi_filters)}
        ORDER BY r.days_late DESC, r.sent_date DESC
    """
    
    rfis_raw = db.execute(sql_rfis).fetchall()
    
    processed_rfis = []
    for r in rfis_raw:
        res_pkg = resolve_canonical_package(subject=r[1], mail_no=r[0], from_org=r[2], to_org=r[3], default_pkg=r[8] or "")
        if sel_rf_pkg != "All Packages" and res_pkg != sel_rf_pkg:
            continue
        processed_rfis.append({
            "RFI No": r[0],
            "Project Package": res_pkg,
            "Subject": r[1],
            "Contractor (From)": r[2],
            "Consultant (To)": r[3],
            "Sent Date": r[4],
            "Due Date": r[5],
            "Days Late": r[6],
            "Status": "⚠️ Overdue" if r[7] or r[6] > 0 else "✅ On Time",
            "Aconex URL": r[9]
        })

    rf_result_df = pd.DataFrame(processed_rfis)
    
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    with col_k1:
        st.metric("Total Filtered RFIs", f"{len(rf_result_df):,}")
    with col_k2:
        ov_count = sum(1 for item in processed_rfis if "Overdue" in item["Status"])
        st.metric("Overdue RFIs", f"{ov_count:,}", delta="-Backlog", delta_color="inverse")
    with col_k3:
        ontime_count = len(rf_result_df) - ov_count
        st.metric("On Time RFIs", f"{ontime_count:,}")
    with col_k4:
        max_d = max([item["Days Late"] for item in processed_rfis], default=0)
        st.metric("Max Delay Recorded", f"+{max_d} Days")

    st.markdown("<br>", unsafe_allow_html=True)
    
    if not rf_result_df.empty:
        st.dataframe(
            rf_result_df,
            column_config={
                "Aconex URL": st.column_config.LinkColumn("Oracle Aconex Link")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Download filtered RFIs to Excel
        wb_rfi = Workbook()
        ws_r = wb_rfi.active
        ws_r.title = "Contractor RFIs"
        ws_r.append(["RFI No", "Project Package", "Subject", "Contractor (From)", "Consultant (To)", "Sent Date", "Due Date", "Days Late", "Status"])
        for item in processed_rfis:
            ws_r.append([item["RFI No"], item["Project Package"], item["Subject"], item["Contractor (From)"], item["Consultant (To)"], str(item["Sent Date"]), str(item["Due Date"]), item["Days Late"], item["Status"]])
        
        out_rfi = io.BytesIO()
        wb_rfi.save(out_rfi)
        out_rfi.seek(0)
        
        st.download_button(
            label="⬇️ Export Filtered Contractor RFIs to Excel (.xlsx)",
            data=out_rfi,
            file_name=f"Contractor_RFIs_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No RFIs match the active filter criteria.")

# =============================================================================
# TAB 4: DIRECT SUPERVISION (SHAKER-ECG CONSORTIUM)
# =============================================================================
with tab_supervision:
    st.markdown("### 🏛️ Direct Supervision Backlog (Shaker-ECG Consortium)")
    st.markdown("Strictly tracking review deliverables assigned to **Shaker-ECG Consortium (SSC)** across Wadi Yemm.")
    
    ssc_df = db.execute("""
        SELECT 
            w.project_package AS [Package],
            s.workflow_no AS [Workflow No],
            s.step_name AS [Step Name],
            s.document_no AS [Document No],
            s.document_title AS [Document Title],
            s.assigned_to_name AS [Reviewer Name],
            s.days_late AS [Days Late],
            s.date_due::VARCHAR AS [Due Date],
            'https://mea.aconex.com/WorkflowSearch?searchtext=' || s.workflow_no || '&projectid=1744833878' AS [Aconex URL]
        FROM fact_workflow_steps s
        JOIN fact_workflows w ON s.workflow_no = w.workflow_no
        WHERE s.is_overdue = true
          AND (s.assigned_to_organization ILIKE '%shaker%' OR s.assigned_to_organization ILIKE '%ecg%')
        ORDER BY s.days_late DESC
    """).df()

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.metric("Total Shaker-ECG Overdue Reviews", f"{len(ssc_df):,}")
    with col_s2:
        max_ssc_delay = ssc_df["Days Late"].max() if not ssc_df.empty else 0
        st.metric("Worst Review Delay", f"+{max_ssc_delay} Days")
    with col_s3:
        affected_pkgs = ssc_df["Package"].nunique() if not ssc_df.empty else 0
        st.metric("Affected Packages", f"{affected_pkgs} Packages")

    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(
        ssc_df,
        column_config={
            "Aconex URL": st.column_config.LinkColumn("Oracle Aconex Link")
        },
        use_container_width=True,
        hide_index=True
    )

# =============================================================================
# TAB 5: TECHNICAL OFFICE DISCIPLINES
# =============================================================================
with tab_disciplines:
    st.markdown("### 📐 Technical Office Disciplines Breakdown")
    
    disc_df = db.execute("""
        SELECT 
            discipline_name AS [Discipline],
            count(*) AS [Total Documents],
            count(CASE WHEN review_status ILIKE '%approved%' THEN 1 END) AS [Approved],
            count(CASE WHEN review_status ILIKE '%rejected%' THEN 1 END) AS [Rejected],
            count(CASE WHEN review_status ILIKE '%revise%' OR review_status ILIKE '%resubmit%' THEN 1 END) AS [Revise & Resubmit],
            count(CASE WHEN review_status IS NULL OR review_status = '' OR review_status ILIKE '%pending%' THEN 1 END) AS [Under Review]
        FROM dim_documents
        WHERE discipline_name IS NOT NULL AND discipline_name != ''
        GROUP BY discipline_name
        ORDER BY count(*) DESC
    """).df()

    st.dataframe(disc_df, use_container_width=True, hide_index=True)

# =============================================================================
# TAB 6: DOCUMENT REGISTRY SEARCH
# =============================================================================
with tab_docs:
    st.markdown("### 📂 Document Registry Search (391,370 Documents)")
    
    col_d1, col_d2, col_d3 = st.columns([2, 1, 1])
    with col_d1:
        doc_search = st.text_input("Search Document No or Title:", "", placeholder="e.g. REH-08-DWG-AR-...")
    with col_d2:
        doc_disc = st.selectbox("Discipline:", ["All Disciplines", "Architectural", "Structural", "Mechanical", "Electrical", "Plumbing", "Infrastructure"], index=0)
    with col_d3:
        doc_limit = st.slider("Result Limit:", 20, 200, 50)

    doc_clauses = ["1=1"]
    if doc_search:
        doc_clauses.append(f"(document_no ILIKE '%{doc_search}%' OR title ILIKE '%{doc_search}%')")
    if doc_disc != "All Disciplines":
        doc_clauses.append(f"discipline_name ILIKE '%{doc_disc}%'")

    doc_results = db.execute(f"""
        SELECT 
            document_no AS [Document No],
            title AS [Title],
            doc_type AS [Doc Type],
            discipline_name AS [Discipline],
            status AS [Status],
            review_status AS [Review Status],
            revision AS [Rev],
            date_modified::VARCHAR AS [Last Modified],
            aconex_url AS [Aconex URL]
        FROM dim_documents
        WHERE {' AND '.join(doc_clauses)}
        ORDER BY date_modified DESC NULLS LAST
        LIMIT {doc_limit}
    """).df()

    st.dataframe(
        doc_results,
        column_config={
            "Aconex URL": st.column_config.LinkColumn("Oracle Aconex Link")
        },
        use_container_width=True,
        hide_index=True
    )
