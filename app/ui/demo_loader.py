"""
demo_loader.py — Chargement de données de démo CityPulse Logistics
===================================================================
DemoLoaderDialog : QDialog avec barre de progression et log en temps réel.
Accessible depuis : EmptyState dashboard, menu Fichier, page Paramètres.
Fonctions legacy conservées pour compatibilité (load_demo_scenario, load_stress_test).
"""

import os
import sys
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QComboBox, QFrame, QCheckBox,
    QFileDialog, QMessageBox, QButtonGroup, QRadioButton, QGroupBox,
    QSizePolicy, QInputDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..database.db_manager import get_connection, log_action
from .toast import show_toast
from .components.confirm_dialog import _dialog_qss

logger = logging.getLogger(__name__)

C = {
    "bg":      "#0D1B2A",
    "panel":   "#112240",
    "input":   "#1A2E4A",
    "accent":  "#00D4FF",
    "success": "#00FF88",
    "warning": "#FFB800",
    "danger":  "#FF4757",
    "text":    "#E8F4FD",
    "text2":   "#8899AA",
    "border":  "#1E3A5F",
    "hover":   "#1A3A5C",
}

_DATASETS = {
    "casablanca": {
        "label":    "Casablanca (complet)",
        "desc":     "3 dépôts · 8 véhicules · 8 chauffeurs · 80 clients · 200 commandes\n"
                    "Routes historiques 30j · Zones GeoJSON · Notifications · Logs",
        "color":    C["accent"],
        "est_sec":  15,
    },
    "paris": {
        "label":    "Paris (secondaire)",
        "desc":     "2 dépôts · 5 véhicules · 50 clients · 80 commandes",
        "color":    "#8B5CF6",
        "est_sec":  8,
    },
    "benchmark": {
        "label":    "Benchmark (500 clients)",
        "desc":     "1 dépôt · 20 véhicules · 500 clients · Sans contraintes créneaux",
        "color":    C["warning"],
        "est_sec":  10,
    },
    "all": {
        "label":    "Tous les datasets",
        "desc":     "Casablanca + Paris + Benchmark en une seule passe",
        "color":    C["success"],
        "est_sec":  35,
    },
}


# ─── Thread de génération ────────────────────────────────────────────────────
class _GeneratorThread(QThread):
    progress_signal = pyqtSignal(str, int, int)   # message, step, total
    finished_signal = pyqtSignal(bool, str)        # success, summary

    def __init__(self, dataset: str, db_path: str, reset: bool,
                 export_dir: str = "", parent=None):
        super().__init__(parent)
        self.dataset    = dataset
        self.db_path    = db_path
        self.reset      = reset
        self.export_dir = export_dir

    def run(self):
        try:
            # Ajouter le répertoire racine au path
            script_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "scripts"
            )
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)

            from scripts.generate_demo_data import (
                _apply_migrations, _open_db, _reset_tables,
                generate_casablanca, generate_paris, generate_benchmark, export_to_csv
            )

            self.progress_signal.emit("Application des migrations…", 0, 100)
            _apply_migrations(self.db_path)

            conn = _open_db(self.db_path)

            if self.reset:
                self.progress_signal.emit("Réinitialisation des tables…", 2, 100)
                _reset_tables(conn, keep_users=False)

            def _cb(msg, step, total):
                pct = int(step / max(total, 1) * 85) + 10
                self.progress_signal.emit(msg, pct, 100)

            datasets = (
                ["casablanca","paris","benchmark"]
                if self.dataset == "all"
                else [self.dataset]
            )
            for ds in datasets:
                self.progress_signal.emit(f"Génération {ds}…", 15, 100)
                if ds == "casablanca":
                    generate_casablanca(conn, cb=_cb)
                elif ds == "paris":
                    generate_paris(conn, cb=_cb)
                elif ds == "benchmark":
                    generate_benchmark(conn, cb=_cb)

            if self.export_dir:
                self.progress_signal.emit("Export CSV/Excel…", 90, 100)
                export_to_csv(conn, self.export_dir)

            # Résumé
            lines = []
            for t in ("clients","vehicles","drivers","orders","routes","algo_results","logs"):
                try:
                    n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    lines.append(f"  {t:<20} {n:>5} lignes")
                except Exception:
                    pass
            conn.close()

            self.progress_signal.emit("Terminé", 100, 100)
            self.finished_signal.emit(True, "\n".join(lines))

        except Exception as e:
            logger.exception("Erreur DemoLoaderDialog")
            self.progress_signal.emit(f"Erreur : {e}", 0, 100)
            self.finished_signal.emit(False, str(e))


