"""
vehicles_widget.py — Gestion complète de la flotte CityPulse Logistics v2.0
============================================================================
• Bandeau alertes documents expirants (get_expiring_documents(30))
• Table : Immatriculation | Marque | Type | Chauffeur | Capacité | CO2/km | Statut | Docs | Actions
• StatusBadge coloré par statut
• Fiche véhicule 7 onglets : Identité, Capacités, Vitesses, Coûts, Chauffeur, Documents, Dispo & Stats
• Calendrier disponibilité mensuel (clic → créer/supprimer indisponibilité)
• Alertes maintenance + Stats flotte (KPICards + camembert Matplotlib)
"""

# ── stdlib ────────────────────────────────────────────────────────────────────
import calendar
import csv
import json as _json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta

# ── PyQt6 ────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QDialog, QFormLayout, QDoubleSpinBox, QSpinBox,
    QTextEdit, QMessageBox, QFileDialog, QFrame, QStackedWidget,
    QTabWidget, QCheckBox, QMenu, QScrollArea, QSizePolicy,
    QAbstractItemView, QGridLayout, QButtonGroup, QGroupBox,
    QDateEdit, QProgressBar, QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QFont, QCursor, QAction, QPixmap

# ── Local ─────────────────────────────────────────────────────────────────────
from ..database.db_manager import (
    get_connection, log_action, get_expiring_documents,
    assign_driver_to_vehicle, get_driver_vehicle_info,
)
from ..utils.photo_storage import (
    finalize_stored_path,
    is_allowed_image_filename,
    resolve_stored_photo,
)
from .toast import show_toast
from .loading_overlay import LoadingOverlay
from .help_dialog import show_help
from .components import SectionHeader, SearchBar, ConfirmDialog, EmptyState, KPICard
from .components.confirm_dialog import _dialog_qss
from .lucide_icons import apply_action_button

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    import openpyxl as _openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

logger = logging.getLogger(__name__)

_FK_USER_MSG = (
    "Contrainte de référence : le dépôt ou le chauffeur indiqué n'existe pas en base. "
    "Choisissez une valeur dans les listes ou laissez vide."
)


def _validated_vehicle_fks(conn, depot_id, driver_id):
    """Retourne (depot_id, driver_id) avec NULL si l'id n'existe pas (évite FOREIGN KEY failed)."""
    d, dr = depot_id, driver_id
    if d is not None:
        try:
            if not conn.execute("SELECT 1 FROM depots WHERE id= ?", (d,)).fetchone():
                d = None
        except Exception:
            d = None
    if dr is not None:
        try:
            if not conn.execute("SELECT 1 FROM drivers WHERE id= ?", (dr,)).fetchone():
                dr = None
        except Exception:
            dr = None
    return d, dr

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

C = {
    "bg":      "#0D1B2A", "panel":   "#112240", "input":   "#1A2E4A",
    "accent":  "#00D4FF", "success": "#00FF88", "warning": "#FFB800",
    "danger":  "#FF4757", "text":    "#E8F4FD", "text2":   "#8899AA",
    "border":  "#1E3A5F", "hover":   "#1A3A5C",
}

_VEH_TYPES    = ["fourgon", "camionnette", "poids lourd", "semi-remorque",
                 "moto", "vélo cargo", "utilitaire", "frigorifique"]
