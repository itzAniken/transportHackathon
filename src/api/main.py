"""
FastAPI Main Application.
Serves:
1. REST API endpoints (/journeys, /stops, /health).
2. Interactive Leaflet Web Interface (/).
3. Swagger / OpenAPI interactive docs (/docs).
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from src.api.routes import router as api_router, initialize_services
from src.config import API_CONFIG, BASE_DIR

app = FastAPI(
    title=API_CONFIG["title"],
    version=API_CONFIG["version"],
    description="Delhi Real-Time Bus Traffic Model & Journey Planner API",
)

# Enable CORS for cross-origin API clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API endpoints
app.include_router(api_router)


@app.on_event("startup")
def startup_event():
    """Initializes GTFS network and traffic speed model on startup."""
    initialize_services()


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    """Serves the interactive Leaflet map dashboard."""
    template_path = BASE_DIR / "src" / "web" / "templates" / "index.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Delhi Bus Journey Planner API</h1><p>Visit <a href='/docs'>/docs</a> for API specification.</p>"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host=API_CONFIG["host"], port=API_CONFIG["port"], reload=True)
