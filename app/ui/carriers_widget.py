"""
carriers_widget.py — Gestion des transporteurs CityPulse Logistics v1.0
========================================================================
QTabWidget 4 onglets :
  Transporteurs  — table + fiche 3 onglets (Infos, Capacités & Tarifs, Performance)
  Expéditions   — table + dialogue + refresh HTTP des statuts via QThread
  Simulation    — comparatif flotte propre vs sous-traitance + camembert Matplotlib
  Évaluation    — récap agrégé + graphique barres + export PDF/Excel
"""

# ── stdlib ────────────────────────────────────────────────────────────────────
import csv
import io
import logging
import math
from datetime import date, datetime

# ── PyQt6 ────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
  QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
  QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
  QDateEdit, QTextEdit, QCheckBox, QMessageBox, QFrame,
  QTabWidget, QAbstractItemView, QMenu, QFileDialog,
  QSizePolicy, QScrollArea, QGroupBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QFont, QAction

# ── Local ─────────────────────────────────────────────────────────────────────
from ..database.db_manager import get_connection, log_action
from .toast import show_toast
from .help_dialog import show_help
from .components import (
  SectionHeader, SearchBar, StatusBadge, StarRating, ConfirmDialog, KPICard,
)
from .lucide_icons import apply_action_button
from .components.confirm_dialog import _dialog_qss

try:
  import matplotlib
  matplotlib.use("Agg")
  import matplotlib.pyplot as plt
  from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
  HAS_MPL = True
except ImportError:
  HAS_MPL = False

try:
  import requests as _requests
  HAS_REQUESTS = True
except ImportError:
  HAS_REQUESTS = False

try:
  import keyring as _keyring
  HAS_KEYRING = True
except ImportError:
  HAS_KEYRING = False

try:
  import openpyxl as _openpyxl
  HAS_OPENPYXL = True
except ImportError:
  HAS_OPENPYXL = False

try:
  from reportlab.lib.pagesizes import A4
  from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
  from reportlab.lib.styles import getSampleStyleSheet
  from reportlab.lib import colors as rl_colors
  HAS_REPORTLAB = True
except ImportError:
  HAS_REPORTLAB = False

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
  "bg":  "#0D1B2A", "panel": "#112240", "input": "#1A2E4A",
  "accent":"#00D4FF", "success":"#00FF88", "warning":"#FFB800",
  "danger":"#FF4757", "text":  "#E8F4FD", "text2": "#8899AA",
  "border":"#1E3A5F", "hover": "#1A3A5C",
}

_GRP_QSS = (
    f"QGroupBox{{border:1px solid {C['border']};border-radius:6px;"
    "margin-top:16px;padding:8px;}}"
    f"QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;"
    f"top:-2px;left:8px;padding:0 4px;color:{C['accent']};"
    f"background:{C['bg']};font-weight:700;font-size:11px;}}"
)

_KEYRING_SERVICE = "citypulse_carrier"
_VEHICLE_TYPES  = ["Camionnette", "Camion 3.5t", "Camion 7.5t", "Camion 12t",
          "Semi-remorque", "Frigorifique", "Citerne", "Benne", "Plateau"]
_SHIP_STATUSES  = ["pending", "collected", "in_transit", "delivered", "failed", "returned"]
_SHIP_STATUS_LBL = {
  "pending":  ("En attente", "warning"),
  "collected": ("Collectée",  "info"),
  "in_transit": ("En transit", "info"),
  "delivered": ("Livrée",   "success"),
  "failed":   ("Échouée",   "danger"),
  "returned":  ("Retournée",  "danger"),
}

_BTN_S = (
  "QPushButton{background:%s;color:%s;border:none;"
  "border-radius:4px;font-size:15px;padding:2px 4px;}"
  "QPushButton:hover{background:%s;}"
)
_INP = (
  f"QLineEdit,QTextEdit,QSpinBox,QDoubleSpinBox,QDateEdit,QComboBox{{"
  f"background:{C['input']};color:{C['text']};border:1px solid {C['border']};"
  "border-radius:5px;padding:4px 8px;}"
  f"QComboBox::drop-down{{border:none;}}"
  f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
  f"border:1px solid {C['border']};}}"
)
_GRP = (
  f"QGroupBox{{color:{C['text2']};border:1px solid {C['border']};"
  "border-radius:5px;margin-top:10px;padding-top:8px;}"
  f"QGroupBox::title{{subcontrol-origin:margin;left:8px;padding:0 4px;"
  f"color:{C['accent']};font-weight:700;}}"
)
_TBL = (
  f"QTableWidget{{background:{C['bg']};color:{C['text']};"
  f"gridline-color:{C['border']};border:none;alternate-background-color:#0F2035;}}"
  f"QTableWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
  f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
  f"border:1px solid {C['border']};padding:4px 6px;font-size:11px;font-weight:600;}}"
)

# ── Keyring helpers ───────────────────────────────────────────────────────────

def _key_set(carrier_id: int, api_key: str):
  if HAS_KEYRING and api_key:
    try:
      _keyring.set_password(_KEYRING_SERVICE, str(carrier_id), api_key)
    except Exception:
      pass

def _key_get(carrier_id: int) -> str:
  if HAS_KEYRING and carrier_id:
    try:
      return _keyring.get_password(_KEYRING_SERVICE, str(carrier_id)) or ""
    except Exception:
      pass
  return ""

def _key_del(carrier_id: int):
  if HAS_KEYRING:
    try:
      _keyring.delete_password(_KEYRING_SERVICE, str(carrier_id))
    except Exception:
      pass


# ── Haversine distance ─────────────────────────────────────────────────────────

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
  R = 6371.0
  try:
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(float(lat1))) * \
      math.cos(math.radians(float(lat2))) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))
  except Exception:
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# TAG INPUT WIDGET
# ═══════════════════════════════════════════════════════════════════════════════

class _TagsInput(QWidget):
  """Simple editable tag list (zones covered)."""

  def __init__(self, initial: str = "", parent=None):
    super().__init__(parent)
    self.setStyleSheet(f"background:{C['input']};border:1px solid {C['border']};border-radius:5px;")
    lo = QHBoxLayout(self); lo.setContentsMargins(4, 2, 4, 2); lo.setSpacing(4)
    self._inp = QLineEdit()
    self._inp.setPlaceholderText("Ajouter zone… (Entrée)")
    self._inp.setStyleSheet(f"background:transparent;border:none;color:{C['text']};")
    self._inp.returnPressed.connect(self._add_tag)
    lo.addWidget(self._inp, 1)
    self._tags: list[str] = [t.strip() for t in initial.split(",") if t.strip()]
    self._chip_lo = QHBoxLayout(); self._chip_lo.setSpacing(4)
    lo.insertLayout(0, self._chip_lo)
    self._render()

  def _render(self):
    for i in reversed(range(self._chip_lo.count())):
      w = self._chip_lo.itemAt(i).widget()
      if w: w.deleteLater()
    for tag in self._tags:
      chip = QPushButton(f"× {tag}")
      chip.setStyleSheet(
        f"QPushButton{{background:{C['hover']};color:{C['accent']};"
        "border:none;border-radius:3px;font-size:11px;padding:1px 6px;}}"
        f"QPushButton:hover{{background:{C['danger']};color:#fff;}}"
      )
      chip.clicked.connect(lambda _, t=tag: self._remove_tag(t))
      self._chip_lo.addWidget(chip)

  def _add_tag(self):
    t = self._inp.text().strip()
    if t and t not in self._tags:
      self._tags.append(t)
      self._render()
    self._inp.clear()

  def _remove_tag(self, tag: str):
    if tag in self._tags:
      self._tags.remove(tag); self._render()

  def get_value(self) -> str:
    return ",".join(self._tags)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS REFRESH THREAD
# ═══════════════════════════════════════════════════════════════════════════════

class _StatusRefreshThread(QThread):
  progress = pyqtSignal(str)
  result  = pyqtSignal(dict)  # {shipment_id: new_status}
  error  = pyqtSignal(str)

  def __init__(self, shipments: list, parent=None):
    super().__init__(parent)
    self.shipments = shipments # list of dicts with tracking_number, api_url, carrier_id

  def run(self):
    if not HAS_REQUESTS:
      self.error.emit("Module 'requests' non disponible."); return
    updates = {}
    for s in self.shipments:
      url  = s.get("api_tracking_url") or ""
      track = s.get("tracking_number") or ""
      sid  = s.get("shipment_id")
      if not (url and track and sid):
        continue
      try:
        self.progress.emit(f"Interrogation suivi {track}…")
        api_key = _key_get(s.get("carrier_id") or 0)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = _requests.get(
          url.rstrip("/") + f"/{track}",
          headers=headers, timeout=8,
        )
        if resp.ok:
          data = resp.json()
          st = data.get("status") or data.get("state") or "in_transit"
          updates[sid] = st
      except Exception as e:
        logger.debug("Tracking refresh %s: %s", track, e)
    self.result.emit(updates)


# ═══════════════════════════════════════════════════════════════════════════════
# CARRIER DIALOG — 3 onglets
# ═══════════════════════════════════════════════════════════════════════════════

