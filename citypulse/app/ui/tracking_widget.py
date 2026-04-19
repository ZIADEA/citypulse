from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QGridLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from ..database.db_manager import get_connection
from .help_dialog import show_help


class TrackingWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.simulation_active = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Suivi en Temps Réel (Simulation)")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()

        self.sim_btn = QPushButton("Démarrer simulation")
        self.sim_btn.setObjectName("primaryBtn")
        self.sim_btn.clicked.connect(self._toggle_simulation)
        header.addWidget(self.sim_btn)

        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "tracking"))
        header.addWidget(help_btn)

        layout.addLayout(header)

        # Status cards
        cards = QGridLayout()
        cards.setSpacing(12)

        self.card_transit = self._make_card("En transit", "0", "#3498db")
        self.card_delivered = self._make_card("Livrés", "0", "#2ecc71")
        self.card_delayed = self._make_card("En retard", "0", "#e74c3c")
        self.card_pending = self._make_card("En attente", "0", "#f39c12")

        cards.addWidget(self.card_transit, 0, 0)
        cards.addWidget(self.card_delivered, 0, 1)
        cards.addWidget(self.card_delayed, 0, 2)
        cards.addWidget(self.card_pending, 0, 3)
        layout.addLayout(cards)

        # Vehicle status table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Véhicule", "Statut", "Prochain arrêt", "ETA", "Livraisons",
            "Progression", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.horizontalHeader().setMinimumSectionSize(50)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        layout.addWidget(self.table)

        # Notifications area
        notif_label = QLabel("Alertes et Notifications")
        notif_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(notif_label)

        self.notif_table = QTableWidget()
        self.notif_table.setColumnCount(4)
        self.notif_table.setHorizontalHeaderLabels(["Heure", "Type", "Message", "Statut"])
        self.notif_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.notif_table.setMaximumHeight(200)
        layout.addWidget(self.notif_table)

    def _make_card(self, title, value, accent_color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1px solid #d8dce3;
                border-radius: 10px;
                border-left: 4px solid {accent_color};
                padding: 12px;
            }}
        """)
        fl = QVBoxLayout(frame)
        fl.setSpacing(4)
        tl = QLabel(title.upper())
        tl.setStyleSheet(f"color: {accent_color}; font-size: 10px; font-weight: bold; border: none;")
        fl.addWidget(tl)
        vl = QLabel(value)
        vl.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        vl.setStyleSheet("color: #2c2c2c; border: none;")
        vl.setObjectName("value")
        fl.addWidget(vl)
        return frame

    def _toggle_simulation(self):
        if self.simulation_active:
            self.simulation_active = False
            self.sim_btn.setText("Démarrer simulation")
            self._sim_timer.stop()
        else:
            self.simulation_active = True
            self.sim_btn.setText("Arrêter simulation")
            self._sim_tick = 0
            self._run_simulation()
            self._sim_timer = QTimer(self)
            self._sim_timer.timeout.connect(self._advance_simulation)
            self._sim_timer.start(2000)

    def _run_simulation(self):
        conn = get_connection()
        self._vehicles = conn.execute("SELECT * FROM vehicles").fetchall()
        conn.close()
        self._update_simulation_ui()

    def _advance_simulation(self):
        self._sim_tick += 1
        self._update_simulation_ui()

    def _update_simulation_ui(self):
        import random
        vehicles = self._vehicles
        tick = getattr(self, '_sim_tick', 0)
        total_deliveries = 8

        self.table.setRowCount(len(vehicles))
        delivered_count = 0
        delayed_count = 0
        transit_count = 0
        pending_count = 0

        for i, v in enumerate(vehicles):
            self.table.setItem(i, 0, QTableWidgetItem(v["registration"] or f"V-{v['id']}"))

            # Simulate progress per vehicle
            base_progress = min(100, (tick * 12 + i * 8) % 120)
            delivered_i = int(base_progress / 100 * total_deliveries)
            remaining = total_deliveries - delivered_i

            if base_progress >= 100:
                status = "Terminé"
                delivered_count += 1
                eta = "—"
            elif base_progress > 0:
                is_delayed = (i + tick) % 5 == 0
                if is_delayed:
                    status = "En retard"
                    delayed_count += 1
                else:
                    status = "En transit"
                    transit_count += 1
                eta = f"~{max(1, 30 - tick * 2 + i * 3)} min"
            else:
                status = "En attente"
                pending_count += 1
                eta = "—"

            status_item = QTableWidgetItem(status)
            if status == "En retard":
                status_item.setForeground(QColor("#e74c3c") if hasattr(self, '_use_color') else QColor("#e74c3c"))
            elif status == "Terminé":
                status_item.setForeground(QColor("#2ecc71"))
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, QTableWidgetItem(f"Client {delivered_i + 1}" if status != "Terminé" else "—"))
            self.table.setItem(i, 3, QTableWidgetItem(eta))
            self.table.setItem(i, 4, QTableWidgetItem(f"{delivered_i}/{total_deliveries}"))

            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(min(base_progress, 100))
            if base_progress >= 100:
                progress.setStyleSheet("QProgressBar::chunk { background: #2ecc71; }")
            self.table.setCellWidget(i, 5, progress)

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(2, 2, 2, 2)
            mark_btn = QPushButton("OK")
            mark_btn.setFixedSize(44, 26)
            mark_btn.setToolTip("Marquer livré")
            fail_btn = QPushButton("X")
            fail_btn.setFixedSize(44, 26)
            fail_btn.setToolTip("Livraison échouée")
            al.addWidget(mark_btn)
            al.addWidget(fail_btn)
            self.table.setCellWidget(i, 6, actions)

        # Update cards
        self.card_transit.findChild(QLabel, "value").setText(str(transit_count))
        self.card_delivered.findChild(QLabel, "value").setText(str(delivered_count))
        self.card_delayed.findChild(QLabel, "value").setText(str(delayed_count))
        self.card_pending.findChild(QLabel, "value").setText(str(pending_count))

        # Live notifications
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        notifs = []
        if delayed_count > 0:
            notifs.append((now, "Retard", f"{delayed_count} véhicule(s) en retard", "Actif"))
        if delivered_count > 0:
            notifs.append((now, "Livraison", f"{delivered_count} véhicule(s) ont terminé", "OK"))
        if transit_count > 0:
            notifs.append((now, "Info", f"{transit_count} véhicule(s) en transit", "OK"))
        self.notif_table.setRowCount(len(notifs))
        for i, (time, ntype, msg, status) in enumerate(notifs):
            self.notif_table.setItem(i, 0, QTableWidgetItem(time))
            type_item = QTableWidgetItem(ntype)
            if ntype == "Retard":
                type_item.setForeground(QColor("#e74c3c"))
            elif ntype == "Livraison":
                type_item.setForeground(QColor("#2ecc71"))
            self.notif_table.setItem(i, 1, type_item)
            self.notif_table.setItem(i, 2, QTableWidgetItem(msg))
            self.notif_table.setItem(i, 3, QTableWidgetItem(status))

    def refresh_data(self):
        if self.simulation_active:
            self._run_simulation()
