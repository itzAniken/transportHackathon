"""
Integration Test for FastAPI API Endpoints.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.routes import get_journeys, search_stops, health_check, initialize_services


def test_api_integration():
    initialize_services()

    # 1. Health check
    h = health_check()
    assert h["status"] == "healthy"
    assert h["total_stops"] > 0
    print("Health check endpoint OK:", h)

    # 2. Stop search
    stops = search_stops(q="Nehru", limit=5)
    assert len(stops) > 0
    assert "Nehru" in stops[0].stop_name
    print(f"Stop search endpoint OK: Found '{stops[0].stop_name}'")

    # 3. Journeys endpoint with stop names
    journey_res = get_journeys(
        from_loc="Kashmere Gate ISBT",
        to_loc="Nehru Place Bus Terminal",
        depart="2026-10-20T08:30:00"
    )
    assert journey_res.options_count > 0
    best = journey_res.journeys[0]
    print(f"Journeys endpoint OK: {journey_res.origin['name']} -> {journey_res.destination['name']}")
    print(f"  Duration: {best.total_duration_minutes}m, Delay: {best.traffic_delay_minutes}m")

    # 4. Journeys endpoint with GPS coordinates
    journey_res_coords = get_journeys(
        from_loc="28.6665,77.2332",
        to_loc="28.5494,77.2536",
        depart="2026-10-20T13:00:00"
    )
    assert journey_res_coords.options_count > 0
    print(f"Journeys endpoint with coordinates OK: Duration: {journey_res_coords.journeys[0].total_duration_minutes}m")


if __name__ == "__main__":
    test_api_integration()
