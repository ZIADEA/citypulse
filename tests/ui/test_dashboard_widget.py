"""Tests UI — DashboardWidget smoke (pytest-qt)."""
import pytest

pytest.importorskip("PyQt6.QtWidgets")

from app.ui.dashboard_widget import DashboardWidget


class _StubMainWindow:
    current_user = {"id": 1, "username": "admin", "role": "admin", "full_name": "Admin"}

    def _nav_to(self, _idx):
        pass

    def _apply_theme(self, *_a, **_k):
        pass


def test_dashboard_widget_instantiates(qtbot, db_memory):
    w = DashboardWidget(_StubMainWindow())
    qtbot.addWidget(w)
    assert w.layout() is not None
