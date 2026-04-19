"""
CityPulse Logistics — Optimisation de Tournées Véhiculées (VRP)
Application desktop PyQt6 avec IA embarquée

Lancement : python main.py
Identifiants par défaut : admin / admin
"""
import sys
import os

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.ui.main_window import MainWindow
from app.ui.splash_screen import SplashScreen


def main():
    # High DPI support
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("CityPulse Logistics")
    app.setOrganizationName("CityPulse")
    app.setApplicationVersion("5.0")

    # Default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Splash screen
    splash = SplashScreen()

    def show_main():
        window = MainWindow()
        window.show()
        # Keep reference alive
        app._main_window = window

    splash.finished.connect(show_main)
    splash.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
