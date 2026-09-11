#!/usr/bin/env python3
"""
CLI Launcher for SWARMRoute Dashboard Backend Server.
Runs FastAPI backend on port 8000.
"""
import sys
from pathlib import Path

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import uvicorn

if __name__ == "__main__":
    print("================================================================================")
    print("           SWARMRoute Live Simulation Backend Server (Port 8000)                ")
    print("================================================================================")
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
