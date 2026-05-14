"""
test_distance.py — Tests unitaires pour le moteur de distances
"""
import pytest
from app.engine.distance import haversine, build_matrix, build_distance_matrix, build_time_matrix


def test_haversine_same_point():
    """Distance entre deux points identiques = 0."""
    assert haversine(33.5731, -7.5898, 33.5731, -7.5898) == 0.0


def test_haversine_known_distance():
    """Distance Casablanca → Rabat ~ 85 km."""
    d = haversine(33.5731, -7.5898, 34.0209, -6.8416)
    assert 75 < d < 100, f"Distance Casablanca→Rabat inattendue : {d:.1f} km"


def test_build_matrix_returns_square(depot_casablanca, clients_10):
    dist_km, time_s, source = build_matrix(clients_10, depot_casablanca)
    n = len(clients_10) + 1
    assert len(dist_km) == n
    assert all(len(row) == n for row in dist_km)
    assert len(time_s) == n


def test_build_matrix_diagonal_zero(depot_casablanca, clients_10):
    dist_km, time_s, _ = build_matrix(clients_10, depot_casablanca)
    for i in range(len(dist_km)):
        assert dist_km[i][i] == 0.0
        assert time_s[i][i] == 0.0


def test_build_matrix_source_field(depot_casablanca, clients_10):
    _, _, source = build_matrix(clients_10, depot_casablanca)
    assert source in ("osrm", "haversine", "cache")


def test_build_time_matrix_coeff(depot_casablanca, clients_10):
    t1 = build_time_matrix(clients_10, depot_casablanca, coeff=1.0)
    t2 = build_time_matrix(clients_10, depot_casablanca, coeff=2.0)
    # Avec coeff=2, tous les temps doivent être >= ceux avec coeff=1
    for i in range(len(t1)):
        for j in range(len(t1[i])):
            assert t2[i][j] >= t1[i][j], f"t2[{i}][{j}] < t1[{i}][{j}]"


def test_retrocompat_build_distance_matrix(depot_casablanca, clients_10):
    """La fonction rétrocompatible doit retourner une liste 2D."""
    dm = build_distance_matrix(clients_10, depot_casablanca)
    assert isinstance(dm, list)
    assert isinstance(dm[0], list)
