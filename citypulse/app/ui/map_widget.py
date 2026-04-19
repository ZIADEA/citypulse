import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from ..database.db_manager import get_connection
from .help_dialog import show_help


LEAFLET_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
    body {{ margin: 0; padding: 0; }}
    #map {{ width: 100%; height: 100vh; background: #f0f0f0; }}
</style>
</head><body>
<div id="map"></div>
<script>
var map = L.map('map').setView([{lat}, {lon}], 12);

var tileLayers = {{
    'Standard': L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '© OpenStreetMap'
    }}),
    'Dark': L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        attribution: '© CartoDB'
    }}),
    'Satellite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        attribution: '© Esri'
    }})
}};
tileLayers['Standard'].addTo(map);
L.control.layers(tileLayers).addTo(map);

var markersGroup = L.layerGroup().addTo(map);
var routesGroup = L.layerGroup().addTo(map);

var COLORS = ['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c','#e67e22','#2980b9','#27ae60','#c0392b'];

function clearAll() {{
    markersGroup.clearLayers();
    routesGroup.clearLayers();
}}

function addDepot(lat, lon, name) {{
    var icon = L.divIcon({{
        className: 'depot-marker',
        html: '<div style="background:#1a1a2e;color:#89b4fa;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:bold;border:3px solid #89b4fa;box-shadow:0 2px 12px rgba(137,180,250,0.4);">D</div>',
        iconSize: [36, 36],
        iconAnchor: [18, 18]
    }});
    L.marker([lat, lon], {{icon: icon}}).addTo(markersGroup).bindPopup('<b>' + name + '</b><br>Dépôt principal');
}}

function addClient(lat, lon, name, demand, order, color, delay) {{
    var borderColor = delay > 0 ? '#e74c3c' : color;
    var icon = L.divIcon({{
        className: 'client-marker',
        html: '<div style="background:' + color + ';color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;border:2px solid ' + borderColor + ';box-shadow:0 2px 6px rgba(0,0,0,0.4);">' + order + '</div>',
        iconSize: [28, 28],
        iconAnchor: [14, 14]
    }});
    var popup = '<b>' + name + '</b><br>Demande: ' + demand + ' kg<br>Ordre: #' + order;
    if (delay > 0) popup += '<br><span style="color:#e74c3c;font-weight:bold">Retard: ' + delay.toFixed(0) + ' min</span>';
    L.marker([lat, lon], {{icon: icon}}).addTo(markersGroup).bindPopup(popup);
}}

function addRoute(coords, color) {{
    L.polyline(coords, {{color: color, weight: 4, opacity: 0.85, dashArray: null, lineCap: 'round', lineJoin: 'round'}}).addTo(routesGroup);
}}

function fitBounds() {{
    var allLayers = [];
    markersGroup.eachLayer(function(l) {{ if(l.getLatLng) allLayers.push(l.getLatLng()); }});
    if (allLayers.length > 0) map.fitBounds(L.latLngBounds(allLayers).pad(0.1));
}}
</script></body></html>"""


class MapWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #ecedf2; padding: 8px;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Carte Interactive")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        tb_layout.addWidget(title)
        tb_layout.addStretch()

        self.center_btn = QPushButton("Recentrer")
        self.center_btn.clicked.connect(self._recenter)
        tb_layout.addWidget(self.center_btn)

        self.refresh_btn = QPushButton("Rafraîchir")
        self.refresh_btn.clicked.connect(self._show_clients)
        tb_layout.addWidget(self.refresh_btn)

        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "map"))
        tb_layout.addWidget(help_btn)

        layout.addWidget(toolbar)

        if HAS_WEB:
            self.web_view = QWebEngineView()
            self._load_map()
            layout.addWidget(self.web_view)
        else:
            no_web = QLabel("PyQt6-WebEngine non installé.\nInstallez avec: pip install PyQt6-WebEngine")
            no_web.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_web.setFont(QFont("Segoe UI", 14))
            no_web.setStyleSheet("color: #888888;")
            layout.addWidget(no_web)

    def _load_map(self, lat=33.5731, lon=-7.5898):
        if not HAS_WEB:
            return
        html = LEAFLET_HTML.format(lat=lat, lon=lon)
        self.web_view.setHtml(html)

    def _run_js(self, js):
        if HAS_WEB:
            self.web_view.page().runJavaScript(js)

    def _recenter(self):
        conn = get_connection()
        depot = conn.execute("SELECT * FROM depots ORDER BY id LIMIT 1").fetchone()
        conn.close()
        if depot:
            self._run_js(f"map.setView([{depot['latitude']}, {depot['longitude']}], 12);")

    def _show_clients(self):
        if not HAS_WEB:
            return
        conn = get_connection()
        clients = conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()
        depot = conn.execute("SELECT * FROM depots ORDER BY id LIMIT 1").fetchone()
        conn.close()

        self._run_js("clearAll();")
        if depot:
            self._run_js(f"addDepot({depot['latitude']}, {depot['longitude']}, '{depot['name']}');")

        for c in clients:
            name = c["name"].replace("'", "\\'")
            self._run_js(
                f"addClient({c['latitude']}, {c['longitude']}, '{name}', "
                f"{c['demand_kg']}, {c['id']}, '#3498db', 0);"
            )

        self._run_js("fitBounds();")

    def display_routes(self, result):
        if not HAS_WEB:
            return

        COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
                   '#1abc9c', '#e67e22', '#2980b9', '#27ae60', '#c0392b']

        self._run_js("clearAll();")

        # Get depot
        conn = get_connection()
        depot = conn.execute("SELECT * FROM depots ORDER BY id LIMIT 1").fetchone()
        conn.close()

        if depot:
            self._run_js(f"addDepot({depot['latitude']}, {depot['longitude']}, '{depot['name']}');")
            depot_lat, depot_lon = depot["latitude"], depot["longitude"]
        else:
            depot_lat, depot_lon = 33.5731, -7.5898

        for i, route_info in enumerate(result.get("routes", [])):
            if not route_info["route"]:
                continue
            color = COLORS[i % len(COLORS)]
            coords = [[depot_lat, depot_lon]]

            for order, stop in enumerate(route_info["route"], 1):
                c = stop["client"]
                lat, lon = c["latitude"], c["longitude"]
                name = c.get("name", "Client").replace("'", "\\'")
                demand = c.get("demand_kg", 0)
                delay = stop.get("delay", 0)
                self._run_js(
                    f"addClient({lat}, {lon}, '{name}', {demand}, {order}, '{color}', {delay});"
                )
                coords.append([lat, lon])

            coords.append([depot_lat, depot_lon])
            coords_json = json.dumps(coords)
            self._run_js(f"addRoute({coords_json}, '{color}');")

        self._run_js("fitBounds();")

    def refresh_data(self):
        self._show_clients()
