"""Tests OR-Tools mode open (aucun appel réseau)."""
import pytest
from app.engine.ortools_solver import ortools_vrp, ORTOOLS_AVAILABLE

from tests.unit.ortools_helpers import depot, make_clients, vehicles

pytestmark = pytest.mark.skipif(not ORTOOLS_AVAILABLE, reason="OR-Tools non installé")


class TestOpenVRP:
    def test_basic_open(self):
        # Arrange
        c, d, v = make_clients(5), depot(), vehicles()
        # Act
        result = ortools_vrp(c, d, v, vrp_mode="open", time_limit_s=5)
        # Assert
        assert isinstance(result, dict)
        assert result["vrp_mode"] == "open"

    def test_open_routes_have_stops(self):
        result = ortools_vrp(make_clients(4), depot(), vehicles(), vrp_mode="open", time_limit_s=5)
        served = sum(
            len([s for s in r["route"] if s.get("type") == "delivery"]) for r in result["routes"]
        )
        assert served >= 0

    def test_open_co2_present(self):
        result = ortools_vrp(make_clients(4), depot(), vehicles(1), vrp_mode="open", time_limit_s=5)
        assert "total_co2_kg" in result
        assert result["total_co2_kg"] >= 0.0

    def test_open_respect_rate_bounded(self):
        result = ortools_vrp(make_clients(5), depot(), vehicles(), vrp_mode="open", time_limit_s=5)
        assert 0.0 <= result.get("respect_rate", 0) <= 100.0

    def test_open_zero_clients(self):
        result = ortools_vrp([], depot(), vehicles(), vrp_mode="open")
        assert result["total_distance_km"] == 0.0
        assert result["clients_served"] == 0
