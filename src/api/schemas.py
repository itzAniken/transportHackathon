"""
Pydantic API Schemas for Delhi Bus Journey Planner.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class StopResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


class JourneyLeg(BaseModel):
    type: str = Field(..., description="'walk', 'bus', or 'transfer'")
    instruction: Optional[str] = None
    route_id: Optional[str] = None
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    boarding_stop: Optional[str] = None
    alighting_stop: Optional[str] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    quiet_hour_seconds: Optional[float] = None
    stops_count: Optional[int] = None
    from_coords: Optional[List[float]] = None
    to_coords: Optional[List[float]] = None
    intermediate_stops: Optional[List[Dict[str, Any]]] = None


class JourneyOptionSchema(BaseModel):
    departure_time: str
    arrival_time: str
    total_duration_minutes: float
    transit_duration_minutes: float
    walking_duration_minutes: float
    traffic_delay_minutes: float
    quiet_hour_duration_minutes: float
    transfers_count: int
    legs: List[JourneyLeg]


class JourneyResponse(BaseModel):
    origin: Dict[str, Any]
    destination: Dict[str, Any]
    departure_query: str
    traffic_conditions: str
    options_count: int
    journeys: List[JourneyOptionSchema]
