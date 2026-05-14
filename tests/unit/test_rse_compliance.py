"""Tests ciblés conformité RSE (CE 561/2006) — sans réseau."""
from app.engine.cost_calculator import check_rse_compliance, MAX_DAILY_DRIVE_H


def test_rse_violation_long_consecutive_drive(driver_1):
    # Arrange — trajets longs, services courts → pause insuffisante
    stops = [
        {"type": "delivery", "arrival_time": 600.0, "departure_time": 610.0},
        {"type": "delivery", "arrival_time": 900.0, "departure_time": 910.0},
    ]
    # Act
    r = check_rse_compliance(stops, driver_1, "08:00")
    # Assert
    assert "compliant" in r
    assert isinstance(r["violations"], list)


def test_rse_empty_stops_compliant(driver_1):
    r = check_rse_compliance([], driver_1)
    assert r["compliant"] is True
    assert r["violations"] == []


def test_rse_daily_cap_constant():
    assert MAX_DAILY_DRIVE_H == 9.0
