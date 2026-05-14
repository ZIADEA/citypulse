"""
map_widget.py — Carte interactive Leaflet.js v2
================================================
PHASE 4-A : layout QDockWidget + MapBridge WebChannel + 9 couches
"""

import json
import logging
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QObject, QTimer, QThread, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QComboBox, QDockWidget, QFrame, QScrollArea, QSizePolicy, QSplitter,
    QToolBar, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QMessageBox, QFileDialog, QSlider, QApplication, QProgressBar,
    QMainWindow,
)

from .webengine_support import (
    HAS_WEB,
    HAS_WEBCHANNEL,
    QWebChannel,
    QWebEngineSettings,
    QWebEngineView,
    WEBENGINE_FALLBACK_LABEL,
)

from ..database.db_manager import get_connection, log_action
from ..paths import settings_json_path
from .help_dialog import show_help
from .lucide_icons import apply_action_button
from .toast import show_toast
from .components.confirm_dialog import _dialog_qss

logger = logging.getLogger(__name__)

try:
    import requests as _requests_mod
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class _WeatherThread(QThread):
    """Récupère la météo OWM en arrière-plan pour ne pas bloquer le thread Qt."""
    result = pyqtSignal(str)   # payload JSON → showWeather()

    def __init__(self, lat: float, lon: float, key: str, parent=None):
        super().__init__(parent)
        self._lat = lat
        self._lon = lon
        self._key = key

    def run(self):
        try:
            from ..services import weather_service as ws
            import json as _j
            cur = ws.get_current(self._lat, self._lon, self._key)
            if not cur:
                self.result.emit('{"text":"","icon":""}')
                return
            main = (cur.get("main") or "").lower()
            ic = "\U0001f327" if "rain" in main else ("❄" if "snow" in main else "☀")
            txt = f"{cur.get('description', '')} {cur.get('temp', '')}°C"
            self.result.emit(_j.dumps({"text": txt, "icon": ic}, ensure_ascii=False))
        except Exception:
            logger.debug("WeatherThread erreur", exc_info=True)
            self.result.emit('{"text":"","icon":""}')

