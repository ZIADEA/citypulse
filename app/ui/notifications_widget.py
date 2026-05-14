"""
notifications_widget.py — Centre de notifications (filtres, détail, résumé journalier)
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QComboBox, QLineEdit, QCheckBox, QSplitter, QTextBrowser,
    QFrame, QDialog, QDialogButtonBox, QMessageBox, QSizePolicy,
)

from ..database.db_manager import get_connection, log_action
from ..paths import settings_json_path
from .help_dialog import show_help
from .lucide_icons import apply_action_button
from .toast import show_toast
from .components.confirm_dialog import _dialog_qss

_SETTINGS_PATH = settings_json_path()

C = {
    "bg": "#0D1B2A", "panel": "#112240", "input": "#1A2E4A",
    "accent": "#00D4FF", "text": "#E8F4FD", "text2": "#8899AA",
    "border": "#1E3A5F", "success": "#00FF88", "warning": "#FFB800",
    "danger": "#FF4757", "info": "#3B9EE8",
}

_SEVERITY_COLORS = {
    "info": C["info"], "warning": C["warning"], "danger": C["danger"],
    "success": C["success"], "high": C["danger"], "medium": C["warning"],
    "low": C["text2"],
}


def _load_json_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class NotificationsWidget(QWidget):
    """Page notifications : liste filtrée + détail + navigation."""

    navigate_request = pyqtSignal(int)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._rows: list[dict] = []
        self._last_summary_date: str | None = None
        self._setup_ui()

        self._hour_timer = QTimer(self)
        self._hour_timer.setInterval(3_600_000)
        self._hour_timer.timeout.connect(self._on_hour_tick)
        self._hour_timer.start()
        QTimer.singleShot(5000, self._on_hour_tick)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 8)
        root.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("Notifications")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['text']};background:transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        hb = QPushButton()
        hb.setFixedSize(32, 32)
        hb.setToolTip("Aide — Notifications")
        hb.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(hb, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        hb.clicked.connect(lambda: show_help(self, "notifications"))
        hdr.addWidget(hb)
        root.addLayout(hdr)

        filt = QFrame()
        filt.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};border-radius:8px;}}"
        )
        fl = QHBoxLayout(filt)
        fl.setContentsMargins(10, 8, 10, 8)
        self._type_cb = QComboBox()
        self._type_cb.addItem("Tous types", "")
        for t in ("info", "alert", "incident", "summary", "system", "order", "vehicle"):
            self._type_cb.addItem(t, t)
        self._sev_cb = QComboBox()
        self._sev_cb.addItem("Toutes sévérités", "")
        for s in ("info", "warning", "danger", "success"):
            self._sev_cb.addItem(s, s)
        self._unread_only = QCheckBox("Non lus seulement")
        self._search = QLineEdit()
        self._search.setPlaceholderText("Recherche titre / message…")
        self._search.setMinimumWidth(180)
        self._btn_apply = QPushButton("Filtrer")
        self._btn_apply.clicked.connect(self.refresh_data)
        self._btn_mark = QPushButton("Tout marquer lu")
        self._btn_mark.clicked.connect(self._mark_all_read)
        for w in (QLabel("Type:"), self._type_cb, QLabel("Sév.:"), self._sev_cb,
                  self._unread_only, self._search, self._btn_apply, self._btn_mark):
            fl.addWidget(w)
        fl.addStretch()
        root.addWidget(filt)

        split = QSplitter(Qt.Orientation.Horizontal)
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget{{background:{C['input']};color:{C['text']};border:1px solid {C['border']};"
            "border-radius:6px;}}"
            f"QListWidget::item{{padding:8px;border-bottom:1px solid {C['border']};}}"
            f"QListWidget::item:selected{{background:{C['panel']};}}"
        )
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.currentItemChanged.connect(self._on_select)
        split.addWidget(self._list)

        detail = QFrame()
        detail.setFixedWidth(280)
        detail.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};border-radius:8px;}}"
        )
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(10, 10, 10, 10)
        dl.addWidget(QLabel("Détail"))
        self._detail = QTextBrowser()
        self._detail.setOpenExternalLinks(True)
        self._detail.setStyleSheet(
            f"QTextBrowser{{background:{C['bg']};color:{C['text']};border:none;font-size:12px;}}"
        )
        dl.addWidget(self._detail, 1)
        self._btn_open = QPushButton("Ouvrir la cible…")
        self._btn_open.setVisible(False)
        self._btn_open.clicked.connect(self._open_action_target)
        dl.addWidget(self._btn_open)
        split.addWidget(detail)
        split.setSizes([700, 280])
        root.addWidget(split, 1)

        self._current_action: dict = {}

    def _on_hour_tick(self):
        cfg = _load_json_settings()
        n = cfg.get("notifications") or {}
        if not n.get("daily_summary", cfg.get("notif_daily_summary", True)):
            return
        hour_target = int(n.get("daily_hour", cfg.get("notif_daily_hour", 18)))
        now = datetime.now()
        if now.hour != hour_target:
            return
        today = now.strftime("%Y-%m-%d")
        if self._last_summary_date == today:
            return
        self._last_summary_date = today
        try:
            conn = get_connection()
            unread = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE is_read=0"
            ).fetchone()[0]
            pending = 0
            try:
                pending = conn.execute(
                    "SELECT COUNT(*) FROM orders WHERE status='pending' AND COALESCE(archived,0)=0"
                ).fetchone()[0]
            except Exception:
                pass
            conn.execute(
                """INSERT INTO notifications
                (type, title, message, severity, is_read, created_at)
                VALUES (?,?,?,?, 0, datetime('now'))""",
                (
                    "summary",
                    f"Résumé du {today}",
                    f"Notifications non lues : {unread}. Commandes en attente : {pending}.",
                    "info",
                ),
            )
            conn.commit()
            conn.close()
            log_action("NOTIF_DAILY_SUMMARY", f"Résumé auto {today}")
            if self.main_window and hasattr(self.main_window, "_topbar"):
                self.main_window._topbar.bell.refresh_from_db()
            self.refresh_data()
        except Exception:
            pass

    def retranslate_ui(self, lang: str):
        pass

    def refresh_data(self):
        type_f = self._type_cb.currentData() or ""
        sev_f = self._sev_cb.currentData() or ""
        unread = self._unread_only.isChecked()
        qtxt = (self._search.text() or "").strip().lower()

        conn = get_connection()
        sql = "SELECT * FROM notifications WHERE 1=1"
        params: list = []
        if type_f:
            sql += " AND type = ?"
            params.append(type_f)
        if sev_f:
            sql += " AND COALESCE(severity,'info') = ?"
            params.append(sev_f)
        if unread:
            sql += " AND is_read = 0"
        sql += " ORDER BY datetime(created_at) DESC LIMIT 500"
        try:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        except Exception:
            rows = []
        conn.close()

        if qtxt:
            rows = [
                r for r in rows
                if qtxt in (r.get("title") or "").lower()
                or qtxt in (r.get("message") or "").lower()
            ]

        self._rows = rows
        self._list.clear()
        for r in rows:
            sev = (r.get("severity") or "info").lower()
            color = _SEVERITY_COLORS.get(sev, C["text2"])
            title = r.get("title") or "—"
            dt = (r.get("created_at") or "")[:16]
            unread_m = "* " if not r.get("is_read") else ""
            it = QListWidgetItem(f"{unread_m}{dt}  {title}")
            it.setData(Qt.ItemDataRole.UserRole, r.get("id"))
            it.setForeground(QColor(color))
            self._list.addItem(it)

        self._detail.clear()
        self._btn_open.setVisible(False)

    def _on_select(self, cur, _prev):
        if not cur:
            return
        nid = cur.data(Qt.ItemDataRole.UserRole)
        row = next((r for r in self._rows if r.get("id") == nid), None)
        if not row:
            return
        msg = (row.get("message") or "").replace("\n", "<br>")
        html = (
            f"<p><b>{row.get('title','')}</b></p>"
            f"<p style='color:#8899AA;font-size:11px'>{row.get('type','')} · "
            f"{row.get('severity','')} · {row.get('created_at','')}</p>"
            f"<p>{msg}</p>"
        )
        self._detail.setHtml(html)
        self._current_action = {
            "related_table": row.get("related_table"),
            "related_id": row.get("related_id"),
            "action_url": row.get("action_url"),
        }
        url = row.get("action_url") or ""
        self._btn_open.setVisible(bool(url))

    def _open_action_target(self):
        url = self._current_action.get("action_url") or ""
        if not url:
            return
        m = re.match(r"citypulse://nav/(\d+)", url, re.I)
        if m:
            self.navigate_request.emit(int(m.group(1)))
            show_toast(self.window(), "Navigation…", "info")
            return
        if url.startswith("http"):
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(url))

    def _on_double_click(self, item):
        nid = item.data(Qt.ItemDataRole.UserRole)
        row = next((r for r in self._rows if r.get("id") == nid), None)
        if not row:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(row.get("title", "Notification"))
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(_dialog_qss() + f"QDialog{{background:{C['bg']};color:{C['text']};}}")
        lo = QVBoxLayout(dlg)
        te = QTextBrowser()
        te.setHtml(self._detail.toHtml())
        lo.addWidget(te)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Fermer")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        if row.get("action_url"):
            nav_btn = QPushButton("Ouvrir la cible")
            nav_btn.setObjectName("primaryBtn")
            nav_btn.clicked.connect(lambda: (self._open_action_target(), dlg.accept()))
            btn_row.addWidget(nav_btn)
        lo.addLayout(btn_row)
        dlg.exec()

        try:
            conn = get_connection()
            conn.execute("UPDATE notifications SET is_read=1 WHERE id= ?", (nid,))
            conn.commit()
            conn.close()
            log_action("NOTIF_READ", f"Notification #{nid} lue")
        except Exception:
            pass
        if self.main_window and hasattr(self.main_window, "_topbar"):
            self.main_window._topbar.bell.refresh_from_db()
        self.refresh_data()

    def _mark_all_read(self):
        try:
            conn = get_connection()
            conn.execute("UPDATE notifications SET is_read=1 WHERE is_read=0")
            conn.commit()
            conn.close()
            log_action("NOTIF_MARK_ALL", "Toutes notifications marquées lues")
            show_toast(self.window(), "Toutes les notifications sont marquées lues.", "success")
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))
        if self.main_window and hasattr(self.main_window, "_topbar"):
            self.main_window._topbar.bell.refresh_from_db()
        self.refresh_data()
