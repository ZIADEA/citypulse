"""
drivers_widget.py — Gestion des chauffeurs CityPulse Logistics v1.0
====================================================================
QTabWidget 4 onglets :
   Chauffeurs   — table + fiche 5 onglets + bandeau alertes permis
   Indisponibilités — calendrier mensuel par chauffeur + suggestion remplacement
   Équipes      — CRUD équipes + gestion membres + manager
   Performance  — filtres + tableau + graphique barres Matplotlib + export CSV
"""

# ── stdlib ────────────────────────────────────────────────────────────────────
import calendar
import csv
import logging
import os
from datetime import date, timedelta, datetime

# ── PyQt6 ────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QDateEdit, QTextEdit, QCheckBox, QMessageBox, QFrame,
    QTabWidget, QAbstractItemView, QMenu, QFileDialog,
    QListWidget, QListWidgetItem, QSizePolicy, QScrollArea,
    QGroupBox, QToolButton, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate, QSize
from PyQt6.QtGui import QColor, QFont, QPixmap, QAction, QPainter, QPen, QBrush

# ── Local ─────────────────────────────────────────────────────────────────────
from ..database.db_manager import (
    get_connection, log_action,
    assign_driver_to_vehicle, get_driver_vehicle_info,
)
from ..services.django_sync_service import get_django_service
from ..utils.photo_storage import (
    finalize_stored_path,
    is_allowed_image_filename,
    resolve_stored_photo,
)
from .toast import show_toast
from .help_dialog import show_help
from .components import SectionHeader, SearchBar, StatusBadge, ConfirmDialog
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

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":    "#0D1B2A", "panel":  "#112240", "input":  "#1A2E4A",
    "accent":"#00D4FF", "success":"#00FF88", "warning":"#FFB800",
    "danger":"#FF4757", "text":   "#E8F4FD", "text2":  "#8899AA",
    "border":"#1E3A5F", "hover":  "#1A3A5C",
}
_GRP_QSS = (
    f"QGroupBox{{border:1px solid {C['border']};border-radius:6px;"
    "margin-top:16px;padding:8px 8px 8px 8px;}}"
    f"QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;"
    f"top:-2px;left:8px;padding:0 4px;color:{C['accent']};"
    f"background:{C['bg']};font-weight:700;font-size:11px;}}"
)

_LICENSE_CATS   = ["B", "C", "C1", "CE", "D", "D1", "DE"]
_CONTRACT_TYPES = ["CDI", "CDD", "Intérim", "Auto-entrepreneur", "Stage"]
_QUALIFS_FLAGS  = ["ADR", "CACES", "FCO", "FIMO", "HAZMAT", "Permis_poids_lourd"]

_BTN_S = (
    "QPushButton{background:%s;color:%s;border:none;"
    "border-radius:4px;font-size:15px;padding:2px 4px;}"
    "QPushButton:hover{background:%s;}"
)
_INP_STYLE = (
    f"QLineEdit,QTextEdit,QSpinBox,QDoubleSpinBox,QDateEdit,QComboBox{{"
    f"background:{C['input']};color:{C['text']};border:1px solid {C['border']};"
    "border-radius:5px;padding:4px 8px;}"
    f"QComboBox::drop-down{{border:none;}}"
    f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
    f"border:1px solid {C['border']};}}"
)
_GRP_STYLE = (
    f"QGroupBox{{color:{C['text2']};border:1px solid {C['border']};"
    "border-radius:5px;margin-top:10px;padding-top:8px;}"
    f"QGroupBox::title{{subcontrol-origin:margin;left:8px;padding:0 4px;"
    f"color:{C['accent']};font-weight:700;}}"
)


def _days_left(expiry_str: str) -> int:
    if not expiry_str:
        return 9999
    try:
        exp = datetime.strptime(expiry_str[:10], "%Y-%m-%d").date()
        return (exp - date.today()).days
    except Exception:
        return 9999


def _ensure_driver_cols():
    """Add optional columns idempotently."""
    try:
        conn = get_connection()
        for col, defn in [
            ("open_start", "INTEGER DEFAULT 0"),
            ("open_stop",  "INTEGER DEFAULT 0"),
            ("photo_path", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE drivers ADD COLUMN {col} {defn}")
                conn.commit()
            except Exception:
                pass
        conn.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# EXPIRE BANNER
# ═══════════════════════════════════════════════════════════════════════════════

class _ExpireLicenseBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("expireBanner")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 10, 6)
        self._layout.setSpacing(3)
        self.setVisible(False)

    def refresh(self):
        for i in reversed(range(self._layout.count())):
            w = self._layout.itemAt(i).widget()
            if w: w.deleteLater()

        alerts = []
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT id, first_name, last_name, license_expiry"
                " FROM drivers WHERE archived=0 AND license_expiry IS NOT NULL"
            ).fetchall()
            conn.close()
            for row in rows:
                d = _days_left(row["license_expiry"])
                if d <= 30:
                    alerts.append((row["first_name"], row["last_name"], row["license_expiry"], d))
        except Exception:
            pass

        if not alerts:
            self.setVisible(False)
            return

        self.setStyleSheet(
            f"QFrame#expireBanner{{background:rgba(255,184,0,26);"
            f"border:1px solid {C['warning']};border-radius:6px;}}"
        )
        for fn, ln, exp, d in alerts:
            color = C["danger"] if d <= 0 else C["warning"]
            status = "EXPIRÉ" if d <= 0 else f"expire dans {d}j"
            lbl = QLabel(f"  {fn} {ln} — permis {status} ({exp})")
            lbl.setStyleSheet(
                f"color:{color};font-size:12px;font-weight:600;background:transparent;"
            )
            self._layout.addWidget(lbl)
        self.setVisible(True)


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVER DIALOG — 5 onglets
# ═══════════════════════════════════════════════════════════════════════════════

