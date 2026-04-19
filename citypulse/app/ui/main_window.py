from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QStatusBar, QMessageBox, QFrame, QScrollArea,
    QApplication, QToolBar, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QIcon, QAction

from .styles import DARK_STYLE, LIGHT_STYLE, REAL_DARK_STYLE
from .login_widget import LoginWidget
from .copilot_widget import CopilotDockWidget
from .dashboard_widget import DashboardWidget
from .clients_widget import ClientsWidget
from .vehicles_widget import VehiclesWidget
from .depots_widget import DepotsWidget
from .optimization_widget import OptimizationWidget
from .map_widget import MapWidget
from .translation_widget import TranslationWidget
from .reports_widget import ReportsWidget
from .settings_widget import SettingsWidget
from .scenarios_widget import ScenariosWidget
from .tracking_widget import TrackingWidget
from .logs_widget import LogsWidget
from .help_dialog import show_help
from .toast import show_toast
from ..database.db_manager import init_database, log_action, save_user_session, get_user_session, get_connection


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CityPulse Logistics — Optimisation de Tournées")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        self.current_user = None
        self.current_theme = "light"

        init_database()
        self._apply_theme("light")
        self._show_login()
        self._setup_shortcuts()

    def _apply_theme(self, theme):
        self.current_theme = theme
        if theme == "dark":
            self.setStyleSheet(REAL_DARK_STYLE)
        else:
            self.setStyleSheet(LIGHT_STYLE)

    def _show_login(self):
        self.login_widget = LoginWidget()
        self.login_widget.login_success.connect(self._on_login)
        self.setCentralWidget(self.login_widget)
        self.statusBar().showMessage("Veuillez vous connecter")

    def _on_login(self, user):
        self.current_user = user
        log_action("SESSION_START", f"Session démarrée pour {user['username']}", user_id=user["id"])
        if user.get("theme"):
            self._apply_theme(user["theme"])
        self._build_main_ui()
        # Welcome toast after UI is built
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(600, lambda: self.notify(
            f"Bienvenue, {user['full_name']} — session active", "info"
        ))

    def _build_main_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Top Header Bar (e-Prelude style) ──
        header_bar = QFrame()
        header_bar.setObjectName("headerBar")
        header_bar.setFixedHeight(36)
        hbar_layout = QHBoxLayout(header_bar)
        hbar_layout.setContentsMargins(12, 0, 12, 0)
        hbar_layout.setSpacing(0)

        # App title
        title_label = QLabel("CityPulse Logistics")
        title_label.setObjectName("appTitle")
        hbar_layout.addWidget(title_label)

        hbar_layout.addStretch()

        # Right side: user info + copilot + logout
        user_lbl = QLabel(f"{self.current_user['full_name']}  |  {self.current_user['role'].capitalize()}")
        user_lbl.setObjectName("headerUser")
        hbar_layout.addWidget(user_lbl)

        copilot_btn = QPushButton("Copilot IA")
        copilot_btn.setObjectName("headerBtn")
        copilot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copilot_btn.setToolTip("Ouvrir / Fermer l'assistant IA (Ctrl+Shift+C)")
        copilot_btn.clicked.connect(self._toggle_copilot)
        hbar_layout.addWidget(copilot_btn)

        guide_btn = QPushButton("Guide")
        guide_btn.setObjectName("headerBtn")
        guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        guide_btn.setToolTip("Guide complet d'utilisation de CityPulse")
        guide_btn.clicked.connect(lambda: show_help(self, "guide"))
        hbar_layout.addWidget(guide_btn)

        about_btn = QPushButton("A propos")
        about_btn.setObjectName("headerBtn")
        about_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        about_btn.setToolTip("Informations sur CityPulse Logistics")
        about_btn.clicked.connect(self._show_about)
        hbar_layout.addWidget(about_btn)

        logout_btn = QPushButton("Déconnexion")
        logout_btn.setObjectName("headerBtnDanger")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self._logout)
        hbar_layout.addWidget(logout_btn)

        main_layout.addWidget(header_bar)

        # ── Navigation Tab Bar (Prelude / Minitab inspired) ──
        nav_bar = QFrame()
        nav_bar.setObjectName("navBar")
        nav_bar.setFixedHeight(34)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 0, 8, 0)
        nav_layout.setSpacing(1)

        self.nav_buttons = []
        _shortcuts = {0:"Ctrl+1", 1:"Ctrl+2", 2:"Ctrl+3", 3:"Ctrl+4",
                      4:"Ctrl+5", 5:"Ctrl+6", 6:"Ctrl+7", 7:"Ctrl+8", 9:"Ctrl+9"}
        nav_items = [
            ("Dashboard",        0),
            ("Clients",          1),
            ("Véhicules",        2),
            ("Dépôts",           3),
            ("Optimisation",     4),
            ("Carte",            5),
            ("Suivi",            6),
            ("Scénarios",        7),
            ("Traduction",       8),
            ("Rapports",         9),
            ("Journal",         10),
            ("Paramètres",      11),
        ]

        for text, idx in nav_items:
            shortcut_hint = _shortcuts.get(idx, "")
            tooltip = f"{text} ({shortcut_hint})" if shortcut_hint else text
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, i=idx: self._nav_to(i))
            nav_layout.addWidget(btn)
            self.nav_buttons.append((btn, idx))

        nav_layout.addStretch()
        main_layout.addWidget(nav_bar)

        # ── Content Stack ──
        self.stack = QStackedWidget()
        self.dashboard_w = DashboardWidget(self)
        self.clients_w = ClientsWidget(self)
        self.vehicles_w = VehiclesWidget(self)
        self.depots_w = DepotsWidget(self)
        self.optimization_w = OptimizationWidget(self)
        self.map_w = MapWidget(self)
        self.tracking_w = TrackingWidget(self)
        self.scenarios_w = ScenariosWidget(self)
        self.translation_w = TranslationWidget(self)
        self.reports_w = ReportsWidget(self)
        self.logs_w = LogsWidget(self)
        self.settings_w = SettingsWidget(self)

        self.stack.addWidget(self.dashboard_w)   # 0
        self.stack.addWidget(self.clients_w)     # 1
        self.stack.addWidget(self.vehicles_w)    # 2
        self.stack.addWidget(self.depots_w)      # 3
        self.stack.addWidget(self.optimization_w)# 4
        self.stack.addWidget(self.map_w)         # 5
        self.stack.addWidget(self.tracking_w)    # 6
        self.stack.addWidget(self.scenarios_w)   # 7
        self.stack.addWidget(self.translation_w) # 8
        self.stack.addWidget(self.reports_w)     # 9
        self.stack.addWidget(self.logs_w)        # 10
        self.stack.addWidget(self.settings_w)    # 11

        main_layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # ── Dock Copilot IA ──
        self.copilot_dock = CopilotDockWidget(main_window=self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.copilot_dock)
        self.copilot_dock.hide()  # caché par défaut

        # ── Professional Status Bar ──
        sbar = self.statusBar()
        sbar.setFixedHeight(26)

        self._status_user = QLabel(
            f"  {self.current_user['full_name']}  |  {self.current_user['role'].capitalize()}"
        )
        self._status_user.setStyleSheet("font-size: 11px; padding: 0 8px;")
        sbar.addWidget(self._status_user)

        self._status_counts = QLabel("")
        self._status_counts.setStyleSheet("font-size: 11px; color: #888; padding: 0 8px;")
        sbar.addWidget(self._status_counts, 1)

        self._status_shortcuts = QLabel("F5 Actualiser  |  Ctrl+N Optimisation  |  F11 Plein écran  |  Ctrl+Shift+C Copilot")
        self._status_shortcuts.setStyleSheet("font-size: 10px; color: #999; padding: 0 8px;")
        self._status_shortcuts.setAlignment(Qt.AlignmentFlag.AlignRight)
        sbar.addPermanentWidget(self._status_shortcuts)

        self._update_status_counts()


        # Default selection — restore last page from session
        saved_page = get_user_session(self.current_user["id"])
        self._nav_to(saved_page)

    def _nav_to(self, index):
        for btn, nav_idx in self.nav_buttons:
            btn.setChecked(nav_idx == index)
        self.stack.setCurrentIndex(index)

        # Save current page to session
        if self.current_user:
            save_user_session(self.current_user["id"], index)

        # Refresh data on navigation
        widget = self.stack.currentWidget()
        if hasattr(widget, "refresh_data"):
            widget.refresh_data()

        # Update live status bar counters
        self._update_status_counts()

    def _update_status_counts(self):
        """Refresh the live counters in the status bar."""
        try:
            conn = get_connection()
            clients = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
            vehicles = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
            depots = conn.execute("SELECT COUNT(*) FROM depots").fetchone()[0]
            optims = conn.execute("SELECT COUNT(*) FROM algo_results").fetchone()[0]
            conn.close()
            self._status_counts.setText(
                f"Clients: {clients}  |  Véhicules: {vehicles}  |  "
                f"Dépôts: {depots}  |  Optimisations: {optims}"
            )
        except Exception:
            pass

    def notify(self, message: str, level: str = "info"):
        """Show a toast notification from anywhere via main_window.notify(...)"""
        show_toast(self, message, level, theme=self.current_theme)

    def _logout(self):
        reply = QMessageBox.question(
            self, "Déconnexion",
            "Voulez-vous vraiment vous déconnecter ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            log_action("LOGOUT", f"Déconnexion de {self.current_user['username']}",
                       user_id=self.current_user["id"])
            self.current_user = None
            self._show_login()

    def _toggle_copilot(self):
        self.copilot_dock.setVisible(not self.copilot_dock.isVisible())

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self._toggle_copilot)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(lambda: self._nav_to(4))
        QShortcut(QKeySequence("F5"), self).activated.connect(
            lambda: self.stack.currentWidget().refresh_data()
            if hasattr(self.stack.currentWidget(), "refresh_data") else None
        )
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            lambda: self.showNormal() if self.isFullScreen() else None
        )
        # Page navigation shortcuts
        QShortcut(QKeySequence("Ctrl+1"), self).activated.connect(lambda: self._nav_to(0))
        QShortcut(QKeySequence("Ctrl+2"), self).activated.connect(lambda: self._nav_to(1))
        QShortcut(QKeySequence("Ctrl+3"), self).activated.connect(lambda: self._nav_to(2))
        QShortcut(QKeySequence("Ctrl+4"), self).activated.connect(lambda: self._nav_to(3))
        QShortcut(QKeySequence("Ctrl+5"), self).activated.connect(lambda: self._nav_to(4))
        QShortcut(QKeySequence("Ctrl+6"), self).activated.connect(lambda: self._nav_to(5))
        QShortcut(QKeySequence("Ctrl+7"), self).activated.connect(lambda: self._nav_to(6))
        QShortcut(QKeySequence("Ctrl+8"), self).activated.connect(lambda: self._nav_to(7))
        QShortcut(QKeySequence("Ctrl+9"), self).activated.connect(lambda: self._nav_to(9))

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _show_about(self):
        conn = get_connection()
        clients = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
        vehicles = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        depots = conn.execute("SELECT COUNT(*) FROM depots").fetchone()[0]
        optims = conn.execute("SELECT COUNT(*) FROM algo_results").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()

        QMessageBox.about(self, "A propos — CityPulse Logistics",
            "<div style='text-align:center;'>"
            "<h2 style='margin:0;'>CityPulse Logistics</h2>"
            "<p style='color:#888; margin:4px 0 12px 0;'>Version 1.2.0 — Avril 2026</p>"
            "</div>"
            "<p>Plateforme professionnelle d'optimisation de tournées VRP "
            "avec intelligence artificielle.</p>"
            "<hr>"
            f"<p><b>Base de données :</b><br>"
            f"   {clients} clients &bull; {vehicles} véhicules &bull; "
            f"{depots} dépôts &bull; {optims} optimisations &bull; {users} utilisateurs</p>"
            "<p><b>Moteurs :</b> Glouton (Nearest Neighbor), 2-opt (Local Search), "
            "Google OR-Tools (Branch & Bound)</p>"
            "<p><b>IA :</b> Mistral LLM, Clustering KMeans, Détection d'anomalies, "
            "Prévision de demande</p>"
            "<hr>"
            "<p style='color:#888; font-size:11px;'>"
            "Python 3.11 &bull; PyQt6 &bull; OR-Tools &bull; Matplotlib &bull; "
            "Leaflet.js &bull; SQLite</p>"
        )
