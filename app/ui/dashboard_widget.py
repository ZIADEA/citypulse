"""
dashboard_widget.py v2.0 — Dashboard CityPulse Logistics
=========================================================
Layout :
  En-tête 48px  : Bonjour [full_name] + horloge 1s + indicateurs OSRM/Mistral
  Ligne 1        : 5 KPICards (livraisons, véhicules, ponctualité, coût, CO₂)
  Ligne 2        : charts Matplotlib 60/40 + panneau alertes 280px
  Ligne 3        : QSplitter 65/35 (logs récents | stats rapides)
  Auto-refresh   : 30s + compteur "Mis à jour il y a Xs"
  Empty state    : bouton "Charger données démo"
"""

import json
import logging
import os
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QSplitter, QDialog, QGridLayout, QSpacerItem,
    QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QCursor

from ..database.db_manager import get_connection, log_action
from ..paths import settings_json_path
from .help_dialog import show_help
from .lucide_icons import apply_action_button
from .toast import show_toast
from .components.confirm_dialog import _dialog_qss

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    import numpy as np
    HAS_MPL = True
except Exception:
    HAS_MPL = False

# ── Palette dark ──────────────────────────────────────────────────────────────
C = {
    "bg":      "#0D1B2A",
    "bg2":     "#0A1628",
    "panel":   "#112240",
    "input":   "#1A2E4A",
    "hover":   "#1A3A5C",
    "accent":  "#00D4FF",
    "success": "#00FF88",
    "warning": "#FFB800",
    "danger":  "#FF4757",
    "text":    "#E8F4FD",
    "text2":   "#8899AA",
    "border":  "#1E3A5F",
    "greedy":  "#3B9EE8",
    "twoopt":  "#00FF88",
    "ortools": "#8B5CF6",
    "muted":   "#8899AA",
}

_SETTINGS_PATH = settings_json_path()


def _load_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _algo_color(name: str) -> str:
    n = (name or "").lower()
    if "glouton" in n or "greedy" in n:   return C["greedy"]
    if "2-opt"  in n or "2opt"  in n:     return C["twoopt"]
    if "or-tools" in n or "ortools" in n: return C["ortools"]
    return C["muted"]


# ── Threads ───────────────────────────────────────────────────────────────────
class _IndicatorChecker(QThread):
    """Vérifie OSRM et Mistral hors thread UI."""
    done = pyqtSignal(bool, bool)   # osrm_ok, mistral_ok

    def run(self):
        osrm_ok = mistral_ok = False
        try:
            import requests
            cfg = _load_settings()
            url = cfg.get("osrm", {}).get("url", "http://router.project-osrm.org")
            r = requests.get(url, timeout=2)
            osrm_ok = r.status_code < 500
        except Exception:
            pass
        try:
            import keyring
            key = keyring.get_password("citypulse", "mistral_api_key")
            mistral_ok = bool(key and key.strip())
        except Exception:
            pass
        self.done.emit(osrm_ok, mistral_ok)


class _WeatherChecker(QThread):
    """Récupère météo via weather_service (cache TTL 15 min)."""
    done = pyqtSignal(dict)

    def run(self):
        try:
            from ..services import weather_service as ws
            key = ws.resolve_owm_api_key()
            if not key:
                self.done.emit({})
                return
            cfg = _load_settings()
            lat = float(cfg.get("map", {}).get("default_lat", 33.5731))
            lon = float(cfg.get("map", {}).get("default_lon", -7.5898))
            d = ws.get_current(lat, lon, key)
            if d:
                self.done.emit({
                    "temp":  d.get("temp", 0),
                    "desc":  d.get("description", ""),
                    "icon":  d.get("icon", d.get("main", "")),
                })
                return
        except Exception:
            pass
        self.done.emit({})


# ── Composants locaux ─────────────────────────────────────────────────────────
class _KPICard(QFrame):
    def __init__(self, icon: str, title: str, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 110)
        self._normal = (
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:10px;}}"
        )
        self._hover = (
            f"QFrame{{background:{C['hover']};border:1px solid {C['accent']};"
            "border-radius:10px;}}"
        )
        self.setStyleSheet(self._normal)

        lo = QVBoxLayout(self)
        lo.setContentsMargins(14, 12, 14, 10)
        lo.setSpacing(4)

        hdr = QHBoxLayout()
        ic = QLabel(icon)
        ic.setStyleSheet("font-size:16px;background:transparent;border:none;")
        hdr.addWidget(ic)
        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:10px;font-weight:700;"
            "background:transparent;border:none;"
        )
        hdr.addWidget(self._title_lbl, 1)
        lo.addLayout(hdr)

        self.value_lbl = QLabel("—")
        self.value_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.value_lbl.setStyleSheet(
            f"color:{C['text']};background:transparent;border:none;"
        )
        lo.addWidget(self.value_lbl)

        self.sub_lbl = QLabel()
        self.sub_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:10px;background:transparent;border:none;"
        )
        lo.addWidget(self.sub_lbl)

        self.trend_lbl = QLabel()
        self.trend_lbl.setStyleSheet(
            "font-size:10px;font-weight:600;background:transparent;border:none;"
        )
        lo.addWidget(self.trend_lbl)

    def set_value(self, value: str, sub: str = "", trend: str = "",
                  trend_up: bool = True, neutral: bool = False):
        self.value_lbl.setText(value)
        self.sub_lbl.setText(sub)
        if trend:
            color = C["muted"] if neutral else (C["success"] if trend_up else C["danger"])
            arrow = "=" if neutral else ("+" if trend_up else "-")
            self.trend_lbl.setText(
                f'<span style="color:{color};">{arrow} {trend}</span>'
            )
        else:
            self.trend_lbl.setText("")

    def enterEvent(self, e):
        self.setStyleSheet(self._hover); super().enterEvent(e)

    def leaveEvent(self, e):
        self.setStyleSheet(self._normal); super().leaveEvent(e)


