"""Tests purs mistral_client (parse, contexte) — sans appel API."""
from app.ai.mistral_client import build_context, parse_command, get_fallback_response


def test_build_context():
    s = build_context({"clients_active": 5, "total_demand_kg": 100.0, "vehicles_total": 2})
    assert "5" in s and "100" in s


def test_parse_optimize():
    cmd = parse_command('OK\n{"action":"optimize"}')
    assert cmd == {"action": "optimize"}


def test_parse_navigate_index():
    cmd = parse_command('{"action":"navigate","page_index":7}')
    assert cmd == {"action": "navigate", "page_index": 7}


def test_fallback_nonempty():
    assert len(get_fallback_response("test")) > 20
