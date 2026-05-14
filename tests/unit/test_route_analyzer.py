"""RouteAnalyzer — pur Python."""
from app.ai.route_analyzer import RouteAnalyzer


def test_analyze_patterns_empty():
    r = RouteAnalyzer.analyze_patterns([], [], [])
    assert r["summary"]["routes_analyzed"] == 0


def test_analyze_patterns_with_stops():
    routes = [{"id": 1, "driver_id": 9}]
    stops = [
        {
            "route_id": 1,
            "stop_order": 1,
            "client_id": 100,
            "latitude": 33.5,
            "longitude": -7.5,
            "planned_arrival": "2026-05-08 08:00:00",
            "planned_departure": "2026-05-08 08:30:00",
            "actual_arrival": "2026-05-08 08:40:00",
            "actual_departure": "2026-05-08 09:00:00",
        },
    ]
    drivers = [{"id": 9, "first_name": "A", "last_name": "B"}]
    r = RouteAnalyzer.analyze_patterns(routes, stops, drivers)
    assert r["summary"]["stops_analyzed"] == 1
    assert len(r["driver_punctuality"]) >= 1
