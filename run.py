"""
Entry point to run the Delhi Bus Traffic Model & Journey Planner service.
Usage:
    python run.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from src.config import API_CONFIG

if __name__ == "__main__":
    print(f"Starting Delhi Bus Journey Planner on http://localhost:{API_CONFIG['port']}")
    print(f"Interactive Web UI: http://localhost:{API_CONFIG['port']}/")
    print(f"Interactive API Docs: http://localhost:{API_CONFIG['port']}/docs")
    uvicorn.run("src.api.main:app", host=API_CONFIG["host"], port=API_CONFIG["port"], reload=False)
