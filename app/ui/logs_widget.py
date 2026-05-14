"""
logs_widget.py — Journal d'audit v2
=====================================
Filtres : niveau + plage de dates | Export CSV | Username résolu
"""
import csv
import logging
import os
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
    QDateEdit, QFileDialog,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QBrush

from ..database.db_manager import get_connection
from .toast import show_toast

logger = logging.getLogger(__name__)

C = {
    "bg": "#0D1B2A", "panel": "#112240", "border": "#1E3A5F",
    "accent": "#00D4FF", "text": "#E8F4FD", "muted": "#8899AA",
}

_LEVEL_COLORS = {
    "ERROR":    "#FF4757",
    "WARNING":  "#FFB800",
    "INFO":     "#00D4FF",
    "DEBUG":    "#8899AA",
    "CRITICAL": "#FF0000",
}

_FLD = (
    f"border:1px solid {C['border']};border-radius:4px;"
    f"padding:4px;background:{C['bg']};color:{C['text']};"
)


class LogsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(8)

        title = QLabel("Journal d'audit")
        title.setObjectName("heading")
        root.addWidget(title)

        # ── Barre de filtres ──────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(8)

        lbl_lvl = QLabel("Niveau :")
        lbl_lvl.setStyleSheet(f"color:{C['muted']};font-size:11px;")
        bar.addWidget(lbl_lvl)
        self._level_cb = QComboBox()
        self._level_cb.addItems(["Tous", "INFO", "WARNING", "ERROR", "DEBUG", "CRITICAL"])
        self._level_cb.setStyleSheet(
            f"QComboBox{{{_FLD}}} QComboBox::drop-down{{border:none;}}"
            f" QComboBox QAbstractItemView{{background:{C['bg']};color:{C['text']};}}"
        )
        self._level_cb.currentIndexChanged.connect(self.refresh_data)
        bar.addWidget(self._level_cb)

        lbl_from = QLabel("Du :")
        lbl_from.setStyleSheet(f"color:{C['muted']};font-size:11px;")
        bar.addWidget(lbl_from)
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addDays(-30))
        self._date_from.setStyleSheet(f"QDateEdit{{{_FLD}}}")
        self._date_from.dateChanged.connect(self.refresh_data)
        bar.addWidget(self._date_from)

        lbl_to = QLabel("Au :")
        lbl_to.setStyleSheet(f"color:{C['muted']};font-size:11px;")
        bar.addWidget(lbl_to)
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setStyleSheet(f"QDateEdit{{{_FLD}}}")
        self._date_to.dateChanged.connect(self.refresh_data)
        bar.addWidget(self._date_to)

        bar.addStretch()

        export_btn = QPushButton("⬇ Export CSV")
        export_btn.setObjectName("secondaryBtn")
        export_btn.clicked.connect(self._export_csv)
        bar.addWidget(export_btn)

        refresh_btn = QPushButton("↺ Actualiser")
        refresh_btn.setObjectName("ghostBtn")
        refresh_btn.clicked.connect(self.refresh_data)
        bar.addWidget(refresh_btn)

        root.addLayout(bar)

        # ── Table ─────────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Date", "Niveau", "Action", "Détails", "Utilisateur"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            f"QTableWidget{{background:{C['bg']};color:{C['text']};"
            f"border:1px solid {C['border']};gridline-color:{C['border']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['muted']};"
            f"border:none;padding:4px;font-size:11px;}}"
            f"QTableWidget::item:alternate{{background:#0a1828;}}"
        )
        root.addWidget(self._table, 1)

        lbl_cnt = QLabel("")
        lbl_cnt.setStyleSheet(f"color:{C['muted']};font-size:10px;")
        self._count_lbl = lbl_cnt
        root.addWidget(lbl_cnt)

    def refresh_data(self):
        try:
            level = self._level_cb.currentText()
            date_from = self._date_from.date().toString("yyyy-MM-dd")
            date_to   = self._date_to.date().toString("yyyy-MM-dd") + " 23:59:59"

            conn = get_connection()
            # Résoudre username via jointure
            base_sql = """
                SELECT l.id, l.action, l.details, l.created_at,
                       COALESCE(l.level, 'INFO') AS level,
                       COALESCE(u.username, CAST(l.user_id AS TEXT), '—') AS username
                FROM logs l
                LEFT JOIN users u ON u.id = l.user_id
                WHERE l.created_at BETWEEN ? AND ?
            """
            params = [date_from, date_to]
            if level != "Tous":
                base_sql += " AND COALESCE(l.level,'INFO') = ?"
                params.append(level)
            base_sql += " ORDER BY l.created_at DESC LIMIT 2000"

            rows = conn.execute(base_sql, params).fetchall()
            conn.close()

            self._table.setRowCount(len(rows))
            self._rows_cache = rows
            for i, r in enumerate(rows):
                lvl = (r["level"] or "INFO").upper()
                color = QColor(_LEVEL_COLORS.get(lvl, C["text"]))
                vals = [
                    (r["created_at"] or "")[:19],
                    lvl,
                    r["action"] or "",
                    r["details"] or "",
                    r["username"] or "—",
                ]
                for j, v in enumerate(vals):
                    item = QTableWidgetItem(str(v))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    if j == 1:
                        item.setForeground(QBrush(color))
                    self._table.setItem(i, j, item)

            self._count_lbl.setText(f"{len(rows)} entrée(s) affichée(s)")
        except Exception:
            logger.exception("Erreur chargement logs")

    def _export_csv(self):
        rows = getattr(self, "_rows_cache", [])
        if not rows:
            show_toast(self.window(), "Aucune donnée à exporter.", "error")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le journal", "journal_audit.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Date", "Niveau", "Action", "Détails", "Utilisateur"])
                for r in rows:
                    w.writerow([
                        (r["created_at"] or "")[:19],
                        (r["level"] or "INFO").upper(),
                        r["action"] or "",
                        r["details"] or "",
                        r["username"] if "username" in r.keys() else "—",
                    ])
            show_toast(self.window(), f"Journal exporté : {os.path.basename(path)}", "success")
        except Exception as e:
            show_toast(self.window(), f"Erreur export : {e}", "error")

    def retranslate_ui(self, lang: str):
        from app.i18n import tr
        if hasattr(self, "_heading"):
            self._heading.setText(tr("page.logs", lang))
