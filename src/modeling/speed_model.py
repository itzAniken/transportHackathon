"""
Time-Varying Speed & Traffic Model.
Estimates stop-to-stop segment travel time and stop dwell time as a function
of route segment, day of week, and hour of day.
Includes hierarchical shrinkage for sparse data and quiet-hour baseline calculations.
"""

from typing import Dict, Tuple, Optional
import math
from datetime import datetime

from src.config import ROUTING_CONFIG, DWELL_CONFIG


class TrafficSpeedModel:
    """
    Hierarchical travel time model combining running speed and stop dwell time.
    """

    def __init__(self):
        # (from_stop, to_stop, route_id, day_type, hour) -> {avg_speed_kmh, sample_count}
        self.segment_speeds: Dict[Tuple[str, str, str, str, int], Dict[str, float]] = {}

        # (route_id, day_type, hour) -> avg_speed_kmh
        self.route_speeds: Dict[Tuple[str, str, int], float] = {}

        # (day_type, hour) -> city_wide_avg_speed_kmh
        self.city_speeds: Dict[Tuple[str, int], float] = {}

        # (stop_id, hour) -> avg_dwell_seconds
        self.stop_dwells: Dict[Tuple[str, int], float] = {}

        # Real-time corridor speed adjustment factors (GTFS-RT fusion)
        self.realtime_factors: Dict[str, float] = {}  # route_id or segment_key -> speed_multiplier

        # Pre-seed realistic Delhi traffic hourly profiles
        self._initialize_delhi_traffic_priors()

    def _initialize_delhi_traffic_priors(self):
        """
        Calibrated Delhi hourly traffic curve reflecting real DTC bus movement patterns:
        - Morning peak (08:00 - 11:00): severe congestion (11 - 13 km/h average)
        - Midday (12:00 - 16:00): moderate traffic (17 - 20 km/h)
        - Evening peak (17:00 - 21:00): highest congestion (9 - 12 km/h)
        - Late night / early morning (22:00 - 05:00): free flow (28 - 34 km/h)
        """
        weekday_hourly_speeds = {
            0: 32.0, 1: 34.0, 2: 35.0, 3: 35.0, 4: 33.0, 5: 30.0,
            6: 25.0, 7: 20.0, 8: 13.5, 9: 11.2, 10: 12.0, 11: 14.5,
            12: 17.0, 13: 18.0, 14: 17.5, 15: 16.5, 16: 15.0, 17: 11.8,
            18: 10.2, 19: 9.8, 20: 12.0, 21: 16.0, 22: 22.0, 23: 27.5
        }

        weekend_hourly_speeds = {
            0: 33.0, 1: 35.0, 2: 35.0, 3: 35.0, 4: 34.0, 5: 31.0,
            6: 27.0, 7: 24.0, 8: 19.0, 9: 16.5, 10: 15.5, 11: 16.0,
            12: 17.5, 13: 18.0, 14: 18.5, 15: 18.0, 16: 16.8, 17: 15.0,
            18: 13.5, 19: 13.0, 20: 14.8, 21: 18.0, 22: 23.0, 23: 28.0
        }

        for h, spd in weekday_hourly_speeds.items():
            self.city_speeds[("weekday", h)] = spd
        for h, spd in weekend_hourly_speeds.items():
            self.city_speeds[("weekend", h)] = spd

    def get_day_type(self, dt: datetime) -> str:
        """Determines 'weekday' (Mon-Fri) or 'weekend' (Sat-Sun)."""
        return "weekend" if dt.weekday() >= 5 else "weekday"

    def estimate_dwell_time_seconds(self, stop_id: str, hour: int) -> float:
        """
        Estimates bus dwell time at a specific stop and hour.
        Major interchange terminals (ISBT, Nehru Place, AIIMS, Connaught Place)
        experience higher passenger boarding dwell.
        """
        if (stop_id, hour) in self.stop_dwells:
            return self.stop_dwells[(stop_id, hour)]

        # Peak vs off-peak baseline dwell
        is_peak = (8 <= hour <= 11) or (17 <= hour <= 21)
        base_dwell = 35.0 if is_peak else 20.0

        # Terminals / major hubs have higher dwell
        major_hubs = ["ST_KG", "ST_NEHRU", "ST_CP", "ST_AIIMS", "ST_ANAND_VIHAR"]
        if any(hub in stop_id for hub in major_hubs):
            base_dwell += (25.0 if is_peak else 15.0)

        # Quiet hours have minimal dwell
        if hour in ROUTING_CONFIG["quiet_hours"]:
            base_dwell = 10.0

        return base_dwell

    def get_effective_speed_kmh(
        self,
        from_stop: str,
        to_stop: str,
        route_id: str,
        dt: datetime,
        use_quiet_hour: bool = False,
    ) -> float:
        """
        Returns estimated running speed in km/h using hierarchical shrinkage fallback:
        Segment Level -> Route Level -> City-Wide Hourly Prior -> Free-Flow Baseline.
        """
        hour = 23 if use_quiet_hour else dt.hour
        day_type = "weekend" if use_quiet_hour else self.get_day_type(dt)
        seg_key = (from_stop, to_stop, route_id, day_type, hour)

        # Level 1: Direct segment observation if sample size >= 5
        if seg_key in self.segment_speeds:
            seg_info = self.segment_speeds[seg_key]
            if seg_info["count"] >= 5:
                speed = seg_info["speed"]
            else:
                # Shrinkage: weighted blend with city speed
                w = seg_info["count"] / 5.0
                city_speed = self.city_speeds.get((day_type, hour), ROUTING_CONFIG["default_city_speed_kmh"])
                speed = (w * seg_info["speed"]) + ((1.0 - w) * city_speed)
        # Level 2: Route-level hourly average
        elif (route_id, day_type, hour) in self.route_speeds:
            speed = self.route_speeds[(route_id, day_type, hour)]
        # Level 3: City-wide hourly profile
        else:
            speed = self.city_speeds.get((day_type, hour), ROUTING_CONFIG["default_city_speed_kmh"])

        # Apply real-time congestion factor if active (and not quiet-hour baseline)
        if not use_quiet_hour and route_id in self.realtime_factors:
            speed *= self.realtime_factors[route_id]

        return max(5.0, min(speed, ROUTING_CONFIG["free_flow_city_speed_kmh"]))

    def estimate_segment_travel_time(
        self,
        from_stop: str,
        to_stop: str,
        route_id: str,
        distance_meters: float,
        dt: datetime,
        use_quiet_hour: bool = False,
    ) -> Dict[str, float]:
        """
        Calculates total segment travel time = running time + boarding dwell time.
        """
        speed_kmh = self.get_effective_speed_kmh(from_stop, to_stop, route_id, dt, use_quiet_hour)
        speed_mps = speed_kmh * 1000.0 / 3600.0

        running_seconds = distance_meters / max(speed_mps, 1.0)
        dwell_seconds = self.estimate_dwell_time_seconds(from_stop, 23 if use_quiet_hour else dt.hour)

        total_seconds = running_seconds + dwell_seconds

        return {
            "total_seconds": round(total_seconds, 1),
            "running_seconds": round(running_seconds, 1),
            "dwell_seconds": round(dwell_seconds, 1),
            "speed_kmh": round(speed_kmh, 1),
        }
