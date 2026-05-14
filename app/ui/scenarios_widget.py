"""
scenarios_widget.py — Gestion des Scénarios
============================================
Layout v2 : panneau détail à droite du tableau, profil trafic en bas.
"""

import csv
import os
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog, QTextEdit,
    QFrame, QScrollArea, QSizePolicy, QComboBox, QDialog, QFileDialog,
    QDoubleSpinBox, QDialogButtonBox, QLineEdit, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help
from .lucide_icons import apply_action_button
from .components.confirm_dialog import _dialog_qss

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

C = {
    "bg": "#0D1B2A", "bg2": "#162840", "bg3": "#1E3A50", "card": "#243F58",
    "hover": "#2A4A66", "accent": "#00C2B2", "orange": "#FF6B35",
    "text": "#E8F4F8", "text2": "#7FA8C0", "muted": "#4A7A9B",
    "success": "#00D97E", "danger": "#FF4757", "warning": "#FFB732",
    "info": "#3B9EE8", "border": "#1E3A50", "border2": "#243F58",
}


def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background:{C['border2']};max-height:1px;border:none;")
    return f


def _section_label(text):
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{C['muted']};font-size:10px;font-weight:600;"
        "background:transparent;padding:4px 0 2px 0;"
    )
    return lbl


def _info_row(label_text, value_text="—"):
    row = QHBoxLayout()
    lbl = QLabel(label_text + " :")
    lbl.setStyleSheet(f"color:{C['muted']};font-size:11px;background:transparent;")
    val = QLabel(value_text)
    val.setStyleSheet(f"color:{C['text']};font-size:11px;font-weight:600;background:transparent;")
    row.addWidget(lbl)
    row.addStretch()
    row.addWidget(val)
    return row, val


