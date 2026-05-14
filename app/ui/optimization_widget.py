"""
optimization_widget.py — Moteur d'Optimisation VRP v3.0
=======================================================
Layout QSplitter horizontal 30/70 :
  GAUCHE  — Configuration (QScrollArea 320px)
  DROITE  — Résultats (QTabWidget 5 onglets)

Threads : un OptimizationThread par algo (parallèle)
Signaux : progress(str), partial_result(dict), finished(dict), error(str), compliance(dict)
"""

import csv
import io
import json
import logging
import time
from datetime import date, datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QRadioButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFrame, QScrollArea, QTextEdit, QMessageBox, QButtonGroup,
    QCheckBox, QTabWidget, QSplitter, QSlider, QTreeWidget,
    QTreeWidgetItem, QAbstractItemView, QSizePolicy, QDateEdit,
    QFileDialog, QApplication, QDialog, QDialogButtonBox, QListWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor

from ..database.db_manager import get_connection, log_action
from ..services.report_service import ReportService, REPORTLAB_OK
from ..services.optimization_service import (
    validate_inputs, run_optimization, save_result,
    check_anomalies_after_run, ValidationError,
)
from ..ai.clustering import get_cluster_summary
from ..engine.ortools_solver import ORTOOLS_AVAILABLE
from ..engine.cost_calculator import (
    check_rse_compliance, check_adr_compliance, check_zfe_compliance,
    calculate_route_cost, calculate_co2,
)
from ..engine.traffic_adjuster import get_traffic_coefficient, classify_day_type
from .toast import show_toast
from .loading_overlay import LoadingOverlay
from .help_dialog import show_help
from .lucide_icons import apply_action_button

try:
    import requests as _req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors as rl_colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":    "#0D1B2A", "panel":  "#112240", "input":  "#1A2E4A",
    "accent":"#00D4FF", "success":"#00FF88", "warning":"#FFB800",
    "danger":"#FF4757", "text":   "#E8F4FD", "text2":  "#8899AA",
    "border":"#1E3A5F", "hover":  "#1A3A5C", "purple": "#8B5CF6",
}
_INP = (
    f"QLineEdit,QSpinBox,QDoubleSpinBox,QDateEdit,QComboBox{{"
    f"background:{C['input']};color:{C['text']};border:1px solid {C['border']};"
    "border-radius:4px;padding:3px 6px;}"
    f"QComboBox::drop-down{{border:none;}}"
    f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
    f"border:1px solid {C['border']};}}"
)
_GRP = (
    f"QGroupBox{{color:{C['text2']};border:1px solid {C['border']};"
    "border-radius:6px;margin-top:10px;padding-top:8px;}"
    f"QGroupBox::title{{subcontrol-origin:margin;left:8px;padding:0 4px;"
    f"color:{C['accent']};font-weight:700;font-size:11px;}}"
)
_RB = f"QRadioButton{{color:{C['text']};background:transparent;}} QCheckBox{{color:{C['text']};background:transparent;}}"
_TBL = (
    f"QTableWidget{{background:{C['bg']};color:{C['text']};"
    f"gridline-color:{C['border']};border:none;alternate-background-color:#0F2035;}}"
    f"QTableWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
    f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
    f"border:1px solid {C['border']};padding:4px 6px;font-size:11px;font-weight:600;}}"
)


# ═══════════════════════════════════════════════════════════════════════════════
# THREADS D'OPTIMISATION
# ═══════════════════════════════════════════════════════════════════════════════

class OptimizationThread(QThread):
    progress       = pyqtSignal(str)
    partial_result = pyqtSignal(str, dict)   # (algo, partial_dict)
    finished       = pyqtSignal(str, dict)   # (algo, result)
    error          = pyqtSignal(str, str)    # (algo, message)
    compliance     = pyqtSignal(str, dict)   # (algo, compliance_dict)

    def __init__(self, algo: str, clients: list, depot: dict, vehicles: list,
                 traffic: float, weather: float, params: dict,
                 use_clustering: bool, greedy_ref: dict,
                 zones: list = None, drivers: list = None):
        super().__init__()
        self.algo           = algo
        self.clients        = clients
        self.depot          = depot
        self.vehicles       = vehicles
        self.traffic        = traffic
        self.weather        = weather
        self.params         = params
        self.use_clustering = use_clustering
        self.greedy_ref     = greedy_ref
        self.zones          = zones or []
        self.drivers        = drivers or []
        self._stop          = False

    def stop(self):
        self._stop = True

    def run(self):
        labels = {
            "greedy":  "Algorithme Glouton en cours…",
            "2opt":    "Optimisation 2-opt en cours…",
            "ortools": f"OR-Tools [{self.params.get('vrp_mode','standard')}] en cours…",
        }
        self.progress.emit(labels.get(self.algo, "Optimisation…"))
        try:
            result = run_optimization(
                self.algo, self.clients, self.depot, self.vehicles,
                self.traffic, self.weather, self.params,
                self.use_clustering, self.greedy_ref,
            )
            if self._stop:
                return
            self.partial_result.emit(self.algo, result)
            self.finished.emit(self.algo, result)

            # Calcul conformité post-run
            comp = self._run_compliance(result)
            self.compliance.emit(self.algo, comp)

        except ValidationError as e:
            self.error.emit(self.algo, str(e))
        except Exception as e:
            logger.exception("Erreur inattendue OptimizationThread [%s]", self.algo)
            self.error.emit(self.algo, f"Erreur interne : {e}")

    def _run_compliance(self, result: dict) -> dict:
        all_stops, all_orders = [], []
        rse_compliant = True
        rse_violations: list = []
        rse_warnings:   list = []

        for route in result.get("routes", []):
            veh   = route.get("vehicle") or {}
            stops = [s for s in route.get("route", []) if s.get("type") == "delivery"]
            if not stops:
                continue
            # Chauffeur du véhicule (injecté par _get_data), sinon fallback liste globale
            drv = veh.get("_driver") or (self.drivers[0] if self.drivers else {})
            all_stops.extend(stops)
            for s in stops:
                c = s.get("client") or {}
                if c.get("adr_class"):
                    all_orders.append(c)
            if drv:
                rse = check_rse_compliance(stops, drv)
                if not rse.get("compliant", True):
                    rse_compliant = False
                    reg = veh.get("registration", "?")
                    drv_name = f"{drv.get('first_name','')} {drv.get('last_name','')}".strip()
                    prefix = f"[{reg}/{drv_name}] " if drv_name else f"[{reg}] "
                    rse_violations.extend(prefix + v for v in rse.get("violations", []))
                    rse_warnings.extend(prefix + w for w in rse.get("warnings", []))

        rse_result = {"compliant": rse_compliant, "violations": rse_violations, "warnings": rse_warnings}
        fallback_veh = (self.vehicles[0] if self.vehicles else {})
        fallback_drv = (self.drivers[0] if self.drivers else {})
        adr = check_adr_compliance(all_orders, fallback_veh, fallback_drv)
        zfe = check_zfe_compliance(all_stops, fallback_veh, self.zones)
        return {"rse": rse_result, "adr": adr, "zfe": zfe}


# ═══════════════════════════════════════════════════════════════════════════════
# PLANIFICATION SEMAINE
# ═══════════════════════════════════════════════════════════════════════════════

class _WeekPlanThread(QThread):
    """Lance l'optimisation jour par jour sur une plage de dates.

    dry_run=True  → calcule mais ne commit pas en BDD (mode analyse/preview)
    dry_run=False → commit immédiatement chaque jour (mode legacy)
    """
    progress    = pyqtSignal(str)
    day_done    = pyqtSignal(dict)   # {date, n_orders, algo_results:{}, best_algo, served_ids, n_served, n_unserved}
    finished    = pyqtSignal(list)
    error       = pyqtSignal(str)

    def __init__(self, start_date: date, n_days: int, algo: str,
                 distribute: bool, dry_run: bool = True,
                 algos_list: list = None):
        super().__init__()
        self.start_date  = start_date
        self.n_days      = n_days
        self.algo        = algo
        self.distribute  = distribute
        self.dry_run     = dry_run
        self.algos_list  = algos_list  # explicit list overrides algo/"best3"

    def _run_algos(self, clients_day, depot, vehicles, day_str) -> dict:
        """Lance un ou plusieurs algos, retourne {algo_name: result, ...}."""
        if self.algos_list:
            algos = self.algos_list
        elif self.algo == "best3":
            algos = ("greedy", "2opt", "ortools")
        else:
            algos = (self.algo,)
        results = {}
        for a in algos:
            try:
                self.progress.emit(f"    [{day_str}] {a}…")
                results[a] = run_optimization(a, clients_day, depot, vehicles)
            except Exception as exc:
                self.progress.emit(f"    [{day_str}] {a} ignoré : {exc}")
        return results

    @staticmethod
    def _pick_best(algo_results: dict) -> str:
        """Retourne le nom de l'algo avec le plus de clients servis (à km égal, le moins de km)."""
        best = None
        for name, r in algo_results.items():
            if best is None:
                best = name; continue
            rb = algo_results[best]
            if (r.get("clients_served", 0), -r.get("total_distance_km", 1e9)) > \
               (rb.get("clients_served", 0), -rb.get("total_distance_km", 1e9)):
                best = name
        return best

    def _load_vehicles(self, day_str: str) -> list:
        conn = get_connection()
        try:
            unavail_ids = {
                r["driver_id"] for r in conn.execute(
                    "SELECT driver_id FROM driver_unavailabilities WHERE date=?",
                    (day_str,)
                ).fetchall()
            }
            veh_rows = conn.execute("SELECT * FROM vehicles WHERE status='disponible'").fetchall()
            all_drivers = {
                r["id"]: dict(r) for r in conn.execute(
                    "SELECT * FROM drivers WHERE COALESCE(archived,0)=0"
                ).fetchall()
            }
        except Exception:
            unavail_ids = set(); veh_rows = []; all_drivers = {}
        finally:
            conn.close()

        vehicles = []
        for row in veh_rows:
            v = dict(row)
            drv = all_drivers.get(v.get("driver_id"))
            if drv and v.get("driver_id") in unavail_ids:
                continue
            if drv:
                v["_driver"] = drv
            vehicles.append(v)
        return vehicles

    @staticmethod
    def _rows_to_clients(rows) -> list:
        return [{
            "id":           r["client_id"],
            "name":         r["name"],
            "latitude":     float(r["latitude"] or 0),
            "longitude":    float(r["longitude"] or 0),
            "demand_kg":    float(r["demand_kg"] or 0),
            "ready_time":   int(r["ready_time"] or 0),
            "due_time":     int(r["due_time"] or 1440),
            "service_time": int(r["service_time"] or 10),
            "priority":     int(r.get("o_priority") or r.get("c_priority") or 3),
            "_order_id":    r["order_id"],
        } for r in rows]

    def _mark_assigned(self, order_ids: list, day_str: str):
        if not order_ids:
            return
        conn = get_connection()
        ph = ",".join("?" * len(order_ids))
        conn.execute(
            f"UPDATE orders SET status='assigned', scheduled_date=? "
            f"WHERE id IN ({ph}) AND scheduled_date IS NULL",
            [day_str] + order_ids,
        )
        conn.execute(
            f"UPDATE orders SET status='assigned' "
            f"WHERE id IN ({ph}) AND scheduled_date IS NOT NULL",
            order_ids,
        )
        conn.commit()
        conn.close()
        log_action("WEEK_PLAN", f"{day_str}: {len(order_ids)} commandes assignées")

    def run(self):
        conn = get_connection()
        try:
            depot_row = conn.execute("SELECT * FROM depots ORDER BY id LIMIT 1").fetchone()
            depot = dict(depot_row) if depot_row else {"latitude": 33.5731, "longitude": -7.5898}
        except Exception:
            depot = {"latitude": 33.5731, "longitude": -7.5898}
        finally:
            conn.close()

        results = []

        if self.distribute:
            conn = get_connection()
            try:
                rows = conn.execute("""
                    SELECT o.id AS order_id,
                           COALESCE(o.priority, c.priority, 3) AS o_priority,
                           COALESCE(o.priority, c.priority, 3) AS c_priority,
                           COALESCE(o.quantity_kg, 0)           AS demand_kg,
                           c.id AS client_id, c.name,
                           c.latitude, c.longitude,
                           COALESCE(c.service_time, 10) AS service_time,
                           COALESCE(c.ready_time, 0)    AS ready_time,
                           COALESCE(c.due_time, 1440)   AS due_time
                    FROM orders o
                    JOIN clients c ON o.client_id = c.id
                    WHERE o.status='pending' AND COALESCE(o.archived,0)=0
                    ORDER BY COALESCE(o.priority, c.priority, 3) ASC
                """).fetchall()
            except Exception as exc:
                self.error.emit(f"Erreur chargement commandes : {exc}"); return
            finally:
                conn.close()

            remaining = [dict(r) for r in rows]

            for i in range(self.n_days):
                if not remaining:
                    break
                day = self.start_date + timedelta(days=i)
                day_str = day.strftime("%Y-%m-%d")
                self.progress.emit(
                    f"Jour {i+1}/{self.n_days} ({day_str}) — {len(remaining)} commandes restantes…"
                )
                vehicles = self._load_vehicles(day_str)
                if not vehicles:
                    self.progress.emit(f"  ↳ Aucun véhicule disponible, jour ignoré.")
                    continue

                clients_day = self._rows_to_clients(remaining)
                algo_results = self._run_algos(clients_day, depot, vehicles, day_str)
                if not algo_results:
                    self.progress.emit(f"  ↳ Aucun algorithme n'a pu s'exécuter.")
                    continue

                best_algo = self._pick_best(algo_results)
                best_result = algo_results.get(best_algo, {})

                served_ids = [
                    (s.get("client") or {}).get("_order_id")
                    for rt in best_result.get("routes", [])
                    for s in rt.get("route", [])
                    if s.get("type") == "delivery"
                ]
                served_ids = [oid for oid in served_ids if oid]

                if not self.dry_run:
                    self._mark_assigned(served_ids, day_str)

                served_set = set(served_ids)
                remaining  = [r for r in remaining if r["order_id"] not in served_set]

                algo_summary = {
                    a: {"km": round(r.get("total_distance_km", 0), 1),
                        "served": r.get("clients_served", 0)}
                    for a, r in algo_results.items()
                }
                res = {
                    "date":              day_str,
                    "n_orders":          len(clients_day),
                    "n_served":          len(served_ids),
                    "n_unserved":        len(clients_day) - len(served_ids),
                    "served_ids":        served_ids,
                    "best_algo":         best_algo or "",
                    "algo_results":      algo_summary,
                    "algo_results_full": algo_results,
                }
                results.append(res)
                self.day_done.emit(res)

        else:
            for i in range(self.n_days):
                day = self.start_date + timedelta(days=i)
                day_str = day.strftime("%Y-%m-%d")
                self.progress.emit(f"Jour {i+1}/{self.n_days} ({day_str})…")

                conn = get_connection()
                try:
                    rows = conn.execute("""
                        SELECT o.id AS order_id,
                               COALESCE(o.priority, c.priority, 3) AS o_priority,
                               COALESCE(o.priority, c.priority, 3) AS c_priority,
                               COALESCE(o.quantity_kg, 0)           AS demand_kg,
                               c.id AS client_id, c.name,
                               c.latitude, c.longitude,
                               COALESCE(c.service_time, 10) AS service_time,
                               COALESCE(c.ready_time, 0)    AS ready_time,
                               COALESCE(c.due_time, 1440)   AS due_time
                        FROM orders o
                        JOIN clients c ON o.client_id = c.id
                        WHERE o.status='pending' AND COALESCE(o.archived,0)=0
                          AND o.scheduled_date=?
                        ORDER BY COALESCE(o.priority, c.priority, 3) ASC
                    """, (day_str,)).fetchall()
                except Exception as exc:
                    self.error.emit(f"Erreur {day_str}: {exc}"); conn.close(); continue
                finally:
                    conn.close()

                if not rows:
                    continue

                vehicles = self._load_vehicles(day_str)
                if not vehicles:
                    continue

                clients_day = self._rows_to_clients(rows)
                algo_results = self._run_algos(clients_day, depot, vehicles, day_str)
                if not algo_results:
                    continue

                best_algo = self._pick_best(algo_results)
                best_result = algo_results.get(best_algo, {})

                served_ids = [
                    (s.get("client") or {}).get("_order_id")
                    for rt in best_result.get("routes", [])
                    for s in rt.get("route", [])
                    if s.get("type") == "delivery"
                ]
                served_ids = [oid for oid in served_ids if oid]

                if not self.dry_run:
                    self._mark_assigned(served_ids, day_str)

                algo_summary = {
                    a: {"km": round(r.get("total_distance_km", 0), 1),
                        "served": r.get("clients_served", 0)}
                    for a, r in algo_results.items()
                }
                res = {
                    "date":              day_str,
                    "n_orders":          len(clients_day),
                    "n_served":          len(served_ids),
                    "n_unserved":        len(clients_day) - len(served_ids),
                    "served_ids":        served_ids,
                    "best_algo":         best_algo or "",
                    "algo_results":      algo_summary,
                    "algo_results_full": algo_results,
                }
                results.append(res)
                self.day_done.emit(res)

        self.finished.emit(results)


