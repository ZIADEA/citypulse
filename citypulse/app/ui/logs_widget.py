from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QDateEdit, QLineEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from ..database.db_manager import get_connection
from .help_dialog import show_help


class LogsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        _header = QHBoxLayout()
        title = QLabel("Journal des Op\u00e9rations")
        title.setObjectName("heading")
        _header.addWidget(title)
        _header.addStretch()
        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "logs"))
        _header.addWidget(help_btn)
        layout.addLayout(_header)

        # Filters
        filter_bar = QHBoxLayout()
        self.level_filter = QComboBox()
        self.level_filter.addItems(["Tous", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_filter.currentTextChanged.connect(lambda: self.refresh_data())
        filter_bar.addWidget(QLabel("Niveau :"))
        filter_bar.addWidget(self.level_filter)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.setMaximumWidth(250)
        self.search_input.textChanged.connect(self._filter_table)
        filter_bar.addWidget(self.search_input)

        filter_bar.addStretch()

        refresh_btn = QPushButton("Rafraîchir")
        refresh_btn.clicked.connect(self.refresh_data)
        filter_bar.addWidget(refresh_btn)

        self.count_label = QLabel("0 entrées")
        self.count_label.setStyleSheet("color: #6c6c6c;")
        filter_bar.addWidget(self.count_label)
        layout.addLayout(filter_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Date/Heure", "Niveau", "Action", "Détails", "Utilisateur"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultSectionSize(110)
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(True)
        layout.addWidget(self.table)

    def refresh_data(self):
        level = self.level_filter.currentText()
        conn = get_connection()
        if level == "Tous":
            rows = conn.execute("SELECT * FROM logs ORDER BY created_at DESC LIMIT 500").fetchall()
        else:
            rows = conn.execute("SELECT * FROM logs WHERE level=? ORDER BY created_at DESC LIMIT 500",
                                (level,)).fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(row["created_at"][:19] if row["created_at"] else "—"))
            level_item = QTableWidgetItem(row["level"])
            if row["level"] == "ERROR":
                level_item.setForeground(Qt.GlobalColor.red)
            elif row["level"] == "WARNING":
                level_item.setForeground(Qt.GlobalColor.yellow)
            elif row["level"] == "CRITICAL":
                level_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(r, 1, level_item)
            self.table.setItem(r, 2, QTableWidgetItem(row["action"]))
            self.table.setItem(r, 3, QTableWidgetItem(row["details"] or ""))
            self.table.setItem(r, 4, QTableWidgetItem(str(row["user_id"] or "—")))

        self.count_label.setText(f"{len(rows)} entrées")

    def _filter_table(self, text):
        for r in range(self.table.rowCount()):
            show = False
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item and text.lower() in item.text().lower():
                    show = True
                    break
            self.table.setRowHidden(r, not show)
