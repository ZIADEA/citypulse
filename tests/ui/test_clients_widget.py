"""Tests UI — ClientsWidget smoke (pytest-qt)."""
import pytest

pytest.importorskip("PyQt6.QtWidgets")

from app.ui.clients_widget import ClientsWidget


class _StubMainWindow:
    current_user = {"id": 1, "username": "admin", "role": "admin", "full_name": "Admin"}

    def _nav_to(self, _idx):
        pass


def test_clients_widget_instantiates(qtbot, db_memory):
    w = ClientsWidget(_StubMainWindow())
    qtbot.addWidget(w)
    assert hasattr(w, "refresh_data")
