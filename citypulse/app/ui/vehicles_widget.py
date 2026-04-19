from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QLineEdit,
    QDoubleSpinBox, QComboBox, QMessageBox, QFileDialog, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import os
import csv
import openpyxl
from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help
from .import_dialog import ColumnSelectionDialog
from .toast import show_toast
from .empty_state import EmptyState


class VehicleDialog(QDialog):
    def __init__(self, parent=None, vehicle=None):
        super().__init__(parent)
        self.vehicle = vehicle
        self.setWindowTitle("Modifier véhicule" if vehicle else "Nouveau véhicule")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)
        layout.setSpacing(12)

        self.reg_input = QLineEdit(vehicle["registration"] if vehicle else "")
        self.type_input = QComboBox()
        self.type_input.addItems(["fourgon", "camionnette", "poids lourd", "moto"])
        if vehicle and vehicle["type"]:
            idx = self.type_input.findText(vehicle["type"])
            if idx >= 0:
                self.type_input.setCurrentIndex(idx)
        self.cap_kg = QDoubleSpinBox()
        self.cap_kg.setRange(0, 99999)
        self.cap_kg.setValue(vehicle["capacity_kg"] if vehicle else 1000)
        self.cap_m3 = QDoubleSpinBox()
        self.cap_m3.setRange(0, 9999)
        self.cap_m3.setValue(vehicle["capacity_m3"] if vehicle else 10)
        self.speed_input = QDoubleSpinBox()
        self.speed_input.setRange(1, 200)
        self.speed_input.setValue(vehicle["max_speed_kmh"] if vehicle else 60)
        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 100)
        self.cost_input.setDecimals(2)
        self.cost_input.setValue(vehicle["cost_per_km"] if vehicle else 0.5)
        self.driver_input = QLineEdit(vehicle["driver_name"] if vehicle and vehicle["driver_name"] else "")
        self.status_input = QComboBox()
        self.status_input.addItems(["disponible", "en tournée", "maintenance", "hors service"])
        if vehicle and vehicle["status"]:
            idx = self.status_input.findText(vehicle["status"])
            if idx >= 0:
                self.status_input.setCurrentIndex(idx)

        layout.addRow("Immatriculation *", self.reg_input)
        layout.addRow("Type", self.type_input)
        layout.addRow("Capacité (kg)", self.cap_kg)
        layout.addRow("Capacité (m³)", self.cap_m3)
        layout.addRow("Vitesse max (km/h)", self.speed_input)
        layout.addRow("Coût / km (€)", self.cost_input)
        layout.addRow("Chauffeur", self.driver_input)
        layout.addRow("Statut", self.status_input)

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
            "registration": self.reg_input.text().strip(),
            "type": self.type_input.currentText(),
            "capacity_kg": self.cap_kg.value(),
            "capacity_m3": self.cap_m3.value(),
            "max_speed_kmh": self.speed_input.value(),
            "cost_per_km": self.cost_input.value(),
            "driver_name": self.driver_input.text().strip(),
            "status": self.status_input.currentText(),
        }


class VehiclesWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Gestion des Véhicules")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.setMaximumWidth(250)
        self.search_input.textChanged.connect(self._filter_table)
        header.addWidget(self.search_input)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tous", "Fourgon", "Camionnette", "Poids lourd", "Moto"])
        self.filter_combo.currentTextChanged.connect(lambda: self.refresh_data())
        header.addWidget(self.filter_combo)

        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "vehicles"))
        header.addWidget(help_btn)

        layout.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("  Ajouter")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_vehicle)
        import_btn = QPushButton("  Importer")
        import_btn.setToolTip("Importer depuis CSV ou Excel (XLS/XLSX)")
        import_btn.clicked.connect(self._import_data)
        export_btn = QPushButton("  Exporter CSV")
        export_btn.clicked.connect(self._export_csv)
        purge_btn = QPushButton("  Tout supprimer")
        purge_btn.setToolTip("Supprimer tous les véhicules")
        purge_btn.clicked.connect(self._purge_data)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(import_btn)
        toolbar.addWidget(export_btn)
        toolbar.addWidget(purge_btn)
        toolbar.addStretch()

        self.count_label = QLabel("0 véhicules")
        self.count_label.setStyleSheet("color: #6c6c6c; font-size: 12px;")
        toolbar.addWidget(self.count_label)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Immatriculation", "Type", "Capacité kg", "Capacité m³",
            "Vitesse", "Coût/km", "Chauffeur", "Statut", "Actions"
        ])
        _tips = [
            "Identifiant unique du véhicule",
            "Numéro d'immatriculation",
            "Type de véhicule (camionnette, poids-lourd…)",
            "Capacité de charge maximale en kilogrammes",
            "Capacité volumique maximale en mètres cubes",
            "Vitesse maximale autorisée (km/h)",
            "Coût d'exploitation par kilomètre (€)",
            "Nom du chauffeur affecté",
            "État actuel : disponible, maintenance, hors service",
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
        self.table.setSortingEnabled(True)
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

        # Stacked: table + empty state
        self._stack = QStackedWidget()
        self._stack.addWidget(self.table)
        self._empty = EmptyState(
            title="Aucun véhicule",
            subtitle="Ajoutez des véhicules manuellement ou importez un fichier CSV/Excel.",
            action_text="Importer des véhicules",
            action_callback=self._import_data,
        )
        self._stack.addWidget(self._empty)
        layout.addWidget(self._stack)

        # Inline editing signals
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self._col_db_map = {
            1: "registration", 2: "type", 3: "capacity_kg", 4: "capacity_m3",
            5: "max_speed_kmh", 6: "cost_per_km", 7: "driver_name", 8: "status"
        }
        self._editing_enabled = False

    def refresh_data(self):
        conn = get_connection()
        filter_type = self.filter_combo.currentText().lower() if hasattr(self, 'filter_combo') else "tous"
        if filter_type == "tous":
            rows = conn.execute("SELECT * FROM vehicles ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM vehicles WHERE type=? ORDER BY id",
                                (filter_type,)).fetchall()
        conn.close()

        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            id_item = QTableWidgetItem(str(row["id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, QTableWidgetItem(row["registration"] or ""))
            self.table.setItem(r, 2, QTableWidgetItem(row["type"] or ""))
            self.table.setItem(r, 3, QTableWidgetItem(str(row["capacity_kg"])))
            self.table.setItem(r, 4, QTableWidgetItem(str(row["capacity_m3"])))
            self.table.setItem(r, 5, QTableWidgetItem(str(row["max_speed_kmh"])))
            self.table.setItem(r, 6, QTableWidgetItem(str(row["cost_per_km"])))
            self.table.setItem(r, 7, QTableWidgetItem(row["driver_name"] or ""))
            status = row["status"] or "disponible"
            item = QTableWidgetItem(status)
            if status == "maintenance":
                item.setForeground(QColor("#888888"))
            elif status == "hors service":
                item.setForeground(QColor("#aaaaaa"))
            self.table.setItem(r, 8, item)

            # Action buttons
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(55, 28)
            edit_btn.setToolTip("Modifier")
            edit_btn.clicked.connect(lambda _, rid=row["id"]: self._edit_vehicle(rid))
            del_btn = QPushButton("Suppr")
            del_btn.setFixedSize(60, 28)
            del_btn.setToolTip("Supprimer")
            del_btn.clicked.connect(lambda _, rid=row["id"]: self._delete_vehicle(rid))
            dup_btn = QPushButton("Dupl")
            dup_btn.setFixedSize(55, 28)
            dup_btn.setToolTip("Dupliquer")
            dup_btn.clicked.connect(lambda _, rid=row["id"]: self._duplicate_vehicle(rid))
            al.addWidget(edit_btn)
            al.addWidget(del_btn)
            al.addWidget(dup_btn)
            self.table.setCellWidget(r, 9, actions)

        self.table.blockSignals(False)
        self._editing_enabled = True
        self.count_label.setText(f"{len(rows)} véhicules")
        self._stack.setCurrentIndex(0 if len(rows) > 0 else 1)

    def _filter_table(self, text):
        for r in range(self.table.rowCount()):
            show = False
            for c in range(self.table.columnCount() - 1):
                item = self.table.item(r, c)
                if item and text.lower() in item.text().lower():
                    show = True
                    break
            self.table.setRowHidden(r, not show)

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
        vehicle_id = int(id_item.text())
        field = self._col_db_map[col]
        value = self.table.item(row, col).text()
        try:
            if field in ("capacity_kg", "capacity_m3", "max_speed_kmh", "cost_per_km"):
                value = float(value)
            conn = get_connection()
            conn.execute(
                f"UPDATE vehicles SET {field}=? WHERE id=?",
                (value, vehicle_id)
            )
            conn.commit()
            conn.close()
            log_action("VEHICLE_INLINE_EDIT", f"Véhicule #{vehicle_id} {field}='{value}'")
        except (ValueError, Exception) as e:
            QMessageBox.warning(self, "Erreur de saisie", f"Valeur invalide pour {field}: {e}")
            self.refresh_data()

    def _add_vehicle(self):
        dlg = VehicleDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["registration"]:
                QMessageBox.warning(self, "Erreur", "Immatriculation obligatoire.")
                return
            conn = get_connection()
            conn.execute(
                """INSERT INTO vehicles (registration, type, capacity_kg, capacity_m3,
                   max_speed_kmh, cost_per_km, driver_name, status, depot_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (data["registration"], data["type"], data["capacity_kg"], data["capacity_m3"],
                 data["max_speed_kmh"], data["cost_per_km"], data["driver_name"], data["status"])
            )
            conn.commit()
            conn.close()
            log_action("VEHICLE_CREATE", f"Véhicule '{data['registration']}' créé")
            self.refresh_data()

    def _edit_vehicle(self, vid):
        conn = get_connection()
        row = conn.execute("SELECT * FROM vehicles WHERE id=?", (vid,)).fetchone()
        conn.close()
        if not row:
            return
        dlg = VehicleDialog(self, dict(row))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            conn = get_connection()
            conn.execute(
                """UPDATE vehicles SET registration=?, type=?, capacity_kg=?, capacity_m3=?,
                   max_speed_kmh=?, cost_per_km=?, driver_name=?, status=? WHERE id=?""",
                (data["registration"], data["type"], data["capacity_kg"], data["capacity_m3"],
                 data["max_speed_kmh"], data["cost_per_km"], data["driver_name"], data["status"], vid)
            )
            conn.commit()
            conn.close()
            log_action("VEHICLE_UPDATE", f"Véhicule #{vid} modifié")
            self.refresh_data()

    def _delete_vehicle(self, vid):
        reply = QMessageBox.question(self, "Confirmer", "Supprimer ce véhicule ?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM vehicles WHERE id=?", (vid,))
            conn.commit()
            conn.close()
            log_action("VEHICLE_DELETE", f"Véhicule #{vid} supprimé")
            self.refresh_data()

    def _duplicate_vehicle(self, vid):
        conn = get_connection()
        row = conn.execute("SELECT * FROM vehicles WHERE id=?", (vid,)).fetchone()
        if row:
            conn.execute(
                """INSERT INTO vehicles (registration, type, capacity_kg, capacity_m3,
                   max_speed_kmh, cost_per_km, driver_name, status, depot_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"{row['registration']} (copie)", row["type"], row["capacity_kg"],
                 row["capacity_m3"], row["max_speed_kmh"], row["cost_per_km"],
                 row["driver_name"], row["status"], row["depot_id"])
            )
            conn.commit()
            log_action("VEHICLE_DUPLICATE", f"Véhicule #{vid} dupliqué")
        conn.close()
        self.refresh_data()

    def _purge_data(self):
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        conn.close()
        if count == 0:
            QMessageBox.information(self, "Purge", "Aucun véhicule à supprimer.")
            return
        reply = QMessageBox.warning(
            self, "Supprimer tous les véhicules",
            f"Voulez-vous vraiment supprimer les {count} véhicules ?\n\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM vehicles")
            conn.commit()
            conn.close()
            log_action("VEHICLE_PURGE", f"{count} véhicules supprimés")
            show_toast(self.window(), f"{count} véhicules supprimés", "success")
            self.refresh_data()

    def _import_data(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Importer Véhicules", "",
            "Tous les formats (*.csv *.xls *.xlsx);;CSV (*.csv);;Excel (*.xls *.xlsx)"
        )
        if not filepath:
            return
        dlg = ColumnSelectionDialog(self, filepath)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        selected = set(dlg.selected_columns)
        ext = os.path.splitext(filepath)[1].lower()
        try:
            if ext in (".xls", ".xlsx"):
                self._import_xls(filepath, selected)
            else:
                self._import_csv(filepath, selected)
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'import", str(e))

    def _import_xls(self, filepath, selected=None):
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers_raw = next(rows_iter)
        headers = [str(h).strip() if h else f"col{i}" for i, h in enumerate(headers_raw)]
        conn = get_connection()
        count = 0

        def _get(row, *keys, default=None):
            for k in keys:
                if k in row and (selected is None or k in selected):
                    v = row[k]
                    if v is not None:
                        return v
            return default

        for vals in rows_iter:
            row = dict(zip(headers, vals))
            if "VEHICLE_CODE" in headers:
                reg = str(_get(row, "VEHICLE_CODE", "REGISTRATION", default=f"V-{count}"))
                vtype = str(_get(row, "VEHICLE_TYPE", "TYPE", default="fourgon"))
                cap_kg = float(_get(row, "CAPACITY_WEIGHT_KG", "CAPACITY_KG", default=1000))
                cap_m3 = float(_get(row, "CAPACITY_VOLUME_M3", "CAPACITY_M3", default=10))
                speed = float(_get(row, "MAX_SPEED_KMH", "SPEED", default=60))
                cost = float(_get(row, "COST_PER_KM", "VARIABLE_COST_KM", default=0.5))
                driver = str(_get(row, "DRIVER_NAME", "DRIVER", default=""))
                conn.execute(
                    """INSERT INTO vehicles (registration, type, capacity_kg, capacity_m3,
                       max_speed_kmh, cost_per_km, driver_name, status, depot_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'disponible', 1)""",
                    (reg, vtype, cap_kg, cap_m3, speed, cost, driver)
                )
            else:
                reg = str(_get(row, "registration", "immatriculation", default=f"V-{count}"))
                vtype = str(_get(row, "type", default="fourgon"))
                cap_kg = float(_get(row, "capacity_kg", "capacite_kg", default=1000))
                cap_m3 = float(_get(row, "capacity_m3", "capacite_m3", default=10))
                speed = float(_get(row, "max_speed_kmh", "vitesse_kmh", default=60))
                cost = float(_get(row, "cost_per_km", "cout_par_km", default=0.5))
                conn.execute(
                    """INSERT INTO vehicles (registration, type, capacity_kg, capacity_m3,
                       max_speed_kmh, cost_per_km, depot_id)
                       VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (reg, vtype, cap_kg, cap_m3, speed, cost)
                )
            count += 1
        conn.commit()
        conn.close()
        wb.close()
        log_action("VEHICLE_IMPORT_XLS", f"{count} véhicules importés depuis {filepath}")
        show_toast(self.window(), f"{count} véhicules importés depuis Excel", "success")
        self.refresh_data()

    def _import_csv(self, filepath=None, selected=None):
        if filepath is None:
            filepath, _ = QFileDialog.getOpenFileName(self, "Importer Véhicules CSV", "", "CSV (*.csv)")
            if not filepath:
                return

        def _get(row, *keys, default=None):
            for k in keys:
                if k in row and (selected is None or k in selected):
                    v = row[k]
                    if v is not None and v != "":
                        return v
            return default

        try:
            conn = get_connection()
            count = 0
            with open(filepath, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    conn.execute(
                        """INSERT INTO vehicles (registration, type, capacity_kg, capacity_m3,
                           max_speed_kmh, cost_per_km, depot_id)
                           VALUES (?, ?, ?, ?, ?, ?, 1)""",
                        (_get(row, "registration", "immatriculation", default=f"V-{count}"),
                         _get(row, "type", default="fourgon"),
                         float(_get(row, "capacity_kg", "capacite_kg", default=1000)),
                         float(_get(row, "capacity_m3", "capacite_m3", default=10)),
                         float(_get(row, "max_speed_kmh", "vitesse_kmh", default=60)),
                         float(_get(row, "cost_per_km", "cout_par_km", default=0.5)))
                    )
                    count += 1
            conn.commit()
            conn.close()
            log_action("VEHICLE_IMPORT", f"{count} véhicules importés")
            show_toast(self.window(), f"{count} véhicules importés", "success")
            self.refresh_data()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def _export_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Exporter CSV", "vehicules.csv", "CSV (*.csv)")
        if not filepath:
            return
        conn = get_connection()
        rows = conn.execute("SELECT * FROM vehicles ORDER BY id").fetchall()
        conn.close()
        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "registration", "type", "capacity_kg", "capacity_m3",
                                 "max_speed_kmh", "cost_per_km", "driver_name", "status"])
                for row in rows:
                    writer.writerow([
                        row["id"], row["registration"], row["type"],
                        row["capacity_kg"], row["capacity_m3"],
                        row["max_speed_kmh"], row["cost_per_km"],
                        row["driver_name"], row["status"]
                    ])
            log_action("VEHICLE_EXPORT", f"{len(rows)} véhicules exportés vers {filepath}")
            show_toast(self.window(), f"{len(rows)} véhicules exportés", "success")
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'export", str(e))
