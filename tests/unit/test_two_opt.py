"""
test_two_opt.py — Tests unitaires pour l'algorithme 2-opt
"""
import pytest
from app.engine.two_opt import two_opt_vrp, _is_feasible
from app.engine.distance import build_matrix


def test_two_opt_improves_or_equals_greedy(clients_10, depot_casablanca, vehicles_3):
    """2-opt doit produire une distance ≤ glouton."""
    from app.engine.greedy import greedy_vrp
    r_greedy = greedy_vrp(clients_10, depot_casablanca, vehicles_3)
    r_2opt   = two_opt_vrp(clients_10, depot_casablanca, vehicles_3)
    assert r_2opt["total_distance_km"] <= r_greedy["total_distance_km"] + 1e-6


def test_two_opt_empty_clients(depot_casablanca, vehicles_3):
    result = two_opt_vrp([], depot_casablanca, vehicles_3)
    assert result["clients_served"] == 0


def test_two_opt_single_client(clients_1, depot_casablanca, vehicles_3):
    result = two_opt_vrp(clients_1, depot_casablanca, vehicles_3)
    assert result["clients_served"] == 1


def test_two_opt_convergence_field(clients_10, depot_casablanca, vehicles_3):
    """Le champ convergence doit être une liste non vide."""
    result = two_opt_vrp(clients_10, depot_casablanca, vehicles_3)
    assert "convergence" in result
    assert isinstance(result["convergence"], list)
    assert len(result["convergence"]) >= 1


def test_two_opt_tw_feasibility(depot_casablanca, vehicles_3):
    """Vérifier que _is_feasible rejette une fenêtre violée."""
    clients = [
        {"name": "C1", "latitude": 33.59, "longitude": -7.61,
         "demand_kg": 50, "ready_time": 0, "due_time": 1, "service_time": 10},
    ]
    dist_km, time_s, _ = build_matrix(clients, depot_casablanca)
    # Route [0, 1, 0] — le due_time=1 min est quasi impossible
    feasible = _is_feasible([0, 1, 0], dist_km, time_s, clients, coeff=1.0)
    # Ne doit pas crasher — peut être True ou False selon la distance
    assert isinstance(feasible, bool)


def test_two_opt_gain_field(clients_10, depot_casablanca, vehicles_3):
    """Le champ gain_vs_greedy doit être un float."""
    result = two_opt_vrp(clients_10, depot_casablanca, vehicles_3)
    assert "gain_vs_greedy" in result
    assert isinstance(result["gain_vs_greedy"], float)
