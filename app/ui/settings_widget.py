"""
settings_widget.py — Paramètres : 5 onglets, sauvegarde JSON.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3

logger = logging.getLogger(__name__)

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QFormLayout, QSpinBox, QComboBox, QLineEdit, QCheckBox, QDoubleSpinBox,
    QMessageBox, QScrollArea, QFrame, QTabWidget, QFileDialog, QColorDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QAbstractItemView, QGridLayout,
)

from ..database.db_manager import get_connection, log_action, hash_password, DB_PATH
from ..paths import project_root, settings_json_path
from ..services.report_service import ReportService

try:
    __import__("requests")
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False
from .help_dialog import show_help
from .lucide_icons import apply_action_button
from .toast import show_toast
from .components.status_badge import StatusBadge
from .components.confirm_dialog import _dialog_qss

_SETTINGS_FILE = settings_json_path()
_PROJECT_ROOT = project_root()
_ASSETS_DIR = os.path.join(_PROJECT_ROOT, "assets")
_LOGO_FILE = os.path.join(_ASSETS_DIR, "logo.png")

_DEFAULT_VEHICLE_COLORS = [
    "#1A6CF6", "#00FF88", "#FF8C00", "#8B5CF6", "#FF4757",
    "#00D4FF", "#FFB800", "#E91E63", "#4CAF50", "#9C27B0",
]

_SNAPSHOT_TABLES_ORDER = [
    "clients", "depots", "vehicles", "drivers", "teams", "team_members",
    "zones", "carriers", "orders", "routes", "route_stops",
    "carrier_shipments", "algo_results", "scenarios",
    "notifications", "logs",
]


def _deep_merge(base: dict, incoming: dict) -> dict:
    out = dict(base)
    for k, v in (incoming or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _default_settings() -> dict:
    return {
        "company": {
            "name": "CityPulse Logistics",
            "address": "Casablanca, Maroc",
            "phone": "",
            "email": "",
            "currency": "MAD",
            "timezone": "Africa/Casablanca",
            "logo_path": "assets/logo.png",
        },
        "map": {
            "provider": "Standard",
            "default_lat": 33.5731,
            "default_lon": -7.5898,
            "default_zoom": 12,
            "default_layer": "Standard",
            "vehicle_colors": list(_DEFAULT_VEHICLE_COLORS),
            "show_labels": True,
            "show_order": True,
        },
        "reports": {
            "theme_color": "#1565C0",
            "header_text": "CityPulse Logistics",
            "footer_text": "",
            "include_logo": True,
            "output_dir": "",
            "scheduled": [],
            "paper_size": "A4",
            "language": "fr",
            "include_qr_code": False,
            "include_signature_block": True,
        },
        "notifications": {
            "enabled": True,
            "expiry_warning_days": 30,
            "sound_enabled": False,
            "auto_dismiss_seconds": 5,
            "daily_summary": True,
            "daily_hour": 18,
        },
        "system": {
            "theme": "dark",
            "ui_lang": "fr",
            "alert_threshold_min": 5,
            "maint_km": 10000.0,
        },
        "osrm": {
            "url": "http://router.project-osrm.org",
            "timeout": 10,
            "fallback_to_haversine": True,
        },
        "mistral": {
            "model": "mistral-small-latest",
            "language": "fr",
            "max_tokens": 1024,
            "temperature": 0.7,
        },
        "translation": {
            "api": "google",
            "provider": "google",
            "default_source": "fr",
            "default_target": "en",
            "offline_mode": False,
        },
    }


def _migrate_flat_root(data: dict) -> None:
    """Normalise anciennes clés racine vers structure imbriquée (in-place)."""
    if "notif_daily_summary" in data:
        data.setdefault("notifications", {})["daily_summary"] = bool(
            data["notif_daily_summary"]
        )
    if "notif_daily_hour" in data:
        data.setdefault("notifications", {})["daily_hour"] = int(data["notif_daily_hour"])
    if "theme" in data and "system" not in data:
        th = data.get("theme", "Noir")
        data["system"] = {
            "theme": "dark" if th in ("Noir", "Dark", "dark") else "light",
            "ui_lang": "fr",
            "alert_threshold_min": int(data.get("alert_threshold", 5)),
            "maint_km": float(data.get("maint_km", 10000)),
        }
    if "lang" in data:
        data.setdefault("system", {})["ui_lang"] = "en" if data.get("lang") == 1 else "fr"


# ── Threads tests API ────────────────────────────────────────────────────────


class _OsrmTestThread(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, base_url: str, timeout: int):
        super().__init__()
        self.base_url = (base_url or "").strip().rstrip("/")
        self.timeout = max(3, min(timeout or 10, 60))

    def run(self):
        if not _HAS_REQUESTS:
            self.done.emit(False, "requests absent")
            return
        try:
            import requests

            u = f"{self.base_url}/route/v1/driving/-7.5898,33.5731;-7.60,33.58?overview=false"
            r = requests.get(u, timeout=self.timeout)
            self.done.emit(r.status_code < 500, f"HTTP {r.status_code}")
        except Exception as e:
            self.done.emit(False, str(e))


class SettingsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._data: dict = {}
        self._report_theme_hex = "#1565C0"
        self._map_colors: list[str] = list(_DEFAULT_VEHICLE_COLORS)
        self._color_buttons: list[QPushButton] = []
        self._threads: list[QThread] = []
        self._setup_ui()

    def _is_admin(self) -> bool:
        r = (self.main_window.current_user or {}).get("role", "").lower()
        return r in ("admin", "administrateur")

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(4, 10, 4, 0)
        title = QLabel("Paramètres & configuration")
        title.setObjectName("heading")
        hdr.addWidget(title)
        hdr.addStretch()
        hb = QPushButton()
        hb.setFixedSize(32, 32)
        hb.setToolTip("Aide — Paramètres")
        hb.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(hb, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        hb.clicked.connect(lambda: show_help(self, "settings"))
        hdr.addWidget(hb)
        root.addLayout(hdr)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabWidget::pane{border:none;background:#0D1B2A;}"
            "QTabBar{border:none;border-bottom:none;}"
            "QTabBar::tab{padding:8px 14px;background:#1A2E4A;color:#E8F4FD;"
            "border-top-left-radius:6px;border-top-right-radius:6px;margin-right:2px;}"
            "QTabBar::tab:selected{background:#112240;color:#00D4FF;}"
        )

        self._tabs.addTab(self._wrap_scroll(self._build_tab_company()), " Entreprise")
        self._tabs.addTab(self._wrap_scroll(self._build_tab_map()), " Carte")
        self._tabs.addTab(self._wrap_scroll(self._build_tab_reports()), " Rapports")
        if self._is_admin():
            self._tabs.addTab(self._wrap_scroll(self._build_tab_users()), " Utilisateurs")
        self._tabs.addTab(self._wrap_scroll(self._build_tab_backup()), " Sauvegarde")

        root.addWidget(self._tabs, 1)

        foot = QFrame()
        foot.setObjectName("settingsFoot")
        foot.setStyleSheet("QFrame#settingsFoot{background:#112240;border-top:1px solid #1E3A5F;}")
        foot.setFixedHeight(56)
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(16, 8, 16, 8)
        fl.addStretch()
        save_btn = QPushButton(" Sauvegarder")
        save_btn.setObjectName("primaryBtn")
        save_btn.setMinimumHeight(40)
        save_btn.setMinimumWidth(200)
        save_btn.clicked.connect(self._save_settings)
        fl.addWidget(save_btn)
        root.addWidget(foot)

    def _wrap_scroll(self, inner: QWidget) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        w.setStyleSheet("QScrollArea{background:#0D1B2A;border:none;}")
        inner.setObjectName("_swInner")
        inner.setStyleSheet("QWidget#_swInner{background:#0D1B2A;}")
        w.setWidget(inner)
        return w

    # ── Tab builders ──────────────────────────────────────────────────────

    def _build_tab_company(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 24)
        layout.setSpacing(14)

        g = QGroupBox("Identité entreprise")
        g.setStyleSheet(self._group_style())
        form = QFormLayout(g)
        self.c_name = QLineEdit()
        self.c_address = QLineEdit()
        self.c_phone = QLineEdit()
        self.c_email = QLineEdit()
        self.c_currency = QComboBox()
        self.c_currency.addItems(["MAD", "EUR", "USD"])
        self.c_tz = QComboBox()
        for z in (
            "Africa/Casablanca", "Europe/Paris", "UTC", "Europe/Madrid",
            "America/New_York", "Asia/Dubai",
        ):
            self.c_tz.addItem(z)
        form.addRow("Nom", self.c_name)
        form.addRow("Adresse", self.c_address)
        form.addRow("Téléphone", self.c_phone)
        form.addRow("Email", self.c_email)
        form.addRow("Devise", self.c_currency)
        form.addRow("Fuseau horaire", self.c_tz)

        logo_row = QHBoxLayout()
        self.c_logo_preview = QLabel()
        self.c_logo_preview.setFixedSize(120, 120)
        self.c_logo_preview.setStyleSheet(
            "background:#1A2E4A;border:1px solid #1E3A5F;border-radius:8px;"
        )
        self.c_logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.c_logo_preview.setText("Aperçu")
        btn_logo = QPushButton("Choisir logo…")
        btn_logo.clicked.connect(self._on_logo_pick)
        logo_row.addWidget(self.c_logo_preview)
        logo_row.addWidget(btn_logo)
        logo_row.addStretch()
        form.addRow("Logo", logo_row)
        layout.addWidget(g)

        g2 = QGroupBox("Interface & alertes")
        g2.setStyleSheet(self._group_style())
        f2 = QFormLayout(g2)
        from app.i18n import LANG_DISPLAY
        self.sys_theme = QComboBox()
        self.sys_theme.addItems(["Sombre", "Clair"])
        self.sys_theme.setMaximumWidth(160)
        self.sys_theme.currentTextChanged.connect(self._on_theme_changed)
        self.sys_lang = QComboBox()
        self.sys_lang.addItems(LANG_DISPLAY)
        self.sys_lang.setMaximumWidth(220)
        self.sys_lang.currentIndexChanged.connect(self._on_lang_changed)
        self.sys_alert = QSpinBox()
        self.sys_alert.setRange(1, 120)
        self.sys_alert.setSuffix(" min")
        self.sys_alert.setMaximumWidth(100)
        self.sys_maint = QDoubleSpinBox()
        self.sys_maint.setRange(1000, 500000)
        self.sys_maint.setSuffix(" km")
        self.sys_maint.setMaximumWidth(160)
        f2.addRow("Thème", self.sys_theme)
        f2.addRow("Langue de l'interface", self.sys_lang)
        f2.addRow("Seuil alerte retard", self.sys_alert)
        f2.addRow("Seuil maintenance", self.sys_maint)
        layout.addWidget(g2)

        g3 = QGroupBox("Notifications — résumé journalier")
        g3.setStyleSheet(self._group_style())
        f3 = QFormLayout(g3)
        self.notif_daily = QCheckBox("Activer le résumé automatique")
        self.notif_hour = QSpinBox()
        self.notif_hour.setRange(0, 23)
        self.notif_hour.setSuffix(" h")
        self.notif_hour.setMaximumWidth(80)
        f3.addRow(self.notif_daily)
        f3.addRow("Heure d'envoi", self.notif_hour)
        layout.addWidget(g3)

        g4 = QGroupBox("Copilote IA (Mistral)")
        g4.setStyleSheet(self._group_style())
        f4 = QFormLayout(g4)
        self.c_mistral_model = QComboBox()
        self.c_mistral_model.setEditable(True)
        self.c_mistral_model.setMaximumWidth(240)
        self.c_mistral_model.addItems(
            ["mistral-small-latest", "mistral-large-latest", "open-mistral-7b"]
        )
        self.c_mistral_lang = QComboBox()
        self.c_mistral_lang.addItems(["fr", "en", "ar", "es", "de"])
        self.c_mistral_lang.setMaximumWidth(100)
        info_key = QLabel(
            "Clé API chargée automatiquement depuis MISTRAL_API_KEY dans le fichier .env"
        )
        info_key.setWordWrap(True)
        info_key.setStyleSheet("color:#7FA8C0;font-size:12px;border:none;")
        f4.addRow(info_key)
        f4.addRow("Modèle", self.c_mistral_model)
        f4.addRow("Langue réponses", self.c_mistral_lang)
        layout.addWidget(g4)

        layout.addStretch()
        return w

    def _group_style(self) -> str:
        return (
            "QGroupBox{color:#E8F4FD;font-weight:600;border:1px solid #1E3A5F;"
            "border-radius:8px;margin-top:10px;padding:12px;padding-top:24px;}"
            "QGroupBox::title{subcontrol-origin:margin;subcontrol-position:top left;"
            "left:12px;padding:2px 8px;}"
        )

    def _on_logo_pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Logo", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        os.makedirs(_ASSETS_DIR, exist_ok=True)
        try:
            shutil.copy2(path, _LOGO_FILE)
            self._refresh_logo_preview()
            show_toast(self.window(), "Logo enregistré : assets/logo.png", "success")
            log_action("COMPANY_LOGO", "Logo copié vers assets/logo.png")
        except Exception as e:
            QMessageBox.warning(self, "Logo", str(e))

    def _refresh_logo_preview(self):
        if os.path.isfile(_LOGO_FILE):
            pm = QPixmap(_LOGO_FILE)
            if not pm.isNull():
                self.c_logo_preview.setPixmap(
                    pm.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
                )
                self.c_logo_preview.setText("")
                return
        self.c_logo_preview.clear()
        self.c_logo_preview.setText("Aperçu")

    def _on_theme_changed(self, text: str):
        mapped = "dark" if text.startswith("Sombre") else "light"
        if self.main_window:
            self.main_window._apply_theme(mapped)

    def _on_lang_changed(self, index: int):
        from app.i18n import LANG_CODES
        lang = LANG_CODES[index] if 0 <= index < len(LANG_CODES) else "fr"
        if self.main_window:
            self.main_window._apply_language(lang)

    def _current_ui_lang(self) -> str:
        from app.i18n import LANG_CODES
        idx = self.sys_lang.currentIndex()
        return LANG_CODES[idx] if 0 <= idx < len(LANG_CODES) else "fr"

    def retranslate_ui(self, lang: str):
        from app.i18n import tr
        _TAB_KEYS = [
            "settings.tab.company", "settings.tab.map",
            "settings.tab.reports",
        ]
        for i, key in enumerate(_TAB_KEYS):
            if i < self._tabs.count():
                self._tabs.setTabText(i, f" {tr(key, lang)}")
        _tab_map_extra = {
            3: "settings.tab.users",
            4: "settings.tab.backup",
        }
        for idx, key in _tab_map_extra.items():
            if idx < self._tabs.count():
                self._tabs.setTabText(idx, f" {tr(key, lang)}")

    def _build_tab_map(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 24)
        g = QGroupBox("Carte")
        g.setStyleSheet(self._group_style())
        form = QFormLayout(g)
        self.m_provider = QComboBox()
        self.m_provider.addItems(["Standard", "Dark", "Satellite", "Terrain"])
        self.m_provider.setMaximumWidth(160)
        self.m_lat = QDoubleSpinBox()
        self.m_lat.setRange(-90, 90)
        self.m_lat.setDecimals(6)
        self.m_lat.setMaximumWidth(130)
        self.m_lon = QDoubleSpinBox()
        self.m_lon.setRange(-180, 180)
        self.m_lon.setDecimals(6)
        self.m_lon.setMaximumWidth(130)
        self.m_zoom = QSpinBox()
        self.m_zoom.setRange(1, 18)
        self.m_zoom.setMaximumWidth(80)
        btn_depot = QPushButton(" Dépôt principal")
        btn_depot.clicked.connect(self._fill_main_depot_coords)
        row = QHBoxLayout()
        row.addWidget(self.m_lat)
        row.addWidget(self.m_lon)
        row.addWidget(btn_depot)
        form.addRow("Fournisseur / fond", self.m_provider)
        form.addRow("Lat / Lon défaut", row)
        form.addRow("Zoom défaut", self.m_zoom)
        self.m_labels = QCheckBox("Afficher labels clients")
        self.m_order = QCheckBox("Afficher numéros d'ordre")
        form.addRow(self.m_labels)
        form.addRow(self.m_order)
        layout.addWidget(g)

        g2 = QGroupBox("Couleurs véhicules (10)")
        g2.setStyleSheet(self._group_style())
        grid = QGridLayout(g2)
        self._color_buttons = []
        for i in range(10):
            b = QPushButton(f"V{i + 1}")
            b.setFixedHeight(32)
            b.setProperty("color_idx", i)
            b.clicked.connect(lambda _, idx=i: self._pick_vehicle_color(idx))
            self._color_buttons.append(b)
            grid.addWidget(b, i // 5, i % 5)
        layout.addWidget(g2)
        layout.addStretch()
        return w

    def _pick_vehicle_color(self, idx: int):
        c = QColorDialog.getColor(QColor(self._map_colors[idx]), self, "Couleur véhicule")
        if c.isValid():
            self._map_colors[idx] = c.name()
            self._apply_color_button_style(idx)

    def _apply_color_button_style(self, idx: int):
        b = self._color_buttons[idx]
        hex_c = self._map_colors[idx]
        b.setStyleSheet(
            f"QPushButton{{background:{hex_c};color:#fff;border:1px solid #1E3A5F;"
            "border-radius:6px;font-weight:600;}}"
        )

    def _fill_main_depot_coords(self):
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT latitude, longitude FROM depots ORDER BY id LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                self.m_lat.setValue(float(row["latitude"] or 0))
                self.m_lon.setValue(float(row["longitude"] or 0))
                show_toast(self.window(), "Coordonnées du dépôt principal appliquées.", "info")
            else:
                QMessageBox.information(self, "Dépôt", "Aucun dépôt en base.")
        except Exception as e:
            QMessageBox.warning(self, "Dépôt", str(e))

    def _build_tab_reports(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 24)
        g = QGroupBox("Mise en page PDF / exports")
        g.setStyleSheet(self._group_style())
        form = QFormLayout(g)
        self.r_color_btn = QPushButton("Choisir couleur thème…")
        self.r_color_btn.clicked.connect(self._pick_report_color)
        self.r_color_preview = QLabel()
        self.r_color_preview.setFixedSize(48, 24)
        self.r_color_preview.setStyleSheet("background:#1565C0;border-radius:4px;")
        row = QHBoxLayout()
        row.addWidget(self.r_color_preview)
        row.addWidget(self.r_color_btn)
        row.addStretch()
        self.r_header = QLineEdit()
        self.r_footer = QLineEdit()
        self.r_logo = QCheckBox("Afficher le logo sur les rapports")
        self.r_out_dir = QLineEdit()
        btn_dir = QPushButton("Parcourir…")
        btn_dir.clicked.connect(self._pick_report_dir)
        row2 = QHBoxLayout()
        row2.addWidget(self.r_out_dir, 1)
        row2.addWidget(btn_dir)
        form.addRow("Couleur thème", row)
        form.addRow("En-tête (texte)", self.r_header)
        form.addRow("Pied de page", self.r_footer)
        form.addRow(self.r_logo)
        form.addRow("Dossier sauvegarde", row2)
        layout.addWidget(g)

        g2 = QGroupBox("Rapports planifiés")
        g2.setStyleSheet(self._group_style())
        h = QVBoxLayout(g2)
        h.setSpacing(6)

        # En-tête colonnes
        hdr_row = QHBoxLayout()
        for txt, w_ in [("Heure", 90), ("Type", 0), ("Actif", 48)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet("color:#7FA8C0;font-size:11px;font-weight:600;")
            if w_:
                lbl.setFixedWidth(w_)
            hdr_row.addWidget(lbl, 0 if w_ else 1)
        hdr_row.addSpacing(28)
        h.addLayout(hdr_row)

        # Zone liste des lignes
        self._sched_rows: list[tuple] = []
        self._sched_list_widget = QWidget()
        self._sched_list_widget.setObjectName("schedList")
        self._sched_list_widget.setStyleSheet("QWidget#schedList{background:transparent;}")
        self._sched_vbox = QVBoxLayout(self._sched_list_widget)
        self._sched_vbox.setContentsMargins(0, 0, 0, 0)
        self._sched_vbox.setSpacing(4)

        sched_scroll = QScrollArea()
        sched_scroll.setWidget(self._sched_list_widget)
        sched_scroll.setWidgetResizable(True)
        sched_scroll.setFixedHeight(150)
        sched_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sched_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        h.addWidget(sched_scroll)

        b_add = QPushButton("+ Ajouter une planification")
        b_add.clicked.connect(lambda: self._sched_add_row())
        h.addWidget(b_add)
        layout.addWidget(g2)
        layout.addStretch()
        return w

    def _pick_report_color(self):
        c = QColorDialog.getColor(QColor(self._report_theme_hex), self, "Couleur thème rapports")
        if c.isValid():
            self._report_theme_hex = c.name()
            self.r_color_preview.setStyleSheet(
                f"background:{self._report_theme_hex};border-radius:4px;border:1px solid #1E3A5F;"
            )

    def _pick_report_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier rapports")
        if d:
            self.r_out_dir.setText(d)

    # Liste des types de rapports disponibles : (clé_json, libellé affiché)
    _SCHED_REPORT_TYPES = [
        ("kpi",                "Rapport KPI (performance)"),
        ("fleet_daily",        "Rapport journalier flotte"),
        ("driver_performance", "Performance chauffeurs"),
        ("algo_comparison",    "Comparaison algorithmes"),
        ("rse",                "Conformité RSE"),
        ("carrier",            "Rapport transporteurs"),
        ("export_excel",       "Export Excel complet"),
    ]

    _FIELD_QSS = (
        "background:#1A2E4A;color:#E8F4FD;border:1px solid #1E3A5F;"
        "border-radius:4px;padding:2px 8px;"
    )
    _COMBO_QSS = (
        "QComboBox{background:#1A2E4A;color:#E8F4FD;border:1px solid #1E3A5F;"
        "border-radius:4px;padding:2px 8px;}"
        "QComboBox::drop-down{border:none;width:20px;}"
        "QComboBox QAbstractItemView{background:#162840;color:#E8F4FD;"
        "border:1px solid #1E3A5F;selection-background-color:#00D4FF;"
        "selection-color:#0D1B2A;outline:none;}"
    )
    _CHK_QSS = (
        "QCheckBox{background:transparent;spacing:0;}"
        "QCheckBox::indicator{width:18px;height:18px;border:2px solid #1E3A5F;"
        "border-radius:4px;background:#1A2E4A;}"
        "QCheckBox::indicator:checked{background:#00D4FF;border-color:#00D4FF;}"
    )

    def _sched_add_row(self, time_val: str = "08:00", type_key: str = "kpi", enabled: bool = True):
        row_w = QFrame()
        row_w.setObjectName("schedRow")
        row_w.setStyleSheet(
            "QFrame#schedRow{background:#162840;border:1px solid #1E3A5F;"
            "border-radius:6px;}"
        )
        row_w.setFixedHeight(38)
        rl = QHBoxLayout(row_w)
        rl.setContentsMargins(8, 4, 8, 4)
        rl.setSpacing(8)

        time_edit = QLineEdit(time_val)
        time_edit.setFixedWidth(80)
        time_edit.setPlaceholderText("HH:MM")
        time_edit.setStyleSheet(self._FIELD_QSS)

        cb = QComboBox()
        cb.setStyleSheet(self._COMBO_QSS)
        for key, label in self._SCHED_REPORT_TYPES:
            cb.addItem(label, key)
        idx = next((i for i, (k, _) in enumerate(self._SCHED_REPORT_TYPES) if k == type_key), 0)
        cb.setCurrentIndex(idx)

        chk = QCheckBox()
        chk.setChecked(enabled)
        chk.setFixedWidth(28)
        chk.setStyleSheet(self._CHK_QSS)

        btn_del = QPushButton("×")
        btn_del.setFixedSize(24, 24)
        btn_del.setStyleSheet(
            "QPushButton{background:#1E3A5F;color:#FF4757;border:none;border-radius:4px;"
            "font-size:14px;font-weight:700;}"
            "QPushButton:hover{background:#FF4757;color:#fff;}"
        )

        rl.addWidget(time_edit)
        rl.addWidget(cb, 1)
        rl.addWidget(chk)
        rl.addWidget(btn_del)

        entry = (time_edit, cb, chk, row_w)
        self._sched_rows.append(entry)
        self._sched_vbox.addWidget(row_w)

        btn_del.clicked.connect(lambda: self._sched_remove_row(entry))

    def _sched_remove_row(self, entry: tuple):
        *_, row_w = entry
        if entry in self._sched_rows:
            self._sched_rows.remove(entry)
        row_w.setParent(None)
        row_w.deleteLater()

    def _build_tab_users(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 24)
        bar = QHBoxLayout()
        b_add = QPushButton("+ Utilisateur")
        b_ref = QPushButton("Actualiser")
        b_add.clicked.connect(self._user_add_dialog)
        b_ref.clicked.connect(self._refresh_users_table)
        bar.addWidget(b_add)
        bar.addWidget(b_ref)
        bar.addStretch()
        layout.addLayout(bar)
        self.u_table = QTableWidget(0, 5)
        self.u_table.setHorizontalHeaderLabels(["ID", "Login", "Rôle", "Actif", "Actions"])
        self.u_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.u_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.u_table.doubleClicked.connect(self._user_edit_selected)
        layout.addWidget(self.u_table)
        return w

    def _refresh_users_table(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, username, role, COALESCE(is_active,1) AS is_active FROM users ORDER BY id"
        ).fetchall()
        conn.close()
        self.u_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.u_table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.u_table.setItem(i, 1, QTableWidgetItem(r["username"] or ""))
            self.u_table.setItem(i, 2, QTableWidgetItem(r["role"] or ""))
            act = "oui" if r["is_active"] else "non"
            self.u_table.setItem(i, 3, QTableWidgetItem(act))
            wdg = QWidget()
            hl = QHBoxLayout(wdg)
            hl.setContentsMargins(2, 2, 2, 2)
            b_e = QPushButton("Modifier")
            b_d = QPushButton("Désactiver")
            uid = int(r["id"])
            b_e.clicked.connect(lambda _, u=uid: self._user_edit(u))
            b_d.clicked.connect(lambda _, u=uid: self._user_deactivate(u))
            hl.addWidget(b_e)
            hl.addWidget(b_d)
            self.u_table.setCellWidget(i, 4, wdg)

    def _user_add_dialog(self):
        self._user_dialog(None)

    def _user_edit_selected(self):
        r = self.u_table.currentRow()
        if r < 0:
            return
        uid = int(self.u_table.item(r, 0).text())
        self._user_edit(uid)

    def _user_edit(self, user_id: int):
        self._user_dialog(user_id)

    def _user_dialog(self, user_id: int | None):
        dlg = QDialog(self)
        dlg.setWindowTitle("Utilisateur" if user_id else "Nouvel utilisateur")
        dlg.setStyleSheet(
            _dialog_qss()
            + "QDialog{background:#0D1B2A;color:#E8F4FD;}"
            "QLineEdit,QComboBox{background:#1A2E4A;color:#E8F4FD;border:1px solid #1E3A5F;border-radius:5px;padding:4px 8px;}"
            "QCheckBox{color:#E8F4FD;background:transparent;}"
        )
        lo = QFormLayout(dlg)
        le_u = QLineEdit()
        le_p = QLineEdit()
        le_p.setEchoMode(QLineEdit.EchoMode.Password)
        le_p.setPlaceholderText("(laisser vide pour ne pas changer)")
        cb_r = QComboBox()
        cb_r.addItems(["admin", "planner", "dispatcher", "viewer"])
        cb_a = QCheckBox("Compte actif")
        cb_a.setChecked(True)
        if user_id:
            conn = get_connection()
            row = conn.execute(
                "SELECT username, role, COALESCE(is_active,1) AS is_active FROM users WHERE id= ?",
                (user_id,),
            ).fetchone()
            conn.close()
            if row:
                le_u.setText(row["username"] or "")
                le_u.setReadOnly(True)
                role_raw = (row["role"] or "viewer").lower()
                role_norm = {
                    "gestionnaire": "planner",
                    "superviseur": "dispatcher",
                    "chauffeur": "dispatcher",
                    "administrateur": "admin",
                }.get(role_raw, role_raw)
                idx = cb_r.findText(role_norm)
                if idx < 0:
                    cb_r.addItem(role_raw)
                    idx = cb_r.findText(role_raw)
                cb_r.setCurrentIndex(max(0, idx))
                cb_a.setChecked(bool(row["is_active"]))
        lo.addRow("Nom d'utilisateur", le_u)
        lo.addRow("Mot de passe", le_p)
        lo.addRow("Rôle", cb_r)
        lo.addRow(cb_a)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        lo.addRow(bb)

        def save():
            uname = le_u.text().strip()
            role = cb_r.currentText()
            if not uname:
                QMessageBox.warning(dlg, "Erreur", "Login requis.")
                return
            conn = get_connection()
            try:
                if user_id:
                    if le_p.text():
                        h, salt = hash_password(le_p.text())
                        conn.execute(
                            "UPDATE users SET password_hash= ?, salt= ?, role= ?, is_active= ? WHERE id= ?",
                            (h, salt, role, 1 if cb_a.isChecked() else 0, user_id),
                        )
                    else:
                        conn.execute(
                            "UPDATE users SET role= ?, is_active= ? WHERE id= ?",
                            (role, 1 if cb_a.isChecked() else 0, user_id),
                        )
                    log_action("USER_UPDATE", f"User #{user_id} mis à jour")
                else:
                    if len(le_p.text()) < 4:
                        QMessageBox.warning(dlg, "Erreur", "Mot de passe min. 4 caractères.")
                        conn.close()
                        return
                    h, salt = hash_password(le_p.text())
                    conn.execute(
                        "INSERT INTO users (username, password_hash, salt, role, full_name, is_active) "
                        "VALUES (?,?,?,?,?,1)",
                        (uname, h, salt, role, uname),
                    )
                    log_action("USER_CREATE", f"Utilisateur {uname} ({role})")
                conn.commit()
            except Exception as e:
                conn.close()
                QMessageBox.warning(dlg, "Erreur", str(e))
                return
            conn.close()
            dlg.accept()
            self._refresh_users_table()
            show_toast(self.window(), "Utilisateur enregistré.", "success")

        bb.accepted.connect(save)
        bb.rejected.connect(dlg.reject)
        dlg.exec()

    def _user_deactivate(self, user_id: int):
        me = (self.main_window.current_user or {}).get("id")
        if me and int(me) == int(user_id):
            QMessageBox.warning(self, "Erreur", "Vous ne pouvez pas vous désactiver vous-même.")
            return
        if QMessageBox.question(
            self, "Confirmer", "Désactiver cet utilisateur ", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        conn.execute("UPDATE users SET is_active=0 WHERE id= ?", (user_id,))
        conn.commit()
        conn.close()
        log_action("USER_DEACTIVATE", f"User #{user_id} désactivé")
        self._refresh_users_table()
        show_toast(self.window(), "Utilisateur désactivé.", "info")

    def _build_tab_backup(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 24)
        g = QGroupBox("Base de données")
        g.setStyleSheet(self._group_style())
        v = QVBoxLayout(g)
        row = QHBoxLayout()
        b_exp = QPushButton("Exporter JSON (snapshot)")
        b_imp = QPushButton("Importer JSON (snapshot)")
        b_exp.clicked.connect(self._backup_export)
        b_imp.clicked.connect(self._backup_import)
        row.addWidget(b_exp)
        row.addWidget(b_imp)
        v.addLayout(row)
        row2 = QHBoxLayout()
        b_rst = QPushButton("Reset données métier")
        b_rst.setObjectName("dangerBtn")
        b_rst.clicked.connect(self._backup_reset_data)
        row2.addWidget(b_rst)
        v.addLayout(row2)
        layout.addWidget(g)

        g3 = QGroupBox("Santé système")
        g3.setStyleSheet(self._group_style())
        v3 = QVBoxLayout(g3)
        self.bak_health_lbl = QLabel("—")
        self.bak_health_lbl.setWordWrap(True)
        self.bak_health_lbl.setStyleSheet("color:#8899AA;font-size:12px;")
        b_h = QPushButton("Vérifier intégrité & taille")
        b_h.clicked.connect(self._backup_health)
        v3.addWidget(b_h)
        v3.addWidget(self.bak_health_lbl)
        layout.addWidget(g3)

        g4 = QGroupBox("OSRM — Serveur de distances routières")
        g4.setStyleSheet(self._group_style())
        f4 = QFormLayout(g4)
        self.o_osrm_url = QLineEdit()
        self.o_osrm_url.setPlaceholderText("http://router.project-osrm.org")
        self.o_osrm_to = QSpinBox()
        self.o_osrm_to.setRange(3, 120)
        self.o_osrm_to.setSuffix(" s")
        self.o_osrm_to.setMaximumWidth(100)
        row4 = QHBoxLayout()
        b_osrm = QPushButton(" Tester")
        self.badge_osrm = StatusBadge("neutral", "—")
        b_osrm.clicked.connect(self._test_osrm)
        row4.addWidget(b_osrm)
        row4.addWidget(self.badge_osrm)
        row4.addStretch()
        info_osrm = QLabel(
            "Si OSRM_URL est défini dans .env, il prend la priorité au démarrage."
        )
        info_osrm.setWordWrap(True)
        info_osrm.setStyleSheet("color:#7FA8C0;font-size:12px;border:none;")
        f4.addRow(info_osrm)
        f4.addRow("URL de base", self.o_osrm_url)
        f4.addRow("Timeout", self.o_osrm_to)
        f4.addRow(row4)
        layout.addWidget(g4)

        layout.addStretch()
        return w

    def _backup_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter snapshot", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            ReportService().generate_full_snapshot(path)
            show_toast(self.window(), "Export terminé.", "success")
        except Exception as e:
            QMessageBox.warning(self, "Export", str(e))

    def _backup_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer snapshot", "", "JSON (*.json)")
        if not path:
            return
        if (
            QMessageBox.warning(
                self,
                "Attention",
                "L'import remplace les données des tables du snapshot. Continuer ",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with open(path, encoding="utf-8") as f:
                snap = json.load(f)
            tables = snap.get("tables") or {}
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=OFF")
            rev = list(reversed(_SNAPSHOT_TABLES_ORDER))
            for t in rev:
                try:
                    conn.execute(f"DELETE FROM {t}")
                except sqlite3.Error:
                    pass
            for t in _SNAPSHOT_TABLES_ORDER:
                for row in tables.get(t, []):
                    if not row:
                        continue
                    cols = list(row.keys())
                    ph = ",".join("?" * len(cols))
                    try:
                        conn.execute(
                            f"INSERT INTO {t} ({','.join(cols)}) VALUES ({ph})",
                            [row[c] for c in cols],
                        )
                    except sqlite3.Error as e:
                        logger.warning("Import %s: %s", t, e)
            conn.commit()
            conn.close()
            log_action("DB_IMPORT_JSON", path)
            show_toast(self.window(), "Import terminé.", "success")
        except Exception as e:
            QMessageBox.warning(self, "Import", str(e))

    def _backup_reset_data(self):
        if (
            QMessageBox.warning(
                self,
                "Reset",
                "Supprimer clients, commandes, routes, arrêts, scénarios, logs, notifications  "
                "(Les utilisateurs sont conservés.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        conn = get_connection()
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            for t in reversed(_SNAPSHOT_TABLES_ORDER):
                try:
                    conn.execute(f"DELETE FROM {t}")
                except sqlite3.Error:
                    pass
            conn.commit()
        finally:
            conn.close()
        log_action("DB_RESET_DATA", "Reset données métier")
        show_toast(self.window(), "Données métier réinitialisées.", "info")

    def _backup_health(self):
        try:
            sz = os.path.getsize(DB_PATH) if os.path.isfile(DB_PATH) else 0
            conn = get_connection()
            row = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            chk = row[0] if row else ""
            self.bak_health_lbl.setText(
                f"SQLite integrity_check : {chk}\nFichier : {DB_PATH}\nTaille : {sz / (1024 * 1024):.2f} Mo"
            )
        except Exception as e:
            self.bak_health_lbl.setText(str(e))

    # ── API test handlers ─────────────────────────────────────────────────

    def _test_osrm(self):
        self.badge_osrm.update_status("pending", "…")
        t = _OsrmTestThread(self.o_osrm_url.text(), self.o_osrm_to.value())
        self._threads.append(t)
        t.done.connect(lambda ok, msg: self.badge_osrm.update_status(
            "success" if ok else "danger", msg
        ))
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        t.start()


    # ── Load / Save ───────────────────────────────────────────────────────

    def _load_disk(self) -> dict:
        raw = {}
        if os.path.isfile(_SETTINGS_FILE):
            try:
                with open(_SETTINGS_FILE, encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception:
                raw = {}
        _migrate_flat_root(raw)
        return _deep_merge(_default_settings(), raw)

    def _apply_to_widgets(self, d: dict):
        self._data = d
        c = d.get("company", {})
        self.c_name.setText(c.get("name", ""))
        self.c_address.setText(c.get("address", ""))
        self.c_phone.setText(c.get("phone", ""))
        self.c_email.setText(c.get("email", ""))
        cur = c.get("currency", "MAD")
        i = self.c_currency.findText(cur)
        if i >= 0:
            self.c_currency.setCurrentIndex(i)
        tz = c.get("timezone", "Africa/Casablanca")
        ti = self.c_tz.findText(tz)
        if ti >= 0:
            self.c_tz.setCurrentIndex(ti)
        self._refresh_logo_preview()

        m = d.get("map", {})
        prov = m.get("default_layer") or m.get("provider", "Standard")
        pi = self.m_provider.findText(prov)
        self.m_provider.setCurrentIndex(max(0, pi))
        self.m_lat.setValue(float(m.get("default_lat", 33.5731)))
        self.m_lon.setValue(float(m.get("default_lon", -7.5898)))
        self.m_zoom.setValue(int(m.get("default_zoom", 12)))
        self.m_labels.setChecked(bool(m.get("show_labels", True)))
        self.m_order.setChecked(bool(m.get("show_order", True)))
        cols = m.get("vehicle_colors") or list(_DEFAULT_VEHICLE_COLORS)
        self._map_colors = list(cols[:10])
        while len(self._map_colors) < 10:
            self._map_colors.append(_DEFAULT_VEHICLE_COLORS[len(self._map_colors) % 10])
        for i in range(10):
            self._apply_color_button_style(i)

        rep = d.get("reports", {})
        self._report_theme_hex = rep.get("theme_color", "#1565C0")
        self.r_color_preview.setStyleSheet(
            f"background:{self._report_theme_hex};border-radius:4px;border:1px solid #1E3A5F;"
        )
        self.r_header.setText(rep.get("header_text", ""))
        self.r_footer.setText(rep.get("footer_text", ""))
        self.r_logo.setChecked(bool(rep.get("include_logo", True)))
        self.r_out_dir.setText(rep.get("output_dir", ""))
        for entry in list(self._sched_rows):
            self._sched_remove_row(entry)
        for row in rep.get("scheduled", []) or []:
            self._sched_add_row(
                time_val=str(row.get("time", "08:00")),
                type_key=str(row.get("type", "kpi")),
                enabled=bool(row.get("enabled", True)),
            )

        sy = d.get("system", {})
        self.sys_theme.setCurrentIndex(0 if sy.get("theme", "dark") == "dark" else 1)
        from app.i18n import LANG_CODES
        _lang = sy.get("ui_lang", "fr")
        _li = LANG_CODES.index(_lang) if _lang in LANG_CODES else 0
        self.sys_lang.blockSignals(True)
        self.sys_lang.setCurrentIndex(_li)
        self.sys_lang.blockSignals(False)
        self.sys_alert.setValue(int(sy.get("alert_threshold_min", 5)))
        self.sys_maint.setValue(float(sy.get("maint_km", 10000)))

        n = d.get("notifications", {})
        self.notif_daily.setChecked(bool(n.get("daily_summary", True)))
        self.notif_hour.setValue(int(n.get("daily_hour", 18)))

        osrm = d.get("osrm", {})
        osrm_url = osrm.get("url") or os.getenv("OSRM_URL", "http://router.project-osrm.org")
        self.o_osrm_url.setText(osrm_url)
        self.o_osrm_to.setValue(int(osrm.get("timeout", 10)))

        ms = d.get("mistral", {})
        mi = self.c_mistral_model.findText(ms.get("model", ""))
        if mi >= 0:
            self.c_mistral_model.setCurrentIndex(mi)
        else:
            self.c_mistral_model.setCurrentText(ms.get("model", "mistral-small-latest"))
        li = self.c_mistral_lang.findText(ms.get("language", "fr"))
        self.c_mistral_lang.setCurrentIndex(max(0, li))

        # translation provider is fixed to google (deep-translator, free)

        if self._is_admin() and hasattr(self, "u_table"):
            self._refresh_users_table()

    def _collect_from_widgets(self) -> dict:
        sched = []
        for time_edit, cb, chk, _ in self._sched_rows:
            sched.append({
                "time": time_edit.text().strip() or "08:00",
                "type": cb.currentData() or "kpi",
                "enabled": chk.isChecked(),
            })
        base = _default_settings()
        out = {
            "company": {
                "name": self.c_name.text().strip(),
                "address": self.c_address.text().strip(),
                "phone": self.c_phone.text().strip(),
                "email": self.c_email.text().strip(),
                "currency": self.c_currency.currentText(),
                "timezone": self.c_tz.currentText(),
                "logo_path": "assets/logo.png",
            },
            "map": {
                "provider": self.m_provider.currentText(),
                "default_lat": self.m_lat.value(),
                "default_lon": self.m_lon.value(),
                "default_zoom": self.m_zoom.value(),
                "default_layer": self.m_provider.currentText(),
                "vehicle_colors": list(self._map_colors[:10]),
                "show_labels": self.m_labels.isChecked(),
                "show_order": self.m_order.isChecked(),
            },
            "reports": {
                **base["reports"],
                "theme_color": self._report_theme_hex,
                "header_text": self.r_header.text().strip(),
                "footer_text": self.r_footer.text().strip(),
                "include_logo": self.r_logo.isChecked(),
                "output_dir": self.r_out_dir.text().strip(),
                "scheduled": sched,
            },
            "notifications": {
                **base["notifications"],
                "daily_summary": self.notif_daily.isChecked(),
                "daily_hour": self.notif_hour.value(),
            },
            "system": {
                "theme": "dark" if self.sys_theme.currentIndex() == 0 else "light",
                "ui_lang": self._current_ui_lang(),
                "alert_threshold_min": self.sys_alert.value(),
                "maint_km": self.sys_maint.value(),
            },
            "osrm": {
                "url": self.o_osrm_url.text().strip() or os.getenv("OSRM_URL", base["osrm"]["url"]),
                "timeout": self.o_osrm_to.value(),
                "fallback_to_haversine": True,
            },
            "mistral": {
                "model": self.c_mistral_model.currentText(),
                "language": self.c_mistral_lang.currentText(),
                "max_tokens": base["mistral"]["max_tokens"],
                "temperature": base["mistral"]["temperature"],
            },
            "translation": {
                "api": "google",
                "provider": "google",
                "default_source": base["translation"]["default_source"],
                "default_target": base["translation"]["default_target"],
                "offline_mode": False,
            },
        }
        return _deep_merge(self._data, out)

    def _save_settings(self):
        try:
            data = self._collect_from_widgets()
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._data = data
            log_action(
                "SETTINGS_SAVE",
                "Paramètres sauvegardés",
                user_id=self.main_window.current_user["id"]
                if self.main_window.current_user
                else None,
            )
            show_toast(self.window(), "Paramètres sauvegardés.", "success")
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))

    def refresh_data(self):
        d = self._load_disk()
        self._apply_to_widgets(d)
