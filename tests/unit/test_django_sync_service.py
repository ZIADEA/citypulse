"""Tests DjangoSyncService (mock requests)."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.django_sync_service import DjangoSyncService


@pytest.fixture
def svc():
    return DjangoSyncService("https://example.com", "secret")


def test_health_check_false_without_requests(monkeypatch):
    import app.services.django_sync_service as m

    monkeypatch.setattr(m, "HAS_REQUESTS", False)
    s = DjangoSyncService("https://x.com", "k")
    assert s.health_check() is False


def test_health_check_ok(svc):
    with patch("app.services.django_sync_service.requests") as req:
        r = MagicMock()
        r.status_code = 200
        req.get.return_value = r
        assert svc.health_check() is True
        req.get.assert_called_once()
        assert "X-CityPulse-Secret" in req.get.call_args.kwargs["headers"]


def test_sync_clients_http_error(svc):
    import requests

    with patch("app.services.django_sync_service.requests") as req:
        resp = MagicMock()
        resp.status_code = 403
        resp.text = "nope"
        err = requests.exceptions.HTTPError(response=resp)
        mock_r = MagicMock()
        mock_r.raise_for_status.side_effect = err
        req.post.return_value = mock_r
        out = svc.sync_clients([])
        assert out.get("ok") is False


def test_pull_confirmations_list(svc):
    with patch("app.services.django_sync_service.requests") as req:
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = [{"order_id": 1, "status": "delivered"}]
        req.get.return_value = r
        rows = svc.pull_confirmations()
        assert len(rows) == 1
        assert rows[0]["order_id"] == 1
