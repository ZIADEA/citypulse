import os
import csv
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFileDialog, QMessageBox, QTextEdit, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ..database.db_manager import get_connection
from .help_dialog import show_help


class ReportsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        _header = QHBoxLayout()
        title = QLabel("Génération de Rapports")
        title.setObjectName("heading")
        _header.addWidget(title)
        _header.addStretch()
        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "reports"))
        _header.addWidget(help_btn)
        layout.addLayout(_header)

        subtitle = QLabel("Exportez vos données et résultats dans différents formats")
        subtitle.setObjectName("subheading")
        layout.addWidget(subtitle)

        # Report types
        types_group = QGroupBox("Types de rapports")
        tl = QVBoxLayout(types_group)

        reports = [
            ("Feuille de route (par véhicule)", self._export_route_sheet),
            ("Rapport comparatif algorithmes", self._export_comparison),
            ("Rapport de tournée complet", self._export_tour_report),
            ("Journal des opérations (logs)", self._export_logs),
            ("Export clients (CSV)", self._export_clients_csv),
            ("Export véhicules (CSV)", self._export_vehicles_csv),
            ("Export complet BDD (JSON)", self._export_full_json),
        ]

        for label, handler in reports:
            btn = QPushButton(label)
            btn.setMinimumHeight(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            tl.addWidget(btn)

        layout.addWidget(types_group)

        # Preview area
        preview_group = QGroupBox("Apercu du rapport")
        pl = QVBoxLayout(preview_group)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("L'aperçu du rapport apparaîtra ici...")
        pl.addWidget(self.preview_text)
        layout.addWidget(preview_group, 1)

        # Export format
        format_bar = QHBoxLayout()
        format_bar.addWidget(QLabel("Format d'export :"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["CSV", "TXT", "JSON", "PDF"])
        format_bar.addWidget(self.format_combo)
        format_bar.addStretch()

        export_btn = QPushButton("Exporter")
        export_btn.setObjectName("primaryBtn")
        export_btn.clicked.connect(self._export_current)
        format_bar.addWidget(export_btn)
        layout.addLayout(format_bar)

    def _generate_comparison_text(self):
        conn = get_connection()
        results = conn.execute(
            "SELECT * FROM algo_results ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        conn.close()

        text = "=" * 60 + "\n"
        text += "  RAPPORT COMPARATIF — ALGORITHMES D'OPTIMISATION\n"
        text += f"  Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n"
        text += "=" * 60 + "\n\n"

        if not results:
            text += "Aucun résultat d'optimisation enregistré.\n"
            return text

        algo_data = {}
        for r in results:
            if r["algorithm"] not in algo_data:
                algo_data[r["algorithm"]] = r

        for algo, r in algo_data.items():
            text += f"- {algo}\n"
            text += f"  Distance totale  : {r['total_distance']:.2f} km\n"
            text += f"  Durée totale     : {r['total_duration']:.1f} min\n"
            text += f"  Coût total       : {r['total_cost']:.2f} €\n"
            text += f"  Clients          : {r['client_count']}\n"
            text += f"  Respect horaires : {r['respect_rate']:.1f}%\n"
            text += f"  Retard moyen     : {r['avg_delay']:.1f} min\n"
            text += f"  Temps CPU        : {r['cpu_time_ms']:.1f} ms\n"
            text += f"  Gain vs Glouton  : {r['gain_vs_greedy']:.1f}%\n"
            text += "-" * 40 + "\n"

        return text

    def _export_route_sheet(self):
        text = self._generate_comparison_text()
        self.preview_text.setPlainText(text)

    def _export_comparison(self):
        text = self._generate_comparison_text()
        self.preview_text.setPlainText(text)

    def _export_tour_report(self):
        self._export_comparison()

    def _export_logs(self):
        conn = get_connection()
        logs = conn.execute("SELECT * FROM logs ORDER BY created_at DESC LIMIT 100").fetchall()
        conn.close()
        text = "JOURNAL DES OPÉRATIONS\n" + "=" * 40 + "\n\n"
        for log in logs:
            text += f"[{log['created_at']}] [{log['level']}] {log['action']}"
            if log['details']:
                text += f" — {log['details']}"
            text += "\n"
        self.preview_text.setPlainText(text)

    def _export_clients_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Exporter clients", "clients.csv", "CSV (*.csv)")
        if not filepath:
            return
        conn = get_connection()
        rows = conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()
        conn.close()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "latitude", "longitude", "demand_kg", "ready_time", "due_time", "service_time", "priority", "type"])
            for r in rows:
                writer.writerow([r["id"], r["name"], r["latitude"], r["longitude"], r["demand_kg"], r["ready_time"], r["due_time"], r["service_time"], r["priority"], r["client_type"]])
        QMessageBox.information(self, "Export", f"{len(rows)} clients exportés vers {filepath}")
        log_action("EXPORT_CLIENTS", filepath)

    def _export_vehicles_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Exporter véhicules", "vehicules.csv", "CSV (*.csv)")
        if not filepath:
            return
        conn = get_connection()
        rows = conn.execute("SELECT * FROM vehicles").fetchall()
        conn.close()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "registration", "type", "capacity_kg", "capacity_m3", "max_speed_kmh", "cost_per_km", "status"])
            for r in rows:
                writer.writerow([r["id"], r["registration"], r["type"], r["capacity_kg"], r["capacity_m3"], r["max_speed_kmh"], r["cost_per_km"], r["status"]])
        QMessageBox.information(self, "Export", f"{len(rows)} véhicules exportés.")
        log_action("EXPORT_VEHICLES", filepath)

    def _export_full_json(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export JSON complet", "citypulse_export.json", "JSON (*.json)")
        if not filepath:
            return
        conn = get_connection()
        data = {
            "clients": [dict(r) for r in conn.execute("SELECT * FROM clients").fetchall()],
            "vehicles": [dict(r) for r in conn.execute("SELECT * FROM vehicles").fetchall()],
            "depots": [dict(r) for r in conn.execute("SELECT * FROM depots").fetchall()],
            "algo_results": [dict(r) for r in conn.execute("SELECT * FROM algo_results").fetchall()],
            "exported_at": datetime.now().isoformat(),
        }
        conn.close()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        QMessageBox.information(self, "Export", f"Données exportées vers {filepath}")
        log_action("EXPORT_FULL", filepath)

    def _export_current(self):
        fmt = self.format_combo.currentText()
        text = self.preview_text.toPlainText()
        if not text:
            QMessageBox.warning(self, "Erreur", "Aucun rapport à exporter. Générez d'abord un rapport.")
            return

        ext = {"CSV": "csv", "TXT": "txt", "JSON": "json", "PDF": "pdf"}.get(fmt, "txt")
        filepath, _ = QFileDialog.getSaveFileName(self, f"Exporter en {fmt}", f"rapport.{ext}", f"{fmt} (*.{ext})")
        if not filepath:
            return

        if fmt == "PDF":
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas
                c = canvas.Canvas(filepath, pagesize=A4)
                width, height = A4
                y = height - 50
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, y, "CityPulse Logistics — Rapport")
                y -= 30
                c.setFont("Helvetica", 10)
                for line in text.split("\n"):
                    if y < 50:
                        c.showPage()
                        y = height - 50
                        c.setFont("Helvetica", 10)
                    c.drawString(50, y, line[:100])
                    y -= 14
                c.save()
                QMessageBox.information(self, "Export PDF", f"Rapport exporté vers {filepath}")
            except ImportError:
                QMessageBox.warning(self, "Erreur", "reportlab non installé. Utilisez: pip install reportlab")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Export", f"Rapport exporté vers {filepath}")

        log_action("EXPORT_REPORT", f"Format: {fmt}, Fichier: {filepath}")

    def refresh_data(self):
        pass
