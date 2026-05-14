"""test_validation.py — Tests de validation des données (pur Python)"""
import pytest
from app.services.optimization_service import validate_inputs, ValidationError
from app.utils.data_validator import generate_stress_test_clients, validate_clients

def test_no_clients(vehicles_3, depot_casablanca):
    with pytest.raises(ValidationError):
        validate_inputs([], vehicles_3, depot_casablanca)

def test_no_vehicles(clients_10, depot_casablanca):
    with pytest.raises(ValidationError):
        validate_inputs(clients_10, [], depot_casablanca)

def test_no_depot(clients_10, vehicles_3):
    with pytest.raises(ValidationError):
        validate_inputs(clients_10, vehicles_3, None)

def test_filters_zero_coords(vehicles_3, depot_casablanca):
    clients = [
        {"latitude":33.59,"longitude":-7.61,"name":"OK","demand_kg":50,"ready_time":0,"due_time":200},
        {"latitude":0,"longitude":0,"name":"BAD","demand_kg":50,"ready_time":0,"due_time":200},
    ]
    valid, warnings = validate_inputs(clients, vehicles_3, depot_casablanca)
    assert len(valid) == 1

def test_filters_inverted_tw(vehicles_3, depot_casablanca):
    clients = [
        {"latitude":33.59,"longitude":-7.61,"name":"OK","demand_kg":50,"ready_time":0,"due_time":300},
        {"latitude":33.58,"longitude":-7.60,"name":"BAD","demand_kg":50,"ready_time":400,"due_time":100},
    ]
    valid, _ = validate_inputs(clients, vehicles_3, depot_casablanca)
    assert len(valid) == 1

def test_stress_generator():
    clients = generate_stress_test_clients(15)
    assert len(clients) == 15
    assert any("COORDS_NULLES" in c["name"] for c in clients)
    assert any("TW_INVERSEE" in c["name"] for c in clients)

def test_stress_validator_rejects():
    raw = generate_stress_test_clients(15)
    valid, report = validate_clients(raw)
    assert len(valid) < len(raw)
    assert any("Rejeté" in r["action"] for r in report)

def test_stress_corrects_neg_demand():
    raw = generate_stress_test_clients(15)
    valid, _ = validate_clients(raw)
    for c in valid:
        assert c["demand_kg"] >= 0
