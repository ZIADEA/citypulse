"""notification_bell.py — Cloche de notifications avec badge et dropdown."""
import logging
from PyQt6.QtWidgets import (
    QPushButton, QMenu, QLabel, QWidgetAction, QWidget,
    QVBoxLayout, QHBoxLayout, QFrame,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont

from ..lucide_icons import lucide_icon, lucide_icon_size

logger = logging.getLogger(__name__)

C = {
    "bg": "#112240",
    "bg2": "#0A1628",
    "accent": "#00D4FF",
    "text": "#E8F4FD",
    "text2": "#8899AA",
    "border": "#1E3A5F",
    "hover": "#1A3A5C",
    "warning": "#FFB800",
    "danger": "#FF4757",
    "success": "#00FF88",
}

_SEVERITY_COLOR = {
    "critical": C["danger"],
    "warning": C["warning"],
    "info": C["accent"],
    "success": C["success"],
}


class NotificationBell(QPushButton):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._count = 0
        self.setFixedHeight(36)
        self.setMinimumWidth(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Notifications")
        self._apply_style()
        self.clicked.connect(self._show_dropdown)
        self.update_count(0)

    def _apply_style(self):
        self.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            "border-radius:6px;padding:4px 6px;}}"
            f"QPushButton:hover{{background:{C['hover']};}}"
        )

    def update_count(self, n: int):
        self._count = max(0, n)
        stroke = C["danger"] if self._count > 0 else C["text2"]
        self.setIcon(lucide_icon("bell", stroke, 20))
        self.setIconSize(lucide_icon_size(20))
        if self._count:
            c = "9+" if self._count > 9 else str(self._count)
            self.setText(c)
            self.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;"
                "border-radius:6px;padding:4px 6px;"
                f"color:{C['danger']};font-weight:700;font-size:12px;}}"
                f"QPushButton:hover{{background:{C['hover']};}}"
            )
        else:
            self.setText("")
            self.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;"
                "border-radius:6px;padding:4px 6px;}}"
                f"QPushButton:hover{{background:{C['hover']};}}"
            )

    def refresh_from_db(self):
        try:
            from ...database.db_manager import get_unread_notifications_count

            n = get_unread_notifications_count()
            self.update_count(n)
        except Exception:
            logger.debug("NotificationBell: impossible de lire les notifications")

    def _show_dropdown(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C['bg']};border:1px solid {C['border']};"
            "border-radius:8px;padding:6px;}}"
            f"QMenu::item{{padding:0;margin:0;}}"
            f"QMenu::item:selected{{background:transparent;}}"
        )

        notifs = self._fetch_recent()
        if not notifs:
            empty = QWidgetAction(menu)
            w = QLabel(" Aucune notification ")
            w.setStyleSheet(
                f"color:{C['text2']};font-size:12px;padding:12px;background:transparent;"
            )
            empty.setDefaultWidget(w)
            menu.addAction(empty)
        else:
            for n in notifs:
                action = QWidgetAction(menu)
                action.setDefaultWidget(self._make_notif_widget(n))
                menu.addAction(action)

        menu.addSeparator()
        all_action = menu.addAction("Voir toutes les notifications →")
        all_action.triggered.connect(self._open_notifications_page)

        menu.exec(self.mapToGlobal(QPoint(0, self.height() + 4)))

    def _fetch_recent(self) -> list:
        try:
            from ...database.db_manager import get_connection

            conn = get_connection()
            rows = conn.execute(
                "SELECT title, message, severity, created_at FROM notifications "
                "WHERE is_read=0 ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
            conn.close()
            return [
                {"title": r[0], "message": r[1], "severity": r[2], "at": r[3]}
                for r in rows
            ]
        except Exception:
            return []

    def _make_notif_widget(self, n: dict) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(280)
        lo = QVBoxLayout(w)
        lo.setContentsMargins(10, 8, 10, 8)
        lo.setSpacing(4)
        sev = (n.get("severity") or "info").lower()
        col = _SEVERITY_COLOR.get(sev, C["text2"])
        t = QLabel(n.get("title") or "—")
        t.setStyleSheet(
            f"color:{col};font-size:12px;font-weight:700;background:transparent;"
        )
        t.setWordWrap(True)
        lo.addWidget(t)
        msg = (n.get("message") or "")[:200]
        if msg:
            m = QLabel(msg)
            m.setStyleSheet(
                f"color:{C['text2']};font-size:11px;background:transparent;"
            )
            m.setWordWrap(True)
            lo.addWidget(m)
        return w

    def _open_notifications_page(self):
        if self.main_window and hasattr(self.main_window, "_nav_to"):
            self.main_window._nav_to(14)
