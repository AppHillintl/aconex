"""
=============================================================================
HILL INTERNATIONAL CORPORATE AUTHENTICATION & DIRECTORY WHITELIST GATE
Restricts platform access exclusively to authorized Hill International staff
whose official @hillintl.com emails exist in the Aconex Project Directory.
=============================================================================
"""

import streamlit as st
import duckdb
from typing import Dict, Any, Optional

DEFAULT_PASSCODE = "HILL-REH-2026"


@st.cache_data(ttl=3600)
def load_hill_directory_whitelist(db_path: str = "aconex_cloud.duckdb") -> Dict[str, Dict[str, str]]:
    """Loads all verified Hill International personnel from dim_user_directory."""
    import os
    if not os.path.exists(db_path) and os.path.exists("aconex.duckdb"):
        db_path = "aconex.duckdb"
    
    whitelist = {}
    try:
        con = duckdb.connect(db_path, read_only=True)
        rows = con.execute("""
            SELECT 
                LOWER(TRIM(email)) AS email,
                user_name,
                COALESCE(position, 'Hill International Team Member') AS position,
                organization_name
            FROM dim_user_directory
            WHERE (organization_name ILIKE '%Hill%' OR email ILIKE '%@hillintl.com%')
              AND email IS NOT NULL AND email != ''
            ORDER BY user_name
        """).fetchall()
        for r in rows:
            em = r[0]
            whitelist[em] = {
                "name": r[1] or em.split('@')[0].capitalize(),
                "position": r[2] or "Project Controls Team",
                "org": r[3] or "Hill International"
            }
        con.close()
    except Exception as e:
        # Fallback security list if db is busy
        whitelist["mohamedmeneaem@hillintl.com"] = {
            "name": "Mohamed Meneaem",
            "position": "Project Controls Lead",
            "org": "Hill International"
        }
    return whitelist


def render_hill_login_gate(db_path: str = "aconex_cloud.duckdb") -> bool:
    """
    Renders the Hill International Enterprise Authentication Gate.
    Returns True if session is authenticated, False otherwise.
    """
    if st.session_state.get("authenticated", False):
        # Render User Badge & Sign Out in Sidebar
        with st.sidebar:
            st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.1); border: 1px solid rgba(14, 165, 233, 0.25); border-radius: 12px; padding: 12px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 32px; height: 32px; border-radius: 50%; background: #0ea5e9; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px;">
                        {st.session_state.get('user_name', 'H')[:1]}
                    </div>
                    <div>
                        <div style="font-size: 12px; font-weight: 700; color: #f8fafc; line-height: 1.2;">
                            {st.session_state.get('user_name', 'Authorized User')}
                        </div>
                        <div style="font-size: 10px; color: #94a3b8; line-height: 1.2; margin-top: 2px;">
                            {st.session_state.get('user_position', 'Hill International')}
                        </div>
                    </div>
                </div>
                <div style="margin-top: 8px; font-size: 10px; font-family: monospace; color: #38bdf8; word-break: break-all;">
                    {st.session_state.get('user_email', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🚪 Sign Out", use_container_width=True, key="btn_sign_out"):
                for k in ["authenticated", "user_email", "user_name", "user_position"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()
        return True

    # User is not authenticated -> Render Login Gate
    whitelist = load_hill_directory_whitelist(db_path)
    required_key = None
    try:
        required_key = st.secrets.get("PROJECT_ACCESS_KEY", DEFAULT_PASSCODE)
    except Exception:
        required_key = DEFAULT_PASSCODE

    col_l, col_center, col_r = st.columns([1, 2, 1])
    with col_center:
        st.markdown("""
        <div style="text-align: center; margin-top: 40px; margin-bottom: 24px;">
            <div style="display: inline-block; padding: 8px 16px; border-radius: 9999px; background: rgba(14, 165, 233, 0.15); border: 1px solid rgba(14, 165, 233, 0.3); font-size: 12px; font-weight: 700; color: #38bdf8; margin-bottom: 16px;">
                🔒 Ras El Hekma Project Controls • Restricted Access
            </div>
            <h1 style="font-size: 1.8rem; font-weight: 800; color: #ffffff; margin-bottom: 8px;">
                Hill International Corporate Portal
            </h1>
            <p style="font-size: 0.85rem; color: #94a3b8; line-height: 1.5;">
                This dashboard contains confidential project controls and contractual records.<br>
                Access is restricted strictly to verified <strong>Hill International Inc.</strong> personnel.
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown("""
            <style>
                .login-card {
                    background: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 16px;
                    padding: 24px;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
                }
            </style>
            """, unsafe_allow_html=True)

            with st.form("hill_login_form"):
                email_input = st.text_input(
                    "Corporate Email Address (@hillintl.com):",
                    placeholder="e.g. mohamedmeneaem@hillintl.com",
                    help="Enter your official Hill International email address as registered in Oracle Aconex Directory"
                ).strip().lower()

                passcode_input = st.text_input(
                    "Project Access Passcode:",
                    type="password",
                    placeholder="Enter project authorization key",
                    help="Contact Project Controls Lead if you need the project key"
                ).strip()

                submit = st.form_submit_button(
                    "🔐 Authenticate & Enter Dashboard",
                    use_container_width=True
                )

                if submit:
                    if not email_input:
                        st.error("⚠️ Please enter your corporate email address.")
                    elif not email_input.endswith("@hillintl.com"):
                        st.error("🚫 Access Denied: Only corporate email addresses ending with '@hillintl.com' are permitted.")
                    elif email_input not in whitelist:
                        st.error(f"🚫 Unauthorized User: The email '{email_input}' is not registered in the Ras El Hekma Project Directory. Please contact Mohamed Meneaem (Project Controls Lead).")
                    elif passcode_input != required_key:
                        st.error("🔑 Invalid Project Access Passcode. Please check with your Project Controls Administrator.")
                    else:
                        user_info = whitelist[email_input]
                        st.session_state["authenticated"] = True
                        st.session_state["user_email"] = email_input
                        st.session_state["user_name"] = user_info["name"]
                        st.session_state["user_position"] = user_info["position"]
                        st.success(f"✅ Verified: Welcome Eng. {user_info['name']} ({user_info['position']})!")
                        st.rerun()

        st.markdown(f"""
        <div style="text-align: center; margin-top: 24px; font-size: 11px; color: #64748b;">
            Client: <strong>MODON Properties</strong> • PMC: <strong>Hill International, Inc.</strong><br>
            Verified Personnel Whitelist: <strong>{len(whitelist):,} Active Engineers & Managers</strong><br>
            Oracle Aconex Instance: <strong>Ras El Hekma (Project 1744833878)</strong>
        </div>
        """, unsafe_allow_html=True)

    return False