class _OsrmGeometryThread(QThread):
    """Récupère la géométrie routière réelle depuis OSRM pour chaque tournée."""
    route_ready = pyqtSignal(int, str)   # vehicle_id, coords_json (liste [lat,lon])
    all_done    = pyqtSignal()

    def __init__(self, routes_data: list, osrm_base: str, parent=None):
        super().__init__(parent)
        # routes_data : [{"vehicle_id": int, "coords": [[lat,lon], ...]}]
        self._routes    = routes_data
        self._osrm_base = osrm_base.rstrip("/")

    def run(self):
        import time
        try:
            import requests as _req
        except ImportError:
            self.all_done.emit()
            return

        for route in self._routes:
            vid    = route["vehicle_id"]
            coords = route["coords"]
            if len(coords) < 2:
                continue
            # Limiter à 50 waypoints pour éviter URL trop longue
            if len(coords) > 50:
                coords = coords[:50]
            try:
                # OSRM attend lon,lat (inverse de Leaflet)
                coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
                url = (f"{self._osrm_base}/route/v1/driving/{coord_str}"
                       f"?overview=full&geometries=geojson")
                resp = _req.get(url, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        geom = data["routes"][0]["geometry"]["coordinates"]
                        # Convertir [lon,lat] → [lat,lon] pour Leaflet
                        leaflet = [[lat, lon] for lon, lat in geom]
                        import json as _j
                        self.route_ready.emit(vid, _j.dumps(leaflet))
            except Exception:
                pass  # On garde les lignes droites pour cette tournée
            time.sleep(0.15)  # Respecter le serveur public OSRM

        self.all_done.emit()


C = {
    "bg": "#0D1B2A", "bg2": "#162840", "card": "#1A2D42",
    "accent": "#00D4FF", "text": "#E8F4F8", "text2": "#7FA8C0",
    "success": "#00FF88", "danger": "#FF4757", "warning": "#FFB800",
    "border": "#1E3A50", "toolbar": "#111E2E",
}

ALGO_COLORS = [
    "#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EC4899",
    "#06B6D4", "#EF4444", "#84CC16", "#F97316", "#6366F1",
]

# ── HTML Leaflet complet ───────────────────────────────────────────────────────
LEAFLET_HTML = """<!DOCTYPE html>
<html><head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>
<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 100%; height: 100%; background: #0D1B2A; }
#map { width: 100%; height: 100%; }
#weather-banner {
  position: absolute; top: 8px; left: 50%; transform: translateX(-50%);
  z-index: 1000; background: rgba(13,27,42,0.85); color: #E8F4F8;
  padding: 4px 16px; border-radius: 20px; font-size: 12px;
  border: 1px solid #1E3A50; pointer-events: none; display: none;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }
.blink-icon { animation: blink 1s infinite; }
.vehicle-dot {
  width: 18px; height: 18px; border-radius: 50%;
  border: 3px solid white; box-shadow: 0 0 8px rgba(0,212,255,0.7);
}
.vehicle-dot.late { border-color: #FF4757; box-shadow: 0 0 8px rgba(255,71,87,0.8); animation: blink .8s infinite; }
.depot-icon {
  width: 36px; height: 36px; border-radius: 50%;
  background: #1A2D42; border: 3px solid #00D4FF;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; box-shadow: 0 2px 12px rgba(0,212,255,.4);
}
.client-num {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: #fff;
  box-shadow: 0 2px 6px rgba(0,0,0,.5);
}
</style>
</head>
<body>
<div id="weather-banner"></div>
<div id="map"></div>
<script>
var map = L.map('map', { zoomControl: false }).setView([{lat}, {lon}], {zoom});
window.__citypulseMap = map;
window.citypulseMapReady = true;
L.control.zoom({ position: 'topright' }).addTo(map);

var BASEMAPS = {
  'Standard': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap', maxZoom: 19 }),
  'Dark': L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { attribution: '&copy; CartoDB', maxZoom: 19 }),
  'Satellite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: '&copy; Esri', maxZoom: 18 }),
  'Terrain': L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenTopoMap', maxZoom: 17 })
};
BASEMAPS['{basemap}'].addTo(map);
var currentBasemap = '{basemap}';

var layerDepots   = L.layerGroup().addTo(map);
var layerClients  = L.layerGroup().addTo(map);
var layerRoutes   = L.layerGroup().addTo(map);
var layerVehicles = L.layerGroup().addTo(map);
var layerHeat     = null;
var layerZones    = L.layerGroup().addTo(map);
var layerAlerts   = L.layerGroup().addTo(map);
var layerDraw     = L.layerGroup().addTo(map);

var layerVisible = { depots:true, clients:true, routes:true, vehicles:true, heatmap:false, zones:true, alerts:true, weather:false, traffic:false };

var bridge = null;
try {
  if (typeof qt !== 'undefined' && typeof QWebChannel !== 'undefined') {
    new QWebChannel(qt.webChannelTransport, function(channel) { bridge = channel.objects.bridge; });
  }
} catch(e) {}

function _call(m, a) { try { if (bridge && bridge[m]) bridge[m](a); } catch(e) {} }
function fmtMin(m) { m=Math.round(m); var h=Math.floor(m/60),mn=m%60; return (h<10?'0'+h:h)+':'+(mn<10?'0'+mn:mn); }
function _escape(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function clearAll() {
  layerDepots.clearLayers(); layerClients.clearLayers();
  layerRoutes.clearLayers(); layerVehicles.clearLayers(); layerAlerts.clearLayers();
  if (layerHeat) { map.removeLayer(layerHeat); layerHeat = null; }
  _routePolylines = {};
}

function addDepot(d) {
  var icon = L.divIcon({ className:'', iconSize:[36,36], iconAnchor:[18,18], html:'<div class="depot-icon">D</div>' });
  L.marker([d.lat, d.lon], {icon:icon})
   .bindPopup('<b>'+_escape(d.name)+'</b><br><small>'+_escape(d.address||'')+'</small><br>'+_escape(d.manager||''), {maxWidth:220})
   .on('click', function(){ _call('on_marker_clicked', JSON.stringify({table:'depots',id:d.id})); })
   .addTo(layerDepots);
}

function addClient(d) {
  var color = d.color || '#3B82F6';
  var icon = L.divIcon({ className:'', iconSize:[28,28], iconAnchor:[14,14], html:'<div class="client-num" style="background:'+color+';">'+(d.order_num||'')+'</div>' });
  var popup = '<b>'+_escape(d.name)+'</b> <small>#'+d.id+'</small><hr style="margin:4px 0">'
    +'Demande: '+d.demand_kg+' kg<br>Creneau: '+fmtMin(d.ready_time)+'-'+fmtMin(d.due_time)+'<br>Type: '+_escape(d.client_type||'standard');
  L.marker([d.lat, d.lon], {icon:icon}).bindPopup(popup, {maxWidth:220}).addTo(layerClients);
}

var _routePolylines = {};
function addRoute(d) {
  var line = L.polyline(d.coords, { color:d.color, weight:4, opacity:0.75, lineCap:'round', lineJoin:'round',
    dashArray: d.is_straight ? '8,6' : null });
  line.bindPopup('<b>'+_escape(d.label||'Route')+'</b>'+(d.is_straight?'<br><small>⏳ Géométrie routière en cours…</small>':''));
  line.addTo(layerRoutes);
  _routePolylines[d.vehicle_id] = { line: line, color: d.color, label: d.label };
}
function updateRouteGeometry(vehicle_id, coords_json) {
  try {
    var entry = _routePolylines[vehicle_id];
    if (!entry) return;
    var coords = JSON.parse(coords_json);
    entry.line.setLatLngs(coords);
    entry.line.setStyle({ opacity:0.9, weight:5, dashArray:null });
    entry.line.bindPopup('<b>'+_escape(entry.label||'Route')+'</b>');
  } catch(e) { console.warn('updateRouteGeometry', e); }
}

function updateVehicle(d) {
  layerVehicles.eachLayer(function(l){ if(l._vid===d.id) layerVehicles.removeLayer(l); });
  var icon = L.divIcon({ className:'', iconSize:[18,18], iconAnchor:[9,9],
    html:'<div class="vehicle-dot'+(d.is_late?' late':'')+'" style="background:'+(d.is_late?'#FF4757':'#00D4FF')+'"></div>' });
  var m = L.marker([d.lat, d.lon], {icon:icon})
    .bindPopup('<b>'+_escape(d.registration||'V'+d.id)+'</b><br>'+_escape(d.status||'')+'<br>'+(d.speed_kmh||0)+' km/h');
  m._vid = d.id;
  m.on('click', function(){ _call('on_marker_clicked', JSON.stringify({table:'vehicles',id:d.id})); });
  m.addTo(layerVehicles);
}

function updateHeatmap(pts) {
  if (layerHeat) { map.removeLayer(layerHeat); layerHeat = null; }
  if (!pts || !pts.length) return;
  layerHeat = L.layerGroup();
  pts.forEach(function(p) {
    L.circle([p[0],p[1]], { radius:300, color:'#00D4FF', fillColor:'#00D4FF', fillOpacity:Math.min(0.5,(p[2]||0.1)*0.6), weight:0 }).addTo(layerHeat);
  });
  if (layerVisible.heatmap) map.addLayer(layerHeat);
}

function addZone(d) {
  try {
    var gj = typeof d.geojson==='string' ? JSON.parse(d.geojson) : d.geojson;
    var color = d.zone_type==='zfe' ? '#FF4757' : (d.zone_type==='livraison' ? '#00FF88' : '#FFB800');
    L.geoJSON(gj, { style:{color:color,weight:2,fillOpacity:.15,fillColor:color},
      onEachFeature:function(f,l){ l.bindPopup('<b>'+_escape(d.name)+'</b><br>Type: '+_escape(d.zone_type)); } }).addTo(layerZones);
  } catch(e) { console.warn('Zone err',e); }
}

function addAlert(d) {
  var icon = L.divIcon({ className:'blink-icon', iconSize:[28,28], iconAnchor:[14,14], html:'<div style="font-size:18px;font-weight:bold;filter:drop-shadow(0 0 4px red);">!</div>' });
  L.marker([d.lat, d.lon], {icon:icon})
   .bindPopup('<b>'+_escape(d.message)+'</b><br>'+_escape(d.severity||'info'))
   .addTo(layerAlerts);
}

function showWeather(d) {
  var el = document.getElementById('weather-banner');
  if (!el) return;
  el.innerHTML = (d.icon||'')+' '+_escape(d.text||'');
  el.style.display = d.text ? 'block' : 'none';
}

function toggleLayer(name, visible) {
  layerVisible[name] = visible;
  var layers = { depots:layerDepots, clients:layerClients, routes:layerRoutes, vehicles:layerVehicles, zones:layerZones, alerts:layerAlerts };
  if (layers[name]) {
    if (visible) { if (!map.hasLayer(layers[name])) map.addLayer(layers[name]); }
    else { if (map.hasLayer(layers[name])) map.removeLayer(layers[name]); }
  }
  if (name==='heatmap' && layerHeat) { if (visible) map.addLayer(layerHeat); else map.removeLayer(layerHeat); }
}

function setBasemap(name) {
  if (BASEMAPS[currentBasemap]) map.removeLayer(BASEMAPS[currentBasemap]);
  if (BASEMAPS[name]) { BASEMAPS[name].addTo(map); currentBasemap = name; }
}

function centerOn(lat, lon, zoom) {
  if (lat !== undefined && lon !== undefined) map.setView([lat,lon], zoom||15);
  else fitBoundsAll();
}

function fitBoundsAll() {
  var bounds = [];
  function collect(lg) { lg.eachLayer(function(l){ if(l.getLatLng) bounds.push(l.getLatLng()); }); }
  collect(layerDepots); collect(layerVehicles); collect(layerClients);
  if (bounds.length > 0) map.fitBounds(L.latLngBounds(bounds).pad(0.1));
}

// ── Mesure de distance native (sans plugin) ──────────────────────────────────
var _measureActive = false, _measurePoints = [], _measureLayer = L.layerGroup().addTo(map);
function toggleMeasure(active) {
  _measureActive = active;
  _measureLayer.clearLayers();
  _measurePoints = [];
  map.getContainer().style.cursor = active ? 'crosshair' : '';
}
map.on('click', function(e) {
  if (!_measureActive) return;
  _measurePoints.push(e.latlng);
  L.circleMarker(e.latlng, {radius:5, color:'#FFB800', fillColor:'#FFB800', fillOpacity:1}).addTo(_measureLayer);
  if (_measurePoints.length >= 2) {
    var total = 0;
    for (var i=1; i<_measurePoints.length; i++) total += _measurePoints[i-1].distanceTo(_measurePoints[i]);
    var km = (total/1000).toFixed(2);
    L.polyline(_measurePoints, {color:'#FFB800', weight:2, dashArray:'6,4'}).addTo(_measureLayer);
    L.popup().setLatLng(e.latlng).setContent('<b>Distance : '+km+' km</b><br><small>Clic droit pour effacer</small>').openOn(map);
  }
});
map.on('contextmenu', function() {
  if (_measureActive) { _measureLayer.clearLayers(); _measurePoints = []; map.closePopup(); }
});

function updateRoutes(json_str) {
  try {
    var data = typeof json_str === 'string' ? JSON.parse(json_str) : json_str;
    layerRoutes.clearLayers(); layerClients.clearLayers(); layerDepots.clearLayers();
    (data.depots||[]).forEach(function(d){ addDepot(d); });
    (data.routes||[]).forEach(function(r, ridx) {
      var color = r.color || ['#3B82F6','#10B981','#8B5CF6','#F59E0B','#EC4899'][ridx%5];
      var coords = [];
      (r.stops||[]).forEach(function(s,sidx) {
        var c = s.client || {};
        if (c.latitude && c.longitude) {
          addClient({id:c.id||sidx, name:c.name||'Client', lat:c.latitude, lon:c.longitude,
            demand_kg:c.demand_kg||0, ready_time:c.ready_time||0, due_time:c.due_time||1440,
            priority:c.priority||3, client_type:c.client_type||'standard', order_num:sidx+1, color:color});
          coords.push([c.latitude, c.longitude]);
        }
      });
      if (r.depot_coords) coords.unshift(r.depot_coords);
      if (coords.length >= 2) addRoute({coords:coords, color:color, label:r.label||'Route', vehicle_id:r.vehicle_id, is_straight:true});
    });
    fitBoundsAll();
  } catch(e) { console.error('updateRoutes error', e); }
}

function updateMarkers(json_str) {
  try {
    var data = typeof json_str === 'string' ? JSON.parse(json_str) : json_str;
    layerClients.clearLayers(); layerDepots.clearLayers();
    (data.depots||[]).forEach(function(d){ addDepot(d); });
    (data.clients||[]).forEach(function(c){ addClient(c); });
    fitBoundsAll();
  } catch(e) { console.error('updateMarkers error', e); }
}

var historyData = [], historyTimer = null, historySpeed = 1, historyIdx = 0;
function loadHistory(json_str) { historyData = JSON.parse(json_str); historyIdx = 0; }
function historyStep(idx) {
  historyIdx = idx;
  if (!historyData[idx]) return;
  layerVehicles.clearLayers();
  (historyData[idx].vehicles||[]).forEach(function(v){ updateVehicle(v); });
}

function exportPNG() { _call('on_marker_clicked', JSON.stringify({table:'export',id:0})); }

map.on('contextmenu', function(e) { _call('on_map_rightclick', JSON.stringify({lat:e.latlng.lat,lng:e.latlng.lng})); });
</script>
</body></html>"""


# ── MapBridge (QObject exposé au JS via QWebChannel) ──────────────────────────

class MapBridge(QObject):
    """Pont bidirectionnel Python ↔ JavaScript."""

    # Signaux JS→Python
    marker_clicked  = pyqtSignal(str, int)   # table, id
    map_rightclicked = pyqtSignal(float, float)
    zone_drawn      = pyqtSignal(str)         # GeoJSON str
    address_found   = pyqtSignal(float, float, str)
    export_requested = pyqtSignal()

    ready_signal = pyqtSignal()  # exposé côté JS pour synchronisation

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(str)
    def on_marker_clicked(self, json_str: str):
        try:
            d = json.loads(json_str)
            if d.get("table") == "export":
                self.export_requested.emit()
            else:
                self.marker_clicked.emit(d.get("table", ""), int(d.get("id", 0)))
        except Exception:
            pass

    @pyqtSlot(str)
    def on_map_rightclick(self, json_str: str):
        try:
            d = json.loads(json_str)
            self.map_rightclicked.emit(float(d["lat"]), float(d["lng"]))
        except Exception:
            pass

    @pyqtSlot(str)
    def on_zone_drawn(self, geojson_str: str):
        self.zone_drawn.emit(geojson_str)

    @pyqtSlot(str)
    def on_address_found(self, json_str: str):
        try:
            d = json.loads(json_str)
            self.address_found.emit(float(d["lat"]), float(d["lon"]), d.get("name", ""))
        except Exception:
            pass


# ── Dialogue zone dessinée ─────────────────────────────────────────────────────

class _ZoneDialog(QDialog):
    def __init__(self, geojson_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouvelle zone")
        self.geojson_str = geojson_str
        self.setMinimumWidth(360)
        self.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            f"QLineEdit,QComboBox{{background:{C['card']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:4px 8px;}}"
        )
        f = QFormLayout(self)
        self.name_edit = QLineEdit("Zone sans nom")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["livraison", "zfe", "exclusion", "autre"])
        self.color_edit = QLineEdit("#00D4FF")
        f.addRow("Nom :", self.name_edit)
        f.addRow("Type :", self.type_combo)
        f.addRow("Couleur :", self.color_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        f.addRow(btns)


# ── Panneau couches (dock gauche) ──────────────────────────────────────────────

class _LayerDock(QWidget):
    layer_toggled = pyqtSignal(str, bool)
    basemap_changed = pyqtSignal(str)

    LAYERS = [
        ("depots",   " Dépôts"),
        ("clients",  " Clients"),
        ("routes",   " Routes"),
        ("vehicles", " Véhicules live"),
        ("heatmap",  " Heatmap"),
        ("zones",    " Zones"),
        ("alerts",   " Alertes"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C['bg2']};color:{C['text']};")
        self.setMinimumWidth(200)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        lbl = QLabel("COUCHES")
        lbl.setStyleSheet(f"color:{C['text2']};font-size:10px;font-weight:700;")
        lay.addWidget(lbl)

        self._checks = {}
        defaults_on = {"depots", "clients", "routes", "vehicles", "zones", "alerts"}
        for key, label in self.LAYERS:
            cb = QCheckBox(label)
            cb.setChecked(key in defaults_on)
            cb.setStyleSheet(f"color:{C['text']};font-size:12px;")
            cb.toggled.connect(lambda checked, k=key: self.layer_toggled.emit(k, checked))
            self._checks[key] = cb
            lay.addWidget(cb)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C['border']};max-height:1px;border:none;margin:6px 0;")
        lay.addWidget(sep)

        lbl2 = QLabel("FOND DE CARTE")
        lbl2.setStyleSheet(f"color:{C['text2']};font-size:10px;font-weight:700;")
        lay.addWidget(lbl2)
        self.basemap_combo = QComboBox()
        self.basemap_combo.addItems(["Standard", "Dark", "Satellite", "Terrain"])
        self.basemap_combo.setStyleSheet(
            f"background:{C['card']};color:{C['text']};border:1px solid {C['border']};border-radius:4px;padding:4px;"
        )
        self.basemap_combo.currentTextChanged.connect(self.basemap_changed)
        lay.addWidget(self.basemap_combo)
        lay.addStretch()


# ── Panneau info droite (dock) ────────────────────────────────────────────────

class _InfoDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C['bg2']};color:{C['text']};")
        self.setMinimumWidth(280)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lbl = QLabel("INFORMATIONS")
        lbl.setStyleSheet(f"color:{C['text2']};font-size:10px;font-weight:700;")
        lay.addWidget(lbl)
        self.content = QLabel("Cliquez sur un marqueur pour afficher les détails.")
        self.content.setWordWrap(True)
        self.content.setStyleSheet(f"color:{C['text']};font-size:12px;")
        lay.addWidget(self.content)
        lay.addStretch()

    def show_info(self, html_text: str):
        self.content.setText(html_text)


