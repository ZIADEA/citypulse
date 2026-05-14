"""Intégration ReportService — snapshot JSON sur base tmp (pas de réseau)."""
import json

from app.services.report_service import ReportService


def test_generate_full_snapshot_writes_json(tmp_path, db_memory):
    out = tmp_path / "snap.json"
    ReportService().generate_full_snapshot(str(out))
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "tables" in data
    assert "clients" in data["tables"]
