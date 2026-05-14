"""Tests UI — OrdersWidget smoke (pytest-qt)."""
import pytest

pytest.importorskip("PyQt6.QtWidgets")

from app.ui.orders_widget import OrdersWidget


class _StubMainWindow:
    current_user = {"id": 1, "username": "admin", "role": "admin", "full_name": "Admin"}

    def _nav_to(self, _idx):
        pass


def test_orders_widget_instantiates(qtbot, db_memory):
    w = OrdersWidget(_StubMainWindow())
    qtbot.addWidget(w)
    assert hasattr(w, "refresh_data")
