"""
RAPTOR (Round-Based Public Transit Routing) Engine.
Computes Pareto-optimal transit journeys (travel time, transfers, walking)
using time-dependent bus speeds from the TrafficSpeedModel.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import copy

from src.ingest.gtfs_loader import GTFSNetwork, haversine_distance_meters
from src.modeling.speed_model import TrafficSpeedModel
from src.config import ROUTING_CONFIG


class JourneyOption:
    """Represents a complete journey from origin to destination."""

    def __init__(self):
        self.departure_time: Optional[datetime] = None
        self.arrival_time: Optional[datetime] = None
        self.total_duration_seconds: float = 0.0
        self.walking_duration_seconds: float = 0.0
        self.transit_duration_seconds: float = 0.0
        self.traffic_delay_seconds: float = 0.0
        self.quiet_hour_duration_seconds: float = 0.0
        self.transfers_count: int = 0
        self.legs: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "departure_time": self.departure_time.isoformat() if self.departure_time else None,
            "arrival_time": self.arrival_time.isoformat() if self.arrival_time else None,
            "total_duration_minutes": round(self.total_duration_seconds / 60.0, 1),
            "transit_duration_minutes": round(self.transit_duration_seconds / 60.0, 1),
            "walking_duration_minutes": round(self.walking_duration_seconds / 60.0, 1),
            "traffic_delay_minutes": round(self.traffic_delay_seconds / 60.0, 1),
            "quiet_hour_duration_minutes": round(self.quiet_hour_duration_seconds / 60.0, 1),
            "transfers_count": self.transfers_count,
            "legs": self.legs,
        }


class RaptorRouter:
    """
    Round-based transit router customized for dynamic bus traffic.
    """

    def __init__(self, network: GTFSNetwork, speed_model: TrafficSpeedModel):
        self.network = network
        self.speed_model = speed_model

    def plan_journey(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        departure_time: datetime,
        max_transfers: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Executes RAPTOR algorithm and returns ranked list of journey options.
        """
        walk_speed = ROUTING_CONFIG["walking_speed_mps"]
        first_mile_max = ROUTING_CONFIG["max_first_mile_walk_m"]
        last_mile_max = ROUTING_CONFIG["max_last_mile_walk_m"]

        # Step 1: Candidate boarding stops & drop-off stops
        origin_stops = self.network.find_nearby_stops(origin_lat, origin_lon, first_mile_max)
        dest_stops = self.network.find_nearby_stops(dest_lat, dest_lon, last_mile_max)

        if not origin_stops or not dest_stops:
            return []

        dest_stop_ids = {sid: dist for sid, dist in dest_stops}

        # Multi-option container
        found_journeys: List[JourneyOption] = []

        # Round 1: Direct routes (0 transfers)
        # Round 2: 1-transfer routes
        # Explore routes connecting origin stops to dest stops
        for s_orig_id, walk_to_first in origin_stops:
            walk_to_first_sec = walk_to_first / walk_speed
            board_time = departure_time + timedelta(seconds=walk_to_first_sec)

            routes_from_orig = self.network.stop_routes.get(s_orig_id, set())

            # Check direct routes
            for r_id in routes_from_orig:
                stop_seq = self.network.route_stops.get(r_id, [])
                if s_orig_id not in stop_seq:
                    continue

                idx_start = stop_seq.index(s_orig_id)
                for idx_end in range(idx_start + 1, len(stop_seq)):
                    s_dest_candidate = stop_seq[idx_end]
                    if s_dest_candidate in dest_stop_ids:
                        walk_from_last = dest_stop_ids[s_dest_candidate]
                        walk_last_sec = walk_from_last / walk_speed

                        # Simulate transit along this direct route
                        direct_journey = self._build_single_leg_journey(
                            origin_lat, origin_lon,
                            dest_lat, dest_lon,
                            departure_time,
                            s_orig_id, walk_to_first, walk_to_first_sec,
                            s_dest_candidate, walk_from_last, walk_last_sec,
                            r_id, stop_seq[idx_start:idx_end + 1]
                        )
                        found_journeys.append(direct_journey)

            # Check 1-transfer routes (Transfer at an intersecting stop)
            if max_transfers >= 1:
                for r1_id in routes_from_orig:
                    seq1 = self.network.route_stops.get(r1_id, [])
                    if s_orig_id not in seq1:
                        continue
                    idx1_start = seq1.index(s_orig_id)

                    for idx1_trans in range(idx1_start + 1, len(seq1)):
                        s_transfer = seq1[idx1_trans]
                        routes_at_transfer = self.network.stop_routes.get(s_transfer, set())

                        for r2_id in routes_at_transfer:
                            if r2_id == r1_id:
                                continue
                            seq2 = self.network.route_stops.get(r2_id, [])
                            if s_transfer not in seq2:
                                continue
                            idx2_start = seq2.index(s_transfer)

                            for idx2_end in range(idx2_start + 1, len(seq2)):
                                s_dest_candidate = seq2[idx2_end]
                                if s_dest_candidate in dest_stop_ids:
                                    walk_from_last = dest_stop_ids[s_dest_candidate]
                                    walk_last_sec = walk_from_last / walk_speed

                                    transfer_journey = self._build_two_leg_journey(
                                        origin_lat, origin_lon,
                                        dest_lat, dest_lon,
                                        departure_time,
                                        s_orig_id, walk_to_first, walk_to_first_sec,
                                        s_transfer,
                                        s_dest_candidate, walk_from_last, walk_last_sec,
                                        r1_id, seq1[idx1_start:idx1_trans + 1],
                                        r2_id, seq2[idx2_start:idx2_end + 1]
                                    )
                                    found_journeys.append(transfer_journey)

        # Sort journeys by total duration, deduplicate by route combination
        unique_journeys = {}
        for j in found_journeys:
            key = tuple(leg.get("route_id", "walk") for leg in j.legs)
            if key not in unique_journeys or j.total_duration_seconds < unique_journeys[key].total_duration_seconds:
                unique_journeys[key] = j

        ranked = sorted(unique_journeys.values(), key=lambda x: (x.transfers_count, x.total_duration_seconds))
        return [j.to_dict() for j in ranked[:5]]

    def _build_single_leg_journey(
        self,
        orig_lat: float, orig_lon: float,
        dest_lat: float, dest_lon: float,
        dep_time: datetime,
        s_board: str, walk_first_m: float, walk_first_sec: float,
        s_alight: str, walk_last_m: float, walk_last_sec: float,
        route_id: str,
        stops_subset: List[str]
    ) -> JourneyOption:
        journey = JourneyOption()
        journey.departure_time = dep_time
        journey.transfers_count = 0

        # Leg 1: Walk to first stop
        board_stop_info = self.network.stops[s_board]
        legs = [{
            "type": "walk",
            "instruction": f"Walk to {board_stop_info['stop_name']}",
            "distance_meters": round(walk_first_m, 1),
            "duration_seconds": round(walk_first_sec, 1),
            "from_coords": [orig_lat, orig_lon],
            "to_coords": [board_stop_info["stop_lat"], board_stop_info["stop_lon"]],
        }]

        current_time = dep_time + timedelta(seconds=walk_first_sec)
        transit_duration = 0.0
        quiet_transit_duration = 0.0

        # Segment-by-segment transit simulation
        intermediate_stops = []
        for i in range(len(stops_subset) - 1):
            s1 = stops_subset[i]
            s2 = stops_subset[i + 1]
            dist = haversine_distance_meters(
                self.network.stops[s1]["stop_lat"], self.network.stops[s1]["stop_lon"],
                self.network.stops[s2]["stop_lat"], self.network.stops[s2]["stop_lon"]
            )
            est = self.speed_model.estimate_segment_travel_time(s1, s2, route_id, dist, current_time)
            quiet_est = self.speed_model.estimate_segment_travel_time(s1, s2, route_id, dist, current_time, use_quiet_hour=True)

            transit_duration += est["total_seconds"]
            quiet_transit_duration += quiet_est["total_seconds"]
            current_time += timedelta(seconds=est["total_seconds"])

            intermediate_stops.append({
                "stop_id": s2,
                "stop_name": self.network.stops[s2]["stop_name"],
                "arrival_time": current_time.isoformat(),
                "speed_kmh": est["speed_kmh"],
            })

        alight_stop_info = self.network.stops[s_alight]
        route_info = self.network.routes[route_id]

        legs.append({
            "type": "bus",
            "route_id": route_id,
            "route_short_name": route_info["route_short_name"],
            "route_long_name": route_info["route_long_name"],
            "boarding_stop": board_stop_info["stop_name"],
            "alighting_stop": alight_stop_info["stop_name"],
            "duration_seconds": round(transit_duration, 1),
            "quiet_hour_seconds": round(quiet_transit_duration, 1),
            "stops_count": len(stops_subset),
            "intermediate_stops": intermediate_stops,
        })

        # Leg 3: Walk to final destination
        legs.append({
            "type": "walk",
            "instruction": f"Walk from {alight_stop_info['stop_name']} to destination",
            "distance_meters": round(walk_last_m, 1),
            "duration_seconds": round(walk_last_sec, 1),
            "from_coords": [alight_stop_info["stop_lat"], alight_stop_info["stop_lon"]],
            "to_coords": [dest_lat, dest_lon],
        })

        current_time += timedelta(seconds=walk_last_sec)
        journey.arrival_time = current_time
        journey.legs = legs
        journey.walking_duration_seconds = walk_first_sec + walk_last_sec
        journey.transit_duration_seconds = transit_duration
        journey.total_duration_seconds = journey.walking_duration_seconds + journey.transit_duration_seconds
        journey.quiet_hour_duration_seconds = journey.walking_duration_seconds + quiet_transit_duration
        journey.traffic_delay_seconds = max(0.0, journey.total_duration_seconds - journey.quiet_hour_duration_seconds)

        return journey

    def _build_two_leg_journey(
        self,
        orig_lat: float, orig_lon: float,
        dest_lat: float, dest_lon: float,
        dep_time: datetime,
        s_board: str, walk_first_m: float, walk_first_sec: float,
        s_transfer: str,
        s_alight: str, walk_last_m: float, walk_last_sec: float,
        r1_id: str, stops1_subset: List[str],
        r2_id: str, stops2_subset: List[str],
    ) -> JourneyOption:
        journey = JourneyOption()
        journey.departure_time = dep_time
        journey.transfers_count = 1

        board_stop_info = self.network.stops[s_board]
        transfer_stop_info = self.network.stops[s_transfer]
        alight_stop_info = self.network.stops[s_alight]

        legs = [{
            "type": "walk",
            "instruction": f"Walk to {board_stop_info['stop_name']}",
            "distance_meters": round(walk_first_m, 1),
            "duration_seconds": round(walk_first_sec, 1),
            "from_coords": [orig_lat, orig_lon],
            "to_coords": [board_stop_info["stop_lat"], board_stop_info["stop_lon"]],
        }]

        current_time = dep_time + timedelta(seconds=walk_first_sec)
        transit_duration = 0.0
        quiet_transit_duration = 0.0

        # Leg 1: Bus 1
        for i in range(len(stops1_subset) - 1):
            s1 = stops1_subset[i]
            s2 = stops1_subset[i + 1]
            dist = haversine_distance_meters(
                self.network.stops[s1]["stop_lat"], self.network.stops[s1]["stop_lon"],
                self.network.stops[s2]["stop_lat"], self.network.stops[s2]["stop_lon"]
            )
            est = self.speed_model.estimate_segment_travel_time(s1, s2, r1_id, dist, current_time)
            quiet_est = self.speed_model.estimate_segment_travel_time(s1, s2, r1_id, dist, current_time, use_quiet_hour=True)

            transit_duration += est["total_seconds"]
            quiet_transit_duration += quiet_est["total_seconds"]
            current_time += timedelta(seconds=est["total_seconds"])

        r1_info = self.network.routes[r1_id]
        legs.append({
            "type": "bus",
            "route_id": r1_id,
            "route_short_name": r1_info["route_short_name"],
            "route_long_name": r1_info["route_long_name"],
            "boarding_stop": board_stop_info["stop_name"],
            "alighting_stop": transfer_stop_info["stop_name"],
            "duration_seconds": round(transit_duration, 1),
            "quiet_hour_seconds": round(quiet_transit_duration, 1),
            "stops_count": len(stops1_subset),
        })

        # Transfer buffer time (e.g. 3 mins waiting for next bus)
        transfer_wait_sec = 180.0
        current_time += timedelta(seconds=transfer_wait_sec)
        legs.append({
            "type": "transfer",
            "instruction": f"Transfer at {transfer_stop_info['stop_name']} to Route {self.network.routes[r2_id]['route_short_name']}",
            "wait_seconds": transfer_wait_sec,
        })

        # Leg 2: Bus 2
        leg2_transit = 0.0
        leg2_quiet = 0.0
        for i in range(len(stops2_subset) - 1):
            s1 = stops2_subset[i]
            s2 = stops2_subset[i + 1]
            dist = haversine_distance_meters(
                self.network.stops[s1]["stop_lat"], self.network.stops[s1]["stop_lon"],
                self.network.stops[s2]["stop_lat"], self.network.stops[s2]["stop_lon"]
            )
            est = self.speed_model.estimate_segment_travel_time(s1, s2, r2_id, dist, current_time)
            quiet_est = self.speed_model.estimate_segment_travel_time(s1, s2, r2_id, dist, current_time, use_quiet_hour=True)

            leg2_transit += est["total_seconds"]
            leg2_quiet += quiet_est["total_seconds"]
            current_time += timedelta(seconds=est["total_seconds"])

        r2_info = self.network.routes[r2_id]
        legs.append({
            "type": "bus",
            "route_id": r2_id,
            "route_short_name": r2_info["route_short_name"],
            "route_long_name": r2_info["route_long_name"],
            "boarding_stop": transfer_stop_info["stop_name"],
            "alighting_stop": alight_stop_info["stop_name"],
            "duration_seconds": round(leg2_transit, 1),
            "quiet_hour_seconds": round(leg2_quiet, 1),
            "stops_count": len(stops2_subset),
        })

        transit_duration += leg2_transit
        quiet_transit_duration += leg2_quiet

        # Last leg: Walk
        legs.append({
            "type": "walk",
            "instruction": f"Walk from {alight_stop_info['stop_name']} to destination",
            "distance_meters": round(walk_last_m, 1),
            "duration_seconds": round(walk_last_sec, 1),
            "from_coords": [alight_stop_info["stop_lat"], alight_stop_info["stop_lon"]],
            "to_coords": [dest_lat, dest_lon],
        })

        current_time += timedelta(seconds=walk_last_sec)
        journey.arrival_time = current_time
        journey.legs = legs
        journey.walking_duration_seconds = walk_first_sec + walk_last_sec + transfer_wait_sec
        journey.transit_duration_seconds = transit_duration
        journey.total_duration_seconds = journey.walking_duration_seconds + journey.transit_duration_seconds
        journey.quiet_hour_duration_seconds = journey.walking_duration_seconds + quiet_transit_duration
        journey.traffic_delay_seconds = max(0.0, journey.total_duration_seconds - journey.quiet_hour_duration_seconds)

        return journey
