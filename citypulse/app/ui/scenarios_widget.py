import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help


class ScenariosWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Gestion des Scénarios")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()

        save_btn = QPushButton("Sauvegarder scénario actuel")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_current)
        header.addWidget(save_btn)

        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "scenarios"))
        header.addWidget(help_btn)

        layout.addLayout(header)

        subtitle = QLabel("Sauvegardez, chargez et comparez vos scénarios d'optimisation")
        subtitle.setObjectName("subheading")
        layout.addWidget(subtitle)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nom", "Clients", "Véhicules", "Algorithme", "Date", "Actions"
        ])
        _tips = [
            "Identifiant unique du sc\u00e9nario",
            "Nom donn\u00e9 au sc\u00e9nario lors de la sauvegarde",
            "Nombre de clients inclus dans le sc\u00e9nario",
            "Nombre de v\u00e9hicules inclus dans le sc\u00e9nario",
            "Algorithme d'optimisation utilis\u00e9",
            "Date de cr\u00e9ation du sc\u00e9nario",
            "Actions disponibles sur cette ligne",
        ]
        for i, tip in enumerate(_tips):
            self.table.horizontalHeaderItem(i).setToolTip(tip)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultSectionSize(90)
        self.table.horizontalHeader().setMinimumSectionSize(50)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setShowGrid(True)
        layout.addWidget(self.table)

        # Description
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMaximumHeight(120)
        self.desc_text.setPlaceholderText("Sélectionnez un scénario pour voir sa description...")
        layout.addWidget(self.desc_text)

    def _save_current(self):
        name, ok = QInputDialog.getText(self, "Sauvegarder scénario", "Nom du scénario :")
        if not ok or not name.strip():
            return

        conn = get_connection()
        clients = [dict(r) for r in conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()]
        vehicles = [dict(r) for r in conn.execute("SELECT * FROM vehicles").fetchall()]
        depots = [dict(r) for r in conn.execute("SELECT * FROM depots").fetchall()]

        data = json.dumps({
            "clients": clients,
            "vehicles": vehicles,
            "depots": depots,
        }, default=str)

        conn.execute(
            """INSERT INTO scenarios (name, client_count, vehicle_count, data_json)
               VALUES (?, ?, ?, ?)""",
            (name.strip(), len(clients), len(vehicles), data)
        )
        conn.commit()
        conn.close()
        log_action("SCENARIO_SAVE", f"Scénario '{name}' sauvegardé")
        QMessageBox.information(self, "Sauvegardé", f"Scénario '{name}' sauvegardé avec {len(clients)} clients.")
        self.refresh_data()

    def _load_scenario(self, scenario_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
        if not row or not row["data_json"]:
            conn.close()
            return

        data = json.loads(row["data_json"])

        # Clear and reload
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
        QMessageBox.information(self, "Chargé", f"Scénario '{row['name']}' chargé.")

        if hasattr(self.main_window, 'clients_w'):
            self.main_window.clients_w.refresh_data()

    def _delete_scenario(self, scenario_id):
        reply = QMessageBox.question(self, "Confirmer", "Supprimer ce scénario ?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM scenarios WHERE id=?", (scenario_id,))
            conn.commit()
            conn.close()
            log_action("SCENARIO_DELETE", f"Scénario #{scenario_id} supprimé")
            self.refresh_data()

    def refresh_data(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM scenarios ORDER BY created_at DESC").fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(row["id"])))
            self.table.setItem(r, 1, QTableWidgetItem(row["name"]))
            self.table.setItem(r, 2, QTableWidgetItem(str(row["client_count"] or 0)))
            self.table.setItem(r, 3, QTableWidgetItem(str(row["vehicle_count"] or 0)))
            self.table.setItem(r, 4, QTableWidgetItem(row["algorithm"] or "—"))
            self.table.setItem(r, 5, QTableWidgetItem(row["created_at"][:16] if row["created_at"] else "—"))

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            load_btn = QPushButton("Ouvrir")
            load_btn.setFixedSize(65, 28)
            load_btn.setToolTip("Charger")
            load_btn.clicked.connect(lambda _, rid=row["id"]: self._load_scenario(rid))
            del_btn = QPushButton("Suppr")
            del_btn.setFixedSize(60, 28)
            del_btn.setToolTip("Supprimer")
            del_btn.clicked.connect(lambda _, rid=row["id"]: self._delete_scenario(rid))
            al.addWidget(load_btn)
            al.addWidget(del_btn)
            self.table.setCellWidget(r, 6, actions)