class ScenariosWidget(QWidget):
    """compare_map_requested : {left: payload, right: payload} pour MapWidget."""

    compare_map_requested = pyqtSignal(dict)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._traffic_profile = {}
        self._traffic_profile_path = ""
        self._scenario_rows: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background:{C['bg']};border:none;")

        container = QWidget()
        container.setStyleSheet(f"background:{C['bg']};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 8, 4, 16)
        layout.setSpacing(18)

        # ── Header ────────────────────────────────────────────────────
        header = QHBoxLayout()
        self._page_title = QLabel("Gestion des Scénarios")
        self._page_title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self._page_title.setStyleSheet(f"color:{C['text']};background:transparent;")
        header.addWidget(self._page_title)
        header.addStretch()

        self._save_btn = QPushButton("Sauvegarder scénario actuel")
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.setMinimumHeight(34)
        self._save_btn.clicked.connect(self._save_current)
        header.addWidget(self._save_btn)

        help_btn = QPushButton()
        help_btn.setFixedSize(34, 34)
        help_btn.setToolTip("Guide d'utilisation")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(help_btn, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        help_btn.clicked.connect(lambda: show_help(self, "scenarios"))
        header.addWidget(help_btn)
        layout.addLayout(header)

        self._page_subtitle = QLabel(
            "Sauvegardez, restaurez et comparez vos scénarios d'optimisation"
        )
        self._page_subtitle.setStyleSheet(
            f"color:{C['text2']};font-size:12px;background:transparent;"
        )
        layout.addWidget(self._page_subtitle)
        layout.addWidget(_sep())

        # ── Section : Scénarios sauvegardés ──────────────────────────
        self._sec_saved_lbl = _section_label("Scénarios sauvegardés")
        layout.addWidget(self._sec_saved_lbl)

        # Splitter: table (gauche) + panneau détail (droite)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStyleSheet(
            f"QSplitter::handle{{background:{C['border2']};width:3px;}}"
        )

        # ── Côté gauche : table + toolbar ────────────────────────────
        left_w = QWidget()
        left_w.setStyleSheet(f"background:{C['bg']};")
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 6, 0)
        left_lay.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nom", "Clients", "Véhicules", "Algorithme", "Date", "Tags", "Actions",
        ])
        _tips = [
            "Identifiant unique", "Nom du scénario", "Nombre de clients",
            "Nombre de véhicules", "Algorithme utilisé", "Date de création", "Tags", "Actions",
        ]
        for i, tip in enumerate(_tips):
            if self.table.horizontalHeaderItem(i):
                self.table.horizontalHeaderItem(i).setToolTip(tip)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultSectionSize(90)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(200)
        self.table.itemSelectionChanged.connect(self._on_table_sel)
        left_lay.addWidget(self.table)

        _btn_style_info = (
            f"background:{C['info']};color:#fff;border:none;border-radius:6px;"
            "padding:6px 12px;font-size:11px;font-weight:600;"
        )
        tool_row = QHBoxLayout()
        for attr, txt, slot in [
            ("_btn_import_json", "Importer JSON",   self._import_json),
            ("_btn_export_json", "Exporter JSON",   self._export_json),
            ("_btn_duplicate",   "Dupliquer",        self._duplicate_selected),
        ]:
            b = QPushButton(txt)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_btn_style_info)
            b.clicked.connect(slot)
            tool_row.addWidget(b)
            setattr(self, attr, b)
        tool_row.addStretch()
        left_lay.addLayout(tool_row)
        main_splitter.addWidget(left_w)

        # ── Côté droit : panneau détail ───────────────────────────────
        right_w = QFrame()
        right_w.setMinimumWidth(220)
        right_w.setStyleSheet(
            f"QFrame{{background:{C['card']};border:1px solid {C['border2']};"
            f"border-radius:10px;}}"
        )
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(14, 12, 14, 14)
        right_lay.setSpacing(8)

        detail_title = QLabel("Scénario sélectionné")
        detail_title.setStyleSheet(
            f"color:{C['text']};font-size:12px;font-weight:700;"
            "background:transparent;border:none;"
        )
        right_lay.addWidget(detail_title)
        right_lay.addWidget(_sep())

        # Info rows
        row_n, self._det_name     = _info_row("Nom")
        row_c, self._det_clients  = _info_row("Clients")
        row_v, self._det_vehicles = _info_row("Véhicules")
        row_a, self._det_algo     = _info_row("Algorithme")
        row_d, self._det_date     = _info_row("Date")
        for r in (row_n, row_c, row_v, row_a, row_d):
            right_lay.addLayout(r)

        right_lay.addWidget(_sep())

        # Tags
        tag_lbl = QLabel("Tags")
        tag_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;font-weight:600;background:transparent;border:none;"
        )
        right_lay.addWidget(tag_lbl)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Séparés par des virgules")
        self.tags_edit.setStyleSheet(
            f"background:{C['bg3']};color:{C['text']};border:1px solid {C['border2']};"
            "border-radius:4px;padding:4px;"
        )
        right_lay.addWidget(self.tags_edit)
        tag_save = QPushButton("Sauver les tags")
        tag_save.setObjectName("secondaryBtn")
        tag_save.clicked.connect(self._save_tags)
        right_lay.addWidget(tag_save)

        right_lay.addWidget(_sep())

        # Description
        desc_lbl = QLabel("Description")
        desc_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;font-weight:600;background:transparent;border:none;"
        )
        right_lay.addWidget(desc_lbl)
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(False)
        self.desc_text.setMinimumHeight(80)
        self.desc_text.setMaximumHeight(140)
        self.desc_text.setPlaceholderText("Description du scénario…")
        self.desc_text.setStyleSheet(
            f"background:{C['bg3']};color:{C['text']};border:1px solid {C['border2']};"
            "border-radius:6px;"
        )
        right_lay.addWidget(self.desc_text)
        desc_save = QPushButton("Sauvegarder description")
        desc_save.setObjectName("secondaryBtn")
        desc_save.clicked.connect(self._save_description)
        right_lay.addWidget(desc_save)

        right_lay.addStretch()
        main_splitter.addWidget(right_w)

        main_splitter.setSizes([640, 260])
        layout.addWidget(main_splitter)
        layout.addWidget(_sep())

        # ── Section : Comparer deux scénarios ────────────────────────
        self._sec_compare_lbl = _section_label("Comparer deux scénarios")
        layout.addWidget(self._sec_compare_lbl)

        cmp_fr = QFrame()
        cmp_fr.setStyleSheet(
            f"QFrame{{background:{C['card']};border:1px solid {C['border2']};border-radius:8px;}}"
        )
        cm = QVBoxLayout(cmp_fr)
        cm.setContentsMargins(12, 10, 12, 12)
        cm.setSpacing(8)

        h1 = QHBoxLayout()
        self._cmp_a = QComboBox()
        self._cmp_b = QComboBox()
        lbl_a = QLabel("A :")
        lbl_a.setStyleSheet(f"color:{C['text2']};background:transparent;")
        lbl_b = QLabel("B :")
        lbl_b.setStyleSheet(f"color:{C['text2']};background:transparent;")
        h1.addWidget(lbl_a)
        h1.addWidget(self._cmp_a, 1)
        h1.addWidget(lbl_b)
        h1.addWidget(self._cmp_b, 1)
        cm.addLayout(h1)

        h2 = QHBoxLayout()
        self._btn_compare = QPushButton("Comparer (tableau + graphique)")
        self._btn_compare.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_compare.setStyleSheet(
            f"background:{C['accent']};color:#0D1B2A;border:none;border-radius:6px;"
            "padding:8px 14px;font-weight:700;"
        )
        self._btn_compare.clicked.connect(self._compare_scenarios)
        h2.addWidget(self._btn_compare)
        h2.addStretch()
        cm.addLayout(h2)
        layout.addWidget(cmp_fr)
        layout.addWidget(_sep())

        # ── Section : Profil de trafic (avancé, en bas) ───────────────
        self._sec_traffic_lbl = _section_label(
            "Profil de trafic horaire CSV (avancé)"
        )
        layout.addWidget(self._sec_traffic_lbl)

        traffic_frame = QFrame()
        traffic_frame.setStyleSheet(
            f"QFrame{{background:{C['card']};border:1px solid {C['border2']};"
            f"border-radius:10px;}}"
        )
        tf = QVBoxLayout(traffic_frame)
        tf.setContentsMargins(16, 12, 16, 14)
        tf.setSpacing(8)

        tf_desc = QLabel(
            "Importez un CSV avec colonnes <b>heure</b> (0–23) et <b>coefficient</b>. "
            "Le coefficient sera appliqué selon l'heure de départ lors de la prochaine optimisation."
        )
        tf_desc.setWordWrap(True)
        tf_desc.setStyleSheet(
            f"color:{C['text2']};font-size:11px;border:none;background:transparent;"
        )
        tf.addWidget(tf_desc)

        tf_bar = QHBoxLayout()
        self.traffic_file_lbl = QLabel("Aucun profil chargé")
        self.traffic_file_lbl.setStyleSheet(
            f"color:{C['muted']};font-size:11px;border:none;background:transparent;"
        )
        tf_bar.addWidget(self.traffic_file_lbl)
        tf_bar.addStretch()

        self._btn_import_csv = QPushButton("Importer CSV")
        self._btn_import_csv.setStyleSheet(
            f"background:{C['info']};color:#fff;border:none;border-radius:6px;"
            "padding:6px 14px;font-size:11px;font-weight:600;"
        )
        self._btn_import_csv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_import_csv.clicked.connect(self._import_traffic_csv)
        tf_bar.addWidget(self._btn_import_csv)

        self._btn_clear_traffic = QPushButton("Effacer")
        self._btn_clear_traffic.setStyleSheet(
            f"background:{C['bg3']};color:{C['text2']};border:1px solid {C['border2']};"
            "border-radius:6px;padding:6px 12px;font-size:11px;"
        )
        self._btn_clear_traffic.clicked.connect(self._clear_traffic_profile)
        tf_bar.addWidget(self._btn_clear_traffic)
        tf.addLayout(tf_bar)

        self.traffic_preview_lbl = QLabel("")
        self.traffic_preview_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:10px;border:none;background:transparent;"
            "font-family:Consolas,monospace;"
        )
        self.traffic_preview_lbl.setWordWrap(True)
        tf.addWidget(self.traffic_preview_lbl)
        layout.addWidget(traffic_frame)

        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── i18n ───────────────────────────────────────────────────────────────
    def retranslate_ui(self, lang: str):
        from app.i18n import tr
        if hasattr(self, "_page_title"):
            self._page_title.setText(tr("section.scenarios", lang))
        if hasattr(self, "_page_subtitle"):
            self._page_subtitle.setText(tr("scenarios.subtitle", lang))
        if hasattr(self, "_save_btn"):
            self._save_btn.setText(tr("scenarios.btn.save", lang))
        if hasattr(self, "_sec_traffic_lbl"):
            self._sec_traffic_lbl.setText(tr("scenarios.section.traffic", lang).upper())
        if hasattr(self, "traffic_file_lbl"):
            if not self._traffic_profile:
                self.traffic_file_lbl.setText(tr("scenarios.traffic.empty", lang))
        if hasattr(self, "_btn_import_csv"):
            self._btn_import_csv.setText(tr("scenarios.btn.import_csv", lang))
            self._btn_clear_traffic.setText(tr("scenarios.btn.clear", lang))
        if hasattr(self, "_sec_saved_lbl"):
            self._sec_saved_lbl.setText(tr("scenarios.section.saved", lang).upper())
        if hasattr(self, "table"):
            self.table.setHorizontalHeaderLabels([
                "ID",
                tr("scenarios.col.name", lang),
                tr("scenarios.col.clients", lang),
                tr("scenarios.col.vehicles", lang),
                tr("scenarios.col.algo", lang),
                tr("scenarios.col.date", lang),
                tr("scenarios.col.tags", lang),
                tr("scenarios.col.actions", lang),
            ])
        if hasattr(self, "_btn_import_json"):
            self._btn_import_json.setText(tr("scenarios.btn.import_json", lang))
            self._btn_export_json.setText(tr("scenarios.btn.export_json", lang))
            self._btn_duplicate.setText(tr("scenarios.btn.duplicate", lang))
        if hasattr(self, "_sec_compare_lbl"):
            self._sec_compare_lbl.setText(tr("scenarios.section.compare", lang).upper())
        if hasattr(self, "_btn_compare"):
            self._btn_compare.setText(tr("scenarios.btn.compare", lang))
        if hasattr(self, "_sec_desc_lbl"):
            self._sec_desc_lbl.setText(tr("scenarios.section.desc", lang).upper())

    # ── Helpers ────────────────────────────────────────────────────────────
    def _update_detail_panel(self, rd: dict | None):
        """Met à jour le panneau droit avec les infos du scénario sélectionné."""
        if rd is None:
            self._det_name.setText("—")
            self._det_clients.setText("—")
            self._det_vehicles.setText("—")
            self._det_algo.setText("—")
            self._det_date.setText("—")
            self.tags_edit.setText("")
            self.desc_text.setPlainText("")
            return
        self._det_name.setText(rd.get("name") or "—")
        self._det_clients.setText(str(rd.get("client_count") or "—"))
        self._det_vehicles.setText(str(rd.get("vehicle_count") or "—"))
        self._det_algo.setText(rd.get("algorithm") or "—")
        dt = rd.get("created_at") or ""
        self._det_date.setText(dt[:16] if dt else "—")
        self.tags_edit.setText(rd.get("tags") or "")
        self.desc_text.setPlainText(rd.get("description") or "")

    # ── Logic ──────────────────────────────────────────────────────────────
    def _save_current(self):
        name, ok = QInputDialog.getText(self, "Sauvegarder scénario", "Nom du scénario :")
        if not ok or not name.strip():
            return
        conn = get_connection()
        clients  = [dict(r) for r in conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()]
        vehicles = [dict(r) for r in conn.execute("SELECT * FROM vehicles").fetchall()]
        depots   = [dict(r) for r in conn.execute("SELECT * FROM depots").fetchall()]
        data = json.dumps({"clients": clients, "vehicles": vehicles, "depots": depots}, default=str)
        conn.execute(
            "INSERT INTO scenarios (name, client_count, vehicle_count, data_json) VALUES (?,?,?,?)",
            (name.strip(), len(clients), len(vehicles), data)
        )
        conn.commit()
        conn.close()
        log_action("SCENARIO_SAVE", f"Scénario '{name}' sauvegardé")
        QMessageBox.information(
            self, "Sauvegardé",
            f"Scénario « {name} » sauvegardé avec {len(clients)} clients et {len(vehicles)} véhicules."
        )
        self.refresh_data()

    def _load_scenario(self, scenario_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM scenarios WHERE id= ?", (scenario_id,)).fetchone()
        if not row or not row["data_json"]:
            conn.close(); return
        n_clients = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
        conn.close()
        reply = QMessageBox.question(
            self, "Restaurer le scénario",
            f"⚠ Cette action remplacera tous vos clients actuels ({n_clients}) "
            f"par les données du scénario « {row['name']} ».\n\n"
            "Les données actuelles seront perdues. Continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        data = json.loads(row["data_json"])
        conn.execute("DELETE FROM clients")
        for c in data.get("clients", []):
            conn.execute(
                """INSERT INTO clients (cust_no, name, address, latitude, longitude, demand_kg,
                   demand_m3, ready_time, due_time, service_time, priority, client_type, instructions)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (c.get("cust_no"), c["name"], c.get("address", ""),
                 c["latitude"], c["longitude"], c.get("demand_kg", 0),
                 c.get("demand_m3", 0), c.get("ready_time", 0), c.get("due_time", 1440),
                 c.get("service_time", 10), c.get("priority", 3),
                 c.get("client_type", "standard"), c.get("instructions", ""))
            )
        conn.commit()
        conn.close()
        log_action("SCENARIO_LOAD", f"Scénario #{scenario_id} chargé")
        QMessageBox.information(self, "Restauré", f"Scénario « {row['name']} » restauré.")
        if hasattr(self.main_window, "clients_w"):
            self.main_window.clients_w.refresh_data()

    def _delete_scenario(self, scenario_id):
        reply = QMessageBox.question(
            self, "Confirmer la suppression",
            "Supprimer ce scénario définitivement ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM scenarios WHERE id= ?", (scenario_id,))
            conn.commit()
            conn.close()
            log_action("SCENARIO_DELETE", f"Scénario #{scenario_id} supprimé")
            self.refresh_data()

    def _import_traffic_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer profil trafic", os.path.expanduser("~"),
            "CSV files (*.csv);;All files (*)"
        )
        if not path: return
        try:
            profile = {}
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    hour = int(row.get("heure", row.get("hour", 0)))
                    coef = float(row.get("coefficient", row.get("coeff", row.get("coef", 1.0))))
                    profile[hour] = coef
            if not profile:
                QMessageBox.warning(self, "Fichier invalide",
                    "Le CSV doit contenir les colonnes : heure, coefficient")
                return
            self._traffic_profile = profile
            self._traffic_profile_path = path
            try:
                conn = get_connection()
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                             ("traffic_profile", json.dumps(profile)))
                conn.commit()
                conn.close()
            except Exception:
                pass
            self.traffic_file_lbl.setText(f"Chargé : {os.path.basename(path)}")
            self.traffic_file_lbl.setStyleSheet(
                f"color:{C['success']};font-size:11px;font-weight:600;border:none;background:transparent;"
            )
            self._show_traffic_preview(profile)
            log_action("TRAFFIC_CSV", f"Profil importé: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Erreur import", f"Impossible de lire le CSV :\n{e}")

    def _show_traffic_preview(self, profile):
        if not profile:
            self.traffic_preview_lbl.setText(""); return
        parts = []
        for h in range(24):
            c = profile.get(h, 1.0)
            parts.append(f"{h:02d}h ×{c:.1f}")
        lines = ["  ".join(parts[i:i+8]) for i in range(0, len(parts), 8)]
        self.traffic_preview_lbl.setText("\n".join(lines))

    def _clear_traffic_profile(self):
        self._traffic_profile = {}
        self._traffic_profile_path = ""
        self.traffic_file_lbl.setText("Aucun profil chargé")
        self.traffic_file_lbl.setStyleSheet(
            f"color:{C['muted']};font-size:11px;border:none;background:transparent;"
        )
        self.traffic_preview_lbl.setText("")
        try:
            conn = get_connection()
            conn.execute("DELETE FROM settings WHERE key='traffic_profile'")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_traffic_coeff_for_hour(self, hour: int) -> float:
        return self._traffic_profile.get(hour, 1.0)

    def refresh_data(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM scenarios ORDER BY created_at DESC").fetchall()
        conn.close()

        self._scenario_rows = [dict(x) for x in rows]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            rd = dict(row)
            tags = rd.get("tags") or ""
            vals = [
                str(row["id"]),
                row["name"],
                str(row["client_count"] or 0),
                str(row["vehicle_count"] or 0),
                row["algorithm"] or "—",
                row["created_at"][:16] if row["created_at"] else "—",
                str(tags),
            ]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setForeground(QColor(C["text"] if c == 1 else C["text2"]))
                self.table.setItem(r, c, item)

            actions = QWidget()
            actions.setStyleSheet(f"background:{C['card']};")
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 3, 4, 3)
            al.setSpacing(6)

            load_btn = QPushButton("Restaurer")
            load_btn.setFixedHeight(28)
            load_btn.setToolTip("Remplace les clients/véhicules/dépôts actuels par ce scénario")
            load_btn.setStyleSheet(
                f"background:{C['warning']};color:#0D1B2A;border:none;"
                "border-radius:5px;padding:0 10px;font-size:11px;font-weight:600;"
            )
            load_btn.clicked.connect(lambda _, rid=row["id"]: self._load_scenario(rid))

            del_btn = QPushButton("Suppr.")
            del_btn.setFixedHeight(28)
            del_btn.setStyleSheet(
                f"background:transparent;color:{C['danger']};border:1px solid {C['danger']};"
                "border-radius:5px;padding:0 10px;font-size:11px;"
            )
            del_btn.clicked.connect(lambda _, rid=row["id"]: self._delete_scenario(rid))

            al.addWidget(load_btn)
            al.addWidget(del_btn)
            al.addStretch()
            self.table.setCellWidget(r, 7, actions)

        self.table.resizeColumnToContents(7)
        self._populate_compare_combos()

    def _populate_compare_combos(self):
        self._cmp_a.clear()
        self._cmp_b.clear()
        for rd in self._scenario_rows:
            self._cmp_a.addItem(rd.get("name", ""), rd.get("id"))
            self._cmp_b.addItem(rd.get("name", ""), rd.get("id"))

    def _on_table_sel(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self._scenario_rows):
            self._update_detail_panel(None)
            return
        rd = self._scenario_rows[r]
        self._update_detail_panel(rd)

    def _selected_row_dict(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self._scenario_rows):
            return None
        return self._scenario_rows[r]

    @staticmethod
    def _map_payload_from_row(rd: dict) -> dict:
        try:
            data = json.loads(rd.get("data_json") or "{}")
        except Exception:
            data = {}
        clients = data.get("clients") or []
        depots = data.get("depots") or []
        depot_list = []
        for d in depots:
            depot_list.append({
                "id": d.get("id", 0),
                "name": d.get("name", "Dépôt"),
                "lat": float(d.get("latitude") or 0),
                "lon": float(d.get("longitude") or 0),
                "address": d.get("address", ""),
                "vehicles": 0,
                "phone": d.get("phone", ""),
                "manager": d.get("manager_name", ""),
            })
        if not depot_list and clients:
            lat = sum(float(c.get("latitude") or 0) for c in clients) / max(len(clients), 1)
            lon = sum(float(c.get("longitude") or 0) for c in clients) / max(len(clients), 1)
            depot_list = [{
                "id": 0, "name": "Centre", "lat": lat, "lon": lon,
                "address": "", "vehicles": 0, "phone": "", "manager": "",
            }]
        if not depot_list:
            depot_list = [{
                "id": 0, "name": "Dépôt", "lat": 33.5731, "lon": -7.5898,
                "address": "", "vehicles": 0, "phone": "", "manager": "",
            }]
        stops = []
        for i, c in enumerate(clients):
            stops.append({"client": {
                "id": c.get("id", i),
                "name": c.get("name", ""),
                "latitude": float(c.get("latitude") or 0),
                "longitude": float(c.get("longitude") or 0),
                "demand_kg": c.get("demand_kg", 0),
                "ready_time": c.get("ready_time", 0),
                "due_time": c.get("due_time", 1440),
                "priority": c.get("priority", 3),
                "client_type": c.get("client_type", "standard"),
            }})
        routes_payload = [{
            "color": "#00D4FF",
            "label": rd.get("name", "Scénario")[:24],
            "vehicle_id": rd.get("id", 0),
            "depot_coords": [depot_list[0]["lat"], depot_list[0]["lon"]],
            "stops": stops,
        }]
        return {"depots": depot_list, "routes": routes_payload}

    def _compare_scenarios(self):
        ida = self._cmp_a.currentData()
        idb = self._cmp_b.currentData()
        if ida is None or idb is None or ida == idb:
            QMessageBox.warning(self, "Comparer", "Sélectionnez deux scénarios distincts.")
            return
        ra = next((x for x in self._scenario_rows if x.get("id") == ida), None)
        rb = next((x for x in self._scenario_rows if x.get("id") == idb), None)
        if not ra or not rb:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Comparaison de scénarios")
        dlg.resize(720, 520)
        dlg.setStyleSheet(_dialog_qss() + f"QDialog{{background:{C['bg']};color:{C['text']};}}")
        lo = QVBoxLayout(dlg)
        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(["Métrique", ra.get("name", "A"), rb.get("name", "B")])
        metrics = []
        for label, key in [
            ("Clients", "client_count"),
            ("Véhicules", "vehicle_count"),
            ("Algorithme", "algorithm"),
        ]:
            metrics.append([label, str(ra.get(key, "—")), str(rb.get(key, "—"))])
        try:
            ja = json.loads(ra.get("results_json") or "{}")
            jb = json.loads(rb.get("results_json") or "{}")
            for algo in sorted(set(ja.keys()) | set(jb.keys())):
                a, b = ja.get(algo, {}), jb.get(algo, {})
                metrics.append([
                    f"Distance km ({algo})",
                    f"{a.get('total_distance_km', '—'):.1f}" if isinstance(a.get("total_distance_km"), (int, float)) else "—",
                    f"{b.get('total_distance_km', '—'):.1f}" if isinstance(b.get("total_distance_km"), (int, float)) else "—",
                ])
                metrics.append([
                    f"Coût total ({algo})",
                    f"{a.get('total_cost', '—'):.2f}" if isinstance(a.get("total_cost"), (int, float)) else "—",
                    f"{b.get('total_cost', '—'):.2f}" if isinstance(b.get("total_cost"), (int, float)) else "—",
                ])
                metrics.append([
                    f"Ponctualité % ({algo})",
                    f"{a.get('respect_rate', '—'):.1f}" if isinstance(a.get("respect_rate"), (int, float)) else "—",
                    f"{b.get('respect_rate', '—'):.1f}" if isinstance(b.get("respect_rate"), (int, float)) else "—",
                ])
        except Exception:
            pass
        tbl.setRowCount(len(metrics))
        for i, row in enumerate(metrics):
            for j, val in enumerate(row):
                tbl.setItem(i, j, QTableWidgetItem(val))
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        lo.addWidget(tbl)
        if HAS_MPL:
            fig = Figure(facecolor=C["bg"])
            ax = fig.add_subplot(111)
            ax.set_facecolor(C["bg3"])
            names = [ra.get("name", "A")[:12], rb.get("name", "B")[:12]]
            try:
                ja = json.loads(ra.get("results_json") or "{}")
                jb = json.loads(rb.get("results_json") or "{}")
                alg = next(iter(ja.keys()), None)
                if alg:
                    y1 = float(ja.get(alg, {}).get("total_distance_km") or 0)
                    y2 = float(jb.get(alg, {}).get("total_distance_km") or 0)
                    bars = ax.bar(names, [y1, y2], color=[C["accent"], C["orange"]])
                    ax.bar_label(bars, fmt="%.1f km", color=C["text2"], padding=4)
                    ax.set_ylabel(f"Distance km ({alg})", color=C["text2"])
                else:
                    ax.text(0.5, 0.5, "Aucune donnée d'optimisation\n(results_json vide)",
                            ha="center", va="center", color=C["text2"])
            except Exception:
                ax.text(0.5, 0.5, "Graphique indisponible", ha="center", va="center")
            ax.tick_params(colors=C["text2"])
            ax.spines[:].set_color(C["border2"])
            cv = FigCanvas(fig)
            cv.setFixedHeight(200)
            lo.addWidget(cv)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lo.addWidget(bb)
        dlg.exec()

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer scénario JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                pack = json.load(f)
            name = pack.get("name") or os.path.basename(path)
            conn = get_connection()
            conn.execute(
                """INSERT INTO scenarios (name, description, tags, client_count, vehicle_count,
                   algorithm, data_json, config_json, results_json)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    name,
                    pack.get("description"),
                    pack.get("tags"),
                    pack.get("client_count", 0),
                    pack.get("vehicle_count", 0),
                    pack.get("algorithm"),
                    json.dumps(pack.get("data") or {}),
                    json.dumps(pack.get("config") or {}),
                    json.dumps(pack.get("results") or {}),
                ),
            )
            conn.commit()
            conn.close()
            log_action("SCENARIO_IMPORT", name)
            QMessageBox.information(self, "Import", f"Scénario « {name} » importé.")
            self.refresh_data()
        except Exception as e:
            QMessageBox.warning(self, "Import", str(e))

    def _export_json(self):
        rd = self._selected_row_dict()
        if not rd:
            QMessageBox.information(self, "Export", "Sélectionnez une ligne dans le tableau.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter JSON", f"scenario_{rd['id']}.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            pack = {
                "name": rd.get("name"),
                "description": rd.get("description"),
                "tags": rd.get("tags"),
                "client_count": rd.get("client_count"),
                "vehicle_count": rd.get("vehicle_count"),
                "algorithm": rd.get("algorithm"),
                "data": json.loads(rd.get("data_json") or "{}"),
                "config": json.loads(rd.get("config_json") or "{}"),
                "results": json.loads(rd.get("results_json") or "{}"),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(pack, f, indent=2, ensure_ascii=False)
            log_action("SCENARIO_EXPORT", path)
            QMessageBox.information(self, "Export", f"Fichier enregistré :\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export", str(e))

    def _duplicate_selected(self):
        rd = self._selected_row_dict()
        if not rd:
            QMessageBox.information(self, "Dupliquer", "Sélectionnez un scénario.")
            return
        name, ok = QInputDialog.getText(self, "Dupliquer", "Nom du nouveau scénario :",
                                        text=f"{rd.get('name','')} (copie)")
        if not ok or not name.strip():
            return
        try:
            conn = get_connection()
            conn.execute(
                """INSERT INTO scenarios (name, description, tags, client_count, vehicle_count,
                   traffic_coeff, weather_coeff, algorithm, data_json, config_json, results_json)
                   SELECT ?, description, tags, client_count, vehicle_count,
                   traffic_coeff, weather_coeff, algorithm, data_json, config_json, results_json
                   FROM scenarios WHERE id= ?""",
                (name.strip(), rd["id"]),
            )
            conn.commit()
            conn.close()
            log_action("SCENARIO_DUPLICATE", f"{rd['id']} → {name}")
            self.refresh_data()
        except Exception as e:
            QMessageBox.warning(self, "Dupliquer", str(e))

    def _save_description(self):
        rd = self._selected_row_dict()
        if not rd:
            QMessageBox.information(self, "Description", "Sélectionnez d'abord un scénario.")
            return
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE scenarios SET description= ? WHERE id= ?",
                (self.desc_text.toPlainText().strip(), rd["id"]),
            )
            conn.commit()
            conn.close()
            log_action("SCENARIO_DESC", f"#{rd['id']}")
            QMessageBox.information(self, "OK", "Description enregistrée.")
            self.refresh_data()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))

    def _save_tags(self):
        rd = self._selected_row_dict()
        if not rd:
            QMessageBox.information(self, "Tags", "Sélectionnez d'abord un scénario.")
            return
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE scenarios SET tags= ? WHERE id= ?",
                (self.tags_edit.text().strip(), rd["id"]),
            )
            conn.commit()
            conn.close()
            log_action("SCENARIO_TAGS", f"#{rd['id']}")
            self.refresh_data()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))