# ─── DemoLoaderDialog ────────────────────────────────────────────────────────
class DemoLoaderDialog(QDialog):
    """
    Dialogue de chargement de données de démo avec barre de progression.
    Usage :
        dlg = DemoLoaderDialog(main_window)
        dlg.exec()
    """

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self._thread: _GeneratorThread | None = None

        self.setWindowTitle("Charger données de démo")
        self.setMinimumWidth(560)
        self.setMinimumHeight(480)
        self.setModal(True)
        self.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
            f"QLabel{{background:transparent;border:none;color:{C['text']};}}"
            f"QGroupBox{{background:{C['panel']};border:1px solid {C['border']};"
            "border-radius:8px;margin-top:10px;padding:12px;padding-top:24px;}"
            f"QGroupBox::title{{color:{C['text2']};font-size:11px;font-weight:700;"
            f"background:{C['panel']};padding:2px 6px;left:10px;"
            "subcontrol-origin:margin;subcontrol-position:top left;}}"
            f"QRadioButton{{color:{C['text']};background:transparent;spacing:8px;}}"
            f"QCheckBox{{color:{C['text']};background:transparent;spacing:8px;}}"
            f"QTextEdit{{background:{C['input']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:6px;font-size:11px;}}"
        )

        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # Titre
        title = QLabel("Données de démonstration CityPulse Logistics")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;")
        root.addWidget(title)

        sub = QLabel(
            "Sélectionnez un dataset pour peupler votre base de données "
            "avec des données réalistes."
        )
        sub.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── Sélection dataset ──────────────────────────────────────────────
        ds_group = QGroupBox("Dataset")
        ds_lo    = QVBoxLayout(ds_group)
        ds_lo.setSpacing(8)
        self._ds_btns: dict[str, QRadioButton] = {}
        self._ds_group = QButtonGroup(self)

        for key, info in _DATASETS.items():
            row = QHBoxLayout()
            rb  = QRadioButton(info["label"])
            rb.setStyleSheet(
                f"QRadioButton::indicator{{width:16px;height:16px;"
                f"border:2px solid {C['border']};border-radius:8px;background:{C['input']};}}"
                f"QRadioButton::indicator:checked{{background:{info['color']};"
                f"border-color:{info['color']};}}"
            )
            self._ds_group.addButton(rb)
            self._ds_btns[key] = rb
            row.addWidget(rb)

            desc = QLabel(info["desc"])
            desc.setStyleSheet(f"color:{C['text2']};font-size:10px;")
            desc.setWordWrap(True)
            row.addWidget(desc, 1)

            est = QLabel(f"~{info['est_sec']}s")
            est.setStyleSheet(f"color:{C['muted']};font-size:10px;" if hasattr(C,'muted') else f"color:{C['text2']};font-size:10px;")
            est.setFixedWidth(40)
            row.addWidget(est)

            ds_lo.addLayout(row)
            rb.clicked.connect(lambda _, k=key: self._on_dataset_selected(k))

        self._ds_btns["casablanca"].setChecked(True)
        self._selected_dataset = "casablanca"
        root.addWidget(ds_group)

        # ── Options ────────────────────────────────────────────────────────
        opt_group = QGroupBox("Options")
        opt_lo    = QVBoxLayout(opt_group)

        self._reset_cb = QCheckBox("Réinitialiser la base avant insertion (supprime données existantes)")
        self._reset_cb.setChecked(True)
        opt_lo.addWidget(self._reset_cb)

        export_row = QHBoxLayout()
        self._export_cb = QCheckBox("Exporter en CSV/Excel après génération")
        self._export_cb.setChecked(False)
        export_row.addWidget(self._export_cb)

        self._export_btn = QPushButton("Choisir…")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setEnabled(False)
        self._export_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:5px;font-size:11px;padding:0 10px;}}"
            f"QPushButton:hover{{background:{C['hover']};}}"
        )
        self._export_dir = ""
        self._export_btn.clicked.connect(self._pick_export_dir)
        export_row.addWidget(self._export_btn)
        opt_lo.addLayout(export_row)
        self._export_cb.toggled.connect(self._export_btn.setEnabled)

        root.addWidget(opt_group)

        # ── Log ────────────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setPlaceholderText("Les étapes de génération s'afficheront ici…")
        root.addWidget(self._log)

        # ── Progress ───────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(10)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C['input']};border:none;border-radius:5px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {C['accent']},stop:1 {C['success']});border-radius:5px;}}"
        )
        root.addWidget(self._progress)

        self._status_lbl = QLabel("Prêt")
        self._status_lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;")
        root.addWidget(self._status_lbl)

        # ── Boutons ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._cancel_btn = QPushButton("Annuler")
        self._cancel_btn.setObjectName("secondaryBtn")
        self._cancel_btn.setFixedHeight(36)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()

        self._start_btn = QPushButton("Générer les données")
        self._start_btn.setObjectName("primaryBtn")
        self._start_btn.setFixedHeight(36)
        self._start_btn.setMinimumWidth(180)
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)

        root.addLayout(btn_row)

    def _on_dataset_selected(self, key: str):
        self._selected_dataset = key

    def _pick_export_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Dossier d'export", "")
        if path:
            self._export_dir = path
            self._export_btn.setText(os.path.basename(path))

    def _on_start(self):
        db_path = self._get_db_path()
        if not db_path:
            return

        self._start_btn.setEnabled(False)
        self._log.clear()
        self._progress.setValue(0)
        self._status_lbl.setText("Génération en cours…")

        export_dir = self._export_dir if self._export_cb.isChecked() else ""

        self._thread = _GeneratorThread(
            dataset   = self._selected_dataset,
            db_path   = db_path,
            reset     = self._reset_cb.isChecked(),
            export_dir= export_dir,
            parent    = self,
        )
        self._thread.progress_signal.connect(self._on_progress)
        self._thread.finished_signal.connect(self._on_done)
        self._thread.start()

    def _get_db_path(self) -> str:
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        db   = os.path.join(root, "citypulse.db")
        if self.main_window and hasattr(self.main_window, "db_path"):
            db = self.main_window.db_path
        return db

    def _on_progress(self, msg: str, step: int, total: int):
        self._progress.setValue(step)
        self._status_lbl.setText(msg)
        self._log.append(f"  > {msg}")
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _on_done(self, success: bool, summary: str):
        self._start_btn.setEnabled(True)
        if success:
            self._progress.setValue(100)
            self._status_lbl.setText("Génération terminée avec succès !")
            self._log.append("\nRésumé :\n" + summary)
            log_action("DEMO_LOAD", f"Dataset {self._selected_dataset} généré")
            if self.main_window:
                self._refresh_main()
            QMessageBox.information(
                self, "Données générées",
                f"Le dataset «{_DATASETS[self._selected_dataset]['label']}» "
                f"a été généré avec succès.\n\n{summary}"
            )
        else:
            self._status_lbl.setText(f"Erreur : {summary[:80]}")
            self._log.append(f"\nErreur : {summary}")
            if self.main_window:
                show_toast(self.main_window, f"Erreur génération : {summary[:60]}", "error")

    def _on_cancel(self):
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._status_lbl.setText("Annulé.")
        self.reject()

    def _refresh_main(self):
        mw = self.main_window
        for attr in ("dashboard_w","clients_w","vehicles_w","depots_w"):
            w = getattr(mw, attr, None)
            if w and hasattr(w, "refresh_data"):
                try:
                    w.refresh_data()
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY — conservé pour compatibilité avec les anciens appels
# ═══════════════════════════════════════════════════════════════════════════════