class _DayDetailDialog(QDialog):
    """Popup de détail pour un jour planifié — 4 onglets."""

    def __init__(self, day_result: dict, parent=None):
        super().__init__(parent)
        self._day     = day_result
        self._results = day_result.get("algo_results_full", {})
        self._best    = day_result.get("best_algo", "") or next(iter(self._results), "")
        date_str      = day_result.get("date", "?")

        self.setWindowTitle(f"Détail — {date_str}")
        self.setMinimumSize(920, 620)
        self.resize(1040, 680)
        self.setStyleSheet(
            f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            "QLabel{background:transparent;}"
            + _GRP + _TBL + _INP + _RB
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 12)
        lo.setSpacing(0)

        # ── En-tête ─────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            f"QFrame{{background:{C['panel']};border-bottom:1px solid {C['border']};}}"
        )
        hlo = QHBoxLayout(hdr)
        hlo.setContentsMargins(18, 0, 18, 0)
        hdr_lbl = QLabel(
            f"📅  {date_str}   —   "
            f"{day_result.get('n_served', 0)}/{day_result.get('n_orders', 0)} commandes servies   —   "
            f"Meilleur : {self._best.upper()}"
        )
        hdr_lbl.setStyleSheet(
            f"color:{C['text']};font-size:13px;font-weight:700;background:transparent;"
        )
        hlo.addWidget(hdr_lbl)
        hlo.addStretch()
        lo.addWidget(hdr)

        # ── Onglets ─────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane{{background:{C['bg']};border:none;}}"
            f"QTabBar::tab{{background:{C['panel']};color:{C['text2']};padding:8px 14px;"
            "border-top-left-radius:6px;border-top-right-radius:6px;margin-right:2px;font-size:12px;}"
            f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
            f"QTabBar::tab:hover{{background:{C['hover']};color:{C['text']};}}"
        )
        self._tabs.addTab(self._build_routes_tab(),     "🚗 Détail véhicules")
        self._tabs.addTab(self._build_charts_tab(),     "📈 Graphiques")
        self._tabs.addTab(self._build_costs_tab(),      "💰 Simulation coûts")
        self._tabs.addTab(self._build_compliance_tab(), "⚠ Conformité RSE")
        lo.addWidget(self._tabs, 1)

        # ── Fermer ──────────────────────────────────────────────────────
        close_lo = QHBoxLayout()
        close_lo.setContentsMargins(12, 0, 12, 0)
        close_lo.addStretch()
        close_btn = QPushButton("Fermer")
        close_btn.setObjectName("secondaryBtn")
        close_btn.setFixedSize(100, 32)
        close_btn.clicked.connect(self.accept)
        close_lo.addWidget(close_btn)
        lo.addLayout(close_lo)

    # ── Tab 0 : Détail véhicules ─────────────────────────────────────

    def _build_routes_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(12, 8, 12, 8)
        lo.setSpacing(6)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Algorithme :"))
        self._dd_algo_cb = QComboBox()
        self._dd_algo_cb.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:4px 8px;}}"
        )
        _ALGO_LABELS = {"greedy": "Greedy", "2opt": "2-opt", "ortools": "OR-Tools"}
        for a in self._results:
            self._dd_algo_cb.addItem(_ALGO_LABELS.get(a, a.upper()), a)
        for i in range(self._dd_algo_cb.count()):
            if self._dd_algo_cb.itemData(i) == self._best:
                self._dd_algo_cb.setCurrentIndex(i)
                break
        self._dd_algo_cb.currentIndexChanged.connect(self._dd_refresh_routes)
        sel_row.addWidget(self._dd_algo_cb)
        sel_row.addStretch()
        lo.addLayout(sel_row)

        self._dd_tree = QTreeWidget()
        self._dd_tree.setColumnCount(5)
        self._dd_tree.setHeaderLabels([
            "Véhicule / Arrêt", "Arrivée", "Retard (min)", "Dist. (km)", "Charge (kg)"
        ])
        self._dd_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            self._dd_tree.header().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._dd_tree.setAlternatingRowColors(True)
        self._dd_tree.setStyleSheet(
            f"QTreeWidget{{background:{C['bg']};color:{C['text']};"
            f"border:1px solid {C['border']};alternate-background-color:#0F2035;}}"
            f"QTreeWidget::item:selected{{background:{C['hover']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:4px;}}"
        )
        lo.addWidget(self._dd_tree, 1)
        self._dd_refresh_routes()
        return w

    def _dd_refresh_routes(self):
        algo   = self._dd_algo_cb.currentData()
        result = self._results.get(algo)
        self._dd_tree.clear()
        if not result:
            return
        for route in result.get("routes", []):
            stops = [s for s in route.get("route", []) if s.get("type") == "delivery"]
            if not stops:
                continue
            veh      = route.get("vehicle", {})
            reg      = veh.get("registration", f"V{route.get('vehicle_index', 0)+1}")
            dist     = route.get("distance_km", 0)
            load     = route.get("load_kg", 0)
            drv_info = veh.get("_driver") or {}
            drv_name = f"{drv_info.get('first_name','')} {drv_info.get('last_name','')}".strip()
            v_label  = f" {reg}" + (f"  ·  {drv_name}" if drv_name else "")
            v_item   = QTreeWidgetItem([
                v_label,
                f"{route.get('duration_min', 0):.0f} min",
                "",
                f"{dist:.1f}",
                f"{load:.0f} kg",
            ])
            v_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            v_item.setForeground(0, QColor(C["accent"]))
            for stop in stops:
                c      = stop.get("client") or {}
                arr    = stop.get("arrival_time", 0)
                delay  = stop.get("delay", 0)
                d_from = stop.get("distance_from_prev", 0)
                s_item = QTreeWidgetItem([
                    f"  {c.get('name', '')}",
                    f"{arr:.0f}",
                    f"{delay:.0f}" if delay else "",
                    f"{d_from:.1f}",
                    f"{c.get('demand_kg', 0):.0f}",
                ])
                if delay > 0:
                    s_item.setForeground(2, QColor(C["warning"]))
                v_item.addChild(s_item)
            self._dd_tree.addTopLevelItem(v_item)
        self._dd_tree.expandAll()

    # ── Tab 1 : Graphiques ───────────────────────────────────────────

    def _build_charts_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(12, 8, 12, 8)
        lo.setSpacing(6)
        if not HAS_MPL:
            lo.addWidget(QLabel("(Matplotlib non disponible)"))
            return w
        try:
            fig, axes = plt.subplots(1, 3, figsize=(13, 4))
            fig.patch.set_facecolor(C["panel"])
            for ax in axes:
                ax.set_facecolor(C["bg"])

            labels = [a.upper() for a in self._results]
            colors = [C["accent"], C["success"], C["warning"]][:len(labels)]

            # Radar
            cats   = ["Distance", "Coût", "Respect", "CO₂ inv."]
            n_cats = len(cats)
            angles = [n / n_cats * 2 * 3.14159 + 3.14159 / 2 for n in range(n_cats)]
            angles += [angles[0]]
            max_dist = max(r.get("total_distance_km", 1) for r in self._results.values()) or 1
            max_cost = max(r.get("total_cost", 1) for r in self._results.values()) or 1
            ax0 = axes[0]
            for (algo, res), col in zip(self._results.items(), colors):
                vals = [
                    1 - res.get("total_distance_km", 0) / max_dist,
                    1 - res.get("total_cost", 0) / max_cost,
                    res.get("respect_rate", 0) / 100,
                    1 - min(res.get("total_co2_kg", 0), 100) / 100,
                ]
                vals += [vals[0]]
                ax0.plot(angles, vals, "o-", color=col, linewidth=2,
                         label=algo.upper(), markersize=4)
                ax0.fill(angles, vals, color=col, alpha=0.15)
            ax0.set_xticks(angles[:-1])
            ax0.set_xticklabels(cats, color=C["text2"], fontsize=9)
            ax0.set_yticklabels([])
            ax0.set_title("Radar perf.", color=C["text2"], fontsize=10)
            for sp in ax0.spines.values():
                sp.set_color(C["border"])
            ax0.legend(loc="upper right", fontsize=8, labelcolor=C["text2"], framealpha=0)

            # Barres distances
            ax1   = axes[1]
            dists = [r.get("total_distance_km", 0) for r in self._results.values()]
            bars  = ax1.bar(labels, dists, color=colors, edgecolor=C["border"], linewidth=0.5)
            ax1.set_title("Distance (km)", color=C["text2"], fontsize=10)
            ax1.tick_params(colors=C["text2"])
            for sp in ax1.spines.values():
                sp.set_color(C["border"])
            for bar, d in zip(bars, dists):
                ax1.text(bar.get_x() + bar.get_width() / 2, d * 1.02, f"{d:.1f}",
                         ha="center", va="bottom", color=C["text"], fontsize=9)

            # Camembert utilisation flotte
            ax2       = axes[2]
            best_r    = self._results.get(self._best) or next(iter(self._results.values()))
            routes_b  = best_r.get("routes", [])
            used      = sum(1 for r in routes_b if r.get("route"))
            empty     = len(routes_b) - used
            if used + empty > 0:
                _, _, autotexts = ax2.pie(
                    [used, empty], labels=["Utilisés", "Vides"],
                    colors=[C["success"], C["border"]],
                    autopct="%1.0f%%", startangle=90,
                    textprops={"color": C["text2"], "fontsize": 9},
                )
                for at in autotexts:
                    at.set_color(C["text"]); at.set_fontweight("bold")
            ax2.set_title(f"Flotte ({self._best.upper()})", color=C["text2"], fontsize=10)

            fig.tight_layout(pad=0.4)
            canvas = FigCanvas(fig)
            canvas.setMinimumHeight(260)
            lo.addWidget(canvas)
            plt.close(fig)
        except Exception as exc:
            lo.addWidget(QLabel(f"Erreur graphiques : {exc}"))
        return w

    # ── Tab 2 : Simulation coûts ─────────────────────────────────────

    def _build_costs_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(12, 8, 12, 8)
        lo.setSpacing(6)

        info = QLabel("Coûts estimés pour les tournées de cette journée.")
        info.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        lo.addWidget(info)

        sl_grp = QGroupBox("Paramètres de coût")
        sl_grp.setStyleSheet(_GRP + _INP)
        sl_lo = QVBoxLayout(sl_grp)
        sl_lo.setSpacing(6)
        self._dd_sliders: dict = {}
        for key, label, mn, mx, default in [
            ("fuel_price",  "Prix carburant (€/L)", 100, 300, 185),
            ("toll_factor", "Péages (€/km)",          0, 100,   0),
            ("labor_rate",  "Taux horaire (€/h)",    100, 400, 150),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(185)
            lbl.setStyleSheet(
                f"color:{C['text2']};font-size:11px;background:transparent;"
            )
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(mn, mx)
            sl.setValue(default)
            sl.setStyleSheet(
                f"QSlider::groove:horizontal{{background:{C['input']};height:4px;border-radius:2px;}}"
                f"QSlider::handle:horizontal{{background:{C['warning']};width:12px;height:12px;"
                "margin:-4px 0;border-radius:6px;}}"
                f"QSlider::sub-page:horizontal{{background:{C['warning']};border-radius:2px;}}"
            )
            val_lbl = QLabel(f"{default/100:.2f}")
            val_lbl.setFixedWidth(50)
            val_lbl.setStyleSheet(
                f"color:{C['text']};font-size:11px;background:transparent;"
            )
            sl.valueChanged.connect(lambda v, l=val_lbl: l.setText(f"{v/100:.2f}"))
            sl.valueChanged.connect(self._dd_recalc_costs)
            row.addWidget(lbl); row.addWidget(sl, 1); row.addWidget(val_lbl)
            sl_lo.addLayout(row)
            self._dd_sliders[key] = sl
        lo.addWidget(sl_grp)

        algos = list(self._results.keys())
        self._dd_cost_table = QTableWidget()
        self._dd_cost_table.setColumnCount(1 + len(algos))
        self._dd_cost_table.setHorizontalHeaderLabels(
            ["Poste de coût"] + [a.upper() for a in algos]
        )
        cost_rows = [
            "Carburant (€)", "Main d'œuvre (€)", "Fixe (€)",
            "Péages (€)", "CO₂ (kg)", "TOTAL (€)"
        ]
        self._dd_cost_table.setRowCount(len(cost_rows))
        for i, r in enumerate(cost_rows):
            self._dd_cost_table.setItem(i, 0, QTableWidgetItem(r))
            for j in range(len(algos)):
                self._dd_cost_table.setItem(i, j + 1, QTableWidgetItem("—"))
        self._dd_cost_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._dd_cost_table.verticalHeader().setVisible(False)
        self._dd_cost_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._dd_cost_table.setStyleSheet(_TBL)
        self._dd_cost_table.setMaximumHeight(220)
        lo.addWidget(self._dd_cost_table)
        lo.addStretch()
        self._dd_recalc_costs()
        return w

    def _dd_recalc_costs(self):
        fuel_price  = self._dd_sliders["fuel_price"].value()  / 100.0
        toll_factor = self._dd_sliders["toll_factor"].value() / 100.0
        labor_rate  = self._dd_sliders["labor_rate"].value()  / 100.0
        for col_i, (algo, result) in enumerate(self._results.items()):
            tot_fuel = tot_labor = tot_fixed = tot_toll = tot_co2 = 0.0
            for route in result.get("routes", []):
                veh = dict(route.get("vehicle") or {})
                if not veh.get("fuel_consumption_l100km"):
                    veh["fuel_consumption_l100km"] = 12.0
                cost = calculate_route_cost(
                    route.get("route", []), veh, {"hourly_rate": labor_rate},
                    fuel_price, toll_factor
                )
                tot_fuel  += cost["fuel_cost"]
                tot_labor += cost["labor_cost"]
                tot_fixed += cost["fixed_cost"]
                tot_toll  += cost["toll_estimate"]
                tot_co2   += calculate_co2(route.get("distance_km", 0), veh)
            total = tot_fuel + tot_labor + tot_fixed + tot_toll
            for row_i, val in enumerate(
                [tot_fuel, tot_labor, tot_fixed, tot_toll, tot_co2, total]
            ):
                it = QTableWidgetItem(f"{val:.2f}")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row_i == 5:
                    it.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                    it.setForeground(QColor(C["warning"]))
                self._dd_cost_table.setItem(row_i, col_i + 1, it)

    # ── Tab 3 : Conformité RSE ───────────────────────────────────────

    def _build_compliance_tab(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(12, 8, 12, 8)
        lo.setSpacing(8)

        note = QLabel(
            "Vérification RSE (CE 561/2006) calculée sur les durées de conduite de cette journée.\n"
            "Pour ADR et ZFE, utilisez l'onglet 'Conformité RSE/ADR/ZFE' de l'optimisation principale."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        lo.addWidget(note)

        algo_sel = QComboBox()
        algo_sel.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:4px 8px;}}"
        )
        _ALGO_LABELS = {"greedy": "Greedy", "2opt": "2-opt", "ortools": "OR-Tools"}
        for a in self._results:
            algo_sel.addItem(_ALGO_LABELS.get(a, a.upper()), a)
        for i in range(algo_sel.count()):
            if algo_sel.itemData(i) == self._best:
                algo_sel.setCurrentIndex(i)
                break
        lo.addWidget(algo_sel)

        self._dd_comp_edit = QTextEdit()
        self._dd_comp_edit.setReadOnly(True)
        self._dd_comp_edit.setStyleSheet(
            f"QTextEdit{{background:{C['bg']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:4px;"
            "font-family:Consolas,monospace;font-size:11px;padding:6px;}}"
        )
        lo.addWidget(self._dd_comp_edit, 1)

        def _refresh(idx):
            algo   = algo_sel.currentData()
            result = self._results.get(algo)
            if not result:
                self._dd_comp_edit.setPlainText("Aucun résultat.")
                return
            lines = [f"=== RSE — {algo.upper()} ===\n"]
            all_ok = True
            for route in result.get("routes", []):
                veh   = route.get("vehicle") or {}
                stops = [s for s in route.get("route", []) if s.get("type") == "delivery"]
                if not stops:
                    continue
                reg  = veh.get("registration", "?")
                drv  = veh.get("_driver") or {}
                rse  = check_rse_compliance(stops, drv)
                icon = "✅" if rse.get("compliant", True) else "❌"
                if not rse.get("compliant", True):
                    all_ok = False
                lines.append(
                    f"{icon}  {reg}  —  {rse.get('total_drive_h', 0):.1f} h conduite, "
                    f"{rse.get('breaks_count', 0)} pause(s)"
                )
                for v in rse.get("violations", []):
                    lines.append(f"   ⚠ {v}")
                for wn in rse.get("warnings", []):
                    lines.append(f"   ℹ {wn}")
            lines.append("")
            if all_ok:
                lines.append("✅  Toutes les tournées sont conformes RSE pour cette journée.")
            lines.append(
                "\nℹ  ADR / ZFE : vérification disponible depuis l'onglet "
                "'Conformité RSE/ADR/ZFE' du panneau principal après optimisation."
            )
            self._dd_comp_edit.setPlainText("\n".join(lines))

        algo_sel.currentIndexChanged.connect(_refresh)
        _refresh(0)
        return w