class _DriverDialog(QDialog):

    def __init__(self, parent=None, driver: dict = None):
        super().__init__(parent)
        self.driver = driver or {}
        self.setWindowTitle("Modifier chauffeur" if driver else "Nouveau chauffeur")
        self.setMinimumSize(640, 540)
        self.resize(700, 560)
        self.setModal(True)
        _pp = self.driver.get("photo_path") or self.driver.get("photo_url") or ""
        self._photo_path = _pp if isinstance(_pp, str) else ""
        self.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            f"QTabWidget::pane{{background:{C['panel']};border:1px solid {C['border']};border-radius:6px;}}"
            f"QTabBar::tab{{background:{C['input']};color:{C['text2']};padding:8px 14px;"
            "border-top-left-radius:4px;border-top-right-radius:4px;margin-right:2px;font-size:12px;}"
            f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
            f"QTabBar::tab:hover{{background:{C['hover']};}}"
            + _INP_STYLE + _GRP_STYLE +
            f"QLabel{{background:transparent;color:{C['text']};}}"
            f"QCheckBox{{color:{C['text']};background:transparent;}}"
        )
        self._setup_ui()

    def _lbl(self, t):
        l = QLabel(t)
        l.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        return l

    def _check_veh_conflict(self):
        """Avertit si le véhicule sélectionné est déjà conduit par un autre chauffeur."""
        if not hasattr(self, "_veh_conflict_lbl"):
            return
        vid = self._veh_cb.currentData()
        if not vid:
            self._veh_conflict_lbl.setText("")
            return
        try:
            info = get_driver_vehicle_info(vehicle_id=vid)
            existing_did = (info.get("driver") or {}).get("id")
            current_did  = self.driver.get("id")
            if existing_did and existing_did != current_did:
                fn = (info.get("driver") or {}).get("first_name", "")
                ln = (info.get("driver") or {}).get("last_name", "")
                self._veh_conflict_lbl.setText(
                    f"Attention : ce véhicule est actuellement assigné à {fn} {ln}. "
                    f"En enregistrant, il sera automatiquement désassigné de ce chauffeur."
                )
            else:
                self._veh_conflict_lbl.setText("")
        except Exception:
            self._veh_conflict_lbl.setText("")

    def _le(self, v="", ph=""):
        w = QLineEdit(str(v) if v else "")
        w.setPlaceholderText(ph)
        return w

    def _spin(self, v, mn, mx, step=1, dec=0, suf=""):
        if dec:
            w = QDoubleSpinBox()
            w.setDecimals(dec)
            fmn, fmx = float(mn), float(mx)
            w.setRange(fmn, fmx)
            w.setSingleStep(float(step))
            fv = float(v or 0)
            w.setValue(min(fmx, max(fmn, fv)))
        else:
            w = QSpinBox()
            imn, imx = int(mn), int(mx)
            w.setRange(imn, imx)
            istep = int(round(float(step)))
            w.setSingleStep(istep if istep > 0 else 1)
            iv = int(round(float(v or 0)))
            w.setValue(min(imx, max(imn, iv)))
        if suf:
            w.setSuffix(suf)
        return w

    def _setup_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 12)
        lo.setSpacing(12)
        tabs = QTabWidget()
        tabs.addTab(self._tab_personnel(),   "  Personnel  ")
        tabs.addTab(self._tab_permis(),      "  Permis & Qualifs  ")
        tabs.addTab(self._tab_horaires(),    "  Horaires  ")
        tabs.addTab(self._tab_rse(),         "  RSE  ")
        tabs.addTab(self._tab_affectation(), "  Affectation  ")
        lo.addWidget(tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn")
        cancel.setFixedHeight(34); cancel.clicked.connect(self.reject)
        save = QPushButton("Sauvegarder"); save.setObjectName("primaryBtn")
        save.setFixedHeight(34); save.setMinimumWidth(120)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(cancel); btn_row.addWidget(save)
        lo.addLayout(btn_row)

    # ── Tab 0 : Personnel ─────────────────────────────────────────────
    def _tab_personnel(self) -> QWidget:
        w = QWidget(); root = QHBoxLayout(w)
        root.setContentsMargins(16, 16, 16, 8); root.setSpacing(16)
        d = self.driver

        # Photo area
        photo_col = QVBoxLayout()
        self._photo_lbl = QLabel()
        self._photo_lbl.setFixedSize(88, 88)
        self._photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_lbl.setStyleSheet(
            f"background:{C['input']};border:1px solid {C['border']};"
            "border-radius:44px;"
        )
        self._photo_lbl.setText("")
        self._photo_lbl.setStyleSheet(
            f"background:{C['input']};border:2px solid {C['border']};"
            "border-radius:44px;font-size:32px;"
        )
        self._refresh_driver_photo_thumb()
        photo_btn = QPushButton("Choisir photo")
        photo_btn.setObjectName("secondaryBtn")
        photo_btn.setFixedHeight(28)
        photo_btn.clicked.connect(self._pick_photo)
        photo_col.addWidget(self._photo_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        photo_col.addWidget(photo_btn)
        photo_col.addStretch()
        root.addLayout(photo_col)

        # Form
        fl = QFormLayout(); fl.setSpacing(10)
        self._first  = self._le(d.get("first_name", ""), "Prénom *")
        self._last   = self._le(d.get("last_name", ""),  "Nom *")
        self._phone  = self._le(d.get("phone") or "",    "+212 6XX XXX XXX")
        self._email  = self._le(d.get("email") or "",    "prenom.nom@example.com")
        self._company= self._le(d.get("company_name") or "", "Entreprise (sous-traitant)")
        self._notes  = QTextEdit()
        self._notes.setMaximumHeight(56)
        self._notes.setPlaceholderText("Notes internes…")
        self._notes.setText(d.get("notes") or "")
        self._notes.setStyleSheet(
            f"QTextEdit{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px;}}"
        )
        fl.addRow(self._lbl("Prénom *"),   self._first)
        fl.addRow(self._lbl("Nom *"),      self._last)
        fl.addRow(self._lbl("Téléphone"),  self._phone)
        fl.addRow(self._lbl("Email"),      self._email)
        fl.addRow(self._lbl("Entreprise"), self._company)
        fl.addRow(self._lbl("Notes"),      self._notes)
        root.addLayout(fl, 1)
        return w

    def _refresh_driver_photo_thumb(self):
        abs_p = resolve_stored_photo(self._photo_path)
        if abs_p:
            pm = QPixmap(abs_p).scaled(
                88, 88, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._photo_lbl.setPixmap(pm)
            self._photo_lbl.setText("")
        else:
            self._photo_lbl.clear()
            self._photo_lbl.setText("")

    def _pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une photo", "",
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
        self._photo_path = path
        self._refresh_driver_photo_thumb()

    # ── Tab 1 : Permis & Qualifs ──────────────────────────────────────
    def _tab_permis(self) -> QWidget:
        w = QWidget(); fl = QFormLayout(w)
        fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
        d = self.driver

        self._lic_num  = self._le(d.get("license_number") or "", "N° permis")
        self._lic_cat  = QComboBox()
        for c in _LICENSE_CATS: self._lic_cat.addItem(c)
        cat = d.get("license_category") or "C"
        idx = self._lic_cat.findText(cat)
        if idx >= 0: self._lic_cat.setCurrentIndex(idx)

        self._lic_exp = QDateEdit(); self._lic_exp.setCalendarPopup(True)
        self._lic_exp.setDisplayFormat("dd/MM/yyyy")
        exp = d.get("license_expiry") or ""
        try:
            self._lic_exp.setDate(QDate.fromString(exp[:10], "yyyy-MM-dd"))
        except Exception:
            self._lic_exp.setDate(QDate.currentDate().addYears(5))

        # Expiry alert
        self._exp_alert = QLabel("")
        self._exp_alert.setStyleSheet("background:transparent;font-size:11px;")
        self._lic_exp.dateChanged.connect(self._update_exp_alert)
        self._update_exp_alert()

        # Qualifications checkboxes
        saved_quals = set((d.get("qualifications") or "").split(","))
        quals_grp = QGroupBox("Qualifications")
        quals_grp.setStyleSheet(_GRP_QSS)
        quals_lo = QHBoxLayout(quals_grp)
        quals_lo.setContentsMargins(8, 4, 8, 4); quals_lo.setSpacing(10)
        self._qual_cbs: dict[str, QCheckBox] = {}
        for q in _QUALIFS_FLAGS:
            cb = QCheckBox(q); cb.setChecked(q in saved_quals)
            quals_lo.addWidget(cb); self._qual_cbs[q] = cb

        self._contract = QComboBox()
        for ct in _CONTRACT_TYPES: self._contract.addItem(ct)
        ct_cur = d.get("contract_type") or "CDI"
        idx = self._contract.findText(ct_cur)
        if idx >= 0: self._contract.setCurrentIndex(idx)

        fl.addRow(self._lbl("N° permis"),      self._lic_num)
        fl.addRow(self._lbl("Catégorie"),       self._lic_cat)
        fl.addRow(self._lbl("Expiration"),      self._lic_exp)
        fl.addRow("",                           self._exp_alert)
        fl.addRow(self._lbl("Qualifications"),  quals_grp)
        fl.addRow(self._lbl("Type de contrat"), self._contract)
        return w

    def _update_exp_alert(self):
        d = self._lic_exp.date().toString("yyyy-MM-dd")
        days = _days_left(d)
        if days <= 0:
            self._exp_alert.setText(" Permis expiré !")
            self._exp_alert.setStyleSheet(f"color:{C['danger']};background:transparent;font-size:11px;font-weight:700;")
        elif days <= 30:
            self._exp_alert.setText(f" Expire dans {days} jours")
            self._exp_alert.setStyleSheet(f"color:{C['warning']};background:transparent;font-size:11px;font-weight:700;")
        else:
            self._exp_alert.setText(f" Valide ({days}j)")
            self._exp_alert.setStyleSheet(f"color:{C['success']};background:transparent;font-size:11px;")

    # ── Tab 2 : Horaires ──────────────────────────────────────────────
    def _tab_horaires(self) -> QWidget:
        w = QWidget(); fl = QFormLayout(w)
        fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
        d = self.driver

        self._ws  = self._le(d.get("work_start_time")  or "07:00", "HH:MM"); self._ws.setFixedWidth(70)
        self._we  = self._le(d.get("work_end_time")    or "17:00", "HH:MM"); self._we.setFixedWidth(70)
        self._lt  = self._le(d.get("lunch_time")       or "12:00", "HH:MM"); self._lt.setFixedWidth(70)
        self._ld  = self._spin(d.get("lunch_duration_minutes", 60), 0, 120, 5, suf=" min")
        self._mh  = self._spin(d.get("max_daily_hours", 10.0), 0, 15, 0.5, dec=1, suf=" h")

        wh_row = QHBoxLayout()
        wh_row.addWidget(self._ws); wh_row.addWidget(QLabel("→")); wh_row.addWidget(self._we); wh_row.addStretch()
        lunch_row = QHBoxLayout()
        lunch_row.addWidget(self._lt); lunch_row.addWidget(QLabel("pause")); lunch_row.addWidget(self._ld); lunch_row.addStretch()

        ot1_grp = QGroupBox("Heures supp. niveau 1")
        ot1_grp.setStyleSheet(_GRP_QSS)
        ot1_lo = QHBoxLayout(ot1_grp); ot1_lo.setContentsMargins(8, 12, 8, 4); ot1_lo.setSpacing(8)
        self._ot1h = self._spin(d.get("overtime_level1_hours", 1.0), 0, 24, 0.5, dec=1, suf=" h")
        self._ot1r = self._spin(d.get("overtime_level1_rate", 1.25), 1.0, 3.0, 0.05, dec=2, suf=" ×")
        for lbl, sp in [("Durée", self._ot1h), ("Taux", self._ot1r)]:
            ot1_lo.addWidget(QLabel(lbl)); ot1_lo.addWidget(sp)
        ot1_lo.addStretch()

        ot2_grp = QGroupBox("Heures supp. niveau 2")
        ot2_grp.setStyleSheet(_GRP_QSS)
        ot2_lo = QHBoxLayout(ot2_grp); ot2_lo.setContentsMargins(8, 12, 8, 4); ot2_lo.setSpacing(8)
        self._ot2h = self._spin(d.get("overtime_level2_hours", 2.0), 0, 24, 0.5, dec=1, suf=" h")
        self._ot2r = self._spin(d.get("overtime_level2_rate", 1.5), 1.0, 3.0, 0.05, dec=2, suf=" ×")
        for lbl, sp in [("Durée", self._ot2h), ("Taux", self._ot2r)]:
            ot2_lo.addWidget(QLabel(lbl)); ot2_lo.addWidget(sp)
        ot2_lo.addStretch()

        fl.addRow(self._lbl("Plage de travail"), wh_row)
        fl.addRow(self._lbl("Pause déjeuner"),   lunch_row)
        fl.addRow(self._lbl("Max heures / jour"),self._mh)
        fl.addRow(self._lbl(""),                 ot1_grp)
        fl.addRow(self._lbl(""),                 ot2_grp)
        return w

    # ── Tab 3 : RSE ───────────────────────────────────────────────────
    def _tab_rse(self) -> QWidget:
        w = QWidget(); fl = QFormLayout(w)
        fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
        d = self.driver

        self._rse1 = self._spin(d.get("max_drive_before_break_min", 270), 0, 480, 15, suf=" min")
        self._rse2 = self._spin(d.get("min_break_minutes", 45),           0, 120, 5,  suf=" min")
        self._rse3 = self._spin(d.get("min_daily_rest_minutes", 660),     0, 720, 15, suf=" min")

        rse_note = QLabel(
            "Valeurs légales CE 561/2006 :\n"
            "• Conduite max avant pause : 270 min (4h30)\n"
            "• Pause minimum : 45 min\n"
            "• Repos journalier : 660 min (11h)"
        )
        rse_note.setStyleSheet(
            f"color:{C['text2']};font-size:11px;background:{C['panel']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:8px;"
        )
        rse_note.setWordWrap(True)

        fl.addRow(self._lbl("Max conduite avant pause"), self._rse1)
        fl.addRow(self._lbl("Pause minimum"),            self._rse2)
        fl.addRow(self._lbl("Repos journalier minimum"), self._rse3)
        fl.addRow("", rse_note)
        return w

    # ── Tab 4 : Affectation ───────────────────────────────────────────
    def _tab_affectation(self) -> QWidget:
        w = QWidget(); fl = QFormLayout(w)
        fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
        d = self.driver

        conn = get_connection()
        depots   = conn.execute("SELECT id, name FROM depots ORDER BY name").fetchall()
        current_vehicle_id = d.get("vehicle_id")
        vehicles = conn.execute(
            """
            SELECT id, registration, COALESCE(status, 'disponible') AS status
            FROM vehicles
            ORDER BY
                CASE
                    WHEN LOWER(REPLACE(TRIM(COALESCE(status, '')), ' ', '_')) = 'disponible' THEN 0
                    ELSE 1
                END,
                registration
            """
        ).fetchall()
        conn.close()

        _STATUS_FR = {
            "en_service":  "en service",
            "en tournée":  "en tournée",
            "maintenance":  "maintenance",
            "hors_service": "hors service",
        }

        self._depot_cb = QComboBox(); self._depot_cb.setEditable(False)
        self._depot_cb.addItem("— Non défini", None)
        for dp in depots: self._depot_cb.addItem(dp["name"], dp["id"])
        if d.get("home_depot_id"):
            idx = self._depot_cb.findData(d["home_depot_id"])
            if idx >= 0: self._depot_cb.setCurrentIndex(idx)

        self._veh_cb = QComboBox(); self._veh_cb.setEditable(True)
        self._veh_cb.addItem("— Non assigné", None)
        for v in vehicles:
            status_norm = (v["status"] or "").strip().lower().replace(" ", "_")
            label = v["registration"]
            if status_norm != "disponible":
                status_fr = _STATUS_FR.get(status_norm, status_norm)
                label = f"{label} ({status_fr})"
            self._veh_cb.addItem(label, v["id"])
        if current_vehicle_id:
            idx = self._veh_cb.findData(current_vehicle_id)
            if idx >= 0: self._veh_cb.setCurrentIndex(idx)

        self._zone = self._le(d.get("zone_assignment") or "", "ex: Zone Nord")
        self._open_start = QCheckBox("Ouvre le départ (open_start)")
        self._open_start.setChecked(bool(d.get("open_start", 0)))
        self._open_stop  = QCheckBox("Ferme l'arrivée (open_stop)")
        self._open_stop.setChecked(bool(d.get("open_stop", 0)))

        # Stats
        did = d.get("id")
        stats_grp = QGroupBox("Statistiques")
        stats_grp.setStyleSheet(_GRP_QSS)
        stats_lo = QFormLayout(stats_grp); stats_lo.setSpacing(6)
        if did:
            try:
                conn = get_connection()
                nb_routes = (conn.execute(
                    "SELECT COUNT(*) FROM routes WHERE driver_id= ?", (did,)
                ).fetchone() or [0])[0]
                total_km = (conn.execute(
                    "SELECT COALESCE(SUM(total_km),0) FROM routes WHERE driver_id= ?", (did,)
                ).fetchone() or [0.0])[0]
                avg_delay = (conn.execute(
                    "SELECT COALESCE(AVG(delay_min),0) FROM arrets WHERE 1"
                ).fetchone() or [0.0])[0]
                conn.close()
                for lbl, val in [
                    ("Tournées effectuées", str(nb_routes)),
                    ("Km total", f"{float(total_km):.0f} km"),
                    ("Retard moyen", f"{float(avg_delay):.1f} min"),
                ]:
                    stats_lo.addRow(
                        QLabel(lbl),
                        _bold_lbl(val)
                    )
            except Exception:
                stats_lo.addRow(QLabel("Stats non disponibles."), QLabel(""))
        else:
            stats_lo.addRow(QLabel("Disponible après sauvegarde."), QLabel(""))

        # Avertissement conflit véhicule
        self._veh_conflict_lbl = QLabel("")
        self._veh_conflict_lbl.setWordWrap(True)
        self._veh_conflict_lbl.setStyleSheet(
            "color:#FFB800;font-size:11px;border:none;background:transparent;"
        )
        self._veh_cb.currentIndexChanged.connect(self._check_veh_conflict)
        self._check_veh_conflict()

        fl.addRow(self._lbl("Dépôt d'attache"), self._depot_cb)
        fl.addRow(self._lbl("Véhicule"),         self._veh_cb)
        fl.addRow("",                            self._veh_conflict_lbl)
        fl.addRow(self._lbl("Zone"),             self._zone)
        fl.addRow("", self._open_start)
        fl.addRow("", self._open_stop)
        fl.addRow(self._lbl(""), stats_grp)
        return w

    # ── Save ──────────────────────────────────────────────────────────
    def _on_save(self):
        if not self._first.text().strip() or not self._last.text().strip():
            QMessageBox.warning(self, "Validation", "Prénom et Nom obligatoires.")
            return
        self.accept()

    def get_data(self) -> dict:
        quals = ",".join(q for q, cb in self._qual_cbs.items() if cb.isChecked())
        return {
            "first_name":               self._first.text().strip(),
            "last_name":                self._last.text().strip(),
            "phone":                    self._phone.text().strip(),
            "email":                    self._email.text().strip(),
            "company_name":             self._company.text().strip(),
            "notes":                    self._notes.toPlainText().strip(),
            "photo_path":               self._photo_path,
            "license_number":           self._lic_num.text().strip(),
            "license_category":         self._lic_cat.currentText(),
            "license_expiry":           self._lic_exp.date().toString("yyyy-MM-dd"),
            "qualifications":           quals,
            "contract_type":            self._contract.currentText(),
            "work_start_time":          self._ws.text().strip() or "07:00",
            "work_end_time":            self._we.text().strip() or "17:00",
            "lunch_time":               self._lt.text().strip() or "12:00",
            "lunch_duration_minutes":   int(self._ld.value()),
            "max_daily_hours":          float(self._mh.value()),
            "overtime_level1_hours":    float(self._ot1h.value()),
            "overtime_level1_rate":     float(self._ot1r.value()),
            "overtime_level2_hours":    float(self._ot2h.value()),
            "overtime_level2_rate":     float(self._ot2r.value()),
            "max_drive_before_break_min": int(self._rse1.value()),
            "min_break_minutes":        int(self._rse2.value()),
            "min_daily_rest_minutes":   int(self._rse3.value()),
            "home_depot_id":            self._depot_cb.currentData(),
            "vehicle_id":               self._veh_cb.currentData(),
            "zone_assignment":          self._zone.text().strip(),
            "open_start":               int(self._open_start.isChecked()),
            "open_stop":                int(self._open_stop.isChecked()),
        }


def _bold_lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;background:transparent;")
    return l


# ═══════════════════════════════════════════════════════════════════════════════
# UNAVAILABILITY DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class _UnavailDialog(QDialog):

    def __init__(self, driver_id: int, date_str: str,
                 existing: dict = None, parent=None):
        super().__init__(parent)
        self.driver_id = driver_id
        self.date_str  = date_str
        self.existing  = existing
        self.setWindowTitle("Indisponibilité")
        self.resize(380, 220)
        self.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            + _INP_STYLE
            + f"QLabel{{background:transparent;color:{C['text']};}}"
        )
        lo = QVBoxLayout(self); fl = QFormLayout(); fl.setSpacing(8); fl.setContentsMargins(14,14,14,8)

        self._date_lbl = QLabel(date_str)
        self._date_lbl.setStyleSheet(f"color:{C['accent']};font-size:14px;font-weight:700;background:transparent;")

        self._reason = QLineEdit(existing.get("reason") or "" if existing else "")
        self._reason.setPlaceholderText("Maladie, Congé, Formation…")
        self._notes  = QTextEdit()
        self._notes.setMaximumHeight(60)
        self._notes.setPlaceholderText("Notes complémentaires")
        self._notes.setText(existing.get("notes") or "" if existing else "")
        self._notes.setStyleSheet(
            f"QTextEdit{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px;}}"
        )

        fl.addRow(QLabel("Date :"),   self._date_lbl)
        fl.addRow(QLabel("Raison :"), self._reason)
        fl.addRow(QLabel("Notes :"),  self._notes)
        lo.addLayout(fl); lo.addStretch()

        btn_row = QHBoxLayout(); btn_row.addStretch()
        if existing:
            del_btn = QPushButton("Supprimer"); del_btn.setObjectName("secondaryBtn")
            del_btn.setFixedHeight(32); del_btn.clicked.connect(self._do_delete)
            btn_row.addWidget(del_btn)
        cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn")
        cancel.setFixedHeight(32); cancel.clicked.connect(self.reject)
        save = QPushButton("Sauvegarder"); save.setObjectName("primaryBtn")
        save.setFixedHeight(32); save.clicked.connect(self.accept)
        btn_row.addWidget(cancel); btn_row.addWidget(save)
        lo.addLayout(btn_row)

    def _do_delete(self):
        if self.existing and self.existing.get("id"):
            conn = get_connection()
            conn.execute("DELETE FROM driver_unavailabilities WHERE id= ?", (self.existing["id"],))
            conn.commit(); conn.close()
            log_action("DRIVER_UNAVAIL_DEL", f"Indispo chauffeur #{self.driver_id} {self.date_str} supprimée")
        self.done(2)

    def get_data(self) -> dict:
        return {
            "driver_id": self.driver_id,
            "date":      self.date_str,
            "reason":    self._reason.text().strip(),
            "notes":     self._notes.toPlainText().strip(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CALENDAR WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

class _CalendarGrid(QWidget):
    """Monthly calendar grid rendering unavailabilities for a driver."""

    date_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._driver_id: int = 0
        self._year  = date.today().year
        self._month = date.today().month
        self._unavail: set = set()
        self._has_route: set = set()
        self._setup_ui()

    def _setup_ui(self):
        lo = QVBoxLayout(self); lo.setSpacing(4)

        # Month nav
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("<"); self._prev_btn.setFixedSize(28, 28)
        self._prev_btn.setToolTip("Mois précédent")
        self._prev_btn.setStyleSheet(_BTN_S % (C["hover"], C["accent"], C["panel"]))
        self._prev_btn.clicked.connect(self._prev_month)
        self._next_btn = QPushButton(">"); self._next_btn.setFixedSize(28, 28)
        self._next_btn.setToolTip("Mois suivant")
        self._next_btn.setStyleSheet(_BTN_S % (C["hover"], C["accent"], C["panel"]))
        self._next_btn.clicked.connect(self._next_month)
        self._month_lbl = QLabel(""); self._month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._month_lbl.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;background:transparent;")
        nav.addWidget(self._prev_btn); nav.addWidget(self._month_lbl, 1); nav.addWidget(self._next_btn)
        lo.addLayout(nav)

        # Legend
        leg = QHBoxLayout()
        for color, label in [
            (C["danger"], "Indisponible"),
            (C["warning"], "Route planifiée"),
        ]:
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background:{color};border-radius:5px;")
            leg.addWidget(dot); leg.addWidget(QLabel(label))
            leg.addSpacing(10)
        leg.addStretch()
        lo.addLayout(leg)

        # Grid
        self._table = QTableWidget(6, 7)
        self._table.setHorizontalHeaderLabels(["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setFixedHeight(210)
        hdr = self._table.horizontalHeader()
        for c in range(7):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setDefaultSectionSize(30)
        self._table.setStyleSheet(
            f"QTableWidget{{background:{C['bg']};color:{C['text']};"
            f"gridline-color:{C['border']};border:1px solid {C['border']};}}"
            f"QTableWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:2px;font-size:11px;font-weight:600;}}"
        )
        self._table.cellClicked.connect(self._on_cell_click)
        lo.addWidget(self._table, 1)
        self._render()

    def set_driver(self, driver_id: int):
        self._driver_id = driver_id
        self._load_data()

    def _load_data(self):
        self._unavail = set(); self._has_route = set()
        if not self._driver_id: self._render(); return
        try:
            conn = get_connection()
            ym = f"{self._year:04d}-{self._month:02d}"
            rows = conn.execute(
                "SELECT date FROM driver_unavailabilities"
                " WHERE driver_id= ? AND date LIKE ? ",
                (self._driver_id, f"{ym}%"),
            ).fetchall()
            self._unavail = {r["date"] for r in rows}
            try:
                r2 = conn.execute(
                    "SELECT planned_date FROM routes WHERE driver_id= ? AND planned_date LIKE ? ",
                    (self._driver_id, f"{ym}%"),
                ).fetchall()
                self._has_route = {r["planned_date"] for r in r2}
            except Exception:
                pass
            conn.close()
        except Exception:
            pass
        self._render()

    def _render(self):
        import calendar as _cal
        self._month_lbl.setText(
            f"{_cal.month_name[self._month].capitalize()} {self._year}"
        )
        self._table.clearContents()
        first_weekday, nb_days = _cal.monthrange(self._year, self._month)
        cell = 0
        for row in range(6):
            for col in range(7):
                day_num = cell - first_weekday + 1
                if 1 <= day_num <= nb_days:
                    ds = f"{self._year:04d}-{self._month:02d}-{day_num:02d}"
                    it = QTableWidgetItem(str(day_num))
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    it.setData(Qt.ItemDataRole.UserRole, ds)
                    if ds in self._unavail:
                        it.setBackground(QColor(C["danger"]))
                        it.setForeground(QColor("#ffffff"))
                        it.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                    elif ds in self._has_route:
                        it.setBackground(QColor(C["warning"]))
                        it.setForeground(QColor(C["bg"]))
                    elif col >= 5:
                        it.setForeground(QColor(C["text2"]))
                    else:
                        it.setForeground(QColor(C["text"]))
                    self._table.setItem(row, col, it)
                cell += 1

    def _prev_month(self):
        self._month -= 1
        if self._month < 1: self._month = 12; self._year -= 1
        self._load_data()

    def _next_month(self):
        self._month += 1
        if self._month > 12: self._month = 1; self._year += 1
        self._load_data()

    def _on_cell_click(self, row, col):
        it = self._table.item(row, col)
        if it and it.data(Qt.ItemDataRole.UserRole):
            self.date_clicked.emit(it.data(Qt.ItemDataRole.UserRole))


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVERS WIDGET — Page principale (4 onglets)
# ═══════════════════════════════════════════════════════════════════════════════

class DriversWidget(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        _ensure_driver_cols()
        self._setup_ui()

    # ── Setup ─────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane{{background:{C['bg']};border:none;}}"
            f"QTabBar::tab{{background:{C['panel']};color:{C['text2']};padding:10px 18px;"
            "border-top-left-radius:6px;border-top-right-radius:6px;margin-right:2px;font-size:13px;font-weight:500;}"
            f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
            f"QTabBar::tab:hover{{background:{C['hover']};color:{C['text']};}}"
        )
        self._tab_drivers  = self._build_tab_drivers()
        self._tab_unavail  = self._build_tab_unavail()
        self._tab_teams    = self._build_tab_teams()
        self._tab_perf     = self._build_tab_perf()
        self._tabs.addTab(self._tab_drivers, "  Chauffeurs")
        self._tabs.addTab(self._tab_unavail, "  Indisponibilités")
        self._tabs.addTab(self._tab_teams,   "  Équipes")
        self._tabs.addTab(self._tab_perf,    "  Performance")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs)

    def retranslate_ui(self, lang: str):
        from app.i18n import tr
        _keys = [
            "drivers.tab.drivers", "drivers.tab.unavail",
            "drivers.tab.teams",   "drivers.tab.perf",
        ]
        for i, key in enumerate(_keys):
            if i < self._tabs.count():
                self._tabs.setTabText(i, f"  {tr(key, lang)}")
        if hasattr(self, "_drv_section_header"):
            self._drv_section_header.set_title(tr("section.drivers", lang))

    def refresh_data(self):
        self._refresh_drivers_tab()

    def _on_tab_changed(self, idx: int):
        if idx == 0: self._refresh_drivers_tab()
        elif idx == 1: self._refresh_unavail_tab()
        elif idx == 2: self._refresh_teams_tab()
        elif idx == 3: self._refresh_perf_tab()

    # ══════════════════════════════════════════════════════════════════
    # TAB 0 : CHAUFFEURS
    # ══════════════════════════════════════════════════════════════════

    def _build_tab_drivers(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w)
        lo.setContentsMargins(20, 14, 20, 18); lo.setSpacing(10)

        self._expire_banner = _ExpireLicenseBanner()
        lo.addWidget(self._expire_banner)

        self._drv_section_header = SectionHeader(
            title="Chauffeurs",
            subtitle="Gestion de la flotte de conducteurs et de leurs qualifications",
            action_text="+ Ajouter chauffeur",
            action_callback=self._add_driver,
        )
        lo.addWidget(self._drv_section_header)

        toolbar = QHBoxLayout(); toolbar.setSpacing(6)
        self._drv_search = SearchBar(placeholder="Nom, permis, zone…")
        self._drv_search.setMaximumWidth(260)
        self._drv_search.search_changed.connect(lambda _: self._refresh_drivers_tab())
        toolbar.addWidget(self._drv_search)
        toolbar.addStretch()
        self._drv_count = QLabel("0 chauffeurs")
        self._drv_count.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        toolbar.addWidget(self._drv_count)
        toolbar.addSpacing(4)
        _hb = QPushButton()
        _hb.setFixedSize(30, 30)
        _hb.setToolTip("Aide — Chauffeurs")
        _hb.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(_hb, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        _hb.clicked.connect(lambda: show_help(self, "drivers"))
        toolbar.addWidget(_hb)
        lo.addLayout(toolbar)

        self._drv_table = QTableWidget()
        self._drv_table.setColumnCount(9)
        self._drv_table.setHorizontalHeaderLabels([
            "Photo", "Nom", "Permis / Cat.", "Qualifs",
            "Véhicule", "Équipe", "Statut", "Exp.", "Actions",
        ])
        hdr = self._drv_table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for col, w2 in [(0,44),(2,110),(4,100),(5,90),(6,80),(7,65),(8,100)]:
            self._drv_table.setColumnWidth(col, w2)
        self._drv_table.verticalHeader().setVisible(False)
        self._drv_table.verticalHeader().setDefaultSectionSize(44)
        self._drv_table.setAlternatingRowColors(True)
        self._drv_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._drv_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._drv_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._drv_table.customContextMenuRequested.connect(self._drv_context_menu)
        self._drv_table.doubleClicked.connect(
            lambda idx: self._edit_driver(
                self._drv_table.item(idx.row(), 1).data(Qt.ItemDataRole.UserRole)
            ) if self._drv_table.item(idx.row(), 1) else None
        )
        self._drv_table.setStyleSheet(
            f"QTableWidget{{background:{C['bg']};color:{C['text']};"
            f"gridline-color:{C['border']};border:none;alternate-background-color:#0F2035;}}"
            f"QTableWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:4px 6px;font-size:11px;font-weight:600;}}"
        )
        lo.addWidget(self._drv_table, 1)
        return w

    def _refresh_drivers_tab(self):
        self._expire_banner.refresh()
        search = self._drv_search.get_text().strip()

        conn = get_connection()
        if search:
            s = f"%{search}%"
            rows = conn.execute("""
                SELECT d.*, v.registration, t.name AS team_name
                FROM drivers d
                LEFT JOIN vehicles v ON v.id=d.vehicle_id
                LEFT JOIN team_members tm ON tm.driver_id=d.id
                LEFT JOIN teams t ON t.id=tm.team_id
                WHERE d.archived=0
                AND (d.first_name LIKE ? OR d.last_name LIKE ? OR COALESCE(d.license_number,'') LIKE ? OR COALESCE(d.zone_assignment,'') LIKE ? )
                GROUP BY d.id ORDER BY d.last_name
            """, [s, s, s, s]).fetchall()
        else:
            rows = conn.execute("""
                SELECT d.*, v.registration, t.name AS team_name
                FROM drivers d
                LEFT JOIN vehicles v ON v.id=d.vehicle_id
                LEFT JOIN team_members tm ON tm.driver_id=d.id
                LEFT JOIN teams t ON t.id=tm.team_id
                WHERE d.archived=0
                GROUP BY d.id ORDER BY d.last_name
            """).fetchall()
        conn.close()

        self._drv_count.setText(f"{len(rows)} chauffeur{'s' if len(rows) != 1 else ''}")
        self._drv_table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            # Photo cell
            photo_lbl = QLabel()
            photo_lbl.setFixedSize(36, 36)
            photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            photo_lbl.setStyleSheet(
                f"background:{C['input']};border-radius:18px;"
                "font-size:18px;color:#8899AA;"
            )
            photo_lbl.setText("")
            try:
                pp = None
                if "photo_path" in row.keys():
                    pp = row["photo_path"]
                if not pp and "photo_url" in row.keys():
                    pp = row["photo_url"]
                abs_p = resolve_stored_photo(pp)
                if abs_p:
                    pm = QPixmap(abs_p).scaled(36, 36,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation)
                    photo_lbl.setPixmap(pm); photo_lbl.setText("")
            except Exception:
                pass
            cw = QWidget(); cl = QHBoxLayout(cw)
            cl.setContentsMargins(4,4,4,4); cl.addWidget(photo_lbl)
            self._drv_table.setCellWidget(r, 0, cw)

            # Name
            name_it = QTableWidgetItem(f"{row['last_name'].upper()} {row['first_name']}")
            name_it.setData(Qt.ItemDataRole.UserRole, row["id"])
            name_it.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self._drv_table.setItem(r, 1, name_it)

            def _it(v, color=None):
                it = QTableWidgetItem(str(v or ""))
                it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
                if color: it.setForeground(QColor(color))
                return it

            cat = row.get("license_category") or "—"
            num = (row.get("license_number") or "")[:8]
            self._drv_table.setItem(r, 2, _it(f"{num} / {cat}"))
            _q_raw = row.get("qualifications") or ""
            try:
                import json as _j
                _parsed = _j.loads(_q_raw) if _q_raw.strip().startswith("[") else _q_raw.split(",")
                _QUAL_MAP = {"POIDS_LOURD": "Permis_poids_lourd", "MATIÈRES_DANGEREUSES": "ADR",
                             "MATIERES_DANGEREUSES": "ADR", "FRIGO": "HAZMAT", "ECO_CONDUITE": ""}
                quals = ", ".join(filter(None, (_QUAL_MAP.get(q, q) for q in _parsed)))
            except Exception:
                quals = _q_raw
            self._drv_table.setItem(r, 3, _it(quals, C["text2"] if quals else None))

            reg = ""
            try: reg = row["registration"] or ""
            except Exception: pass
            self._drv_table.setItem(r, 4, _it(reg, C["accent"] if reg else None))

            team = ""
            try: team = row["team_name"] or ""
            except Exception: pass
            self._drv_table.setItem(r, 5, _it(team))

            # Status badge
            days = _days_left(row.get("license_expiry") or "")
            if days <= 0:    st, var = "Expiré",     "danger"
            elif days <= 30: st, var = "Alerte",      "warning"
            else:            st, var = "Actif",       "success"
            badge = StatusBadge(var, st)
            cw2 = QWidget(); cl2 = QHBoxLayout(cw2)
            cl2.setContentsMargins(4,2,4,2); cl2.addWidget(badge); cl2.addStretch()
            self._drv_table.setCellWidget(r, 6, cw2)

            exp_str = (row.get("license_expiry") or "")[:10]
            exp_it = _it(exp_str)
            if days <= 0:    exp_it.setForeground(QColor(C["danger"]))
            elif days <= 30: exp_it.setForeground(QColor(C["warning"]))
            self._drv_table.setItem(r, 7, exp_it)

            self._drv_table.setCellWidget(r, 8, self._drv_action_widget(row["id"]))

    def _drv_action_widget(self, did: int) -> QWidget:
        w = QWidget(); lo = QHBoxLayout(w); lo.setContentsMargins(3,1,3,1); lo.setSpacing(3)
        for lucide_key, tip, fn, fg, hbg in [
            ("pencil",   "Modifier",      lambda _, i=did: self._edit_driver(i),         C["accent"],  C["panel"]),
            ("calendar", "Indispos",      lambda _, i=did: self._quick_unavail(i),        C["warning"], C["panel"]),
            ("globe",    "Compte web",    lambda _, i=did: self._create_web_account(i),   "#7EC8E3",    C["panel"]),
            ("archive",  "Archiver",      lambda _, i=did: self._delete_driver(i),        C["danger"],  "#3A1020"),
        ]:
            btn = QPushButton(); btn.setFixedSize(28, 28)
            btn.setToolTip(tip); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_action_button(btn, lucide_key, fg, C["hover"], hbg, icon_px=16)
            btn.clicked.connect(fn); lo.addWidget(btn)
        return w

    def _create_web_account(self, did: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM drivers WHERE id=?", (did,)).fetchone()
        conn.close()
        if not row:
            return
        first = row["first_name"] or ""
        last  = row["last_name"]  or ""
        email = row["email"] if "email" in row.keys() else ""
        svc = get_django_service()
        if not svc.base_url or not svc.secret_key:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Compte web",
                "Django non configure.\nAllez dans Parametres > Django et renseignez l'URL et la cle.")
            return
        result = svc.create_web_user(
            desktop_id=did, role="driver",
            first_name=first, last_name=last, email=email or "",
        )
        self._show_credentials_dialog(result, "driver", f"{first} {last}".strip())

    def _show_credentials_dialog(self, result: dict, role: str, display_name: str):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel,
                                     QLineEdit, QPushButton, QFormLayout, QApplication)
        from .components.confirm_dialog import _dialog_qss
        if not result.get("ok"):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Compte web", f"Erreur : {result.get('error','inconnue')}")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Compte web cree")
        dlg.setFixedWidth(380)
        dlg.setStyleSheet(_dialog_qss() + f"QDialog{{background:{C['bg']};color:{C['text']};}}")
        lo = QVBoxLayout(dlg)
        lo.setSpacing(12)
        status_lbl = QLabel("Compte cree" if result.get("created") else "Compte mis a jour")
        status_lbl.setStyleSheet(f"color:{'#00FF88' if result.get('created') else '#FFB800'};font-weight:bold;font-size:13px;")
        lo.addWidget(status_lbl)
        lo.addWidget(QLabel(f"Chauffeur : <b>{display_name}</b>"))
        form = QFormLayout()
        form.setSpacing(8)
        field_style = f"background:{C['panel']};color:{C['text']};border:1px solid {C['border']};border-radius:5px;padding:4px 8px;"
        u_edit = QLineEdit(result.get("username", ""))
        u_edit.setReadOnly(True); u_edit.setStyleSheet(field_style)
        p_edit = QLineEdit(result.get("_password", ""))
        p_edit.setReadOnly(True); p_edit.setStyleSheet(field_style)
        form.addRow("Identifiant :", u_edit)
        form.addRow("Mot de passe :", p_edit)
        lo.addLayout(form)
        note = QLabel("Transmettez ces identifiants au chauffeur.\nLe mot de passe ne sera plus affiche.")
        note.setStyleSheet(f"color:{C['text2']};font-size:11px;")
        note.setWordWrap(True)
        lo.addWidget(note)
        copy_btn = QPushButton("Copier les identifiants")
        copy_btn.setObjectName("secondaryBtn")
        def _copy():
            QApplication.clipboard().setText(
                f"Identifiant : {u_edit.text()}\nMot de passe : {p_edit.text()}")
            copy_btn.setText("Copie !")
        copy_btn.clicked.connect(_copy)
        lo.addWidget(copy_btn)
        close_btn = QPushButton("Fermer")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(dlg.accept)
        lo.addWidget(close_btn)
        dlg.exec()

    def _drv_context_menu(self, pos):
        row = self._drv_table.rowAt(pos.y())
        if row < 0: return
        it = self._drv_table.item(row, 1)
        did = it.data(Qt.ItemDataRole.UserRole) if it else None
        if not did: return
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};"
            "border-radius:6px;padding:4px;}}"
            f"QMenu::item{{padding:6px 18px;border-radius:4px;}}"
            f"QMenu::item:selected{{background:{C['hover']};}}"
        )
        for label, fn in [
            ("  Modifier",        lambda: self._edit_driver(did)),
            ("  Indispos",       lambda: self._quick_unavail(did)),
            (None, None),
            ("  Archiver",       lambda: self._delete_driver(did)),
        ]:
            if label is None: menu.addSeparator()
            else:
                act = QAction(label, self); act.triggered.connect(fn); menu.addAction(act)
        menu.exec(self._drv_table.viewport().mapToGlobal(pos))

    # ── Driver CRUD ───────────────────────────────────────────────────

    def _add_driver(self):
        dlg = _DriverDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        data = dlg.get_data()
        conn = get_connection()
        cur = conn.execute("""
            INSERT INTO drivers
            (first_name,last_name,phone,email,company_name,notes,
             license_number,license_category,license_expiry,qualifications,
             contract_type,work_start_time,work_end_time,lunch_time,
             lunch_duration_minutes,max_daily_hours,
             overtime_level1_hours,overtime_level1_rate,
             overtime_level2_hours,overtime_level2_rate,
             max_drive_before_break_min,min_break_minutes,min_daily_rest_minutes,
             home_depot_id,vehicle_id,zone_assignment,open_start,open_stop)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["first_name"], data["last_name"], data["phone"], data["email"],
            data["company_name"], data["notes"], data["license_number"],
            data["license_category"], data["license_expiry"], data["qualifications"],
            data["contract_type"], data["work_start_time"], data["work_end_time"],
            data["lunch_time"], data["lunch_duration_minutes"], data["max_daily_hours"],
            data["overtime_level1_hours"], data["overtime_level1_rate"],
            data["overtime_level2_hours"], data["overtime_level2_rate"],
            data["max_drive_before_break_min"], data["min_break_minutes"],
            data["min_daily_rest_minutes"], data["home_depot_id"], data["vehicle_id"],
            data["zone_assignment"], data["open_start"], data["open_stop"],
        ))
        new_id = cur.lastrowid
        stored = ""
        try:
            stored = finalize_stored_path(data.get("photo_path") or "", "driver", new_id)
        except (FileNotFoundError, ValueError, OSError) as e:
            QMessageBox.warning(
                self, "Photo",
                f"Impossible d'enregistrer la photo :\n{e}",
            )
        try:
            conn.execute(
                "UPDATE drivers SET photo_path= ?, photo_url= ? WHERE id= ?",
                (stored, stored, new_id),
            )
        except Exception:
            conn.execute(
                "UPDATE drivers SET photo_url= ? WHERE id= ?",
                (stored, new_id),
            )
        conn.commit(); conn.close()
        # Synchronisation bidirectionnelle chauffeur ↔ véhicule
        try:
            assign_driver_to_vehicle(new_id, data.get("vehicle_id"))
        except Exception:
            logger.exception("Erreur sync véhicule-chauffeur (création chauffeur)")
        log_action("DRIVER_CREATE", f"Chauffeur {data['first_name']} {data['last_name']} créé")
        show_toast(self.window(), f"Chauffeur {data['last_name']} créé", "success")
        self._refresh_drivers_tab()
        self._refresh_unavail_combos()

    def _edit_driver(self, did: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM drivers WHERE id= ?", (did,)).fetchone()
        conn.close()
        if not row: return
        dlg = _DriverDialog(self, dict(row))
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        data = dlg.get_data()
        stored = ""
        try:
            stored = finalize_stored_path(data.get("photo_path") or "", "driver", did)
        except (FileNotFoundError, ValueError, OSError) as e:
            QMessageBox.warning(
                self, "Photo",
                f"Impossible d'enregistrer la photo :\n{e}",
            )
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE drivers SET
                first_name= ?,last_name= ?,phone= ?,email= ?,company_name= ?,notes= ?,
                license_number= ?,license_category= ?,license_expiry= ?,qualifications= ?,
                contract_type= ?,work_start_time= ?,work_end_time= ?,lunch_time= ?,
                lunch_duration_minutes= ?,max_daily_hours= ?,
                overtime_level1_hours= ?,overtime_level1_rate= ?,
                overtime_level2_hours= ?,overtime_level2_rate= ?,
                max_drive_before_break_min= ?,min_break_minutes= ?,min_daily_rest_minutes= ?,
                home_depot_id= ?,vehicle_id= ?,zone_assignment= ?,open_start= ?,open_stop= ?,
                photo_path= ?, photo_url= ? WHERE id=?
            """, (
                data["first_name"], data["last_name"], data["phone"], data["email"],
                data["company_name"], data["notes"], data["license_number"],
                data["license_category"], data["license_expiry"], data["qualifications"],
                data["contract_type"], data["work_start_time"], data["work_end_time"],
                data["lunch_time"], data["lunch_duration_minutes"], data["max_daily_hours"],
                data["overtime_level1_hours"], data["overtime_level1_rate"],
                data["overtime_level2_hours"], data["overtime_level2_rate"],
                data["max_drive_before_break_min"], data["min_break_minutes"],
                data["min_daily_rest_minutes"], data["home_depot_id"], data["vehicle_id"],
                data["zone_assignment"], data["open_start"], data["open_stop"],
                stored, stored, did,
            ))
        except Exception:
            conn.execute("""
                UPDATE drivers SET
                first_name= ?,last_name= ?,phone= ?,email= ?,company_name= ?,notes= ?,
                license_number= ?,license_category= ?,license_expiry= ?,qualifications= ?,
                contract_type= ?,work_start_time= ?,work_end_time= ?,lunch_time= ?,
                lunch_duration_minutes= ?,max_daily_hours= ?,
                overtime_level1_hours= ?,overtime_level1_rate= ?,
                overtime_level2_hours= ?,overtime_level2_rate= ?,
                max_drive_before_break_min= ?,min_break_minutes= ?,min_daily_rest_minutes= ?,
                home_depot_id= ?,vehicle_id= ?,zone_assignment= ?,open_start= ?,open_stop= ?,
                photo_url= ? WHERE id=?
            """, (
                data["first_name"], data["last_name"], data["phone"], data["email"],
                data["company_name"], data["notes"], data["license_number"],
                data["license_category"], data["license_expiry"], data["qualifications"],
                data["contract_type"], data["work_start_time"], data["work_end_time"],
                data["lunch_time"], data["lunch_duration_minutes"], data["max_daily_hours"],
                data["overtime_level1_hours"], data["overtime_level1_rate"],
                data["overtime_level2_hours"], data["overtime_level2_rate"],
                data["max_drive_before_break_min"], data["min_break_minutes"],
                data["min_daily_rest_minutes"], data["home_depot_id"], data["vehicle_id"],
                data["zone_assignment"], data["open_start"], data["open_stop"],
                stored, did,
            ))
        conn.commit(); conn.close()
        # Synchronisation bidirectionnelle chauffeur ↔ véhicule
        try:
            assign_driver_to_vehicle(did, data.get("vehicle_id"))
        except Exception:
            logger.exception("Erreur sync véhicule-chauffeur (modification chauffeur)")
        log_action("DRIVER_UPDATE", f"Chauffeur #{did} modifié")
        show_toast(self.window(), "Chauffeur mis à jour", "success")
        self._refresh_drivers_tab()
        self._refresh_unavail_combos()

    def _delete_driver(self, did: int):
        if not ConfirmDialog.ask(self, "Archiver", "Archiver ce chauffeur ", "danger"): return
        conn = get_connection()
        conn.execute("UPDATE drivers SET archived=1 WHERE id= ?", (did,))
        conn.commit(); conn.close()
        log_action("DRIVER_DELETE", f"Chauffeur #{did} archivé")
        show_toast(self.window(), "Chauffeur archivé", "info")
        self._refresh_drivers_tab()
        self._refresh_unavail_combos()

    def _quick_unavail(self, did: int):
        """Switch to unavailabilities tab and select this driver."""
        self._tabs.setCurrentIndex(1)
        for i in range(self._unavail_combo.count()):
            if self._unavail_combo.itemData(i) == did:
                self._unavail_combo.setCurrentIndex(i)
                break

    # ══════════════════════════════════════════════════════════════════
    # TAB 1 : INDISPONIBILITÉS
    # ══════════════════════════════════════════════════════════════════

    def _build_tab_unavail(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w)
        lo.setContentsMargins(20, 14, 20, 18); lo.setSpacing(12)

        hdr = QHBoxLayout()
        t = QLabel("Indisponibilités"); t.setStyleSheet(f"color:{C['text']};font-size:16px;font-weight:700;background:transparent;")
        hdr.addWidget(t); hdr.addSpacing(20)
        hdr.addWidget(QLabel("Chauffeur :"))

        self._unavail_combo = QComboBox(); self._unavail_combo.setFixedWidth(220)
        self._unavail_combo.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
            f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
            f"border:1px solid {C['border']};}}"
        )
        self._unavail_combo.currentIndexChanged.connect(self._on_unavail_driver_changed)
        hdr.addWidget(self._unavail_combo); hdr.addStretch()
        lo.addLayout(hdr)

        # Calendar
        self._cal_grid = _CalendarGrid()
        self._cal_grid.date_clicked.connect(self._on_cal_date_click)
        lo.addWidget(self._cal_grid)

        # Info bar
        self._unavail_info = QLabel("Cliquez sur un jour pour ajouter/modifier une indisponibilité.")
        self._unavail_info.setStyleSheet(f"color:{C['text2']};font-size:12px;background:transparent;")
        lo.addWidget(self._unavail_info)
        lo.addStretch()
        return w

    def _refresh_unavail_tab(self):
        self._refresh_unavail_combos()

    def _refresh_unavail_combos(self):
        cur_id = self._unavail_combo.currentData()
        self._unavail_combo.blockSignals(True)
        self._unavail_combo.clear()
        self._unavail_combo.addItem("— Sélectionner un chauffeur", None)
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT id, first_name, last_name FROM drivers WHERE archived=0 ORDER BY last_name"
            ).fetchall()
            conn.close()
            for row in rows:
                self._unavail_combo.addItem(f"{row['last_name']} {row['first_name']}", row["id"])
        except Exception:
            pass
        self._unavail_combo.blockSignals(False)
        if cur_id:
            for i in range(self._unavail_combo.count()):
                if self._unavail_combo.itemData(i) == cur_id:
                    self._unavail_combo.setCurrentIndex(i); break

    def _on_unavail_driver_changed(self):
        did = self._unavail_combo.currentData()
        if did:
            self._cal_grid.set_driver(did)
        else:
            self._cal_grid._driver_id = 0
            self._cal_grid._unavail = set()
            self._cal_grid._has_route = set()
            self._cal_grid._render()

    def _on_cal_date_click(self, date_str: str):
        did = self._unavail_combo.currentData()
        if not did:
            self._unavail_info.setText("Sélectionnez d'abord un chauffeur.")
            return
        try:
            conn = get_connection()
            existing = conn.execute(
                "SELECT * FROM driver_unavailabilities WHERE driver_id= ? AND date= ?",
                (did, date_str),
            ).fetchone()
            existing_dict = dict(existing) if existing else None
            # Check for planned routes
            has_route = False
            try:
                r = conn.execute(
                    "SELECT id FROM routes WHERE driver_id= ? AND planned_date= ? LIMIT 1",
                    (did, date_str),
                ).fetchone()
                has_route = r is not None
            except Exception:
                pass
            conn.close()
        except Exception:
            existing_dict = None; has_route = False

        dlg = _UnavailDialog(did, date_str, existing_dict, self)
        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted and not existing_dict:
            data = dlg.get_data()
            conn = get_connection()
            conn.execute(
                "INSERT INTO driver_unavailabilities (driver_id,date,reason,notes)"
                " VALUES (?,?,?,?)",
                (data["driver_id"], data["date"], data["reason"], data["notes"]),
            )
            conn.commit(); conn.close()
            log_action("DRIVER_UNAVAIL_ADD", f"Indispo #{did} le {date_str}")
        elif result == QDialog.DialogCode.Accepted and existing_dict:
            data = dlg.get_data()
            conn = get_connection()
            conn.execute(
                "UPDATE driver_unavailabilities SET reason= ?,notes= ? WHERE id= ?",
                (data["reason"], data["notes"], existing_dict["id"]),
            )
            conn.commit(); conn.close()
            log_action("DRIVER_UNAVAIL_UPD", f"Indispo #{did} le {date_str} modifiée")
        # After change refresh calendar
        if result in (QDialog.DialogCode.Accepted, 2):
            self._cal_grid._load_data()
            if has_route and result != 2:
                self._suggest_replacement(did, date_str)

    def _suggest_replacement(self, did: int, date_str: str):
        try:
            conn = get_connection()
            unavail_ids = {
                r["driver_id"] for r in conn.execute(
                    "SELECT driver_id FROM driver_unavailabilities WHERE date= ?", (date_str,)
                ).fetchall()
            }
            alts = conn.execute("""
                SELECT id, first_name, last_name FROM drivers
                WHERE archived=0 AND id != ? ORDER BY last_name
            """, (did,)).fetchall()
            conn.close()
            available = [a for a in alts if a["id"] not in unavail_ids]
        except Exception:
            available = []
        msg = f"Une route est planifiée le {date_str} pour ce chauffeur.\n\n"
        if available:
            names = ", ".join(f"{a['first_name']} {a['last_name']}" for a in available[:5])
            msg += f"Remplaçants disponibles : {names}"
        else:
            msg += "Aucun remplaçant disponible ce jour."
        QMessageBox.information(self, "Suggestion remplacement", msg)

    # ══════════════════════════════════════════════════════════════════
    # TAB 2 : ÉQUIPES
    # ══════════════════════════════════════════════════════════════════

    def _build_tab_teams(self) -> QWidget:
        w = QWidget(); root = QHBoxLayout(w)
        root.setContentsMargins(20, 14, 20, 18); root.setSpacing(16)

        # Left : team list
        left = QVBoxLayout(); left.setSpacing(6)
        t_hdr = QHBoxLayout()
        t_hdr.addWidget(QLabel("Équipes"))
        add_team = QPushButton("+ Nouvelle équipe")
        add_team.setObjectName("primaryBtn")
        add_team.setMinimumWidth(148)
        add_team.setFixedHeight(32)
        add_team.clicked.connect(self._add_team)
        t_hdr.addStretch(); t_hdr.addWidget(add_team)
        left.addLayout(t_hdr)

        self._team_list = QListWidget()
        self._team_list.setFixedWidth(200)
        self._team_list.setStyleSheet(
            f"QListWidget{{background:{C['panel']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;}}"
            f"QListWidget::item{{padding:8px 10px;}}"
            f"QListWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
            f"QListWidget::item:hover{{background:{C['input']};}}"
        )
        self._team_list.currentItemChanged.connect(self._on_team_selected)
        left.addWidget(self._team_list, 1)

        del_team_btn = QPushButton(" Supprimer équipe"); del_team_btn.setFixedHeight(28)
        del_team_btn.setStyleSheet(_BTN_S % (C["hover"], C["danger"], "#3A1020"))
        del_team_btn.clicked.connect(self._delete_team)
        left.addWidget(del_team_btn)
        root.addLayout(left)

        # Right : team detail
        right = QVBoxLayout(); right.setSpacing(8)

        self._team_name_lbl = QLabel("Sélectionnez une équipe")
        self._team_name_lbl.setStyleSheet(f"color:{C['accent']};font-size:16px;font-weight:700;background:transparent;")
        right.addWidget(self._team_name_lbl)

        mgr_row = QHBoxLayout()
        mgr_row.addWidget(QLabel("Manager :"))
        self._mgr_combo = QComboBox(); self._mgr_combo.setFixedWidth(200)
        self._mgr_combo.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
            f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
            f"border:1px solid {C['border']};}}"
        )
        save_mgr = QPushButton(" Enregistrer"); save_mgr.setFixedHeight(28)
        save_mgr.setToolTip("Enregistrer le manager de l'équipe")
        save_mgr.setStyleSheet(_BTN_S % (C["hover"], C["success"], C["panel"]))
        save_mgr.setToolTip("Enregistrer manager"); save_mgr.clicked.connect(self._save_manager)
        mgr_row.addWidget(self._mgr_combo); mgr_row.addWidget(save_mgr); mgr_row.addStretch()
        right.addLayout(mgr_row)

        members_row = QHBoxLayout(); members_row.setSpacing(8)

        # Members list
        ml = QVBoxLayout(); ml.setSpacing(4)
        ml.addWidget(QLabel("Membres de l'équipe"))
        self._members_list = QListWidget()
        self._members_list.setStyleSheet(
            f"QListWidget{{background:{C['panel']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;}}"
            f"QListWidget::item{{padding:6px 10px;}}"
            f"QListWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
        )
        ml.addWidget(self._members_list, 1)

        # Transferts membre ↔ pool chauffeurs
        mid = QVBoxLayout(); mid.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        add_m = QPushButton("Ajouter →")
        add_m.setObjectName("primaryBtn")
        add_m.setMinimumWidth(120)
        add_m.setFixedHeight(32)
        add_m.clicked.connect(self._add_member)
        rem_m = QPushButton("← Retirer")
        rem_m.setObjectName("secondaryBtn")
        rem_m.setMinimumWidth(120)
        rem_m.setFixedHeight(32)
        rem_m.clicked.connect(self._remove_member)
        mid.addStretch(); mid.addWidget(add_m); mid.addSpacing(6)
        mid.addWidget(rem_m); mid.addStretch()

        # All drivers list
        al = QVBoxLayout(); al.setSpacing(4)
        al.addWidget(QLabel("Tous les chauffeurs"))
        self._all_drivers_list = QListWidget()
        self._all_drivers_list.setStyleSheet(
            f"QListWidget{{background:{C['panel']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;}}"
            f"QListWidget::item{{padding:6px 10px;}}"
            f"QListWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
        )
        al.addWidget(self._all_drivers_list, 1)

        members_row.addLayout(ml, 1)
        members_row.addLayout(mid)
        members_row.addLayout(al, 1)
        right.addLayout(members_row, 1)
        root.addLayout(right, 1)
        w.setStyleSheet(_dialog_qss())
        return w

    def _refresh_teams_tab(self):
        self._team_list.clear()
        try:
            conn = get_connection()
            teams = conn.execute(
                "SELECT * FROM teams WHERE archived=0 ORDER BY name"
            ).fetchall()
            conn.close()
            for team in teams:
                it = QListWidgetItem(team["name"])
                it.setData(Qt.ItemDataRole.UserRole, team["id"])
                it.setData(Qt.ItemDataRole.UserRole + 1, dict(team))
                self._team_list.addItem(it)
        except Exception:
            pass
        self._reload_all_drivers_list()

    def _reload_all_drivers_list(self):
        self._all_drivers_list.clear()
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT id, first_name, last_name FROM drivers WHERE archived=0 ORDER BY last_name"
            ).fetchall()
            conn.close()
            for row in rows:
                it = QListWidgetItem(f"{row['last_name']} {row['first_name']}")
                it.setData(Qt.ItemDataRole.UserRole, row["id"])
                self._all_drivers_list.addItem(it)
        except Exception:
            pass

    def _on_team_selected(self, current, _prev):
        if not current: return
        team_id = current.data(Qt.ItemDataRole.UserRole)
        team_data = current.data(Qt.ItemDataRole.UserRole + 1) or {}
        self._team_name_lbl.setText(current.text())
        self._current_team_id = team_id

        # Load members
        self._members_list.clear()
        self._mgr_combo.clear()
        self._mgr_combo.addItem("— Aucun manager", None)
        try:
            conn = get_connection()
            members = conn.execute("""
                SELECT d.id, d.first_name, d.last_name
                FROM team_members tm JOIN drivers d ON d.id=tm.driver_id
                WHERE tm.team_id= ? AND d.archived=0 ORDER BY d.last_name
            """, (team_id,)).fetchall()
            conn.close()
            for m in members:
                it = QListWidgetItem(f"{m['last_name']} {m['first_name']}")
                it.setData(Qt.ItemDataRole.UserRole, m["id"])
                self._members_list.addItem(it)
                self._mgr_combo.addItem(f"{m['last_name']} {m['first_name']}", m["id"])
        except Exception:
            pass

        mgr = team_data.get("manager_driver_id")
        if mgr:
            for i in range(self._mgr_combo.count()):
                if self._mgr_combo.itemData(i) == mgr:
                    self._mgr_combo.setCurrentIndex(i); break

    def _add_team(self):
        name, ok = _simple_input_dialog(self, "Nouvelle équipe", "Nom de l'équipe :")
        if not ok or not name.strip(): return
        conn = get_connection()
        conn.execute("INSERT INTO teams (name) VALUES (?)", (name.strip(),))
        conn.commit(); conn.close()
        log_action("TEAM_CREATE", f"Équipe '{name}' créée")
        show_toast(self.window(), f"Équipe '{name}' créée", "success")
        self._refresh_teams_tab()

    def _delete_team(self):
        cur = self._team_list.currentItem()
        if not cur: return
        tid = cur.data(Qt.ItemDataRole.UserRole)
        if not ConfirmDialog.ask(self, "Supprimer", f"Supprimer l'équipe « {cur.text()} » ", "danger"): return
        conn = get_connection()
        conn.execute("UPDATE teams SET archived=1 WHERE id= ?", (tid,))
        conn.execute("DELETE FROM team_members WHERE team_id= ?", (tid,))
        conn.commit(); conn.close()
        log_action("TEAM_DELETE", f"Équipe #{tid} supprimée")
        show_toast(self.window(), "Équipe supprimée", "info")
        self._refresh_teams_tab()

    def _add_member(self):
        cur = self._all_drivers_list.currentItem()
        if not cur: return
        team_id = getattr(self, "_current_team_id", None)
        if not team_id: return
        drv_id = cur.data(Qt.ItemDataRole.UserRole)
        try:
            conn = get_connection()
            exists = conn.execute(
                "SELECT 1 FROM team_members WHERE team_id= ? AND driver_id= ?", (team_id, drv_id)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO team_members (team_id, driver_id) VALUES (?,?)", (team_id, drv_id)
                )
                conn.commit()
                log_action("TEAM_MEMBER_ADD", f"Chauffeur #{drv_id} → équipe #{team_id}")
            conn.close()
        except Exception as e:
            show_toast(self.window(), f"Erreur: {e}", "error"); return
        self._on_team_selected(self._team_list.currentItem(), None)

    def _remove_member(self):
        cur = self._members_list.currentItem()
        if not cur: return
        team_id = getattr(self, "_current_team_id", None)
        if not team_id: return
        drv_id = cur.data(Qt.ItemDataRole.UserRole)
        conn = get_connection()
        conn.execute("DELETE FROM team_members WHERE team_id= ? AND driver_id= ?", (team_id, drv_id))
        conn.commit(); conn.close()
        log_action("TEAM_MEMBER_REMOVE", f"Chauffeur #{drv_id} retiré de l'équipe #{team_id}")
        self._on_team_selected(self._team_list.currentItem(), None)

    def _save_manager(self):
        team_id = getattr(self, "_current_team_id", None)
        if not team_id: return
        mgr_id = self._mgr_combo.currentData()
        conn = get_connection()
        conn.execute("UPDATE teams SET manager_driver_id= ? WHERE id= ?", (mgr_id, team_id))
        conn.commit(); conn.close()
        log_action("TEAM_MANAGER", f"Manager équipe #{team_id} → #{mgr_id}")
        show_toast(self.window(), "Manager enregistré", "success")

    # ══════════════════════════════════════════════════════════════════
    # TAB 3 : PERFORMANCE
    # ══════════════════════════════════════════════════════════════════

    def _build_tab_perf(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w)
        lo.setContentsMargins(20, 14, 20, 18); lo.setSpacing(10)

        t_lbl = QLabel("Performance des chauffeurs")
        t_lbl.setStyleSheet(f"color:{C['text']};font-size:16px;font-weight:700;background:transparent;")
        lo.addWidget(t_lbl)

        # Filters
        filt = QHBoxLayout(); filt.setSpacing(8)
        filt.addWidget(QLabel("Chauffeur :"))
        self._perf_drv = QComboBox(); self._perf_drv.setFixedWidth(200)
        self._perf_drv.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
            f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
            f"border:1px solid {C['border']};}}"
        )
        filt.addWidget(self._perf_drv)
        filt.addWidget(QLabel("De :"))
        self._perf_from = QDateEdit(); self._perf_from.setCalendarPopup(True); self._perf_from.setDisplayFormat("dd/MM/yyyy")
        self._perf_from.setDate(QDate.currentDate().addMonths(-3))
        self._perf_to = QDateEdit(); self._perf_to.setCalendarPopup(True); self._perf_to.setDisplayFormat("dd/MM/yyyy")
        self._perf_to.setDate(QDate.currentDate())
        for de in [self._perf_from, self._perf_to]:
            de.setStyleSheet(
                f"QDateEdit{{background:{C['input']};color:{C['text']};"
                f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
            )
        filt.addWidget(QLabel("à :")); filt.addWidget(self._perf_from)
        filt.addWidget(self._perf_to)
        apply_btn = QPushButton("Actualiser"); apply_btn.setObjectName("primaryBtn")
        apply_btn.setFixedHeight(30); apply_btn.clicked.connect(self._refresh_perf_tab)
        filt.addWidget(apply_btn)
        exp_btn = QPushButton(" CSV"); exp_btn.setFixedHeight(30)
        exp_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px 10px;}}"
        )
        exp_btn.clicked.connect(self._export_perf)
        filt.addWidget(exp_btn)
        filt.addStretch()
        lo.addLayout(filt)

        # Table
        self._perf_table = QTableWidget()
        self._perf_table.setColumnCount(7)
        self._perf_table.setHorizontalHeaderLabels([
            "Chauffeur", "Tournées", "Km total", "Km moy/tour",
            "Retard moy (min)", "Taux ponctualité", "Dernière tournée",
        ])
        hdr = self._perf_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._perf_table.verticalHeader().setVisible(False)
        self._perf_table.verticalHeader().setDefaultSectionSize(32)
        self._perf_table.setAlternatingRowColors(True)
        self._perf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._perf_table.setMaximumHeight(200)
        self._perf_table.setStyleSheet(
            f"QTableWidget{{background:{C['bg']};color:{C['text']};"
            f"gridline-color:{C['border']};border:none;alternate-background-color:#0F2035;}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:4px 6px;font-size:11px;font-weight:600;}}"
        )
        lo.addWidget(self._perf_table)

        # Chart placeholder
        self._perf_chart_container = QWidget()
        self._perf_chart_container.setMinimumHeight(250)
        self._perf_chart_lo = QVBoxLayout(self._perf_chart_container)
        self._perf_chart_lo.setContentsMargins(0, 0, 0, 0)
        if not HAS_MPL:
            no_mpl = QLabel("(Matplotlib requis pour les graphiques)")
            no_mpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_mpl.setStyleSheet(f"color:{C['text2']};font-size:13px;background:transparent;")
            self._perf_chart_lo.addWidget(no_mpl)
        lo.addWidget(self._perf_chart_container, 1)
        return w

    def _refresh_perf_tab(self):
        # Reload driver combo
        cur_id = self._perf_drv.currentData()
        self._perf_drv.blockSignals(True)
        self._perf_drv.clear()
        self._perf_drv.addItem("— Tous les chauffeurs", None)
        try:
            conn = get_connection()
            drvs = conn.execute(
                "SELECT id, first_name, last_name FROM drivers WHERE archived=0 ORDER BY last_name"
            ).fetchall()
            conn.close()
            for d in drvs:
                self._perf_drv.addItem(f"{d['last_name']} {d['first_name']}", d["id"])
        except Exception:
            pass
        self._perf_drv.blockSignals(False)
        if cur_id:
            for i in range(self._perf_drv.count()):
                if self._perf_drv.itemData(i) == cur_id:
                    self._perf_drv.setCurrentIndex(i); break

        from_dt = self._perf_from.date().toString("yyyy-MM-dd")
        to_dt   = self._perf_to.date().toString("yyyy-MM-dd")
        flt_id  = self._perf_drv.currentData()

        self._perf_data = self._load_perf_data(from_dt, to_dt, flt_id)
        self._fill_perf_table()
        self._draw_perf_chart()

    def _load_perf_data(self, from_dt, to_dt, driver_id=None) -> list:
        results = []
        try:
            conn = get_connection()
            where = "r.planned_date >= ? AND r.planned_date <= ?"
            params = [from_dt, to_dt]
            if driver_id:
                where += " AND r.driver_id= ?"
                params.append(driver_id)
            rows = conn.execute(f"""
                SELECT
                    d.id, d.first_name, d.last_name,
                    COUNT(r.id) AS nb_routes,
                    COALESCE(SUM(r.total_km),0) AS total_km,
                    COALESCE(AVG(r.total_km),0) AS avg_km,
                    MAX(r.planned_date) AS last_date,
                    COALESCE(AVG(
                        CAST(r.on_time_count AS REAL) / NULLIF(r.stops_count,0) * 100
                    ),0) AS on_time_pct
                FROM routes r
                JOIN drivers d ON d.id=r.driver_id
                WHERE {where}
                GROUP BY d.id
                ORDER BY nb_routes DESC
            """, params).fetchall()
            conn.close()
            for row in rows:
                results.append({
                    "id":          row["id"],
                    "name":        f"{row['last_name']} {row['first_name']}",
                    "nb_routes":   int(row["nb_routes"]),
                    "total_km":    float(row["total_km"]),
                    "avg_km":      float(row["avg_km"]),
                    "last_date":   row["last_date"] or "",
                    "on_time_pct": float(row["on_time_pct"]),
                    "avg_delay":   0.0,
                })
        except Exception as e:
            logger.debug("Perf data error: %s", e)
        return results

    def _fill_perf_table(self):
        data = self._perf_data
        self._perf_table.setRowCount(len(data))
        for r, row in enumerate(data):
            def _it(v, color=None):
                it = QTableWidgetItem(str(v))
                it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
                if color: it.setForeground(QColor(color))
                return it
            self._perf_table.setItem(r, 0, _it(row["name"]))
            self._perf_table.setItem(r, 1, _it(str(row["nb_routes"])))
            self._perf_table.setItem(r, 2, _it(f"{row['total_km']:.0f}"))
            self._perf_table.setItem(r, 3, _it(f"{row['avg_km']:.1f}"))
            self._perf_table.setItem(r, 4, _it(f"{row['avg_delay']:.1f}"))
            pct = row["on_time_pct"]
            color = C["success"] if pct >= 90 else C["warning"] if pct >= 70 else C["danger"]
            self._perf_table.setItem(r, 5, _it(f"{pct:.1f}%", color))
            self._perf_table.setItem(r, 6, _it(row["last_date"]))

    def _draw_perf_chart(self):
        # Clear previous
        for i in reversed(range(self._perf_chart_lo.count())):
            w = self._perf_chart_lo.itemAt(i).widget()
            if w: w.deleteLater()
        if not HAS_MPL or not self._perf_data: return
        try:
            data = self._perf_data[:10]
            names = [d["name"].split()[0][:8] for d in data]
            kms   = [d["total_km"] for d in data]

            fig, ax = plt.subplots(figsize=(8, 3))
            fig.patch.set_facecolor("#112240")
            ax.set_facecolor("#0D1B2A")
            bars = ax.bar(names, kms, color="#00D4FF", edgecolor="#1E3A5F", linewidth=0.5)
            ax.set_ylabel("Km total", color="#8899AA", fontsize=10)
            ax.tick_params(axis="x", colors="#8899AA", labelsize=9, rotation=20)
            ax.tick_params(axis="y", colors="#8899AA", labelsize=9)
            for sp in ax.spines.values(): sp.set_color("#1E3A5F")
            ax.yaxis.label.set_color("#8899AA")
            fig.tight_layout(pad=0.5)
            canvas = FigCanvas(fig)
            canvas.setMinimumHeight(240)
            self._perf_chart_lo.addWidget(canvas)
            plt.close(fig)
        except Exception as e:
            logger.debug("Chart draw error: %s", e)

    def _export_perf(self):
        if not hasattr(self, "_perf_data") or not self._perf_data:
            show_toast(self.window(), "Aucune donnée à exporter.", "info"); return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter performances", "perf_chauffeurs.csv", "CSV (*.csv)"
        )
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=self._perf_data[0].keys())
                w.writeheader(); w.writerows(self._perf_data)
            show_toast(self.window(), f"{len(self._perf_data)} lignes exportées", "success")
        except Exception as e:
            show_toast(self.window(), f"Erreur export: {e}", "error")


# ── Helper ────────────────────────────────────────────────────────────────────

def _simple_input_dialog(parent, title: str, label: str) -> tuple:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(320, 100)
    dlg.setStyleSheet(
        _dialog_qss()
        + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
        f"QLineEdit{{background:{C['input']};color:{C['text']};"
        f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
        f"QLabel{{background:transparent;color:{C['text']};}}"
    )
    lo = QVBoxLayout(dlg); fl = QFormLayout(); fl.setSpacing(8); fl.setContentsMargins(12,12,12,8)
    inp = QLineEdit(); inp.setPlaceholderText("…")
    fl.addRow(QLabel(label), inp); lo.addLayout(fl)
    btn_row = QHBoxLayout(); btn_row.addStretch()
    cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn"); cancel.setFixedHeight(30)
    cancel.clicked.connect(dlg.reject)
    ok = QPushButton("OK"); ok.setObjectName("primaryBtn"); ok.setFixedHeight(30)
    ok.clicked.connect(dlg.accept)
    btn_row.addWidget(cancel); btn_row.addWidget(ok); lo.addLayout(btn_row)
    result = dlg.exec()
    return inp.text(), result == QDialog.DialogCode.Accepted