class _ChartFrame(QFrame):
    def __init__(self, title: str, action_text: str = "", action_cb=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:10px;}}"
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(14, 10, 14, 10)
        lo.setSpacing(6)

        hdr = QHBoxLayout()
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:10px;font-weight:700;"
            "background:transparent;border:none;"
        )
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        self._action_btn = None
        if action_text and action_cb:
            btn = QPushButton(action_text)
            self._action_btn = btn
            btn.setStyleSheet(
                f"QPushButton{{color:{C['accent']};background:none;border:none;"
                "font-size:11px;font-weight:600;}}"
                f"QPushButton:hover{{color:{C['text']};}}"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(action_cb)
            hdr.addWidget(btn)
        lo.addLayout(hdr)

        if HAS_MPL:
            self.fig = Figure(facecolor=C["panel"])
            self.fig.subplots_adjust(left=0.12, right=0.97, top=0.92, bottom=0.18)
            self.canvas = FigureCanvas(self.fig)
            self.canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            lo.addWidget(self.canvas)
        else:
            lo.addWidget(QLabel("Matplotlib non disponible"), alignment=Qt.AlignmentFlag.AlignCenter)

    def _ax_style(self, ax):
        ax.set_facecolor(C["input"])
        ax.tick_params(colors=C["text2"], labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(C["border"])
        ax.yaxis.label.set_color(C["muted"])
        ax.yaxis.label.set_size(8)
        ax.xaxis.label.set_color(C["muted"])
        ax.xaxis.label.set_size(8)

    def placeholder(self, msg: str):
        if not HAS_MPL: return
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor(C["input"])
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                color=C["muted"], fontsize=9, transform=ax.transAxes,
                style="italic", linespacing=1.8)
        ax.axis("off")
        self.canvas.draw()


# ── Panneau alertes ───────────────────────────────────────────────────────────
class _AlertsPanel(QFrame):
    navigate = pyqtSignal(int)   # index page

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:10px;}}"
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(12, 10, 12, 10)
        lo.setSpacing(6)

        hdr = QHBoxLayout()
        self._title_lbl = QLabel(" Alertes")
        self._title_lbl.setStyleSheet(
            f"color:{C['text']};font-size:12px;font-weight:700;"
            "background:transparent;border:none;"
        )
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        self._mark_btn = QPushButton(" Tout lu")
        self._mark_btn.setFixedHeight(24)
        self._mark_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:4px;"
            "font-size:10px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{C['success']};border-color:{C['success']};}}"
        )
        self._mark_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mark_btn.clicked.connect(self._mark_all_read)
        hdr.addWidget(self._mark_btn)
        lo.addLayout(hdr)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C['border']};border:none;")
        lo.addWidget(sep)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("background:transparent;border:none;")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_lo = QVBoxLayout(self._list_widget)
        self._list_lo.setContentsMargins(0, 0, 0, 0)
        self._list_lo.setSpacing(4)
        self._list_lo.addStretch()
        self._scroll.setWidget(self._list_widget)
        lo.addWidget(self._scroll, 1)

        # Mini météo (48px, visible si données dispo)
        self._weather_widget = QFrame()
        self._weather_widget.setFixedHeight(48)
        self._weather_widget.setStyleSheet(
            f"QFrame{{background:{C['input']};border:1px solid {C['border']};"
            "border-radius:6px;}}"
        )
        wl = QHBoxLayout(self._weather_widget)
        wl.setContentsMargins(10, 4, 10, 4)
        self._weather_icon = QLabel("")
        self._weather_icon.setStyleSheet("font-size:20px;background:transparent;border:none;")
        wl.addWidget(self._weather_icon)
        wc = QVBoxLayout()
        self._weather_temp = QLabel("—°C")
        self._weather_temp.setStyleSheet(
            f"color:{C['text']};font-size:13px;font-weight:700;"
            "background:transparent;border:none;"
        )
        wc.addWidget(self._weather_temp)
        self._weather_desc = QLabel("—")
        self._weather_desc.setStyleSheet(
            f"color:{C['text2']};font-size:10px;background:transparent;border:none;"
        )
        wc.addWidget(self._weather_desc)
        wl.addLayout(wc)
        wl.addStretch()
        self._weather_widget.setVisible(False)
        lo.addWidget(self._weather_widget)

    def refresh(self, notifs: list):
        # Clear old items (keep stretch at bottom)
        while self._list_lo.count() > 1:
            item = self._list_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not notifs:
            empty = QLabel("Aucune alerte non lue")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{C['muted']};font-size:11px;background:transparent;border:none;padding:12px;"
            )
            self._list_lo.insertWidget(0, empty)
            return

        _SV = {"critical": C["danger"], "warning": C["warning"],
               "info": C["accent"], "success": C["success"]}
        _ICONS = {"critical": "", "warning": "", "info": "", "success": ""}

        for i, n in enumerate(notifs[:15]):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C['input']};border-left:3px solid "
                f"{_SV.get(n.get('severity','info'), C['accent'])};"
                "border-top-right-radius:4px;border-bottom-right-radius:4px;padding:0;}}"
                f"QFrame:hover{{background:{C['hover']};}}"
            )
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            cl.setSpacing(2)

            top_row = QHBoxLayout()
            ic = QLabel(_ICONS.get(n.get("severity", "info"), ""))
            ic.setStyleSheet("font-size:11px;background:transparent;border:none;")
            top_row.addWidget(ic)
            t = QLabel(n.get("title", "")[:30])
            t.setStyleSheet(
                f"color:{C['text']};font-size:11px;font-weight:600;"
                "background:transparent;border:none;"
            )
            top_row.addWidget(t, 1)
            ts = QLabel((n.get("created_at") or "")[:10])
            ts.setStyleSheet(
                f"color:{C['muted']};font-size:9px;background:transparent;border:none;"
            )
            top_row.addWidget(ts)
            cl.addLayout(top_row)

            if n.get("message"):
                msg = QLabel(n["message"][:55] + ("…" if len(n.get("message","")) > 55 else ""))
                msg.setStyleSheet(
                    f"color:{C['text2']};font-size:10px;background:transparent;border:none;"
                )
                cl.addWidget(msg)

            # Click → navigate if related_table
            idx = _table_to_nav(n.get("related_table", ""))
            if idx >= 0:
                def _go(_, page=idx): self.navigate.emit(page)
                card.mousePressEvent = _go
            self._list_lo.insertWidget(i, card)

    def update_weather(self, data: dict):
        if not data:
            self._weather_widget.setVisible(False)
            return
        icons = {
            "Clear": "", "Clouds": "", "Rain": "",
            "Drizzle": "", "Snow": "", "Thunderstorm": "",
            "Mist": "", "Haze": "",
        }
        self._weather_icon.setText(icons.get(data.get("icon",""), ""))
        self._weather_temp.setText(f"{data.get('temp','—')}°C")
        self._weather_desc.setText(data.get("desc", "—"))
        self._weather_widget.setVisible(True)

    def _mark_all_read(self):
        try:
            conn = get_connection()
            conn.execute("UPDATE notifications SET is_read=1")
            conn.commit()
            conn.close()
            log_action("NOTIF_CLEAR", "Toutes les notifications marquées lues")
            self.refresh([])
        except Exception:
            pass


