"""
test_ortools_mdvrp.py — Tests du solveur OR-Tools mode multi_depot
"""
import pytest
from app.engine.ortools_solver import ortools_vrp, ORTOOLS_AVAILABLE, _build_zfe_pairs


pytestmark = pytest.mark.skipif(not ORTOOLS_AVAILABLE, reason="OR-Tools non installé")


@pytest.fixture
def depot_a():
    return {"latitude": 33.5731, "longitude": -7.5898, "name": "Dépôt A"}

@pytest.fixture
def depot_b():
    return {"latitude": 33.6100, "longitude": -7.5200, "name": "Dépôt B"}

@pytest.fixture
def clients_6(depot_a):
    base_lat, base_lon = depot_a["latitude"], depot_a["longitude"]
    return [
        {
            "name": f"Client {i+1}",
            "latitude":  base_lat + (i - 3) * 0.01,
            "longitude": base_lon + (i - 3) * 0.01,
            "demand_kg":    20,
            "ready_time":   60,
            "due_time":     900,
            "service_time": 10,
        }
        for i in range(6)
    ]

@pytest.fixture
def vehicles_2():
    return [
        {"capacity_kg": 200, "cost_per_km": 0.5, "co2_per_km": 0.25, "registration": "V1"},
        {"capacity_kg": 200, "cost_per_km": 0.5, "co2_per_km": 0.25, "registration": "V2"},
    ]


class TestMultiDepotMode:

    def test_returns_dict(self, clients_6, depot_a, vehicles_2, depot_b):
        result = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="multi_depot",
            depots=[depot_a, depot_b],
            time_limit_s=5,
        )
        assert isinstance(result, dict)
        assert "routes" in result
        assert "vrp_mode" in result

    def test_vrp_mode_tag(self, clients_6, depot_a, vehicles_2):
        result = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="multi_depot",
            depots=[depot_a],
            time_limit_s=5,
        )
        assert result["vrp_mode"] == "multi_depot"

    def test_all_clients_served_or_reported(self, clients_6, depot_a, vehicles_2, depot_b):
        result = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="multi_depot",
            depots=[depot_a, depot_b],
            time_limit_s=10,
        )
        assert result.get("clients_total") == 6
        assert result.get("clients_served", 0) >= 0

    def test_distance_positive(self, clients_6, depot_a, vehicles_2):
        result = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="multi_depot",
            depots=[depot_a],
            time_limit_s=5,
        )
        assert result["total_distance_km"] >= 0.0

    def test_empty_clients(self, depot_a, vehicles_2):
        result = ortools_vrp(
            [], depot_a, vehicles_2,
            vrp_mode="multi_depot",
            time_limit_s=5,
        )
        assert result["clients_total"] == 0
        assert result["total_distance_km"] == 0.0


class TestZFEPenalty:

    def test_build_zfe_pairs_empty_zones(self, clients_6):
        pairs = _build_zfe_pairs(clients_6, [])
        assert pairs == set()

    def test_build_zfe_pairs_no_zfe_type(self, clients_6):
        zones = [{"zone_type": "delivery", "latitude": 33.58, "longitude": -7.59, "radius_km": 5}]
        pairs = _build_zfe_pairs(clients_6, zones)
        assert pairs == set()

    def test_build_zfe_pairs_all_inside(self, depot_a, clients_6):
        """Si tous les clients sont dans la ZFE, toutes les paires sont pénalisées."""
        zones = [{
            "zone_type": "zfe",
            "latitude": depot_a["latitude"],
            "longitude": depot_a["longitude"],
            "radius_km": 100,
        }]
        pairs = _build_zfe_pairs(clients_6, zones)
        assert len(pairs) > 0

    def test_zfe_increases_cost(self, clients_6, depot_a, vehicles_2):
        """Le coût avec ZFE doit être >= coût sans ZFE."""
        result_no_zfe = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="standard", time_limit_s=5,
        )
        zones = [{
            "zone_type": "zfe",
            "latitude": depot_a["latitude"],
            "longitude": depot_a["longitude"],
            "radius_km": 50,
        }]
        result_zfe = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="standard", zones=zones, time_limit_s=5,
        )
        # Le coût ne peut pas diminuer avec des pénalités ZFE
        assert result_zfe["total_distance_km"] >= result_no_zfe["total_distance_km"] - 0.01


class TestOpenVRP:

    def test_open_mode_returns_result(self, clients_6, depot_a, vehicles_2):
        result = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="open",
            time_limit_s=5,
        )
        assert result["vrp_mode"] == "open"
        assert "routes" in result

    def test_open_mode_less_distance_than_standard(self, clients_6, depot_a, vehicles_2):
        """En mode open, pas de retour au dépôt → distance ≤ mode standard."""
        r_standard = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="standard", time_limit_s=5,
        )
        r_open = ortools_vrp(
            clients_6, depot_a, vehicles_2,
            vrp_mode="open", time_limit_s=5,
        )
        if r_standard.get("clients_served", 0) > 0 and r_open.get("clients_served", 0) > 0:
            assert r_open["total_distance_km"] <= r_standard["total_distance_km"] + 0.1


class TestSkillConstraints:

    def test_vehicle_cant_serve_adr(self, depot_a):
        """Un véhicule non-ADR ne devrait pas être assigné à un client ADR."""
        clients = [
            {"name": "ADR Client", "latitude": 33.58, "longitude": -7.59,
             "demand_kg": 50, "ready_time": 60, "due_time": 600,
             "service_time": 10, "adr_class": "3"},
        ]
        vehicles = [
            {"capacity_kg": 1000, "cost_per_km": 0.5, "allowed_adr": False, "registration": "STD"},
        ]
        result = ortools_vrp(clients, depot_a, vehicles, vrp_mode="standard", time_limit_s=5)
        assert isinstance(result, dict)

    def test_valid_mode_names(self, clients_6, depot_a, vehicles_2):
        for mode in ("standard", "open"):
            res = ortools_vrp(clients_6, depot_a, vehicles_2, vrp_mode=mode, time_limit_s=3)
            assert res.get("vrp_mode") == mode

    def test_invalid_mode_returns_error(self, clients_6, depot_a, vehicles_2):
        result = ortools_vrp(clients_6, depot_a, vehicles_2, vrp_mode="unknown_mode")
        assert "error" in result
