from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QDialog,
    QFormLayout, QDoubleSpinBox, QSpinBox, QTextEdit, QMessageBox,
    QFileDialog, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import csv
import os
import openpyxl
from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help
from .import_dialog import ColumnSelectionDialog
from .toast import show_toast
from .empty_state import EmptyState


class ClientDialog(QDialog):
    def __init__(self, parent=None, client=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Modifier client" if client else "Nouveau client")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(12)

        self.name_input = QLineEdit(self.client["name"] if self.client else "")
        self.address_input = QLineEdit(self.client["address"] if self.client and self.client["address"] else "")
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)
        self.lat_input.setDecimals(6)
        self.lat_input.setValue(self.client["latitude"] if self.client else 33.5731)
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180, 180)
        self.lon_input.setDecimals(6)
        self.lon_input.setValue(self.client["longitude"] if self.client else -7.5898)
        self.demand_input = QDoubleSpinBox()
        self.demand_input.setRange(0, 99999)
        self.demand_input.setValue(self.client["demand_kg"] if self.client else 0)
        self.volume_input = QDoubleSpinBox()
        self.volume_input.setRange(0, 9999)
        self.volume_input.setValue(self.client["demand_m3"] if self.client else 0)
        self.ready_input = QSpinBox()
        self.ready_input.setRange(0, 1440)
        self.ready_input.setValue(self.client["ready_time"] if self.client else 0)
        self.due_input = QSpinBox()
        self.due_input.setRange(0, 1440)
        self.due_input.setValue(self.client["due_time"] if self.client else 1440)
        self.service_input = QSpinBox()
        self.service_input.setRange(0, 300)
        self.service_input.setValue(self.client["service_time"] if self.client else 10)
        self.priority_input = QComboBox()
        self.priority_input.addItems(["1 - Très haute", "2 - Haute", "3 - Normale", "4 - Basse", "5 - Très basse"])
        if self.client:
            self.priority_input.setCurrentIndex(self.client["priority"] - 1)
        else:
            self.priority_input.setCurrentIndex(2)
        self.type_input = QComboBox()
        self.type_input.addItems(["standard", "prioritaire", "occasionnel", "ponctuel"])
        if self.client and self.client["client_type"]:
            idx = self.type_input.findText(self.client["client_type"])
            if idx >= 0:
                self.type_input.setCurrentIndex(idx)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        if self.client and self.client["instructions"]:
            self.notes_input.setPlainText(self.client["instructions"])

        layout.addRow("Nom *", self.name_input)
        layout.addRow("Adresse", self.address_input)
        layout.addRow("Latitude", self.lat_input)
        layout.addRow("Longitude", self.lon_input)
        layout.addRow("Demande (kg)", self.demand_input)
        layout.addRow("Volume (m³)", self.volume_input)
        layout.addRow("Heure début (min)", self.ready_input)
        layout.addRow("Heure fin (min)", self.due_input)
        layout.addRow("Temps service (min)", self.service_input)
        layout.addRow("Priorité", self.priority_input)
        layout.addRow("Type", self.type_input)
        layout.addRow("Instructions", self.notes_input)

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
            "demand_kg": self.demand_input.value(),
            "demand_m3": self.volume_input.value(),
            "ready_time": self.ready_input.value(),
            "due_time": self.due_input.value(),
            "service_time": self.service_input.value(),
            "priority": self.priority_input.currentIndex() + 1,
            "client_type": self.type_input.currentText(),
            "instructions": self.notes_input.toPlainText().strip(),
        }


