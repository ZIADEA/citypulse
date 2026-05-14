"""Tests weather_service — réseau mocké (aucun appel HTTP réel)."""
from unittest.mock import MagicMock, patch

import app.services.weather_service as ws


def test_get_current_no_key():
    assert ws.get_current(33.5, -7.5, None) is None


def test_traffic_factor_rain():
    f = ws.get_traffic_factor({"main": "rain", "wind_speed": 5})
    assert 1.0 <= f <= 1.5


def test_forecast_empty_without_key():
    assert ws.get_forecast_5days(33.5, -7.5, None) == []


@patch.object(ws, "HAS_REQUESTS", True)
@patch("app.services.weather_service.requests.get")
def test_get_current_uses_cache_after_first_call(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "weather": [{"description": "nuageux", "main": "Clouds", "id": 801}],
        "main": {"temp": 20.0, "feels_like": 19.0, "humidity": 60},
        "wind": {"speed": 3.0},
    }
    mock_get.return_value = mock_resp
    ws._cache.clear()
    a = ws.get_current(1.0, 2.0, "fake-key-abc")
    b = ws.get_current(1.0, 2.0, "fake-key-abc")
    assert a is not None
    assert b is not None
    assert a.get("temp") == 20.0
    assert mock_get.call_count == 1
