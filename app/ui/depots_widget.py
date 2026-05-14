"""
depots_widget.py — Gestion des dépôts CityPulse Logistics v2.0
===============================================================
• Table + SectionHeader + "+ Ajouter dépôt"
• Fiche 3 onglets : Infos | Carte Leaflet | Stats
• Vue globale — carte de tous les dépôts + zones de couverture
"""

# ── stdlib ────────────────────────────────────────────────────────────────────
import logging

# ── PyQt6 ────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox,
    QMessageBox, QFrame, QStackedWidget, QTabWidget,
    QTextEdit, QAbstractItemView, QMenu, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QColor, QFont, QAction

# ── Local ─────────────────────────────────────────────────────────────────────
from ..database.db_manager import get_connection, log_action
from .toast import show_toast
from .help_dialog import show_help
from .components import SectionHeader, SearchBar, ConfirmDialog, EmptyState
from .components.confirm_dialog import _dialog_qss
from .lucide_icons import apply_action_button

from .webengine_support import (
    HAS_WEB,
    QWebEngineView,
    QWebEngineSettings,
    WEBENGINE_FALLBACK_SHORT,
)

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":    "#0D1B2A", "panel":  "#112240", "input":  "#1A2E4A",
    "accent":"#00D4FF", "success":"#00FF88", "warning":"#FFB800",
    "danger":"#FF4757", "text":   "#E8F4FD", "text2":  "#8899AA",
    "border":"#1E3A5F", "hover":  "#1A3A5C",
}
_DEPOT_COLORS = ["#00D4FF", "#00FF88", "#FFB800", "#C3A6FF", "#FF6B6B", "#96CEB4"]


# ═══════════════════════════════════════════════════════════════════════════════
# GEOCODER THREAD
# ═══════════════════════════════════════════════════════════════════════════════

class _GeocoderThread(QThread):
    result = pyqtSignal(float, float, str)
    error  = pyqtSignal(str)

    def __init__(self, address: str, parent=None):
        super().__init__(parent)
        self.address = address

    def run(self):
        if not HAS_REQUESTS:
            self.error.emit("Module 'requests' non disponible.")
            return
        try:
            resp = _requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": self.address, "format": "json", "limit": 1},
                headers={"User-Agent": "CityPulse/5.5"}, timeout=10,
            )
            data = resp.json()
            if data:
                self.result.emit(float(data[0]["lat"]), float(data[0]["lon"]),
                                 data[0].get("display_name", self.address))
            else:
                self.error.emit(f"Adresse introuvable : {self.address[:60]}")
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# LEAFLET HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _minimap_html(lat: float, lon: float, name: str = "", radius_km: float = 0) -> str:
    safe = (name or "").replace("'", "\\'")[:50]
    circle_js = ""
    if radius_km > 0:
        circle_js = (
            f"L.circle([{lat},{lon}],{{radius:{radius_km * 1000},"
            "color:'#00D4FF',fillColor:'rgba(0,212,255,0.08)',"
            "weight:1.5}).addTo(m);"
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        "<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>"
        "<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>"
        "<style>html,body,#map{width:100%;height:100%;margin:0;padding:0;}</style>"
        f"</head><body><div id='map'></div><script>"
        f"var m=L.map('map',{{zoomControl:true}}).setView([{lat},{lon}],13);"
        "window.__citypulseMap=m;"
        "L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(m);"
        f"L.marker([{lat},{lon}]).addTo(m).bindPopup('{safe}').openPopup();"
        f"{circle_js}"
        "</script></body></html>"
    )


