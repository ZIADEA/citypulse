"""Tests ForecastEngine (sans BDD)."""
from app.ai.demand_forecast import ForecastEngine, forecast_from_algo_results_history


def test_predict_client_demand_basic():
    eng = ForecastEngine()
    hist = [
        {"date": "2026-01-01", "quantity": 10},
        {"date": "2026-01-02", "quantity": 12},
        {"date": "2026-01-03", "quantity": 11},
    ]
    out = eng.predict_client_demand(42, hist, days=3)
    assert len(out) == 3
    assert all("predicted" in r and r["client_id"] == 42 for r in out)


def test_predict_fleet_empty():
    eng = ForecastEngine()
    d = eng.predict_fleet_demand([], days=5)
    assert len(d["forecast"]) == 5
    assert d.get("message")


def test_forecast_from_algo_history_compat():
    hist = [{"date": "2026-01-0%d" % i, "actual": i * 2} for i in range(1, 6)]
    pack = forecast_from_algo_results_history(hist, days_ahead=2)
    assert "forecast" in pack and len(pack["forecast"]) == 2
    assert "historical" in pack
