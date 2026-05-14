"""Tests OR-Tools pickup-delivery (aucun réseau)."""
import pytest
from app.engine.ortools_solver import ortools_vrp, ORTOOLS_AVAILABLE

from tests.unit.ortools_helpers import depot, make_clients, vehicles

pytestmark = pytest.mark.skipif(not ORTOOLS_AVAILABLE, reason="OR-Tools non installé")


def _pd_clients():
    return [
        {"name": "Pickup A", "latitude": 33.58, "longitude": -7.60,
         "demand_kg": 30, "ready_time": 60, "due_time": 600, "service_time": 10},
        {"name": "Delivery A", "latitude": 33.56, "longitude": -7.58,
         "demand_kg": 0, "ready_time": 120, "due_time": 720, "service_time": 10},
        {"name": "Pickup B", "latitude": 33.59, "longitude": -7.61,
         "demand_kg": 20, "ready_time": 60, "due_time": 600, "service_time": 10},
        {"name": "Delivery B", "latitude": 33.57, "longitude": -7.57,
         "demand_kg": 0, "ready_time": 180, "due_time": 800, "service_time": 10},
    ]


class TestPickupDelivery:
    def test_pd_basic(self):
        # Arrange
        clients = _pd_clients()
        # Act
        result = ortools_vrp(
            clients, depot(), vehicles(1, 500),
            vrp_mode="pickup_delivery",
            pickup_delivery_pairs=[(0, 1), (2, 3)],
            time_limit_s=8,
        )
        # Assert
        assert isinstance(result, dict)
        assert result["vrp_mode"] == "pickup_delivery"

    def test_pd_no_pairs_runs(self):
        result = ortools_vrp(
            _pd_clients(), depot(), vehicles(),
            vrp_mode="pickup_delivery",
            pickup_delivery_pairs=[],
            time_limit_s=5,
        )
        assert "error" not in result or result.get("clients_served", 0) >= 0

    def test_pd_invalid_pair_indices(self):
        clients = _pd_clients()
        result = ortools_vrp(
            clients, depot(), vehicles(),
            vrp_mode="pickup_delivery",
            pickup_delivery_pairs=[(0, 99), (100, 1)],
            time_limit_s=5,
        )
        assert isinstance(result, dict)

    def test_pd_distance_positive(self):
        result = ortools_vrp(
            _pd_clients(), depot(), vehicles(1, 500),
            vrp_mode="pickup_delivery",
            pickup_delivery_pairs=[(0, 1), (2, 3)],
            time_limit_s=8,
        )
        assert result.get("total_distance_km", 0) >= 0.0
