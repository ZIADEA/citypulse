"""
conftest.py — Fixtures partagées CityPulse.

Règles : pas de réseau dans les tests (mocker requests) ; fichiers temporaires via tmp_path.
Objectif durée suite : < 90 s (`pytest.ini` timeout + `pytest-timeout`).
"""
from __future__ import annotations

import os
import pytest


def pytest_configure(config):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    # Même contrainte que main.py : WebEngine avant toute instance QCoreApplication
    try:
        from PyQt6.QtCore import QCoreApplication, Qt

        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    except ImportError:
        pass


@pytest.fixture
def qtapp(qapp):
    """Alias explicite sur la QApplication pytest-qt."""
    return qapp


@pytest.fixture
def depot_casablanca():
    # Arrange
    return {"latitude": 33.5731, "longitude": -7.5898, "name": "Dépôt Central Casablanca"}


@pytest.fixture
def depot_rabat():
    return {"latitude": 34.0209, "longitude": -6.8416, "name": "Dépôt Rabat"}


@pytest.fixture
def clients_10():
    """10 premiers clients Solomon C101 (coordonnées GPS Casablanca)."""
    base_lat, base_lon = 33.5731, -7.5898
    data = [
        (1, 45, 68, 10, 912, 967, 90),
        (2, 45, 70, 30, 825, 870, 90),
        (3, 42, 66, 10, 65, 146, 90),
        (4, 42, 68, 10, 727, 782, 90),
        (5, 42, 65, 10, 15, 67, 90),
        (6, 40, 69, 20, 621, 702, 90),
        (7, 40, 66, 20, 170, 225, 90),
        (8, 38, 68, 20, 255, 324, 90),
        (9, 38, 70, 10, 534, 605, 90),
        (10, 35, 66, 10, 357, 410, 90),
    ]
    return [
        {
            "name": f"Client {i+1}",
            "latitude": base_lat + (y - 50) * 0.01,
            "longitude": base_lon + (x - 50) * 0.01,
            "demand_kg": dem,
            "ready_time": ready,
            "due_time": due,
            "service_time": svc,
        }
        for i, (_, x, y, dem, ready, due, svc) in enumerate(data)
    ]


@pytest.fixture
def clients_50(clients_10):
    """50 clients dérivés (réplication géo décalée)."""
    out = []
    for k in range(5):
        for i, c in enumerate(clients_10):
            out.append({
                **c,
                "name": f"{c['name']}-{k}",
                "latitude": c["latitude"] + k * 0.001,
                "longitude": c["longitude"] + k * 0.001,
            })
    return out[:50]


@pytest.fixture
def clients_1(depot_casablanca):
    return [{
        "name": "Client Unique",
        "latitude": 33.60,
        "longitude": -7.55,
        "demand_kg": 50,
        "ready_time": 60,
        "due_time": 300,
        "service_time": 10,
    }]


@pytest.fixture
def vehicles_3():
    return [
        {"capacity_kg": 200, "max_speed_kmh": 60, "cost_per_km": 0.5, "registration": "V1"},
        {"capacity_kg": 200, "max_speed_kmh": 60, "cost_per_km": 0.5, "registration": "V2"},
        {"capacity_kg": 200, "max_speed_kmh": 60, "cost_per_km": 0.5, "registration": "V3"},
    ]


@pytest.fixture
def vehicle_small():
    return [{"capacity_kg": 5, "max_speed_kmh": 60, "cost_per_km": 0.5, "registration": "SMALL"}]


@pytest.fixture
def driver_1():
    return {
        "id": 1, "first_name": "Ali", "last_name": "Benali",
        "license_category": "CE", "qualifications": ["ADR", "FIMO"],
        "work_start": "07:00", "work_end": "18:00",
        "max_drive_before_break_min": 270,
        "min_break_minutes": 45,
        "min_daily_rest_minutes": 660,
        "max_daily_h": 9.0,
        "hourly_rate": 16.0,
        "overtime1_hours": 2.0,
        "overtime1_rate": 1.25,
        "overtime2_rate": 1.50,
        "contract_type": "CDI",
    }