# ── Barre d'outils verticale ──────────────────────────────────────────────────

def _tool_btn(label: str, tooltip: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setToolTip(tooltip)
    btn.setFixedSize(44, 44)
    btn.setStyleSheet(
        f"QPushButton{{background:{C['toolbar']};color:{C['text']};border:none;"
        f"border-radius:6px;font-size:18px;}}"
        f"QPushButton:hover{{background:{C['card']};color:{C['accent']};}}"
    )
    return btn


# ── Géocodage asynchrone ──────────────────────────────────────────────────────

class _GeocoderThread(QThread):
    result = pyqtSignal(float, float, str)
    error  = pyqtSignal(str)

    def __init__(self, query: str, parent=None):
        super().__init__(parent)
        self._query = query

    def run(self):
        try:
            import requests as _req
            r = _req.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": self._query, "format": "json", "limit": 1},
                headers={"User-Agent": "CityPulse/5.40"},
                timeout=8,
            )
            data = r.json()
            if data:
                self.result.emit(float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", ""))
            else:
                self.error.emit("Adresse introuvable")
        except Exception as e:
            self.error.emit(str(e))


# ── Widget principal ───────────────────────────────────────────────────────────

class MapWidget(QWidget):
    """Carte interactive Leaflet v2 — PHASE 4-A."""

    # Signaux sortants
    marker_clicked   = pyqtSignal(str, int)
    zone_drawn       = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main_window    = main_window
        self._bridge        = None
        self._channel       = None
        self._compare_mode  = False
        self._current_routes = None
        self._setup_ui()
        self._load_map()

    def _setup_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Toolbar verticale gauche ──────────────────────────────────
        toolbar_frame = QFrame()
        toolbar_frame.setFixedWidth(52)
        toolbar_frame.setStyleSheet(f"background:{C['toolbar']};")
        tb_lay = QVBoxLayout(toolbar_frame)
        tb_lay.setContentsMargins(4, 8, 4, 8)
        tb_lay.setSpacing(4)

        self._btn_measure  = _tool_btn("", "Mesurer une distance (cliquer deux points)")
        self._btn_search   = _tool_btn("", "Rechercher une adresse (Nominatim)")
        self._btn_center   = _tool_btn("", "Centrer sur tous les éléments")
        self._btn_compare  = _tool_btn("", "Vue comparative (2 cartes)")
        self._btn_export   = _tool_btn("", "Exporter la carte en PNG")
        self._btn_full     = _tool_btn("", "Plein écran")
        self._btn_settings = _tool_btn("", "Paramètres de la carte")
        self._btn_help     = _tool_btn("", "Aide — Carte interactive")
        apply_action_button(self._btn_measure,  "move",        C["text"],    C["toolbar"], C["card"], 20)
        apply_action_button(self._btn_search,   "search",      C["text"],    C["toolbar"], C["card"], 20)
        apply_action_button(self._btn_center,   "crosshair",   C["text"],    C["toolbar"], C["card"], 20)
        apply_action_button(self._btn_compare,  "columns",     C["text"],    C["toolbar"], C["card"], 20)
        apply_action_button(self._btn_export,   "download",    C["text"],    C["toolbar"], C["card"], 20)
        apply_action_button(self._btn_full,     "maximize",    C["text"],    C["toolbar"], C["card"], 20)
        apply_action_button(self._btn_settings, "settings",    C["accent"],  C["toolbar"], C["card"], 20)
        apply_action_button(self._btn_help,     "help-circle", C["text"],    C["toolbar"], C["card"], 20)

        self._measure_active = False
        self._btn_measure.clicked.connect(self._toggle_measure)
        self._btn_search.clicked.connect(self._open_address_search)
        self._btn_center.clicked.connect(lambda: self._run_js("fitBoundsAll();"))
        self._btn_compare.clicked.connect(self._toggle_compare)
        self._btn_export.clicked.connect(self._export_png)
        self._btn_full.clicked.connect(self._toggle_fullscreen)
        self._btn_settings.clicked.connect(self._open_map_settings)
        self._btn_help.clicked.connect(lambda: show_help(self, "map"))

        for b in [self._btn_measure, self._btn_search, self._btn_center]:
            tb_lay.addWidget(b)
        tb_lay.addStretch()
        for b in [self._btn_compare, self._btn_export, self._btn_full, self._btn_settings, self._btn_help]:
            tb_lay.addWidget(b)

        outer.addWidget(toolbar_frame)

        # ── Dock couches gauche ───────────────────────────────────────
        self._layer_dock_widget = _LayerDock()
        self._layer_dock_widget.layer_toggled.connect(self._on_layer_toggle)
        self._layer_dock_widget.basemap_changed.connect(self._on_basemap_change)

        layer_dock = QDockWidget("Couches")
        layer_dock.setWidget(self._layer_dock_widget)
        layer_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        layer_dock.setMinimumWidth(200)
        layer_dock.setMaximumWidth(220)
        layer_dock.setStyleSheet(
            f"QDockWidget{{background:{C['bg2']};color:{C['text']};}}"
            f"QDockWidget::title{{background:{C['toolbar']};color:{C['text2']};padding:4px 8px;font-size:10px;font-weight:700;}}"
        )

        # ── Zone centrale (carte + animation) ─────────────────────────
        central = QWidget()
        central_lay = QVBoxLayout(central)
        central_lay.setContentsMargins(0, 0, 0, 0)
        central_lay.setSpacing(0)

        # Vue principale
        self._map_stack = QSplitter(Qt.Orientation.Horizontal)
        if HAS_WEB:
            self._web = QWebEngineView()
            _s = self._web.settings()
            _s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            _s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            self._map_stack.addWidget(self._web)
        else:
            no = QLabel(WEBENGINE_FALLBACK_LABEL)
            no.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no.setStyleSheet(f"color:{C['text2']};font-size:14px;")
            self._map_stack.addWidget(no)

        central_lay.addWidget(self._map_stack, 1)

        # ── Dock info droite ──────────────────────────────────────────
        self._info_dock_widget = _InfoDock()
        info_dock = QDockWidget("Détails")
        info_dock.setWidget(self._info_dock_widget)
        info_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        info_dock.setMinimumWidth(280)
        info_dock.setMaximumWidth(320)
        info_dock.setVisible(False)   # s'ouvre au clic sur marker
        info_dock.setStyleSheet(layer_dock.styleSheet())
        self._info_dock = info_dock

        # ── Assemblage horizontal ─────────────────────────────────────
        content = QSplitter(Qt.Orientation.Horizontal)
        content.addWidget(layer_dock)
        content.addWidget(central)
        content.addWidget(info_dock)
        content.setSizes([210, 800, 0])
        content.setHandleWidth(2)
        content.setStyleSheet(f"QSplitter::handle{{background:{C['border']};}}")

        outer.addWidget(content, 1)

    # ── Chargement de la carte ────────────────────────────────────────────────

    def _load_map(self):
        if not HAS_WEB:
            return
        import json as _j
        try:
            cfg = _j.load(open(settings_json_path(), encoding="utf-8"))
            lat    = cfg.get("map", {}).get("default_lat", 33.5731)
            lon    = cfg.get("map", {}).get("default_lon", -7.5898)
            zoom   = cfg.get("map", {}).get("default_zoom", 12)
            basemap = cfg.get("map", {}).get("default_layer", "Standard")
        except Exception:
            lat, lon, zoom, basemap = 33.5731, -7.5898, 12, "Standard"

        html = LEAFLET_HTML.replace("{lat}", str(lat)).replace("{lon}", str(lon)) \
                           .replace("{zoom}", str(zoom)).replace("{basemap}", basemap)

        if HAS_WEBCHANNEL:
            self._bridge  = MapBridge(self)
            self._channel = QWebChannel(self._web.page())
            self._channel.registerObject("bridge", self._bridge)
            self._web.page().setWebChannel(self._channel)
            self._bridge.marker_clicked.connect(self._on_marker_clicked)
            self._bridge.zone_drawn.connect(self._on_zone_drawn)
            self._bridge.address_found.connect(self._on_address_found)
            self._bridge.export_requested.connect(self._export_png)

        self._web.setHtml(html, QUrl("qrc:///"))
        def _on_load_finished(ok):
            # Le HTML est chargé mais les CDN externes (Leaflet) peuvent encore télécharger.
            # On démarre le polling via _do_refresh() qui teste window.citypulseMapReady.
            QTimer.singleShot(500, self._do_refresh)
        self._web.loadFinished.connect(_on_load_finished)

    # ── JS runner ─────────────────────────────────────────────────────────────

    def _run_js(self, js: str):
        if HAS_WEB:
            self._web.page().runJavaScript(js)

    # ── Couches ───────────────────────────────────────────────────────────────

    def _on_layer_toggle(self, name: str, visible: bool):
        self._run_js(f"toggleLayer({json.dumps(name)}, {str(visible).lower()});")

    def _on_basemap_change(self, name: str):
        self._run_js(f"setBasemap({json.dumps(name)});")

    # ── Affichage routes (signal routes_ready) ────────────────────────────────

    def display_routes(self, result: dict):
        """Appelé par OptimizationWidget via signal routes_ready."""
        if not HAS_WEB:
            return
        self._current_routes = result

        conn = get_connection()
        depots = conn.execute("SELECT * FROM depots").fetchall()
        conn.close()

        depot_list = [
            {"id": d["id"], "name": d["name"], "lat": d["latitude"],
             "lon": d["longitude"], "address": d.get("address", ""),
             "manager": d.get("manager_name", ""), "phone": d.get("phone", "")}
            for d in depots
        ]

        dep_lat = depot_list[0]["lat"] if depot_list else 33.5731
        dep_lon = depot_list[0]["lon"] if depot_list else -7.5898

        routes_payload = []
        for i, route in enumerate(result.get("routes", [])):
            color = ALGO_COLORS[i % len(ALGO_COLORS)]
            vehicle = route.get("vehicle", {})
            reg = (vehicle.get("registration") or f"V{i+1}")
            stops = route.get("route", [])
            stop_list = []
            for s in stops:
                c = s.get("client", {})
                stop_list.append({
                    "client": {
                        "id": c.get("id", 0), "name": c.get("name", ""),
                        "latitude": c.get("latitude", 0), "longitude": c.get("longitude", 0),
                        "demand_kg": c.get("demand_kg", 0),
                        "ready_time": c.get("ready_time", 0), "due_time": c.get("due_time", 1440),
                        "priority": c.get("priority", 3), "client_type": c.get("client_type", "standard"),
                    }
                })
            dist = route.get("distance_km", 0)
            routes_payload.append({
                "color": color, "label": f"{reg} — {dist:.1f} km",
                "vehicle_id": i, "depot_coords": [dep_lat, dep_lon], "stops": stop_list
            })

        payload = {"depots": depot_list, "routes": routes_payload}
        js_str = json.dumps(payload, ensure_ascii=False)

        def _send(ready):
            if not ready:
                QTimer.singleShot(600, lambda: self._web.page().runJavaScript(
                    "typeof updateRoutes==='function'",
                    lambda r: self._run_js(f"updateRoutes({js_str});") if r else None
                ))
                return
            self._run_js(f"updateRoutes({js_str});")
            # Enrichir avec géométrie routière OSRM en arrière-plan
            self._fetch_osrm_geometry(routes_payload, dep_lat, dep_lon)

        self._web.page().runJavaScript("typeof updateRoutes==='function'", _send)
        self._info_dock.setVisible(True)

    def _fetch_osrm_geometry(self, routes_payload: list, dep_lat: float, dep_lon: float):
        """Lance le thread OSRM pour remplacer les lignes droites par les vraies routes."""
        if not HAS_REQUESTS:
            return
        from ..engine.distance import OSRM_BASE_URL
        routes_data = []
        for r in routes_payload:
            coords = [[dep_lat, dep_lon]]
            for s in r.get("stops", []):
                c = s.get("client", {})
                lat = c.get("latitude", 0)
                lon = c.get("longitude", 0)
                if lat and lon:
                    coords.append([float(lat), float(lon)])
            coords.append([dep_lat, dep_lon])  # retour dépôt
            if len(coords) >= 2:
                routes_data.append({"vehicle_id": r["vehicle_id"], "coords": coords})

        if not routes_data:
            return

        # Arrêter le thread précédent si encore actif
        if hasattr(self, "_osrm_thread") and self._osrm_thread.isRunning():
            self._osrm_thread.quit()

        self._osrm_thread = _OsrmGeometryThread(routes_data, OSRM_BASE_URL, parent=self)
        self._osrm_thread.route_ready.connect(
            lambda vid, coords_json: self._run_js(
                f"updateRouteGeometry({vid}, {json.dumps(coords_json)});"
            )
        )
        self._osrm_thread.start()

    # ── Marker click ──────────────────────────────────────────────────────────

    def _on_marker_clicked(self, table: str, id_: int):
        self.marker_clicked.emit(table, id_)
        self._info_dock.setVisible(True)
        if table == "clients":
            conn = get_connection()
            r = conn.execute("SELECT * FROM clients WHERE id= ?", (id_,)).fetchone()
            conn.close()
            if r:
                info = f"<b>{r['name']}</b><br>Demande: {r['demand_kg']} kg<br>Priorité: {r['priority']}"
                self._info_dock_widget.show_info(info)
        elif table == "depots":
            conn = get_connection()
            r = conn.execute("SELECT * FROM depots WHERE id= ?", (id_,)).fetchone()
            conn.close()
            if r:
                info = f"<b>{r['name']}</b><br>{r.get('address','')}"
                self._info_dock_widget.show_info(info)
        elif table == "vehicles":
            conn = get_connection()
            r = conn.execute("SELECT * FROM vehicles WHERE id= ?", (id_,)).fetchone()
            conn.close()
            if r:
                info = (f"<b>{r['registration']}</b><br>"
                        f"{r.get('brand','')} {r.get('model','')}<br>"
                        f"Capacité : {r.get('capacity_kg',0)} kg<br>"
                        f"Statut : {r.get('status','')}")
                self._info_dock_widget.show_info(info)
        elif table == "export":
            pass

    # ── Zone dessinée ─────────────────────────────────────────────────────────

    def _on_address_found(self, lat: float, lon: float, name: str):
        """Reçu quand le JS trouve une adresse via géocodage côté carte."""
        self._push(f"map.setView([{lat},{lon}], 15);")
        show_toast(self.window(), f"Adresse trouvée : {name}", "info")

    def _push(self, js: str):
        """Alias de _run_js pour usage interne cohérent."""
        self._run_js(js)

    def _on_zone_drawn(self, geojson_str: str):
        dlg = _ZoneDialog(geojson_str, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name      = dlg.name_edit.text().strip() or "Zone"
        zone_type = dlg.type_combo.currentText()
        color     = dlg.color_edit.text().strip()

        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO zones (name, zone_type, geojson, color, created_at) "
            "VALUES (?,?,?,?,?)",
            (name, zone_type, geojson_str, color, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        log_action("ZONE_CREATED", f"Zone '{name}' type={zone_type}")
        show_toast(self.window(), f"Zone « {name} » sauvegardée", "success")
        self.zone_drawn.emit(geojson_str)
        # Redessiner couche zones
        self._load_zones()

    # ── Outils toolbar ────────────────────────────────────────────────────────

    def _toggle_measure(self):
        self._measure_active = not getattr(self, "_measure_active", False)
        self._run_js(f"toggleMeasure({'true' if self._measure_active else 'false'});")
        apply_action_button(
            self._btn_measure,
            "move",
            C["accent"] if self._measure_active else C["text"],
            C["toolbar"], C["card"], 20,
        )
        if self._measure_active:
            show_toast(self.window(),
                       "Mode mesure activé — cliquez pour poser des points, clic droit pour effacer",
                       "info")

    def _open_address_search(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Rechercher une adresse")
        dlg.setMinimumWidth(380)
        dlg.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            f"QLineEdit{{background:{C['card']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:4px 8px;}}"
        )
        f = QFormLayout(dlg)
        addr = QLineEdit()
        addr.setPlaceholderText("Ex: Avenue Hassan II, Casablanca")
        f.addRow("Adresse :", addr)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        f.addRow(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted or not addr.text().strip():
            return
        self._geocode_address(addr.text().strip())

    def _geocode_address(self, query: str):
        if not query.strip():
            return
        t = _GeocoderThread(query, self)
        t.result.connect(lambda lat, lon, name: (
            self._run_js(f"map.setView([{lat},{lon}], 15);"),
            show_toast(self.window(), f"Adresse : {name[:80]}", "info")
        ))
        t.error.connect(lambda msg: show_toast(self.window(), f"Géocodage: {msg}", "error"))
        t.start()
        self._geocoder_thread = t  # garder référence

    def _toggle_compare(self):
        self._compare_mode = not self._compare_mode
        if self._compare_mode:
            self._show_compare_view()
        else:
            self._hide_compare_view()

    def _show_compare_view(self):
        if not HAS_WEB:
            return
        self._web2 = QWebEngineView()
        self._map_stack.addWidget(self._web2)
        self._map_stack.setSizes([600, 600])
        # Charger la même carte dans le second iframe
        html2 = self._web.page().url().toString()
        import json as _j
        try:
            cfg = _j.load(open(settings_json_path(), encoding="utf-8"))
            lat = cfg["map"].get("default_lat", 33.5731)
            lon = cfg["map"].get("default_lon", -7.5898)
        except Exception:
            lat, lon = 33.5731, -7.5898
        html = LEAFLET_HTML.replace("{lat}", str(lat)).replace("{lon}", str(lon)) \
                           .replace("{zoom}", "12").replace("{basemap}", "Dark")
        self._web2.setHtml(html, QUrl("qrc:///"))
        show_toast(self.window(), "Vue comparative activée", "info")

    def _hide_compare_view(self):
        if hasattr(self, "_web2"):
            self._web2.setParent(None)
            self._web2.deleteLater()
            del self._web2
        self._map_stack.setSizes([1, 0])
        show_toast(self.window(), "Vue comparative désactivée", "info")

    def _export_png(self):
        if not HAS_WEB:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter la carte", "carte.png", "PNG (*.png)")
        if not path:
            return
        self._web.grab().save(path, "PNG")
        show_toast(self.window(), f"Carte exportée : {path}", "success")
        log_action("MAP_EXPORT_PNG", path)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _open_map_settings(self):
        self.main_window._nav_to(15)
        w = self.main_window.stack.widget(15)
        if hasattr(w, "_tabs"):
            w._tabs.setCurrentIndex(1)  # onglet Carte

    # ── Chargement données depuis BDD ─────────────────────────────────────────

    def _load_all_layers(self):
        if not HAS_WEB:
            return
        self._run_js("clearAll();")
        self._load_depots()
        self._load_clients()
        self._load_zones()
        self._load_alerts()
        self._load_vehicles()
        # Routes : priorité à l'optimisation en mémoire, sinon depuis la BDD
        if getattr(self, "_current_routes", None):
            QTimer.singleShot(200, lambda: self.display_routes(self._current_routes))
        else:
            self._load_routes_from_db()

    def _load_routes_from_db(self):
        """Charge les tournées les plus récentes depuis routes + route_stops."""
        try:
            conn = get_connection()
            routes = conn.execute(
                """SELECT r.id, r.algorithm, r.total_distance_km,
                          v.registration, v.id as vehicle_id,
                          d.latitude as dep_lat, d.longitude as dep_lon
                   FROM routes r
                   LEFT JOIN vehicles v ON v.id = r.vehicle_id
                   LEFT JOIN depots d ON d.id = r.depot_id
                   WHERE r.archived = 0 OR r.archived IS NULL
                   ORDER BY r.created_at DESC
                   LIMIT 40"""
            ).fetchall()

            if not routes:
                conn.close()
                return

            # Grouper par date de création (prendre uniquement le dernier batch)
            routes_payload = []
            for i, route in enumerate(routes):
                stops_rows = conn.execute(
                    """SELECT rs.stop_order, c.id, c.name, c.latitude, c.longitude,
                              c.demand_kg, c.ready_time, c.due_time
                       FROM route_stops rs
                       JOIN clients c ON c.id = rs.client_id
                       WHERE rs.route_id = ?
                       ORDER BY rs.stop_order""",
                    (route["id"],)
                ).fetchall()

                stop_list = []
                coords_valid = False
                for s in stops_rows:
                    lat = s["latitude"]
                    lon = s["longitude"]
                    if lat and lon:
                        coords_valid = True
                    stop_list.append({
                        "client": {
                            "id": s["id"], "name": s["name"] or "",
                            "latitude": float(lat) if lat else 0,
                            "longitude": float(lon) if lon else 0,
                            "demand_kg": s["demand_kg"] or 0,
                            "ready_time": s["ready_time"] or 0,
                            "due_time": s["due_time"] or 1440,
                            "priority": 3, "client_type": "standard",
                        }
                    })

                if not coords_valid:
                    continue

                dep_lat = route["dep_lat"] or 33.5731
                dep_lon = route["dep_lon"] or -7.5898
                color = ALGO_COLORS[i % len(ALGO_COLORS)]
                reg = route["registration"] or f"V{i+1}"
                dist = route["total_distance_km"] or 0
                routes_payload.append({
                    "color": color,
                    "label": f"{reg} — {dist:.1f} km",
                    "vehicle_id": route["vehicle_id"] or i,
                    "depot_coords": [float(dep_lat), float(dep_lon)],
                    "stops": stop_list,
                })

            conn.close()

            if not routes_payload:
                return

            # Dépôts pour la carte
            conn2 = get_connection()
            depots = conn2.execute("SELECT * FROM depots").fetchall()
            conn2.close()
            depot_list = [
                {"id": d["id"], "name": d["name"],
                 "lat": float(d["latitude"]), "lon": float(d["longitude"]),
                 "address": d.get("address", ""), "manager": d.get("manager_name", ""),
                 "phone": d.get("phone", "")}
                for d in depots if d["latitude"] and d["longitude"]
            ]

            payload = {"depots": depot_list, "routes": routes_payload}
            js_str = json.dumps(payload, ensure_ascii=False)
            self._run_js(f"updateRoutes({js_str});")

            # Enrichir avec géométrie OSRM
            dep_lat = depot_list[0]["lat"] if depot_list else 33.5731
            dep_lon = depot_list[0]["lon"] if depot_list else -7.5898
            self._fetch_osrm_geometry(routes_payload, dep_lat, dep_lon)

        except Exception:
            logger.debug("_load_routes_from_db erreur", exc_info=True)

    def _load_depots(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM depots").fetchall()
        conn.close()
        parts = []
        for d in rows:
            lat = d["latitude"]
            lon = d["longitude"]
            if not lat or not lon:
                continue
            data = {"id": d["id"], "name": d["name"],
                    "lat": float(lat), "lon": float(lon),
                    "address": d.get("address", ""),
                    "manager": d.get("manager_name", ""), "phone": d.get("phone", "")}
            parts.append(f"addDepot({json.dumps(data, ensure_ascii=False)});")
        if parts:
            self._run_js("".join(parts))

    def _load_clients(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT id,name,latitude,longitude,demand_kg,ready_time,due_time,priority,client_type "
            "FROM clients WHERE archived=0"
        ).fetchall()
        conn.close()
        parts = []
        for i, c in enumerate(rows):
            lat = c["latitude"]
            lon = c["longitude"]
            if not lat or not lon:
                continue
            color = ALGO_COLORS[i % len(ALGO_COLORS)]
            data = {"id": c["id"], "name": c["name"],
                    "lat": float(lat), "lon": float(lon),
                    "demand_kg": c["demand_kg"] or 0,
                    "ready_time": c["ready_time"] or 0, "due_time": c["due_time"] or 1440,
                    "priority": c["priority"] or 3, "client_type": c["client_type"] or "standard",
                    "order_num": i + 1, "color": color}
            parts.append(f"addClient({json.dumps(data, ensure_ascii=False)});")
        if parts:
            self._run_js("".join(parts))

    def _load_zones(self):
        self._run_js("layerZones.clearLayers();")
        try:
            conn = get_connection()
            rows = conn.execute("SELECT name,zone_type,geojson,color FROM zones").fetchall()
            conn.close()
            parts = []
            for z in rows:
                if not z["geojson"]:
                    continue
                data = {"name": z["name"], "zone_type": z["zone_type"],
                        "geojson": z["geojson"], "color": z.get("color", "#00D4FF")}
                parts.append(f"addZone({json.dumps(data, ensure_ascii=False)});")
            if parts:
                self._run_js("".join(parts))
        except Exception:
            pass

    def _load_alerts(self):
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT n.*, c.latitude, c.longitude FROM notifications n "
                "LEFT JOIN clients c ON n.related_id=c.id "
                "WHERE n.is_read=0 AND n.severity IN ('danger','warning') LIMIT 20"
            ).fetchall()
            conn.close()
            parts = []
            for n in rows:
                if n["latitude"] and n["longitude"]:
                    data = {"lat": n["latitude"], "lon": n["longitude"],
                            "message": n.get("title", "Alerte"), "severity": n.get("severity", "warning")}
                    parts.append(f"addAlert({json.dumps(data, ensure_ascii=False)});")
            if parts:
                self._run_js("".join(parts))
        except Exception:
            pass

    def _load_heatmap(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT latitude, longitude, demand_kg FROM clients WHERE archived=0"
        ).fetchall()
        conn.close()
        pts = [[r["latitude"], r["longitude"], min(1.0, (r["demand_kg"] or 0) / 1000.0)]
               for r in rows if r["latitude"] and r["longitude"]]
        self._run_js(f"updateHeatmap({json.dumps(pts)});")

    def _load_vehicles(self):
        """Affiche chaque véhicule à la position de son dépôt (ou dernier arrêt connu)."""
        try:
            conn = get_connection()
            rows = conn.execute("""
                SELECT v.id, v.registration, v.brand, v.status,
                       d.latitude, d.longitude, d.name as depot_name
                FROM vehicles v
                LEFT JOIN depots d ON v.depot_id = d.id
                WHERE COALESCE(v.status,'disponible') NOT IN ('hors_service','archive','archivé')
            """).fetchall()
            conn.close()
            parts = []
            for v in rows:
                lat = v["latitude"] or 0.0
                lon = v["longitude"] or 0.0
                if not lat or not lon:
                    continue
                reg = v["registration"] or f"V{v['id']}"
                st  = v["status"] or "disponible"
                data = {
                    "id": v["id"], "lat": lat, "lon": lon,
                    "registration": reg, "status": st,
                    "is_late": False, "speed_kmh": 0,
                    "next_stop": v["depot_name"] or "Dépôt",
                }
                parts.append(f"updateVehicle({json.dumps(data, ensure_ascii=False)});")
            if parts:
                self._run_js("".join(parts))
        except Exception:
            logger.debug("_load_vehicles error", exc_info=True)

    # ── Méthodes publiques appelées par Python→JS ─────────────────────────────

    def update_routes(self, payload: dict):
        self._run_js(f"updateRoutes({json.dumps(payload, ensure_ascii=False)});")

    def update_markers(self, payload: dict):
        self._run_js(f"updateMarkers({json.dumps(payload, ensure_ascii=False)});")

    def toggle_layer(self, name: str, visible: bool):
        self._run_js(f"toggleLayer({json.dumps(name)}, {str(visible).lower()});")

    def set_basemap(self, name: str):
        self._run_js(f"setBasemap({json.dumps(name)});")

    def center_on(self, lat: float = None, lon: float = None, zoom: int = 15):
        if lat is not None and lon is not None:
            self._run_js(f"centerOn({lat}, {lon}, {zoom});")
        else:
            self._run_js("fitBoundsAll();")

    # ── refresh_data (navigation) ─────────────────────────────────────────────

    def retranslate_ui(self, lang: str):
        pass

    def refresh_data(self):
        if not HAS_WEB:
            return
        self._do_refresh()

    def _do_refresh(self, _attempt: int = 0):
        """Charge les couches dès que Leaflet est prêt (flag window.citypulseMapReady).
        Retry toutes les 700ms, abandon après 20 tentatives (~14s)."""
        if _attempt > 20:
            logger.warning("MapWidget: abandon chargement couches après 14s")
            return

        def _after_check(ready):
            if not ready:
                QTimer.singleShot(700, lambda: self._do_refresh(_attempt + 1))
                return
            try:
                self._run_js("map.invalidateSize();")
                self._load_all_layers()
                self._load_heatmap()
                QTimer.singleShot(300, lambda: self._run_js(
                    "map.invalidateSize(); fitBoundsAll();"
                ))
                self._update_weather_banner()
            except Exception:
                logger.exception("MapWidget._do_refresh: erreur chargement couches")

        self._web.page().runJavaScript(
            "window.citypulseMapReady === true",
            _after_check
        )

    def _update_weather_banner(self):
        """Lance la récupération météo en arrière-plan (non bloquant)."""
        if not HAS_WEB:
            return
        try:
            from ..services import weather_service as ws
            key = ws.resolve_owm_api_key()
            if not key:
                return
            try:
                with open(settings_json_path(), encoding="utf-8") as cf:
                    cfg = json.load(cf)
                lat = float(cfg.get("map", {}).get("default_lat", 33.5731))
                lon = float(cfg.get("map", {}).get("default_lon", -7.5898))
            except Exception:
                lat, lon = 33.5731, -7.5898
            # Annuler le thread précédent s'il tourne encore
            if hasattr(self, "_weather_thread") and self._weather_thread.isRunning():
                self._weather_thread.quit()
            self._weather_thread = _WeatherThread(lat, lon, key, parent=self)
            self._weather_thread.result.connect(
                lambda payload: self._run_js(f"showWeather({payload});")
            )
            self._weather_thread.start()
        except Exception:
            logger.debug("weather banner", exc_info=True)

    def apply_dual_scenario_routes(self, left_payload: dict, right_payload: dict):
        """Affiche deux jeux de routes (carte scindée)."""
        if not HAS_WEB:
            return
        self._show_compare_view()

        def _push():
            self.update_routes(left_payload or {"depots": [], "routes": []})
            if hasattr(self, "_web2") and self._web2:
                js = json.dumps(right_payload or {"depots": [], "routes": []}, ensure_ascii=False)
                self._web2.page().runJavaScript(f"updateRoutes({js});")

        QTimer.singleShot(450, _push)
