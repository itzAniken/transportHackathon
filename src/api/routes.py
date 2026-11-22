"""
FastAPI Route Handlers for Delhi Bus Journey Planner API.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone
import dateutil.parser

from src.api.schemas import JourneyResponse, StopResponse
from src.ingest.gtfs_loader import GTFSNetwork
from src.modeling.speed_model import TrafficSpeedModel
from src.routing.raptor import RaptorRouter

router = APIRouter()

# Global instances initialized on app startup
network: Optional[GTFSNetwork] = None
speed_model: Optional[TrafficSpeedModel] = None
router_engine: Optional[RaptorRouter] = None


def initialize_services():
    global network, speed_model, router_engine
    network = GTFSNetwork()
    # Try loading from disk, otherwise load high-fidelity representative Delhi network
    loaded = network.load_from_directory()
    if not loaded:
        network.populate_delhi_sample_network()

    speed_model = TrafficSpeedModel()
    router_engine = RaptorRouter(network, speed_model)


def parse_location(loc_str: str) -> dict:
    """
    Parses a location string that could be:
    1. 'lat,lon' coordinates (e.g. '28.6665,77.2332')
    2. A stop name or stop ID (e.g. 'Kashmere Gate ISBT')
    """
    loc_str = loc_str.strip()
    # Try lat,lon
    if "," in loc_str:
        parts = loc_str.split(",")
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return {
                "name": f"Coordinates ({lat:.4f}, {lon:.4f})",
                "lat": lat,
                "lon": lon,
            }
        except ValueError:
            pass

    # Search for stop name
    results = network.search_stops(loc_str, limit=1)
    if results:
        top = results[0]
        return {
            "name": top["stop_name"],
            "lat": top["stop_lat"],
            "lon": top["stop_lon"],
            "stop_id": top["stop_id"],
        }

    raise HTTPException(
        status_code=400,
        detail=f"Location '{loc_str}' could not be resolved to coordinates or a recognized stop."
    )


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Delhi Bus Real-Time Traffic & Journey Planner API",
        "total_stops": len(network.stops) if network else 0,
        "total_routes": len(network.routes) if network else 0,
        "total_segments": len(network.segments) if network else 0,
    }


@router.get("/stops", response_model=List[StopResponse])
def search_stops(
    q: str = Query("", description="Search term for stop name or ID"),
    limit: int = Query(10, ge=1, le=50)
):
    """Returns matching bus stops for autocomplete."""
    if not q:
        # Return first N stops
        sample = list(network.stops.values())[:limit]
        return [StopResponse(**s) for s in sample]

    matches = network.search_stops(q, limit=limit)
    return [StopResponse(**s) for s in matches]


@router.get("/journeys", response_model=JourneyResponse)
def get_journeys(
    from_loc: str = Query(..., alias="from", description="Origin coordinates ('lat,lon') or stop name"),
    to_loc: str = Query(..., alias="to", description="Destination coordinates ('lat,lon') or stop name"),
    depart: Optional[str] = Query(None, description="Departure time (ISO format or 'now'). Defaults to current time."),
):
    """
    Plans transit journeys between origin and destination with traffic-informed travel times.
    """
    if not network or not router_engine:
        initialize_services()

    # Parse locations
    orig = parse_location(from_loc)
    dest = parse_location(to_loc)

    # Parse departure time
    if not depart or depart.lower() == "now":
        dep_time = datetime.now()
    else:
        try:
            dep_time = dateutil.parser.isoparse(depart)
        except Exception:
            try:
                # Support standard date-time string formats
                dep_time = datetime.fromisoformat(depart.replace("Z", "+00:00"))
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid departure time format '{depart}'. Use ISO-8601 (e.g. '2026-10-20T08:30:00')."
                )

    journeys = router_engine.plan_journey(
        origin_lat=orig["lat"],
        origin_lon=orig["lon"],
        dest_lat=dest["lat"],
        dest_lon=dest["lon"],
        departure_time=dep_time,
    )

    if not journeys:
        raise HTTPException(
            status_code=404,
            detail="No feasible bus journeys found between the requested locations within walking limits."
        )

    hour = dep_time.hour
    traffic_cond = "Heavy Peak Traffic" if (8 <= hour <= 11 or 17 <= hour <= 21) else (
        "Free Flow / Quiet Hours" if hour in [23, 0, 1, 2, 3, 4] else "Moderate Traffic"
    )

    return JourneyResponse(
        origin=orig,
        destination=dest,
        departure_query=dep_time.isoformat(),
        traffic_conditions=traffic_cond,
        options_count=len(journeys),
        journeys=journeys,
    )