def _table_to_nav(table: str) -> int:
    _MAP = {
        "clients": 1, "vehicles": 2, "drivers": 3, "depots": 4,
        "orders": 5, "carriers": 6, "routes": 9, "route_stops": 9,
        "scenarios": 10, "logs": 13, "algo_results": 7, "anomalies": 5,
    }
    return _MAP.get((table or "").lower(), -1)


# ── Dialog Analyser patterns ──────────────────────────────────────────────────
class _RouteAnalyzerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(" Analyse des patterns de tournées")
        self.setMinimumSize(700, 480)
        self.setStyleSheet(
            _dialog_qss() + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(20, 20, 20, 20)
        lo.setSpacing(14)

        title = QLabel("Analyse des patterns — 30 derniers jours")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['text']};background:transparent;border:none;")
        lo.addWidget(title)

        if HAS_MPL:
            fig = Figure(figsize=(7, 4), facecolor=C["panel"])
            fig.subplots_adjust(left=0.1, right=0.97, top=0.90, bottom=0.14, wspace=0.35)
            canvas = FigureCanvas(fig)
            lo.addWidget(canvas)

            try:
                conn = get_connection()
                d30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                rows = conn.execute(
                    "SELECT algorithm, total_distance, cost_total, on_time_rate, respect_rate, created_at "
                    "FROM algo_results WHERE created_at >= ? ORDER BY created_at",
                    (d30,)
                ).fetchall()
                conn.close()

                by_algo: dict = {}
                for r in rows:
                    a = (r[0] or "").split("(")[0].strip()[:12]
                    by_algo.setdefault(a, {"dist": [], "cost": [], "rate": []})
                    by_algo[a]["dist"].append(r[1] or 0)
                    by_algo[a]["cost"].append(r[2] or 0)
                    by_algo[a]["rate"].append(r[3] or r[4] or 0)

                ax1 = fig.add_subplot(131)
                ax2 = fig.add_subplot(132)
                ax3 = fig.add_subplot(133)
                for ax in (ax1, ax2, ax3):
                    ax.set_facecolor(C["input"])
                    ax.tick_params(colors=C["text2"], labelsize=7)
                    ax.spines["top"].set_visible(False)
                    ax.spines["right"].set_visible(False)
                    for sp in ("left", "bottom"):
                        ax.spines[sp].set_color(C["border"])

                algos = list(by_algo.keys())
                x = range(len(algos))
                colors = [_algo_color(a) for a in algos]

                ax1.bar(x, [sum(v["dist"])/max(len(v["dist"]),1) for v in by_algo.values()],
                        color=colors, alpha=0.85)
                ax1.set_xticks(list(x)); ax1.set_xticklabels(algos, fontsize=6, color=C["text2"])
                ax1.set_title("Dist. moy. (km)", fontsize=8, color=C["text2"])

                ax2.bar(x, [sum(v["cost"])/max(len(v["cost"]),1) for v in by_algo.values()],
                        color=colors, alpha=0.85)
                ax2.set_xticks(list(x)); ax2.set_xticklabels(algos, fontsize=6, color=C["text2"])
                ax2.set_title("Coût moy. (€)", fontsize=8, color=C["text2"])

                ax3.bar(x, [sum(v["rate"])/max(len(v["rate"]),1) for v in by_algo.values()],
                        color=colors, alpha=0.85)
                ax3.set_xticks(list(x)); ax3.set_xticklabels(algos, fontsize=6, color=C["text2"])
                ax3.set_title("Ponctualité (%)", fontsize=8, color=C["text2"])

                canvas.draw()
            except Exception:
                logger.exception("RouteAnalyzerDialog chart error")

        # Stats table
        try:
            conn = get_connection()
            d30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            rows = conn.execute(
                "SELECT algorithm, COUNT(*), AVG(total_distance), AVG(cost_total), AVG(COALESCE(on_time_rate, respect_rate)) "
                "FROM algo_results WHERE created_at >= ? GROUP BY algorithm",
                (d30,)
            ).fetchall()
            conn.close()

            tbl = QTableWidget(len(rows), 5)
            tbl.setHorizontalHeaderLabels(
                ["Algorithme", "Runs", "Dist. moy. (km)", "Coût moy. (€)", "Ponctualité (%)"]
            )
            tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            tbl.setAlternatingRowColors(True)
            tbl.setMaximumHeight(180)
            tbl.verticalHeader().setDefaultSectionSize(28)
            for i, r in enumerate(rows):
                vals = [
                    r[0] or "",
                    str(r[1]),
                    f"{r[2]:.1f}" if r[2] else "—",
                    f"{r[3]:.1f}" if r[3] else "—",
                    f"{r[4]:.1f}" if r[4] else "—",
                ]
                for j, v in enumerate(vals):
                    item = QTableWidgetItem(v)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    tbl.setItem(i, j, item)
            lo.addWidget(tbl)
        except Exception:
            pass

        close = QPushButton("Fermer")
        close.setObjectName("secondaryBtn")
        close.setFixedHeight(34)
        close.clicked.connect(self.accept)
        lo.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)