def show_demo_loader(main_window):
    """Ouvre DemoLoaderDialog (point d'entrée unique recommandé)."""
    dlg = DemoLoaderDialog(main_window, parent=main_window)
    dlg.exec()


def load_demo_scenario(main_window, scenario="10"):
    """Legacy : chargement rapide Solomon."""
    import csv as _csv

    SOLOMON_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "archive", "solomon_dataset"
    )
    scenarios = {
        "10":  (os.path.join(SOLOMON_DIR, "C1", "C101.csv"), 11),
        "50":  (os.path.join(SOLOMON_DIR, "R1", "R101.csv"), 51),
        "100": (os.path.join(SOLOMON_DIR, "RC1","RC101.csv"),None),
    }
    choices = ["10 clients (C101)","50 clients (R101)","100 clients (RC101)"]
    choice, ok = QInputDialog.getItem(
        main_window, "Charger données démo",
        "Choisissez un scénario :", choices, 0, False
    )
    if not ok:
        return

    key = "10" if "10" in choice else "50" if "50" in choice else "100"
    filepath, max_rows = scenarios[key]

    if not os.path.exists(filepath):
        QMessageBox.warning(main_window,"Fichier manquant",
                            f"Fichier non trouvé :\n{filepath}\n\n"
                            "Utilisez plutôt le générateur de démo intégré.")
        show_demo_loader(main_window)
        return

    clients, depot = [], None
    with open(filepath) as f:
        reader = _csv.reader(f)
        next(reader)
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows: break
            if len(row) < 7: continue
            no, x, y = int(row[0]), float(row[1]), float(row[2])
            lat = 33.5731 + (y - 50) * 0.01
            lon = -7.5898 + (x - 50) * 0.01
            entry = {"cust_no": no, "name": f"Client {no}",
                     "latitude": lat, "longitude": lon,
                     "demand_kg": float(row[3]), "ready_time": int(row[4]),
                     "due_time": int(row[5]), "service_time": int(row[6])}
            if no == 1 and float(row[3]) == 0:
                depot = entry
            else:
                clients.append(entry)

    conn = get_connection()
    conn.execute("DELETE FROM clients")
    for c in clients:
        conn.execute(
            "INSERT INTO clients (cust_no,name,latitude,longitude,demand_kg,"
            "ready_time,due_time,service_time,client_type) VALUES (?,?,?,?,?,?,?,?,'demo')",
            (c["cust_no"],c["name"],c["latitude"],c["longitude"],
             c["demand_kg"],c["ready_time"],c["due_time"],c["service_time"])
        )
    if depot:
        conn.execute("UPDATE depots SET latitude= ?,longitude= ? WHERE id=1",
                     (depot["latitude"],depot["longitude"]))
    v = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    for i in range(max(0, 3 - v)):
        conn.execute(
            "INSERT INTO vehicles (registration,type,capacity_kg,capacity_m3,"
            "max_speed_kmh,cost_per_km,depot_id,status)"
            " VALUES (?,?,?,?,?,?,1,'disponible')",
            (f"DEMO-{v+i+1:03d}","fourgon",200,15,60,0.5))
    conn.commit()
    conn.close()
    log_action("DEMO_LOAD", f"Solomon {key} clients chargé")
    QMessageBox.information(
        main_window, "Données démo chargées",
        f"{len(clients)} clients chargés depuis Solomon {key}."
    )
    for attr in ("clients_w","dashboard_w"):
        w = getattr(main_window, attr, None)
        if w and hasattr(w, "refresh_data"):
            w.refresh_data()


