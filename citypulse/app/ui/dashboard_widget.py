from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QScrollArea, QPushButton, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from .help_dialog import show_help

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except (ImportError, Exception):
    HAS_MPL = False

from ..database.db_manager import get_connection


class KPICard(QFrame):
    def __init__(self, title, value, icon="", color="#3a3a4a"):
        super().__init__()
        self.setProperty("class", "card")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1px solid #d8dce3;
                border-radius: 10px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        top = QHBoxLayout()
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet("color: #6c6c6c; font-size: 11px; font-weight: bold;")
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 14px; color: #6c6c6c;")
        top.addWidget(title_lbl)
        top.addStretch()
        top.addWidget(icon_lbl)
        layout.addLayout(top)

        self.value_label = QLabel(str(value))
        self.value_label.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #2c2c2c;")
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))


class DashboardWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.layout_main = QVBoxLayout(container)
        self.layout_main.setContentsMargins(24, 24, 24, 24)
        self.layout_main.setSpacing(20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()

        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "dashboard"))
        header.addWidget(help_btn)

        self.layout_main.addLayout(header)

        subtitle = QLabel("Vue d'ensemble de vos opérations logistiques")
        subtitle.setObjectName("subheading")
        self.layout_main.addWidget(subtitle)

        # ── Quick Actions Bar ──
        qa_frame = QFrame()
        qa_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d8dce3;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        qa_layout = QHBoxLayout(qa_frame)
        qa_layout.setContentsMargins(12, 8, 12, 8)
        qa_layout.setSpacing(8)

        qa_label = QLabel("Actions rapides")
        qa_label.setStyleSheet("font-weight: 600; font-size: 12px; border: none; color: #6c6c6c;")
        qa_layout.addWidget(qa_label)
        qa_layout.addSpacing(8)


        qa_items = [
            ("Nouvelle optimisation", 4),
            ("Voir carte", 5),
            ("Importer clients", 1),
            ("Rapports", 9),
            ("Suivi", 6),
        ]
        for text, nav_idx in qa_items:
            btn = QPushButton(f"  {text}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("border: 1px solid #d8dce3; border-radius: 4px; padding: 6px 14px; font-size: 11px;")
            btn.clicked.connect(lambda checked, i=nav_idx: self.main_window._nav_to(i))
            qa_layout.addWidget(btn)
        qa_layout.addStretch()
        self.layout_main.addWidget(qa_frame)

        # KPI Cards
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(16)

        self.kpi_distance = KPICard("Distance totale", "0 km", "", "#2c2c2c")
        self.kpi_cost = KPICard("Co\u00fbt total", "0 \u20ac", "", "#4a4a4a")
        self.kpi_deliveries = KPICard("Livraisons", "0 / 0", "", "#6a6a6a")
        self.kpi_delay = KPICard("Retard moyen", "0 min", "", "#8a8a8a")
        self.kpi_respect = KPICard("Respect horaires", "0 %", "", "#4a4a4a")
        self.kpi_fleet = KPICard("Utilisation flotte", "0 %", "", "#6a6a6a")

        kpi_grid.addWidget(self.kpi_distance, 0, 0)
        kpi_grid.addWidget(self.kpi_cost, 0, 1)
        kpi_grid.addWidget(self.kpi_deliveries, 0, 2)
        kpi_grid.addWidget(self.kpi_delay, 1, 0)
        kpi_grid.addWidget(self.kpi_respect, 1, 1)
        kpi_grid.addWidget(self.kpi_fleet, 1, 2)

        self.layout_main.addLayout(kpi_grid)

        # ── Data Health / Readiness Section ──
        health_title = QLabel("Santé des données")
        health_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.layout_main.addWidget(health_title)

        health_grid = QGridLayout()
        health_grid.setSpacing(12)

        self.health_clients = self._make_health_card("Clients", "0", "Chargez des clients pour commencer")
        self.health_vehicles = self._make_health_card("Véhicules", "0", "Ajoutez des véhicules")
        self.health_depots = self._make_health_card("Dépôts", "0", "Configurez un dépôt")
        self.health_ready = self._make_health_card("Prêt à optimiser", "Non", "Besoin de clients + véhicules + dépôt")

        health_grid.addWidget(self.health_clients[0], 0, 0)
        health_grid.addWidget(self.health_vehicles[0], 0, 1)
        health_grid.addWidget(self.health_depots[0], 0, 2)
        health_grid.addWidget(self.health_ready[0], 0, 3)
        self.layout_main.addLayout(health_grid)

        # Charts section
        if HAS_MPL:
            charts_title = QLabel("Graphiques analytiques")
            charts_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            self.layout_main.addWidget(charts_title)

            charts_grid = QGridLayout()
            charts_grid.setSpacing(16)

            # Chart 1: Algorithm comparison
            self.fig_compare = Figure(figsize=(5, 3), facecolor="#ffffff")
            self.canvas_compare = FigureCanvas(self.fig_compare)
            self.canvas_compare.setMinimumHeight(280)
            charts_grid.addWidget(self._wrap_chart("Comparaison Algorithmes", self.canvas_compare), 0, 0)

            # Chart 2: Convergence 2-opt
            self.fig_convergence = Figure(figsize=(5, 3), facecolor="#ffffff")
            self.canvas_convergence = FigureCanvas(self.fig_convergence)
            self.canvas_convergence.setMinimumHeight(280)
            charts_grid.addWidget(self._wrap_chart("Convergence 2-opt", self.canvas_convergence), 0, 1)

            # Chart 3: Delivery distribution
            self.fig_pie = Figure(figsize=(5, 3), facecolor="#ffffff")
            self.canvas_pie = FigureCanvas(self.fig_pie)
            self.canvas_pie.setMinimumHeight(280)
            charts_grid.addWidget(self._wrap_chart("Répartition par véhicule", self.canvas_pie), 1, 0)

            # Chart 4: CPU scalability
            self.fig_scatter = Figure(figsize=(5, 3), facecolor="#ffffff")
            self.canvas_scatter = FigureCanvas(self.fig_scatter)
            self.canvas_scatter.setMinimumHeight(280)
            charts_grid.addWidget(self._wrap_chart("Scalabilité CPU", self.canvas_scatter), 1, 1)

            self.layout_main.addLayout(charts_grid)

        self.layout_main.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _wrap_chart(self, title, canvas):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d8dce3;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(frame)
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #2c2c2c; border: none;")
        layout.addWidget(lbl)
        layout.addWidget(canvas)
        return frame

    def _make_health_card(self, title, value, hint):
        """Create a small data-health indicator card.  Returns (frame, value_lbl, hint_lbl)."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d8dce3;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        lo = QVBoxLayout(frame)
        lo.setSpacing(4)
        lo.setContentsMargins(12, 10, 12, 10)
        t = QLabel(title.upper())
        t.setStyleSheet("color: #6c6c6c; font-size: 10px; font-weight: bold; border: none;")
        lo.addWidget(t)
        v = QLabel(value)
        v.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        v.setStyleSheet("color: #2c2c2c; border: none;")
        lo.addWidget(v)
        h = QLabel(hint)
        h.setStyleSheet("color: #999; font-size: 10px; border: none;")
        h.setWordWrap(True)
        lo.addWidget(h)
        return frame, v, h

    def refresh_data(self):
        conn = get_connection()
        # Get latest results
        results = conn.execute(
            "SELECT * FROM algo_results ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        clients_count = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
        vehicles_count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        depots_count = conn.execute("SELECT COUNT(*) FROM depots").fetchone()[0]
        conn.close()

        if results:
            latest = results[0]
            self.kpi_distance.set_value(f"{latest['total_distance']:.1f} km")
            self.kpi_cost.set_value(f"{latest['total_cost']:.1f} €")
            self.kpi_deliveries.set_value(f"{latest['client_count']} / {latest['client_count']}")
            self.kpi_delay.set_value(f"{latest['avg_delay']:.1f} min")
            self.kpi_respect.set_value(f"{latest['respect_rate']:.1f} %")
            self.kpi_fleet.set_value(f"{latest['fleet_utilization']:.0f} %" if latest['fleet_utilization'] else "N/A")
        else:
            self.kpi_distance.set_value("— km")
            self.kpi_cost.set_value("— €")
            self.kpi_deliveries.set_value(f"0 / {clients_count}")
            self.kpi_delay.set_value("— min")
            self.kpi_respect.set_value("— %")
            self.kpi_fleet.set_value(f"{vehicles_count} véh.")

        # ── Update data health cards ──
        _, cv, ch = self.health_clients
        cv.setText(str(clients_count))
        ch.setText("OK" if clients_count > 0 else "Importez ou ajoutez des clients")

        _, vv, vh = self.health_vehicles
        vv.setText(str(vehicles_count))
        vh.setText("OK" if vehicles_count > 0 else "Ajoutez des véhicules")

        _, dv, dh = self.health_depots
        dv.setText(str(depots_count))
        dh.setText("OK" if depots_count > 0 else "Configurez au moins un dépôt")

        _, rv, rh = self.health_ready
        ready = clients_count > 0 and vehicles_count > 0 and depots_count > 0
        rv.setText("Oui" if ready else "Non")
        rv.setStyleSheet(f"color: {'#22c55e' if ready else '#ef4444'}; border: none;")
        rh.setText("Lancez une optimisation !" if ready else
                   "Besoin de clients + véhicules + dépôt")

        if HAS_MPL:
            self._update_charts(results)

    def _update_charts(self, results):
        # Group by algorithm
        algo_data = {}
        for r in results:
            algo = r["algorithm"]
            if algo not in algo_data:
                algo_data[algo] = r

        if algo_data:
            # Chart 1: Bar comparison
            ax = self.fig_compare.clear()
            ax = self.fig_compare.add_subplot(111)
            ax.set_facecolor("#ffffff")
            algos = list(algo_data.keys())
            distances = [algo_data[a]["total_distance"] for a in algos]
            short_names = [a.split("(")[0].strip()[:12] for a in algos]
            colors = ["#2c2c2c", "#6a6a6a", "#aaaaaa"][:len(algos)]
            ax.bar(short_names, distances, color=colors)
            ax.set_ylabel("Distance (km)", color="#666666")
            ax.tick_params(colors="#666666")
            self.fig_compare.tight_layout()
            self.canvas_compare.draw()

            # Chart 3: Pie
            ax3 = self.fig_pie.clear()
            ax3 = self.fig_pie.add_subplot(111)
            ax3.set_facecolor("#ffffff")
            if len(algos) > 0:
                sizes = [algo_data[a]["total_distance"] for a in algos]
                ax3.pie(sizes, labels=short_names, autopct="%1.1f%%",
                        colors=colors, textprops={"color": "#2c2c2c"})
            self.fig_pie.tight_layout()
            self.canvas_pie.draw()

        # Chart 2: Empty convergence placeholder
        ax2 = self.fig_convergence.clear()
        ax2 = self.fig_convergence.add_subplot(111)
        ax2.set_facecolor("#ffffff")
        ax2.text(0.5, 0.5, "Lancez 2-opt\npour voir la convergence",
                 ha="center", va="center", color="#6c6c6c", fontsize=12,
                 transform=ax2.transAxes)
        ax2.tick_params(colors="#666666")
        self.fig_convergence.tight_layout()
        self.canvas_convergence.draw()

        # Chart 4: Empty scatter placeholder
        ax4 = self.fig_scatter.clear()
        ax4 = self.fig_scatter.add_subplot(111)
        ax4.set_facecolor("#ffffff")
        # Plot from history
        conn = get_connection()
        rows = conn.execute(
            "SELECT client_count, cpu_time_ms, algorithm FROM algo_results ORDER BY created_at"
        ).fetchall()
        conn.close()
        if rows:
            cmap = {"Glouton": "#2c2c2c", "2-opt": "#6a6a6a", "OR-Tools": "#aaaaaa"}
            for row in rows:
                c = "#6c6c6c"
                for k, v in cmap.items():
                    if k in (row["algorithm"] or ""):
                        c = v
                        break
                ax4.scatter(row["client_count"], row["cpu_time_ms"], color=c, s=40, alpha=0.8)
            ax4.set_xlabel("Nb clients", color="#666666")
            ax4.set_ylabel("Temps CPU (ms)", color="#666666")
        else:
            ax4.text(0.5, 0.5, "Pas encore de donn\u00e9es",
                     ha="center", va="center", color="#6c6c6c", fontsize=12,
                     transform=ax4.transAxes)
        ax4.tick_params(colors="#666666")
        self.fig_scatter.tight_layout()
        self.canvas_scatter.draw()

    def update_convergence(self, convergence_data):
        if not HAS_MPL or not convergence_data:
            return
        ax = self.fig_convergence.clear()
        ax = self.fig_convergence.add_subplot(111)
        ax.set_facecolor("#ffffff")
        ax.plot(convergence_data, color="#2c2c2c", linewidth=2)
        ax.set_xlabel("Am\u00e9liorations", color="#666666")
        ax.set_ylabel("Distance", color="#666666")
        ax.tick_params(colors="#666666")
        self.fig_convergence.tight_layout()
        self.canvas_convergence.draw()


