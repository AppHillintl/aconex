# Ras El Hekma Project Controls & Executive Backlog Dispatch Hub

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
**Client:** Modon Properties  
**Project Management Consultant (PMC):** Hill International, Inc.  
**Program:** Ras El Hekma Master Development Program

---

## 🏗️ Platform Overview

An executive project controls platform built for real-time monitoring and backlog dispatch of all project deliverables, workflows, correspondence, and technical requests across **Ras El Hekma (REH)** packages.

### 🌟 Key Capabilities
- **20 Comprehensive Packages**: Tracking DP01–DP07, Infrastructure, Grand Canal, West Canal, Airport, RO Plant, STP, Substation, Ring Road, and South Golf.
- **5-Tier Canonical Resolution**: Multi-tiered contract mapping classifying every RFI, Mail, and Workflow into its exact package with 99.6% precision.
- **Contractor RFIs Tracker**: 12,465+ RFIs with SLA tracking and strict separation between ECG (Design Consultant) and Shaker-ECG Consortium (Supervision Consultant - SSC).
- **Direct Supervision Backlog**: Dedicated monitoring of Shaker-ECG consortium review workflows.
- **Automated Dispatch**: Instant generation of executive Excel registers (.xlsx) and official Outlook-compatible email reminder drafts with automated TO/CC recipient matrices.
- **Dual Architecture**: Native FastAPI + Tailwind web portal AND cloud-ready Streamlit application.

---

## 🚀 Instant Deployment on Streamlit Cloud (share.streamlit.io)

1. **Push to GitHub**:
   - Open **GitHub Desktop**.
   - Add this repository (`File` -> `Add Local Repository` -> Select `ACONEX` folder).
   - Click **Publish repository** to push it to your GitHub account (make it Public or Private).

2. **Deploy on Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io) and log in with your GitHub account.
   - Click **New app**.
   - Select your repository: `your-username/ACONEX`.
   - Main file path: `streamlit_app.py`.
   - Click **Deploy!**

Your executive dashboard will be live online on a public or private URL within 2 minutes!

---

## 💻 Local Execution

### Option A: Run Streamlit Cloud Version
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Option B: Run Full FastAPI + Single Page Web Portal
```bash
pip install fastapi uvicorn duckdb openpyxl pydantic
python platform/backend/main.py
```
Then navigate to: `http://localhost:8000`
