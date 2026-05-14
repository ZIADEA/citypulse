"""Tests UI — LoginWidget (pytest-qt)."""
import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QLineEdit

from app.ui.login_widget import LoginWidget


def test_login_widget_has_fields(qtbot):
    # Arrange / Act
    w = LoginWidget()
    qtbot.addWidget(w)
    # Assert
    assert isinstance(w.login_username, QLineEdit)
    assert w.login_password.echoMode() == QLineEdit.EchoMode.Password
