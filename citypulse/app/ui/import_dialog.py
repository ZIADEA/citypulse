"""
Dialogue de sélection de colonnes pour l'import CSV / XLS.

Affiche un aperçu des colonnes détectées dans le fichier et permet
à l'utilisateur de choisir lesquelles inclure avant l'import.
"""

import csv
import os
import openpyxl

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt


def _read_headers_and_preview(filepath: str):
    """Return (headers: list[str], preview_rows: list[dict]) from CSV or XLS."""
    ext = os.path.splitext(filepath)[1].lower()
    headers = []
    preview = []

    if ext in (".xls", ".xlsx"):
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        raw = next(rows_iter, None)
        if raw:
            headers = [str(h).strip() if h else f"col{i}" for i, h in enumerate(raw)]
        for i, vals in enumerate(rows_iter):
            if i >= 5:
                break
            preview.append(dict(zip(headers, vals)))
        wb.close()
    else:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            for i, row in enumerate(reader):
                if i >= 5:
                    break
                preview.append(row)

    return headers, preview


class ColumnSelectionDialog(QDialog):
    """Dialogue permettant de sélectionner les colonnes à importer."""

    def __init__(self, parent, filepath: str):
        super().__init__(parent)
        self.filepath = filepath
        self.setWindowTitle("Sélection des colonnes")
        self.setMinimumSize(520, 400)
        self.resize(580, 480)
        self.setStyleSheet(
            "QDialog { background-color: #ffffff; }"
            "QLabel#dlgTitle { font-size: 16px; font-weight: bold; color: #1a1a1a; }"
            "QLabel#previewLabel { font-size: 11px; color: #888; }"
            "QCheckBox { font-size: 13px; padding: 3px 0; }"
        )

        self.selected_columns: list[str] = []
        self._checkboxes: list[QCheckBox] = []

        self._headers, self._preview = _read_headers_and_preview(filepath)

        self._setup_ui()

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(10)

        # Title
        fname = os.path.basename(self.filepath)
        title = QLabel(f"Colonnes détectées — {fname}")
        title.setObjectName("dlgTitle")
        layout.addWidget(title)

        info = QLabel(f"{len(self._headers)} colonnes trouvées. Cochez celles à importer.")
        info.setObjectName("previewLabel")
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #d8dce3;")
        layout.addWidget(sep)

        # Select-all toggle
        toggle_row = QHBoxLayout()
        self._select_all_cb = QCheckBox("Tout sélectionner")
        self._select_all_cb.setChecked(True)
        self._select_all_cb.setStyleSheet("font-weight: bold;")
        self._select_all_cb.stateChanged.connect(self._on_toggle_all)
        toggle_row.addWidget(self._select_all_cb)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        # Scrollable column list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #d8dce3; border-radius: 4px; }")
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.setSpacing(4)

        for col in self._headers:
            preview_vals = []
            for row in self._preview[:3]:
                v = row.get(col, "")
                if v is not None:
                    preview_vals.append(str(v)[:20])
            hint = ", ".join(preview_vals) if preview_vals else ""
            cb = QCheckBox(col)
            cb.setChecked(True)
            if hint:
                cb.setToolTip(f"Aperçu : {hint}")
            cb.stateChanged.connect(self._update_toggle)
            self._checkboxes.append(cb)
            inner_layout.addWidget(cb)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Importer")
        ok_btn.setFixedWidth(100)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setObjectName("primaryBtn")
        ok_btn.clicked.connect(self._accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    # ── Slots ───────────────────────────────────────────────────

    def _on_toggle_all(self, state):
        checked = state == Qt.CheckState.Checked.value
        for cb in self._checkboxes:
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)

    def _update_toggle(self):
        all_checked = all(cb.isChecked() for cb in self._checkboxes)
        self._select_all_cb.blockSignals(True)
        self._select_all_cb.setChecked(all_checked)
        self._select_all_cb.blockSignals(False)

    def _accept(self):
        self.selected_columns = [cb.text() for cb in self._checkboxes if cb.isChecked()]
        if not self.selected_columns:
            QMessageBox.warning(self, "Aucune colonne", "Sélectionnez au moins une colonne.")
            return
        self.accept()
