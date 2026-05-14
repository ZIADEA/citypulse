"""Intégration optimization_service — validation + run greedy (pas de réseau)."""
import pytest

from app.services.optimization_service import validate_inputs, run_optimization, ValidationError


def test_validate_inputs_rejects_empty_clients(vehicles_3, depot_casablanca):
    with pytest.raises(ValidationError):
        validate_inputs([], vehicles_3, depot_casablanca)


def test_run_optimization_greedy(db_memory, clients_10, depot_casablanca, vehicles_3):
    # Arrange
    valid, _ = validate_inputs(clients_10, vehicles_3, depot_casablanca)
    # Act
    result = run_optimization("greedy", valid, depot_casablanca, vehicles_3)
    # Assert
    assert "glouton" in (result.get("algorithm") or "").lower()
    assert result.get("clients_served", 0) >= 0
