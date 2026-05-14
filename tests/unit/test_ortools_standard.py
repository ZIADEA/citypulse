"""Tests OR-Tools VRPTW standard, reload, objectifs, séquence, déjeuner."""
import pytest
from app.engine.ortools_solver import ortools_vrp, ORTOOLS_AVAILABLE

from tests.unit.ortools_helpers import depot, make_clients, vehicles

pytestmark = pytest.mark.skipif(not ORTOOLS_AVAILABLE, reason="OR-Tools non installé")


class TestStandardVRP:
    def test_standard_mode_explicit(self):
        # Arrange / Act
        result = ortools_vrp(
            make_clients(5), depot(), vehicles(),
            vrp_mode="standard", time_limit_s=5,
        )
        # Assert
        assert isinstance(result, dict)
        assert result.get("vrp_mode") == "standard"

    def test_standard_clients_served_non_negative(self):
        result = ortools_vrp(make_clients(6), depot(), vehicles(), time_limit_s=5)
        assert result.get("clients_served", 0) >= 0


class TestReloadMode:
    def test_reload_mode_tag(self):
        result = ortools_vrp(
            make_clients(6), depot(), vehicles(1, 50),
            vrp_mode="reload", time_limit_s=5,
        )
        assert result["vrp_mode"] == "reload"

    def test_reload_result_structure(self):
        result = ortools_vrp(
            make_clients(8), depot(), vehicles(2, 30),
            vrp_mode="reload", time_limit_s=5,
        )
        for route in result["routes"]:
            assert "reload_count" in route
            assert route["reload_count"] >= 0

    def test_reload_does_not_crash_large(self):
        result = ortools_vrp(
            make_clients(20), depot(), vehicles(3, 60),
            vrp_mode="reload", time_limit_s=8,
        )
        assert isinstance(result, dict)
        assert result.get("clients_total") == 20


class TestMultiObjective:
    def test_distance_only(self):
        result = ortools_vrp(
            make_clients(5), depot(), vehicles(),
            objective_weights={"distance": 1.0, "cost": 0.0, "delays": 0.0, "co2": 0.0},
            time_limit_s=5,
        )
        assert isinstance(result, dict)

    def test_delay_heavy_weight(self):
        result = ortools_vrp(
            make_clients(5), depot(), vehicles(),
            objective_weights={"distance": 0.1, "cost": 0.0, "delays": 5.0, "co2": 0.0},
            time_limit_s=5,
        )
        assert isinstance(result, dict)

    def test_co2_weight(self):
        v_electric = [{
            "capacity_kg": 500, "cost_per_km": 0.2, "co2_per_km": 0.05,
            "registration": "E1", "motorisation": "electrique",
        }]
        result = ortools_vrp(
            make_clients(4), depot(), v_electric,
            objective_weights={"distance": 0.5, "cost": 0.3, "delays": 1.0, "co2": 2.0},
            time_limit_s=5,
        )
        assert result.get("total_co2_kg", 0) >= 0.0


class TestForcedSequence:
    def test_forced_sequence_no_crash(self):
        clients = make_clients(5)
        result = ortools_vrp(
            clients, depot(), vehicles(),
            vrp_mode="standard",
            forced_sequence=[(0, 1), (2, 3)],
            time_limit_s=5,
        )
        assert isinstance(result, dict)

    def test_forced_sequence_out_of_bounds(self):
        result = ortools_vrp(
            make_clients(3), depot(), vehicles(),
            forced_sequence=[(0, 99), (50, 1)],
            time_limit_s=5,
        )
        assert isinstance(result, dict)


class TestLunchBreak:
    def test_custom_lunch_window(self):
        result = ortools_vrp(
            make_clients(5), depot(), vehicles(),
            lunch_window=(660, 780),
            time_limit_s=5,
        )
        assert isinstance(result, dict)

    def test_default_lunch_window(self):
        result = ortools_vrp(make_clients(5), depot(), vehicles(), time_limit_s=5)
        assert isinstance(result, dict)
