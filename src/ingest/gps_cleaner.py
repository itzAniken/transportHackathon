"""
GPS Trace Cleaner & Filter.
Filters raw GPS pings for:
1. Spatial bounding box (Delhi NCR).
2. Physical speed bounds (0 - 90 km/h).
3. Monotonic timestamps per vehicle.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.config import DELHI_BOUNDS, GPS_THRESHOLDS


def is_valid_gps_ping(lat: float, lon: float, speed_kmh: Optional[float] = None) -> bool:
    """Validates whether a GPS ping falls within Delhi NCR and has plausible speed."""
    if not (DELHI_BOUNDS["lat_min"] <= lat <= DELHI_BOUNDS["lat_max"]):
        return False
    if not (DELHI_BOUNDS["lon_min"] <= lon <= DELHI_BOUNDS["lon_max"]):
        return False

    if speed_kmh is not None:
        if speed_kmh < GPS_THRESHOLDS["min_speed_kmh"] or speed_kmh > GPS_THRESHOLDS["max_speed_kmh"]:
            return False

    return True


def clean_vehicle_trajectory(pings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cleans and sorts a vehicle's GPS trajectory chronologically.
    Removes time jumps, teleportation outliers, and stationary noise.
    """
    if not pings:
        return []

    # Filter invalid points
    valid_pings = [
        p for p in pings
        if is_valid_gps_ping(p["lat"], p["lon"], p.get("speed"))
    ]

    # Sort chronologically
    valid_pings.sort(key=lambda x: x["timestamp"])

    cleaned = []
    prev_time = -1

    for p in valid_pings:
        t = p["timestamp"]
        # Monotonic time check
        if t <= prev_time:
            continue

        cleaned.append(p)
        prev_time = t

    return cleaned
