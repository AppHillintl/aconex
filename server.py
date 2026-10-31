import os
import sys
from pathlib import Path

# Add backend and etl modules to sys.path so all imports resolve seamlessly
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "platform" / "backend"))
sys.path.insert(0, str(ROOT_DIR / "platform" / "etl"))

import main as backend_main

# Expose FastAPI app for uvicorn
app = backend_main.app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