@pytest.fixture
def drivers_3():
    return [
        {
            "id": 1, "first_name": "Ali", "last_name": "Benali",
            "license_category": "CE", "qualifications": ["ADR", "FIMO", "FCO"],
            "work_start": "07:00", "work_end": "18:00",
            "max_drive_before_break_min": 270,
            "min_break_minutes": 45,
            "min_daily_rest_minutes": 660,
            "max_daily_h": 9.0,
            "hourly_rate": 16.0,
            "overtime1_hours": 2.0,
            "overtime1_rate": 1.25,
            "overtime2_rate": 1.50,
            "contract_type": "CDI",
        },
        {
            "id": 2, "first_name": "Sara", "last_name": "El Fassi",
            "license_category": "C", "qualifications": ["FIMO"],
            "work_start": "08:00", "work_end": "17:00",
            "max_drive_before_break_min": 270,
            "min_break_minutes": 45,
            "min_daily_rest_minutes": 660,
            "max_daily_h": 9.0,
            "hourly_rate": 15.0,
            "overtime1_hours": 2.0,
            "overtime1_rate": 1.25,
            "overtime2_rate": 1.50,
            "contract_type": "CDI",
        },
        {
            "id": 3, "first_name": "Omar", "last_name": "Tazi",
            "license_category": "B", "qualifications": [],
            "work_start": "09:00", "work_end": "18:00",
            "max_drive_before_break_min": 270,
            "min_break_minutes": 45,
            "min_daily_rest_minutes": 660,
            "max_daily_h": 9.0,
            "hourly_rate": 13.0,
            "overtime1_hours": 2.0,
            "overtime1_rate": 1.25,
            "overtime2_rate": 1.50,
            "contract_type": "CDD",
        },
    ]


@pytest.fixture
def zones_2():
    return [
        {
            "id": 1, "name": "ZFE Centre Casablanca", "zone_type": "zfe",
            "latitude": 33.5950, "longitude": -7.6192, "radius_km": 2.0,
            "description": "ZFE",
        },
        {
            "id": 2, "name": "Zone Industrielle", "zone_type": "delivery",
            "latitude": 33.6100, "longitude": -7.5200, "radius_km": 3.5,
            "description": "Livraison",
        },
    ]


@pytest.fixture
def orders_20():
    """20 commandes synthétiques."""
    base_lat, base_lon = 33.5731, -7.5898
    orders = []
    for i in range(20):
        orders.append({
            "id": i + 1,
            "reference": f"ORD-T{i+1:04d}",
            "client_id": (i % 10) + 1,
            "quantity_kg": float(10 + i * 2),
            "status": "pending",
            "latitude": base_lat + (i % 5 - 2) * 0.02,
            "longitude": base_lon + (i % 6 - 3) * 0.02,
        })
    return orders


@pytest.fixture
def orders_30():
    base_lat, base_lon = 33.5731, -7.5898
    adr_classes = ["", "", "", "", "3", "8", "", "", "3", ""]
    temp_reqs = ["ambiant", "ambiant", "frigo", "ambiant", "ambiant",
                 "ambiant", "frigo", "ambiant", "ambiant", "ambiant"]
    statuses = ["pending", "assigned", "in_progress", "pending", "pending",
                "delivered", "pending", "assigned", "pending", "in_progress"]
    orders = []
    for i in range(30):
        orders.append({
            "id": i + 1,
            "reference": f"ORD-2026-{i+1:04d}",
            "client_id": (i % 10) + 1,
            "quantity_kg": float(10 + i * 5),
            "volume_m3": float(0.1 + i * 0.05),
            "adr_class": adr_classes[i % 10],
            "temperature_requirement": temp_reqs[i % 10],
            "status": statuses[i % 10],
            "priority": (i % 3) + 1,
            "latitude": base_lat + (i % 5 - 2) * 0.02,
            "longitude": base_lon + (i % 6 - 3) * 0.02,
            "ready_time": 480 + (i % 4) * 60,
            "due_time": 900 + (i % 4) * 30,
            "service_time": 15,
        })
    return orders


@pytest.fixture
def route_sample(depot_casablanca, clients_10):
    """Payload résultat simplifié (tests UI / intégration)."""
    return {
        "vehicle_id": 1,
        "registration": "TEST-1",
        "stops": [
            {"type": "depot", "name": "Dépôt", **{k: depot_casablanca[k] for k in ("latitude", "longitude")}},
            {"type": "delivery", "client": clients_10[0]},
        ],
        "total_km": 12.5,
    }


@pytest.fixture
def db_memory(tmp_path, monkeypatch):
    """
    SQLite fichier dans tmp_path + migrations ; DB_PATH patché pour get_connection().
    """
    from app.database import db_manager
    from app.database.db_manager import init_database, run_migrations

    path = str(tmp_path / "citypulse_test.db")
    init_database(path)
    run_migrations(path)
    monkeypatch.setattr(db_manager, "DB_PATH", path)
    yield path


@pytest.fixture
def db_populated(db_memory, clients_10):
    """Base initialisée + quelques clients et un dépôt supplémentaire."""
    from app.database.db_manager import get_connection

    conn = get_connection()
    conn.execute(
        "INSERT INTO depots (name, address, latitude, longitude) VALUES (?,?,?,?)",
        ("Rabat", "Rabat", 34.02, -6.84),
    )
    for i, c in enumerate(clients_10[:5]):
        conn.execute(
            """INSERT INTO clients (name, address, latitude, longitude, demand_kg, ready_time, due_time, service_time)
               VALUES (?,?,?,?,?,?,?,?)""",
            (c["name"], "", c["latitude"], c["longitude"], c["demand_kg"],
             c["ready_time"], c["due_time"], c["service_time"]),
        )
    conn.commit()
    conn.close()
    return db_memory