# ═══════════════════════════════════════════════════════════════════════════════
# DashboardWidget
# ═══════════════════════════════════════════════════════════════════════════════
class DashboardWidget(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._convergence_data: list = []
        self._last_refresh: datetime | None = None
        self._threads: list = []
        self._current_lang = "fr"

        # Horloge 1s
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick)
        self._clock_timer.start(1000)

        # Auto-refresh 30s
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_data)
        self._refresh_timer.start(30_000)

        self._setup_ui()
        # Différer le chargement des données après le premier rendu du widget
        QTimer.singleShot(0, self.refresh_data)
        QTimer.singleShot(200, self._check_indicators)

    # ── Construction UI ──────────────────────────────────────────────────────
    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background:{C['bg']};border:none;")

        container = QWidget()
        container.setObjectName("dashContainer")
        container.setStyleSheet(f"QWidget#dashContainer{{background:{C['bg']};}}")
        main = QVBoxLayout(container)
        main.setContentsMargins(4, 8, 4, 16)
        main.setSpacing(18)

        # ── En-tête 48px ──────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:10px;}}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 0, 18, 0)
        hl.setSpacing(12)

        self._greeting_lbl = QLabel("Bonjour !")
        self._greeting_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._greeting_lbl.setStyleSheet(
            f"color:{C['text']};background:transparent;border:none;"
        )
        hl.addWidget(self._greeting_lbl)

        hl.addStretch()

        self._clock_lbl = QLabel()
        self._clock_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:12px;background:transparent;border:none;"
        )
        hl.addWidget(self._clock_lbl)

        hl.addSpacing(16)

        # Indicateurs
        self._osrm_lbl  = self._make_indicator("OSRM",   "Attente")
        self._mistral_lbl = self._make_indicator("Mistral", "Attente")
        hl.addWidget(self._osrm_lbl)
        hl.addSpacing(8)
        hl.addWidget(self._mistral_lbl)

        hl.addSpacing(16)

        # Refresh info + bouton
        self._age_lbl = QLabel()
        self._age_lbl.setStyleSheet(
            f"color:{C['muted']};font-size:10px;background:transparent;border:none;"
        )
        hl.addWidget(self._age_lbl)

        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setToolTip("Actualiser maintenant")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['accent']};"
            f"border:1px solid {C['border']};border-radius:6px;font-size:14px;}}"
            f"QPushButton:hover{{background:{C['hover']};}}"
        )
        refresh_btn.clicked.connect(self.refresh_data)
        hl.addWidget(refresh_btn)

        help_btn = QPushButton()
        help_btn.setFixedSize(30, 30)
        help_btn.setToolTip("Aide — Tableau de bord")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(help_btn, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        help_btn.clicked.connect(lambda: show_help(self, "dashboard"))
        hl.addWidget(help_btn)

        main.addWidget(header)

        # ── Empty state (caché si données) ────────────────────────────────
        self._empty_frame = self._build_empty_state()
        main.addWidget(self._empty_frame)
        self._empty_frame.setVisible(False)

        # ── Bandeau anomalies ─────────────────────────────────────────────
        self._anomaly_bar = QFrame()
        self._anomaly_bar.setVisible(False)
        self._anomaly_bar.setStyleSheet(
            f"QFrame{{background:rgba(255,184,0,20);border:1px solid {C['warning']};"
            "border-radius:8px;}}"
        )
        abl = QHBoxLayout(self._anomaly_bar)
        abl.setContentsMargins(12, 6, 12, 6)
        abl.setSpacing(10)
        _wi = QLabel("")
        _wi.setStyleSheet(f"color:{C['warning']};font-size:16px;background:transparent;border:none;")
        abl.addWidget(_wi)
        self._anomaly_lbl = QLabel()
        self._anomaly_lbl.setStyleSheet(
            f"color:{C['warning']};font-size:12px;background:transparent;border:none;"
        )
        abl.addWidget(self._anomaly_lbl, 1)
        _ab = QPushButton("Voir →")
        _ab.setStyleSheet(
            f"background:{C['warning']};color:#0D1B2A;border:none;"
            "border-radius:5px;padding:3px 10px;font-size:11px;font-weight:600;"
        )
        _ab.clicked.connect(lambda: self.main_window._nav_to(5))
        abl.addWidget(_ab)
        main.addWidget(self._anomaly_bar)

        # ── Ligne 1 : 5 KPIs ─────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        self._kpi_livr    = _KPICard("", "Livraisons aujourd'hui")
        self._kpi_veh     = _KPICard("", "Véhicules actifs")
        self._kpi_ponct   = _KPICard("Temps", "Taux ponctualité")
        self._kpi_cost    = _KPICard("", "Coût moyen tournée")
        self._kpi_co2     = _KPICard("", "CO₂ économisé")
        for kpi in (self._kpi_livr, self._kpi_veh, self._kpi_ponct,
                    self._kpi_cost, self._kpi_co2):
            kpi_row.addWidget(kpi)
        main.addLayout(kpi_row)

        # ── Ligne 2 : charts + alertes ────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        # Charts 60/40 dans un QSplitter
        chart_splitter = QSplitter(Qt.Orientation.Horizontal)
        chart_splitter.setStyleSheet(
            "QSplitter::handle{background:#1E3A5F;width:4px;}"
        )

        self._chart_activity = _ChartFrame(
            "LIVRAISONS / DISTANCE — 7 DERNIERS JOURS",
            action_text="Voir suivi →",
            action_cb=lambda: self.main_window._nav_to(9),
        )
        self._chart_activity.setMinimumHeight(230)
        chart_splitter.addWidget(self._chart_activity)

        self._chart_algos = _ChartFrame(
            "COMPARAISON ALGORITHMES (7J)",
            action_text="Optimiser →",
            action_cb=lambda: self.main_window._nav_to(7),
        )
        self._chart_algos.setMinimumHeight(230)
        chart_splitter.addWidget(self._chart_algos)

        chart_splitter.setSizes([600, 400])
        row2.addWidget(chart_splitter, 1)

        # Panneau alertes fixe 280px
        self._alerts = _AlertsPanel()
        self._alerts.navigate.connect(self.main_window._nav_to)
        row2.addWidget(self._alerts)

        main.addLayout(row2)

        # ── Ligne 3 : logs + stats rapides ───────────────────────────────
        row3_splitter = QSplitter(Qt.Orientation.Horizontal)
        row3_splitter.setStyleSheet(
            "QSplitter::handle{background:#1E3A5F;width:4px;}"
        )

        # Tableau activité récente (65%)
        logs_frame = QFrame()
        logs_frame.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:10px;}}"
        )
        lfl = QVBoxLayout(logs_frame)
        lfl.setContentsMargins(14, 10, 14, 10)
        lfl.setSpacing(6)

        lfhdr = QHBoxLayout()
        self._logs_title_lbl = QLabel(" ACTIVITÉ RÉCENTE")
        self._logs_title_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:10px;font-weight:700;"
            "background:transparent;border:none;"
        )
        lfhdr.addWidget(self._logs_title_lbl)
        lfhdr.addStretch()
        logs_nav = QPushButton("Journal complet →")
        self._logs_nav_btn = logs_nav
        logs_nav.setStyleSheet(
            f"QPushButton{{color:{C['accent']};background:none;border:none;"
            "font-size:11px;font-weight:600;}}"
            f"QPushButton:hover{{color:{C['text']};}}"
        )
        logs_nav.setCursor(Qt.CursorShape.PointingHandCursor)
        logs_nav.clicked.connect(lambda: self.main_window._nav_to(13))
        lfhdr.addWidget(logs_nav)
        lfl.addLayout(lfhdr)

        self._logs_table = QTableWidget()
        self._logs_table.setColumnCount(3)
        self._logs_table.setHorizontalHeaderLabels(["Date", "Action", "Détails"])
        self._logs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._logs_table.setAlternatingRowColors(True)
        self._logs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._logs_table.verticalHeader().setDefaultSectionSize(28)
        self._logs_table.setMaximumHeight(240)
        lfl.addWidget(self._logs_table)
        row3_splitter.addWidget(logs_frame)

        # Stats rapides (35%)
        stats_frame = QFrame()
        stats_frame.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:10px;}}"
        )
        sfl = QVBoxLayout(stats_frame)
        sfl.setContentsMargins(14, 12, 14, 12)
        sfl.setSpacing(10)

        self._stats_title_lbl = QLabel(" STATS RAPIDES")
        self._stats_title_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:10px;font-weight:700;"
            "background:transparent;border:none;"
        )
        sfl.addWidget(self._stats_title_lbl)

        self._stat_forecast   = self._stat_row("", "Prévision J+1", "—")
        self._stat_pending    = self._stat_row("", "Commandes en attente", "—")
        self._stat_veh_dispo  = self._stat_row("", "Véhicules dispo demain", "—")
        self._stat_alerts     = self._stat_row("", "Alertes non lues", "—")

        for row_w in (self._stat_forecast, self._stat_pending,
                      self._stat_veh_dispo, self._stat_alerts):
            sfl.addWidget(row_w)

        sfl.addStretch()

        self._analyze_btn = QPushButton(" Analyser patterns")
        self._analyze_btn.setObjectName("primaryBtn")
        self._analyze_btn.setFixedHeight(36)
        self._analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._analyze_btn.clicked.connect(self._open_analyzer)
        sfl.addWidget(self._analyze_btn)

        row3_splitter.addWidget(stats_frame)
        row3_splitter.setSizes([650, 350])
        main.addWidget(row3_splitter)

        main.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _make_indicator(self, label: str, icon: str) -> QLabel:
        lbl = QLabel(f"{icon} {label}")
        lbl.setStyleSheet(
            f"color:{C['muted']};font-size:11px;background:transparent;border:none;"
        )
        return lbl

    def _build_empty_state(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:2px dashed {C['border']};"
            "border-radius:12px;}}"
        )
        lo = QVBoxLayout(f)
        lo.setContentsMargins(40, 40, 40, 40)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.setSpacing(12)

        ic = QLabel("")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("font-size:52px;background:transparent;border:none;")
        lo.addWidget(ic)

        title = QLabel("Aucune donnée disponible")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{C['text']};background:transparent;border:none;"
        )
        lo.addWidget(title)

        sub = QLabel(
            "Chargez des clients, véhicules et dépôts, puis lancez une optimisation."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{C['text2']};font-size:12px;background:transparent;border:none;"
        )
        lo.addWidget(sub)

        btn = QPushButton(" Charger données démo")
        btn.setObjectName("primaryBtn")
        btn.setFixedSize(220, 38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._load_demo)
        lo.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return f

    def _stat_row(self, icon: str, label: str, value: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet("background:transparent;border:none;")
        row = QHBoxLayout(f)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        ic = QLabel(icon)
        ic.setStyleSheet("font-size:14px;background:transparent;border:none;")
        ic.setFixedWidth(20)
        row.addWidget(ic)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{C['text2']};font-size:12px;background:transparent;border:none;"
        )
        row.addWidget(lbl, 1)
        val = QLabel(value)
        val.setStyleSheet(
            f"color:{C['text']};font-size:12px;font-weight:700;"
            "background:transparent;border:none;"
        )
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(val)
        f._value_lbl = val    # type: ignore[attr-defined]
        f._label_lbl  = lbl   # type: ignore[attr-defined]
        return f

    # ── Refresh ───────────────────────────────────────────────────────────────
    def refresh_data(self):
        try:
            conn = get_connection()

            has_clients = conn.execute(
                "SELECT COUNT(*) FROM clients WHERE archived=0"
            ).fetchone()[0] > 0
            has_results = conn.execute(
                "SELECT COUNT(*) FROM algo_results"
            ).fetchone()[0] > 0

            self._empty_frame.setVisible(not has_clients and not has_results)

            self._refresh_kpis(conn)
            self._refresh_anomalies(conn)
            self._refresh_charts(conn)
            self._refresh_alerts(conn)
            self._refresh_logs(conn)
            self._refresh_stats(conn)
            conn.close()

            self._last_refresh = datetime.now()
        except Exception:
            logger.exception("Erreur refresh_data dashboard")

    def _refresh_kpis(self, conn):
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        d7 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        d14 = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

        # KPI 1 : Livraisons aujourd'hui
        try:
            delivered = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE DATE(scheduled_date)= ? AND status='delivered' AND archived=0",
                (today,)
            ).fetchone()[0]
            total_today = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE DATE(scheduled_date)= ? AND archived=0",
                (today,)
            ).fetchone()[0]
            deliv_yest = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE DATE(scheduled_date)= ? AND status='delivered' AND archived=0",
                (yesterday,)
            ).fetchone()[0]
            pct = f"{delivered}/{total_today}" if total_today else "0"
            trend = ""
            if deliv_yest > 0:
                delta = ((delivered - deliv_yest) / deliv_yest) * 100
                trend = f"{abs(delta):.0f}% vs hier"
                self._kpi_livr.set_value(pct, f"total : {total_today}", trend, delta >= 0)
            else:
                self._kpi_livr.set_value(pct, f"total : {total_today}")
        except Exception:
            self._kpi_livr.set_value("—")

        # KPI 2 : Véhicules actifs
        try:
            active = conn.execute(
                "SELECT COUNT(*) FROM vehicles WHERE status='en service'"
            ).fetchone()[0]
            total_veh = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
            self._kpi_veh.set_value(
                str(active), f"total : {total_veh}",
                f"{active}/{total_veh}",
                True, neutral=(active == 0)
            )
        except Exception:
            self._kpi_veh.set_value("—")

        # KPI 3 : Taux ponctualité 7j
        try:
            rate = conn.execute(
                "SELECT AVG(COALESCE(on_time_rate, respect_rate, 0)) FROM algo_results "
                "WHERE created_at >= ?", (d7,)
            ).fetchone()[0] or 0
            rate_prev = conn.execute(
                "SELECT AVG(COALESCE(on_time_rate, respect_rate, 0)) FROM algo_results "
                "WHERE created_at >= ? AND created_at < ?", (d14, d7)
            ).fetchone()[0] or 0
            trend = ""
            trend_up = True
            if rate_prev > 0:
                delta = rate - rate_prev
                trend = f"{abs(delta):.1f}pt vs S-1"
                trend_up = delta >= 0
            self._kpi_ponct.set_value(f"{rate:.1f}%", "7 jours glissants", trend, trend_up)
        except Exception:
            self._kpi_ponct.set_value("—")

        # KPI 4 : Coût moyen 7j
        try:
            cost7 = conn.execute(
                "SELECT AVG(COALESCE(cost_total, 0)) FROM algo_results WHERE created_at >= ?",
                (d7,)
            ).fetchone()[0] or 0
            cost_prev = conn.execute(
                "SELECT AVG(COALESCE(cost_total, 0)) FROM algo_results "
                "WHERE created_at >= ? AND created_at < ?", (d14, d7)
            ).fetchone()[0] or 0
            trend = ""
            trend_up = False
            if cost_prev > 0:
                delta_pct = ((cost7 - cost_prev) / cost_prev) * 100
                trend = f"{abs(delta_pct):.1f}% vs S-1"
                trend_up = delta_pct < 0   # coût moins = mieux
            self._kpi_cost.set_value(f"{cost7:.0f} €", "par tournée, 7j", trend, trend_up)
        except Exception:
            self._kpi_cost.set_value("—")

        # KPI 5 : CO₂ économisé (OR-Tools vs Greedy)
        try:
            rows = conn.execute(
                "SELECT algorithm, AVG(COALESCE(co2_total, 0)) FROM algo_results "
                "WHERE created_at >= ? AND co2_total > 0 GROUP BY algorithm",
                (d7,)
            ).fetchall()
            greedy_co2 = ortools_co2 = 0.0
            for r in rows:
                n = (r[0] or "").lower()
                if "greedy" in n or "glouton" in n:
                    greedy_co2 = r[1]
                elif "or-tools" in n or "ortools" in n:
                    ortools_co2 = r[1]
            saved = max(0.0, greedy_co2 - ortools_co2)
            self._kpi_co2.set_value(
                f"{saved:.1f} kg",
                "OR-Tools vs Greedy, 7j",
                "Optimisé" if saved > 0 else "",
                True, neutral=(saved == 0)
            )
        except Exception:
            self._kpi_co2.set_value("—")

    def _refresh_anomalies(self, conn):
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM anomalies WHERE created_at >= ?",
                ((datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),)
            ).fetchone()[0]
            if count > 0:
                self._anomaly_lbl.setText(
                    f"{count} anomalie(s) détectée(s) sur 7 jours — "
                    "Vérifiez les résultats d'optimisation."
                )
                self._anomaly_bar.setVisible(True)
            else:
                self._anomaly_bar.setVisible(False)
        except Exception:
            self._anomaly_bar.setVisible(False)

    def _refresh_alerts(self, conn):
        try:
            rows = conn.execute(
                "SELECT type, severity, title, message, related_table, related_id, created_at "
                "FROM notifications WHERE is_read=0 ORDER BY created_at DESC LIMIT 15"
            ).fetchall()
            notifs = [
                {
                    "type": r[0], "severity": r[1], "title": r[2],
                    "message": r[3], "related_table": r[4],
                    "related_id": r[5], "created_at": r[6],
                }
                for r in rows
            ]
            self._alerts.refresh(notifs)
        except Exception:
            self._alerts.refresh([])

    def _refresh_logs(self, conn):
        try:
            rows = conn.execute(
                "SELECT created_at, action, details FROM logs ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        except Exception:
            rows = []

        self._logs_table.setRowCount(len(rows))
        _ACTION_COLOR = {
            "ERROR": C["danger"], "LOGIN": C["success"], "LOGOUT": C["warning"],
            "OPTIMIZE": C["accent"], "SESSION_START": C["success"],
        }
        for i, r in enumerate(rows):
            date_str = (r[0] or "")[:16]
            action   = r[1] or ""
            details  = r[2] or ""
            color = _ACTION_COLOR.get(action.split("_")[0], C["text2"])
            for j, (val, fg) in enumerate([
                (date_str, C["muted"]),
                (action[:24], color),
                (details[:80], C["text"]),
            ]):
                item = QTableWidgetItem(val)
                item.setForeground(QColor(fg))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._logs_table.setItem(i, j, item)

    def _refresh_stats(self, conn):
        # Commandes en attente
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE status='pending' AND archived=0"
            ).fetchone()[0]
            self._stat_pending._value_lbl.setText(str(pending))
        except Exception:
            self._stat_pending._value_lbl.setText("—")

        # Véhicules dispo demain
        try:
            dispo = conn.execute(
                "SELECT COUNT(*) FROM vehicles WHERE status='disponible'"
            ).fetchone()[0]
            self._stat_veh_dispo._value_lbl.setText(str(dispo))
        except Exception:
            self._stat_veh_dispo._value_lbl.setText("—")

        # Alertes non lues
        try:
            unread = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE is_read=0"
            ).fetchone()[0]
            self._stat_alerts._value_lbl.setText(str(unread))
        except Exception:
            self._stat_alerts._value_lbl.setText("—")

        # Prévision J+1 (série chargée ici — moteur sans BDD)
        try:
            from ..ai.demand_forecast import forecast_from_algo_results_history
            rows = conn.execute(
                """SELECT DATE(created_at) as day, SUM(client_count) as total_clients
                   FROM algo_results
                   GROUP BY DATE(created_at)
                   ORDER BY day ASC
                   LIMIT 60"""
            ).fetchall()
            historical = [
                {"date": r["day"], "actual": int(r["total_clients"] or 0)}
                for r in rows
            ]
            fc = forecast_from_algo_results_history(historical, days_ahead=1)
            forecasts = fc.get("forecast", [])
            if forecasts:
                pred = forecasts[0].get("predicted", 0)
                self._stat_forecast._value_lbl.setText(f"~{pred:.0f} clients")
            else:
                self._stat_forecast._value_lbl.setText("—")
        except Exception:
            self._stat_forecast._value_lbl.setText("—")

    # ── Charts ────────────────────────────────────────────────────────────────
    def _refresh_charts(self, conn):
        if not HAS_MPL:
            return
        d7 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        self._draw_activity_chart(conn, d7)
        self._draw_algo_chart(conn, d7)

    def _draw_activity_chart(self, conn, d7: str):
        """Barres nb livraisons/j + courbe distance/j sur 7 jours."""
        # Construire la liste des 7 derniers jours
        days = [
            (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(6, -1, -1)
        ]
        labels = [
            (datetime.now() - timedelta(days=i)).strftime("%a %d")
            for i in range(6, -1, -1)
        ]
        deliv_by_day = {d: 0 for d in days}
        dist_by_day  = {d: 0.0 for d in days}

        # 2 requêtes GROUP BY au lieu de 14 requêtes individuelles
        try:
            for row in conn.execute(
                "SELECT DATE(scheduled_date) as d, COUNT(*) FROM orders "
                "WHERE DATE(scheduled_date) >= ? AND status='delivered' GROUP BY d",
                (d7,)
            ).fetchall():
                if row[0] in deliv_by_day:
                    deliv_by_day[row[0]] = row[1]
        except Exception:
            pass
        try:
            for row in conn.execute(
                "SELECT DATE(created_at) as d, COALESCE(SUM(total_distance), 0) "
                "FROM algo_results WHERE DATE(created_at) >= ? GROUP BY d",
                (d7,)
            ).fetchall():
                if row[0] in dist_by_day:
                    dist_by_day[row[0]] = float(row[1] or 0)
        except Exception:
            pass

        deliveries = [deliv_by_day[d] for d in days]
        distances  = [dist_by_day[d]  for d in days]

        self._chart_activity.fig.clear()
        if not any(deliveries) and not any(distances):
            self._chart_activity.placeholder("Aucune activité sur 7 jours\nLancez des optimisations")
            return

        ax1 = self._chart_activity.fig.add_subplot(111)
        self._chart_activity._ax_style(ax1)
        x = np.arange(len(labels))

        bars = ax1.bar(x, deliveries, color=C["accent"], alpha=0.75, width=0.5,
                       label="Livraisons")
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, fontsize=7, color=C["text2"])
        ax1.set_ylabel("Livraisons", fontsize=8, color=C["accent"])
        ax1.tick_params(axis="y", colors=C["accent"])

        # Axe secondaire : distance
        if any(distances):
            ax2 = ax1.twinx()
            ax2.plot(x, distances, color=C["warning"], linewidth=2,
                     marker="o", markersize=4, label="Distance (km)")
            ax2.set_ylabel("Distance (km)", fontsize=8, color=C["warning"])
            ax2.tick_params(axis="y", colors=C["warning"], labelsize=7)
            ax2.spines["right"].set_color(C["border"])
            ax2.spines["top"].set_visible(False)

        ax1.legend(loc="upper left", fontsize=7, framealpha=0, labelcolor=C["text2"])
        self._chart_activity.canvas.draw()

    def _draw_algo_chart(self, conn, d7: str):
        """Barres groupées Greedy / 2-opt / OR-Tools : distance + coût moy."""
        try:
            rows = conn.execute(
                "SELECT algorithm, AVG(total_distance), AVG(COALESCE(cost_total,0)) "
                "FROM algo_results WHERE created_at >= ? GROUP BY algorithm",
                (d7,)
            ).fetchall()
        except Exception:
            rows = []

        if not rows:
            self._chart_algos.placeholder("Aucune donnée d'algo sur 7j\nLancez des optimisations")
            return

        algos  = [(r[0] or "").split("(")[0].strip()[:14] for r in rows]
        dists  = [r[1] or 0 for r in rows]
        costs  = [r[2] or 0 for r in rows]
        colors = [_algo_color(a) for a in algos]
        x = np.arange(len(algos))
        w = 0.36

        self._chart_algos.fig.clear()
        ax = self._chart_algos.fig.add_subplot(111)
        self._chart_algos._ax_style(ax)

        b1 = ax.bar(x - w/2, dists, width=w, color=colors, alpha=0.9, label="Distance (km)")
        b2 = ax.bar(x + w/2, costs, width=w, color=colors, alpha=0.45, label="Coût (€)")

        ax.set_xticks(x)
        ax.set_xticklabels(algos, fontsize=7, color=C["text2"])
        ax.legend(fontsize=7, framealpha=0, labelcolor=C["text2"])

        for bar in b1:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.5,
                        f"{h:.0f}", ha="center", va="bottom",
                        fontsize=6, color=C["text2"])

        self._chart_algos.canvas.draw()

    # ── Indicateurs OSRM / Mistral ────────────────────────────────────────────
    def _check_indicators(self):
        t = _IndicatorChecker(self)
        t.done.connect(self._on_indicators)
        self._threads.append(t)
        t.start()

        w = _WeatherChecker(self)
        w.done.connect(self._alerts.update_weather)
        self._threads.append(w)
        w.start()

    def _on_indicators(self, osrm_ok: bool, mistral_ok: bool):
        self._osrm_lbl.setText(
            f"{'' if osrm_ok else ''} OSRM"
        )
        self._osrm_lbl.setStyleSheet(
            f"color:{'#00FF88' if osrm_ok else '#FF4757'};"
            "font-size:11px;background:transparent;border:none;"
        )
        self._mistral_lbl.setText(
            f"{'' if mistral_ok else ''} Mistral"
        )
        self._mistral_lbl.setStyleSheet(
            f"color:{'#00FF88' if mistral_ok else '#FF4757'};"
            "font-size:11px;background:transparent;border:none;"
        )

    # ── Utilitaires ──────────────────────────────────────────────────────────
    def retranslate_ui(self, lang: str):
        from app.i18n import tr
        self._current_lang = lang
        if hasattr(self, "_kpi_livr"):
            self._kpi_livr._title_lbl.setText(tr("dash.kpi.deliveries", lang).upper())
            self._kpi_veh._title_lbl.setText(tr("dash.kpi.vehicles", lang).upper())
            self._kpi_ponct._title_lbl.setText(tr("dash.kpi.punctuality", lang).upper())
            self._kpi_cost._title_lbl.setText(tr("dash.kpi.avg_cost", lang).upper())
            self._kpi_co2._title_lbl.setText(tr("dash.kpi.co2", lang).upper())
        if hasattr(self, "_chart_activity"):
            self._chart_activity._title_lbl.setText(tr("dash.chart.activity", lang))
            if self._chart_activity._action_btn:
                self._chart_activity._action_btn.setText(tr("dash.action.tracking", lang))
            self._chart_algos._title_lbl.setText(tr("dash.chart.algos", lang))
            if self._chart_algos._action_btn:
                self._chart_algos._action_btn.setText(tr("dash.action.optimize", lang))
        if hasattr(self, "_logs_title_lbl"):
            self._logs_title_lbl.setText(f" {tr('dash.logs.title', lang)}")
            self._logs_nav_btn.setText(tr("dash.logs.link", lang))
            self._logs_table.setHorizontalHeaderLabels([
                tr("dash.logs.col.date", lang),
                tr("dash.logs.col.action", lang),
                tr("dash.logs.col.detail", lang),
            ])
        if hasattr(self, "_stats_title_lbl"):
            self._stats_title_lbl.setText(f" {tr('dash.stats.title', lang)}")
        if hasattr(self, "_stat_forecast"):
            self._stat_forecast._label_lbl.setText(tr("dash.stats.forecast", lang))
            self._stat_pending._label_lbl.setText(tr("dash.stats.pending", lang))
            self._stat_veh_dispo._label_lbl.setText(tr("dash.stats.veh_dispo", lang))
            self._stat_alerts._label_lbl.setText(tr("dash.stats.alerts", lang))
        if hasattr(self, "_alerts"):
            self._alerts._title_lbl.setText(f" {tr('dash.alerts.title', lang)}")
            self._alerts._mark_btn.setText(f" {tr('dash.alerts.mark_read', lang)}")
        if hasattr(self, "_analyze_btn"):
            self._analyze_btn.setText(f" {tr('dash.btn.analyze', lang)}")

    def _tick(self):
        from app.i18n import tr
        u = self.main_window.current_user if hasattr(self.main_window, "current_user") else None
        name = (u or {}).get("full_name") or (u or {}).get("username", "")
        now = datetime.now()
        lang = getattr(self, "_current_lang", "fr")
        greeting = tr("dash.greeting.evening", lang) if now.hour >= 19 else tr("dash.greeting.day", lang)
        self._greeting_lbl.setText(f"{greeting}, {name} !" if name else f"{greeting} !")
        self._clock_lbl.setText(now.strftime("%a %d %b %Y — %H:%M:%S"))

        if self._last_refresh:
            secs = int((now - self._last_refresh).total_seconds())
            self._age_lbl.setText(f"⟳ Mis à jour il y a {secs}s")

    def _load_demo(self):
        try:
            from .demo_loader import load_demo_scenario
            load_demo_scenario(self.main_window)
        except Exception as e:
            show_toast(self.window(), f"Erreur : {e}", "error")

    def _open_analyzer(self):
        dlg = _RouteAnalyzerDialog(self)
        dlg.exec()

    def update_convergence(self, data: list):
        """Appelé par OptimizationWidget après un run 2-opt."""
        self._convergence_data = data

    def _set_stat(self, frame: QFrame, value: str):
        frame._value_lbl.setText(value)  # type: ignore[attr-defined]