_FUEL_TYPES   = ["diesel", "essence", "électrique", "hybride", "gaz (GNV)", "hydrogène"]
_STATUS_OPTS  = ["disponible", "en_service", "maintenance", "hors_service"]
_STATUS_LABEL = {
    "disponible":   "disponible",
    "en_service":   "en service",
    "en tournée":   "en service",
    "maintenance":  "maintenance",
    "hors_service": "hors service",
    "hors service": "hors service",
}
_STATUS_COLOR = {
    "disponible":   C["success"],
    "en_service":   C["accent"],
    "en tournée":   C["accent"],
    "maintenance":  C["warning"],
    "hors_service": C["danger"],
    "hors service": C["danger"],
}
_DAYS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def _normalize_vehicle_status_bucket(status: str | None) -> str:
    """
    Canonical bucket for KPI / filtres / graphiques : disponible | en_service |
    maintenance | hors_service | other.

    La BDD ou imports peuvent stocker « en service » (espace), EN_SERVICE, etc.
    La colonne tableau affiche via _STATUS_LABEL ; les compteurs doivent utiliser
    le même regroupement.
    """
    s = (status or "disponible").strip().lower().replace("_", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    if s == "disponible":
        return "disponible"
    if s in ("en service", "en tournée", "en tournee"):
        return "en_service"
    if s == "maintenance":
        return "maintenance"
    if s == "hors service":
        return "hors_service"
    return "other"


def _sc(status: str) -> str:
    return _STATUS_COLOR.get((status or "").lower(), C["text2"])


def _days_color(days_left: int) -> str:
    if days_left < 0:
        return C["danger"]
    if days_left <= 7:
        return C["danger"]
    if days_left <= 30:
        return C["warning"]
    return C["success"]


def _ensure_column(conn, table: str, col: str, defn: str = "TEXT"):
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
        conn.commit()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT BANNER — Documents expirants
# ═══════════════════════════════════════════════════════════════════════════════

class _ExpireBanner(QFrame):
    """Bandeau compact listant les documents de véhicules expirant dans 30 jours."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:#2A1A0A;border:1px solid {C['warning']};"
            "border-radius:6px;padding:4px;}}"
            f"QLabel{{background:transparent;color:{C['warning']};font-size:12px;}}"
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(10, 6, 10, 6)
        lo.setSpacing(3)

        hdr = QHBoxLayout()
        icon = QLabel("  Documents expirants :")
        icon.setStyleSheet(f"color:{C['warning']};font-weight:700;font-size:12px;background:transparent;")
        hdr.addWidget(icon)
        hdr.addStretch()
        dismiss = QPushButton("×")
        dismiss.setToolTip("Masquer le bandeau")
        dismiss.setFixedSize(20, 20)
        dismiss.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;color:{C['warning']};"
            "font-size:16px;}} QPushButton:hover{color:#fff;}"
        )
        dismiss.clicked.connect(lambda: self.setVisible(False))
        hdr.addWidget(dismiss)
        lo.addLayout(hdr)

        self._items_layout = QVBoxLayout()
        self._items_layout.setSpacing(1)
        lo.addLayout(self._items_layout)
        self.setVisible(False)

    def refresh(self):
        # Clear old items
        for i in reversed(range(self._items_layout.count())):
            w = self._items_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        docs = get_expiring_documents(30)
        if not docs:
            self.setVisible(False)
            return

        for d in docs[:6]:
            days  = d["days_left"]
            color = _days_color(days)
            if days < 0:
                txt = f"  {d['registration']} — {d['doc_type']} : EXPIRÉ depuis {abs(days)} j"
            else:
                txt = f"  {d['registration']} — {d['doc_type']} : expire dans {days} j ({d['expiry_date']})"
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color:{color};font-size:11px;background:transparent;")
            self._items_layout.addWidget(lbl)

        if len(docs) > 6:
            more = QLabel(f"  … et {len(docs) - 6} autre(s)")
            more.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            self._items_layout.addWidget(more)

        self.setVisible(True)


# ═══════════════════════════════════════════════════════════════════════════════
# CALENDAR DIALOG — Disponibilité mensuelle
# ═══════════════════════════════════════════════════════════════════════════════

class _CalendarDialog(QDialog):
    """Grille mensuelle de disponibilité — clic pour créer/supprimer une indisponibilité."""

    _TABLE = "vehicle_unavailabilities"

    def __init__(self, vehicle_id: int, registration: str, parent=None):
        super().__init__(parent)
        self.vid  = vehicle_id
        self.reg  = registration
        self._year  = date.today().year
        self._month = date.today().month
        self._unavail: set[str] = set()

        self.setWindowTitle(f"Disponibilité — {registration}")
        self.setMinimumSize(500, 420)
        self.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            f"QLabel{{background:transparent;color:{C['text']};}}"
        )
        self._ensure_table()
        self._setup_ui()
        self._load_month()

    def _ensure_table(self):
        try:
            conn = get_connection()
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._TABLE} (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id  INTEGER NOT NULL,
                    date        TEXT    NOT NULL,
                    reason      TEXT,
                    UNIQUE(vehicle_id, date)
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _setup_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 12)
        lo.setSpacing(10)

        # Nav bar
        nav = QHBoxLayout()
        prev = QPushButton("<")
        prev.setFixedSize(32, 28)
        prev.setToolTip("Mois précédent")
        prev.clicked.connect(lambda: self._nav(-1))
        nxt = QPushButton(">")
        nxt.setFixedSize(32, 28)
        nxt.setToolTip("Mois suivant")
        nxt.clicked.connect(lambda: self._nav(1))
        self._month_lbl = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._month_lbl.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;")
        nav.addWidget(prev)
        nav.addWidget(self._month_lbl, 1)
        nav.addWidget(nxt)
        lo.addLayout(nav)

        # Legend
        leg = QHBoxLayout()
        for color, label in [(C["success"], "Disponible"), (C["danger"], "Indisponible")]:
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background:{color};border-radius:5px;")
            leg.addWidget(dot)
            leg.addWidget(QLabel(label))
            leg.addSpacing(16)
        leg.addStretch()
        lo.addLayout(leg)

        # Calendar grid
        self._grid = QGridLayout()
        self._grid.setSpacing(4)
        lo.addLayout(self._grid)
        lo.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close = QPushButton("Fermer")
        close.setObjectName("secondaryBtn")
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        lo.addLayout(btn_row)

    def _nav(self, delta: int):
        m = self._month + delta
        y = self._year
        if m < 1:
            m = 12; y -= 1
        elif m > 12:
            m = 1; y += 1
        self._month = m
        self._year  = y
        self._load_month()

    def _load_month(self):
        self._month_lbl.setText(
            f"{calendar.month_name[self._month]} {self._year}"
        )
        # Load unavailabilities
        self._unavail.clear()
        try:
            conn = get_connection()
            rows = conn.execute(
                f"SELECT date FROM {self._TABLE} WHERE vehicle_id=?"
                " AND date LIKE ?",
                (self.vid, f"{self._year:04d}-{self._month:02d}-%")
            ).fetchall()
            conn.close()
            self._unavail = {r[0] for r in rows}
        except Exception:
            pass
        self._rebuild_grid()

    def _rebuild_grid(self):
        # Clear grid
        for i in reversed(range(self._grid.count())):
            item = self._grid.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        # Day-of-week headers
        _HDR_STYLE = (
            f"QLabel{{color:{C['text2']};font-size:11px;font-weight:600;"
            "text-align:center;background:transparent;}}"
        )
        for col, day in enumerate(_DAYS_FR):
            h = QLabel(day, alignment=Qt.AlignmentFlag.AlignCenter)
            h.setStyleSheet(_HDR_STYLE)
            self._grid.addWidget(h, 0, col)

        # Days
        cal = calendar.monthcalendar(self._year, self._month)
        _DAY_BASE = (
            "QPushButton{border-radius:4px;font-size:12px;font-weight:600;"
            "border:1px solid %s;color:%s;background:%s;}"
            "QPushButton:hover{border-color:%s;}"
        )
        for row_idx, week in enumerate(cal):
            for col_idx, day in enumerate(week):
                if day == 0:
                    continue
                d_str = f"{self._year:04d}-{self._month:02d}-{day:02d}"
                is_unavail = d_str in self._unavail
                today = date.today()
                is_today = (date(self._year, self._month, day) == today)

                if is_unavail:
                    bg, fg, bd = "#3A1020", C["danger"], C["danger"]
                elif is_today:
                    bg, fg, bd = C["hover"], C["accent"], C["accent"]
                else:
                    bg, fg, bd = C["input"], C["text"], C["border"]

                btn = QPushButton(str(day))
                btn.setFixedSize(40, 34)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(_DAY_BASE % (bd, fg, bg, C["accent"]))
                btn.clicked.connect(
                    lambda _, ds=d_str: self._toggle_day(ds))
                self._grid.addWidget(btn, row_idx + 1, col_idx)

    def _toggle_day(self, d_str: str):
        try:
            conn = get_connection()
            if d_str in self._unavail:
                conn.execute(
                    f"DELETE FROM {self._TABLE} WHERE vehicle_id= ? AND date= ?",
                    (self.vid, d_str)
                )
                self._unavail.discard(d_str)
            else:
                conn.execute(
                    f"INSERT OR IGNORE INTO {self._TABLE} (vehicle_id, date) VALUES (?,?)",
                    (self.vid, d_str)
                )
                self._unavail.add(d_str)
            conn.commit()
            conn.close()
            log_action("VEHICLE_UNAVAIL",
                       f"Véhicule #{self.vid} : toggle indisponibilité {d_str}")
        except Exception as e:
            logger.exception("CalendarDialog toggle error")
        self._rebuild_grid()


# ═══════════════════════════════════════════════════════════════════════════════
# FLEET STATS DIALOG — KPICards + Camembert
# ═══════════════════════════════════════════════════════════════════════════════

class _FleetStatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Statistiques flotte")
        self.resize(700, 500)
        self.setStyleSheet(
            _dialog_qss() + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(20, 20, 20, 12)
        lo.setSpacing(14)

        conn = get_connection()
        rows = conn.execute("SELECT status FROM vehicles").fetchall()
        total = len(rows)
        by_status: dict[str, int] = {}
        for r in rows:
            b = _normalize_vehicle_status_bucket(r["status"])
            by_status[b] = by_status.get(b, 0) + 1
        avail = by_status.get("disponible", 0)
        en_sv = by_status.get("en_service", 0)
        maint = by_status.get("maintenance", 0)
        hors  = by_status.get("hors_service", 0)
        other = by_status.get("other", 0)

        try:
            km_total = conn.execute(
                "SELECT COALESCE(SUM(total_distance),0) FROM algo_results"
            ).fetchone()[0] or 0
        except Exception:
            km_total = 0

        try:
            co2 = conn.execute(
                "SELECT COALESCE(SUM(co2_total),0) FROM algo_results"
            ).fetchone()[0] or 0
        except Exception:
            co2 = 0
        conn.close()

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        for label, val, sub, icon in [
            ("Total flotte",  str(total), "véhicules",     ""),
            ("Disponibles",   str(avail), "prêts",         ""),
            ("En service",    str(en_sv), "actifs",        ""),
            ("Maintenance",   str(maint), "en atelier",    ""),
            ("Hors service",  str(hors),  "indisponibles", ""),
        ]:
            card = KPICard(label, val, unit=sub, icon=icon)
            kpi_row.addWidget(card)
        lo.addLayout(kpi_row)

        extra_row = QHBoxLayout()
        extra_row.setSpacing(10)
        for label, val, sub, icon in [
            ("km optimisés", f"{km_total:,.0f}", "tous algos", ""),
            ("CO2 estimé",   f"{co2:.1f} kg",   "émis total", ""),
        ]:
            card = KPICard(label, val, unit=sub, icon=icon)
            extra_row.addWidget(card)
        extra_row.addStretch()
        lo.addLayout(extra_row)

        # Pie chart
        if HAS_MPL and total > 0:
            sizes  = [avail, en_sv, maint, hors, other]
            labels = ["Disponible", "En service", "Maintenance", "Hors service", "Autre"]
            colors = ["#00FF88", "#00D4FF", "#FFB800", "#FF4757", "#8899AA"]
            sizes_f  = [s for s in sizes if s > 0]
            labels_f = [l for l, s in zip(labels, sizes) if s > 0]
            colors_f = [c for c, s in zip(colors, sizes) if s > 0]

            fig, ax = plt.subplots(figsize=(5, 3.2), dpi=90)
            fig.patch.set_facecolor("#0D1B2A")
            ax.set_facecolor("#0D1B2A")
            wedges, texts, autotexts = ax.pie(
                sizes_f, labels=labels_f, colors=colors_f,
                autopct="%1.0f%%", startangle=90,
                textprops={"color": "#E8F4FD", "fontsize": 9},
            )
            for at in autotexts:
                at.set_color("#0D1B2A")
                at.set_fontweight("bold")
            ax.set_title("Répartition statuts flotte",
                         color="#E8F4FD", fontsize=11, pad=10)
            canvas = FigCanvas(fig)
            canvas.setFixedHeight(280)
            lo.addWidget(canvas)
            plt.close(fig)
        else:
            lo.addWidget(QLabel("(Matplotlib requis pour le graphique)"))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close = QPushButton("Fermer")
        close.setObjectName("secondaryBtn")
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        lo.addLayout(btn_row)


# ═══════════════════════════════════════════════════════════════════════════════
# VEHICLE DIALOG — 7 onglets
# ═══════════════════════════════════════════════════════════════════════════════

class _VehicleDialog(QDialog):

    def __init__(self, parent=None, vehicle: dict = None):
        super().__init__(parent)
        self.vehicle = vehicle or {}
        self.setWindowTitle("Modifier véhicule" if vehicle else "Nouveau véhicule")
        self.setMinimumSize(660, 520)
        self.resize(720, 560)
        self.setModal(True)
        self.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            f"QTabWidget::pane{{background:{C['panel']};border:1px solid {C['border']};border-radius:6px;}}"
            f"QTabBar::tab{{background:{C['input']};color:{C['text2']};padding:7px 12px;"
            "border-top-left-radius:4px;border-top-right-radius:4px;margin-right:2px;font-size:11px;}"
            f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
            f"QTabBar::tab:hover{{background:{C['hover']};}}"
            f"QLineEdit,QDoubleSpinBox,QSpinBox,QComboBox,QDateEdit{{background:{C['input']};"
            f"color:{C['text']};border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
            f"QCheckBox{{color:{C['text']};background:transparent;spacing:6px;}}"
            f"QLabel{{background:transparent;color:{C['text']};}}"
            f"QGroupBox{{color:{C['text2']};border:1px solid {C['border']};"
            "border-radius:5px;margin-top:10px;padding-top:8px;font-size:11px;}"
            f"QGroupBox::title{{subcontrol-origin:margin;left:10px;}}"
        )
        self._setup_ui()

    # ── helpers ───────────────────────────────────────────────────────
    def _lbl(self, t: str) -> QLabel:
        l = QLabel(t)
        l.setStyleSheet(f"color:{C['text2']};font-size:11px;")
        return l

    def _le(self, val="", ph="") -> QLineEdit:
        w = QLineEdit(str(val) if val else "")
        w.setPlaceholderText(ph)
        return w

    def _spin(self, val=0, mn=0, mx=99999, step=1, dec=0):
        if dec:
            w = QDoubleSpinBox()
            w.setDecimals(dec)
            fmn, fmx = float(mn), float(mx)
            w.setRange(fmn, fmx)
            w.setSingleStep(float(step))
            fv = float(val or 0)
            w.setValue(min(fmx, max(fmn, fv)))
        else:
            w = QSpinBox()
            imn, imx = int(mn), int(mx)
            w.setRange(imn, imx)
            istep = int(round(float(step)))
            w.setSingleStep(istep if istep > 0 else 1)
            iv = int(round(float(val or 0)))
            w.setValue(min(imx, max(imn, iv)))
        return w

    def _combo(self, items, cur="") -> QComboBox:
        w = QComboBox()
        w.addItems(items)
        idx = w.findText(str(cur or ""))
        if idx >= 0:
            w.setCurrentIndex(idx)
        return w

    def _chk(self, val, label="") -> QCheckBox:
        w = QCheckBox(label)
        w.setChecked(bool(val))
        return w

    def _check_driver_conflict(self):
        """Affiche un avertissement si le chauffeur sélectionné est déjà assigné à un autre véhicule."""
        if not hasattr(self, "_driver_conflict_lbl"):
            return
        did = self._driver_combo.currentData()
        if not did:
            self._driver_conflict_lbl.setText("")
            return
        try:
            info = get_driver_vehicle_info(driver_id=did)
            existing_vid = (info.get("vehicle") or {}).get("id")
            current_vid  = self.vehicle.get("id")
            if existing_vid and existing_vid != current_vid:
                reg = (info.get("vehicle") or {}).get("registration", f"#{existing_vid}")
                self._driver_conflict_lbl.setText(
                    f"Attention : ce chauffeur est actuellement assigné au véhicule {reg}. "
                    f"En enregistrant, il sera automatiquement désassigné de ce véhicule."
                )
            else:
                self._driver_conflict_lbl.setText("")
        except Exception:
            self._driver_conflict_lbl.setText("")

    def _date_edit(self, val: str = "") -> QDateEdit:
        w = QDateEdit()
        w.setCalendarPopup(True)
        w.setDisplayFormat("yyyy-MM-dd")
        if val:
            try:
                dt = datetime.strptime(val[:10], "%Y-%m-%d")
                w.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                w.setDate(QDate.currentDate())
        else:
            w.setDate(QDate.currentDate())
        return w

    def _date_val(self, widget: QDateEdit) -> str:
        return widget.date().toString("yyyy-MM-dd")

    # ── UI setup ──────────────────────────────────────────────────────
    def _setup_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 12)
        lo.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._tab_identity(),   "  Identité  ")
        self._tabs.addTab(self._tab_capacities(), "  Capacités  ")
        self._tabs.addTab(self._tab_speeds(),     "  Vitesses  ")
        self._tabs.addTab(self._tab_costs(),      "  Coûts  ")
        self._tabs.addTab(self._tab_driver(),     "  Chauffeur  ")
        self._tabs.addTab(self._tab_documents(),  "  Documents  ")
        self._tabs.addTab(self._tab_dispo(),      "  Dispo & Stats  ")
        lo.addWidget(self._tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setObjectName("secondaryBtn")
        cancel.setFixedHeight(34)
        cancel.clicked.connect(self.reject)
        save = QPushButton("Sauvegarder")
        save.setObjectName("primaryBtn")
        save.setFixedHeight(34)
        save.setMinimumWidth(120)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        lo.addLayout(btn_row)

    # ── Tab 0 : Identité ──────────────────────────────────────────────
    def _tab_identity(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        fl.setContentsMargins(16, 16, 16, 8)
        v = self.vehicle

        self._reg    = self._le(v.get("registration", ""), "ex: MA-123-A-45 *")
        self._brand  = self._le(v.get("brand", ""),        "ex: Renault")
        self._model  = self._le(v.get("model", ""),        "ex: Master L2H2")
        self._year   = self._spin(v.get("year", 2020), 1990, 2035)
        self._vtype  = self._combo(_VEH_TYPES,  v.get("type") or v.get("vehicle_type") or "fourgon")
        self._fuel   = self._combo(_FUEL_TYPES, v.get("fuel_type") or "diesel")

        # Photo (aperçu + chemin)
        photo_block = QVBoxLayout()
        photo_block.setSpacing(8)
        photo_row = QHBoxLayout()
        self._photo = self._le(v.get("photo_url", ""), "Chemin, fichier local ou URL")
        browse_btn = QPushButton("Parcourir…")
        browse_btn.setFixedHeight(28)
        browse_btn.clicked.connect(self._browse_photo)
        photo_row.addWidget(self._photo)
        photo_row.addWidget(browse_btn)
        photo_block.addLayout(photo_row)
        self._photo_preview = QLabel()
        self._photo_preview.setFixedSize(120, 120)
        self._photo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_preview.setStyleSheet(
            f"background:{C['input']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:6px;font-size:22px;"
        )
        self._photo_preview.setText("—")
        photo_block.addWidget(self._photo_preview, alignment=Qt.AlignmentFlag.AlignLeft)
        self._photo.textChanged.connect(self._update_vehicle_photo_preview)
        self._update_vehicle_photo_preview()

        fl.addRow(self._lbl("Immatriculation *"), self._reg)
        fl.addRow(self._lbl("Marque"),            self._brand)
        fl.addRow(self._lbl("Modèle"),            self._model)
        fl.addRow(self._lbl("Année"),             self._year)
        fl.addRow(self._lbl("Type"),              self._vtype)
        fl.addRow(self._lbl("Motorisation"),      self._fuel)
        wrap = QWidget()
        wrap_lo = QVBoxLayout(wrap)
        wrap_lo.setContentsMargins(0, 0, 0, 0)
        wrap_lo.addLayout(photo_block)
        fl.addRow(self._lbl("Photo"),             wrap)
        return w

    def _update_vehicle_photo_preview(self, *_):
        p = self._photo.text().strip()
        if p.lower().startswith(("http://", "https://")):
            self._photo_preview.clear()
            self._photo_preview.setText("")
            return
        abs_p = resolve_stored_photo(p)
        if abs_p:
            pm = QPixmap(abs_p).scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._photo_preview.setPixmap(pm)
            self._photo_preview.setText("")
        else:
            self._photo_preview.clear()
            self._photo_preview.setText("—")

    def _browse_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner photo", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        if not is_allowed_image_filename(path):
            QMessageBox.warning(
                self, "Photo",
                "Formats autorisés : PNG, JPEG, WebP, BMP.",
            )
            return
        self._photo.setText(path)

    # ── Tab 1 : Capacités ─────────────────────────────────────────────
    def _tab_capacities(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        fl.setContentsMargins(16, 16, 16, 8)
        v = self.vehicle

        self._cap_kg    = self._spin(v.get("capacity_kg", 1000),  0, 99999, 50, 1)
        self._cap_m3    = self._spin(v.get("capacity_m3",  10),   0,  9999,  1, 2)
        self._palettes  = self._spin(v.get("palettes", 0),       0,   100)
        self._h_cm      = self._spin(v.get("max_height_cm",  0), 0,  5000)
        self._w_cm      = self._spin(v.get("max_width_cm",   0), 0,  5000)
        self._l_cm      = self._spin(v.get("max_length_cm",  0), 0, 25000)
        self._co2       = self._spin(v.get("co2_per_km", 0.21),  0,  5,   0.01, 3)
        self._fuel_conso = self._spin(v.get("fuel_consumption_l100km", 0.0), 0, 200, 0.5, 1)
        # Si 0 et motorisation connue, pré-estimer
        if not v.get("fuel_consumption_l100km"):
            fuel = (v.get("fuel_type") or "diesel").lower()
            vtype = (v.get("type") or v.get("vehicle_type") or "fourgon").lower()
            for (vk, fk), (conso, _co2) in self._CONSO_TABLE.items():
                if vk in vtype and fk in fuel:
                    self._fuel_conso.setValue(conso); break
            else:
                self._fuel_conso.setValue(12.0 if "électrique" not in fuel else 20.0)

        self._adr  = self._chk(v.get("allowed_adr", 0), "Autorisé matières dangereuses (ADR)")
        self._zfe  = self._chk(v.get("allowed_zfe", 1), "Autorisé zones faibles émissions (ZFE)")

        dims_row = QHBoxLayout()
        for lbl, spin in [("H", self._h_cm), ("L", self._w_cm), ("Lo", self._l_cm)]:
            dims_row.addWidget(QLabel(lbl))
            dims_row.addWidget(spin)
        dims_row.addStretch()

        # Ligne consommation + bouton Estimer
        self._conso_lbl = self._lbl("Consommation (L/100km)")
        conso_row = QHBoxLayout()
        conso_row.addWidget(self._fuel_conso)
        est_btn = QPushButton("⟳ Estimer")
        est_btn.setFixedSize(76, 26)
        est_btn.setToolTip("Pré-remplir selon type de véhicule et motorisation")
        est_btn.setStyleSheet(
            f"QPushButton{{background:#1A2E4A;color:#8899AA;border:1px solid #1E3A5F;"
            "border-radius:4px;font-size:11px;}}"
            f"QPushButton:hover{{color:#E8F4FD;border-color:#00D4FF;}}"
        )
        est_btn.clicked.connect(self._auto_estimate_consumption)
        conso_row.addWidget(est_btn)
        conso_row.addStretch()

        fl.addRow(self._lbl("Poids max (kg)"),   self._cap_kg)
        fl.addRow(self._lbl("Volume (m³)"),       self._cap_m3)
        fl.addRow(self._lbl("Palettes"),          self._palettes)
        fl.addRow(self._lbl("Dimensions (cm)"),   dims_row)
        fl.addRow(self._conso_lbl,                conso_row)
        fl.addRow(self._lbl("CO2 (kg/km)"),       self._co2)
        fl.addRow("",                             self._adr)
        fl.addRow("",                             self._zfe)
        return w

    # Estimation automatique consommation
    _CONSO_TABLE = {
        # (vehicle_type_keyword, fuel_keyword) → (L/100km, CO2 kg/km)
        ("semi",       "diesel"):     (35.0, 0.92),
        ("semi",       "gaz"):        (28.0, 0.56),
        ("poids",      "diesel"):     (28.0, 0.74),
        ("poids",      "hybride"):    (18.0, 0.48),
        ("poids",      "gaz"):        (22.0, 0.44),
        ("frigorif",   "diesel"):     (20.0, 0.53),
        ("camion",     "diesel"):     (16.0, 0.42),
        ("camion",     "essence"):    (14.0, 0.38),
        ("camionnette","diesel"):     (12.0, 0.32),
        ("camionnette","essence"):    (11.0, 0.30),
        ("camionnette","électrique"): (22.0, 0.0),   # kWh/100km
        ("camionnette","hybride"):    ( 7.0, 0.19),
        ("utilitaire", "diesel"):     (11.0, 0.29),
        ("utilitaire", "essence"):    (10.0, 0.27),
        ("utilitaire", "électrique"): (20.0, 0.0),
        ("utilitaire", "hybride"):    ( 6.5, 0.17),
        ("fourgon",    "diesel"):     (10.0, 0.26),
        ("fourgon",    "essence"):    ( 9.0, 0.24),
        ("fourgon",    "électrique"): (18.0, 0.0),
        ("fourgon",    "hybride"):    ( 6.0, 0.16),
        ("fourgon",    "gaz"):        ( 8.0, 0.16),
        ("moto",       "essence"):    ( 4.5, 0.12),
        ("moto",       "électrique"): ( 5.0, 0.0),
        ("vélo",       "électrique"): ( 2.0, 0.0),
        ("vélo",       ""):           ( 0.0, 0.0),
    }

    def _auto_estimate_consumption(self):
        vtype = self._vtype.currentText().lower()
        fuel  = self._fuel.currentText().lower()
        for (vk, fk), (conso, co2) in self._CONSO_TABLE.items():
            if vk in vtype and fk in fuel:
                self._fuel_conso.setValue(conso)
                self._co2.setValue(co2)
                # Adapter le libellé si électrique
                is_elec = "électrique" in fuel
                self._conso_lbl.setText(
                    "Consommation (kWh/100km)" if is_elec else "Consommation (L/100km)"
                )
                return
        # Fallback générique
        self._fuel_conso.setValue(12.0 if "électrique" not in fuel else 20.0)
        self._co2.setValue(0.0 if "électrique" in fuel else 0.27)

    # ── Tab 2 : Vitesses ──────────────────────────────────────────────
    def _tab_speeds(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        fl.setContentsMargins(16, 16, 16, 8)
        v = self.vehicle

        self._sp_hw  = self._spin(v.get("speed_highway",  110), 1, 200)
        self._sp_nat = self._spin(v.get("speed_national",  80), 1, 200)
        self._sp_urb = self._spin(v.get("speed_urban",     45), 1, 200)
        self._sp_z30 = self._spin(v.get("speed_zone30",    25), 1, 100)

        note = QLabel(
            "Ces vitesses sont utilisées par le moteur OSRM pour le calcul des\n"
            "temps de trajet selon le type de route."
        )
        note.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")

        def _row(lbl, spin, icon=""):
            rw = QHBoxLayout()
            rw.addWidget(spin)
            rw.addWidget(QLabel("km/h"))
            rw.addStretch()
            return rw

        fl.addRow(self._lbl("Autoroute"),   _row("", self._sp_hw))
        fl.addRow(self._lbl("Nationale"),   _row("", self._sp_nat))
        fl.addRow(self._lbl("Urbaine"),     _row("", self._sp_urb))
        fl.addRow(self._lbl("Zone 30"),     _row("", self._sp_z30))
        fl.addRow("", note)
        return w

    # ── Tab 3 : Coûts ─────────────────────────────────────────────────
    def _tab_costs(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        fl.setContentsMargins(16, 16, 16, 8)
        v = self.vehicle

        self._cost_km   = self._spin(v.get("cost_per_km",          0.5), 0, 100, 0.01, 3)
        self._cost_hr   = self._spin(v.get("cost_per_hour",        15.0), 0, 500, 0.5,  2)
        self._cost_fix  = self._spin(v.get("cost_fixed_daily",     50.0), 0, 9999, 1,   2)
        self._cost_idle = self._spin(v.get("cost_non_utilisation",  0.0), 0, 9999, 1,   2)

        note = QLabel(
            "Coût/km : carburant + usure\nCoût/h : chauffeur + frais\n"
            "Fixe/j : assurance + amortissement\n"
            "Non-utilisation/j : pénalité d'immobilisation"
        )
        note.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")

        fl.addRow(self._lbl("Coût / km (€)"),           self._cost_km)
        fl.addRow(self._lbl("Coût / heure (€)"),        self._cost_hr)
        fl.addRow(self._lbl("Coût fixe / jour (€)"),    self._cost_fix)
        fl.addRow(self._lbl("Non-utilisation / jour (€)"), self._cost_idle)
        fl.addRow("", note)
        return w

    # ── Tab 4 : Chauffeur ─────────────────────────────────────────────
    def _tab_driver(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        fl.setContentsMargins(16, 16, 16, 8)
        v = self.vehicle

        from PyQt6.QtCore import Qt as _Qt
        from PyQt6.QtWidgets import QCompleter as _QCompleter
        self._driver_combo = QComboBox()
        self._driver_combo.setEditable(True)
        self._driver_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._driver_combo.setMinimumHeight(36)
        # Style direct : flèche visible sur fond sombre
        self._driver_combo.setStyleSheet("""
            QComboBox {
                background: #0A1628;
                color: #E8F4F8;
                border: 2px solid #2E5F88;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
            }
            QComboBox:focus { border: 2px solid #00D4FF; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #2E5F88;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QComboBox::down-arrow {
                width: 10px; height: 10px;
                border-left: 2px solid #7FA8C0;
                border-bottom: 2px solid #7FA8C0;
                transform: rotate(-45deg);
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background: #162840;
                color: #E8F4F8;
                border: 1px solid #1E3A50;
                selection-background-color: #00D4FF;
                selection-color: #0D1B2A;
                outline: none;
            }
        """)
        self._driver_combo.addItem("— Aucun chauffeur assigné —", None)
        self._driver_id: int | None = None
        try:
            conn = get_connection()
            cur_did = v.get("driver_id")
            if cur_did is not None:
                where_sql = "WHERE (COALESCE(archived, 0)=0) OR id=?"
                params_d: tuple = (cur_did,)
            else:
                where_sql = "WHERE COALESCE(archived, 0)=0"
                params_d = ()
            drivers = conn.execute(
                f"SELECT id, "
                f"COALESCE(first_name,'') AS first_name, "
                f"COALESCE(last_name,'') AS last_name, "
                f"COALESCE(license_number,'') AS license_number "
                f"FROM drivers {where_sql} "
                f"ORDER BY LOWER(COALESCE(last_name,'')), LOWER(COALESCE(first_name,''))",
                params_d,
            ).fetchall()
            conn.close()
            for d in drivers:
                first = (d["first_name"] or "").strip()
                last  = (d["last_name"]  or "").strip()
                full_name = f"{first} {last}".strip() or f"Chauffeur #{d['id']}"
                lic = (d["license_number"] or "").strip()
                label = f"{full_name}  —  {lic}" if lic else full_name
                self._driver_combo.addItem(label, d["id"])
            # Compléteur de recherche
            completer = _QCompleter(
                [self._driver_combo.itemText(i) for i in range(self._driver_combo.count())]
            )
            completer.setFilterMode(_Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(_Qt.CaseSensitivity.CaseInsensitive)
            self._driver_combo.setCompleter(completer)
            # Pré-sélection du chauffeur déjà assigné
            cur_name = v.get("driver_name") or ""
            for i in range(1, self._driver_combo.count()):
                item_data = self._driver_combo.itemData(i)
                item_text = self._driver_combo.itemText(i)
                if cur_did is not None and str(item_data) == str(cur_did):
                    self._driver_combo.setCurrentIndex(i)
                    break
                if cur_name and cur_name in item_text:
                    self._driver_combo.setCurrentIndex(i)
                    break
        except Exception:
            logger.exception("Erreur chargement liste chauffeurs dans dialog véhicule")

        # Avertissement conflit d'affectation
        self._driver_conflict_lbl = QLabel("")
        self._driver_conflict_lbl.setWordWrap(True)
        self._driver_conflict_lbl.setStyleSheet(
            "color:#FFB800;font-size:11px;border:none;background:transparent;"
        )
        self._driver_combo.currentIndexChanged.connect(self._check_driver_conflict)
        self._check_driver_conflict()  # vérification initiale

        self._open_start  = self._chk(v.get("open_start", 0),   "Départ ouvert (open start)")
        self._open_stop   = self._chk(v.get("open_stop", 0),    "Arrivée ouverte (open stop)")
        self._reload      = self._chk(v.get("reload_allowed", 1),"Rechargement autorisé")

        fl.addRow(self._lbl("Chauffeur assigné"), self._driver_combo)
        fl.addRow("", self._driver_conflict_lbl)
        fl.addRow("", self._open_start)
        fl.addRow("", self._open_stop)
        fl.addRow("", self._reload)
        return w

    # ── Tab 5 : Documents ─────────────────────────────────────────────
    def _tab_documents(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        fl.setContentsMargins(16, 16, 16, 8)
        v = self.vehicle

        self._ins_expiry = self._date_edit(v.get("insurance_expiry") or "")
        self._ct_expiry  = self._date_edit(v.get("technical_inspection_expiry") or "")
        self._ins_num    = self._le(v.get("insurance_number") or "", "N° police d'assurance")

        # Alert indicators
        today = date.today()
        for label, col in [("Assurance", "insurance_expiry"),
                            ("CT",        "technical_inspection_expiry")]:
            val = v.get(col) or ""
            if val:
                try:
                    exp = datetime.strptime(val[:10], "%Y-%m-%d").date()
                    dl  = (exp - today).days
                    if dl < 0:
                        status_lbl = QLabel(f"  EXPIRÉ depuis {abs(dl)} jours")
                        status_lbl.setStyleSheet(f"color:{C['danger']};font-size:11px;background:transparent;")
                    elif dl <= 30:
                        status_lbl = QLabel(f"  Expire dans {dl} jours")
                        status_lbl.setStyleSheet(f"color:{C['warning']};font-size:11px;background:transparent;")
                    else:
                        status_lbl = QLabel(f"  Valide encore {dl} jours")
                        status_lbl.setStyleSheet(f"color:{C['success']};font-size:11px;background:transparent;")
                    fl.addRow(self._lbl(label + " — expiration"), getattr(
                        self, "_ins_expiry" if label == "Assurance" else "_ct_expiry"))
                    fl.addRow("", status_lbl)
                    continue
                except Exception:
                    pass
            fl.addRow(
                self._lbl(label + " — expiration"),
                self._ins_expiry if label == "Assurance" else self._ct_expiry
            )

        fl.addRow(self._lbl("N° assurance"),       self._ins_num)

        note = QLabel(
            "Les alertes s'affichent automatiquement si l'expiration\n"
            "est dans moins de 30 jours."
        )
        note.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        fl.addRow("", note)
        return w

    # ── Tab 6 : Dispo & Stats ─────────────────────────────────────────
    def _tab_dispo(self) -> QWidget:
        outer = QWidget()
        outer_lo = QVBoxLayout(outer)
        outer_lo.setContentsMargins(0, 0, 0, 0)
        outer_lo.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(420)

        inner = QWidget()
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lo = QVBoxLayout(inner)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(16)
        v = self.vehicle

        _grp_qss = (
            f"QGroupBox{{color:{C['text2']};border:1px solid {C['border']};"
            "border-radius:6px;margin-top:18px;padding-top:14px;padding-bottom:10px;}"
            f"QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;"
            f"left:12px;padding:4px 6px 0 6px;color:{C['text']};font-weight:600;}}"
        )

        fl = QFormLayout()
        fl.setSpacing(8)

        # Dépôt d'attache
        self._depot_combo = QComboBox()
        self._depot_combo.addItem("(Aucun)", None)
        try:
            conn = get_connection()
            depots = conn.execute("SELECT id, name FROM depots ORDER BY name").fetchall()
            conn.close()
            for d in depots:
                self._depot_combo.addItem(d["name"], d["id"])
            cur_did = v.get("depot_id")
            for i in range(1, self._depot_combo.count()):
                if self._depot_combo.itemData(i) == cur_did:
                    self._depot_combo.setCurrentIndex(i)
                    break
        except Exception:
            pass
        fl.addRow(self._lbl("Dépôt d'attache"), self._depot_combo)
        lo.addLayout(fl)

        # Planning hebdo (grille 2 lignes : évite bandeau trop bas et titres qui se chevauchent)
        schedule_grp = QGroupBox("Planning hebdomadaire")
        schedule_grp.setStyleSheet(_grp_qss)
        sched_lo = QGridLayout(schedule_grp)
        sched_lo.setHorizontalSpacing(12)
        sched_lo.setVerticalSpacing(8)
        try:
            sched = _json.loads(v.get("weekly_schedule") or "{}")
        except Exception:
            sched = {}
        day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self._sched_cbs: dict[str, QCheckBox] = {}
        for i, (key, label) in enumerate(zip(day_keys, _DAYS_FR)):
            cb = QCheckBox(label)
            cb.setChecked(sched.get(key, key not in ("sat", "sun")))
            cb.setStyleSheet(f"QCheckBox{{color:{C['text']};background:transparent;spacing:4px;}}")
            self._sched_cbs[key] = cb
            sched_lo.addWidget(cb, i // 4, i % 4)
        lo.addWidget(schedule_grp)

        # Stats tournées
        stats_grp = QGroupBox("Statistiques (toutes tournées)")
        stats_grp.setStyleSheet(_grp_qss)
        stats_fl = QFormLayout(stats_grp)
        stats_fl.setSpacing(8)
        stats_fl.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        vid = v.get("id")
        km_total = nb_tours = cout_total = 0
        if vid:
            try:
                conn = get_connection()
                res = conn.execute("""
                    SELECT COUNT(*) as nb, COALESCE(SUM(total_distance),0) as km,
                           COALESCE(SUM(total_cost),0) as cout
                    FROM algo_results WHERE vehicle_id=?
                """, (vid,)).fetchone()
                conn.close()
                if res:
                    nb_tours   = res["nb"] or 0
                    km_total   = res["km"] or 0
                    cout_total = res["cout"] or 0
            except Exception:
                pass

        for lbl, val in [
            ("Km totaux",     f"{km_total:,.1f} km"),
            ("Nb tournées",   str(nb_tours)),
            ("Coût total",    f"{cout_total:,.2f} €"),
        ]:
            lbl_w = QLabel(lbl)
            lbl_w.setWordWrap(True)
            lbl_w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            lbl_w.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            val_w = QLabel(val)
            val_w.setWordWrap(True)
            val_w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            val_w.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;background:transparent;")
            stats_fl.addRow(lbl_w, val_w)
        lo.addWidget(stats_grp)
        lo.addStretch()

        scroll.setWidget(inner)
        outer_lo.addWidget(scroll)
        return outer

    # ── Save ──────────────────────────────────────────────────────────
    def _on_save(self):
        if not self._reg.text().strip():
            QMessageBox.warning(self, "Validation", "L'immatriculation est obligatoire.")
            return
        self.accept()

    def get_data(self) -> dict:
        driver_id   = self._driver_combo.currentData()
        raw_name    = self._driver_combo.currentText().split("  —  ")[0].strip()
        driver_name = "" if raw_name.startswith("—") else raw_name
        sched = {k: cb.isChecked() for k, cb in self._sched_cbs.items()}
        return {
            # Identité
            "registration":  self._reg.text().strip().upper(),
            "brand":         self._brand.text().strip(),
            "model":         self._model.text().strip(),
            "year":          self._year.value(),
            "type":          self._vtype.currentText(),
            "vehicle_type":  self._vtype.currentText(),
            "fuel_type":     self._fuel.currentText(),
            "photo_url":     self._photo.text().strip(),
            # Capacités
            "capacity_kg":   self._cap_kg.value(),
            "capacity_m3":   self._cap_m3.value(),
            "palettes":      self._palettes.value(),
            "max_height_cm": self._h_cm.value(),
            "max_width_cm":  self._w_cm.value(),
            "max_length_cm": self._l_cm.value(),
            "co2_per_km":               self._co2.value(),
            "fuel_consumption_l100km":  self._fuel_conso.value(),
            "allowed_adr":   int(self._adr.isChecked()),
            "allowed_zfe":   int(self._zfe.isChecked()),
            # Vitesses
            "speed_highway":  self._sp_hw.value(),
            "speed_national": self._sp_nat.value(),
            "speed_urban":    self._sp_urb.value(),
            "speed_zone30":   self._sp_z30.value(),
            # Coûts
            "cost_per_km":           self._cost_km.value(),
            "cost_per_hour":         self._cost_hr.value(),
            "cost_fixed_daily":      self._cost_fix.value(),
            "cost_non_utilisation":  self._cost_idle.value(),
            # Chauffeur
            "driver_id":       driver_id,
            "driver_name":     driver_name,
            "open_start":      int(self._open_start.isChecked()),
            "open_stop":       int(self._open_stop.isChecked()),
            "reload_allowed":  int(self._reload.isChecked()),
            # Documents
            "insurance_expiry":             self._date_val(self._ins_expiry),
            "technical_inspection_expiry":  self._date_val(self._ct_expiry),
            "insurance_number":             self._ins_num.text().strip(),
            # Dispo
            "depot_id":       self._depot_combo.currentData(),
            "weekly_schedule":_json.dumps(sched),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# VEHICLES WIDGET — Page principale
# ═══════════════════════════════════════════════════════════════════════════════

class VehiclesWidget(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._threads: list = []
        self._doc_alerts: dict[int, int] = {}  # vehicle_id → days_left (min)
        self._setup_ui()
        self._ensure_extra_columns()

    def _ensure_extra_columns(self):
        """Ajoute les colonnes étendues si elles manquent (silencieux)."""
        try:
            conn = get_connection()
            for col, defn in [
                ("brand",                    "TEXT"),
                ("palettes",                 "INTEGER DEFAULT 0"),
                ("cost_non_utilisation",     "REAL DEFAULT 0"),
                ("weekly_schedule",          "TEXT"),
                ("driver_id",               "INTEGER"),
                ("fuel_consumption_l100km",  "REAL DEFAULT 0"),
            ]:
                _ensure_column(conn, "vehicles", col, defn)
            conn.close()
        except Exception:
            pass

    # ── UI construction ───────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 8)
        root.setSpacing(14)

        # ── Alert banner ───────────────────────────────────────────────
        self._banner = _ExpireBanner(self)
        root.addWidget(self._banner)

        # ── SectionHeader ──────────────────────────────────────────────
        self._header = SectionHeader(
            title="Gestion de la Flotte",
            subtitle="Véhicules, documents, disponibilités et statistiques",
            action_text="+ Ajouter véhicule",
            action_callback=self._add_vehicle,
        )
        root.addWidget(self._header)

        # ── Toolbar ────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._search = SearchBar(placeholder="Rechercher (immat, marque, type)…")
        self._search.setMaximumWidth(300)
        self._search.search_changed.connect(self._on_search)
        toolbar.addWidget(self._search)
        toolbar.addSpacing(6)

        _S = (
            f"QPushButton{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;"
            "font-size:12px;padding:4px 10px;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
        )
        for attr, txt, tip, fn in [
            ("_btn_export_csv", "Exporter CSV", "Exporter la flotte en CSV",    self._export_csv),
            ("_btn_stats",      "Stats flotte", "KPIs + graphique répartition", self._show_stats),
        ]:
            btn = QPushButton(txt)
            btn.setFixedHeight(30)
            btn.setToolTip(tip)
            btn.setStyleSheet(_S)
            btn.clicked.connect(fn)
            toolbar.addWidget(btn)
            setattr(self, attr, btn)

        # Status filter
        self._status_filter = QComboBox()
        self._status_filter.addItems(["Tous statuts", "disponible", "en_service",
                                       "maintenance", "hors_service"])
        self._status_filter.setFixedWidth(140)
        self._status_filter.setStyleSheet(_S)
        self._status_filter.currentIndexChanged.connect(self.refresh_data)
        toolbar.addWidget(self._status_filter)

        toolbar.addStretch()
        self._count_lbl = QLabel("0 véhicules")
        self._count_lbl.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        toolbar.addWidget(self._count_lbl)
        toolbar.addSpacing(4)
        _hb = QPushButton()
        _hb.setFixedSize(30, 30)
        _hb.setToolTip("Aide — Véhicules")
        _hb.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(_hb, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        _hb.clicked.connect(lambda: show_help(self, "vehicles"))
        toolbar.addWidget(_hb)
        root.addLayout(toolbar)

        # ── Table ──────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            "Immat.", "Marque", "Type", "Chauffeur",
            "Cap. kg", "CO2/km", "Statut", "Docs", "Actions",
        ])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col, w in [(2,100),(3,130),(4,75),(5,70),(6,100),(7,50),(8,120)]:
            self._table.setColumnWidth(col, w)

        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.doubleClicked.connect(self._on_dblclick)
        self._table.setStyleSheet(
            f"QTableWidget{{background:{C['bg']};color:{C['text']};"
            f"gridline-color:{C['border']};border:none;"
            "alternate-background-color:#0F2035;}"
            f"QTableWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:5px 6px;font-size:11px;font-weight:600;}}"
        )

        self._empty = EmptyState(
            title="Aucun véhicule",
            subtitle="Ajoutez votre flotte manuellement ou importez un fichier CSV.",
            action_text="+ Ajouter un véhicule",
            action_callback=self._add_vehicle,
        )
        self._stack = QStackedWidget()
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)
        root.addWidget(self._stack, 1)

        # ── Fleet KPI mini-bar ─────────────────────────────────────────
        self._kpi_bar = QFrame()
        self._kpi_bar.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:6px;padding:6px;}}"
        )
        kpi_lo = QHBoxLayout(self._kpi_bar)
        kpi_lo.setSpacing(16)
        self._kpi_labels: dict[str, QLabel] = {}
        for key, label in [("total","Total"),("dispo","Disponibles"),
                           ("service","En service"),("maint","Maintenance")]:
            lo2 = QVBoxLayout()
            lo2.setSpacing(0)
            v_lbl = QLabel("0")
            v_lbl.setStyleSheet(f"color:{C['accent']};font-size:18px;font-weight:700;background:transparent;")
            t_lbl = QLabel(label)
            t_lbl.setStyleSheet(f"color:{C['text2']};font-size:10px;background:transparent;")
            lo2.addWidget(v_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            lo2.addWidget(t_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            self._kpi_labels[key] = v_lbl
            kpi_lo.addLayout(lo2)
            if key != "maint":
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet(f"color:{C['border']};")
                kpi_lo.addWidget(sep)
        kpi_lo.addStretch()
        root.addWidget(self._kpi_bar)
        self._overlay = LoadingOverlay(self)

    # ── Data loading ──────────────────────────────────────────────────

    def retranslate_ui(self, lang: str):
        from app.i18n import tr
        if hasattr(self, "_header"):
            self._header.set_title(tr("section.vehicles", lang))
        if hasattr(self, "_btn_export_csv"):
            self._btn_export_csv.setText(tr("vehicles.btn.export_csv", lang))
            self._btn_stats.setText(tr("vehicles.btn.stats", lang))
        if hasattr(self, "_status_filter") and self._status_filter.count() > 0:
            self._status_filter.setItemText(0, tr("vehicles.filter.all", lang))

    def refresh_data(self):
        self._banner.refresh()

        # Colonne « Docs » : get_expiring_documents(365) —  hors fenêtre,  échéance
        # dans les 365 j (non expirée),  expirée (voir aussi bandeau bannière = 30 j).
        self._doc_alerts = {}
        for d in get_expiring_documents(365):
            vid = d["vehicle_id"]
            existing = self._doc_alerts.get(vid, 999)
            self._doc_alerts[vid] = min(existing, d["days_left"])

        conn = get_connection()
        where = "WHERE 1=1"
        params: list = []

        search = self._search.get_text().strip()

        if search:
            s = f"%{search}%"
            where += " AND (registration LIKE ? OR COALESCE(brand,'') LIKE ? "
            where += " OR type LIKE ? OR COALESCE(driver_name,'') LIKE ? )"
            params += [s, s, s, s]

        sf = self._status_filter.currentText()
        _STATUS_VALUES = ["", "disponible", "en_service", "maintenance", "hors_service"]
        sf_val = _STATUS_VALUES[self._status_filter.currentIndex()] if self._status_filter.currentIndex() < len(_STATUS_VALUES) else sf
        if self._status_filter.currentIndex() != 0:
            sf = sf_val
        if self._status_filter.currentIndex() != 0:
            if sf == "en_service":
                where += (
                    " AND lower(replace(trim(ifnull(status,'')),' ','_')) IN "
                    "('en_service','en_tournée','en_tournee')"
                )
            elif sf == "hors_service":
                where += (
                    " AND lower(replace(trim(ifnull(status,'')),' ','_')) = 'hors_service'"
                )
            else:
                where += " AND status= ?"
                params.append(sf)

        rows = conn.execute(
            f"SELECT * FROM vehicles {where} ORDER BY registration", params
        ).fetchall()

        # KPI counts — même regroupement que la colonne Statut (espaces / casse / libellés)
        all_rows = conn.execute("SELECT status FROM vehicles").fetchall()
        conn.close()

        total  = len(all_rows)
        dispo  = sum(
            1 for r in all_rows if _normalize_vehicle_status_bucket(r["status"]) == "disponible"
        )
        en_sv  = sum(
            1 for r in all_rows if _normalize_vehicle_status_bucket(r["status"]) == "en_service"
        )
        maint  = sum(
            1 for r in all_rows if _normalize_vehicle_status_bucket(r["status"]) == "maintenance"
        )

        self._kpi_labels["total"].setText(str(total))
        self._kpi_labels["dispo"].setText(str(dispo))
        self._kpi_labels["service"].setText(str(en_sv))
        self._kpi_labels["maint"].setText(str(maint))
        self._kpi_labels["dispo"].setStyleSheet(f"color:{C['success']};font-size:18px;font-weight:700;background:transparent;")
        self._kpi_labels["service"].setStyleSheet(f"color:{C['accent']};font-size:18px;font-weight:700;background:transparent;")
        self._kpi_labels["maint"].setStyleSheet(f"color:{C['warning']};font-size:18px;font-weight:700;background:transparent;")

        self._count_lbl.setText(f"{len(rows)} véhicule{'s' if len(rows)!=1 else ''}")
        self._fill_table(rows)
        self._stack.setCurrentIndex(0 if rows else 1)

    def _on_search(self, text: str):
        self.refresh_data()

    def _fill_table(self, rows):
        self._table.setSortingEnabled(False)
        self._table.blockSignals(True)
        self._table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            def _item(val, color=None, align=None) -> QTableWidgetItem:
                it = QTableWidgetItem(str(val) if val is not None else "")
                it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
                if color:
                    it.setForeground(QColor(color))
                if align:
                    it.setTextAlignment(align)
                return it

            # 0 Immat (store vid in UserRole)
            immat_it = _item(row["registration"] or "")
            immat_it.setData(Qt.ItemDataRole.UserRole, row["id"])
            immat_it.setFont(QFont("monospace", 10, QFont.Weight.Bold))
            self._table.setItem(r, 0, immat_it)

            # 1 Marque
            brand = ""
            try:
                brand = row["brand"] or ""
            except Exception:
                pass
            self._table.setItem(r, 1, _item(brand))

            # 2 Type
            self._table.setItem(r, 2, _item(row.get("type") or ""))

            # 3 Chauffeur
            drv = row.get("driver_name") or ""
            self._table.setItem(r, 3, _item(drv, color=C["text2"] if not drv else None))

            # 4 Cap. kg
            self._table.setItem(r, 4, _item(
                f"{float(row['capacity_kg']):.0f}",
                align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            ))

            # 5 CO2/km
            co2 = 0.0
            try:
                co2 = float(row["co2_per_km"] or 0)
            except Exception:
                pass
            self._table.setItem(r, 5, _item(
                f"{co2:.3f}",
                align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            ))

            # 6 Statut (colored)
            status = row.get("status") or "disponible"
            status_it = _item(_STATUS_LABEL.get(status, status), color=_sc(status))
            self._table.setItem(r, 6, status_it)

            # 7 Docs — seuil 365 j (distinct du bandeau 30 j) :  /  / 
            vid = row["id"]
            days = self._doc_alerts.get(vid)
            if days is None:
                doc_txt   = "✓"   # ✓ vert
                doc_color = C["success"]
            elif days < 0:
                doc_txt   = "✗"   # ✗ rouge
                doc_color = C["danger"]
            else:
                doc_txt   = "⚠"   # ⚠ orange
                doc_color = C["warning"]
            doc_it = _item(doc_txt, color=doc_color,
                           align=Qt.AlignmentFlag.AlignCenter)
            if days is not None:
                suffix = "expiré" if days < 0 else f"{days}j"
                doc_it.setToolTip(f"Document expire : {suffix}")
            self._table.setItem(r, 7, doc_it)

            # 8 Actions
            self._table.setCellWidget(r, 8, self._make_actions(row["id"]))

        self._table.blockSignals(False)
        self._table.setSortingEnabled(True)

    def _make_actions(self, vid: int) -> QWidget:
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(4, 2, 4, 2)
        lo.setSpacing(3)
        for lucide_key, tip, fn, bg, fg, hbg in [
            ("pencil", "Modifier",          lambda _, i=vid: self._edit_vehicle(i),     C["hover"], C["accent"],  C["panel"]),
            ("calendar", "Disponibilité",    lambda _, i=vid: self._show_calendar(i),    C["hover"], C["warning"], C["panel"]),
            ("copy", "Dupliquer",        lambda _, i=vid: self._duplicate_vehicle(i), C["hover"], C["text2"],  C["panel"]),
            ("trash-2", "Supprimer",        lambda _, i=vid: self._delete_vehicle(i),   C["hover"], C["danger"],  "#3A1020"),
        ]:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_action_button(btn, lucide_key, fg, bg, hbg, icon_px=16)
            btn.clicked.connect(fn)
            lo.addWidget(btn)
        return w

    # ── Context menu ──────────────────────────────────────────────────

    def _context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        item = self._table.item(row, 0)
        vid = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not vid:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};"
            "border-radius:6px;padding:4px;}}"
            f"QMenu::item{{padding:6px 18px;border-radius:4px;}}"
            f"QMenu::item:selected{{background:{C['hover']};}}"
        )
        for label, fn in [
            ("  Modifier",            lambda: self._edit_vehicle(vid)),
            ("  Calendrier dispo",   lambda: self._show_calendar(vid)),
            ("  Dupliquer",          lambda: self._duplicate_vehicle(vid)),
            (None, None),
            ("  Supprimer",         lambda: self._delete_vehicle(vid)),
        ]:
            if label is None:
                menu.addSeparator()
            else:
                act = QAction(label, self)
                act.triggered.connect(fn)
                menu.addAction(act)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_dblclick(self, idx):
        item = self._table.item(idx.row(), 0)
        if item:
            vid = item.data(Qt.ItemDataRole.UserRole)
            if vid:
                self._edit_vehicle(vid)

    # ── CRUD ──────────────────────────────────────────────────────────

    def _save_extended(self, conn, vid: int, data: dict):
        """Applique les colonnes étendues silencieusement (ignore manquantes)."""
        for col, val in [
            ("brand",                data.get("brand")),
            ("model",                data.get("model")),
            ("year",                 data.get("year")),
            ("vehicle_type",         data.get("vehicle_type")),
            ("fuel_type",            data.get("fuel_type")),
            ("photo_url",            data.get("photo_url")),
            ("palettes",             data.get("palettes")),
            ("max_height_cm",        data.get("max_height_cm")),
            ("max_width_cm",         data.get("max_width_cm")),
            ("max_length_cm",        data.get("max_length_cm")),
            ("co2_per_km",              data.get("co2_per_km")),
            ("fuel_consumption_l100km", data.get("fuel_consumption_l100km")),
            ("allowed_adr",          data.get("allowed_adr")),
            ("allowed_zfe",          data.get("allowed_zfe")),
            ("speed_highway",        data.get("speed_highway")),
            ("speed_national",       data.get("speed_national")),
            ("speed_urban",          data.get("speed_urban")),
            ("speed_zone30",         data.get("speed_zone30")),
            ("cost_per_hour",        data.get("cost_per_hour")),
            ("cost_fixed_daily",     data.get("cost_fixed_daily")),
            ("cost_non_utilisation", data.get("cost_non_utilisation")),
            ("open_start",           data.get("open_start")),
            ("open_stop",            data.get("open_stop")),
            ("reload_allowed",       data.get("reload_allowed")),
            ("insurance_expiry",     data.get("insurance_expiry")),
            ("technical_inspection_expiry", data.get("technical_inspection_expiry")),
            ("insurance_number",     data.get("insurance_number")),
            ("weekly_schedule",      data.get("weekly_schedule")),
        ]:
            if val is not None:
                try:
                    conn.execute(f"UPDATE vehicles SET {col}= ? WHERE id= ?", (val, vid))
                except Exception:
                    pass

    def _add_vehicle(self):
        dlg = _VehicleDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        conn = get_connection()
        nd, ndr = _validated_vehicle_fks(conn, data.get("depot_id"), data.get("driver_id"))
        if nd != data.get("depot_id") or ndr != data.get("driver_id"):
            QMessageBox.information(
                self, "Références",
                "Le dépôt ou le chauffeur sélectionné est invalide. "
                "La liaison a été retirée pour cet enregistrement.",
            )
        data["depot_id"], data["driver_id"] = nd, ndr
        try:
            cur = conn.execute("""
                INSERT INTO vehicles
                (registration, type, capacity_kg, capacity_m3, max_speed_kmh,
                 cost_per_km, driver_name, status, depot_id)
                VALUES (?,?,?,?,?,?,?,'disponible',?)
            """, (
                data["registration"], data["type"], data["capacity_kg"],
                data["capacity_m3"], data.get("speed_highway", 110),
                data["cost_per_km"], data["driver_name"],
                data.get("depot_id"),
            ))
            vid = cur.lastrowid
            raw_photo = data.get("photo_url") or ""
            try:
                data["photo_url"] = finalize_stored_path(raw_photo, "vehicle", vid)
            except (FileNotFoundError, ValueError, OSError) as e:
                QMessageBox.warning(
                    self, "Photo",
                    f"Impossible d'enregistrer la photo :\n{e}",
                )
                rs = (raw_photo or "").strip()
                data["photo_url"] = rs if rs.lower().startswith(("http://", "https://")) else ""
            self._save_extended(conn, vid, data)
            # Synchronisation bidirectionnelle véhicule ↔ chauffeur
            assign_driver_to_vehicle(data.get("driver_id"), vid, conn)
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            QMessageBox.warning(self, "Enregistrement", _FK_USER_MSG)
            return
        conn.close()
        log_action("VEHICLE_CREATE", f"Véhicule '{data['registration']}' créé")
        show_toast(self.window(), f"Véhicule {data['registration']} créé", "success")
        self.refresh_data()

    def _edit_vehicle(self, vid: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM vehicles WHERE id= ?", (vid,)).fetchone()
        conn.close()
        if not row:
            return
        dlg = _VehicleDialog(self, dict(row))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        conn = get_connection()
        nd, ndr = _validated_vehicle_fks(conn, data.get("depot_id"), data.get("driver_id"))
        if nd != data.get("depot_id") or ndr != data.get("driver_id"):
            QMessageBox.information(
                self, "Références",
                "Le dépôt ou le chauffeur sélectionné est invalide. "
                "La liaison a été retirée pour cet enregistrement.",
            )
        data["depot_id"], data["driver_id"] = nd, ndr
        try:
            conn.execute("""
                UPDATE vehicles SET registration= ?, type= ?, capacity_kg= ?,
                capacity_m3= ?, max_speed_kmh= ?, cost_per_km= ?,
                driver_name= ?, depot_id= ?, status= ? WHERE id=?
            """, (
                data["registration"], data["type"], data["capacity_kg"],
                data["capacity_m3"], data.get("speed_highway", 110),
                data["cost_per_km"], data["driver_name"],
                data.get("depot_id"),
                row["status"] or "disponible",
                vid,
            ))
            raw_photo = data.get("photo_url") or ""
            try:
                data["photo_url"] = finalize_stored_path(raw_photo, "vehicle", vid)
            except (FileNotFoundError, ValueError, OSError) as e:
                QMessageBox.warning(
                    self, "Photo",
                    f"Impossible d'enregistrer la photo :\n{e}",
                )
                rs = (raw_photo or "").strip()
                data["photo_url"] = rs if rs.lower().startswith(("http://", "https://")) else ""
            self._save_extended(conn, vid, data)
            # Synchronisation bidirectionnelle véhicule ↔ chauffeur
            assign_driver_to_vehicle(data.get("driver_id"), vid, conn)
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            QMessageBox.warning(self, "Enregistrement", _FK_USER_MSG)
            return
        conn.close()
        log_action("VEHICLE_UPDATE", f"Véhicule #{vid} modifié")
        show_toast(self.window(), "Véhicule mis à jour", "success")
        self.refresh_data()

    def _delete_vehicle(self, vid: int):
        conn = get_connection()
        reg = (conn.execute("SELECT registration FROM vehicles WHERE id= ?",
                            (vid,)).fetchone() or {}).get("registration", vid)
        conn.close()
        if not ConfirmDialog.ask(
            self, "Supprimer véhicule",
            f"Supprimer définitivement {reg} ", "danger"
        ):
            return
        conn = get_connection()
        conn.execute("DELETE FROM vehicles WHERE id= ?", (vid,))
        conn.commit()
        conn.close()
        log_action("VEHICLE_DELETE", f"Véhicule #{vid} ({reg}) supprimé")
        show_toast(self.window(), f"Véhicule {reg} supprimé", "success")
        self.refresh_data()

    def _duplicate_vehicle(self, vid: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM vehicles WHERE id= ?", (vid,)).fetchone()
        if not row:
            conn.close()
            return
        dup_depot = row.get("depot_id")
        try:
            if dup_depot is not None and not conn.execute(
                "SELECT 1 FROM depots WHERE id= ?", (dup_depot,)
            ).fetchone():
                dup_depot = None
        except Exception:
            dup_depot = None
        try:
            cur = conn.execute("""
                INSERT INTO vehicles
                (registration, type, capacity_kg, capacity_m3, max_speed_kmh,
                 cost_per_km, driver_name, status, depot_id)
                VALUES (?,?,?,?,?,?,?,'disponible',?)
            """, (
                f"{row['registration']}-CPY", row["type"], row["capacity_kg"],
                row["capacity_m3"], row["max_speed_kmh"], row["cost_per_km"],
                row.get("driver_name") or "", dup_depot,
            ))
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            QMessageBox.warning(self, "Duplication", _FK_USER_MSG)
            return
        for col in ("brand","model","year","vehicle_type","fuel_type","co2_per_km",
                    "allowed_adr","allowed_zfe","speed_highway","speed_national",
                    "speed_urban","speed_zone30","cost_per_hour","cost_fixed_daily",
                    "open_start","open_stop","reload_allowed","palettes"):
            try:
                val = row[col]
                if val is not None:
                    conn.execute(f"UPDATE vehicles SET {col}= ? WHERE id= ?", (val, new_id))
            except Exception:
                pass
        try:
            old_ph = row["photo_url"] if "photo_url" in row.keys() else None
        except Exception:
            old_ph = None
        if old_ph:
            abs_p = resolve_stored_photo(old_ph)
            if abs_p:
                try:
                    new_rel = finalize_stored_path(abs_p, "vehicle", new_id)
                    if new_rel:
                        conn.execute(
                            "UPDATE vehicles SET photo_url= ? WHERE id= ?",
                            (new_rel, new_id),
                        )
                except (FileNotFoundError, ValueError, OSError) as e:
                    QMessageBox.warning(
                        self, "Photo",
                        f"Duplication de la photo impossible :\n{e}",
                    )
        conn.commit()
        conn.close()
        log_action("VEHICLE_DUPLICATE", f"Véhicule #{vid} dupliqué")
        show_toast(self.window(), "Véhicule dupliqué", "success")
        self.refresh_data()

    # ── Dialogs ───────────────────────────────────────────────────────

    def _show_calendar(self, vid: int):
        conn = get_connection()
        row = conn.execute("SELECT registration FROM vehicles WHERE id= ?", (vid,)).fetchone()
        conn.close()
        reg = row["registration"] if row else f"V{vid}"
        _CalendarDialog(vid, reg, self).exec()

    def _show_stats(self):
        _FleetStatsDialog(self).exec()

    # ── Export ────────────────────────────────────────────────────────

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter flotte CSV", "vehicules.csv", "CSV (*.csv)")
        if not path:
            return
        conn = get_connection()
        rows = conn.execute("SELECT * FROM vehicles ORDER BY registration").fetchall()
        conn.close()
        COLS = ["id","registration","brand","model","year","type","fuel_type",
                "capacity_kg","capacity_m3","max_speed_kmh","co2_per_km",
                "cost_per_km","cost_per_hour","driver_name","status","depot_id"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(COLS)
            for row in rows:
                writer.writerow([row.get(c) for c in COLS])
        log_action("VEHICLE_EXPORT_CSV", f"{len(rows)} véhicules → {path}")
        show_toast(self.window(), f"{len(rows)} véhicules exportés (CSV)", "success")
