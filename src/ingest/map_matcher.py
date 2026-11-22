"""
Route Map-Matcher & Segment Speed Extractor.
Projects GPS trajectories onto GTFS route stop sequences to calculate:
1. Stop-to-stop segment travel times and running speeds.
2. Dwell times at passenger boarding stops.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from src.ingest.gtfs_loader import GTFSNetwork, haversine_distance_meters
from src.config import DWELL_CONFIG, ROUTING_CONFIG


class RouteMapMatcher:
    """
    Matches bus GPS pings against ordered GTFS route stops.
    """

    def __init__(self, network: GTFSNetwork):
        self.network = network

    def extract_segment_observations(
        self,
        route_id: str,
        cleaned_trajectory: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Extracts segment travel time observations from a vehicle's GPS trace.
        Returns list of observations:
        {
            'from_stop_id': s_from,
            'to_stop_id': s_to,
            'route_id': route_id,
            'timestamp': dt,
            'hour': dt.hour,
            'day_type': 'weekday' | 'weekend',
            'duration_seconds': duration,
            'distance_meters': distance,
            'speed_kmh': speed,
            'dwell_seconds': dwell_time,
        }
        """
        stop_seq = self.network.route_stops.get(route_id, [])
        if len(stop_seq) < 2 or not cleaned_trajectory:
            return []

        # Find closest GPS ping for each stop in sequence
        # Tracking stop passage timestamp and dwell
        stop_passages = {}
        buffer_radius = DWELL_CONFIG["buffer_radius_meters"]

        for stop_id in stop_seq:
            stop_info = self.network.stops.get(stop_id)
            if not stop_info:
                continue

            s_lat = stop_info["stop_lat"]
            s_lon = stop_info["stop_lon"]

            # Find pings within dwell buffer
            pings_in_stop = []
            for ping in cleaned_trajectory:
                dist = haversine_distance_meters(s_lat, s_lon, ping["lat"], ping["lon"])
                if dist <= buffer_radius:
                    pings_in_stop.append((dist, ping))

            if pings_in_stop:
                # Closest ping represents stop passage
                pings_in_stop.sort(key=lambda x: x[0])
                closest_ping = pings_in_stop[0][1]

                # Dwell time estimate = time spent at stop with low speed
                t_min = min(p["timestamp"] for _, p in pings_in_stop)
                t_max = max(p["timestamp"] for _, p in pings_in_stop)
                dwell = min(DWELL_CONFIG["max_dwell_duration_sec"], max(0.0, float(t_max - t_min)))

                stop_passages[stop_id] = {
                    "timestamp": closest_ping["timestamp"],
                    "dwell_seconds": dwell,
                }

        # Calculate consecutive segment traversal times
        observations = []
        for i in range(len(stop_seq) - 1):
            s_from = stop_seq[i]
            s_to = stop_seq[i + 1]

            if s_from in stop_passages and s_to in stop_passages:
                t1 = stop_passages[s_from]["timestamp"]
                t2 = stop_passages[s_to]["timestamp"]

                # Monotonic forward progress
                if t2 > t1:
                    duration = float(t2 - t1)
                    dist = haversine_distance_meters(
                        self.network.stops[s_from]["stop_lat"],
                        self.network.stops[s_from]["stop_lon"],
                        self.network.stops[s_to]["stop_lat"],
                        self.network.stops[s_to]["stop_lon"],
                    )

                    # Plausible duration (speed between 3 km/h and 80 km/h)
                    speed_mps = dist / max(duration, 1.0)
                    speed_kmh = speed_mps * 3.6

                    if 3.0 <= speed_kmh <= 80.0:
                        dt = datetime.fromtimestamp(t1)
                        day_type = "weekend" if dt.weekday() >= 5 else "weekday"

                        observations.append({
                            "from_stop_id": s_from,
                            "to_stop_id": s_to,
                            "route_id": route_id,
                            "timestamp": t1,
                            "hour": dt.hour,
                            "day_type": day_type,
                            "duration_seconds": duration,
                            "distance_meters": dist,
                            "speed_kmh": round(speed_kmh, 1),
                            "dwell_seconds": stop_passages[s_from]["dwell_seconds"],
                        })

        return observations