class _WeeklyPlannerDialog(QDialog):
    """Dialogue de configuration de la planification hebdomadaire."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Planifier la semaine automatiquement")
        self.setMinimumWidth(520)
        self.setStyleSheet(
            "QDialog{background:#0D1B2A;color:#E8F4F8;}"
            "QLabel{background:transparent;}"
            "QGroupBox{color:#7FA8C0;font-size:11px;font-weight:600;"
            "border:1px solid #243F58;border-radius:6px;margin-top:8px;padding-top:10px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}"
            "QDateEdit,QComboBox,QSpinBox{background:#1E3A50;color:#E8F4F8;"
            "border:1px solid #243F58;border-radius:4px;padding:4px;}"
            "QRadioButton,QCheckBox{color:#E8F4F8;background:transparent;}"
            "QTableWidget{background:#162840;color:#E8F4F8;gridline-color:#243F58;"
            "border:1px solid #243F58;}"
            "QHeaderView::section{background:#243F58;color:#7FA8C0;border:none;padding:4px;}"
        )

        lo = QVBoxLayout(self)
        lo.setSpacing(14)
        lo.setContentsMargins(20, 16, 20, 16)

        # ── Date range ─────────────────────────────────────────────
        date_grp = QGroupBox("Période de planification")
        dlo = QHBoxLayout(date_grp)
        today = date.today()
        monday = today - timedelta(days=today.weekday())  # lundi de la semaine courante

        dlo.addWidget(QLabel("Du :"))
        self._start = QDateEdit()
        self._start.setCalendarPopup(True)
        self._start.setDate(QDate(monday.year, monday.month, monday.day))
        self._start.setDisplayFormat("dd/MM/yyyy")
        dlo.addWidget(self._start)

        dlo.addWidget(QLabel("Nombre de jours :"))
        self._n_days = QSpinBox()
        self._n_days.setRange(1, 14)
        self._n_days.setValue(5)
        self._n_days.setSuffix(" jours")
        dlo.addWidget(self._n_days)
        dlo.addStretch()
        lo.addWidget(date_grp)

        # ── Mode ────────────────────────────────────────────────────
        mode_grp = QGroupBox("Mode de distribution")
        mlo = QVBoxLayout(mode_grp)
        self._rb_distribute = QRadioButton(
            "Distribuer automatiquement toutes les commandes en attente\n"
            "(remplit chaque jour avec les commandes prioritaires d'abord)"
        )
        self._rb_distribute.setChecked(True)
        self._rb_scheduled = QRadioButton(
            "Respecter les dates prévues des commandes\n"
            "(planifie uniquement les commandes dont scheduled_date correspond au jour)"
        )
        mlo.addWidget(self._rb_distribute)
        mlo.addWidget(self._rb_scheduled)
        lo.addWidget(mode_grp)

        # ── Algorithme ──────────────────────────────────────────────
        algo_grp = QGroupBox("Algorithme d'optimisation")
        algo_lo = QVBoxLayout(algo_grp)
        algo_lo.setSpacing(6)
        alo = QHBoxLayout()
        alo.addWidget(QLabel("Algorithme :"))
        self._algo_cb = QComboBox()
        self._algo_cb.addItem("Glouton — rapide (recommandé pour la semaine)", "greedy")
        self._algo_cb.addItem("2-opt — plus précis, plus lent", "2opt")
        self._algo_cb.addItem("⭐ Meilleur des 3 (Greedy + 2-opt + OR-Tools)", "best3")
        alo.addWidget(self._algo_cb, 1)
        algo_lo.addLayout(alo)

        self._algo_warn = QLabel(
            "⚠ Lance OR-Tools sur chaque jour (~30 s/jour). "
            "Pour 5 jours : environ 2–3 minutes."
        )
        self._algo_warn.setWordWrap(True)
        self._algo_warn.setStyleSheet(
            "color:#FFB800;font-size:10px;background:transparent;border:none;"
        )
        self._algo_warn.setVisible(False)
        algo_lo.addWidget(self._algo_warn)
        self._algo_cb.currentIndexChanged.connect(
            lambda: self._algo_warn.setVisible(self._algo_cb.currentData() == "best3")
        )
        lo.addWidget(algo_grp)

        # ── Aperçu commandes en attente ─────────────────────────────
        prev_grp = QGroupBox("Aperçu des commandes en attente")
        plo = QVBoxLayout(prev_grp)
        self._preview_tbl = QTableWidget()
        self._preview_tbl.setColumnCount(3)
        self._preview_tbl.setHorizontalHeaderLabels(["Date prévue", "Commandes en attente", "Priorité haute (1★★★★★)"])
        self._preview_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._preview_tbl.setMaximumHeight(130)
        self._preview_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        plo.addWidget(self._preview_tbl)
        lo.addWidget(prev_grp)
        self._load_preview()

        # ── Boutons ─────────────────────────────────────────────────
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Planifier →")
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryBtn")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lo.addWidget(bb)

    def _load_preview(self):
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT scheduled_date,
                       COUNT(*) AS n_total,
                       SUM(CASE WHEN COALESCE(o.priority,3)=1 THEN 1 ELSE 0 END) AS n_high
                FROM orders o
                WHERE o.status='pending' AND COALESCE(o.archived,0)=0
                GROUP BY scheduled_date
                ORDER BY scheduled_date
                LIMIT 14
            """).fetchall()
            # Aussi compter les commandes sans date
            no_date = conn.execute("""
                SELECT COUNT(*) AS n, SUM(CASE WHEN COALESCE(priority,3)=1 THEN 1 ELSE 0 END) AS h
                FROM orders WHERE status='pending' AND COALESCE(archived,0)=0
                AND (scheduled_date IS NULL OR scheduled_date='')
            """).fetchone()
        except Exception:
            rows = []; no_date = None
        finally:
            conn.close()

        data = [(r["scheduled_date"] or "—", r["n_total"], r["n_high"]) for r in rows]
        if no_date and no_date["n"]:
            data.insert(0, ("(sans date)", no_date["n"], no_date["h"] or 0))

        self._preview_tbl.setRowCount(len(data))
        for i, (d, n, h) in enumerate(data):
            self._preview_tbl.setItem(i, 0, QTableWidgetItem(str(d)))
            self._preview_tbl.setItem(i, 1, QTableWidgetItem(str(n)))
            self._preview_tbl.setItem(i, 2, QTableWidgetItem(str(h or 0)))

    def get_params(self):
        start = self._start.date().toPyDate()
        return (
            start,
            self._n_days.value(),
            self._algo_cb.currentData(),
            self._rb_distribute.isChecked(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# WIDGET PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class OptimizationWidget(QWidget):
    routes_ready = pyqtSignal(dict)   # → MapWidget + TrackingWidget

    def __init__(self, main_window):
        super().__init__()
        self.main_window  = main_window
        self.results:  dict  = {}        # {algo: result_dict}
        self._threads: list  = []
        self._pending: list  = []
        self._greedy_ref     = None
        self._compliance: dict = {}      # {algo: compliance_dict}
        self._running    = False
        self._wx_thread  = None
        self._settings_applied = False
        self._setup_ui()
        self._overlay = LoadingOverlay(self)

    # ══════════════════════════════════════════════════════════════════════
    # UI PRINCIPALE — Splitter 30/70
    # ══════════════════════════════════════════════════════════════════════

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr_bar = QFrame()
        hdr_bar.setFixedHeight(48)
        hdr_bar.setStyleSheet(f"QFrame{{background:{C['panel']};border-bottom:1px solid {C['border']};}}")
        hdr_lo = QHBoxLayout(hdr_bar); hdr_lo.setContentsMargins(20, 0, 16, 0)
        title = QLabel("Moteur d'Optimisation VRP v3")
        title.setStyleSheet(f"color:{C['text']};font-size:16px;font-weight:700;background:transparent;")
        hdr_lo.addWidget(title)
        hdr_lo.addStretch()
        self._source_badge = QLabel("")
        self._source_badge.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        hdr_lo.addWidget(self._source_badge)
        hdr_lo.addSpacing(8)
        _hb = QPushButton()
        _hb.setFixedSize(30, 30)
        _hb.setToolTip("Aide — Optimisation")
        _hb.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(_hb, "help-circle", "#7FA8C0", C["panel"], C["hover"], 18)
        _hb.clicked.connect(lambda: show_help(self, "optimization"))
        hdr_lo.addWidget(_hb)
        root.addWidget(hdr_bar)

        # ── Splitter ──────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{C['border']};width:3px;}}")

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([320, 900])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # ── Barre de progression + log ────────────────────────────────────
        bottom = QFrame()
        bottom.setFixedHeight(140)
        bottom.setStyleSheet(f"QFrame{{background:{C['panel']};border-top:1px solid {C['border']};}}")
        blo = QVBoxLayout(bottom); blo.setContentsMargins(12, 6, 12, 6); blo.setSpacing(4)

        prog_row = QHBoxLayout()
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 0); self._prog_bar.setVisible(False)
        self._prog_bar.setFixedHeight(8)
        self._prog_bar.setStyleSheet(
            f"QProgressBar{{background:{C['input']};border:none;border-radius:4px;}}"
            f"QProgressBar::chunk{{background:{C['accent']};border-radius:4px;}}"
        )
        self._prog_status = QLabel("Prêt")
        self._prog_status.setStyleSheet(f"color:{C['text2']};font-size:12px;background:transparent;")
        prog_row.addWidget(self._prog_bar, 1); prog_row.addWidget(self._prog_status)
        blo.addLayout(prog_row)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True); self._log_edit.setMaximumHeight(80)
        self._log_edit.setStyleSheet(
            f"QTextEdit{{background:{C['bg']};color:{C['text2']};border:1px solid {C['border']};"
            "border-radius:4px;font-size:11px;font-family:Consolas,monospace;}"
        )
        blo.addWidget(self._log_edit)

        # Actions post-run
        act_row = QHBoxLayout(); act_row.setSpacing(6)
        self._btn_confirm  = QPushButton("✅ Confirmer le plan"); self._btn_confirm.setFixedHeight(28)
        self._btn_map      = QPushButton(" Carte");              self._btn_map.setFixedHeight(28)
        self._btn_tracking = QPushButton(" Suivi");              self._btn_tracking.setFixedHeight(28)
        self._btn_scen     = QPushButton(" Scénario");           self._btn_scen.setFixedHeight(28)
        self._btn_pdf      = QPushButton(" PDF");                self._btn_pdf.setFixedHeight(28)
        self._btn_csv_exp  = QPushButton(" CSV");                self._btn_csv_exp.setFixedHeight(28)
        _btn_style = (
            f"QPushButton{{background:{C['input']};color:{C['text']};border:1px solid {C['border']};"
            "border-radius:4px;font-size:11px;padding:0 8px;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
        )
        _confirm_style = (
            f"QPushButton{{background:{C['success']};color:#000;border:none;"
            "border-radius:4px;font-size:11px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:#00cc77;}}"
        )
        self._btn_confirm.setStyleSheet(_confirm_style)
        for btn in [self._btn_map, self._btn_tracking, self._btn_scen, self._btn_pdf, self._btn_csv_exp]:
            btn.setStyleSheet(_btn_style)
        for btn in [self._btn_confirm, self._btn_map, self._btn_tracking,
                    self._btn_scen, self._btn_pdf, self._btn_csv_exp]:
            btn.setVisible(False)
            act_row.addWidget(btn)
        act_row.addStretch()
        blo.addLayout(act_row)

        self._btn_confirm.clicked.connect(self._confirm_plan)
        self._btn_map.clicked.connect(lambda: self.main_window._nav_to(8))
        self._btn_tracking.clicked.connect(lambda: self.main_window._nav_to(9))
        self._btn_scen.clicked.connect(self._save_as_scenario)
        self._btn_pdf.clicked.connect(self._export_pdf)
        self._btn_csv_exp.clicked.connect(self._export_csv)
        root.addWidget(bottom)

    # ══════════════════════════════════════════════════════════════════════
    # GAUCHE — Configuration
    # ══════════════════════════════════════════════════════════════════════

    def _build_left_panel(self) -> QWidget:
        outer = QWidget(); outer.setFixedWidth(320)
        outer.setStyleSheet(f"QWidget{{background:{C['bg']};}}")
        lo = QVBoxLayout(outer); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea{{background:{C['bg']};border:none;}}")

        inner = QWidget()
        inner.setStyleSheet(f"QWidget{{background:{C['bg']};}}")
        vlo = QVBoxLayout(inner); vlo.setContentsMargins(10, 10, 10, 10); vlo.setSpacing(8)

        # ── Sélecteur de mode ─────────────────────────────────────────────────
        mode_frame = QFrame()
        mode_frame.setStyleSheet(
            f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:6px;}}"
        )
        mflo = QHBoxLayout(mode_frame)
        mflo.setContentsMargins(8, 6, 8, 6)
        mflo.setSpacing(16)
        self._rb_mode_day  = QRadioButton("Par jour")
        self._rb_mode_week = QRadioButton("Par semaine")
        self._rb_mode_day.setChecked(True)
        for rb in (self._rb_mode_day, self._rb_mode_week):
            rb.setStyleSheet(_RB)
        _bg_mode = QButtonGroup(inner)
        _bg_mode.addButton(self._rb_mode_day)
        _bg_mode.addButton(self._rb_mode_week)
        mflo.addWidget(self._rb_mode_day)
        mflo.addWidget(self._rb_mode_week)
        mflo.addStretch()
        vlo.addWidget(mode_frame)

        # ── Bandeau météo (partagé) ───────────────────────────────────────────
        self._wx_warn_frame = QFrame()
        self._wx_warn_frame.setVisible(False)
        self._wx_warn_frame.setStyleSheet(
            f"QFrame{{background:#2a2210;border:1px solid {C['warning']};border-radius:6px;}}"
        )
        wxlo = QVBoxLayout(self._wx_warn_frame)
        self._wx_warn_lbl = QLabel("")
        self._wx_warn_lbl.setWordWrap(True)
        self._wx_warn_lbl.setStyleSheet(
            f"color:{C['warning']};font-size:11px;padding:6px;background:transparent;"
        )
        wxlo.addWidget(self._wx_warn_lbl)
        vlo.addWidget(self._wx_warn_frame)

        # ── Mode Jour : section Données ───────────────────────────────────────
        self._grp_data_widget = self._grp_data()
        vlo.addWidget(self._grp_data_widget)

        # ── Mode Semaine : section Période + distribution ─────────────────────
        self._grp_week_widget = self._grp_week_period()
        self._grp_week_widget.setVisible(False)
        vlo.addWidget(self._grp_week_widget)

        # ── Groupes partagés (algos, VRP, objectif, avancé, limites) ──────────
        vlo.addWidget(self._grp_algorithms())
        vlo.addWidget(self._grp_vrp_mode())
        vlo.addWidget(self._grp_objective())
        vlo.addWidget(self._grp_advanced())
        vlo.addWidget(self._grp_limits())
        vlo.addStretch()

        # ── Bouton mode Jour : 🚀 Lancer ─────────────────────────────────────
        self._btn_run = QPushButton("🚀 Lancer l'optimisation")
        self._btn_run.setObjectName("primaryBtn")
        self._btn_run.setFixedHeight(48)
        self._btn_run.clicked.connect(self._run_selected)
        vlo.addWidget(self._btn_run)

        self._btn_stop = QPushButton("⏹ Arrêter")
        self._btn_stop.setFixedHeight(36)
        self._btn_stop.setVisible(False)
        self._btn_stop.setStyleSheet(
            f"QPushButton{{background:{C['danger']};color:#fff;border:none;"
            "border-radius:6px;font-weight:700;font-size:13px;}}"
            f"QPushButton:hover{{background:#cc3344;}}"
        )
        self._btn_stop.clicked.connect(self._stop_all)
        vlo.addWidget(self._btn_stop)

        # ── Bouton mode Semaine : 📅 Planifier → ─────────────────────────────
        self._btn_week = QPushButton("📅 Planifier la semaine →")
        self._btn_week.setFixedHeight(48)
        self._btn_week.setVisible(False)
        self._btn_week.setToolTip(
            "Ouvre l'onglet de planification hebdomadaire :\n"
            "benchmark multi-algo + validation interactive."
        )
        self._btn_week.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:#000;"
            "border:none;border-radius:6px;"
            "font-weight:700;font-size:13px;}}"
            f"QPushButton:hover{{background:#00bbee;}}"
        )
        self._btn_week.clicked.connect(lambda: self._tabs.setCurrentIndex(5))
        vlo.addWidget(self._btn_week)

        # ── Connexion toggle ─────────────────────────────────────────────────
        self._rb_mode_day.toggled.connect(self._on_mode_toggled)

        scroll.setWidget(inner)
        lo.addWidget(scroll, 1)
        return outer

    def _grp_data(self) -> QGroupBox:
        grp = QGroupBox("Données"); grp.setStyleSheet(_GRP + _INP + _RB)
        fl = QVBoxLayout(grp); fl.setSpacing(4)
        self._data_clients_lbl  = QLabel("Clients : —")
        self._data_vehicles_lbl = QLabel("Véhicules : —")
        self._data_depots_lbl   = QLabel("Dépôts : —")
        for l in [self._data_clients_lbl, self._data_vehicles_lbl, self._data_depots_lbl]:
            l.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            fl.addWidget(l)
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Date :"))
        self._date_edit = QDateEdit(); self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setDisplayFormat("dd/MM/yyyy")
        date_row.addWidget(self._date_edit)
        fl.addLayout(date_row)
        reload_btn = QPushButton("⟳ Actualiser")
        reload_btn.setFixedHeight(26)
        reload_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text2']};border:1px solid {C['border']};"
            "border-radius:4px;font-size:11px;}}"
        )
        reload_btn.clicked.connect(self._refresh_data_counts)
        fl.addWidget(reload_btn)
        return grp

    def _grp_week_period(self) -> QGroupBox:
        """Contrôles de période & distribution — mode Semaine uniquement."""
        grp = QGroupBox("Période & distribution")
        grp.setStyleSheet(_GRP + _INP + _RB)
        lo = QVBoxLayout(grp)
        lo.setSpacing(6)

        today_py  = date.today()
        monday_py = today_py - timedelta(days=today_py.weekday())

        row_start = QHBoxLayout()
        row_start.addWidget(QLabel("Du :"))
        self._wp_start = QDateEdit()
        self._wp_start.setCalendarPopup(True)
        self._wp_start.setDate(QDate(monday_py.year, monday_py.month, monday_py.day))
        self._wp_start.setDisplayFormat("dd/MM/yyyy")
        row_start.addWidget(self._wp_start)
        lo.addLayout(row_start)

        row_days = QHBoxLayout()
        row_days.addWidget(QLabel("Jours :"))
        self._wp_n_days = QSpinBox()
        self._wp_n_days.setRange(1, 14)
        self._wp_n_days.setValue(5)
        self._wp_n_days.setSuffix(" j")
        row_days.addWidget(self._wp_n_days)
        lo.addLayout(row_days)

        self._wp_rb_distribute = QRadioButton("Distribuer toutes les commandes")
        self._wp_rb_distribute.setToolTip(
            "Répartit toutes les commandes en attente sur N jours,\n"
            "les plus prioritaires d'abord."
        )
        self._wp_rb_distribute.setChecked(True)
        self._wp_rb_scheduled = QRadioButton("Respecter les dates prévues")
        self._wp_rb_scheduled.setToolTip(
            "Planifie uniquement les commandes dont scheduled_date = ce jour."
        )
        lo.addWidget(self._wp_rb_distribute)
        lo.addWidget(self._wp_rb_scheduled)
        return grp

    def _on_mode_toggled(self, day_mode: bool):
        """Bascule visibilité entre mode Par jour et Par semaine."""
        self._grp_data_widget.setVisible(day_mode)
        self._grp_week_widget.setVisible(not day_mode)
        self._btn_run.setVisible(day_mode)
        if not day_mode:
            self._btn_stop.setVisible(False)
        self._btn_week.setVisible(not day_mode)

    def _grp_algorithms(self) -> QGroupBox:
        grp = QGroupBox("Algorithmes"); grp.setStyleSheet(_GRP + _RB)
        fl = QVBoxLayout(grp); fl.setSpacing(2)
        self._chk_greedy  = QCheckBox("Greedy (Glouton)"); self._chk_greedy.setChecked(True)
        self._chk_2opt    = QCheckBox("2-opt (Amélioration locale)"); self._chk_2opt.setChecked(True)
        self._chk_ortools = QCheckBox("OR-Tools (Google VRP)")
        if not ORTOOLS_AVAILABLE:
            self._chk_ortools.setEnabled(False)
            self._chk_ortools.setToolTip("OR-Tools non installé — pip install ortools")
        else:
            self._chk_ortools.setChecked(True)
        for cb in [self._chk_greedy, self._chk_2opt, self._chk_ortools]:
            fl.addWidget(cb)
        return grp

    def _grp_vrp_mode(self) -> QGroupBox:
        grp = QGroupBox("Mode VRP (OR-Tools)"); grp.setStyleSheet(_GRP + _RB)
        fl = QVBoxLayout(grp); fl.setSpacing(2)
        self._vrp_group = QButtonGroup(grp)
        for mode, label in [
            ("standard",        "Standard — VRPTW classique"),
            ("multi_depot",     "Multi-dépôt (M-DVRPTW)"),
            ("open",            "Ouvert (OVRP, pas de retour)"),
            ("pickup_delivery", "Ramassage–Livraison (PDPTW)"),
            ("reload",          "Rechargement intermédiaire"),
        ]:
            rb = QRadioButton(label)
            rb.setProperty("vrp_mode", mode)
            if mode == "standard":
                rb.setChecked(True)
            self._vrp_group.addButton(rb)
            fl.addWidget(rb)
        return grp

    def _grp_objective(self) -> QGroupBox:
        grp = QGroupBox("Objectif d'optimisation"); grp.setStyleSheet(_GRP + _RB + _INP)
        fl = QVBoxLayout(grp); fl.setSpacing(4)
        self._obj_group = QButtonGroup(grp)
        self._obj_distance = QRadioButton("Minimiser distance"); self._obj_distance.setChecked(True)
        self._obj_cost     = QRadioButton("Minimiser coût")
        self._obj_delays   = QRadioButton("Minimiser retards")
        self._obj_balanced = QRadioButton("Équilibré (pondéré)")
        for rb in [self._obj_distance, self._obj_cost, self._obj_delays, self._obj_balanced]:
            self._obj_group.addButton(rb); fl.addWidget(rb)
        self._obj_balanced.toggled.connect(self._toggle_sliders)

        # 4 sliders (visibles seulement si Équilibré)
        self._slider_frame = QFrame()
        self._slider_frame.setVisible(False)
        slo = QVBoxLayout(self._slider_frame); slo.setSpacing(4); slo.setContentsMargins(0,4,0,0)
        self._sliders = {}
        for key, label, default in [
            ("distance", "Distance",  100),
            ("cost",     "Coût",       50),
            ("delays",   "Retards",   200),
            ("co2",      "CO₂",        30),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label} :")
            lbl.setFixedWidth(68)
            lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0, 300); sl.setValue(default); sl.setFixedHeight(18)
            sl.setStyleSheet(
                f"QSlider::groove:horizontal{{background:{C['input']};height:4px;border-radius:2px;}}"
                f"QSlider::handle:horizontal{{background:{C['accent']};width:12px;height:12px;"
                "margin:-4px 0;border-radius:6px;}}"
                f"QSlider::sub-page:horizontal{{background:{C['accent']};border-radius:2px;}}"
            )
            val_lbl = QLabel(str(default)); val_lbl.setFixedWidth(32)
            val_lbl.setStyleSheet(f"color:{C['text']};font-size:11px;background:transparent;")
            sl.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
            row.addWidget(lbl); row.addWidget(sl, 1); row.addWidget(val_lbl)
            slo.addLayout(row)
            self._sliders[key] = sl
        fl.addWidget(self._slider_frame)
        return grp

    def _toggle_sliders(self, on: bool):
        self._slider_frame.setVisible(on)

    def _grp_advanced(self) -> QGroupBox:
        grp = QGroupBox("Options avancées"); grp.setStyleSheet(_GRP + _RB + _INP)
        fl = QVBoxLayout(grp); fl.setSpacing(3)
        self._chk_cluster    = QCheckBox("Pré-clustering KMeans (≥20 clients)")
        self._chk_traffic    = QCheckBox("Ajustement trafic horaire")
        self._chk_rse        = QCheckBox("Pauses RSE (CE 561/2006)")
        self._chk_rse.setChecked(True)
        self._chk_skills     = QCheckBox("Compétences ADR/ZFE/Température")
        self._chk_tw         = QCheckBox("Contraintes fenêtres horaires")
        self._chk_tw.setChecked(True)
        self._chk_lunch      = QCheckBox("Interdire livraison 12h–14h")
        self._chk_forced_seq = QCheckBox("Séquences forcées (config BDD)")

        self._chk_cluster.toggled.connect(self._on_cluster_toggled)
        for cb in [self._chk_cluster, self._chk_traffic, self._chk_rse,
                   self._chk_skills, self._chk_tw, self._chk_lunch, self._chk_forced_seq]:
            fl.addWidget(cb)

        self._cluster_summary = QLabel("")
        self._cluster_summary.setWordWrap(True)
        self._cluster_summary.setStyleSheet(f"color:{C['purple']};font-size:10px;padding-left:20px;background:transparent;")
        fl.addWidget(self._cluster_summary)

        # Conditions météo + trafic
        grp2 = QGroupBox("Météo / trafic"); grp2.setStyleSheet(_GRP + _INP + _RB)
        g2lo = QVBoxLayout(grp2); g2lo.setSpacing(6)

        # Bouton Live OWM
        live_row = QHBoxLayout(); live_row.setSpacing(6)
        live_btn = QPushButton("🌤 Météo en direct")
        live_btn.setFixedHeight(28)
        live_btn.setEnabled(HAS_REQUESTS)
        live_btn.setToolTip(
            "Récupère la météo actuelle via OpenWeatherMap (clé requise dans Paramètres)"
            if HAS_REQUESTS else "Module 'requests' non installé"
        )
        live_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['accent']};border:1px solid {C['border']};"
            "border-radius:4px;font-size:11px;padding:0 10px;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
            f"QPushButton:disabled{{color:{C['text2']};}}"
        )
        live_btn.clicked.connect(self._fetch_live_weather)
        self._weather_live_lbl = QLabel("— conditions non chargées")
        self._weather_live_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:10px;background:transparent;"
        )
        live_row.addWidget(live_btn); live_row.addStretch()
        g2lo.addLayout(live_row)
        g2lo.addWidget(self._weather_live_lbl)

        # Coefficient météo stocké en interne (fixé par OWM, défaut ×1.0)
        self._weather_coeff = 1.0

        traf_row = QHBoxLayout()
        traf_lbl = QLabel("Trafic ×:")
        traf_lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        self._traffic_spin = QDoubleSpinBox()
        self._traffic_spin.setRange(1.0, 5.0); self._traffic_spin.setValue(1.0)
        self._traffic_spin.setSingleStep(0.1)
        self._traffic_spin.valueChanged.connect(self._update_coeff)
        auto_traf = QPushButton("Auto")
        auto_traf.setFixedHeight(24)
        auto_traf.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['accent']};border:1px solid {C['border']};"
            "border-radius:3px;font-size:10px;padding:0 5px;}}"
        )
        auto_traf.clicked.connect(self._auto_traffic)
        traf_row.addWidget(traf_lbl); traf_row.addWidget(self._traffic_spin); traf_row.addWidget(auto_traf)
        g2lo.addLayout(traf_row)

        self._coeff_lbl = QLabel("Coeff. final : ×1.00")
        self._coeff_lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        g2lo.addWidget(self._coeff_lbl)
        fl.addWidget(grp2)
        return grp

    def _grp_limits(self) -> QGroupBox:
        grp = QGroupBox("Limites"); grp.setStyleSheet(_GRP + _INP)
        fl = QVBoxLayout(grp); fl.setSpacing(4)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("OR-Tools (s) :"))
        self._time_spin = QSpinBox(); self._time_spin.setRange(5, 600); self._time_spin.setValue(30)
        row1.addWidget(self._time_spin)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("2-opt iter. :"))
        self._iter_spin = QSpinBox(); self._iter_spin.setRange(100, 10000); self._iter_spin.setValue(1000)
        row2.addWidget(self._iter_spin)
        for l in [row1, row2]: fl.addLayout(l)
        return grp

    # ══════════════════════════════════════════════════════════════════════
    # DROITE — 5 onglets
    # ══════════════════════════════════════════════════════════════════════

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"QWidget{{background:{C['bg']};}}")
        lo = QVBoxLayout(w); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane{{background:{C['bg']};border:none;}}"
            f"QTabBar::tab{{background:{C['panel']};color:{C['text2']};padding:8px 14px;"
            "border-top-left-radius:6px;border-top-right-radius:6px;margin-right:2px;font-size:12px;}"
            f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
            f"QTabBar::tab:hover{{background:{C['hover']};color:{C['text']};}}"
        )
        self._tabs.addTab(self._tab_comparison(),    " Comparaison")
        self._tabs.addTab(self._tab_routes(),        " Détail véhicules")
        self._tabs.addTab(self._tab_charts(),        " Graphiques")
        self._tabs.addTab(self._tab_cost_sim(),      " Simulation coûts")
        self._tabs.addTab(self._tab_compliance(),    " Conformité RSE/ADR/ZFE")
        self._tabs.addTab(self._tab_week_planner(),  "📅 Planif. semaine")
        lo.addWidget(self._tabs, 1)
        return w

    # ── Tab 0 : Comparaison temps réel ────────────────────────────────

    def _tab_comparison(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(12, 10, 12, 8); lo.setSpacing(8)
        sub = QLabel("Résultats mis à jour en temps réel à chaque algorithme terminé.")
        sub.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        lo.addWidget(sub)

        self._cmp_table = QTableWidget()
        self._cmp_table.setColumnCount(4)
        self._cmp_table.setHorizontalHeaderLabels(["Métrique", "Greedy", "2-opt", "OR-Tools"])
        self._cmp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 4): self._cmp_table.setColumnWidth(col, 110)
        self._cmp_table.verticalHeader().setVisible(False)
        self._cmp_table.setAlternatingRowColors(True)
        self._cmp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._cmp_table.setStyleSheet(_TBL)

        self._metrics = [
            ("Distance totale (km)",    True),
            ("Durée totale (min)",       True),
            ("Coût total (€)",           True),
            ("CO₂ total (kg)",           True),
            ("Clients servis",           False),
            ("Respect horaires (%)",     False),
            ("Retard moyen (min)",       True),
            ("Temps CPU (ms)",           True),
            ("Gain vs Glouton (%)",      False),
            ("Utilisation flotte (%)",   False),
            ("Mode VRP",                 None),
            ("Source distance",          None),
        ]
        self._cmp_table.setRowCount(len(self._metrics))
        for i, (m, _) in enumerate(self._metrics):
            it = QTableWidgetItem(m)
            it.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            it.setForeground(QColor(C["text2"]))
            self._cmp_table.setItem(i, 0, it)
            for j in range(1, 4):
                self._cmp_table.setItem(i, j, QTableWidgetItem("—"))
        lo.addWidget(self._cmp_table, 1)

        # Bandeau meilleur algo
        self._best_banner = QLabel("")
        self._best_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._best_banner.setStyleSheet(
            f"color:{C['success']};font-size:14px;font-weight:700;"
            f"background:{C['panel']};border:1px solid {C['success']};"
            "border-radius:6px;padding:8px;"
        )
        self._best_banner.setVisible(False)
        lo.addWidget(self._best_banner)
        return w

    # ── Tab 1 : Détail par véhicule ────────────────────────────────────

    def _tab_routes(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(12, 8, 12, 8); lo.setSpacing(8)

        # Sélecteur algo
        sel_row = QHBoxLayout(); sel_row.setSpacing(6)
        sel_row.addWidget(QLabel("Algorithme :"))
        self._route_algo_cb = QComboBox()
        self._route_algo_cb.addItems(["Greedy", "2-opt", "OR-Tools"])
        self._route_algo_cb.currentIndexChanged.connect(self._refresh_route_tree)
        self._route_algo_cb.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
        )
        sel_row.addWidget(self._route_algo_cb); sel_row.addStretch()
        _csv_btn = QPushButton(" CSV"); _csv_btn.setFixedHeight(28)
        _csv_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;font-size:11px;padding:0 8px;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
        )
        _csv_btn.clicked.connect(self._export_route_csv); sel_row.addWidget(_csv_btn)
        lo.addLayout(sel_row)

        self._route_tree = QTreeWidget()
        self._route_tree.setColumnCount(5)
        self._route_tree.setHeaderLabels(["Véhicule / Arrêt", "Arrivée", "Retard (min)", "Dist. (km)", "Charge (kg)"])
        self._route_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5): self._route_tree.header().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._route_tree.setAlternatingRowColors(True)
        self._route_tree.setStyleSheet(
            f"QTreeWidget{{background:{C['bg']};color:{C['text']};"
            f"border:1px solid {C['border']};alternate-background-color:#0F2035;}}"
            f"QTreeWidget::item:selected{{background:{C['hover']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:4px;}}"
        )
        lo.addWidget(self._route_tree, 1)

        # Lock par véhicule
        lock_note = QLabel("ℹ Verrouillez une tournée pour qu'elle ne soit pas modifiée lors du prochain run.")
        lock_note.setStyleSheet(f"color:{C['text2']};font-size:10px;background:transparent;")
        lock_note.setWordWrap(True)
        lo.addWidget(lock_note)
        return w

    # ── Tab 2 : Graphiques ─────────────────────────────────────────────

    def _tab_charts(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(12, 8, 12, 8); lo.setSpacing(6)
        if not HAS_MPL:
            lbl = QLabel("(Matplotlib non disponible)")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{C['text2']};background:transparent;")
            lo.addWidget(lbl); return w

        self._chart_container = QWidget()
        self._chart_lo = QVBoxLayout(self._chart_container)
        self._chart_lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(self._chart_container, 1)

        regen = QPushButton("⟳ Régénérer graphiques"); regen.setFixedHeight(28)
        regen.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text2']};border:1px solid {C['border']};"
            "border-radius:4px;font-size:11px;padding:0 10px;}}"
        )
        regen.clicked.connect(self._draw_charts)
        lo.addWidget(regen)
        return w

    # ── Tab 3 : Simulation coûts ───────────────────────────────────────

    def _tab_cost_sim(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(12, 8, 12, 8); lo.setSpacing(6)
        info = QLabel("Modifiez les paramètres pour recalculer les coûts sans relancer le VRP.")
        info.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        lo.addWidget(info)

        sl_grp = QGroupBox("Paramètres de coût"); sl_grp.setStyleSheet(_GRP + _INP)
        sl_lo = QVBoxLayout(sl_grp); sl_lo.setSpacing(6)

        self._sim_sliders = {}
        for key, label, mn, mx, default, decimals, suffix in [
            ("fuel_price",   "Prix carburant (€/L)", 100, 300, 185, 2, ""),
            ("toll_factor",  "Péages (€/km)",         0, 100,   0, 2, ""),
            ("labor_rate",   "Taux horaire (€/h)",   100, 400, 150, 2, ""),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(160)
            lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(mn, mx); sl.setValue(default)
            sl.setStyleSheet(
                f"QSlider::groove:horizontal{{background:{C['input']};height:4px;border-radius:2px;}}"
                f"QSlider::handle:horizontal{{background:{C['warning']};width:12px;height:12px;"
                "margin:-4px 0;border-radius:6px;}}"
                f"QSlider::sub-page:horizontal{{background:{C['warning']};border-radius:2px;}}"
            )
            val_lbl = QLabel(f"{default/100:.2f}")
            val_lbl.setFixedWidth(50)
            val_lbl.setStyleSheet(f"color:{C['text']};font-size:11px;background:transparent;")
            sl.valueChanged.connect(lambda v, l=val_lbl, d=decimals: l.setText(f"{v/100:.{d}f}"))
            sl.valueChanged.connect(self._recalc_costs)
            row.addWidget(lbl); row.addWidget(sl, 1); row.addWidget(val_lbl)
            sl_lo.addLayout(row)
            self._sim_sliders[key] = sl
        lo.addWidget(sl_grp)

        # Résultats simulés
        self._cost_result_table = QTableWidget()
        self._cost_result_table.setColumnCount(4)
        self._cost_result_table.setHorizontalHeaderLabels(["Poste de coût", "Greedy", "2-opt", "OR-Tools"])
        self._cost_result_table.setRowCount(6)
        cost_rows = ["Carburant (€)", "Main d'œuvre (€)", "Fixe (€)", "Péages (€)", "CO₂ (kg)", "TOTAL (€)"]
        for i, r in enumerate(cost_rows):
            self._cost_result_table.setItem(i, 0, QTableWidgetItem(r))
            for j in range(1, 4): self._cost_result_table.setItem(i, j, QTableWidgetItem("—"))
        self._cost_result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._cost_result_table.verticalHeader().setVisible(False)
        self._cost_result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._cost_result_table.setStyleSheet(_TBL)
        self._cost_result_table.setMaximumHeight(220)
        lo.addWidget(self._cost_result_table)
        lo.addStretch()
        return w

    # ── Tab 4 : Conformité RSE/ADR/ZFE ────────────────────────────────

    def _tab_compliance(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(12, 8, 12, 8); lo.setSpacing(6)
        info = QLabel("Résultats de conformité calculés après chaque run d'optimisation.")
        info.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        lo.addWidget(info)

        self._comp_algo_cb = QComboBox()
        self._comp_algo_cb.addItems(["Greedy", "2-opt", "OR-Tools"])
        self._comp_algo_cb.currentIndexChanged.connect(self._refresh_compliance_view)
        self._comp_algo_cb.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:4px 8px;}}"
        )
        lo.addWidget(self._comp_algo_cb)

        # 3 panneaux RSE / ADR / ZFE dans un scroll
        scroll_comp = QScrollArea()
        scroll_comp.setWidgetResizable(True)
        scroll_comp.setFrameShape(QFrame.Shape.NoFrame)
        scroll_comp.setStyleSheet(f"QScrollArea{{background:{C['bg']};border:none;}}")
        panels_w = QWidget(); panels_w.setStyleSheet(f"QWidget{{background:{C['bg']};}}")
        panels_lo = QVBoxLayout(panels_w); panels_lo.setSpacing(8); panels_lo.setContentsMargins(0,0,4,0)

        self._comp_panels: dict = {}
        for key, emoji, title in [("rse", "RSE", "RSE — Règlement CE 561/2006"),
                                   ("adr", "ADR", "ADR — Matières dangereuses"),
                                   ("zfe", "ZFE", "ZFE — Zones à faibles émissions")]:
            panel = QFrame()
            panel.setStyleSheet(
                f"QFrame{{background:{C['panel']};border:1px solid {C['border']};"
                "border-radius:6px;padding:6px;}}"
            )
            p_lo = QVBoxLayout(panel); p_lo.setSpacing(4)
            hdr2 = QLabel(f"{emoji}  {title}")
            hdr2.setStyleSheet(f"color:{C['text']};font-weight:700;font-size:12px;background:transparent;")
            p_lo.addWidget(hdr2)
            status_lbl = QLabel("—")
            status_lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            p_lo.addWidget(status_lbl)
            detail_edit = QTextEdit()
            detail_edit.setReadOnly(True)
            detail_edit.setMinimumHeight(90)
            detail_edit.setMaximumHeight(220)
            detail_edit.setStyleSheet(
                f"QTextEdit{{background:{C['bg']};color:{C['text2']};border:1px solid {C['border']};"
                "border-radius:4px;font-size:10px;font-family:Consolas,monospace;padding:4px;}}"
            )
            p_lo.addWidget(detail_edit)
            panels_lo.addWidget(panel)
            self._comp_panels[key] = (status_lbl, detail_edit)

        panels_lo.addStretch()
        scroll_comp.setWidget(panels_w)
        lo.addWidget(scroll_comp, 1)

        fix_btn = QPushButton(" Suggestions de correction")
        fix_btn.setObjectName("primaryBtn"); fix_btn.setFixedHeight(32)
        fix_btn.clicked.connect(self._show_compliance_fixes)
        lo.addWidget(fix_btn)
        lo.addStretch()
        return w

    # ── Tab 5 : Planification hebdomadaire ────────────────────────────────

    def _tab_week_planner(self) -> QWidget:
        """Onglet 5 — résultats uniquement (la config est dans le panneau gauche)."""
        w = QWidget()
        w.setStyleSheet(f"QWidget{{background:{C['bg']};}}")
        lo = QVBoxLayout(w)
        lo.setContentsMargins(12, 10, 12, 10)
        lo.setSpacing(8)

        hdr = QLabel("Planification automatique — benchmark multi-jours")
        hdr.setStyleSheet(
            f"color:{C['text']};font-size:14px;font-weight:700;background:transparent;"
        )
        lo.addWidget(hdr)

        info = QLabel(
            "Configurez la période et le mode dans le panneau gauche (mode « Par semaine »), "
            "puis analysez les algorithmes jour par jour (sans assigner). "
            "Comparez les résultats et validez pour assigner les commandes."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        lo.addWidget(info)

        # ── Boutons d'action ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._wp_btn_analyse = QPushButton("🔍 Analyser (simulation)")
        self._wp_btn_analyse.setObjectName("primaryBtn")
        self._wp_btn_analyse.setFixedHeight(40)
        self._wp_btn_analyse.setToolTip(
            "Lance les algorithmes sur chaque jour en mode simulation\n"
            "(aucune commande n'est assignée — preview uniquement)"
        )
        self._wp_btn_analyse.clicked.connect(self._launch_week_analysis)
        btn_row.addWidget(self._wp_btn_analyse)

        self._wp_btn_validate = QPushButton("✅ Valider et assigner")
        self._wp_btn_validate.setFixedHeight(40)
        self._wp_btn_validate.setEnabled(False)
        self._wp_btn_validate.setToolTip(
            "Confirme les résultats de l'analyse et assigne les commandes en base."
        )
        self._wp_btn_validate.setStyleSheet(
            f"QPushButton{{background:{C['success']};color:#000;border:none;"
            "border-radius:6px;font-weight:700;font-size:13px;}}"
            f"QPushButton:hover{{background:#00cc70;}}"
            f"QPushButton:disabled{{background:{C['border']};color:{C['text2']};}}"
        )
        self._wp_btn_validate.clicked.connect(self._validate_week_plan)
        btn_row.addWidget(self._wp_btn_validate)

        lo.addLayout(btn_row)

        # ── Boutons d'export / navigation ─────────────────────────────────
        act_row = QHBoxLayout()
        act_row.setSpacing(6)

        self._wp_btn_tracking = QPushButton("📍 Suivi")
        self._wp_btn_tracking.setFixedHeight(32)
        self._wp_btn_tracking.setEnabled(False)
        self._wp_btn_tracking.setToolTip(
            "Envoie la planification semaine vers le Gantt de suivi."
        )
        self._wp_btn_tracking.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:5px;font-size:12px;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
            f"QPushButton:disabled{{color:{C['text2']};background:{C['bg']};}}"
        )
        self._wp_btn_tracking.clicked.connect(self._wp_send_to_tracking)
        act_row.addWidget(self._wp_btn_tracking)

        self._wp_btn_pdf = QPushButton("📄 Rapport PDF")
        self._wp_btn_pdf.setFixedHeight(32)
        self._wp_btn_pdf.setEnabled(False)
        self._wp_btn_pdf.setToolTip("Génère un rapport PDF de la planification semaine.")
        self._wp_btn_pdf.setStyleSheet(self._wp_btn_tracking.styleSheet())
        self._wp_btn_pdf.clicked.connect(self._wp_export_pdf)
        act_row.addWidget(self._wp_btn_pdf)

        self._wp_btn_csv = QPushButton("📤 CSV")
        self._wp_btn_csv.setFixedHeight(32)
        self._wp_btn_csv.setEnabled(False)
        self._wp_btn_csv.setToolTip("Exporte tous les arrêts de la semaine en CSV.")
        self._wp_btn_csv.setStyleSheet(self._wp_btn_tracking.styleSheet())
        self._wp_btn_csv.clicked.connect(self._wp_export_csv)
        act_row.addWidget(self._wp_btn_csv)

        act_row.addStretch()
        lo.addLayout(act_row)

        # ── Log de progression ────────────────────────────────────────────
        self._wp_log = QTextEdit()
        self._wp_log.setReadOnly(True)
        self._wp_log.setMaximumHeight(80)
        self._wp_log.setStyleSheet(
            f"QTextEdit{{background:{C['bg']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:4px;"
            "font-size:10px;font-family:Consolas,monospace;padding:4px;}}"
        )
        lo.addWidget(self._wp_log)

        # ── Tableau résultats ─────────────────────────────────────────────
        self._wp_table = QTableWidget()
        self._wp_table.setColumnCount(7)
        self._wp_table.setHorizontalHeaderLabels([
            "Jour", "# Cmd",
            "Greedy", "2-opt", "OR-Tools",
            "Meilleur", "Statut",
        ])
        hh = self._wp_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for col in (2, 3, 4):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._wp_table.verticalHeader().setVisible(False)
        self._wp_table.setAlternatingRowColors(True)
        self._wp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._wp_table.setStyleSheet(_TBL)
        self._wp_table.cellDoubleClicked.connect(self._on_week_day_dblclick)
        lo.addWidget(self._wp_table, 1)

        hint_lbl = QLabel(
            "💡 Double-cliquez sur un jour pour voir le détail "
            "(véhicules, graphiques, coûts, conformité)"
        )
        hint_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;font-style:italic;background:transparent;"
        )
        hint_lbl.setWordWrap(True)
        lo.addWidget(hint_lbl)

        self._wp_summary_lbl = QLabel("")
        self._wp_summary_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;background:transparent;"
        )
        self._wp_summary_lbl.setWordWrap(True)
        lo.addWidget(self._wp_summary_lbl)

        self._pending_week_plan: list = []
        return w

    # ══════════════════════════════════════════════════════════════════════
    # LOGIQUE : données / lancement / callbacks
    # ══════════════════════════════════════════════════════════════════════

    def retranslate_ui(self, lang: str):
        _tab_labels = {
            "fr": [" Comparaison", " Détail véhicules", " Graphiques", " Simulation coûts", " Conformité RSE/ADR/ZFE", "📅 Planif. semaine"],
            "en": [" Comparison", " Vehicle Detail", " Charts", " Cost Simulation", " RSE/ADR/ZFE Compliance", "📅 Week Planning"],
            "ar": [" المقارنة", " تفاصيل المركبات", " الرسوم البيانية", " محاكاة التكاليف", " الامتثال", "📅 تخطيط الأسبوع"],
            "es": [" Comparación", " Detalle vehículos", " Gráficos", " Simulación costes", " Conformidad RSE/ADR/ZFE", "📅 Planif. semana"],
            "de": [" Vergleich", " Fahrzeugdetail", " Diagramme", " Kostensimulation", " Konformität RSE/ADR/ZFE", "📅 Wochenplanung"],
        }
        labels = _tab_labels.get(lang, _tab_labels["fr"])
        if hasattr(self, "_tabs"):
            for i, lbl in enumerate(labels):
                if i < self._tabs.count():
                    self._tabs.setTabText(i, lbl)

    def refresh_data(self):
        self._refresh_data_counts()
        self._poll_weather_warning()

    def _poll_weather_warning(self):
        if self._wx_thread and self._wx_thread.isRunning():
            return

        class _WxThread(QThread):
            done = pyqtSignal(float)

            def run(self):
                from ..services import weather_service as ws
                key = ws.resolve_owm_api_key()
                if not key:
                    self.done.emit(1.0)
                    return
                try:
                    conn = get_connection()
                    d = conn.execute(
                        "SELECT latitude, longitude FROM depots ORDER BY id LIMIT 1"
                    ).fetchone()
                    conn.close()
                    lat = float(d["latitude"]) if d else 33.5731
                    lon = float(d["longitude"]) if d else -7.5898
                except Exception:
                    lat, lon = 33.5731, -7.5898
                w = ws.get_current(lat, lon, key)
                self.done.emit(ws.get_traffic_factor(w) if w else 1.0)

        self._wx_thread = _WxThread(self)
        self._wx_thread.done.connect(self._on_wx_factor)
        self._wx_thread.start()

    def _on_wx_factor(self, fac: float):
        if fac > 1.1:
            self._wx_warn_frame.setVisible(True)
            self._wx_warn_lbl.setText(
                f" Météo réelle : facteur routier ~×{fac:.2f} (> 1.1). "
                "Prévoyez des marges ou ajustez le coefficient météo / trafic ci-dessous."
            )
        else:
            self._wx_warn_frame.setVisible(False)

    def _refresh_data_counts(self):
        try:
            conn = get_connection()
            n_c = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
            n_v = conn.execute("SELECT COUNT(*) FROM vehicles WHERE status='disponible'").fetchone()[0]
            n_d = conn.execute("SELECT COUNT(*) FROM depots").fetchone()[0]
            conn.close()
            self._data_clients_lbl.setText(f"Clients actifs : {n_c}")
            self._data_vehicles_lbl.setText(f"Véhicules disponibles : {n_v}")
            self._data_depots_lbl.setText(f"Dépôts : {n_d}")
        except Exception:
            pass

    def _get_data(self, silent=False):
        planned_date = self._date_edit.date().toString("yyyy-MM-dd")
        conn = get_connection()
        try:
            clients_rows  = conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()
            vehicles_rows = conn.execute("SELECT * FROM vehicles WHERE status='disponible'").fetchall()
            depot_row     = conn.execute("SELECT * FROM depots ORDER BY id LIMIT 1").fetchone()
            # Toujours charger tous les chauffeurs actifs (pour jointure + filtrage)
            all_drivers_rows = conn.execute(
                "SELECT * FROM drivers WHERE COALESCE(archived,0)=0"
            ).fetchall()
            # Indisponibilités pour la date planifiée
            unavail_rows = conn.execute(
                "SELECT driver_id FROM driver_unavailabilities WHERE date=?",
                (planned_date,)
            ).fetchall()
            zones_rows = conn.execute("SELECT * FROM zones").fetchall() if self._chk_skills.isChecked() else []
        except Exception:
            all_drivers_rows = []; unavail_rows = []; zones_rows = []
        finally:
            conn.close()

        clients = [dict(r) for r in clients_rows] if 'clients_rows' in dir() else []
        depot   = dict(depot_row) if 'depot_row' in dir() and depot_row else {"latitude": 33.5731, "longitude": -7.5898}

        # Index chauffeurs par id
        all_drivers = {r["id"]: dict(r) for r in all_drivers_rows}
        # Ensemble des driver_id indisponibles ce jour
        unavail_ids = {r["driver_id"] for r in unavail_rows}

        # Joindre le chauffeur à chaque véhicule + exclure si chauffeur indisponible
        vehicles = []
        skipped  = []
        for row in (vehicles_rows if 'vehicles_rows' in dir() else []):
            v = dict(row)
            driver_id = v.get("driver_id")
            drv = all_drivers.get(driver_id) if driver_id else None
            if drv and driver_id in unavail_ids:
                name = f"{drv.get('first_name','')} {drv.get('last_name','')}".strip()
                skipped.append(f"{v.get('registration','?')} (chauffeur {name or driver_id} indisponible)")
                continue
            if drv:
                v["_driver"] = drv  # disponible pour OR-Tools RSE + conformité
            vehicles.append(v)

        if skipped and not silent:
            self._log(
                f"⚠ {len(skipped)} véhicule(s) exclu(s) — chauffeur indisponible le {planned_date} : "
                + ", ".join(skipped)
            )

        # Liste chauffeurs pour le panneau conformité RSE
        self._drivers_data = list(all_drivers.values()) if self._chk_rse.isChecked() else []
        self._zones_data   = [dict(r) for r in zones_rows]

        try:
            valid_clients, warnings = validate_inputs(clients, vehicles, depot)
            if warnings and not silent:
                self._log(f" {warnings[0]}")
            return valid_clients, vehicles, depot
        except ValidationError as e:
            if not silent:
                QMessageBox.warning(self, "Données manquantes", str(e))
            return None, None, None

    def _get_vrp_mode(self) -> str:
        for btn in self._vrp_group.buttons():
            if btn.isChecked():
                return btn.property("vrp_mode")
        return "standard"

    def _get_objective_weights(self) -> dict:
        if self._obj_balanced.isChecked():
            return {k: self._sliders[k].value() / 100.0 for k in self._sliders}
        if self._obj_cost.isChecked():
            return {"distance": 0.3, "cost": 2.0, "delays": 1.0, "co2": 0.1}
        if self._obj_delays.isChecked():
            return {"distance": 0.5, "cost": 0.3, "delays": 3.0, "co2": 0.1}
        return {"distance": 1.0, "cost": 0.5, "delays": 2.0, "co2": 0.3}

    def _get_weather_coeff(self) -> float:
        return getattr(self, "_weather_coeff", 1.0)

    def _auto_traffic(self):
        sel_date = self._date_edit.date().toPyDate()
        day_type = classify_day_type(sel_date)
        hour     = datetime.now().hour
        coeff    = get_traffic_coefficient(hour, day_type)
        self._traffic_spin.setValue(round(coeff, 2))

    def _fetch_live_weather(self):
        """Récupère la météo en direct via OWM dans un thread et applique le coefficient."""
        class _OwmThread(QThread):
            done  = pyqtSignal(dict)
            error = pyqtSignal(str)
            def __init__(self, lat, lon, key):
                super().__init__(); self.lat = lat; self.lon = lon; self.key = key
            def run(self):
                try:
                    from ..services import weather_service as ws
                    cur = ws.get_current(self.lat, self.lon, self.key)
                    if cur:
                        self.done.emit(cur)
                    else:
                        self.error.emit("Aucune donnée météo reçue.")
                except Exception as e:
                    self.error.emit(str(e))

        try:
            from ..services import weather_service as ws
            key = ws.resolve_owm_api_key()
            if not key:
                show_toast(self.window(),
                    "Clé OpenWeatherMap absente. Ajoutez-la dans Paramètres → Entreprise.", "info")
                return
            conn = get_connection()
            depot = conn.execute("SELECT latitude, longitude FROM depots ORDER BY id LIMIT 1").fetchone()
            conn.close()
            lat = float(depot["latitude"]) if depot else 33.5731
            lon = float(depot["longitude"]) if depot else -7.5898
        except Exception as e:
            show_toast(self.window(), f"Erreur: {e}", "error"); return

        self._weather_live_lbl.setText("⏳ Chargement…")
        thread = _OwmThread(lat, lon, key)
        thread.done.connect(self._apply_owm_weather)
        thread.error.connect(lambda msg: (
            self._weather_live_lbl.setText("❌ Erreur"),
            show_toast(self.window(), f"Météo OWM: {msg}", "error")
        ))
        thread.finished.connect(lambda: None)
        if not hasattr(self, "_owm_threads"): self._owm_threads = []
        self._owm_threads.append(thread)
        thread.start()

    def _apply_owm_weather(self, cur: dict):
        """Applique la météo OWM : stocke le coefficient météo + met à jour le trafic."""
        from ..services import weather_service as ws
        main_cond = (cur.get("main") or "").lower()
        temp      = cur.get("temp", 0)
        tf        = ws.get_traffic_factor(cur)

        # Stocker le coefficient météo
        self._weather_coeff = tf

        # Trafic horaire × météo
        sel_date   = self._date_edit.date().toPyDate()
        day_type   = classify_day_type(sel_date)
        hour_coeff = get_traffic_coefficient(datetime.now().hour, day_type)
        combined   = round(hour_coeff * tf, 2)
        self._traffic_spin.setValue(min(combined, 5.0))

        cond_fr = {
            "clear": "Dégagé", "clouds": "Nuageux", "rain": "Pluie",
            "drizzle": "Bruine", "snow": "Neige", "thunderstorm": "Orage",
            "mist": "Brume", "fog": "Brouillard",
        }.get(main_cond, cur.get("main", "?"))

        self._weather_live_lbl.setText(
            f"🌡 {cond_fr} {temp:.0f}°C  —  météo ×{tf:.2f}  ×  trafic ×{hour_coeff:.2f}"
        )
        self._weather_live_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:10px;background:transparent;"
        )
        self._update_coeff()
        show_toast(self.window(),
            f"Météo : {cond_fr} {temp:.0f}°C — coeff. final ×{combined:.2f}", "success")

    def _update_coeff(self, *_):
        t = self._traffic_spin.value()
        w = self._get_weather_coeff()
        self._coeff_lbl.setText(f"Coeff. final : ×{t * w:.2f}")

    def _on_cluster_toggled(self, checked: bool):
        if checked:
            cl, veh, _ = self._get_data(silent=True)
            if cl and veh:
                summary = get_cluster_summary(cl, veh)
                self._cluster_summary.setText("\n".join(summary) if summary else "")
        else:
            self._cluster_summary.setText("")

    def _run_selected(self):
        clients, vehicles, depot = self._get_data()
        if clients is None:
            return
        algos = []
        if self._chk_greedy.isChecked():  algos.append("greedy")
        if self._chk_2opt.isChecked():    algos.append("2opt")
        if self._chk_ortools.isChecked() and ORTOOLS_AVAILABLE: algos.append("ortools")
        if not algos:
            show_toast(self.window(), "Sélectionnez au moins un algorithme.", "info"); return

        self.results = {}; self._greedy_ref = None; self._compliance = {}
        self._pending = list(algos)
        self._running = True
        self._btn_run.setVisible(False); self._btn_stop.setVisible(True)
        self._prog_bar.setVisible(True)
        self._log(f"> Lancement {len(algos)} algorithme(s)…")
        self._launch_next(clients, vehicles, depot)

    def _launch_next(self, clients, vehicles, depot):
        if not self._pending or not self._running:
            return
        algo = self._pending.pop(0)
        params = {
            "max_iterations": self._iter_spin.value(),
            "time_limit":     self._time_spin.value(),
            "legal_break":    self._chk_rse.isChecked(),
            "vrp_mode":       self._get_vrp_mode(),
            "objective_weights": self._get_objective_weights(),
            "zones":          self._zones_data if hasattr(self, "_zones_data") else [],
            "forced_sequence": [] if not self._chk_forced_seq.isChecked() else self._load_forced_sequences(),
            "lunch_window":   (720, 840) if self._chk_lunch.isChecked() else None,
        }
        self._current_params = params
        t = OptimizationThread(
            algo, clients, depot, vehicles,
            self._traffic_spin.value(), self._get_weather_coeff(),
            params,
            use_clustering=self._chk_cluster.isChecked(),
            greedy_ref=self._greedy_ref,
            zones=self._zones_data if hasattr(self, "_zones_data") else [],
            drivers=self._drivers_data if hasattr(self, "_drivers_data") else [],
        )
        t.progress.connect(self._on_progress)
        t.finished.connect(self._on_result)
        t.error.connect(self._on_error)
        t.compliance.connect(self._on_compliance)
        self._threads.append(t)
        t.start()
        self._log(f"  • {algo.upper()} démarré…")

    def _stop_all(self):
        self._running = False
        self._pending.clear()
        for t in self._threads:
            if hasattr(t, "stop"): t.stop()
        self._set_running(False)
        self._log("Stop Arrêté par l'utilisateur.")
        show_toast(self.window(), "Optimisation arrêtée.", "info")

    def _on_progress(self, msg: str):
        self._prog_status.setText(msg); self._log(f"  {msg}")

    def _on_error(self, algo: str, msg: str):
        self._log(f" [{algo}] {msg}")
        show_toast(self.window(), f"{algo}: {msg}", "error")
        if not self._pending:
            self._set_running(False)

    def _on_result(self, algo: str, result: dict):
        if algo == "greedy":
            self._greedy_ref = result
        self.results[algo] = result
        self._update_cmp_table()
        self._refresh_route_tree()
        self._recalc_costs()

        dist = result.get("total_distance_km", 0)
        cpu  = result.get("cpu_time_ms", 0)
        resp = result.get("respect_rate", 0)
        src  = result.get("distance_source", "")
        self._source_badge.setText(f"Source: {src.upper()}")
        self._log(f" [{algo}] {dist:.1f} km | {resp:.0f}% | {cpu:.0f} ms | {src}")
        show_toast(self.window(), f"{algo}: {dist:.1f} km | {resp:.0f}%", "success")

        greedy_dist = (self._greedy_ref or {}).get("total_distance_km", 0)
        save_result(result, greedy_dist)
        self.routes_ready.emit(result)

        if not self._pending:
            self._set_running(False)
            self._draw_charts()
            self._show_post_actions()
            self._update_best_banner()

        # Lancer le prochain (chaîne séquentielle pour éviter la surcharge)
        if self._pending and self._running:
            clients, vehicles, depot = self._get_data(silent=True)
            if clients:
                self._launch_next(clients, vehicles, depot)

    def _on_compliance(self, algo: str, comp: dict):
        self._compliance[algo] = comp
        self._refresh_compliance_view()

    def _set_running(self, running: bool):
        self._running = running
        self._btn_run.setVisible(not running)
        self._btn_stop.setVisible(running)
        self._prog_bar.setVisible(running)
        if not running:
            self._prog_status.setText("Terminé.")

    # ══════════════════════════════════════════════════════════════════════
    # MISE À JOUR DES ONGLETS
    # ══════════════════════════════════════════════════════════════════════

    def _update_cmp_table(self):
        col_map = {"greedy": 1, "2opt": 2, "ortools": 3}
        g_dist = (self._greedy_ref or {}).get("total_distance_km") or 0

        for algo, col in col_map.items():
            if algo not in self.results: continue
            r    = self.results[algo]
            gain = ((g_dist - r.get("total_distance_km", 0)) / g_dist * 100) if g_dist else 0
            fleet= sum(1 for rt in r.get("routes", []) if rt.get("route"))
            total= max(len(r.get("routes", [])), 1)

            values = [
                f"{r.get('total_distance_km', 0):.2f}",
                f"{r.get('total_duration_min', 0):.1f}",
                f"{r.get('total_cost', 0):.2f}",
                f"{r.get('total_co2_kg', sum(calculate_co2(rt.get('distance_km', 0), rt.get('vehicle') or {}) for rt in r.get('routes', []))):.2f}",
                f"{r.get('clients_served', 0)} / {r.get('clients_total', 0)}",
                f"{r.get('respect_rate', 0):.1f}",
                f"{r.get('avg_delay_min', 0):.1f}",
                f"{r.get('cpu_time_ms', 0):.1f}",
                f"{gain:.1f}" if algo != "greedy" else "—",
                f"{fleet / total * 100:.0f}",
                r.get("vrp_mode", "standard"),
                r.get("distance_source", ""),
            ]
            for row_i, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._cmp_table.setItem(row_i, col, item)

        self._highlight_best_cmp()

    def _highlight_best_cmp(self):
        minimize_rows = {0, 1, 2, 3, 6, 7}
        maximize_rows = {4, 5, 8, 9}
        for row_i, (_, minimize) in enumerate(self._metrics):
            if minimize is None: continue
            vals = []
            for col in range(1, 4):
                it = self._cmp_table.item(row_i, col)
                if it and it.text() not in ("—", "", ""):
                    try:
                        v = float(it.text().split("/")[0].strip())
                        vals.append((col, v))
                    except ValueError:
                        pass
            if len(vals) < 2: continue
            best_col = (min if minimize else max)(vals, key=lambda x: x[1])[0]
            it = self._cmp_table.item(row_i, best_col)
            if it:
                it.setForeground(QColor(C["success"]))
                f = it.font(); f.setBold(True); it.setFont(f)

    def _update_best_banner(self):
        if not self.results: return
        best = min(self.results.items(), key=lambda kv: kv[1].get("total_distance_km", 1e9))
        algo, res = best
        dist = res.get("total_distance_km", 0)
        gain = 0
        if algo != "greedy" and "greedy" in self.results:
            gd = self.results["greedy"].get("total_distance_km", 0)
            gain = (gd - dist) / gd * 100 if gd else 0
        self._best_banner.setText(
            f" Meilleur algo : {algo.upper()} — {dist:.1f} km"
            + (f" (gain {gain:.1f}% vs Greedy)" if gain > 0 else "")
        )
        self._best_banner.setVisible(True)

    def _refresh_route_tree(self):
        algo_map = {"Greedy": "greedy", "2-opt": "2opt", "OR-Tools": "ortools"}
        algo = algo_map.get(self._route_algo_cb.currentText(), "greedy")
        result = self.results.get(algo)
        self._route_tree.clear()
        if not result: return

        for route in result.get("routes", []):
            stops = [s for s in route.get("route", []) if s.get("type") == "delivery"]
            if not stops: continue
            veh  = route.get("vehicle", {})
            reg  = veh.get("registration", f"V{route.get('vehicle_index',0)+1}")
            dist = route.get("distance_km", 0)
            load = route.get("load_kg", 0)
            co2  = route.get("co2_kg", 0)
            drv_info = veh.get("_driver") or {}
            drv_name = f"{drv_info.get('first_name','')} {drv_info.get('last_name','')}".strip()
            v_label  = f" {reg}" + (f"  ·  {drv_name}" if drv_name else "  · Chauffeur non assigné")
            v_item = QTreeWidgetItem([
                v_label,
                f"{route.get('duration_min', 0):.0f} min",
                "",
                f"{dist:.1f}",
                f"{load:.0f} kg | CO₂ {co2:.1f} kg",
            ])
            v_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            v_item.setForeground(0, QColor(C["accent"] if drv_name else C["warning"]))

            act_w = QWidget()
            act_lo = QHBoxLayout(act_w)
            act_lo.setContentsMargins(0, 0, 0, 0)
            act_lo.setSpacing(4)
            lock_btn = QPushButton("Verrou.")
            lock_btn.setFixedSize(52, 22)
            lock_btn.setToolTip("Verrouiller la tournée (base routes)")
            lock_btn.setStyleSheet(
                f"QPushButton{{background:{C['input']};color:{C['text2']};"
                "border:none;border-radius:3px;font-size:10px;padding:0 4px;}}"
            )
            lock_btn.clicked.connect(lambda _, r=result, rt=route, v=veh, b=lock_btn: self._lock_route(r, rt, v, b))
            man_btn = QPushButton("Manif.")
            man_btn.setFixedSize(48, 22)
            man_btn.setToolTip("Manifeste de chargement (PDF)")
            man_btn.setStyleSheet(lock_btn.styleSheet())
            man_btn.clicked.connect(lambda _, rt=route: self._export_load_manifest(rt))
            cmr_btn = QPushButton("CMR")
            cmr_btn.setFixedSize(40, 22)
            cmr_btn.setToolTip("Lettre de voiture CMR (PDF)")
            cmr_btn.setStyleSheet(lock_btn.styleSheet())
            cmr_btn.clicked.connect(lambda _, rt=route: self._export_cmr_route(rt))
            act_lo.addWidget(lock_btn)
            act_lo.addWidget(man_btn)
            act_lo.addWidget(cmr_btn)

            for stop in stops:
                c      = stop.get("client") or {}
                arr    = stop.get("arrival_time", 0)
                delay  = stop.get("delay", 0)
                d_from = stop.get("distance_from_prev", 0)
                s_item = QTreeWidgetItem([
                    f"  {c.get('name', '')}",
                    f"{arr:.0f}",
                    f"{delay:.0f}" if delay else "",
                    f"{d_from:.1f}",
                    f"{c.get('demand_kg', 0):.0f}",
                ])
                if delay > 0:
                    s_item.setForeground(2, QColor(C["warning"]))
                v_item.addChild(s_item)

            self._route_tree.addTopLevelItem(v_item)
            self._route_tree.setItemWidget(v_item, 4, act_w)
        self._route_tree.expandAll()

    def _resolve_db_route_id(self, vehicle: dict) -> int | None:
        vid = vehicle.get("id")
        if not vid:
            return None
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT id FROM routes WHERE vehicle_id= ? ORDER BY id DESC LIMIT 1",
                (int(vid),),
            ).fetchone()
            conn.close()
            return int(row["id"]) if row else None
        except Exception:
            return None

    def _first_order_id_on_route(self, route_id: int) -> int | None:
        try:
            conn = get_connection()
            row = conn.execute(
                """SELECT order_id FROM route_stops
                   WHERE route_id= ? AND order_id IS NOT NULL
                   ORDER BY stop_order LIMIT 1""",
                (route_id,),
            ).fetchone()
            conn.close()
            return int(row["order_id"]) if row and row["order_id"] else None
        except Exception:
            return None

    def _export_load_manifest(self, route: dict):
        if not REPORTLAB_OK:
            show_toast(self.window(), "Installez reportlab pour le PDF.", "error")
            return
        veh = route.get("vehicle") or {}
        reg = (veh.get("registration") or "vehicule").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "Manifeste de chargement", f"manifeste_{reg}.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            svc = ReportService()
            rid = self._resolve_db_route_id(veh)
            if rid is not None:
                svc.generate_load_manifest(rid, path)
            else:
                svc.generate_load_manifest_from_optimization_route(route, path)
            show_toast(self.window(), f"Manifeste généré : {path}", "success")
        except Exception as e:
            QMessageBox.warning(self, "Manifeste", str(e))

    def _export_cmr_route(self, route: dict):
        if not REPORTLAB_OK:
            show_toast(self.window(), "Installez reportlab pour le PDF.", "error")
            return
        veh = route.get("vehicle") or {}
        reg = (veh.get("registration") or "vehicule").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(self, "CMR", f"CMR_{reg}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            svc = ReportService()
            rid = self._resolve_db_route_id(veh)
            oid = self._first_order_id_on_route(rid) if rid is not None else None
            if oid is not None:
                svc.generate_cmr(oid, path)
            else:
                svc.generate_cmr_from_optimization_route(route, path)
            show_toast(self.window(), f"CMR généré : {path}", "success")
        except Exception as e:
            QMessageBox.warning(self, "CMR", str(e))

    def _lock_route(self, result: dict, route: dict, vehicle: dict, btn: QPushButton = None):
        """Persiste la tournée dans routes+route_stops avec is_locked=1."""
        vid = vehicle.get("id")
        if not vid:
            show_toast(self.window(), "Véhicule sans ID — impossible de verrouiller.", "warning")
            return
        planned_date = self._date_edit.date().toString("yyyy-MM-dd")
        stops = [s for s in route.get("route", []) if s.get("type") == "delivery"]
        if not stops:
            show_toast(self.window(), "Aucun arrêt à verrouiller.", "warning")
            return
        try:
            conn = get_connection()
            # Ajouter client_id si absent (requis par _load_forced_sequences)
            try:
                conn.execute("ALTER TABLE route_stops ADD COLUMN client_id INTEGER")
                conn.commit()
            except Exception:
                pass
            # Trouver ou créer la route
            row = conn.execute(
                "SELECT id FROM routes WHERE vehicle_id=? AND planned_date=? ORDER BY id DESC LIMIT 1",
                (int(vid), planned_date),
            ).fetchone()
            if row:
                route_id = int(row["id"])
                conn.execute("UPDATE routes SET is_locked=1 WHERE id=?", (route_id,))
            else:
                conn.execute(
                    """INSERT INTO routes (vehicle_id, planned_date, status, is_locked,
                       total_km, total_duration_min, stops_count)
                       VALUES (?,?,?,?,?,?,?)""",
                    (int(vid), planned_date, "planned", 1,
                     route.get("distance_km", 0),
                     route.get("duration_min", 0),
                     len(stops)),
                )
                route_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            # Remplacer les arrêts
            conn.execute("DELETE FROM route_stops WHERE route_id=?", (route_id,))
            for i, stop in enumerate(stops):
                client = stop.get("client") or {}
                cid = client.get("id")
                order_id = None
                if cid:
                    ord_row = conn.execute(
                        "SELECT id FROM orders WHERE client_id=? AND archived=0 ORDER BY id DESC LIMIT 1",
                        (int(cid),),
                    ).fetchone()
                    if ord_row:
                        order_id = int(ord_row["id"])
                arr_min = float(stop.get("arrival_time") or 0)
                dep_min = float(stop.get("departure_time") or arr_min)
                arr_str = f"{int(arr_min // 60):02d}:{int(arr_min % 60):02d}"
                dep_str = f"{int(dep_min // 60):02d}:{int(dep_min % 60):02d}"
                conn.execute(
                    """INSERT INTO route_stops
                       (route_id, order_id, client_id, stop_type, stop_order,
                        planned_arrival, planned_departure, distance_from_prev_km, status, is_locked)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (route_id, order_id, cid, "delivery", i + 1,
                     arr_str, dep_str,
                     stop.get("distance_from_prev", 0),
                     "pending", 1),
                )
            conn.commit()
            conn.close()
            log_action("ROUTE_LOCK",
                       f"Tournée verrouillée — véhicule #{vid} ({vehicle.get('registration','')}), "
                       f"{len(stops)} arrêts, date {planned_date}")
            if btn:
                btn.setText("🔒")
                btn.setStyleSheet(
                    f"QPushButton{{background:{C['purple']};color:#fff;"
                    "border:none;border-radius:3px;font-size:10px;padding:0 4px;}}"
                )
                btn.setToolTip("Tournée verrouillée — séquence forcée au prochain run")
            show_toast(self.window(),
                       f"{vehicle.get('registration','')} verrouillé ({len(stops)} arrêts).",
                       "success")
        except Exception as e:
            logger.exception("Erreur verrouillage tournée")
            show_toast(self.window(), f"Erreur verrouillage : {e}", "error")

    def _draw_charts(self):
        if not HAS_MPL or not self.results: return
        for i in reversed(range(self._chart_lo.count())):
            w = self._chart_lo.itemAt(i).widget()
            if w: w.deleteLater()

        try:
            fig, axes = plt.subplots(1, 3, figsize=(14, 4))
            fig.patch.set_facecolor("#112240")
            for ax in axes: ax.set_facecolor("#0D1B2A")

            labels = [a.upper() for a in self.results]
            colors = [C["accent"], C["success"], C["warning"]][:len(labels)]

            # ── Radar (distances/cost/respect) ────────────────────────
            cats = ["Distance", "Coût", "Respect", "CO₂ inv."]
            n_cats = len(cats)
            angles = [n / n_cats * 2 * 3.14159 + 3.14159 / 2 for n in range(n_cats)]
            angles += [angles[0]]

            max_dist = max(r.get("total_distance_km", 1) for r in self.results.values()) or 1
            max_cost = max(r.get("total_cost", 1) for r in self.results.values()) or 1
            ax0 = axes[0]; ax0.set_facecolor("#0D1B2A")

            for (algo, res), col in zip(self.results.items(), colors):
                vals = [
                    1 - res.get("total_distance_km", 0) / max_dist,
                    1 - res.get("total_cost", 0) / max_cost,
                    res.get("respect_rate", 0) / 100,
                    1 - min(res.get("total_co2_kg", 0), 100) / 100,
                ]
                vals += [vals[0]]
                ax0.plot(angles, vals, "o-", color=col, linewidth=2, label=algo.upper(), markersize=4)
                ax0.fill(angles, vals, color=col, alpha=0.15)

            ax0.set_xticks(angles[:-1]); ax0.set_xticklabels(cats, color=C["text2"], fontsize=9)
            ax0.set_yticklabels([]); ax0.set_title("Radar perf.", color=C["text2"], fontsize=10)
            ax0.tick_params(colors=C["text2"])
            for sp in ax0.spines.values(): sp.set_color(C["border"])
            ax0.legend(loc="upper right", fontsize=8, labelcolor=C["text2"], framealpha=0)

            # ── Histogramme distances ──────────────────────────────────
            ax1 = axes[1]
            dists = [r.get("total_distance_km", 0) for r in self.results.values()]
            bars  = ax1.bar(labels, dists, color=colors, edgecolor=C["border"], linewidth=0.5)
            ax1.set_title("Distance (km)", color=C["text2"], fontsize=10)
            ax1.tick_params(colors=C["text2"]); ax1.yaxis.label.set_color(C["text2"])
            for sp in ax1.spines.values(): sp.set_color(C["border"])
            for bar, d in zip(bars, dists):
                ax1.text(bar.get_x() + bar.get_width()/2, d * 1.02, f"{d:.1f}",
                         ha="center", va="bottom", color=C["text"], fontsize=9)

            # ── Camembert utilisation flotte ──────────────────────────
            ax2 = axes[2]
            algo_best = min(self.results.items(), key=lambda kv: kv[1].get("total_distance_km", 1e9))
            routes_best = algo_best[1].get("routes", [])
            used  = sum(1 for r in routes_best if r.get("route"))
            empty = len(routes_best) - used
            if used + empty > 0:
                wedges, texts, autotexts = ax2.pie(
                    [used, empty],
                    labels=["Utilisés", "Vides"],
                    colors=[C["success"], C["border"]],
                    autopct="%1.0f%%",
                    startangle=90,
                    textprops={"color": C["text2"], "fontsize": 9},
                )
                for at in autotexts: at.set_color(C["text"]); at.set_fontweight("bold")
            ax2.set_title(f"Flotte ({algo_best[0].upper()})", color=C["text2"], fontsize=10)

            fig.tight_layout(pad=0.4)
            canvas = FigCanvas(fig); canvas.setMinimumHeight(250)
            self._chart_lo.addWidget(canvas)
            plt.close(fig)
        except Exception as e:
            logger.debug("Chart error: %s", e)

    def _recalc_costs(self):
        fuel_price  = self._sim_sliders["fuel_price"].value() / 100.0
        toll_factor = self._sim_sliders["toll_factor"].value() / 100.0
        labor_rate  = self._sim_sliders["labor_rate"].value() / 100.0

        col_map = {"greedy": 1, "2opt": 2, "ortools": 3}
        for algo, col in col_map.items():
            if algo not in self.results:
                for row in range(6):
                    self._cost_result_table.setItem(row, col, QTableWidgetItem("—"))
                continue
            result = self.results[algo]

            # Calcul par véhicule avec ses vraies données (consommation, motorisation, co2…)
            total_fuel = total_labor = total_fixed = total_toll = total_co2 = 0.0
            for route in result.get("routes", []):
                veh = dict(route.get("vehicle") or {})
                # Fallbacks si données absentes en BDD
                if not veh.get("fuel_consumption_l100km"):
                    veh["fuel_consumption_l100km"] = 12.0
                drv = {"hourly_rate": labor_rate}
                stops = route.get("route", [])
                cost = calculate_route_cost(stops, veh, drv, fuel_price, toll_factor)
                total_fuel  += cost["fuel_cost"]
                total_labor += cost["labor_cost"]
                total_fixed += cost["fixed_cost"]
                total_toll  += cost["toll_estimate"]
                total_co2   += calculate_co2(route.get("distance_km", 0), veh)

            total = total_fuel + total_labor + total_fixed + total_toll
            rows_vals = [
                f"{total_fuel:.2f}",
                f"{total_labor:.2f}",
                f"{total_fixed:.2f}",
                f"{total_toll:.2f}",
                f"{total_co2:.2f}",
                f"{total:.2f}",
            ]
            for i, v in enumerate(rows_vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if i == 5:
                    it.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                    it.setForeground(QColor(C["warning"]))
                self._cost_result_table.setItem(i, col, it)

    def _refresh_compliance_view(self):
        algo_map = {"Greedy": "greedy", "2-opt": "2opt", "OR-Tools": "ortools"}
        algo = algo_map.get(self._comp_algo_cb.currentText(), "greedy")
        comp = self._compliance.get(algo)

        for key in ("rse", "adr", "zfe"):
            status_lbl, detail_lbl = self._comp_panels[key]
            if not comp:
                status_lbl.setText("— (aucun résultat)"); detail_lbl.setPlainText(""); continue
            data = comp.get(key, {})
            ok   = data.get("compliant", True)
            viols = data.get("violations", [])
            warns = data.get("warnings", [])
            status_lbl.setText(" Conforme" if ok else f" {len(viols)} violation(s)")
            status_lbl.setStyleSheet(
                f"color:{C['success'] if ok else C['danger']};font-size:12px;font-weight:700;background:transparent;"
            )
            lines = viols + ([f"⚠ {w}" for w in warns])
            detail_lbl.setPlainText("\n".join(lines) if lines else "Aucune violation détectée.")

    def _show_compliance_fixes(self):
        algo_map = {"Greedy": "greedy", "2-opt": "2opt", "OR-Tools": "ortools"}
        algo_label = self._comp_algo_cb.currentText()
        algo = algo_map.get(algo_label, "greedy")
        comp = self._compliance.get(algo, {})
        if not comp:
            show_toast(self.window(), "Lancez d'abord une optimisation.", "info"); return

        rse_data = comp.get("rse", {})
        adr_data = comp.get("adr", {})
        zfe_data = comp.get("zfe", {})
        rse_viols = rse_data.get("violations", [])
        adr_viols = adr_data.get("violations", [])
        zfe_viols = zfe_data.get("violations", [])
        total = len(rse_viols) + len(adr_viols) + len(zfe_viols)

        if total == 0:
            show_toast(self.window(), "Aucune violation — tout est conforme !", "success")
            return

        suggestions = []

        # ── RSE suggestions ───────────────────────────────────────────
        if rse_viols:
            n_rse = len(rse_viols)
            # Detect long drive times from violation messages
            max_h = 0.0
            for v in rse_viols:
                try:
                    import re
                    m = re.search(r"(\d+\.\d+)h", v)
                    if m:
                        max_h = max(max_h, float(m.group(1)))
                except Exception:
                    pass

            suggestions.append("🕐  VIOLATIONS RSE — Règlement CE 561/2006")
            suggestions.append(f"   {n_rse} violation(s) de conduite sans pause suffisante (max 4h30).")

            if algo == "greedy":
                suggestions.append(
                    "   ⚠ L'algorithme Glouton ne gère pas les pauses RSE.\n"
                    "   → Relancez avec OR-Tools et la case 'Pauses RSE' cochée."
                )
            elif algo in ("2opt", "ortools") and max_h > 6:
                suggestions.append(
                    "   → Les routes sont trop longues (>{:.0f}h de conduite).".format(max_h)
                )

            # Count unique drivers with violations
            import re as _re
            drivers_viol = set(_re.findall(r"\[.*?/(.*?)\]", "\n".join(rse_viols)))
            if drivers_viol:
                suggestions.append(
                    f"   → Chauffeurs concernés : {', '.join(sorted(drivers_viol)[:5])}"
                    + (" …" if len(drivers_viol) > 5 else "")
                )

            suggestions.append("")
            suggestions.append("   Actions recommandées :")
            if algo != "ortools":
                suggestions.append("   1. Utilisez OR-Tools avec 'Pauses RSE (CE 561/2006)' cochée")
                suggestions.append("      → Le solveur insère automatiquement des pauses de 45 min")
            else:
                suggestions.append("   1. 'Pauses RSE' est cochée mais les routes restent longues :")
            suggestions.append(
                "   2. Ajoutez des véhicules pour réduire le nb de clients/tournée\n"
                "      (actuellement ~{} clients/véhicule)".format(
                    round(len(self._clients_data) / max(len(self._vehicles_data), 1))
                    if hasattr(self, "_clients_data") and hasattr(self, "_vehicles_data")
                    else "?"
                )
            )
            suggestions.append(
                "   3. Activez 'Interdire livraison 12h–14h'\n"
                "      → Force une coupure naturelle au déjeuner"
            )
            suggestions.append(
                "   4. Définissez des fenêtres horaires plus strictes sur les clients\n"
                "      → OR-Tools crée des routes plus courtes pour les respecter"
            )
            suggestions.append("")

        # ── ADR suggestions ───────────────────────────────────────────
        if adr_viols:
            suggestions.append("☢  VIOLATIONS ADR — Matières dangereuses")
            suggestions.append(f"   {len(adr_viols)} violation(s) détectée(s).")
            suggestions.append("   Actions recommandées :")
            suggestions.append(
                "   1. Cochez 'Compétences ADR/ZFE/Température' dans les options avancées\n"
                "      → OR-Tools n'affecte les commandes ADR qu'aux véhicules homologués"
            )
            suggestions.append(
                "   2. Vérifiez que vos véhicules ont la case 'ADR' cochée dans leur fiche\n"
                "      (Page Véhicules → onglet Capacités)"
            )
            suggestions.append(
                "   3. Vérifiez que les chauffeurs concernés ont la qualification ADR\n"
                "      (Page Chauffeurs → onglet Permis & Qualifs)"
            )
            suggestions.append("")

        # ── ZFE suggestions ───────────────────────────────────────────
        if zfe_viols:
            suggestions.append("🚫  VIOLATIONS ZFE — Zones à faibles émissions")
            suggestions.append(f"   {len(zfe_viols)} violation(s) détectée(s).")
            suggestions.append("   Actions recommandées :")
            suggestions.append(
                "   1. Cochez 'Compétences ADR/ZFE/Température'\n"
                "      → OR-Tools pénalise les véhicules non autorisés en ZFE (×1.5)"
            )
            suggestions.append(
                "   2. Marquez vos véhicules propres comme 'Autorisé ZFE'\n"
                "      (Page Véhicules → onglet Capacités → case ZFE)"
            )
            suggestions.append(
                "   3. Assignez les tournées ZFE aux véhicules électriques/hybrides"
            )
            suggestions.append("")

        # ── Dialog ────────────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Suggestions de correction — {algo_label}")
        dlg.setMinimumWidth(560)
        dlg.setMinimumHeight(420)
        dlg.setStyleSheet(
            "QDialog{background:#0D1B2A;color:#E8F4F8;}"
            "QLabel{background:transparent;}"
            "QTextEdit{background:#112240;color:#E8F4F8;border:1px solid #1E3A5F;"
            "border-radius:6px;font-family:Consolas,monospace;font-size:12px;}"
        )
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(18, 14, 18, 14)
        lo.setSpacing(10)

        title = QLabel(f"<b>{total} violation(s) — recommandations</b>")
        title.setStyleSheet("font-size:14px;color:#FFB800;")
        lo.addWidget(title)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText("\n".join(suggestions))
        lo.addWidget(txt)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryBtn")
        bb.accepted.connect(dlg.accept)
        lo.addWidget(bb)
        dlg.exec()

    # ══════════════════════════════════════════════════════════════════════
    # POST-RUN ACTIONS
    # ══════════════════════════════════════════════════════════════════════

    def _show_post_actions(self):
        for btn in [self._btn_confirm, self._btn_map, self._btn_tracking,
                    self._btn_scen, self._btn_pdf, self._btn_csv_exp]:
            btn.setVisible(True)

    def _confirm_plan(self):
        """Confirme le meilleur résultat et le persiste comme plan officiel en base."""
        from ..services.optimization_service import save_plan as _save_plan

        if not self.results:
            show_toast(self.window(), "Lancez d'abord une optimisation.", "info")
            return

        best_algo, best_result = min(
            self.results.items(), key=lambda kv: kv[1].get("total_distance_km", 1e9)
        )
        planned_date = self._date_edit.date().toString("yyyy-MM-dd")
        n_active  = len([r for r in best_result.get("routes", []) if r.get("route")])
        n_clients = best_result.get("clients_served", 0)

        box = QMessageBox(self)
        box.setWindowTitle("Confirmer le plan")
        box.setText(
            f"Confirmer le plan du <b>{planned_date}</b> ?<br><br>"
            f"Algorithme retenu : <b>{best_algo.upper()}</b><br>"
            f"{n_active} tournée(s) · {n_clients} client(s) servi(s)<br><br>"
            "Les routes seront sauvegardées, les commandes passées en <b>assigned</b> "
            "et les calendriers chauffeurs/véhicules bloqués pour ce jour."
        )
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.button(QMessageBox.StandardButton.Yes).setText("✅ Confirmer")
        box.button(QMessageBox.StandardButton.Cancel).setText("Annuler")
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            saved = _save_plan(best_result, planned_date)
            self._btn_confirm.setText("✅ Plan confirmé")
            self._btn_confirm.setEnabled(False)
            show_toast(
                self.window(),
                f"Plan {planned_date} confirmé — {saved['routes']} tournée(s), "
                f"{saved['stops']} arrêt(s), {saved['orders_updated']} commande(s).",
                "success",
            )
        except Exception as exc:
            logger.exception("_confirm_plan error")
            show_toast(self.window(), f"Erreur confirmation : {exc}", "error")

    def _save_as_scenario(self):
        if not self.results:
            show_toast(self.window(), "Aucun résultat à sauvegarder.", "info"); return
        best_algo, best_result = min(
            self.results.items(), key=lambda kv: kv[1].get("total_distance_km", 1e9)
        )
        try:
            # config_json = paramètres utilisés pour ce run
            config_data = {
                "algorithms": list(self.results.keys()),
                "best_algo": best_algo,
                "date": datetime.now().isoformat(),
                "vrp_mode": self._current_params.get("vrp_mode", "standard") if hasattr(self, "_current_params") else "standard",
            }
            # results_json = résumé comparatif + routes du meilleur algo
            results_data = {}
            for k, v in self.results.items():
                results_data[k] = {
                    "total_distance_km": v.get("total_distance_km"),
                    "total_cost": v.get("total_cost"),
                    "respect_rate": v.get("respect_rate"),
                    "total_co2_kg": v.get("total_co2_kg"),
                    "clients_served": v.get("clients_served"),
                    "clients_total": v.get("clients_total"),
                    "cpu_time_ms": v.get("cpu_time_ms"),
                }
            # data_json = routes détaillées du meilleur algo (pour carte / suivi)
            routes_summary = []
            for route in best_result.get("routes", []):
                veh = route.get("vehicle", {})
                stops = [
                    {"client_id": (s.get("client") or {}).get("id"),
                     "client_name": (s.get("client") or {}).get("name", ""),
                     "arrival_time": s.get("arrival_time")}
                    for s in route.get("route", [])
                ]
                routes_summary.append({
                    "vehicle_id": veh.get("id"),
                    "registration": veh.get("registration"),
                    "distance_km": route.get("distance_km"),
                    "stops": stops,
                })
            data_json = {"routes": routes_summary, "algo": best_algo}

            n_clients  = best_result.get("clients_total") or 0
            n_vehicles = len([r for r in best_result.get("routes", []) if r.get("vehicle")])

            conn = get_connection()
            conn.execute("""
                INSERT INTO scenarios
                  (name, client_count, vehicle_count, algorithm,
                   data_json, config_json, results_json)
                VALUES (?,?,?,?,?,?,?)
            """, (
                f"Scénario {datetime.now().strftime('%d/%m %H:%M')} ({best_algo})",
                n_clients,
                n_vehicles,
                best_algo,
                json.dumps(data_json, ensure_ascii=False),
                json.dumps(config_data, ensure_ascii=False),
                json.dumps(results_data, ensure_ascii=False),
            ))
            conn.commit(); conn.close()
            log_action("SCENARIO_CREATE", f"Scénario créé depuis optimisation ({best_algo})")
            show_toast(self.window(), "Scénario sauvegardé.", "success")
        except Exception as e:
            show_toast(self.window(), f"Erreur sauvegarde: {e}", "error")

    def _export_pdf(self):
        if not self.results or not HAS_REPORTLAB:
            show_toast(self.window(), "Installez reportlab ou lancez une optimisation.", "info"); return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter PDF", "optimisation.pdf", "PDF (*.pdf)")
        if not path: return
        try:
            doc  = SimpleDocTemplate(path, pagesize=A4)
            styl = getSampleStyleSheet()
            elts = [Paragraph("Rapport d'optimisation VRP", styl["Title"]), Spacer(1, 12)]
            headers = ["Métrique"] + [a.upper() for a in self.results]
            rows_data = [headers]
            for metric, _ in self._metrics[:10]:
                row = [metric]
                col_map = {"greedy": 0, "2opt": 1, "ortools": 2}
                for algo in self.results:
                    ci = col_map.get(algo, 0)
                    it = self._cmp_table.item(
                        [m for m, _ in self._metrics].index(metric) if metric in [m for m, _ in self._metrics] else 0,
                        ci + 1
                    )
                    row.append(it.text() if it else "—")
                rows_data.append(row)
            tbl = Table(rows_data)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), rl_colors.HexColor("#0A1628")),
                ("TEXTCOLOR",  (0,0), (-1,0), rl_colors.white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 9),
                ("ALIGN",      (0,0), (-1,-1), "CENTER"),
                ("GRID",       (0,0), (-1,-1), 0.5, rl_colors.grey),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [rl_colors.whitesmoke, rl_colors.white]),
            ]))
            elts.append(tbl)
            doc.build(elts)
            show_toast(self.window(), f"PDF exporté : {path.split('/')[-1]}", "success")
        except Exception as e:
            show_toast(self.window(), f"Erreur PDF: {e}", "error")

    def _export_csv(self):
        if not self.results:
            show_toast(self.window(), "Aucun résultat.", "info"); return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter CSV", "optimisation.csv", "CSV (*.csv)")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Métrique"] + [a.upper() for a in self.results])
                for row_i, (metric, _) in enumerate(self._metrics):
                    row = [metric]
                    for col_i, algo in enumerate(self.results):
                        it = self._cmp_table.item(row_i, col_i + 1)
                        row.append(it.text() if it else "—")
                    writer.writerow(row)
            show_toast(self.window(), f"CSV exporté : {path.split('/')[-1]}", "success")
        except Exception as e:
            show_toast(self.window(), f"Erreur CSV: {e}", "error")

    def _export_route_pdf(self):
        show_toast(self.window(), "Export PDF routes — utilisez 'Rapports' pour le rapport complet.", "info")

    def _export_route_csv(self):
        if not self.results:
            show_toast(self.window(), "Aucun résultat.", "info"); return
        algo_map = {"Greedy": "greedy", "2-opt": "2opt", "OR-Tools": "ortools"}
        algo     = algo_map.get(self._route_algo_cb.currentText(), "greedy")
        result   = self.results.get(algo)
        if not result:
            show_toast(self.window(), "Algorithme non calculé.", "info"); return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter", f"routes_{algo}.csv", "CSV (*.csv)")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Véhicule", "Arrêt", "Client", "Arrivée (min)", "Retard (min)", "Distance (km)"])
                for ri, route in enumerate(result.get("routes", [])):
                    veh = route.get("vehicle", {})
                    for si, stop in enumerate(route.get("route", [])):
                        if stop.get("type") != "delivery": continue
                        c = stop.get("client") or {}
                        writer.writerow([
                            veh.get("registration", f"V{ri+1}"),
                            si + 1,
                            c.get("name", ""),
                            f"{stop.get('arrival_time', 0):.0f}",
                            f"{stop.get('delay', 0):.0f}",
                            f"{stop.get('distance_from_prev', 0):.2f}",
                        ])
            show_toast(self.window(), "CSV routes exporté.", "success")
        except Exception as e:
            show_toast(self.window(), f"Erreur CSV: {e}", "error")

    def _load_forced_sequences(self) -> list:
        """Charge les séquences forcées depuis la table route_stops (ordres verrouillés)."""
        if not self._chk_forced_seq.isChecked():
            return []
        try:
            from ..database.db_manager import get_connection
            conn = get_connection()
            rows = conn.execute(
                """SELECT rs.route_id, rs.client_id, rs.stop_order
                   FROM route_stops rs
                   JOIN routes r ON r.id = rs.route_id
                   WHERE r.is_locked = 1
                   ORDER BY rs.route_id, rs.stop_order"""
            ).fetchall()
            conn.close()
            # Construire paires (a, b) = arrêts consécutifs dans la même tournée
            pairs = []
            prev_id = None
            prev_route = None
            for row in rows:
                cid = row["client_id"]
                rid = row["route_id"]
                if prev_id is not None and cid is not None and rid == prev_route:
                    pairs.append((prev_id, cid))
                prev_id = cid
                prev_route = rid
            return pairs
        except Exception:
            return []

    # ── Log interne ───────────────────────────────────────────────────

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_edit.append(f"[{ts}] {msg}")
        sb = self._log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Planificateur hebdomadaire (onglet 5) ──────────────────────────

    def _launch_week_analysis(self):
        """Lance le benchmark multi-algo en dry_run=True depuis l'onglet Planif."""
        try:
            conn = get_connection()
            depot_row = conn.execute("SELECT id FROM depots ORDER BY id LIMIT 1").fetchone()
            conn.close()
        except Exception:
            depot_row = None
        if not depot_row:
            show_toast(self.window(), "Aucun dépôt configuré.", "error")
            return

        algos = []
        if self._chk_greedy.isChecked():  algos.append("greedy")
        if self._chk_2opt.isChecked():    algos.append("2opt")
        if self._chk_ortools.isChecked() and ORTOOLS_AVAILABLE: algos.append("ortools")
        if not algos:
            show_toast(self.window(), "Sélectionnez au moins un algorithme.", "info")
            return

        start_date = self._wp_start.date().toPyDate()
        n_days     = self._wp_n_days.value()
        distribute = self._wp_rb_distribute.isChecked()

        # Réinitialiser l'affichage
        self._wp_table.setRowCount(0)
        self._wp_log.clear()
        self._wp_summary_lbl.setText("")
        self._wp_btn_validate.setEnabled(False)
        self._wp_btn_tracking.setEnabled(False)
        self._wp_btn_pdf.setEnabled(False)
        self._wp_btn_csv.setEnabled(False)
        self._pending_week_plan = []

        ts = datetime.now().strftime("%H:%M:%S")
        self._wp_log.append(
            f"[{ts}] Analyse du {start_date} sur {n_days} j. — "
            f"algos : {', '.join(algos)}…"
        )

        self._wp_btn_analyse.setEnabled(False)

        self._week_thread = _WeekPlanThread(
            start_date=start_date,
            n_days=n_days,
            algo="best3",
            distribute=distribute,
            dry_run=True,
            algos_list=algos,
        )
        self._week_thread.progress.connect(self._wp_on_progress)
        self._week_thread.day_done.connect(self._on_week_day_analysis)
        self._week_thread.finished.connect(self._on_week_analysis_done)
        self._week_thread.error.connect(self._wp_on_error)
        if not hasattr(self, "_week_threads"): self._week_threads = []
        self._week_threads.append(self._week_thread)
        self._week_thread.start()

    def _wp_on_progress(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._wp_log.append(f"[{ts}] {msg}")
        sb = self._wp_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _wp_on_error(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._wp_log.append(f"[{ts}] ❌ {msg}")
        show_toast(self.window(), f"Erreur planification: {msg}", "error")
        self._wp_btn_analyse.setEnabled(True)

    def _on_week_day_analysis(self, day_result: dict):
        """Remplit une ligne dans le tableau des résultats au fil de l'analyse."""
        self._pending_week_plan.append(day_result)

        row = self._wp_table.rowCount()
        self._wp_table.insertRow(row)

        day_str     = day_result.get("date", "?")
        n_orders    = day_result.get("n_orders", 0)
        n_served    = day_result.get("n_served", 0)
        best_algo   = day_result.get("best_algo", "")
        algo_summary = day_result.get("algo_results", {})

        self._wp_table.setItem(row, 0, QTableWidgetItem(day_str))
        it_n = QTableWidgetItem(str(n_orders))
        it_n.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wp_table.setItem(row, 1, it_n)

        for a_name, col in (("greedy", 2), ("2opt", 3), ("ortools", 4)):
            d = algo_summary.get(a_name)
            txt = f"{d['km']} km / {d['served']} servis" if d else "—"
            item = QTableWidgetItem(txt)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if d and a_name == best_algo:
                item.setForeground(QColor(C["success"]))
                f = item.font(); f.setBold(True); item.setFont(f)
            self._wp_table.setItem(row, col, item)

        best_item = QTableWidgetItem(best_algo.upper() if best_algo else "—")
        best_item.setForeground(QColor(C["success"]))
        best_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wp_table.setItem(row, 5, best_item)

        if n_served == n_orders and n_orders > 0:
            status_txt, status_col = "✅ Complet",            C["success"]
        elif n_served > 0:
            status_txt, status_col = f"⚠ {n_served}/{n_orders}", C["warning"]
        else:
            status_txt, status_col = "❌ Aucun",              C["danger"]
        status_item = QTableWidgetItem(status_txt)
        status_item.setForeground(QColor(status_col))
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wp_table.setItem(row, 6, status_item)

        ts = datetime.now().strftime("%H:%M:%S")
        self._wp_log.append(
            f"[{ts}]  {day_str} : {n_served}/{n_orders} — meilleur={best_algo.upper()}"
        )
        sb = self._wp_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_week_analysis_done(self, results: list):
        """Analyse terminée — active le bouton Valider."""
        self._wp_btn_analyse.setEnabled(True)

        total_served = sum(r.get("n_served", 0) for r in results)
        total_orders = sum(r.get("n_orders", 0) for r in results)
        days_done    = len(results)

        ts = datetime.now().strftime("%H:%M:%S")
        self._wp_log.append(
            f"[{ts}] ✅ Analyse terminée — {total_served}/{total_orders} commandes "
            f"planifiables sur {days_done} jour(s)."
        )

        if total_served > 0:
            self._wp_btn_validate.setEnabled(True)
            self._wp_btn_tracking.setEnabled(True)
            self._wp_btn_pdf.setEnabled(True)
            self._wp_btn_csv.setEnabled(True)
            self._wp_summary_lbl.setText(
                f"Analyse : {days_done} jour(s) · {total_served}/{total_orders} commandes planifiables. "
                "→ Cliquez 'Valider et assigner' pour confirmer."
            )
            self._wp_summary_lbl.setStyleSheet(
                f"color:{C['accent']};font-size:11px;font-weight:600;background:transparent;"
            )
        else:
            self._wp_summary_lbl.setText(
                "Aucune commande planifiable — vérifiez vos données (clients, véhicules, dépôts)."
            )
            self._wp_summary_lbl.setStyleSheet(
                f"color:{C['warning']};font-size:11px;background:transparent;"
            )

    # ── Helpers export / navigation semaine ───────────────────────────────

    def _build_week_merged_result(self) -> dict:
        """Fusionne tous les jours planifiés en un résultat unique pour le Gantt."""
        all_routes    = []
        total_km      = 0.0
        total_served  = 0
        total_dur     = 0.0
        total_cost    = 0.0

        for day_result in self._pending_week_plan:
            best_algo = day_result.get("best_algo", "")
            full      = day_result.get("algo_results_full", {})
            res       = full.get(best_algo, {})
            day_str   = day_result.get("date", "?")

            for route in res.get("routes", []):
                if not route.get("route"):
                    continue
                route_copy = dict(route)
                veh_copy   = dict(route.get("vehicle") or {})
                reg        = veh_copy.get("registration", "V")
                veh_copy["registration"] = f"{reg} [{day_str}]"
                route_copy["vehicle"]    = veh_copy
                all_routes.append(route_copy)
                total_km    += route.get("distance_km", 0)
                total_served += len(route.get("route", []))
                total_dur   += route.get("duration_min", 0)
                total_cost  += route.get("distance_km", 0) * (
                    (route.get("vehicle") or {}).get("cost_per_km", 0.5)
                )

        return {
            "algorithm":         "Planification semaine",
            "routes":            all_routes,
            "total_distance_km": total_km,
            "total_cost":        total_cost,
            "total_duration_min": total_dur,
            "clients_served":    total_served,
            "clients_total":     total_served,
            "respect_rate":      0,
            "avg_delay_min":     0,
            "cpu_time_ms":       0,
            "traffic_coeff":     1.0,
            "weather_coeff":     1.0,
            "distance_source":   "haversine",
        }

    def _wp_send_to_tracking(self):
        """Envoie la planification semaine vers le Gantt de suivi (sélecteur par jour)."""
        if not getattr(self, "_pending_week_plan", []):
            show_toast(self.window(), "Aucun résultat — lancez d'abord l'analyse.", "info")
            return
        tracking = getattr(self.main_window, "tracking_w", None)
        if tracking and hasattr(tracking, "set_week_plan"):
            tracking.set_week_plan(self._pending_week_plan)
        self.main_window._nav_to(9)

    def _wp_export_csv(self):
        """Exporte tous les arrêts de la semaine planifiée en CSV."""
        if not getattr(self, "_pending_week_plan", []):
            show_toast(self.window(), "Aucun résultat à exporter.", "info")
            return

        default_name = f"planif_semaine_{date.today().isoformat()}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la planification semaine", default_name, "CSV (*.csv)"
        )
        if not path:
            return

        rows = []
        for day_result in self._pending_week_plan:
            best_algo = day_result.get("best_algo", "")
            full      = day_result.get("algo_results_full", {})
            res       = full.get(best_algo, {})
            day_str   = day_result.get("date", "?")

            for route in res.get("routes", []):
                veh = route.get("vehicle") or {}
                for stop in route.get("route", []):
                    client = stop.get("client") or {}
                    arr    = stop.get("arrival_time", 0)
                    h, m   = divmod(int(arr), 60)
                    rows.append({
                        "Date":           day_str,
                        "Algorithme":     best_algo,
                        "Véhicule":       veh.get("registration", "?"),
                        "Client":         client.get("name", "?"),
                        "Adresse":        client.get("address", ""),
                        "Latitude":       client.get("latitude", ""),
                        "Longitude":      client.get("longitude", ""),
                        "Arrivée":        f"{h:02d}:{m:02d}",
                        "Délai (min)":    round(stop.get("delay", 0), 1),
                        "Demande (kg)":   client.get("demand_kg", 0),
                        "Distance (km)":  round(stop.get("distance_from_prev", 0), 2),
                        "Type":           stop.get("type", "delivery"),
                    })

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
                else:
                    f.write("Aucun arrêt planifié.\n")
            show_toast(self.window(), f"CSV exporté ({len(rows)} arrêts).", "success")
            log_action("EXPORT", f"Planif. semaine CSV — {len(rows)} arrêts → {path}")
        except Exception as exc:
            logger.exception("Erreur export CSV semaine")
            show_toast(self.window(), f"Erreur export : {exc}", "error")

    def _wp_export_pdf(self):
        """Génère un rapport PDF de la planification semaine."""
        if not getattr(self, "_pending_week_plan", []):
            show_toast(self.window(), "Aucun résultat à exporter.", "info")
            return
        if not REPORTLAB_OK:
            show_toast(self.window(), "reportlab non installé — pip install reportlab", "error")
            return

        default_name = f"planif_semaine_{date.today().isoformat()}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le rapport PDF semaine", default_name, "PDF (*.pdf)"
        )
        if not path:
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle,
                Paragraph, Spacer, HRFlowable,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors as rl_colors
            from reportlab.lib.units import cm

            doc    = SimpleDocTemplate(path, pagesize=A4,
                                       leftMargin=1.5*cm, rightMargin=1.5*cm,
                                       topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet()
            H1     = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=14, spaceAfter=6)
            H2     = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceAfter=4)
            NORM   = styles["Normal"]

            elems = []
            elems.append(Paragraph("Planification automatique — Semaine", H1))
            elems.append(Paragraph(
                f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
                f"{len(self._pending_week_plan)} jour(s) planifié(s)", NORM
            ))
            elems.append(Spacer(1, 0.4*cm))
            elems.append(HRFlowable(width="100%", thickness=1,
                                    color=rl_colors.HexColor("#00D4FF")))
            elems.append(Spacer(1, 0.3*cm))

            total_km  = 0.0
            total_srv = 0

            for day_result in self._pending_week_plan:
                best_algo = day_result.get("best_algo", "")
                full      = day_result.get("algo_results_full", {})
                res       = full.get(best_algo, {})
                day_str   = day_result.get("date", "?")
                n_orders  = day_result.get("n_orders", 0)
                n_served  = day_result.get("n_served", 0)
                day_km    = res.get("total_distance_km", 0)
                total_km  += day_km
                total_srv += n_served

                elems.append(Paragraph(
                    f"📅 {day_str} — {best_algo.upper()} · {n_served}/{n_orders} cde · {day_km:.1f} km",
                    H2
                ))

                # Tableau des arrêts
                tbl_data = [["Véhicule", "Client", "Arrivée", "Délai (min)", "Demande (kg)", "Distance (km)"]]
                for route in res.get("routes", []):
                    veh = route.get("vehicle") or {}
                    for stop in route.get("route", []):
                        client = stop.get("client") or {}
                        arr    = stop.get("arrival_time", 0)
                        h, m   = divmod(int(arr), 60)
                        tbl_data.append([
                            veh.get("registration", "?"),
                            client.get("name", "?")[:28],
                            f"{h:02d}:{m:02d}",
                            f"{stop.get('delay', 0):.0f}",
                            f"{client.get('demand_kg', 0):.0f}",
                            f"{stop.get('distance_from_prev', 0):.2f}",
                        ])

                if len(tbl_data) > 1:
                    tbl = Table(tbl_data, repeatRows=1,
                                colWidths=[3*cm, 5.5*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm])
                    tbl.setStyle(TableStyle([
                        ("BACKGROUND",   (0, 0), (-1, 0), rl_colors.HexColor("#162840")),
                        ("TEXTCOLOR",    (0, 0), (-1, 0), rl_colors.HexColor("#00D4FF")),
                        ("FONTSIZE",     (0, 0), (-1, -1), 8),
                        ("GRID",         (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#1E3A5F")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                         [rl_colors.HexColor("#0D1B2A"), rl_colors.HexColor("#0F2035")]),
                        ("TEXTCOLOR",    (0, 1), (-1, -1), rl_colors.HexColor("#E8F4FD")),
                        ("ALIGN",        (2, 0), (-1, -1), "CENTER"),
                    ]))
                    elems.append(tbl)
                else:
                    elems.append(Paragraph("(aucun arrêt)", NORM))

                elems.append(Spacer(1, 0.4*cm))

            # Récap global
            elems.append(HRFlowable(width="100%", thickness=1,
                                    color=rl_colors.HexColor("#00D4FF")))
            elems.append(Spacer(1, 0.2*cm))
            elems.append(Paragraph(
                f"<b>Total semaine :</b> {total_srv} arrêts · {total_km:.1f} km", NORM
            ))

            doc.build(elems)
            show_toast(self.window(), f"PDF généré ({len(self._pending_week_plan)} jours).", "success")
            log_action("EXPORT", f"Planif. semaine PDF → {path}")

        except Exception as exc:
            logger.exception("Erreur export PDF semaine")
            show_toast(self.window(), f"Erreur PDF : {exc}", "error")

    def _on_week_day_dblclick(self, row: int, col: int):
        """Double-clic sur une ligne du tableau → popup de détail du jour."""
        pending = getattr(self, "_pending_week_plan", [])
        if row >= len(pending):
            return
        day_result = pending[row]
        if not day_result.get("algo_results_full"):
            show_toast(self.window(), "Détail non disponible — relancez l'analyse.", "info")
            return
        dlg = _DayDetailDialog(day_result, self)
        dlg.exec()

    def _validate_week_plan(self):
        """Commit la planification semaine : routes+stops en base, orders assignées, calendriers bloqués."""
        from ..services.optimization_service import save_plan as _save_plan

        if not getattr(self, "_pending_week_plan", []):
            show_toast(self.window(), "Rien à valider — lancez d'abord une analyse.", "info")
            return

        total_served = sum(r.get("n_served", 0) for r in self._pending_week_plan)
        days = len(self._pending_week_plan)

        box = QMessageBox(self)
        box.setWindowTitle("Valider la planification semaine")
        box.setText(
            f"Confirmer la planification de <b>{total_served}</b> commande(s) "
            f"sur <b>{days}</b> jour(s) ?<br><br>"
            "Pour chaque journée : les routes seront sauvegardées, les commandes passées en "
            "<b>assigned</b> et les calendriers chauffeurs/véhicules bloqués."
        )
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.button(QMessageBox.StandardButton.Yes).setText("✅ Valider")
        box.button(QMessageBox.StandardButton.Cancel).setText("Annuler")
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        self._wp_btn_validate.setEnabled(False)
        total_routes = 0
        total_stops  = 0
        committed    = 0
        errors       = 0

        for day_result in self._pending_week_plan:
            day_str   = day_result.get("date", "")
            best_algo = day_result.get("best_algo", "")
            full      = day_result.get("algo_results_full", {})
            best_res  = full.get(best_algo) if best_algo else None

            if not day_str:
                continue

            # ── Sauvegarder routes + route_stops + mise à jour orders ──────
            if best_res:
                try:
                    saved = _save_plan(best_res, day_str)
                    total_routes += saved["routes"]
                    total_stops  += saved["stops"]
                    committed    += saved["orders_updated"]
                except Exception as exc:
                    errors += 1
                    ts = datetime.now().strftime("%H:%M:%S")
                    self._wp_log.append(f"[{ts}] ⚠ Erreur routes {day_str}: {exc}")
            else:
                # Fallback : mettre à jour uniquement le statut des commandes
                served_ids = day_result.get("served_ids", [])
                if served_ids:
                    try:
                        conn = get_connection()
                        ph = ",".join("?" * len(served_ids))
                        conn.execute(
                            f"UPDATE orders SET status='assigned', scheduled_date=? "
                            f"WHERE id IN ({ph}) AND (scheduled_date IS NULL OR scheduled_date='')",
                            [day_str] + served_ids,
                        )
                        conn.execute(
                            f"UPDATE orders SET status='assigned' "
                            f"WHERE id IN ({ph}) AND scheduled_date IS NOT NULL",
                            served_ids,
                        )
                        conn.commit()
                        conn.close()
                        committed += len(served_ids)
                        log_action("WEEK_PLAN_FALLBACK", f"{day_str}: {len(served_ids)} commandes assignées")
                    except Exception as exc:
                        errors += 1
                        ts = datetime.now().strftime("%H:%M:%S")
                        self._wp_log.append(f"[{ts}] ⚠ Erreur orders {day_str}: {exc}")

        # ── Mettre à jour la colonne Statut du tableau ─────────────────────
        for r_idx in range(self._wp_table.rowCount()):
            old_it = self._wp_table.item(r_idx, 6)
            if old_it and "❌" not in old_it.text():
                new_it = QTableWidgetItem("✅ Confirmée")
                new_it.setForeground(QColor(C["success"]))
                new_it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._wp_table.setItem(r_idx, 6, new_it)

        ts = datetime.now().strftime("%H:%M:%S")
        self._wp_log.append(
            f"[{ts}] ✅ {total_routes} tournée(s) · {total_stops} arrêts · "
            f"{committed} commande(s) confirmées en base."
        )

        msg = f"{total_routes} tournée(s), {committed} commande(s) confirmées."
        if errors:
            msg += f" {errors} erreur(s) — vérifiez le journal."
        show_toast(self.window(), msg, "success" if not errors else "warning")

        summary_style = (
            f"color:{C['success']};font-size:11px;font-weight:600;background:transparent;"
            if not errors else
            f"color:{C['warning']};font-size:11px;background:transparent;"
        )
        self._wp_summary_lbl.setText(
            f"✅ Planification confirmée : {total_routes} tournée(s) · "
            f"{total_stops} arrêts · {committed} commande(s) sur {days} jour(s)."
            + (f" ({errors} erreur(s))" if errors else "")
        )
        self._wp_summary_lbl.setStyleSheet(summary_style)
        self._refresh_data_counts()
