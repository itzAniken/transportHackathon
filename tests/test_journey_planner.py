"""
Unit & Integration Tests for Delhi Bus Journey Planner.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from src.ingest.gtfs_loader import GTFSNetwork
from src.modeling.speed_model import TrafficSpeedModel
from src.routing.raptor import RaptorRouter


def test_network_initialization():
    net = GTFSNetwork()
    net.populate_delhi_sample_network()

    assert len(net.stops) >= 15
    assert len(net.routes) >= 5
    assert len(net.segments) >= 15
    print("Network initialization test passed.")


def test_peak_vs_quiet_hour_difference():
    net = GTFSNetwork()
    net.populate_delhi_sample_network()

    model = TrafficSpeedModel()
    router = RaptorRouter(net, model)

    kg_stop = net.stops["ST_KG"]
    nehru_stop = net.stops["ST_NEHRU"]

    # 1. Tuesday Morning Peak (8:30 AM)
    peak_time = datetime(2026, 10, 20, 8, 30)
    peak_results = router.plan_journey(
        origin_lat=kg_stop["stop_lat"],
        origin_lon=kg_stop["stop_lon"],
        dest_lat=nehru_stop["stop_lat"],
        dest_lon=nehru_stop["stop_lon"],
        departure_time=peak_time,
    )
    assert len(peak_results) > 0
    peak_duration = peak_results[0]["total_duration_minutes"]

    # 2. Tuesday Late Night Quiet Hour (11:00 PM)
    quiet_time = datetime(2026, 10, 20, 23, 0)
    quiet_results = router.plan_journey(
        origin_lat=kg_stop["stop_lat"],
        origin_lon=kg_stop["stop_lon"],
        dest_lat=nehru_stop["stop_lat"],
        dest_lon=nehru_stop["stop_lon"],
        departure_time=quiet_time,
    )
    assert len(quiet_results) > 0
    quiet_duration = quiet_results[0]["total_duration_minutes"]

    print(f"Kashmere Gate -> Nehru Place:")
    print(f"  Peak Hour (8:30 AM): {peak_duration} mins")
    print(f"  Quiet Hour (11:00 PM): {quiet_duration} mins")
    print(f"  Traffic Delay: {peak_results[0]['traffic_delay_minutes']} mins")

    # The peak hour trip MUST take longer than quiet hour
    assert peak_duration > quiet_duration
    assert peak_results[0]["traffic_delay_minutes"] > 0
    print("Peak vs Quiet Hour traffic sensitivity test passed!")


if __name__ == "__main__":
    test_network_initialization()
    test_peak_vs_quiet_hour_difference()
