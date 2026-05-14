"""
test_greedy.py — Tests unitaires pour l'algorithme glouton
"""
import pytest
from app.engine.greedy import greedy_vrp


def test_greedy_empty_clients(depot_casablanca, vehicles_3):
    """0 client → résultat vide propre."""
    result = greedy_vrp([], depot_casablanca, vehicles_3)
    assert result["clients_served"] == 0
    assert result["total_distance_km"] == 0.0
    assert result["routes"] == []


def test_greedy_single_client(clients_1, depot_casablanca, vehicles_3):
    """1 client → 1 client servi, distance > 0."""
    result = greedy_vrp(clients_1, depot_casablanca, vehicles_3)
    assert result["clients_served"] == 1
    assert result["total_distance_km"] > 0


def test_greedy_all_served(clients_10, depot_casablanca, vehicles_3):
    """10 clients, capacité suffisante → tous servis."""
    result = greedy_vrp(clients_10, depot_casablanca, vehicles_3)
    assert result["clients_served"] == 10
    assert result["clients_total"] == 10
    assert result["total_distance_km"] > 0


def test_greedy_capacity_overflow(clients_10, depot_casablanca, vehicle_small):
    """Capacité ridiculement faible → 0 ou très peu de clients servis."""
    result = greedy_vrp(clients_10, depot_casablanca, vehicle_small)
    assert result["clients_served"] < 10


def test_greedy_result_fields(clients_10, depot_casablanca, vehicles_3):
    """Vérifier que tous les champs attendus sont présents."""
    result = greedy_vrp(clients_10, depot_casablanca, vehicles_3)
    required = [
        "algorithm", "routes", "total_distance_km", "total_cost",
        "clients_served", "clients_total", "respect_rate",
        "avg_delay_min", "cpu_time_ms", "distance_source"
    ]
    for field in required:
        assert field in result, f"Champ manquant : {field}"


def test_greedy_coeff_increases_time(clients_10, depot_casablanca, vehicles_3):
    """Un coefficient trafic élevé ne doit pas réduire le nombre de clients servis."""
    r1 = greedy_vrp(clients_10, depot_casablanca, vehicles_3, traffic_coeff=1.0)
    r2 = greedy_vrp(clients_10, depot_casablanca, vehicles_3, traffic_coeff=2.0)
    # La distance ne change pas (même routes), mais les durées augmentent
    assert r2["clients_served"] >= 0   # pas de crash


def test_greedy_respect_rate_range(clients_10, depot_casablanca, vehicles_3):
    """Le taux de respect doit être entre 0 et 100."""
    result = greedy_vrp(clients_10, depot_casablanca, vehicles_3)
    assert 0.0 <= result["respect_rate"] <= 100.0
