"""
Central configuration for Delhi Bus Traffic Model & Journey Planner.
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
GTFS_RAW_DIR = RAW_DATA_DIR / "gtfs"
GPS_RAW_DIR = RAW_DATA_DIR / "gps"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
VALIDATION_DATA_DIR = DATA_DIR / "validation"
DOCS_DIR = BASE_DIR / "docs"

# Processed artifacts
SEGMENTS_FILE = PROCESSED_DATA_DIR / "segments.parquet"
STOPS_INDEX_FILE = PROCESSED_DATA_DIR / "stops_index.pkl"
SPEED_PROFILES_FILE = PROCESSED_DATA_DIR / "speed_profiles.parquet"
DWELL_PROFILES_FILE = PROCESSED_DATA_DIR / "dwell_profiles.parquet"

# Delhi Geographic Bounding Box (for GPS outlier filtering)
DELHI_BOUNDS = {
    "lat_min": 28.30,
    "lat_max": 28.95,
    "lon_min": 76.80,
    "lon_max": 77.45,
}

# GPS Quality & Outlier Thresholds
GPS_THRESHOLDS = {
    "max_speed_kmh": 90.0,
    "min_speed_kmh": 0.0,
    "max_time_gap_seconds": 600,  # 10 minutes max gap between consecutive points
}

# Stop Dwell Time Detection
DWELL_CONFIG = {
    "buffer_radius_meters": 35.0,
    "max_dwell_speed_kmh": 3.0,
    "min_dwell_duration_sec": 5.0,
    "max_dwell_duration_sec": 300.0,  # Cap at 5 mins to prevent counting layovers as normal dwell
}

# Walking & Routing Constants
ROUTING_CONFIG = {
    "walking_speed_mps": 1.1,         # ~4 km/h
    "max_first_mile_walk_m": 800.0,   # Max walk to first boarding stop
    "max_last_mile_walk_m": 800.0,    # Max walk from last drop-off stop
    "max_transfer_walk_m": 300.0,     # Max walking distance between transfer stops
    "max_transfers": 2,               # 0, 1, or 2 transfers
    "quiet_hours": [23, 0, 1, 2, 3, 4], # Quiet night hours for traffic delta baseline
    "default_city_speed_kmh": 18.0,   # Average fallback bus speed in Delhi
    "free_flow_city_speed_kmh": 28.0, # Average uncongested bus speed
}

# API Configuration
API_CONFIG = {
    "title": "Delhi Bus Journey Planner & Traffic API",
    "version": "1.0.0",
    "host": "0.0.0.0",
    "port": 8000,
}