def load_stress_test(main_window):
    """Legacy : chargement stress test avec données corrompues."""
    import random as _random

    _rng = _random.Random(42)
    base_lat, base_lon = 33.5731, -7.5898

    anomaly_types = (
        ["ok"]*5 + ["coords_zero"]*2 + ["tw_inverted"]*2 +
        ["neg_demand"] + ["overflow"] + ["duplicate"]*2 + ["ok"]
    )
    raw = []
    for i, atype in enumerate(anomaly_types):
        lat = base_lat + _rng.uniform(-0.08, 0.08)
        lon = base_lon + _rng.uniform(-0.08, 0.08)
        if atype == "coords_zero":
            lat, lon = 0.0, 0.0
        ready = _rng.randint(0, 400)
        due   = ready + _rng.randint(60, 300)
        raw.append({
            "cust_no": i+1,
            "name":    f"ALERTE {atype.upper()}_{i}" if atype != "ok" else f"Client Test {i+1}",
            "latitude": lat, "longitude": lon,
            "demand_kg": -50 if atype=="neg_demand" else 9999 if atype=="overflow" else _rng.uniform(20,150),
            "ready_time": due+60 if atype=="tw_inverted" else ready,
            "due_time":   ready-30 if atype=="tw_inverted" else due,
            "service_time": _rng.randint(5,20),
            "_atype": atype,
        })

    valid, report = [], []
    seen = {}
    for c in raw:
        rejected = False
        issues = []
        if c["latitude"] == 0 and c["longitude"] == 0:
            issues.append("Coordonnées (0,0)"); rejected = True
        if c["due_time"] < c["ready_time"]:
            issues.append("Fenêtre inversée"); rejected = True
        if c["demand_kg"] < 0:
            issues.append(f"Demande négative → 1kg"); c = {**c, "demand_kg": 1.0}
        if c["name"] in seen:
            issues.append("Doublon")
        else:
            seen[c["name"]] = True
        if issues:
            report.append({"client": c["name"], "issues": ", ".join(issues),
                           "action": "Rejeté" if rejected else "Corrigé"})
        if not rejected:
            valid.append(c)

    from PyQt6.QtWidgets import (QDialog as _QD, QVBoxLayout as _VL,
                                  QTableWidget as _TW, QTableWidgetItem as _TWI,
                                  QHeaderView as _HV)
    dlg = _QD(main_window)
    dlg.setWindowTitle("Rapport Stress Test")
    dlg.setMinimumSize(680, 380)
    lo = _VL(dlg)
    lo.addWidget(QLabel(
        f"<b>{len(raw)} clients générés</b> — "
        f"<span style='color:#00FF88'>{len(valid)} valides</span> | "
        f"<span style='color:#FF4757'>{len(raw)-len(valid)} rejetés</span>"
    ))
    tbl = _TW(len(report), 3)
    tbl.setHorizontalHeaderLabels(["Client","Anomalie","Action"])
    tbl.horizontalHeader().setSectionResizeMode(1, _HV.ResizeMode.Stretch)
    for i, r in enumerate(report):
        tbl.setItem(i,0,_TWI(r["client"]))
        tbl.setItem(i,1,_TWI(r["issues"]))
        ai = _TWI(r["action"])
        from PyQt6.QtGui import QColor as _QC
        ai.setForeground(_QC("#FF4757" if "Rejeté" in r["action"] else "#FFB800"))
        tbl.setItem(i,2,ai)
    lo.addWidget(tbl)
    btn_row = QHBoxLayout()
    imp_btn = QPushButton(f"Importer {len(valid)} clients valides")
    imp_btn.setObjectName("primaryBtn")
    can_btn = QPushButton("Annuler")
    can_btn.setObjectName("secondaryBtn")

    def _do():
        conn = get_connection()
        conn.execute("DELETE FROM clients")
        for c in valid:
            conn.execute(
                "INSERT INTO clients (cust_no,name,latitude,longitude,demand_kg,"
                "ready_time,due_time,service_time,client_type) VALUES (?,?,?,?,?,?,?,?,'stress')",
                (c["cust_no"],c["name"],c["latitude"],c["longitude"],
                 c["demand_kg"],c["ready_time"],c["due_time"],c["service_time"])
            )
        conn.commit(); conn.close()
        log_action("STRESS_TEST",f"{len(valid)} clients importés")
        for attr in ("clients_w","dashboard_w"):
            w = getattr(main_window,attr,None)
            if w and hasattr(w,"refresh_data"): w.refresh_data()
        dlg.accept()

    imp_btn.clicked.connect(_do)
    can_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(imp_btn); btn_row.addStretch(); btn_row.addWidget(can_btn)
    lo.addLayout(btn_row)
    dlg.exec()
