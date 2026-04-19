from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QLineEdit,
    QDoubleSpinBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help
from .toast import show_toast


class DepotDialog(QDialog):
    def __init__(self, parent=None, depot=None):
        super().__init__(parent)
        self.depot = depot
        self.setWindowTitle("Modifier dépôt" if depot else "Nouveau dépôt")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self.name_input = QLineEdit(depot["name"] if depot else "")
        self.address_input = QLineEdit(depot["address"] if depot and depot["address"] else "")
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)
        self.lat_input.setDecimals(6)
        self.lat_input.setValue(depot["latitude"] if depot else 33.5731)
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180, 180)
        self.lon_input.setDecimals(6)
        self.lon_input.setValue(depot["longitude"] if depot else -7.5898)
        self.open_input = QLineEdit(depot["opening_time"] if depot else "08:00")
        self.close_input = QLineEdit(depot["closing_time"] if depot else "18:00")
        self.capacity_input = QDoubleSpinBox()
        self.capacity_input.setRange(0, 999999)
        self.capacity_input.setValue(depot["storage_capacity"] if depot and depot["storage_capacity"] else 0)

        layout.addRow("Nom *", self.name_input)
        layout.addRow("Adresse", self.address_input)
        layout.addRow("Latitude", self.lat_input)
        layout.addRow("Longitude", self.lon_input)
        layout.addRow("Ouverture", self.open_input)
        layout.addRow("Fermeture", self.close_input)
        layout.addRow("Capacité stockage", self.capacity_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Sauvegarder")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addRow(btn_layout)

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "address": self.address_input.text().strip(),
            "latitude": self.lat_input.value(),
            "longitude": self.lon_input.value(),
            "opening_time": self.open_input.text().strip(),
            "closing_time": self.close_input.text().strip(),
            "storage_capacity": self.capacity_input.value(),
        }


class DepotsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Gestion des Dépôts")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("Ajouter un dépôt")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_depot)
        header.addWidget(add_btn)

        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "depots"))
        header.addWidget(help_btn)

        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nom", "Adresse", "Latitude", "Longitude", "Ouverture", "Fermeture", "Actions"
        ])
        _tips = [
            "Identifiant unique du d\u00e9p\u00f4t",
            "Nom du d\u00e9p\u00f4t ou de l'entrep\u00f4t",
            "Adresse postale du d\u00e9p\u00f4t",
            "Coordonn\u00e9e GPS latitude (degr\u00e9s d\u00e9cimaux)",
            "Coordonn\u00e9e GPS longitude (degr\u00e9s d\u00e9cimaux)",
            "Heure d'ouverture du d\u00e9p\u00f4t (HH:MM)",
            "Heure de fermeture du d\u00e9p\u00f4t (HH:MM)",
            "Actions disponibles sur cette ligne",
        ]
        for i, tip in enumerate(_tips):
            self.table.horizontalHeaderItem(i).setToolTip(tip)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultSectionSize(90)
        self.table.horizontalHeader().setMinimumSectionSize(50)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setShowGrid(True)

        # Formula bar (Minitab-style)
        formula_bar = QFrame()
        formula_bar.setObjectName("formulaBar")
        fb_layout = QHBoxLayout(formula_bar)
        fb_layout.setContentsMargins(0, 0, 0, 0)
        fb_layout.setSpacing(0)
        self.cell_ref = QLabel("A1")
        self.cell_ref.setObjectName("cellRef")
        self.cell_content = QLineEdit()
        self.cell_content.setObjectName("cellContent")
        self.cell_content.setPlaceholderText("Sélectionnez une cellule...")
        self.cell_content.returnPressed.connect(self._apply_formula_bar)
        fb_layout.addWidget(self.cell_ref)
        fb_layout.addWidget(self.cell_content)
        layout.addWidget(formula_bar)

        layout.addWidget(self.table)

        # Inline editing signals
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self._col_db_map = {
            1: "name", 2: "address", 3: "latitude", 4: "longitude",
            5: "opening_time", 6: "closing_time"
        }
        self._editing_enabled = False

    def refresh_data(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM depots ORDER BY id").fetchall()
        conn.close()

        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            id_item = QTableWidgetItem(str(row["id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, QTableWidgetItem(row["name"]))
            self.table.setItem(r, 2, QTableWidgetItem(row["address"] or ""))
            self.table.setItem(r, 3, QTableWidgetItem(f"{row['latitude']:.6f}"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{row['longitude']:.6f}"))
            self.table.setItem(r, 5, QTableWidgetItem(row["opening_time"] or ""))
            self.table.setItem(r, 6, QTableWidgetItem(row["closing_time"] or ""))

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(55, 28)
            edit_btn.clicked.connect(lambda _, rid=row["id"]: self._edit_depot(rid))
            del_btn = QPushButton("Suppr")
            del_btn.setFixedSize(60, 28)
            del_btn.clicked.connect(lambda _, rid=row["id"]: self._delete_depot(rid))
            al.addWidget(edit_btn)
            al.addWidget(del_btn)
            self.table.setCellWidget(r, 7, actions)

        self.table.blockSignals(False)
        self._editing_enabled = True

    def _on_current_cell_changed(self, row, col, prev_row, prev_col):
        if row < 0 or col < 0:
            return
        col_letter = chr(65 + col) if col < 26 else f"C{col}"
        self.cell_ref.setText(f"{col_letter}{row + 1}")
        item = self.table.item(row, col)
        self.cell_content.setText(item.text() if item else "")

    def _apply_formula_bar(self):
        row = self.table.currentRow()
        col = self.table.currentColumn()
        if row >= 0 and col > 0 and col in self._col_db_map:
            item = self.table.item(row, col)
            if item:
                item.setText(self.cell_content.text())

    def _on_cell_changed(self, row, col):
        if not self._editing_enabled or col not in self._col_db_map:
            return
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        depot_id = int(id_item.text())
        field = self._col_db_map[col]
        value = self.table.item(row, col).text()
        try:
            if field in ("latitude", "longitude"):
                value = float(value)
            conn = get_connection()
            conn.execute(
                f"UPDATE depots SET {field}=? WHERE id=?",
                (value, depot_id)
            )
            conn.commit()
            conn.close()
            log_action("DEPOT_INLINE_EDIT", f"Dépôt #{depot_id} {field}='{value}'")
        except (ValueError, Exception) as e:
            QMessageBox.warning(self, "Erreur de saisie", f"Valeur invalide pour {field}: {e}")
            self.refresh_data()

    def _add_depot(self):
        dlg = DepotDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            conn = get_connection()
            conn.execute(
                "INSERT INTO depots (name, address, latitude, longitude, opening_time, closing_time, storage_capacity) VALUES (?,?,?,?,?,?,?)",
                (data["name"], data["address"], data["latitude"], data["longitude"],
                 data["opening_time"], data["closing_time"], data["storage_capacity"])
            )
            conn.commit()
            conn.close()
            log_action("DEPOT_CREATE", f"Dépôt '{data['name']}' créé")
            show_toast(self.window(), f"Dépôt '{data['name']}' créé", "success")
            self.refresh_data()

    def _edit_depot(self, depot_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM depots WHERE id=?", (depot_id,)).fetchone()
        conn.close()
        if not row:
            return
        dlg = DepotDialog(self, dict(row))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            conn = get_connection()
            conn.execute(
                "UPDATE depots SET name=?, address=?, latitude=?, longitude=?, opening_time=?, closing_time=?, storage_capacity=? WHERE id=?",
                (data["name"], data["address"], data["latitude"], data["longitude"],
                 data["opening_time"], data["closing_time"], data["storage_capacity"], depot_id)
            )
            conn.commit()
            conn.close()
            log_action("DEPOT_UPDATE", f"Dépôt #{depot_id} modifié")
            show_toast(self.window(), "Dépôt modifié", "success")
            self.refresh_data()

    def _delete_depot(self, depot_id):
        if depot_id == 1:
            QMessageBox.warning(self, "Erreur", "Le dépôt principal ne peut pas être supprimé.")
            return
        reply = QMessageBox.question(self, "Confirmer", "Supprimer ce dépôt ?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM depots WHERE id=?", (depot_id,))
            conn.commit()
            conn.close()
            log_action("DEPOT_DELETE", f"Dépôt #{depot_id} supprimé")
            show_toast(self.window(), "Dépôt supprimé", "info")
            self.refresh_data()