_GLOBAL_MAP_HTML = """<!DOCTYPE html><html><head><meta charset='utf-8'/>
<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>
<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>
<style>html,body,#map{width:100%;height:100%;margin:0;padding:0;}</style></head>
<body><div id='map'></div><script>
var m=L.map('map').setView([33.5731,-7.5898],7);
window.__citypulseMap=m;
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(m);
var COLORS=['#00D4FF','#00FF88','#FFB800','#C3A6FF','#FF6B6B','#96CEB4'];
var data=DEPOT_JSON;var bnds=[];
data.forEach(function(d,i){
  var col=COLORS[i%COLORS.length];
  var icon=L.divIcon({html:'<div style="background:'+col+
    ';width:16px;height:16px;border-radius:50%;border:2px solid #fff;'+
    'box-shadow:0 1px 4px rgba(0,0,0,.5)"></div>',
    iconSize:[16,16],iconAnchor:[8,8]});
  L.marker([d.a,d.o],{icon:icon}).addTo(m)
    .bindPopup('<b>'+d.n+'</b><br>'+d.addr+'<br>'+d.open+' – '+d.close);
  if(d.r>0)L.circle([d.a,d.o],{radius:d.r*1000,color:col,
    fillColor:col,fillOpacity:0.06,weight:1.5}).addTo(m);
  bnds.push([d.a,d.o]);
});
if(bnds.length)m.fitBounds(bnds,{padding:[30,30]});
</script></body></html>"""

_LEAFLET_HTML_BASE = QUrl("qrc:///")


def _configure_leaflet_webview(view: QWebEngineView) -> None:
    if QWebEngineSettings is None:
        return
    s = view.settings()
    s.setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
    )
    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)


def _set_depot_leaflet_html(view: QWebEngineView, html: str) -> None:
    view.setHtml(html, _LEAFLET_HTML_BASE)