class _CarrierDialog(QDialog):

  def __init__(self, parent=None, carrier: dict = None):
    super().__init__(parent)
    self.carrier = carrier or {}
    self.setWindowTitle("Modifier transporteur" if carrier else "Nouveau transporteur")
    self.setMinimumSize(620, 500)
    self.resize(680, 520)
    self.setModal(True)
    self.setStyleSheet(
      _dialog_qss()
      + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
      f"QTabWidget::pane{{background:{C['panel']};border:1px solid {C['border']};border-radius:6px;}}"
      f"QTabBar::tab{{background:{C['input']};color:{C['text2']};padding:8px 14px;"
      "border-top-left-radius:4px;border-top-right-radius:4px;margin-right:2px;font-size:12px;}"
      f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
      f"QTabBar::tab:hover{{background:{C['hover']};}}"
      + _INP + _GRP +
      f"QLabel{{background:transparent;color:{C['text']};}}"
      f"QCheckBox{{color:{C['text']};background:transparent;}}"
    )
    self._setup_ui()

  def _lbl(self, t):
    l = QLabel(t); l.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
    return l

  def _le(self, v="", ph=""):
    w = QLineEdit(str(v) if v else ""); w.setPlaceholderText(ph); return w

  def _spin(self, v, mn, mx, dec=2, pref="", suf=""):
    w = QDoubleSpinBox()
    w.setRange(mn, mx); w.setDecimals(dec); w.setValue(float(v or 0))
    if pref: w.setPrefix(pref)
    if suf: w.setSuffix(suf)
    return w

  def _setup_ui(self):
    lo = QVBoxLayout(self); lo.setContentsMargins(16, 16, 16, 12); lo.setSpacing(12)
    tabs = QTabWidget()
    tabs.addTab(self._tab_infos(),   " Infos ")
    tabs.addTab(self._tab_capacites(), " Capacités & Tarifs ")
    tabs.addTab(self._tab_perf(),   " Performance ")
    lo.addWidget(tabs, 1)
    row = QHBoxLayout(); row.addStretch()
    cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn"); cancel.setFixedHeight(34)
    cancel.clicked.connect(self.reject)
    save = QPushButton("Sauvegarder"); save.setObjectName("primaryBtn")
    save.setFixedHeight(34); save.setMinimumWidth(120); save.clicked.connect(self._on_save)
    row.addWidget(cancel); row.addWidget(save)
    lo.addLayout(row)

  # ── Tab 0 : Infos ─────────────────────────────────────────────────
  def _tab_infos(self) -> QWidget:
    w = QWidget(); fl = QFormLayout(w); fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
    c = self.carrier
    self._name  = self._le(c.get("name", ""),     "Nom du transporteur *")
    self._contact = self._le(c.get("contact_name", "") or "", "Nom du contact")
    self._phone  = self._le(c.get("phone", "") or "",  "+33 X XX XX XX XX")
    self._email  = self._le(c.get("email", "") or "",  "contact@transporteur.fr")
    self._website = self._le(c.get("website", "") or "", "https://…")
    self._notes  = QTextEdit()
    self._notes.setMaximumHeight(70)
    self._notes.setPlaceholderText("Notes internes, conditions…")
    self._notes.setText(c.get("notes") or "")
    self._notes.setStyleSheet(
      f"QTextEdit{{background:{C['input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:4px;}}"
    )
    for lbl, w2 in [
      ("Nom *", self._name), ("Contact", self._contact), ("Téléphone", self._phone),
      ("Email", self._email), ("Site web", self._website), ("Notes", self._notes),
    ]:
      fl.addRow(self._lbl(lbl), w2)
    return w

  # ── Tab 1 : Capacités & Tarifs ────────────────────────────────────
  def _tab_capacites(self) -> QWidget:
    w = QWidget(); fl = QFormLayout(w); fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
    c = self.carrier
    self._zones = _TagsInput(c.get("zones_covered") or "")

    saved_types = set((c.get("vehicle_types") or "").split(","))
    vtypes_grp = QGroupBox("Types de véhicules couverts")
    vtypes_grp.setStyleSheet(_GRP_QSS)
    vtypes_lo = QVBoxLayout(vtypes_grp)
    vtypes_lo.setContentsMargins(8, 12, 8, 6); vtypes_lo.setSpacing(4)
    row1 = QHBoxLayout(); row2 = QHBoxLayout()
    self._vtype_cbs: dict[str, QCheckBox] = {}
    for i, vt in enumerate(_VEHICLE_TYPES):
      cb = QCheckBox(vt); cb.setChecked(vt in saved_types)
      (row1 if i < 5 else row2).addWidget(cb)
      self._vtype_cbs[vt] = cb
    (row1 if len(_VEHICLE_TYPES) <= 5 else row2).addStretch()
    row1.addStretch(); vtypes_lo.addLayout(row1); vtypes_lo.addLayout(row2)

    self._cpkm = self._spin(c.get("cost_per_km", 0), 0, 99, pref="€ ", suf="/km")
    self._cpkg = self._spin(c.get("cost_per_kg", 0), 0, 99, pref="€ ", suf="/kg")
    self._cfixed= self._spin(c.get("cost_fixed", 0), 0, 9999, 0, pref="€ ", suf=" fixe")

    fl.addRow(self._lbl("Zones couvertes"), self._zones)
    fl.addRow(self._lbl("Types véhicules"), vtypes_grp)
    fl.addRow(self._lbl("Coût / km"),    self._cpkm)
    fl.addRow(self._lbl("Coût / kg"),    self._cpkg)
    fl.addRow(self._lbl("Coût fixe"),    self._cfixed)
    return w

  # ── Tab 2 : Performance ───────────────────────────────────────────
  def _tab_perf(self) -> QWidget:
    w = QWidget(); fl = QFormLayout(w); fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
    c = self.carrier

    rating_row = QHBoxLayout()
    self._rating = StarRating(int(round(float(c.get("rating", 3) or 3))), 5, read_only=False)
    rating_row.addWidget(self._rating); rating_row.addStretch()

    self._on_time = self._spin(c.get("on_time_rate", 0) or 0, 0, 100, 1, suf=" %")

    # Bouton recalcul automatique depuis carrier_shipments
    on_time_row = QHBoxLayout(); on_time_row.setSpacing(6)
    on_time_row.addWidget(self._on_time, 1)
    self._recalc_btn = QPushButton("↻ Recalculer")
    self._recalc_btn.setFixedHeight(30)
    self._recalc_btn.setToolTip(
      "Calcule automatiquement depuis les expéditions livrées\n"
      "(livrées à temps / total livrées × 100)"
    )
    self._recalc_btn.setStyleSheet(
      f"QPushButton{{background:{C['input']};color:{C['accent']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:2px 10px;font-size:11px;}}"
      f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
      f"QPushButton:disabled{{color:{C['text2']};border-color:{C['border']};}}"
    )
    cid_for_calc = c.get("id")
    self._recalc_btn.setEnabled(bool(cid_for_calc))
    if not cid_for_calc:
      self._recalc_btn.setToolTip("Disponible après la première sauvegarde du transporteur")
    self._recalc_btn.clicked.connect(self._recalc_on_time)
    on_time_row.addWidget(self._recalc_btn)

    self._api_url = self._le(c.get("api_tracking_url") or "", "https://api.transporteur.com/track")

    # API key — masked input, value from keyring
    self._api_key_changed = False
    api_key_row = QHBoxLayout()
    self._api_key_inp = QLineEdit()
    self._api_key_inp.setEchoMode(QLineEdit.EchoMode.Password)
    self._api_key_inp.setPlaceholderText("Clé API (stockée dans le trousseau OS)")
    cid = c.get("id")
    if cid:
      existing_key = _key_get(cid)
      if existing_key:
        self._api_key_inp.setPlaceholderText("**** Clé existante (laisser vide pour conserver)")
    self._api_key_inp.textChanged.connect(lambda _: setattr(self, "_api_key_changed", True))
    self._show_key_btn = QPushButton()
    self._show_key_btn.setFixedSize(30, 30)
    self._show_key_btn.setCheckable(True)
    self._show_key_btn.setToolTip("Afficher / masquer la clé API")
    apply_action_button(self._show_key_btn, "eye", "#7FA8C0", "transparent", "#1A2E4A", 16)
    self._show_key_btn.toggled.connect(
      lambda on: self._api_key_inp.setEchoMode(
        QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
      )
    )
    api_key_row.addWidget(self._api_key_inp, 1); api_key_row.addWidget(self._show_key_btn)

    keyring_note = QLabel(
      "La clé API est chiffrée dans le trousseau système (keyring OS)."
      if HAS_KEYRING else
      " Module 'keyring' non disponible — clé non persistée."
    )
    keyring_note.setStyleSheet(
      f"color:{C['text2'] if HAS_KEYRING else C['warning']};font-size:10px;background:transparent;"
    )

    fl.addRow(self._lbl("Note globale"),  rating_row)
    fl.addRow(self._lbl("Ponctualité %"), on_time_row)
    fl.addRow(self._lbl("URL API suivi"), self._api_url)
    fl.addRow(self._lbl("Clé API"),    api_key_row)
    fl.addRow("",             keyring_note)
    return w

  def _recalc_on_time(self):
    cid = self.carrier.get("id")
    if not cid:
      return
    conn = get_connection()
    row = conn.execute("""
      SELECT
        COUNT(CASE WHEN status='delivered'
                    AND (actual_delivery IS NULL
                         OR actual_delivery <= estimated_delivery) THEN 1 END) AS on_time,
        COUNT(CASE WHEN status='delivered' THEN 1 END) AS total_delivered
      FROM carrier_shipments
      WHERE carrier_id = ?
    """, (cid,)).fetchone()
    conn.close()
    total = row["total_delivered"] if row else 0
    if total == 0:
      QMessageBox.information(self, "Ponctualité",
        "Aucune expédition livrée trouvée pour ce transporteur.\n"
        "La valeur reste inchangée.")
      return
    rate = round(row["on_time"] * 100.0 / total)
    self._on_time.setValue(rate)
    QMessageBox.information(self, "Ponctualité recalculée",
      f"{row['on_time']} livraisons à temps sur {total} livrées → {rate} %")

  def _on_save(self):
    if not self._name.text().strip():
      QMessageBox.warning(self, "Validation", "Le nom est obligatoire."); return
    self.accept()

  def get_data(self) -> dict:
    vtypes = ",".join(vt for vt, cb in self._vtype_cbs.items() if cb.isChecked())
    return {
      "name":       self._name.text().strip(),
      "contact_name":   self._contact.text().strip(),
      "phone":      self._phone.text().strip(),
      "email":      self._email.text().strip(),
      "website":     self._website.text().strip(),
      "notes":      self._notes.toPlainText().strip(),
      "zones_covered":  self._zones.get_value(),
      "vehicle_types":  vtypes,
      "cost_per_km":   self._cpkm.value(),
      "cost_per_kg":   self._cpkg.value(),
      "cost_fixed":    self._cfixed.value(),
      "rating":      float(self._rating.get_rating()),
      "on_time_rate":   self._on_time.value(),
      "api_tracking_url": self._api_url.text().strip(),
      "_api_key":     self._api_key_inp.text() if self._api_key_changed else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SHIPMENT DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class _ShipmentDialog(QDialog):

  def __init__(self, parent=None, shipment: dict = None):
    super().__init__(parent)
    self.shipment = shipment or {}
    self.setWindowTitle("Modifier expédition" if shipment else "Nouvelle expédition")
    self.resize(520, 420)
    self.setModal(True)
    self.setStyleSheet(
      _dialog_qss()
      + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
      + _INP +
      f"QLabel{{background:transparent;color:{C['text']};}}"
    )
    conn = get_connection()
    self._carriers = conn.execute(
      "SELECT id, name FROM carriers WHERE archived=0 ORDER BY name"
    ).fetchall()
    self._orders  = conn.execute("""
      SELECT o.id, o.reference, c.name AS cname
      FROM orders o LEFT JOIN clients c ON c.id=o.client_id
      WHERE o.archived=0 AND o.status NOT IN ('delivered','cancelled')
      ORDER BY o.scheduled_date DESC
    """).fetchall()
    conn.close()
    self._setup_ui()

  def _lbl(self, t):
    l = QLabel(t); l.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
    return l

  def _setup_ui(self):
    lo = QVBoxLayout(self); fl = QFormLayout()
    fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
    s = self.shipment

    self._carrier_cb = QComboBox(); self._carrier_cb.setEditable(True)
    for cr in self._carriers:
      self._carrier_cb.addItem(cr["name"], cr["id"])
    if s.get("carrier_id"):
      idx = self._carrier_cb.findData(s["carrier_id"])
      if idx >= 0: self._carrier_cb.setCurrentIndex(idx)

    self._order_cb = QComboBox(); self._order_cb.setEditable(True)
    for or_ in self._orders:
      self._order_cb.addItem(f"{or_['reference']} – {or_['cname'] or ''}", or_["id"])
    if s.get("order_id"):
      idx = self._order_cb.findData(s["order_id"])
      if idx >= 0: self._order_cb.setCurrentIndex(idx)

    self._track  = QLineEdit(s.get("tracking_number") or "")
    self._track.setPlaceholderText("N° de suivi transporteur")
    self._status = QComboBox()
    for st in _SHIP_STATUSES:
      self._status.addItem(_SHIP_STATUS_LBL[st][0], st)
    cur_st = s.get("status") or "pending"
    idx = self._status.findData(cur_st)
    if idx >= 0: self._status.setCurrentIndex(idx)

    self._est_date = QDateEdit(); self._est_date.setCalendarPopup(True)
    self._est_date.setDisplayFormat("dd/MM/yyyy")
    est = s.get("estimated_delivery") or ""
    try:
      self._est_date.setDate(QDate.fromString(est[:10], "yyyy-MM-dd"))
    except Exception:
      self._est_date.setDate(QDate.currentDate().addDays(2))

    self._cost = QDoubleSpinBox(); self._cost.setRange(0, 99999); self._cost.setDecimals(2)
    self._cost.setPrefix("€ "); self._cost.setValue(float(s.get("cost") or 0))

    self._notes_e = QTextEdit()
    self._notes_e.setMaximumHeight(56)
    self._notes_e.setPlaceholderText("Notes…")
    self._notes_e.setText(s.get("notes") or "")
    self._notes_e.setStyleSheet(
      f"QTextEdit{{background:{C['input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:4px;}}"
    )

    fl.addRow(self._lbl("Transporteur *"),  self._carrier_cb)
    fl.addRow(self._lbl("Commande *"),    self._order_cb)
    fl.addRow(self._lbl("N° tracking"),    self._track)
    fl.addRow(self._lbl("Statut"),      self._status)
    fl.addRow(self._lbl("Livraison estimée"), self._est_date)
    fl.addRow(self._lbl("Coût total (€)"),  self._cost)
    fl.addRow(self._lbl("Notes"),       self._notes_e)
    lo.addLayout(fl); lo.addStretch()

    btn_row = QHBoxLayout(); btn_row.addStretch()
    cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn")
    cancel.setFixedHeight(32); cancel.clicked.connect(self.reject)
    save = QPushButton("Sauvegarder"); save.setObjectName("primaryBtn")
    save.setFixedHeight(32); save.setMinimumWidth(110); save.clicked.connect(self._on_save)
    btn_row.addWidget(cancel); btn_row.addWidget(save)
    lo.addLayout(btn_row)

  def _on_save(self):
    if not self._carrier_cb.currentData() or not self._order_cb.currentData():
      QMessageBox.warning(self, "Validation", "Transporteur et Commande sont obligatoires.")
      return
    self.accept()

  def get_data(self) -> dict:
    return {
      "carrier_id":    self._carrier_cb.currentData(),
      "order_id":     self._order_cb.currentData(),
      "tracking_number":  self._track.text().strip(),
      "status":      self._status.currentData(),
      "estimated_delivery":self._est_date.date().toString("yyyy-MM-dd"),
      "cost":       self._cost.value(),
      "notes":       self._notes_e.toPlainText().strip(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATION COMPARISON DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class _SimulationDialog(QDialog):
  """Compare flotte propre vs sous-traitance for selected orders."""

  def __init__(self, order_ids: list, parent=None):
    super().__init__(parent)
    self.order_ids = order_ids
    self.setWindowTitle(f"Simulation — {len(order_ids)} commande(s)")
    self.resize(800, 580)
    self.setStyleSheet(
      _dialog_qss()
      + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
      + _INP +
      f"QLabel{{background:transparent;color:{C['text']};}}"
    )
    self._carriers         = []
    self._computed_rows    = []
    self._current_carrier  = {}
    self._total_fleet      = 0.0
    self._total_carrier    = 0.0
    self._setup_ui()
    self._compute()

  def _setup_ui(self):
    lo = QVBoxLayout(self); lo.setContentsMargins(16, 12, 16, 12); lo.setSpacing(10)

    hdr = QHBoxLayout()
    t = QLabel("Comparaison Flotte propre vs Sous-traitance")
    t.setStyleSheet(f"color:{C['text']};font-size:15px;font-weight:700;background:transparent;")
    hdr.addWidget(t); hdr.addStretch()
    carrier_lbl = QLabel("Transporteur :")
    carrier_lbl.setStyleSheet(f"color:{C['text2']};background:transparent;")
    self._carrier_sel = QComboBox(); self._carrier_sel.setFixedWidth(200)
    self._carrier_sel.setStyleSheet(
      f"QComboBox{{background:{C['input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
    )
    conn = get_connection()
    self._carriers = conn.execute(
      "SELECT * FROM carriers WHERE archived=0 ORDER BY name"
    ).fetchall()
    conn.close()
    for cr in self._carriers:
      self._carrier_sel.addItem(cr["name"], cr["id"])
    self._carrier_sel.currentIndexChanged.connect(self._compute)
    hdr.addWidget(carrier_lbl); hdr.addWidget(self._carrier_sel)
    lo.addLayout(hdr)

    # Summary KPIs
    kpi_row = QHBoxLayout()
    self._kpi_fleet  = KPICard("Flotte propre",  "€ —", icon="")
    self._kpi_carrier = KPICard("Sous-traitance",  "€ —", icon="")
    self._kpi_saving = KPICard("Économie estimée", "€ —", icon="")
    for k in [self._kpi_fleet, self._kpi_carrier, self._kpi_saving]:
      kpi_row.addWidget(k)
    lo.addLayout(kpi_row)

    # Comparison table
    self._cmp_table = QTableWidget()
    self._cmp_table.setColumnCount(6)
    self._cmp_table.setHorizontalHeaderLabels([
      "Commande", "Client", "kg", "Dist. est. (km)",
      "Coût flotte (€)", "Coût transport. (€)",
    ])
    self._cmp_table.horizontalHeader().setSectionResizeMode(
      0, QHeaderView.ResizeMode.Fixed); self._cmp_table.setColumnWidth(0, 130)
    self._cmp_table.horizontalHeader().setSectionResizeMode(
      1, QHeaderView.ResizeMode.Stretch)
    self._cmp_table.verticalHeader().setVisible(False)
    self._cmp_table.verticalHeader().setDefaultSectionSize(30)
    self._cmp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self._cmp_table.setMaximumHeight(220)
    self._cmp_table.setStyleSheet(_TBL)
    lo.addWidget(self._cmp_table)

    # Recommendation
    self._rec_lbl = QLabel("")
    self._rec_lbl.setWordWrap(True)
    self._rec_lbl.setStyleSheet(
      f"color:{C['text']};font-size:13px;font-weight:600;background:{C['panel']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:10px;"
    )
    lo.addWidget(self._rec_lbl)

    # Chart
    self._chart_container = QFrame()
    self._chart_container.setMinimumHeight(200)
    self._chart_lo = QVBoxLayout(self._chart_container)
    self._chart_lo.setContentsMargins(0, 0, 0, 0)
    lo.addWidget(self._chart_container, 1)

    # Action buttons
    action_row = QHBoxLayout(); action_row.setSpacing(8)
    self._btn_fleet = QPushButton("✓  Assigner à ma flotte")
    self._btn_fleet.setObjectName("primaryBtn")
    self._btn_fleet.setFixedHeight(36)
    self._btn_fleet.clicked.connect(self._assign_fleet)
    self._btn_subcontract = QPushButton("🚛  Sous-traiter")
    self._btn_subcontract.setObjectName("secondaryBtn")
    self._btn_subcontract.setFixedHeight(36)
    self._btn_subcontract.clicked.connect(self._assign_subcontract)
    action_row.addWidget(self._btn_fleet)
    action_row.addWidget(self._btn_subcontract)
    action_row.addStretch()
    close_btn = QPushButton("Fermer"); close_btn.setObjectName("ghostBtn")
    close_btn.setFixedHeight(36); close_btn.clicked.connect(self.accept)
    action_row.addWidget(close_btn)
    lo.addLayout(action_row)

  def _compute(self):
    cid = self._carrier_sel.currentData()
    carrier = next((dict(c) for c in self._carriers if c["id"] == cid), {})

    try:
      conn = get_connection()
      depot = conn.execute("SELECT latitude, longitude FROM depots LIMIT 1").fetchone()
      dep_lat = float(depot["latitude"]) if depot else 33.57
      dep_lon = float(depot["longitude"]) if depot else -7.59
      avg_cpkm = float(conn.execute(
        "SELECT COALESCE(AVG(cost_per_km),1.2) FROM vehicles WHERE cost_per_km>0"
      ).fetchone()[0] or 1.2)

      orders_data = []
      for oid in self.order_ids:
        row = conn.execute("""
          SELECT o.*, c.name AS cname, c.latitude, c.longitude
          FROM orders o LEFT JOIN clients c ON c.id=o.client_id
          WHERE o.id=?
        """, (oid,)).fetchone()
        if row: orders_data.append(dict(row))
      conn.close()
    except Exception:
      return

    rows = []
    total_fleet = 0.0; total_carrier = 0.0
    for o in orders_data:
      dist = _haversine_km(dep_lat, dep_lon, o.get("latitude") or dep_lat, o.get("longitude") or dep_lon)
      dist = max(dist, 2.0) * 2 # round-trip estimate
      kg = float(o.get("quantity_kg") or 0)
      fleet_cost = dist * avg_cpkm
      c_cpkm = float(carrier.get("cost_per_km") or 0)
      c_cpkg = float(carrier.get("cost_per_kg") or 0)
      c_fixed = float(carrier.get("cost_fixed") or 0)
      carrier_cost = c_fixed + dist * c_cpkm + kg * c_cpkg if carrier else 0.0
      total_fleet  += fleet_cost
      total_carrier += carrier_cost
      rows.append({
        "ref":   o.get("reference") or f"#{o['id']}",
        "client": o.get("cname") or "",
        "kg":   kg,
        "dist":  dist,
        "fleet":  fleet_cost,
        "carrier": carrier_cost,
      })

    self._fill_cmp_table(rows)
    # saving > 0  →  fleet coûte PLUS que le transporteur → sous-traiter est rentable
    # saving < 0  →  fleet coûte MOINS que le transporteur → garder la flotte propre
    saving = total_fleet - total_carrier
    self._kpi_fleet.set_value(f"€ {total_fleet:.0f}")
    self._kpi_carrier.set_value(f"€ {total_carrier:.0f}" if carrier else "€ —")
    self._kpi_saving.set_value(f"€ {abs(saving):.0f}" if carrier else "€ —")

    if carrier:
      if saving > 0:
        # Flotte plus chère → sous-traiter est rentable
        self._rec_lbl.setText(
          f" Recommandation : Sous-traiter à {carrier.get('name','')} est "
          f"plus économique de € {saving:.0f} sur ces {len(rows)} commandes."
        )
        self._rec_lbl.setStyleSheet(
          f"color:{C['warning']};font-size:13px;font-weight:600;"
          f"background:{C['panel']};border:1px solid {C['border']};border-radius:5px;padding:10px;"
        )
      else:
        # Flotte moins chère → garder la flotte propre
        self._rec_lbl.setText(
          f" Recommandation : Votre flotte propre est plus économique de "
          f"€ {abs(saving):.0f} — conserver la livraison en interne."
        )
        self._rec_lbl.setStyleSheet(
          f"color:{C['success']};font-size:13px;font-weight:600;"
          f"background:{C['panel']};border:1px solid {C['border']};border-radius:5px;padding:10px;"
        )
    else:
      self._rec_lbl.setText("Sélectionnez un transporteur pour comparer.")

    # Mémoriser pour les boutons d'action
    self._computed_rows    = rows
    self._current_carrier  = carrier
    self._total_fleet      = total_fleet
    self._total_carrier    = total_carrier
    # Mettre à jour le libellé du bouton sous-traiter
    name = carrier.get("name", "") if carrier else ""
    self._btn_subcontract.setText(f"🚛  Sous-traiter à {name}" if name else "🚛  Sous-traiter")
    self._draw_pie(total_fleet, total_carrier, name)

  # ── Actions directes depuis la simulation ─────────────────────────────
  def _assign_fleet(self):
    """Ouvre un mini-dialogue pour affecter toutes les commandes à un véhicule + chauffeur."""
    total_kg = sum(float(r.get("kg") or 0) for r in getattr(self, "_computed_rows", []))

    conn = get_connection()
    vehicles = conn.execute(
      "SELECT id, registration, brand, capacity_kg FROM vehicles "
      "WHERE LOWER(COALESCE(status,'')) NOT IN ('hors_service','archived') ORDER BY registration"
    ).fetchall()
    drivers = conn.execute(
      "SELECT id, first_name, last_name FROM drivers ORDER BY last_name"
    ).fetchall()
    conn.close()

    dlg = QDialog(self)
    dlg.setWindowTitle("Assigner à la flotte")
    dlg.setFixedWidth(420)
    dlg.setModal(True)
    dlg.setStyleSheet(
      _dialog_qss()
      + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
      + _INP + f"QLabel{{background:transparent;color:{C['text']};}}"
    )
    dlo = QVBoxLayout(dlg); dlo.setSpacing(12); dlo.setContentsMargins(20, 16, 20, 16)

    info = QLabel(f"{len(self.order_ids)} commande(s) — total {total_kg:.0f} kg")
    info.setStyleSheet(f"color:{C['text2']};font-size:11px;")
    dlo.addWidget(info)

    fl = QFormLayout(); fl.setSpacing(10)
    lbl2 = lambda t: (lambda l: (l.setStyleSheet(f"color:{C['text2']};font-size:11px;"), l)[1])(QLabel(t))

    v_combo = QComboBox(); v_combo.setEditable(True)
    v_combo.addItem("— Choisir un véhicule", None)
    for v in vehicles:
      cap = float(v.get("capacity_kg") or 0)
      v_combo.addItem(
        f"{v['registration']} · {v.get('brand','')}  ({cap:.0f} kg)",
        int(v["id"])
      )

    cap_lbl = QLabel("")
    cap_lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;")

    def _on_vehicle_changed():
      vid = v_combo.currentData()
      cap = next((float(v.get("capacity_kg") or 0) for v in vehicles if int(v["id"]) == vid), 0) if vid else 0
      if cap > 0:
        if total_kg > cap:
          cap_lbl.setText(f"⚠  {total_kg:.0f} kg > capacité {cap:.0f} kg")
          cap_lbl.setStyleSheet(f"color:{C['warning']};font-size:11px;")
        else:
          cap_lbl.setText(f"✓  {total_kg:.0f} kg / {cap:.0f} kg")
          cap_lbl.setStyleSheet(f"color:{C['success']};font-size:11px;")
      else:
        cap_lbl.setText("")

    v_combo.currentIndexChanged.connect(_on_vehicle_changed)

    d_combo = QComboBox(); d_combo.setEditable(True)
    d_combo.addItem("— Chauffeur (optionnel)", None)
    for d in drivers:
      d_combo.addItem(f"{d.get('first_name','')} {d.get('last_name','')}".strip(), int(d["id"]))

    fl.addRow(lbl2("Véhicule *"), v_combo)
    fl.addRow("", cap_lbl)
    fl.addRow(lbl2("Chauffeur"), d_combo)
    dlo.addLayout(fl)

    btn_row = QHBoxLayout(); btn_row.addStretch()
    cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn"); cancel.clicked.connect(dlg.reject)
    confirm = QPushButton("✓ Confirmer l'affectation"); confirm.setObjectName("primaryBtn"); confirm.clicked.connect(dlg.accept)
    btn_row.addWidget(cancel); btn_row.addWidget(confirm)
    dlo.addLayout(btn_row)

    if dlg.exec() != QDialog.DialogCode.Accepted:
      return
    vid = v_combo.currentData()
    did = d_combo.currentData()
    if not vid:
      QMessageBox.warning(self, "Validation", "Veuillez choisir un véhicule."); return

    conn = get_connection()
    try:
      conn.execute("ALTER TABLE orders ADD COLUMN carrier_id INTEGER")
    except Exception:
      pass
    for oid in self.order_ids:
      conn.execute(
        "UPDATE orders SET status='assigned', vehicle_id=?, driver_id=?, carrier_id=NULL WHERE id=?",
        (vid, did, oid)
      )
    conn.commit(); conn.close()
    log_action("ORDER_BATCH_ASSIGN",
      f"{len(self.order_ids)} commandes assignées au véhicule #{vid}")
    main_win = self.parent()
    self.accept()
    show_toast(main_win.window() if main_win else None,
      f"{len(self.order_ids)} commande(s) assignée(s) à la flotte", "success")

  def _assign_subcontract(self):
    """Crée les expéditions sous-traitées pour toutes les commandes et ferme la simulation."""
    carrier = getattr(self, "_current_carrier", {})
    if not carrier:
      QMessageBox.warning(self, "Validation", "Sélectionnez un transporteur d'abord."); return

    if not ConfirmDialog.ask(self,
      "Confirmer la sous-traitance",
      f"Sous-traiter {len(self.order_ids)} commande(s) à {carrier['name']} ?\n"
      "Les statuts seront mis à jour dans la page Commandes.", "info"):
      return

    cid = int(carrier["id"])
    conn = get_connection()
    try:
      conn.execute("ALTER TABLE orders ADD COLUMN carrier_id INTEGER")
    except Exception:
      pass
    created = 0
    for oid in self.order_ids:
      already = conn.execute(
        "SELECT id FROM carrier_shipments WHERE carrier_id=? AND order_id=?", (cid, oid)
      ).fetchone()
      if not already:
        conn.execute("""
          INSERT INTO carrier_shipments
          (carrier_id, order_id, status, created_at)
          VALUES (?, ?, 'pending', datetime('now'))
        """, (cid, oid))
        created += 1
      conn.execute(
        "UPDATE orders SET status='assigned', carrier_id=?, vehicle_id=NULL, driver_id=NULL WHERE id=?",
        (cid, oid)
      )
    conn.commit(); conn.close()
    log_action("ORDER_BATCH_SUBCONTRACT",
      f"{len(self.order_ids)} commandes sous-traitées → {carrier['name']}")
    main_win = self.parent()
    self.accept()
    show_toast(main_win.window() if main_win else None,
      f"{created} expédition(s) créée(s) chez {carrier['name']}", "success")

  def _fill_cmp_table(self, rows: list):
    self._cmp_table.setRowCount(len(rows))
    for r, row in enumerate(rows):
      def _it(v, color=None):
        it = QTableWidgetItem(str(v))
        it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
        if color: it.setForeground(QColor(color))
        return it
      self._cmp_table.setItem(r, 0, _it(row["ref"]))
      self._cmp_table.setItem(r, 1, _it(row["client"]))
      self._cmp_table.setItem(r, 2, _it(f"{row['kg']:.0f}"))
      self._cmp_table.setItem(r, 3, _it(f"{row['dist']:.1f}"))
      fc, cc = row["fleet"], row["carrier"]
      fleet_color = C["success"] if fc <= cc else C["text"]
      carr_color = C["success"] if cc < fc else C["text"]
      self._cmp_table.setItem(r, 4, _it(f"{fc:.2f}", fleet_color))
      self._cmp_table.setItem(r, 5, _it(f"{cc:.2f}" if cc else "—", carr_color))

  def _draw_pie(self, fleet: float, carrier: float, carrier_name: str):
    for i in reversed(range(self._chart_lo.count())):
      w = self._chart_lo.itemAt(i).widget()
      if w: w.deleteLater()
    if not HAS_MPL or fleet + carrier == 0: return
    try:
      sizes = [fleet, carrier] if carrier > 0 else [fleet, 0.001]
      labels = [f"Flotte propre\n€ {fleet:.0f}", f"{carrier_name or 'Transporteur'}\n€ {carrier:.0f}"]
      colors = ["#00D4FF", "#FFB800"]
      fig, ax = plt.subplots(figsize=(5, 3))
      fig.patch.set_facecolor("#112240"); ax.set_facecolor("#112240")
      wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, autopct="%1.0f%%",
        startangle=140, textprops={"color": "#E8F4FD", "fontsize": 10},
      )
      for at in autotexts: at.set_color("#0D1B2A"); at.set_fontweight("bold")
      fig.tight_layout(pad=0.3)
      canvas = FigCanvas(fig); canvas.setMinimumHeight(200)
      self._chart_lo.addWidget(canvas)
      plt.close(fig)
    except Exception as e:
      logger.debug("Simulation pie error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# CARRIERS WIDGET — Page principale (4 onglets)
# ═══════════════════════════════════════════════════════════════════════════════

class CarriersWidget(QWidget):

  def __init__(self, main_window):
    super().__init__()
    self.main_window = main_window
    self._threads: list = []
    self._sim_order_ids: list = []
    self._setup_ui()

  def _setup_ui(self):
    root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
    self._tabs = QTabWidget()
    self._tabs.setUsesScrollButtons(True)
    self._tabs.setStyleSheet(
      f"QTabWidget::pane{{background:{C['bg']};border:none;}}"
      f"QTabBar::tab{{background:{C['panel']};color:{C['text2']};padding:10px 18px;"
      "border-top-left-radius:6px;border-top-right-radius:6px;margin-right:2px;font-size:13px;font-weight:500;}"
      f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
      f"QTabBar::tab:hover{{background:{C['hover']};color:{C['text']};}}"
    )
    self._tabs.addTab(self._build_tab_carriers(), " Transporteurs")
    self._tabs.addTab(self._build_tab_shipments(), " Expéditions sous-traitées")
    self._tabs.addTab(self._build_tab_sim(),    " Simuler (flotte vs S/T)")
    self._tabs.addTab(self._build_tab_eval(),   " Évaluation transporteurs")
    self._tabs.currentChanged.connect(self._on_tab)
    root.addWidget(self._tabs)

  def retranslate_ui(self, lang: str):
    from app.i18n import tr
    _keys = [
        "carriers.tab.carriers", "carriers.tab.shipments",
        "carriers.tab.sim",      "carriers.tab.eval",
    ]
    for i, key in enumerate(_keys):
        if i < self._tabs.count():
            self._tabs.setTabText(i, f" {tr(key, lang)}")
    if hasattr(self, "_car_section_header"):
        self._car_section_header.set_title(tr("section.carriers", lang))

  def refresh_data(self):
    self._refresh_carriers()

  def _on_tab(self, idx: int):
    if idx == 0: self._refresh_carriers()
    elif idx == 1: self._refresh_shipments()
    elif idx == 2: self._refresh_sim()
    elif idx == 3: self._refresh_eval()

  # ══════════════════════════════════════════════════════════════════
  # TAB 0 — TRANSPORTEURS
  # ══════════════════════════════════════════════════════════════════

  def _build_tab_carriers(self) -> QWidget:
    w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(20, 14, 20, 18); lo.setSpacing(10)
    self._car_section_header = SectionHeader(
      title="Transporteurs partenaires",
      subtitle="Gestion des sous-traitants, tarifs et performance",
      action_text="+ Ajouter transporteur",
      action_callback=self._add_carrier,
    )
    lo.addWidget(self._car_section_header)
    tb = QHBoxLayout()
    self._car_search = SearchBar(placeholder="Nom, zone, type…"); self._car_search.setMaximumWidth(250)
    self._car_search.search_changed.connect(lambda _: self._refresh_carriers())
    tb.addWidget(self._car_search)
    sim_btn = QPushButton("Simuler coûts…")
    sim_btn.setObjectName("secondaryBtn")
    sim_btn.setToolTip("Ouvre l’onglet de simulation : comparer flotte propre vs sous-traitance")
    sim_btn.setFixedHeight(30)
    sim_btn.clicked.connect(lambda: self._tabs.setCurrentIndex(2))
    tb.addWidget(sim_btn)
    tb.addStretch()
    self._car_count = QLabel("0 transporteurs")
    self._car_count.setStyleSheet(f"color:{C['text2']};font-size:12px;")
    tb.addWidget(self._car_count)
    tb.addSpacing(4)
    _hb = QPushButton()
    _hb.setFixedSize(30, 30)
    _hb.setToolTip("Aide — Transporteurs")
    _hb.setCursor(Qt.CursorShape.PointingHandCursor)
    apply_action_button(_hb, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
    _hb.clicked.connect(lambda: show_help(self, "carriers"))
    tb.addWidget(_hb)
    lo.addLayout(tb)

    self._car_table = QTableWidget(); self._car_table.setColumnCount(8)
    self._car_table.setHorizontalHeaderLabels([
      "Nom", "Contact", "Zones", "Types", "€/km", "Note ", "Ponctualité %", "Actions",
    ])
    hdr = self._car_table.horizontalHeader()
    hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    for col, w2 in [(1,110),(3,130),(4,55),(5,75),(6,90),(7,100)]:
      self._car_table.setColumnWidth(col, w2)
    self._car_table.verticalHeader().setVisible(False)
    self._car_table.verticalHeader().setDefaultSectionSize(38)
    self._car_table.setAlternatingRowColors(True)
    self._car_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self._car_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self._car_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self._car_table.customContextMenuRequested.connect(self._car_ctx_menu)
    self._car_table.doubleClicked.connect(
      lambda idx: self._edit_carrier(
        self._car_table.item(idx.row(), 0).data(Qt.ItemDataRole.UserRole)
      ) if self._car_table.item(idx.row(), 0) else None
    )
    self._car_table.setStyleSheet(_TBL)
    lo.addWidget(self._car_table, 1)
    return w

  def _refresh_carriers(self):
    search = ""
    try:
      search = self._car_search.get_text().strip()
    except Exception:
      pass
    conn = get_connection()
    if search:
      s = f"%{search}%"
      rows = conn.execute("""
        SELECT * FROM carriers WHERE archived=0
        AND (name LIKE ? OR COALESCE(zones_covered,'') LIKE ? OR COALESCE(vehicle_types,'') LIKE ? )
        ORDER BY name
      """, [s, s, s]).fetchall()
    else:
      rows = conn.execute("SELECT * FROM carriers WHERE archived=0 ORDER BY name").fetchall()
    conn.close()

    self._car_count.setText(f"{len(rows)} transporteur{'s' if len(rows)!=1 else ''}")
    self._car_table.setRowCount(len(rows))
    for r, row in enumerate(rows):
      def _it(v, color=None):
        it = QTableWidgetItem(str(v or ""))
        it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
        if color: it.setForeground(QColor(color))
        return it

      n_it = _it(row["name"])
      n_it.setData(Qt.ItemDataRole.UserRole, row["id"])
      n_it.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
      self._car_table.setItem(r, 0, n_it)
      self._car_table.setItem(r, 1, _it(row.get("contact_name") or ""))
      zones_full = (row.get("zones_covered") or "").replace(",", ", ")
      zones = (zones_full[:35] + "…") if len(zones_full) > 35 else zones_full
      self._car_table.setItem(r, 2, _it(zones, C["text2"] if zones else None))
      vtypes_full = (row.get("vehicle_types") or "").replace(",", ", ")
      vtypes = (vtypes_full[:30] + "…") if len(vtypes_full) > 30 else vtypes_full
      self._car_table.setItem(r, 3, _it(vtypes))
      self._car_table.setItem(r, 4, _it(f"{float(row.get('cost_per_km') or 0):.2f}"))

      # Note (étoiles affichées)
      try:
        r_stars = max(1, min(5, int(round(float(row.get("rating") or 3)))))
      except (TypeError, ValueError):
        r_stars = 3
      stars = "★" * r_stars + "☆" * (5 - r_stars)
      self._car_table.setItem(r, 5, _it(stars, C["warning"]))

      otr = row.get("on_time_rate")
      otr_str = f"{float(otr):.0f}%" if otr is not None else "—"
      otr_color = (C["success"] if float(otr or 0) >= 90
             else C["warning"] if float(otr or 0) >= 70
             else C["danger"]) if otr is not None else C["text2"]
      self._car_table.setItem(r, 6, _it(otr_str, otr_color))

      self._car_table.setCellWidget(r, 7, self._car_actions(row["id"]))

  def _car_actions(self, cid: int) -> QWidget:
    w = QWidget(); lo = QHBoxLayout(w); lo.setContentsMargins(3,1,3,1); lo.setSpacing(3)
    for lucide_key, tip, fn, fg, hbg in [
      ("pencil", "Modifier", lambda _, i=cid: self._edit_carrier(i), C["accent"], C["panel"]),
      ("package", "Expéditions",lambda _,i=cid: self._filter_shipments_by_carrier(i), C["warning"], C["panel"]),
      ("trash-2", "Supprimer", lambda _,i=cid: self._delete_carrier(i), C["danger"], "#3A1020"),
    ]:
      btn = QPushButton(); btn.setFixedSize(28, 28)
      btn.setToolTip(tip); btn.setCursor(Qt.CursorShape.PointingHandCursor)
      apply_action_button(btn, lucide_key, fg, C["hover"], hbg, icon_px=16)
      btn.clicked.connect(fn); lo.addWidget(btn)
    return w

  def _car_ctx_menu(self, pos):
    row = self._car_table.rowAt(pos.y())
    if row < 0: return
    it = self._car_table.item(row, 0)
    cid = it.data(Qt.ItemDataRole.UserRole) if it else None
    if not cid: return
    menu = QMenu(self)
    menu.setStyleSheet(
      f"QMenu{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};"
      "border-radius:6px;padding:4px;}}"
      f"QMenu::item{{padding:6px 18px;border-radius:4px;}}"
      f"QMenu::item:selected{{background:{C['hover']};}}"
    )
    for label, fn in [
      (" Modifier",  lambda: self._edit_carrier(cid)),
      (" Expéditions", lambda: self._filter_shipments_by_carrier(cid)),
      (None, None),
      (" Supprimer",  lambda: self._delete_carrier(cid)),
    ]:
      if label is None: menu.addSeparator()
      else:
        act = QAction(label, self); act.triggered.connect(fn); menu.addAction(act)
    menu.exec(self._car_table.viewport().mapToGlobal(pos))

  # ── Carrier CRUD ──────────────────────────────────────────────────

  def _add_carrier(self):
    dlg = _CarrierDialog(self)
    if dlg.exec() != QDialog.DialogCode.Accepted: return
    data = dlg.get_data()
    conn = get_connection()
    cur = conn.execute("""
      INSERT INTO carriers
      (name,contact_name,phone,email,website,notes,zones_covered,
       vehicle_types,cost_per_km,cost_per_kg,cost_fixed,rating,
       on_time_rate,api_tracking_url)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
      data["name"], data["contact_name"], data["phone"], data["email"],
      data["website"], data["notes"], data["zones_covered"], data["vehicle_types"],
      data["cost_per_km"], data["cost_per_kg"], data["cost_fixed"], data["rating"],
      data["on_time_rate"], data["api_tracking_url"],
    ))
    new_id = cur.lastrowid; conn.commit(); conn.close()
    if data.get("_api_key"):
      _key_set(new_id, data["_api_key"])
    log_action("CARRIER_CREATE", f"Transporteur '{data['name']}' créé")
    show_toast(self.window(), f"Transporteur '{data['name']}' créé", "success")
    self._refresh_carriers()

  def _edit_carrier(self, cid: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM carriers WHERE id= ?", (cid,)).fetchone()
    conn.close()
    if not row: return
    dlg = _CarrierDialog(self, dict(row))
    if dlg.exec() != QDialog.DialogCode.Accepted: return
    data = dlg.get_data()
    conn = get_connection()
    conn.execute("""
      UPDATE carriers SET
      name= ?,contact_name= ?,phone= ?,email= ?,website= ?,notes= ?,
      zones_covered= ?,vehicle_types= ?,cost_per_km= ?,cost_per_kg= ?,
      cost_fixed= ?,rating= ?,on_time_rate= ?,api_tracking_url= ? WHERE id=?
    """, (
      data["name"], data["contact_name"], data["phone"], data["email"],
      data["website"], data["notes"], data["zones_covered"], data["vehicle_types"],
      data["cost_per_km"], data["cost_per_kg"], data["cost_fixed"], data["rating"],
      data["on_time_rate"], data["api_tracking_url"], cid,
    ))
    conn.commit(); conn.close()
    if data.get("_api_key"):
      _key_set(cid, data["_api_key"])
    log_action("CARRIER_UPDATE", f"Transporteur #{cid} modifié")
    show_toast(self.window(), "Transporteur mis à jour", "success")
    self._refresh_carriers()

  def _delete_carrier(self, cid: int):
    if not ConfirmDialog.ask(self, "Supprimer", "Supprimer ce transporteur ", "danger"): return
    conn = get_connection()
    conn.execute("UPDATE carriers SET archived=1 WHERE id= ?", (cid,))
    conn.commit(); conn.close()
    _key_del(cid)
    log_action("CARRIER_DELETE", f"Transporteur #{cid} supprimé")
    show_toast(self.window(), "Transporteur supprimé", "info")
    self._refresh_carriers()

  # ══════════════════════════════════════════════════════════════════
  # TAB 1 — EXPÉDITIONS SOUS-TRAITÉES
  # ══════════════════════════════════════════════════════════════════

  def _build_tab_shipments(self) -> QWidget:
    w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(20, 14, 20, 18); lo.setSpacing(10)
    lo.addWidget(SectionHeader(
      title="Expéditions sous-traitées",
      subtitle="Suivi des livraisons confiées aux transporteurs partenaires",
      action_text="+ Nouvelle expédition",
      action_callback=self._add_shipment,
    ))
    tb = QHBoxLayout(); tb.setSpacing(6)
    self._shp_car_filter = QComboBox(); self._shp_car_filter.setFixedWidth(200)
    self._shp_car_filter.setStyleSheet(
      f"QComboBox{{background:{C['input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
    )
    self._shp_car_filter.currentIndexChanged.connect(lambda _: self._refresh_shipments())
    tb.addWidget(QLabel("Transporteur :")); tb.addWidget(self._shp_car_filter)

    refresh_btn = QPushButton(" Rafraîchir statuts")
    refresh_btn.setFixedHeight(30)
    refresh_btn.setStyleSheet(
      f"QPushButton{{background:{C['input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:4px 12px;}}"
      f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
    )
    refresh_btn.clicked.connect(self._refresh_tracking)
    tb.addWidget(refresh_btn)
    tb.addStretch()
    self._shp_count = QLabel("0 expéditions")
    self._shp_count.setStyleSheet(f"color:{C['text2']};font-size:12px;")
    tb.addWidget(self._shp_count)
    lo.addLayout(tb)

    self._shp_progress = QProgressBar(); self._shp_progress.setVisible(False)
    self._shp_progress.setFixedHeight(4)
    self._shp_progress.setTextVisible(False)
    self._shp_progress.setStyleSheet(
      f"QProgressBar{{background:{C['panel']};border:none;border-radius:2px;}}"
      f"QProgressBar::chunk{{background:{C['accent']};border-radius:2px;}}"
    )
    lo.addWidget(self._shp_progress)

    self._shp_table = QTableWidget(); self._shp_table.setColumnCount(8)
    self._shp_table.setHorizontalHeaderLabels([
      "N° Tracking", "Commande", "Transporteur", "Statut",
      "Livraison est.", "Coût (€)", "Créé le", "Actions",
    ])
    hdr = self._shp_table.horizontalHeader()
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    for col, w2 in [(0,130),(3,110),(4,95),(5,80),(6,85),(7,80)]:
      self._shp_table.setColumnWidth(col, w2)
    self._shp_table.verticalHeader().setVisible(False)
    self._shp_table.verticalHeader().setDefaultSectionSize(38)
    self._shp_table.setAlternatingRowColors(True)
    self._shp_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self._shp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self._shp_table.doubleClicked.connect(
      lambda idx: self._edit_shipment(
        self._shp_table.item(idx.row(), 0).data(Qt.ItemDataRole.UserRole)
      ) if self._shp_table.item(idx.row(), 0) else None
    )
    self._shp_table.setStyleSheet(_TBL)
    lo.addWidget(self._shp_table, 1)
    return w

  def _filter_shipments_by_carrier(self, cid: int):
    self._tabs.setCurrentIndex(1)
    for i in range(self._shp_car_filter.count()):
      if self._shp_car_filter.itemData(i) == cid:
        self._shp_car_filter.setCurrentIndex(i); return

  def _refresh_shipments(self):
    # Reload carrier filter combo
    cur = self._shp_car_filter.currentData()
    self._shp_car_filter.blockSignals(True)
    self._shp_car_filter.clear()
    self._shp_car_filter.addItem("— Tous les transporteurs", None)
    try:
      conn = get_connection()
      cars = conn.execute("SELECT id, name FROM carriers WHERE archived=0 ORDER BY name").fetchall()
      for c in cars: self._shp_car_filter.addItem(c["name"], c["id"])
      conn.close()
    except Exception:
      pass
    if cur:
      for i in range(self._shp_car_filter.count()):
        if self._shp_car_filter.itemData(i) == cur:
          self._shp_car_filter.setCurrentIndex(i); break
    self._shp_car_filter.blockSignals(False)

    cid = self._shp_car_filter.currentData()
    conn = get_connection()
    if cid:
      rows = conn.execute("""
        SELECT cs.*, c.name AS carrier_name, c.api_tracking_url, o.reference
        FROM carrier_shipments cs
        JOIN carriers c ON c.id=cs.carrier_id
        LEFT JOIN orders o ON o.id=cs.order_id
        WHERE cs.carrier_id= ? ORDER BY cs.created_at DESC
      """, (cid,)).fetchall()
    else:
      rows = conn.execute("""
        SELECT cs.*, c.name AS carrier_name, c.api_tracking_url, o.reference
        FROM carrier_shipments cs
        JOIN carriers c ON c.id=cs.carrier_id
        LEFT JOIN orders o ON o.id=cs.order_id
        ORDER BY cs.created_at DESC
      """).fetchall()
    conn.close()
    self._shp_rows_cache = [dict(r) for r in rows]
    self._shp_count.setText(f"{len(rows)} expédition{'s' if len(rows)!=1 else ''}")
    self._fill_shp_table(rows)

  def _fill_shp_table(self, rows):
    self._shp_table.setRowCount(len(rows))
    for r, row in enumerate(rows):
      def _it(v, color=None):
        it = QTableWidgetItem(str(v or ""))
        it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
        if color: it.setForeground(QColor(color))
        return it
      track_it = _it(row.get("tracking_number") or "—")
      track_it.setData(Qt.ItemDataRole.UserRole, row["id"])
      track_it.setFont(QFont("Consolas", 9))
      self._shp_table.setItem(r, 0, track_it)
      self._shp_table.setItem(r, 1, _it(row.get("reference") or f"Order #{row.get('order_id','')}"))
      self._shp_table.setItem(r, 2, _it(row.get("carrier_name") or ""))
      st = row.get("status") or "pending"
      st_lbl, st_var = _SHIP_STATUS_LBL.get(st, (st, "default"))
      badge = StatusBadge(st_lbl, st_var)
      cw = QWidget(); cl = QHBoxLayout(cw); cl.setContentsMargins(4,2,4,2)
      cl.addWidget(badge); cl.addStretch()
      self._shp_table.setCellWidget(r, 3, cw)
      self._shp_table.setItem(r, 4, _it((row.get("estimated_delivery") or "")[:10]))
      self._shp_table.setItem(r, 5, _it(f"{float(row.get('cost') or 0):.2f}"))
      self._shp_table.setItem(r, 6, _it((row.get("created_at") or "")[:10]))
      self._shp_table.setCellWidget(r, 7, self._shp_actions(row["id"]))

  def _shp_actions(self, sid: int) -> QWidget:
    w = QWidget(); lo = QHBoxLayout(w); lo.setContentsMargins(3,1,3,1); lo.setSpacing(3)
    for lucide_key, tip, fn, fg, hbg in [
      ("pencil", "Modifier", lambda _, i=sid: self._edit_shipment(i), C["accent"], C["panel"]),
      ("trash-2", "Supprimer", lambda _, i=sid: self._delete_shipment(i), C["danger"], "#3A1020"),
    ]:
      btn = QPushButton(); btn.setFixedSize(28, 28)
      btn.setToolTip(tip); btn.setCursor(Qt.CursorShape.PointingHandCursor)
      apply_action_button(btn, lucide_key, fg, C["hover"], hbg, icon_px=16)
      btn.clicked.connect(fn); lo.addWidget(btn)
    return w

  # Correspondance statut expédition → statut commande
  _SHIP_TO_ORDER_STATUS = {
    "pending":    "assigned",
    "collected":  "assigned",
    "in_transit": "in_progress",
    "delivered":  "delivered",
    "failed":     "failed",
    "returned":   "pending",
  }

  def _ensure_order_carrier_col(self, conn):
    """Ajoute carrier_id à orders si absent (idempotent)."""
    try:
      conn.execute("ALTER TABLE orders ADD COLUMN carrier_id INTEGER")
      conn.commit()
    except Exception:
      pass

  def _sync_order_from_shipment(self, conn, order_id: int, carrier_id: int, shp_status: str):
    """Met à jour orders.status et orders.carrier_id selon le statut de l'expédition."""
    self._ensure_order_carrier_col(conn)
    order_status = self._SHIP_TO_ORDER_STATUS.get(shp_status, "assigned")
    conn.execute(
      "UPDATE orders SET status=?, carrier_id=? WHERE id=?",
      (order_status, carrier_id, order_id)
    )

  def _add_shipment(self):
    dlg = _ShipmentDialog(self)
    if dlg.exec() != QDialog.DialogCode.Accepted: return
    data = dlg.get_data()
    conn = get_connection()
    self._ensure_order_carrier_col(conn)
    conn.execute("""
      INSERT INTO carrier_shipments
      (carrier_id,order_id,tracking_number,status,estimated_delivery,cost,notes)
      VALUES (?,?,?,?,?,?,?)
    """, (data["carrier_id"], data["order_id"], data["tracking_number"],
       data["status"], data["estimated_delivery"], data["cost"], data["notes"]))
    self._sync_order_from_shipment(conn, data["order_id"], data["carrier_id"], data["status"])
    conn.commit(); conn.close()
    log_action("SHIPMENT_CREATE", f"Expédition créée → transporteur #{data['carrier_id']}")
    show_toast(self.window(), "Expédition créée", "success")
    self._refresh_shipments()

  def _edit_shipment(self, sid: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM carrier_shipments WHERE id= ?", (sid,)).fetchone()
    conn.close()
    if not row: return
    dlg = _ShipmentDialog(self, dict(row))
    if dlg.exec() != QDialog.DialogCode.Accepted: return
    data = dlg.get_data()
    conn = get_connection()
    conn.execute("""
      UPDATE carrier_shipments SET
      carrier_id= ?,order_id= ?,tracking_number= ?,status= ?,
      estimated_delivery= ?,cost= ?,notes= ? WHERE id=?
    """, (data["carrier_id"], data["order_id"], data["tracking_number"],
       data["status"], data["estimated_delivery"], data["cost"], data["notes"], sid))
    self._sync_order_from_shipment(conn, data["order_id"], data["carrier_id"], data["status"])
    conn.commit(); conn.close()
    log_action("SHIPMENT_UPDATE", f"Expédition #{sid} modifiée")
    show_toast(self.window(), "Expédition mise à jour", "success")
    self._refresh_shipments()

  def _delete_shipment(self, sid: int):
    if not ConfirmDialog.ask(self, "Supprimer", "Supprimer cette expédition ", "danger"): return
    conn = get_connection()
    row = conn.execute("SELECT order_id FROM carrier_shipments WHERE id= ?", (sid,)).fetchone()
    conn.execute("DELETE FROM carrier_shipments WHERE id= ?", (sid,))
    if row:
      self._ensure_order_carrier_col(conn)
      conn.execute(
        "UPDATE orders SET status='pending', carrier_id=NULL WHERE id=?",
        (row["order_id"],)
      )
    conn.commit(); conn.close()
    log_action("SHIPMENT_DELETE", f"Expédition #{sid} supprimée")
    show_toast(self.window(), "Expédition supprimée", "info")
    self._refresh_shipments()

  def _refresh_tracking(self):
    rows = getattr(self, "_shp_rows_cache", [])
    to_refresh = [
      {"shipment_id": r["id"], "tracking_number": r.get("tracking_number"),
       "api_tracking_url": r.get("api_tracking_url"), "carrier_id": r.get("carrier_id")}
      for r in rows if r.get("tracking_number") and r.get("api_tracking_url")
        and r.get("status") not in ("delivered","failed","returned")
    ]
    if not to_refresh:
      show_toast(self.window(), "Aucune expédition avec URL de suivi active.", "info"); return
    self._shp_progress.setVisible(True); self._shp_progress.setRange(0, 0)
    t = _StatusRefreshThread(to_refresh, self)
    t.progress.connect(lambda m: show_toast(self.window(), m, "info"))
    t.result.connect(self._on_tracking_result)
    t.error.connect(lambda e: (
      show_toast(self.window(), f"Erreur suivi: {e}", "error"),
      self._shp_progress.setVisible(False),
    ))
    self._threads.append(t); t.start()

  def _on_tracking_result(self, updates: dict):
    self._shp_progress.setVisible(False)
    if not updates:
      show_toast(self.window(), "Aucune mise à jour disponible.", "info"); return
    conn = get_connection()
    for sid, new_status in updates.items():
      if new_status in _SHIP_STATUSES:
        conn.execute("UPDATE carrier_shipments SET status= ? WHERE id= ?", (new_status, sid))
    conn.commit(); conn.close()
    log_action("SHIPMENT_TRACK_REFRESH", f"{len(updates)} statuts mis à jour")
    show_toast(self.window(), f"{len(updates)} statut(s) mis à jour", "success")
    self._refresh_shipments()

  # ══════════════════════════════════════════════════════════════════
  # TAB 2 — SIMULATION
  # ══════════════════════════════════════════════════════════════════

  def _build_tab_sim(self) -> QWidget:
    w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(20, 14, 20, 18); lo.setSpacing(10)
    t = QLabel("Simulation : Flotte propre vs Sous-traitance")
    t.setStyleSheet(f"color:{C['text']};font-size:16px;font-weight:700;background:transparent;")
    lo.addWidget(t)
    sub = QLabel(
      "Sélectionnez des commandes en attente, puis lancez la simulation "
      "pour comparer le coût de votre flotte versus un transporteur."
    )
    sub.setStyleSheet(f"color:{C['text2']};font-size:12px;background:transparent;")
    sub.setWordWrap(True)
    lo.addWidget(sub)

    # Order multi-select table
    multi_hdr = QHBoxLayout()
    multi_hdr.addWidget(QLabel("Commandes en attente (sélection multiple) :"))
    multi_hdr.addStretch()
    run_btn = QPushButton("Lancer la simulation")
    run_btn.setObjectName("primaryBtn")
    run_btn.setFixedHeight(36)
    run_btn.setMinimumWidth(200)
    run_btn.setStyleSheet(
      f"QPushButton{{background:{C['accent']};color:#FFFFFF;border:none;"
      "border-top-left-radius:6px;border-top-right-radius:6px;"
      "border-bottom-left-radius:6px;border-bottom-right-radius:6px;"
      "padding:6px 18px;font-size:13px;font-weight:600;min-height:32px;}}"
      f"QPushButton:hover{{background:{C['accent']};border:1px solid #FFFFFF;color:#FFFFFF;}}"
      f"QPushButton:pressed{{background:{C['hover']};color:#FFFFFF;}}"
    )
    run_btn.clicked.connect(self._run_simulation)
    multi_hdr.addWidget(run_btn)
    lo.addLayout(multi_hdr)

    self._sim_table = QTableWidget(); self._sim_table.setColumnCount(5)
    self._sim_table.setHorizontalHeaderLabels(["Réf", "Client", "kg", "Statut", "Date"])
    self._sim_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    for col, w2 in [(0,130),(2,55),(3,100),(4,90)]:
      self._sim_table.setColumnWidth(col, w2)
    self._sim_table.verticalHeader().setVisible(False)
    self._sim_table.verticalHeader().setDefaultSectionSize(32)
    self._sim_table.setAlternatingRowColors(True)
    self._sim_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    self._sim_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self._sim_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self._sim_table.setMaximumHeight(260)
    self._sim_table.setStyleSheet(_TBL)
    lo.addWidget(self._sim_table)

    self._sim_note = QLabel("Sélectionnez au moins une commande, puis cliquez « Simuler ».")
    self._sim_note.setStyleSheet(f"color:{C['text2']};font-size:12px;background:transparent;")
    lo.addWidget(self._sim_note)
    lo.addStretch()
    return w

  def _refresh_sim(self):
    try:
      conn = get_connection()
      rows = conn.execute("""
        SELECT o.*, c.name AS cname FROM orders o
        LEFT JOIN clients c ON c.id=o.client_id
        WHERE o.archived=0 AND o.status NOT IN ('delivered','cancelled')
        ORDER BY o.scheduled_date DESC
      """).fetchall()
      conn.close()
    except Exception:
      rows = []
    self._sim_table.setRowCount(len(rows))
    self._sim_orders = {i: dict(r) for i, r in enumerate(rows)}
    for r, row in enumerate(rows):
      def _it(v, color=None):
        it = QTableWidgetItem(str(v or ""))
        it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
        if color: it.setForeground(QColor(color))
        return it
      ref_it = _it(row.get("reference") or f"#{row['id']}")
      ref_it.setData(Qt.ItemDataRole.UserRole, row["id"])
      self._sim_table.setItem(r, 0, ref_it)
      self._sim_table.setItem(r, 1, _it(row.get("cname") or ""))
      self._sim_table.setItem(r, 2, _it(f"{float(row.get('quantity_kg') or 0):.0f}"))
      st = row.get("status") or "pending"
      self._sim_table.setItem(r, 3, _it(st, C["text2"]))
      self._sim_table.setItem(r, 4, _it(row.get("scheduled_date") or ""))

  def _run_simulation(self):
    sel_rows = self._sim_table.selectionModel().selectedRows()
    if not sel_rows:
      show_toast(self.window(), "Sélectionnez au moins une commande.", "info"); return
    order_ids = []
    for sr in sel_rows:
      it = self._sim_table.item(sr.row(), 0)
      if it: order_ids.append(it.data(Qt.ItemDataRole.UserRole))
    if not order_ids: return
    dlg = _SimulationDialog(order_ids, self)
    dlg.exec()

  # ══════════════════════════════════════════════════════════════════
  # TAB 3 — ÉVALUATION
  # ══════════════════════════════════════════════════════════════════

  def _build_tab_eval(self) -> QWidget:
    w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(20, 14, 20, 18); lo.setSpacing(10)
    t = QLabel("Évaluation des transporteurs")
    t.setStyleSheet(f"color:{C['text']};font-size:16px;font-weight:700;background:transparent;")
    lo.addWidget(t)

    # Filters
    filt = QHBoxLayout(); filt.setSpacing(8)
    filt.addWidget(QLabel("Période :"))
    self._eval_from = QDateEdit(); self._eval_from.setCalendarPopup(True)
    self._eval_from.setDisplayFormat("dd/MM/yyyy"); self._eval_from.setDate(QDate.currentDate().addMonths(-6))
    self._eval_to = QDateEdit(); self._eval_to.setCalendarPopup(True)
    self._eval_to.setDisplayFormat("dd/MM/yyyy"); self._eval_to.setDate(QDate.currentDate())
    for de in [self._eval_from, self._eval_to]:
      de.setStyleSheet(
        f"QDateEdit{{background:{C['input']};color:{C['text']};"
        f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
      )
    filt.addWidget(self._eval_from); filt.addWidget(QLabel("→")); filt.addWidget(self._eval_to)
    apply = QPushButton("Actualiser")
    apply.setObjectName("primaryBtn")
    apply.setFixedHeight(30)
    apply.setStyleSheet(
      f"QPushButton{{background:{C['accent']};color:#FFFFFF;border:none;"
      "border-top-left-radius:5px;border-top-right-radius:5px;"
      "border-bottom-left-radius:5px;border-bottom-right-radius:5px;"
      "padding:4px 14px;font-size:12px;font-weight:600;}}"
      f"QPushButton:hover{{background:{C['accent']};border:1px solid #FFFFFF;color:#FFFFFF;}}"
      f"QPushButton:pressed{{background:{C['hover']};color:#FFFFFF;}}"
    )
    apply.clicked.connect(self._refresh_eval)
    filt.addWidget(apply)
    filt.addStretch()

    _S = (
      f"QPushButton{{background:{C['input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:5px;padding:4px 10px;font-size:12px;}}"
      f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
    )
    for label, fn in [(" Excel", self._export_excel), (" PDF", self._export_pdf)]:
      btn = QPushButton(label); btn.setFixedHeight(30); btn.setStyleSheet(_S)
      btn.clicked.connect(fn); filt.addWidget(btn)
    lo.addLayout(filt)

    # Recap table
    self._eval_table = QTableWidget(); self._eval_table.setColumnCount(7)
    self._eval_table.setHorizontalHeaderLabels([
      "Transporteur", "Expéditions", "Livrées", "Taux livr. %",
      "Coût total (€)", "Ponctualité %", "Note ",
    ])
    self._eval_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    self._eval_table.verticalHeader().setVisible(False)
    self._eval_table.verticalHeader().setDefaultSectionSize(32)
    self._eval_table.setAlternatingRowColors(True)
    self._eval_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self._eval_table.setMaximumHeight(200)
    self._eval_table.setStyleSheet(_TBL)
    lo.addWidget(self._eval_table)

    # Chart
    self._eval_chart_ctn = QWidget(); self._eval_chart_ctn.setMinimumHeight(240)
    self._eval_chart_lo = QVBoxLayout(self._eval_chart_ctn); self._eval_chart_lo.setContentsMargins(0,0,0,0)
    if not HAS_MPL:
      no_mpl = QLabel("(Matplotlib requis)")
      no_mpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
      no_mpl.setStyleSheet(f"color:{C['text2']};background:transparent;")
      self._eval_chart_lo.addWidget(no_mpl)
    lo.addWidget(self._eval_chart_ctn, 1)
    return w

  def _refresh_eval(self):
    from_dt = self._eval_from.date().toString("yyyy-MM-dd")
    to_dt  = self._eval_to.date().toString("yyyy-MM-dd")
    try:
      conn = get_connection()
      rows = conn.execute("""
        SELECT
          c.id, c.name, c.on_time_rate, c.rating,
          COUNT(cs.id) AS nb,
          SUM(CASE WHEN cs.status='delivered' THEN 1 ELSE 0 END) AS delivered,
          COALESCE(SUM(cs.cost),0) AS total_cost
        FROM carriers c
        LEFT JOIN carrier_shipments cs ON cs.carrier_id=c.id
          AND cs.created_at >= ? AND cs.created_at <= ?
        WHERE c.archived=0
        GROUP BY c.id ORDER BY c.name
      """, (from_dt, to_dt)).fetchall()
      conn.close()
    except Exception as e:
      logger.debug("Eval query error: %s", e)
      rows = []

    self._eval_data = [dict(r) for r in rows]
    self._fill_eval_table()
    self._draw_eval_chart()

  def _fill_eval_table(self):
    data = self._eval_data
    self._eval_table.setRowCount(len(data))
    for r, row in enumerate(data):
      def _it(v, color=None):
        it = QTableWidgetItem(str(v or ""))
        it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
        if color: it.setForeground(QColor(color))
        return it
      self._eval_table.setItem(r, 0, _it(row["name"]))
      nb = row["nb"] or 0
      dlvd = row["delivered"] or 0
      self._eval_table.setItem(r, 1, _it(str(nb)))
      self._eval_table.setItem(r, 2, _it(str(dlvd)))
      rate = round(dlvd / nb * 100, 1) if nb else 0.0
      rate_color = C["success"] if rate >= 90 else C["warning"] if rate >= 70 else C["danger"]
      self._eval_table.setItem(r, 3, _it(f"{rate:.1f}%", rate_color))
      self._eval_table.setItem(r, 4, _it(f"{float(row['total_cost']):.0f}"))
      otr = row.get("on_time_rate")
      otr_str = f"{float(otr):.0f}%" if otr is not None else "—"
      self._eval_table.setItem(r, 5, _it(otr_str))
      rating = float(row.get("rating") or 3)
      stars = "★" * int(rating) + "☆" * (5 - int(rating))
      self._eval_table.setItem(r, 6, _it(stars[:5], C["warning"]))

  def _draw_eval_chart(self):
    for i in reversed(range(self._eval_chart_lo.count())):
      w = self._eval_chart_lo.itemAt(i).widget()
      if w: w.deleteLater()
    if not HAS_MPL or not self._eval_data: return
    try:
      names  = [d["name"][:10] for d in self._eval_data]
      costs  = [float(d["total_cost"]) for d in self._eval_data]
      ratings = [float(d.get("rating") or 3) for d in self._eval_data]

      fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3))
      fig.patch.set_facecolor("#112240")
      for ax in (ax1, ax2):
        ax.set_facecolor("#0D1B2A")
        ax.tick_params(colors="#8899AA", labelsize=9)
        for sp in ax.spines.values(): sp.set_color("#1E3A5F")

      ax1.bar(names, costs, color="#00D4FF", edgecolor="#1E3A5F", linewidth=0.5)
      ax1.set_title("Coût total (€)", color="#8899AA", fontsize=10)
      ax1.tick_params(axis="x", rotation=20)

      ax2.bar(names, ratings, color="#FFB800", edgecolor="#1E3A5F", linewidth=0.5)
      ax2.set_ylim(0, 5); ax2.set_title("Note ( / 5)", color="#8899AA", fontsize=10)
      ax2.tick_params(axis="x", rotation=20)

      fig.tight_layout(pad=0.5)
      canvas = FigCanvas(fig); canvas.setMinimumHeight(220)
      self._eval_chart_lo.addWidget(canvas)
      plt.close(fig)
    except Exception as e:
      logger.debug("Eval chart error: %s", e)

  # ── Exports ───────────────────────────────────────────────────────

  def _export_excel(self):
    data = getattr(self, "_eval_data", [])
    if not data: show_toast(self.window(), "Actualisez d'abord les données.", "info"); return
    if not HAS_OPENPYXL: show_toast(self.window(), "openpyxl requis pour l'export Excel.", "error"); return
    path, _ = QFileDialog.getSaveFileName(self, "Exporter", "eval_transporteurs.xlsx", "Excel (*.xlsx)")
    if not path: return
    try:
      wb = _openpyxl.Workbook(); ws = wb.active
      ws.title = "Évaluation transporteurs"
      ws.append(["Transporteur","Expéditions","Livrées","Taux livr. %","Coût total","Ponctualité %","Note"])
      for row in data:
        nb = row["nb"] or 0; dlvd = row["delivered"] or 0
        rate = round(dlvd/nb*100, 1) if nb else 0
        ws.append([row["name"], nb, dlvd, rate,
              round(float(row["total_cost"]),2),
              row.get("on_time_rate"), row.get("rating")])
      wb.save(path)
      show_toast(self.window(), f"Export Excel : {path.split('/')[-1]}", "success")
    except Exception as e:
      show_toast(self.window(), f"Erreur export: {e}", "error")

  def _export_pdf(self):
    data = getattr(self, "_eval_data", [])
    if not data: show_toast(self.window(), "Actualisez d'abord les données.", "info"); return
    if not HAS_REPORTLAB: show_toast(self.window(), "reportlab requis pour l'export PDF.", "error"); return
    path, _ = QFileDialog.getSaveFileName(self, "Exporter", "eval_transporteurs.pdf", "PDF (*.pdf)")
    if not path: return
    try:
      doc = SimpleDocTemplate(path, pagesize=A4)
      styles = getSampleStyleSheet()
      elements = [Paragraph("Évaluation des Transporteurs", styles["Title"]), Spacer(1, 12)]
      headers = ["Transporteur","Expéd.","Livrées","Taux %","Coût €","Taux ponct. %","Note"]
      table_data = [headers]
      for row in data:
        nb = row["nb"] or 0; dlvd = row["delivered"] or 0
        rate = round(dlvd/nb*100, 1) if nb else 0
        table_data.append([
          str(row["name"])[:20], str(nb), str(dlvd), f"{rate}%",
          f"{float(row['total_cost']):.0f}",
          f"{float(row.get('on_time_rate') or 0):.0f}%",
          str(row.get("rating") or "—"),
        ])
      tbl = Table(table_data)
      tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rl_colors.HexColor("#0A1628")),
        ("TEXTCOLOR", (0,0), (-1,0), rl_colors.white),
        ("ALIGN",   (0,0), (-1,-1),"CENTER"),
        ("FONTNAME",  (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rl_colors.whitesmoke, rl_colors.white]),
        ("GRID",    (0,0), (-1,-1), 0.5, rl_colors.grey),
      ]))
      elements.append(tbl)
      doc.build(elements)
      show_toast(self.window(), f"PDF généré : {path.split('/')[-1]}", "success")
    except Exception as e:
      show_toast(self.window(), f"Erreur PDF: {e}", "error")
