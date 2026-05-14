"""test_anomaly.py — Tests détection d'anomalies"""
from app.ai.anomaly_detection import detect_anomalies, zscore_anomalies, detect_all


def _make_records(n=10, inject_anomaly=False):
    records = []
    for i in range(n):
        records.append({
            "total_distance": 100.0 + i * 2,
            "total_cost":      50.0 + i,
            "avg_delay":       2.0 + i * 0.1,
            "algorithm":       "Glouton",
            "created_at":      f"2025-01-{i+1:02d}",
        })
    if inject_anomaly:
        records.append({
            "total_distance": 9999.0,   # outlier massif
            "total_cost":     5000.0,
            "avg_delay":      999.0,
            "algorithm":      "OR-Tools",
            "created_at":     "2025-01-15",
        })
    return records


def test_no_anomaly_clean_data():
    records = _make_records(10, inject_anomaly=False)
    anomalies = detect_anomalies(records)
    assert isinstance(anomalies, list)


def test_detects_obvious_outlier():
    records = _make_records(10, inject_anomaly=True)
    anomalies = detect_anomalies(records)
    assert len(anomalies) >= 1
    # L'outlier massif doit être détecté
    distances = [a["record"]["total_distance"] for a in anomalies]
    assert any(d > 1000 for d in distances)


def test_severity_field_present():
    records = _make_records(10, inject_anomaly=True)
    anomalies = detect_anomalies(records)
    for a in anomalies:
        assert "severity" in a
        assert a["severity"] in ("low", "medium", "high")


def test_description_field_readable():
    records = _make_records(10, inject_anomaly=True)
    anomalies = detect_anomalies(records)
    for a in anomalies:
        assert "description" in a
        assert len(a["description"]) > 10


def test_insufficient_data_returns_empty():
    records = _make_records(3)
    anomalies = detect_anomalies(records)
    assert anomalies == []


def test_zscore_detects_outlier():
    values = [10.0, 11.0, 10.5, 9.8, 10.2, 100.0]  # 100 est un outlier
    outliers = zscore_anomalies(values)
    assert len(outliers) >= 1
    assert 5 in outliers   # index du 100.0


def test_zscore_no_outlier():
    values = [10.0, 10.1, 9.9, 10.2, 10.05]
    outliers = zscore_anomalies(values)
    assert outliers == []


def test_detect_all_has_suggestion():
    clients = [
        {
            "id": 1,
            "name": "Test",
            "latitude": 0.0,
            "longitude": 0.0,
            "demand_kg": 10.0,
            "service_time": 15,
            "ready_time": 480,
            "due_time": 600,
        },
    ]
    orders = [{"id": 1, "client_id": 1, "quantity_kg": 500.0}]
    rows = detect_all(clients, orders)
    assert any("suggestion" in r for r in rows)
