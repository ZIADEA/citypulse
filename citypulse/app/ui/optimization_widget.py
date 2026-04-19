import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QRadioButton, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QFrame, QGridLayout,
    QScrollArea, QTextEdit, QMessageBox, QButtonGroup, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help
from .toast import show_toast
from .loading_overlay import LoadingOverlay
from ..engine.greedy import greedy_vrp
from ..engine.two_opt import two_opt_vrp
from ..engine.ortools_solver import ortools_vrp, ORTOOLS_AVAILABLE


class OptimizationThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)

    def __init__(self, algo, clients, depot, vehicles, traffic, weather, params):
        super().__init__()
        self.algo = algo
        self.clients = clients
        self.depot = depot
        self.vehicles = vehicles
        self.traffic = traffic
        self.weather = weather
        self.params = params

    def run(self):
        try:
            if self.algo == "greedy":
                self.progress.emit("Calcul glouton en cours...")
                result = greedy_vrp(self.clients, self.depot, self.vehicles,
                                    self.traffic, self.weather)
            elif self.algo == "2opt":
                self.progress.emit("Optimisation 2-opt en cours...")
                result = two_opt_vrp(self.clients, self.depot, self.vehicles,
                                     self.traffic, self.weather,
                                     self.params.get("max_iterations", 1000))
            elif self.algo == "ortools":
                self.progress.emit("OR-Tools en cours...")
                result = ortools_vrp(self.clients, self.depot, self.vehicles,
                                     self.traffic, self.weather,
                                     self.params.get("time_limit", 30))
            else:
                result = {"error": "Algorithme inconnu"}
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"error": str(e)})


class OptimizationWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.results = {}
        self.threads = []
        self._setup_ui()
        self._overlay = LoadingOverlay(self)

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header
        _header = QHBoxLayout()
        title = QLabel("Moteur d'Optimisation IA")
        title.setObjectName("heading")
        _header.addWidget(title)
        _header.addStretch()
        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "optimization"))
        _header.addWidget(help_btn)
        main_layout.addLayout(_header)
        subtitle = QLabel("Configurez et lancez les algorithmes de résolution VRP")
        subtitle.setObjectName("subheading")
        main_layout.addWidget(subtitle)

        # Config section
        config_grid = QGridLayout()
        config_grid.setSpacing(16)

        # Traffic group
        traffic_group = QGroupBox("Conditions de trafic")
        tl = QVBoxLayout(traffic_group)
        self.traffic_buttons = QButtonGroup()
        traffic_options = [
            ("Fluide (×1.0)", 1.0), ("Chargé (×1.3)", 1.3),
            ("Heure de pointe (×1.7)", 1.7), ("Accident (×2.2)", 2.2),
        ]
        for i, (label, coeff) in enumerate(traffic_options):
            rb = QRadioButton(label)
            rb.coeff = coeff
            self.traffic_buttons.addButton(rb, i)
            tl.addWidget(rb)
            if i == 0:
                rb.setChecked(True)

        custom_traffic_h = QHBoxLayout()
        self.traffic_custom_rb = QRadioButton("Personnalisé :")
        self.traffic_custom_rb.coeff = 1.0
        self.traffic_buttons.addButton(self.traffic_custom_rb, len(traffic_options))
        self.traffic_custom_spin = QDoubleSpinBox()
        self.traffic_custom_spin.setRange(1.0, 5.0)
        self.traffic_custom_spin.setValue(1.0)
        self.traffic_custom_spin.setSingleStep(0.1)
        custom_traffic_h.addWidget(self.traffic_custom_rb)
        custom_traffic_h.addWidget(self.traffic_custom_spin)
        tl.addLayout(custom_traffic_h)
        config_grid.addWidget(traffic_group, 0, 0)

        # Weather group
        weather_group = QGroupBox("Conditions meteo")
        wl = QVBoxLayout(weather_group)
        self.weather_buttons = QButtonGroup()
        weather_options = [
            ("Ensoleille (x1.0)", 1.0), ("Pluie legere (x1.1)", 1.1),
            ("Pluie forte (x1.25)", 1.25), ("Neige (x1.6)", 1.6),
            ("Verglas (x2.0)", 2.0),
        ]
        for i, (label, coeff) in enumerate(weather_options):
            rb = QRadioButton(label)
            rb.coeff = coeff
            self.weather_buttons.addButton(rb, i)
            wl.addWidget(rb)
            if i == 0:
                rb.setChecked(True)
        config_grid.addWidget(weather_group, 0, 1)

        # Algorithm params
        params_group = QGroupBox("Parametres algorithmes")
        pl = QVBoxLayout(params_group)
        params_form = QGridLayout()

        params_form.addWidget(QLabel("Max itérations 2-opt :"), 0, 0)
        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(100, 5000)
        self.iter_spin.setValue(1000)
        params_form.addWidget(self.iter_spin, 0, 1)

        params_form.addWidget(QLabel("Temps CPU OR-Tools (s) :"), 1, 0)
        self.time_spin = QSpinBox()
        self.time_spin.setRange(5, 300)
        self.time_spin.setValue(30)
        params_form.addWidget(self.time_spin, 1, 1)

        params_form.addWidget(QLabel("Objectif :"), 2, 0)
        self.objective_combo = QComboBox()
        self.objective_combo.addItems(["Minimiser distance", "Minimiser coût", "Minimiser retards"])
        params_form.addWidget(self.objective_combo, 2, 1)

        pl.addLayout(params_form)
        config_grid.addWidget(params_group, 0, 2)
        main_layout.addLayout(config_grid)

        # Coefficient display
        self.coeff_label = QLabel("Coefficient final : ×1.00")
        self.coeff_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.coeff_label.setStyleSheet("color: #666666;")
        main_layout.addWidget(self.coeff_label)

        # Update coefficient display when radio buttons change
        self.traffic_buttons.buttonClicked.connect(self._update_coeff)
        self.weather_buttons.buttonClicked.connect(self._update_coeff)
        self.traffic_custom_spin.valueChanged.connect(self._update_coeff)

        # Launch buttons
        btn_layout = QHBoxLayout()
        self.btn_greedy = QPushButton("Glouton")
        self.btn_greedy.setMinimumHeight(44)
        self.btn_greedy.clicked.connect(lambda: self._run_algo("greedy"))
        self.btn_2opt = QPushButton("2-opt")
        self.btn_2opt.setMinimumHeight(44)
        self.btn_2opt.clicked.connect(lambda: self._run_algo("2opt"))
        self.btn_ortools = QPushButton("OR-Tools")
        self.btn_ortools.setMinimumHeight(44)
        self.btn_ortools.clicked.connect(lambda: self._run_algo("ortools"))
        if not ORTOOLS_AVAILABLE:
            self.btn_ortools.setEnabled(False)
            self.btn_ortools.setToolTip("OR-Tools non install\u00e9")
        self.btn_all = QPushButton("Comparer les 3")
        self.btn_all.setObjectName("primaryBtn")
        self.btn_all.setMinimumHeight(44)
        self.btn_all.clicked.connect(self._run_all)

        btn_layout.addWidget(self.btn_greedy)
        btn_layout.addWidget(self.btn_2opt)
        btn_layout.addWidget(self.btn_ortools)
        btn_layout.addWidget(self.btn_all)
        main_layout.addLayout(btn_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6c6c6c;")
        main_layout.addWidget(self.status_label)

        # Results comparison table
        results_title = QLabel("Tableau de comparaison")
        results_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        main_layout.addWidget(results_title)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Métrique", "Glouton", "2-opt", "OR-Tools"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setRowCount(9)
        metrics = [
            "Distance totale (km)", "Durée totale (min)", "Coût total (€)",
            "Clients servis", "Respect horaires (%)", "Retard moyen (min)",
            "Temps CPU (ms)", "Gain vs Glouton (%)", "Utilisation flotte (%)"
        ]
        for i, m in enumerate(metrics):
            self.results_table.setItem(i, 0, QTableWidgetItem(m))
            for j in range(1, 4):
                self.results_table.setItem(i, j, QTableWidgetItem("—"))
        self.results_table.setMinimumHeight(340)
        main_layout.addWidget(self.results_table)

        # Routes detail
        routes_title = QLabel("Détail des tournées")
        routes_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        main_layout.addWidget(routes_title)

        self.routes_text = QTextEdit()
        self.routes_text.setReadOnly(True)
        self.routes_text.setMinimumHeight(200)
        self.routes_text.setPlaceholderText("Les détails des tournées apparaîtront ici après optimisation...")
        main_layout.addWidget(self.routes_text)

        main_layout.addStretch()
        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _update_coeff(self, *args):
        t = self._get_traffic_coeff()
        w = self._get_weather_coeff()
        total = t * w
        self.coeff_label.setText(f"Coefficient final : ×{total:.2f}  (trafic ×{t:.1f} × météo ×{w:.2f})")

    def _get_traffic_coeff(self):
        btn = self.traffic_buttons.checkedButton()
        if btn == self.traffic_custom_rb:
            return self.traffic_custom_spin.value()
        return btn.coeff if btn else 1.0

    def _get_weather_coeff(self):
        btn = self.weather_buttons.checkedButton()
        return btn.coeff if btn else 1.0

    def _get_data(self):
        conn = get_connection()
        clients_rows = conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()
        vehicles_rows = conn.execute("SELECT * FROM vehicles WHERE status='disponible'").fetchall()
        depot_row = conn.execute("SELECT * FROM depots ORDER BY id LIMIT 1").fetchone()
        conn.close()

        if not clients_rows:
            QMessageBox.warning(self, "Erreur", "Aucun client chargé. Importez des données ou utilisez le mode démo.")
            return None, None, None
        if not vehicles_rows:
            QMessageBox.warning(self, "Erreur", "Aucun véhicule disponible.")
            return None, None, None

        clients = [dict(r) for r in clients_rows]
        vehicles = [dict(r) for r in vehicles_rows]
        depot = {"latitude": depot_row["latitude"], "longitude": depot_row["longitude"]} if depot_row else {"latitude": 33.5731, "longitude": -7.5898}
        return clients, vehicles, depot

    def _run_algo(self, algo_name):
        clients, vehicles, depot = self._get_data()
        if clients is None:
            return

        traffic = self._get_traffic_coeff()
        weather = self._get_weather_coeff()
        params = {
            "max_iterations": self.iter_spin.value(),
            "time_limit": self.time_spin.value(),
        }

        self.progress_bar.setVisible(True)
        self._set_buttons_enabled(False)
        self._overlay.start("Optimisation en cours")

        thread = OptimizationThread(algo_name, clients, depot, vehicles, traffic, weather, params)
        thread.progress.connect(lambda msg: self.status_label.setText(msg))
        thread.finished.connect(lambda result: self._on_result(algo_name, result))
        self.threads.append(thread)
        thread.start()

    def _run_all(self):
        self.results = {}
        self._pending = ["greedy", "2opt"]
        if ORTOOLS_AVAILABLE:
            self._pending.append("ortools")
        self._run_algo(self._pending.pop(0))

    def _on_result(self, algo_name, result):
        self.progress_bar.setVisible(False)
        self._set_buttons_enabled(True)
        self._overlay.stop()

        if "error" in result and not result.get("routes"):
            QMessageBox.warning(self, "Erreur", result["error"])
            self.status_label.setText(f"Erreur : {result['error']}")
            return

        self.results[algo_name] = result
        self._update_table()
        self._update_routes_detail(algo_name, result)
        self._save_result(result)

        # Update convergence chart
        if algo_name == "2opt" and "convergence" in result:
            if hasattr(self.main_window, 'dashboard_w'):
                self.main_window.dashboard_w.update_convergence(result["convergence"])

        # Update map
        if hasattr(self.main_window, 'map_w'):
            self.main_window.map_w.display_routes(result)

        self.status_label.setText(
            f"{result['algorithm']} terminé — {result['total_distance_km']:.1f} km | "
            f"{result['cpu_time_ms']:.0f} ms | {result['respect_rate']:.0f}% respect"
        )
        show_toast(self.window(),
                   f"{result['algorithm']} : {result['total_distance_km']:.1f} km en {result['cpu_time_ms']:.0f} ms",
                   "success")

        log_action("OPTIMIZATION",
                    f"{result['algorithm']}: {result['total_distance_km']:.1f}km, "
                    f"{result['cpu_time_ms']:.0f}ms, {result['clients_served']} clients")

        # Chain next algo if running all
        if hasattr(self, '_pending') and self._pending:
            self._run_algo(self._pending.pop(0))

    def _update_table(self):
        col_map = {"greedy": 1, "2opt": 2, "ortools": 3}
        for algo, col in col_map.items():
            if algo in self.results:
                r = self.results[algo]
                greedy_dist = self.results.get("greedy", {}).get("total_distance_km", 0)
                gain = ((greedy_dist - r["total_distance_km"]) / greedy_dist * 100) if greedy_dist > 0 else 0
                fleet_count = len([rt for rt in r["routes"] if rt["route"]])
                total_v = len(r["routes"])
                utilization = (fleet_count / total_v * 100) if total_v > 0 else 0

                values = [
                    f"{r['total_distance_km']:.2f}",
                    f"{r['total_duration_min']:.1f}",
                    f"{r['total_cost']:.2f}",
                    f"{r['clients_served']} / {r['clients_total']}",
                    f"{r['respect_rate']:.1f}",
                    f"{r['avg_delay_min']:.1f}",
                    f"{r['cpu_time_ms']:.1f}",
                    f"{gain:.1f}" if algo != "greedy" else "—",
                    f"{utilization:.0f}",
                ]
                for row_idx, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.results_table.setItem(row_idx, col, item)

        # Highlight best values
        self._highlight_best()

    def _highlight_best(self):
        minimize_rows = [0, 1, 2, 5, 6]  # distance, duration, cost, delay, cpu
        maximize_rows = [3, 4, 7, 8]     # clients, respect, gain, utilization

        for row in range(9):
            values = []
            for col in range(1, 4):
                item = self.results_table.item(row, col)
                if item and item.text() != "—":
                    try:
                        val = float(item.text().split("/")[0].strip())
                        values.append((col, val))
                    except ValueError:
                        pass

            if len(values) < 2:
                continue

            if row in minimize_rows:
                best_col = min(values, key=lambda x: x[1])[0]
            else:
                best_col = max(values, key=lambda x: x[1])[0]

            item = self.results_table.item(row, best_col)
            if item:
                item.setForeground(Qt.GlobalColor.green)
                font = item.font()
                font.setBold(True)
                item.setFont(font)

    def _update_routes_detail(self, algo_name, result):
        html = f"<h3>{result['algorithm']}</h3>"
        for route_info in result["routes"]:
            if not route_info["route"]:
                continue
            v = route_info["vehicle"]
            reg = v.get('registration', 'Vehicule')
            html += f"<h4>{reg} - {route_info['distance_km']:.2f} km | Charge: {route_info['load_kg']:.0f} kg</h4><ol>"
            for stop in route_info["route"]:
                c = stop["client"]
                status = "OK" if stop["delay"] == 0 else f"+{stop['delay']:.0f}min"
                html += f"<li>{c.get('name', 'Client')} — Arrivée: {stop['arrival_time']:.0f}min | {status}</li>"
            html += "</ol>"

        current = self.routes_text.toHtml()
        self.routes_text.setHtml(current + html)

    def _save_result(self, result):
        conn = get_connection()
        fleet_count = len([rt for rt in result["routes"] if rt["route"]])
        total_v = len(result["routes"])
        utilization = (fleet_count / total_v * 100) if total_v > 0 else 0
        greedy_dist = self.results.get("greedy", {}).get("total_distance_km", 0)
        gain = ((greedy_dist - result["total_distance_km"]) / greedy_dist * 100) if greedy_dist > 0 else 0

        conn.execute(
            """INSERT INTO algo_results (algorithm, client_count, vehicle_count,
               total_distance, total_duration, total_cost, cpu_time_ms,
               respect_rate, avg_delay, gain_vs_greedy, fleet_utilization,
               traffic_coeff, weather_coeff)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result["algorithm"], result["clients_total"], total_v,
             result["total_distance_km"], result["total_duration_min"],
             result["total_cost"], result["cpu_time_ms"],
             result["respect_rate"], result["avg_delay_min"],
             gain, utilization,
             result.get("traffic_coeff", 1.0), result.get("weather_coeff", 1.0))
        )
        conn.commit()
        conn.close()

    def _set_buttons_enabled(self, enabled):
        self.btn_greedy.setEnabled(enabled)
        self.btn_2opt.setEnabled(enabled)
        self.btn_ortools.setEnabled(enabled and ORTOOLS_AVAILABLE)
        self.btn_all.setEnabled(enabled)

    def refresh_data(self):
        pass
