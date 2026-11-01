import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Paths
DATA_DIR = BASE_DIR.parent.parent / "Data"
OUTPUT_DIR = DATA_DIR / "update" / "Up"
SCRATCH_DIR = DATA_DIR / "update" / "scratch"
PROFILE_DIR = BASE_DIR / "browser_profile"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Aconex Instance Config
ACONEX_BASE_URL = "https://mea.aconex.com"
PROJECT_ID = "1744833878"

# Credentials
ACONEX_USERNAME = os.getenv("ACONEX_USERNAME", "mohamedmeneaem@hillintl.com")
ACONEX_PASSWORD = os.getenv("ACONEX_PASSWORD", "")

# Standard URLs
URL_LOGIN = f"{ACONEX_BASE_URL}/"
URL_DOCUMENTS = f"{ACONEX_BASE_URL}/authentication/index.html?Action=View&MENU_TARGET=DOC-SEARCH&ENTITY=PROJECT&ID={PROJECT_ID}"
URL_MAILS = f"{ACONEX_BASE_URL}/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID={PROJECT_ID}"
URL_WORKFLOWS = f"{ACONEX_BASE_URL}/WorkflowSearch?projectid={PROJECT_ID}"

# Python Executable for Batches
PYTHON_EXE = r"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe"
