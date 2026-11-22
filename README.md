# Delhi Real-Time Bus Traffic Model & Journey Planner
### Transport Stack Hackathon 2026 — Problem 1 / Phase 1

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-199900.svg)](https://leafletjs.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent, time-dependent transit journey planner for Delhi NCR that models bus travel times from real-world GPS movements and GTFS data rather than relying on static timetables.

---

## 🌟 Key Features

- **Dynamic Speed Modeling**: Predicts travel times as a function of route segment, day of week, and hour of day.
- **Dwell Time Separation**: Decomposes trip duration into link running speed and passenger boarding dwell times at stops.
- **Hierarchical Shrinkage**: Gracefully falls back across Segment $\rightarrow$ Route $\rightarrow$ City-Wide Hourly $\rightarrow$ Timetable levels to handle sparse data.
- **RAPTOR Transit Routing**: Round-based transit routing engine supporting multi-modal walking, direct routes, and transfers.
- **Quiet-Hour Baseline & Traffic Penalty**: Automatically calculates the same journey at uncongested hours (11:00 PM) to show commuters the exact traffic penalty.
- **Interactive Web Interface**: Single-page Leaflet.js dashboard with interactive pin-dropping, stop autocomplete, and live corridor speed visualizations.
- **Documented REST API**: Production-grade FastAPI endpoints with OpenAPI Swagger documentation.

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Setup Environment
```bash
git clone <repo-url>
cd transportHackathon

# Install dependencies
python -m pip install -r requirements.txt
```

### 3. Launch the Server
```bash
python run.py
```

The system will start locally on port 8000:
- **Interactive Web Client:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🌐 API Reference

### `GET /journeys`
Plans transit journeys between origin and destination with traffic-informed travel times.

**Query Parameters:**
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `from` | string | **Yes** | Origin coordinates or stop name | `Kashmere Gate ISBT` or `28.6665,77.2332` |
| `to` | string | **Yes** | Destination coordinates or stop name | `Nehru Place Bus Terminal` or `28.5494,77.2536` |
| `depart` | string | No | Departure time (ISO 8601 or `now`) | `2026-10-20T08:30:00` |

**Sample Request:**
```bash
curl -X GET "http://localhost:8000/journeys?from=Kashmere%20Gate%20ISBT&to=Nehru%20Place%20Bus%20Terminal&depart=2026-10-20T08:30:00"
```

**Sample JSON Response:**
```json
{
  "origin": {
    "name": "Kashmere Gate ISBT",
    "lat": 28.6665,
    "lon": 77.2332,
    "stop_id": "ST_KG"
  },
  "destination": {
    "name": "Nehru Place Bus Terminal",
    "lat": 28.5494,
    "lon": 77.2536,
    "stop_id": "ST_NEHRU"
  },
  "departure_query": "2026-10-20T08:30:00",
  "traffic_conditions": "Heavy Peak Traffic",
  "options_count": 2,
  "journeys": [
    {
      "departure_time": "2026-10-20T08:30:00",
      "arrival_time": "2026-10-20T09:41:36",
      "total_duration_minutes": 71.6,
      "transit_duration_minutes": 71.6,
      "walking_duration_minutes": 0.0,
      "traffic_delay_minutes": 39.5,
      "quiet_hour_duration_minutes": 32.6,
      "transfers_count": 0,
      "legs": [
        {
          "type": "bus",
          "route_id": "R_429",
          "route_short_name": "429",
          "route_long_name": "Kashmere Gate ISBT - Nehru Place via Ring Road",
          "boarding_stop": "Kashmere Gate ISBT",
          "alighting_stop": "Nehru Place Bus Terminal",
          "duration_seconds": 4296.0,
          "quiet_hour_seconds": 1956.0,
          "stops_count": 7
        }
      ]
    }
  ]
}
```

### `GET /stops`
Fuzzy autocomplete for bus stop names and geographic coordinates.

```bash
curl -X GET "http://localhost:8000/stops?q=Nehru"
```

---

## 📊 Benchmarking & Accuracy Validation

To run the automated validation suite against Google Maps Transit benchmarks and Static Timetables:

```bash
python data/validation/benchmark_suite.py
```

### Benchmark Summary (vs Google Maps)

| Metric | Static GTFS Timetable | Our Dynamic Traffic Model |
| :--- | :--- | :--- |
| **Mean Absolute Error (MAE)** | **16.00 minutes** | **3.11 minutes** |
| **Accuracy Improvement** | Baseline | **+80.6% improvement** |

Detailed report available in [`docs/validation_report.md`](docs/validation_report.md).

---

## 🔬 Technical Documentation

For the complete architectural design, map-matching methodology, Kalman filter live-fusion, and handling of noisy/sparse GPS data, see:
👉 [`docs/technical_note.md`](docs/technical_note.md)

---

## 📂 Project Organization

```text
├── data/
│   ├── raw/                   # Raw GTFS and daily SQLite GPS databases
│   ├── processed/             # Precomputed speed profiles & spatial indexes
│   └── validation/            # Validation benchmark runner & CSV outputs
├── src/
│   ├── config.py              # Central configuration & thresholds
│   ├── ingest/                # GTFS loader, GPS cleaner, map-matching
│   ├── modeling/              # Hourly traffic speed model, dwell extraction
│   ├── routing/               # RAPTOR transit router & walking legs
│   ├── api/                   # FastAPI route handlers & Pydantic schemas
│   └── web/                   # Interactive Leaflet.js dashboard
├── docs/
│   ├── technical_note.md      # Comprehensive methodology note
│   └── validation_report.md   # Accuracy report vs Google Maps
├── tests/                     # Automated unit and integration tests
├── requirements.txt           # Project dependencies
└── run.py                     # One-click execution entrypoint
```