class ClientsWidget(QWidget):
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
        title = QLabel("Gestion des Clients")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.setMaximumWidth(250)
        self.search_input.textChanged.connect(self._filter_table)
        header.addWidget(self.search_input)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tous", "Prioritaire", "Standard", "Occasionnel"])
        self.filter_combo.currentTextChanged.connect(lambda: self.refresh_data())
        header.addWidget(self.filter_combo)

        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "clients"))
        header.addWidget(help_btn)

        layout.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("  Ajouter")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_client)
        import_btn = QPushButton("  Importer")
        import_btn.setToolTip("Importer depuis CSV ou Excel (XLS/XLSX)")
        import_btn.clicked.connect(self._import_data)
        export_btn = QPushButton("  Exporter CSV")
        export_btn.clicked.connect(self._export_csv)
        purge_btn = QPushButton("  Tout supprimer")
        purge_btn.setToolTip("Supprimer tous les clients importés")
        purge_btn.clicked.connect(self._purge_data)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(import_btn)
        toolbar.addWidget(export_btn)
        toolbar.addWidget(purge_btn)
        toolbar.addStretch()

        self.count_label = QLabel("0 clients")
        self.count_label.setStyleSheet("color: #6c6c6c; font-size: 12px;")
        toolbar.addWidget(self.count_label)
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nom", "Latitude", "Longitude", "Demande (kg)",
            "Début", "Fin", "Service", "Priorité", "Type", "Actions"
        ])        # Tooltips documentation colonnes
        _tips = [
            "Identifiant unique du client",
            "Nom ou raison sociale du client",
            "Coordonn\u00e9e GPS latitude (degr\u00e9s d\u00e9cimaux)",
            "Coordonn\u00e9e GPS longitude (degr\u00e9s d\u00e9cimaux)",
            "Quantit\u00e9 \u00e0 livrer en kilogrammes",
            "Heure la plus t\u00f4t pour livrer (minutes depuis minuit)",
            "Heure limite de livraison (minutes depuis minuit)",
            "Dur\u00e9e du service chez le client (minutes)",
            "Niveau de priorit\u00e9 (1 = urgente, 5 = basse)",
            "Type de client (standard, prioritaire, fragile)",
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
            title="Aucun client",
            subtitle="Importez un fichier CSV ou Excel, ou ajoutez manuellement vos clients.",
            action_text="Importer des clients",
            action_callback=self._import_data,
        )
        self._stack.addWidget(self._empty)
        layout.addWidget(self._stack)

        # Inline editing signals
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self._col_db_map = {
            1: "name", 2: "latitude", 3: "longitude", 4: "demand_kg",
            5: "ready_time", 6: "due_time", 7: "service_time",
            8: "priority", 9: "client_type"
        }
        self._editing_enabled = False

    def refresh_data(self):
        conn = get_connection()
        filter_type = self.filter_combo.currentText().lower() if hasattr(self, 'filter_combo') else "tous"
        if filter_type == "tous":
            rows = conn.execute("SELECT * FROM clients WHERE archived=0 ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM clients WHERE archived=0 AND client_type=? ORDER BY id",
                                (filter_type,)).fetchall()
        conn.close()

        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            id_item = QTableWidgetItem(str(row["id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, QTableWidgetItem(row["name"]))
            self.table.setItem(r, 2, QTableWidgetItem(f"{row['latitude']:.4f}"))
            self.table.setItem(r, 3, QTableWidgetItem(f"{row['longitude']:.4f}"))
            self.table.setItem(r, 4, QTableWidgetItem(str(row["demand_kg"])))
            self.table.setItem(r, 5, QTableWidgetItem(str(row["ready_time"])))
            self.table.setItem(r, 6, QTableWidgetItem(str(row["due_time"])))
            self.table.setItem(r, 7, QTableWidgetItem(str(row["service_time"])))
            self.table.setItem(r, 8, QTableWidgetItem(str(row["priority"])))
            self.table.setItem(r, 9, QTableWidgetItem(row["client_type"] or "standard"))

            # Action buttons
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(55, 28)
            edit_btn.setToolTip("Modifier")
            edit_btn.clicked.connect(lambda _, rid=row["id"]: self._edit_client(rid))
            del_btn = QPushButton("Suppr")
            del_btn.setFixedSize(60, 28)
            del_btn.setToolTip("Supprimer")
            del_btn.clicked.connect(lambda _, rid=row["id"]: self._delete_client(rid))
            dup_btn = QPushButton("Dupl")
            dup_btn.setFixedSize(55, 28)
            dup_btn.setToolTip("Dupliquer")
            dup_btn.clicked.connect(lambda _, rid=row["id"]: self._duplicate_client(rid))
            al.addWidget(edit_btn)
            al.addWidget(del_btn)
            al.addWidget(dup_btn)
            self.table.setCellWidget(r, 10, actions)

        self.table.blockSignals(False)
        self._editing_enabled = True
        self.count_label.setText(f"{len(rows)} clients")
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
        client_id = int(id_item.text())
        field = self._col_db_map[col]
        value = self.table.item(row, col).text()
        try:
            if field in ("latitude", "longitude", "demand_kg"):
                value = float(value)
            elif field in ("ready_time", "due_time", "service_time", "priority"):
                value = int(float(value))
            conn = get_connection()
            conn.execute(
                f"UPDATE clients SET {field}=?, updated_at=datetime('now') WHERE id=?",
                (value, client_id)
            )
            conn.commit()
            conn.close()
            log_action("CLIENT_INLINE_EDIT", f"Client #{client_id} {field}='{value}'")
        except (ValueError, Exception) as e:
            QMessageBox.warning(self, "Erreur de saisie", f"Valeur invalide pour {field}: {e}")
            self.refresh_data()

    def _add_client(self):
        dlg = ClientDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Erreur", "Le nom est obligatoire.")
                return
            conn = get_connection()
            conn.execute(
                """INSERT INTO clients (name, address, latitude, longitude, demand_kg, demand_m3,
                   ready_time, due_time, service_time, priority, client_type, instructions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["name"], data["address"], data["latitude"], data["longitude"],
                 data["demand_kg"], data["demand_m3"], data["ready_time"], data["due_time"],
                 data["service_time"], data["priority"], data["client_type"], data["instructions"])
            )
            conn.commit()
            conn.close()
            log_action("CLIENT_CREATE", f"Client '{data['name']}' créé")
            self.refresh_data()

    def _edit_client(self, client_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        conn.close()
        if not row:
            return
        dlg = ClientDialog(self, dict(row))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            conn = get_connection()
            conn.execute(
                """UPDATE clients SET name=?, address=?, latitude=?, longitude=?, demand_kg=?,
                   demand_m3=?, ready_time=?, due_time=?, service_time=?, priority=?,
                   client_type=?, instructions=?, updated_at=datetime('now') WHERE id=?""",
                (data["name"], data["address"], data["latitude"], data["longitude"],
                 data["demand_kg"], data["demand_m3"], data["ready_time"], data["due_time"],
                 data["service_time"], data["priority"], data["client_type"],
                 data["instructions"], client_id)
            )
            conn.commit()
            conn.close()
            log_action("CLIENT_UPDATE", f"Client #{client_id} modifié")
            self.refresh_data()

    def _delete_client(self, client_id):
        reply = QMessageBox.question(
            self, "Confirmer", "Supprimer ce client (archivage) ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("UPDATE clients SET archived=1 WHERE id=?", (client_id,))
            conn.commit()
            conn.close()
            log_action("CLIENT_DELETE", f"Client #{client_id} archivé")
            self.refresh_data()

    def _duplicate_client(self, client_id):
        conn = get_connection()
        row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        if row:
            conn.execute(
                """INSERT INTO clients (name, address, latitude, longitude, demand_kg, demand_m3,
                   ready_time, due_time, service_time, priority, client_type, instructions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"{row['name']} (copie)", row["address"], row["latitude"], row["longitude"],
                 row["demand_kg"], row["demand_m3"], row["ready_time"], row["due_time"],
                 row["service_time"], row["priority"], row["client_type"], row["instructions"])
            )
            conn.commit()
            log_action("CLIENT_DUPLICATE", f"Client #{client_id} dupliqué")
        conn.close()
        self.refresh_data()

    def _import_data(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Importer Clients", "",
            "Tous les formats (*.csv *.xls *.xlsx);;CSV (*.csv);;Excel (*.xls *.xlsx)"
        )
        if not filepath:
            return
        # Column selection dialog
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
            """Return value from row only if the matching key is in selected columns."""
            for k in keys:
                if k in row and (selected is None or k in selected):
                    v = row[k]
                    if v is not None:
                        return v
            return default

        for vals in rows_iter:
            row = dict(zip(headers, vals))
            # Auto-detect real-world dataset (CUSTOMER_CODE format)
            if "CUSTOMER_CODE" in headers:
                name = str(_get(row, "CUSTOMER_CODE", "CUSTOMER_NAME", default=f"Client {count}"))
                lat = float(_get(row, "LATITUDE", "LAT", "YCOORD", default=33.5731))
                lon = float(_get(row, "LONGITUDE", "LON", "XCOORD", default=-7.5898))
                demand = float(_get(row, "DEMAND_KG", "DEMAND", "QUANTITY_KG", default=0))
                ready = int(float(_get(row, "READY_TIME", "TIME_FROM", default=0)))
                due = int(float(_get(row, "DUE_TIME", "TIME_TO", default=1440)))
                service = int(float(_get(row, "SERVICE_TIME", "UNLOADING_TIME_MIN", default=10)))
                conn.execute(
                    """INSERT INTO clients (name, latitude, longitude, demand_kg,
                       ready_time, due_time, service_time) VALUES (?,?,?,?,?,?,?)""",
                    (name, lat, lon, demand, ready, due, service)
                )
            # Solomon format
            elif "CUST NO." in headers or "CUST_NO" in headers:
                cust_no = int(_get(row, "CUST NO.", "CUST_NO", default=0))
                x = float(_get(row, "XCOORD.", "XCOORD", default=0))
                y = float(_get(row, "YCOORD.", "YCOORD", default=0))
                demand = float(_get(row, "DEMAND", default=0))
                ready = int(float(_get(row, "READY TIME", "READY_TIME", default=0)))
                due = int(float(_get(row, "DUE DATE", "DUE_TIME", default=1440)))
                service = int(float(_get(row, "SERVICE TIME", "SERVICE_TIME", default=10)))
                lat = 33.5731 + (y - 50) * 0.01
                lon = -7.5898 + (x - 50) * 0.01
                if demand == 0 and cust_no <= 1:
                    count += 1
                    continue
                conn.execute(
                    """INSERT INTO clients (cust_no, name, latitude, longitude, demand_kg,
                       ready_time, due_time, service_time) VALUES (?,?,?,?,?,?,?,?)""",
                    (cust_no, f"Client {cust_no}", lat, lon, demand, ready, due, service)
                )
            else:
                name = str(_get(row, "name", "nom", default=f"Client {count}"))
                lat = float(_get(row, "latitude", "lat", default=33.5731))
                lon = float(_get(row, "longitude", "lon", default=-7.5898))
                demand = float(_get(row, "demand_kg", "demand", default=0))
                conn.execute(
                    "INSERT INTO clients (name, latitude, longitude, demand_kg) VALUES (?,?,?,?)",
                    (name, lat, lon, demand)
                )
            count += 1
        conn.commit()
        conn.close()
        wb.close()
        log_action("CLIENT_IMPORT_XLS", f"{count} clients importés depuis {filepath}")
        show_toast(self.window(), f"{count} clients importés depuis Excel", "success")
        self.refresh_data()

    def _import_csv(self, filepath=None, selected=None):
        if filepath is None:
            filepath, _ = QFileDialog.getOpenFileName(self, "Importer CSV", "", "CSV (*.csv);;Tous (*)")
            if not filepath:
                return

        def _get(row, *keys, default=None):
            for k in keys:
                if k in row and (selected is None or k in selected):
                    v = row[k]
                    if v is not None and v != "":
                        return v
            return default

        conn = get_connection()
        count = 0
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Auto-detect Solomon format
                if "CUST NO." in row or "CUST_NO" in row:
                    cust_no = int(_get(row, "CUST NO.", "CUST_NO", default=0))
                    x = float(_get(row, "XCOORD.", "XCOORD", default=0))
                    y = float(_get(row, "YCOORD.", "YCOORD", default=0))
                    demand = float(_get(row, "DEMAND", default=0))
                    ready = int(float(_get(row, "READY TIME", "READY_TIME", default=0)))
                    due = int(float(_get(row, "DUE DATE", "DUE_TIME", default=1440)))
                    service = int(float(_get(row, "SERVICE TIME", "SERVICE_TIME", default=10)))
                    lat = 33.5731 + (y - 50) * 0.01
                    lon = -7.5898 + (x - 50) * 0.01
                    if demand == 0 and cust_no <= 1:
                        count += 1
                        continue
                    conn.execute(
                        """INSERT INTO clients (cust_no, name, latitude, longitude, demand_kg,
                           ready_time, due_time, service_time) VALUES (?,?,?,?,?,?,?,?)""",
                        (cust_no, f"Client {cust_no}", lat, lon, demand, ready, due, service)
                    )
                else:
                    name = _get(row, "name", "nom", default=f"Client {count}")
                    lat = float(_get(row, "latitude", "lat", default=33.5731))
                    lon = float(_get(row, "longitude", "lon", default=-7.5898))
                    demand = float(_get(row, "demand_kg", "demand", default=0))
                    conn.execute(
                        "INSERT INTO clients (name, latitude, longitude, demand_kg) VALUES (?,?,?,?)",
                        (name, lat, lon, demand)
                    )
                count += 1
        conn.commit()
        conn.close()
        log_action("CLIENT_IMPORT", f"{count} clients importés depuis {filepath}")
        show_toast(self.window(), f"{count} clients importés", "success")
        self.refresh_data()

    def _purge_data(self):
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
        conn.close()
        if count == 0:
            QMessageBox.information(self, "Purge", "Aucun client à supprimer.")
            return
        reply = QMessageBox.warning(
            self, "Supprimer tous les clients",
            f"Voulez-vous vraiment supprimer les {count} clients ?\n\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM clients")
            conn.commit()
            conn.close()
            log_action("CLIENT_PURGE", f"{count} clients supprimés")
            show_toast(self.window(), f"{count} clients supprimés", "success")
            self.refresh_data()

    def _export_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Exporter CSV", "clients.csv", "CSV (*.csv)")
        if not filepath:
            return
        conn = get_connection()
        rows = conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()
        conn.close()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "latitude", "longitude", "demand_kg",
                             "ready_time", "due_time", "service_time", "priority", "type"])
            for row in rows:
                writer.writerow([row["id"], row["name"], row["latitude"], row["longitude"],
                                 row["demand_kg"], row["ready_time"], row["due_time"],
                                 row["service_time"], row["priority"], row["client_type"]])
        log_action("CLIENT_EXPORT", f"Export CSV vers {filepath}")
        show_toast(self.window(), f"{len(rows)} clients exportés", "success")