def _invalidate_depot_leaflet(view: QWebEngineView) -> None:
    view.page().runJavaScript(
        "try{var mm=window.__citypulseMap;if(mm&&mm.invalidateSize){"
        "mm.invalidateSize();}}catch(e){}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DEPOT DIALOG — 3 onglets
# ═══════════════════════════════════════════════════════════════════════════════

class _DepotDialog(QDialog):

    def __init__(self, parent=None, depot: dict = None):
        super().__init__(parent)
        self.depot = depot or {}
        self.setWindowTitle("Modifier dépôt" if depot else "Nouveau dépôt")
        self.setMinimumSize(620, 500)
        self.resize(680, 540)
        self.setModal(True)
        self._geo_thread = None
        self.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            f"QTabWidget::pane{{background:{C['panel']};border:1px solid {C['border']};border-radius:6px;}}"
            f"QTabBar::tab{{background:{C['input']};color:{C['text2']};padding:8px 14px;"
            "border-top-left-radius:4px;border-top-right-radius:4px;margin-right:2px;font-size:12px;}"
            f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
            f"QTabBar::tab:hover{{background:{C['hover']};}}"
            f"QLineEdit,QDoubleSpinBox,QSpinBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
            f"QLabel{{background:transparent;color:{C['text']};}}"
        )
        self._setup_ui()

    def _lbl(self, t): l = QLabel(t); l.setStyleSheet(f"color:{C['text2']};font-size:11px;"); return l
    def _le(self, v="", ph=""): w = QLineEdit(str(v) if v else ""); w.setPlaceholderText(ph); return w

    def _spin(self, v=0, mn=0, mx=99999, step=1, dec=0):
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
        return w

    def _setup_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 16, 16, 12)
        lo.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._tab_info(),  "  Infos  ")
        self._tabs.addTab(self._tab_map(),   "  Carte  ")
        self._tabs.addTab(self._tab_stats(), "  Stats  ")
        lo.addWidget(self._tabs, 1)
        self._tabs.currentChanged.connect(self._on_depot_tab_changed)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn")
        cancel.setFixedHeight(34); cancel.clicked.connect(self.reject)
        save = QPushButton("Sauvegarder"); save.setObjectName("primaryBtn")
        save.setFixedHeight(34); save.setMinimumWidth(120)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(cancel); btn_row.addWidget(save)
        lo.addLayout(btn_row)

    def _on_depot_tab_changed(self, index: int):
        if index != 1 or not HAS_WEB or not hasattr(self, "_map_view"):
            return
        QTimer.singleShot(80, lambda: _invalidate_depot_leaflet(self._map_view))

    def _on_depot_minimap_loaded(self, ok: bool):
        if not ok or not HAS_WEB or not hasattr(self, "_map_view"):
            return
        QTimer.singleShot(50, lambda: _invalidate_depot_leaflet(self._map_view))

    # ── Tab 0 : Infos ─────────────────────────────────────────────────
    def _tab_info(self) -> QWidget:
        w = QWidget(); fl = QFormLayout(w)
        fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
        d = self.depot

        self._name    = self._le(d.get("name", ""),    "Nom du dépôt *")
        self._address = self._le(d.get("address", ""), "Adresse complète")
        self._manager = self._le(d.get("manager_name", "") or "", "Nom du responsable")
        self._phone   = self._le(d.get("phone", "") or "", "Téléphone")

        coord_row = QHBoxLayout()
        self._lat = self._spin(d.get("latitude", 33.5731), -90, 90, 0.000001, 6)
        self._lon = self._spin(d.get("longitude", -7.5898), -180, 180, 0.000001, 6)
        for lbl, sp in [("Lat", self._lat), ("Lon", self._lon)]:
            coord_row.addWidget(QLabel(lbl)); coord_row.addWidget(sp)
        self._geo_btn = QPushButton("Géocoder")
        self._geo_btn.setObjectName("primaryBtn"); self._geo_btn.setFixedHeight(28)
        self._geo_btn.clicked.connect(self._do_geocode)
        coord_row.addWidget(self._geo_btn)
        self._geo_status = QLabel("")
        self._geo_status.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")

        tw_row = QHBoxLayout()
        self._open  = self._le(d.get("open_time")  or d.get("opening_time", "08:00"), "HH:MM")
        self._close = self._le(d.get("close_time") or d.get("closing_time", "20:00"), "HH:MM")
        self._open.setFixedWidth(70); self._close.setFixedWidth(70)
        for lbl, le in [("Ouv", self._open), ("Ferm", self._close)]:
            tw_row.addWidget(QLabel(lbl)); tw_row.addWidget(le)
        tw_row.addStretch()

        self._bays     = self._spin(d.get("loading_bays", 4), 0, 100)
        self._capacity = self._spin(d.get("storage_capacity", 0) or
                                    d.get("max_vehicles", 50), 0, 9999999)
        self._notes    = QTextEdit()
        self._notes.setMaximumHeight(60)
        self._notes.setPlaceholderText("Notes opérationnelles…")
        self._notes.setStyleSheet(
            f"QTextEdit{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px;}}"
        )

        fl.addRow(self._lbl("Nom *"),            self._name)
        fl.addRow(self._lbl("Adresse"),          self._address)
        fl.addRow(self._lbl("Responsable"),      self._manager)
        fl.addRow(self._lbl("Téléphone"),        self._phone)
        fl.addRow(self._lbl("Coordonnées"),      coord_row)
        fl.addRow("",                            self._geo_status)
        fl.addRow(self._lbl("Horaires"),         tw_row)
        fl.addRow(self._lbl("Quais chargement"), self._bays)
        fl.addRow(self._lbl("Capacité (unités)"),self._capacity)
        fl.addRow(self._lbl("Notes"),            self._notes)
        return w

    def _do_geocode(self):
        addr = self._address.text().strip()
        if not addr:
            self._geo_status.setText("Entrez une adresse.")
            return
        self._geo_btn.setEnabled(False)
        self._geo_status.setText("Géocodage…")
        self._geo_thread = _GeocoderThread(addr, self)
        self._geo_thread.result.connect(self._on_geo_ok)
        self._geo_thread.error.connect(lambda e: (
            self._geo_status.setText(f"Erreur: {e[:50]}"),
            self._geo_btn.setEnabled(True),
        ))
        self._geo_thread.start()

    def _on_geo_ok(self, lat, lon, name):
        self._lat.setValue(lat); self._lon.setValue(lon)
        self._geo_status.setText(f"OK: {name[:55]}")
        self._geo_btn.setEnabled(True)
        self._update_map()

    # ── Tab 1 : Carte ─────────────────────────────────────────────────
    def _tab_map(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w)
        lo.setContentsMargins(16, 16, 16, 8); lo.setSpacing(8)

        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("Rayon couverture (km) :"))
        self._radius = self._spin(
            self.depot.get("coverage_radius_km", 20), 0, 500, 5, 1)
        radius_row.addWidget(self._radius)
        radius_row.addStretch()
        lo.addLayout(radius_row)

        if HAS_WEB:
            self._map_view = QWebEngineView()
            _configure_leaflet_webview(self._map_view)
            self._map_view.setMinimumHeight(300)
            lat = float(self.depot.get("latitude") or 33.5731)
            lon = float(self.depot.get("longitude") or -7.5898)
            r   = float(self.depot.get("coverage_radius_km", 20) or 20)
            _set_depot_leaflet_html(
                self._map_view,
                _minimap_html(lat, lon, self.depot.get("name", ""), r),
            )
            self._map_view.loadFinished.connect(self._on_depot_minimap_loaded)
            self._lat.valueChanged.connect(self._update_map)
            self._lon.valueChanged.connect(self._update_map)
            self._radius.valueChanged.connect(self._update_map)
            lo.addWidget(self._map_view, 1)
        else:
            lo.addWidget(QLabel(f"(Carte non disponible — {WEBENGINE_FALLBACK_SHORT})"))
        return w

    def _update_map(self):
        if HAS_WEB and hasattr(self, "_map_view"):
            _set_depot_leaflet_html(
                self._map_view,
                _minimap_html(
                    self._lat.value(),
                    self._lon.value(),
                    self._name.text(),
                    float(self._radius.value()),
                ),
            )

    # ── Tab 2 : Stats ─────────────────────────────────────────────────
    def _tab_stats(self) -> QWidget:
        w = QWidget(); fl = QFormLayout(w)
        fl.setSpacing(10); fl.setContentsMargins(16, 16, 16, 8)
        did = self.depot.get("id")

        def _stat(label: str, val: str):
            lw = QLabel(label); lw.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            vw = QLabel(val);   vw.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:600;background:transparent;")
            fl.addRow(lw, vw)

        if did:
            try:
                conn = get_connection()
                nb_veh = conn.execute(
                    "SELECT COUNT(*) FROM vehicles WHERE depot_id= ?", (did,)
                ).fetchone()[0] or 0
                nb_cli = conn.execute(
                    "SELECT COUNT(*) FROM clients WHERE archived=0"
                ).fetchone()[0] or 0
                nb_routes = conn.execute(
                    "SELECT COUNT(*) FROM algo_results WHERE 1"
                ).fetchone()[0] or 0
                conn.close()
            except Exception:
                nb_veh = nb_cli = nb_routes = 0
            _stat("Véhicules attachés", str(nb_veh))
            _stat("Clients actifs (total)", str(nb_cli))
            _stat("Tournées optimisées (total)", str(nb_routes))
        else:
            fl.addRow(QLabel("Stats disponibles après sauvegarde."))
        return w

    # ── Save ──────────────────────────────────────────────────────────
    def _on_save(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, "Validation", "Le nom est obligatoire.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name":            self._name.text().strip(),
            "address":         self._address.text().strip(),
            "manager_name":    self._manager.text().strip(),
            "phone":           self._phone.text().strip(),
            "latitude":        self._lat.value(),
            "longitude":       self._lon.value(),
            "open_time":       self._open.text().strip() or "08:00",
            "close_time":      self._close.text().strip() or "20:00",
            "opening_time":    self._open.text().strip() or "08:00",
            "closing_time":    self._close.text().strip() or "20:00",
            "loading_bays":    self._bays.value(),
            "storage_capacity":self._capacity.value(),
            "coverage_radius_km": float(self._radius.value()),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL MAP DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class _GlobalMapDialog(QDialog):
    def __init__(self, depots: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Vue globale — {len(depots)} dépôts")
        self.resize(820, 620)
        self.setStyleSheet(_dialog_qss() + f"QDialog{{background:{C['bg']};color:{C['text']};}}")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)

        if HAS_WEB:
            import json as _json
            data = _json.dumps([{
                "n": (d.get("name") or "")[:40],
                "addr": (d.get("address") or "")[:40],
                "open": d.get("open_time") or d.get("opening_time") or "08:00",
                "close": d.get("close_time") or d.get("closing_time") or "20:00",
                "a": float(d.get("latitude") or 0),
                "o": float(d.get("longitude") or 0),
                "r": float(d.get("coverage_radius_km") or 0),
            } for d in depots if float(d.get("latitude") or 0) != 0])
            view = QWebEngineView()
            _configure_leaflet_webview(view)
            _set_depot_leaflet_html(
                view, _GLOBAL_MAP_HTML.replace("DEPOT_JSON", data)
            )

            def _on_glob_load(ok: bool):
                if ok:
                    QTimer.singleShot(50, lambda v=view: _invalidate_depot_leaflet(v))

            view.loadFinished.connect(_on_glob_load)
            lo.addWidget(view, 1)
        else:
            lbl = QLabel(f"{len(depots)} dépôts — {WEBENGINE_FALLBACK_SHORT}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{C['text2']};font-size:14px;")
            lo.addWidget(lbl, 1)

        # Legend
        leg = QHBoxLayout()
        leg.setContentsMargins(14, 6, 14, 6)
        for i, d in enumerate(depots[:6]):
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background:{_DEPOT_COLORS[i % len(_DEPOT_COLORS)]};border-radius:5px;")
            leg.addWidget(dot)
            leg.addWidget(QLabel(d.get("name", f"D{i+1}")[:16]))
            leg.addSpacing(12)
        leg.addStretch()
        close_btn = QPushButton("Fermer")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        leg.addWidget(close_btn)
        lo.addLayout(leg)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPOTS WIDGET — Page principale
# ═══════════════════════════════════════════════════════════════════════════════

class DepotsWidget(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._threads: list = []
        self._ensure_column()
        self._setup_ui()

    def _ensure_column(self):
        try:
            conn = get_connection()
            for col, defn in [
                ("manager_name",       "TEXT"),
                ("phone",              "TEXT"),
                ("coverage_radius_km", "REAL DEFAULT 20"),
                ("open_time",          "TEXT DEFAULT '08:00'"),
                ("close_time",         "TEXT DEFAULT '20:00'"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE depots ADD COLUMN {col} {defn}")
                    conn.commit()
                except Exception:
                    pass
            conn.close()
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 8)
        root.setSpacing(14)

        self._header = SectionHeader(
            title="Gestion des Dépôts",
            subtitle="Centres de distribution, zones de couverture et statistiques",
            action_text="+ Ajouter dépôt",
            action_callback=self._add_depot,
        )
        root.addWidget(self._header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._search = SearchBar(placeholder="Rechercher (nom, ville, responsable)…")
        self._search.setMaximumWidth(280)
        self._search.search_changed.connect(self._on_search)
        toolbar.addWidget(self._search)
        toolbar.addSpacing(6)

        _S = (
            f"QPushButton{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;"
            "font-size:12px;padding:4px 10px;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
        )
        btn_map = QPushButton("Vue Carte globale")
        btn_map.setFixedHeight(30)
        btn_map.setStyleSheet(_S)
        btn_map.clicked.connect(self._show_global_map)
        toolbar.addWidget(btn_map)

        toolbar.addStretch()
        self._count_lbl = QLabel("0 dépôts")
        self._count_lbl.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        toolbar.addWidget(self._count_lbl)
        toolbar.addSpacing(4)
        _hb = QPushButton()
        _hb.setFixedSize(30, 30)
        _hb.setToolTip("Aide — Dépôts")
        _hb.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(_hb, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        _hb.clicked.connect(lambda: show_help(self, "depots"))
        toolbar.addWidget(_hb)
        root.addLayout(toolbar)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Nom", "Adresse", "Responsable", "Horaires",
            "Quais", "Capacité", "Rayon km", "Actions",
        ])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col, w in [(2,130),(3,120),(4,55),(5,80),(6,70),(7,110)]:
            self._table.setColumnWidth(col, w)

        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.doubleClicked.connect(self._on_dblclick)
        self._table.setStyleSheet(
            f"QTableWidget{{background:{C['bg']};color:{C['text']};"
            f"gridline-color:{C['border']};border:none;alternate-background-color:#0F2035;}}"
            f"QTableWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:4px 6px;font-size:11px;font-weight:600;}}"
        )

        self._empty = EmptyState(
            title="Aucun dépôt",
            subtitle="Créez vos centres de distribution pour lancer l'optimisation.",
            action_text="+ Ajouter un dépôt",
            action_callback=self._add_depot,
        )
        self._stack = QStackedWidget()
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)
        root.addWidget(self._stack, 1)

    # ── Data ──────────────────────────────────────────────────────────

    def retranslate_ui(self, lang: str):
        from app.i18n import tr
        if hasattr(self, "_header"):
            self._header.set_title(tr("section.depots", lang))

    def refresh_data(self):
        search = self._search.get_text().strip()

        conn = get_connection()
        if search:
            s = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM depots"
                " WHERE name LIKE ? OR COALESCE(address,'') LIKE ? "
                " OR COALESCE(manager_name,'') LIKE ? "
                " ORDER BY name", [s, s, s]
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM depots ORDER BY name"
            ).fetchall()
        conn.close()

        self._count_lbl.setText(f"{len(rows)} dépôt{'s' if len(rows) != 1 else ''}")
        self._fill_table(rows)
        self._stack.setCurrentIndex(0 if rows else 1)

    def _on_search(self, _):
        self.refresh_data()

    def _fill_table(self, rows):
        self._table.setSortingEnabled(False)
        self._table.blockSignals(True)
        self._table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            def _item(val, color=None) -> QTableWidgetItem:
                it = QTableWidgetItem(str(val) if val is not None else "")
                it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
                if color:
                    it.setForeground(QColor(color))
                return it

            # Store depot id in row 0
            name_it = _item(row["name"])
            name_it.setData(Qt.ItemDataRole.UserRole, row["id"])
            name_it.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self._table.setItem(r, 0, name_it)

            self._table.setItem(r, 1, _item(row.get("address") or ""))

            mgr = ""
            try: mgr = row["manager_name"] or ""
            except Exception: pass
            self._table.setItem(r, 2, _item(mgr, color=C["text2"] if not mgr else None))

            open_t  = row.get("open_time")  or row.get("opening_time")  or "08:00"
            close_t = row.get("close_time") or row.get("closing_time")  or "20:00"
            self._table.setItem(r, 3, _item(f"{open_t} – {close_t}"))

            bays = 0
            try: bays = row["loading_bays"] or 0
            except Exception: pass
            self._table.setItem(r, 4, _item(str(bays)))

            cap = 0
            try: cap = row["storage_capacity"] or 0
            except Exception: pass
            self._table.setItem(r, 5, _item(str(cap)))

            rad = 0.0
            try: rad = float(row["coverage_radius_km"] or 0)
            except Exception: pass
            self._table.setItem(r, 6, _item(f"{rad:.0f}"))

            self._table.setCellWidget(r, 7, self._make_actions(row["id"], row.get("name", "")))

        self._table.blockSignals(False)
        self._table.setSortingEnabled(True)

    def _make_actions(self, did: int, name: str) -> QWidget:
        w = QWidget(); lo = QHBoxLayout(w)
        lo.setContentsMargins(4, 2, 4, 2); lo.setSpacing(3)
        for lucide_key, tip, fn, bg, fg, hbg in [
            ("pencil", "Modifier",      lambda _, i=did: self._edit_depot(i),   C["hover"], C["accent"], C["panel"]),
            ("map", "Carte dépôt",  lambda _, i=did: self._show_one_map(i), C["hover"], "#96CEB4",   C["panel"]),
            ("trash-2", "Supprimer",    lambda _, i=did, n=name: self._delete_depot(i, n), C["hover"], C["danger"], "#3A1020"),
        ]:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_action_button(btn, lucide_key, fg, bg, hbg, icon_px=16)
            btn.clicked.connect(fn)
            lo.addWidget(btn)
        return w

    def _context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0: return
        item = self._table.item(row, 0)
        did = item.data(Qt.ItemDataRole.UserRole) if item else None
        name = item.text() if item else ""
        if not did: return

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};"
            "border-radius:6px;padding:4px;}}"
            f"QMenu::item{{padding:6px 18px;border-radius:4px;}}"
            f"QMenu::item:selected{{background:{C['hover']};}}"
        )
        for label, fn in [
            ("  Modifier",       lambda: self._edit_depot(did)),
            ("  Voir sur carte", lambda: self._show_one_map(did)),
            (None, None),
            ("  Supprimer",     lambda: self._delete_depot(did, name)),
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
            did = item.data(Qt.ItemDataRole.UserRole)
            if did: self._edit_depot(did)

    # ── CRUD ──────────────────────────────────────────────────────────

    def _save_extended(self, conn, did: int, data: dict):
        for col, val in [
            ("manager_name",       data.get("manager_name")),
            ("phone",              data.get("phone")),
            ("open_time",          data.get("open_time")),
            ("close_time",         data.get("close_time")),
            ("loading_bays",       data.get("loading_bays")),
            ("coverage_radius_km", data.get("coverage_radius_km")),
        ]:
            if val is not None:
                try:
                    conn.execute(f"UPDATE depots SET {col}= ? WHERE id= ?", (val, did))
                except Exception:
                    pass

    def _add_depot(self):
        dlg = _DepotDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        data = dlg.get_data()
        conn = get_connection()
        cur = conn.execute("""
            INSERT INTO depots
            (name, address, latitude, longitude, opening_time, closing_time, storage_capacity)
            VALUES (?,?,?,?,?,?,?)
        """, (data["name"], data["address"], data["latitude"], data["longitude"],
              data["opening_time"], data["closing_time"], data["storage_capacity"]))
        did = cur.lastrowid
        self._save_extended(conn, did, data)
        conn.commit(); conn.close()
        log_action("DEPOT_CREATE", f"Dépôt '{data['name']}' créé")
        show_toast(self.window(), f"Dépôt '{data['name']}' créé", "success")
        self.refresh_data()

    def _edit_depot(self, did: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM depots WHERE id= ?", (did,)).fetchone()
        conn.close()
        if not row: return
        dlg = _DepotDialog(self, dict(row))
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        data = dlg.get_data()
        conn = get_connection()
        conn.execute("""
            UPDATE depots SET name= ?, address= ?, latitude= ?, longitude= ?,
            opening_time= ?, closing_time= ?, storage_capacity= ? WHERE id=?
        """, (data["name"], data["address"], data["latitude"], data["longitude"],
              data["opening_time"], data["closing_time"], data["storage_capacity"], did))
        self._save_extended(conn, did, data)
        conn.commit(); conn.close()
        log_action("DEPOT_UPDATE", f"Dépôt #{did} modifié")
        show_toast(self.window(), "Dépôt mis à jour", "success")
        self.refresh_data()

    def _delete_depot(self, did: int, name: str = ""):
        if did == 1:
            QMessageBox.warning(self, "Erreur",
                                "Le dépôt principal (id=1) ne peut pas être supprimé.")
            return
        if not ConfirmDialog.ask(self, "Supprimer dépôt",
                                  f"Supprimer définitivement « {name} » ", "danger"):
            return
        conn = get_connection()
        conn.execute("DELETE FROM depots WHERE id= ?", (did,))
        conn.commit(); conn.close()
        log_action("DEPOT_DELETE", f"Dépôt #{did} ({name}) supprimé")
        show_toast(self.window(), f"Dépôt supprimé", "info")
        self.refresh_data()

    # ── Map ───────────────────────────────────────────────────────────

    def _show_global_map(self):
        conn = get_connection()
        depots = [dict(r) for r in conn.execute("SELECT * FROM depots").fetchall()]
        conn.close()
        if not depots:
            show_toast(self.window(), "Aucun dépôt à afficher.", "info")
            return
        _GlobalMapDialog(depots, self).exec()

    def _show_one_map(self, did: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM depots WHERE id= ?", (did,)).fetchone()
        conn.close()
        if row: _GlobalMapDialog([dict(row)], self).exec()
