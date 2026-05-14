"""
main_window.py — Fenêtre principale CityPulse Logistics
=======================================================
Sidebar collapsible (palette / profondeur alignées sur le fork TourVP),
icônes Lucide par entrée, TopBar + fade-in de page.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QMessageBox, QFrame, QSizePolicy, QScrollArea,
    QToolButton, QGraphicsOpacityEffect, QMenuBar, QMenu,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QColor, QAction

from .styles import get_stylesheet
from .components.topbar import TopBar

DARK_STYLE = get_stylesheet("dark")
from .login_widget import LoginWidget
from .copilot_widget import CopilotDockWidget
from .dashboard_widget import DashboardWidget
from .clients_widget import ClientsWidget
from .vehicles_widget import VehiclesWidget
from .depots_widget import DepotsWidget
from .orders_widget import OrdersWidget
from .drivers_widget import DriversWidget
from .carriers_widget import CarriersWidget
from .optimization_widget import OptimizationWidget
from .map_widget import MapWidget
from .translation_widget import TranslationWidget
from .reports_widget import ReportsWidget
from .settings_widget import SettingsWidget
from .scenarios_widget import ScenariosWidget
from .tracking_widget import TrackingWidget
from .logs_widget import LogsWidget
from .notifications_widget import NotificationsWidget
from .help_dialog import show_help
from .toast import show_toast
from ..database.db_manager import (
    init_database, log_action, save_user_session,
    get_user_session, get_connection
)

# ── Palette : fusion Tour (accent cyan) + profondeur sidebar/cartes type TourVP
BG      = "#0D1B2A"
BG2     = "#162840"
CARD    = "#243F58"
HOVER   = "#2A4A66"
ACCENT  = "#00D4FF"
TEXT    = "#E8F4FD"
TEXT2   = "#7FA8C0"
MUTED   = "#4A7A9B"
BORDER  = "#1E3A5F"
DANGER  = "#FF4757"

SIDEBAR_EXPANDED  = 210
SIDEBAR_COLLAPSED = 52

# ── Lucide SVG paths (stroke-only, viewBox 0 0 24 24) ────────────────────────
# Identiques aux icônes du prototype HTML (Lucide icon set)
_LUCIDE = {
    "dashboard": (
        "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"
    ),
    "users": (
        "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"
        " M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75"
    ),
    "truck": (
        "M1 3h15v13H1z M16 8h4l3 5v3h-7z"
        " M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"
        " M18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"
    ),
    "warehouse": (
        "M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35A2 2 0 0 1 3.26 6.5l8-3.2a2 2 0 0 1 1.48 0l8 3.2A2 2 0 0 1 22 8.35z"
        " M6 18h12 M6 14h12 M9 10h1 M14 10h1"
    ),
    "zap": "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
    "map": (
        "M1 6v16l7-4 8 4 7-4V2l-7 4-8-4-7 4z"
        " M8 2v16 M16 6v16"
    ),
    "activity": "M22 12h-4l-3 9L9 3l-3 9H2",
    "layers": (
        "M12 2l10 6.5v7L12 22 2 15.5v-7L12 2z"
        " M12 22v-6.5 M22 8.5l-10 7-10-7"
    ),
    "globe": (
        "M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z"
        " M2 12h20 M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10"
        " 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
    ),
    "file-text": (
        "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
        " M14 2v6h6 M16 13H8 M16 17H8 M10 9H8"
    ),
    "clipboard": (
        "M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"
        " M9 2h6a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"
        " M12 11h4 M12 16h4 M8 11h.01 M8 16h.01"
    ),
    "bell": (
        "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"
        " M10.3 21a1.94 1.94 0 0 0 3.4 0"
    ),
    "settings": (
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"
        " M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06"
        " a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09"
        " A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83"
        " l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09"
        " A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83"
        " l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09"
        " a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83"
        " l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09"
        " a1.65 1.65 0 0 0-1.51 1z"
    ),
    # Logo truck icon
    "logo-truck": (
        "M1 3h15v13H1z M16 8h4l3 5v3h-7z"
        " M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"
        " M18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"
    ),
    "bot": (
        "M12 8V4H8 M8 8H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-8"
        " a2 2 0 0 0-2-2h-4 M16 8H8 M9 16h.01 M15 16h.01"
    ),
    "user-check": (
        "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"
        " M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"
        " M16 11l2 2 4-4"
    ),
    "log-out": (
        "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"
        " M16 17l5-5-5-5 M21 12H9"
    ),
    # Distinct des autres entrées (évite doublon camion / presse-papiers)
    "shopping-bag": (
        "M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z M3 6h18"
        " M16 10a4 4 0 1 1-8 0"
    ),
    "briefcase": (
        "M16 8V6a2 2 0 0 0-2-2H10a2 2 0 0 0-2 2v2H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-4"
        " M9 2h6v4H9z M8 16h.01 M16 16h.01"
    ),
    "file-clock": (
        "M16 22h4a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v3 M14 2v4h4"
        " M10 2v8 M8 12h6 M8 16h4"
    ),
}


def _accent_highlight_rgba(accent_hex: str, alpha: float = 0.10) -> str:
    h = accent_hex.lstrip("#")
    if len(h) != 6:
        return f"rgba(0,212,255,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _make_svg_pixmap(path_key: str, color: str, size: int = 18) -> "QPixmap":
    """Render a Lucide SVG path to a QPixmap at the given size."""
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QPixmap, QPainter
    from PyQt6.QtCore import QByteArray, Qt as _Qt

    d = _LUCIDE.get(path_key, "")
    # Build full SVG — use multiple <path> tags split by " M" if needed
    svg_str = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"'
        f' width="{size}" height="{size}">'
        f'<path d="{d}" fill="none" stroke="{color}"'
        f' stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg_str.encode()))
    pm = QPixmap(size, size)
    pm.fill(_Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def _svg_icon_label(path_key: str, color: str, size: int = 18) -> "QLabel":
    """Return a QLabel displaying a Lucide icon as a pixmap."""
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("background:transparent;border:none;padding:0;")
    pm = _make_svg_pixmap(path_key, color, size)
    lbl.setPixmap(pm)
    return lbl


# Nav item definitions: (lucide_key, label, page_index)
NAV_ITEMS = [
    ("dashboard",  "Tableau de bord",  0),
    ("users",      "Clients",          1),
    ("truck",      "Véhicules",        2),
    ("user-check", "Chauffeurs",       3),
    ("warehouse",  "Dépôts",           4),
    ("shopping-bag", "Commandes",      5),
    ("briefcase",  "Transporteurs",    6),
    ("zap",        "Optimisation",     7),
    ("map",        "Carte",            8),
    ("activity",   "Suivi",            9),
    ("layers",     "Scénarios",       10),
    ("globe",      "Traduction",      11),
    ("file-text",  "Rapports",        12),
    ("file-clock", "Journal",         13),
    ("bell",       "Notifications",   14),
    ("settings",   "Paramètres",      15),
]

PAGE_NAMES = [
    "Tableau de bord", "Clients", "Véhicules", "Chauffeurs", "Dépôts",
    "Commandes", "Transporteurs", "Optimisation", "Carte", "Suivi en temps réel",
    "Scénarios", "Traduction", "Rapports", "Journal", "Notifications", "Paramètres",
]

# Clés i18n alignées sur NAV_ITEMS (même ordre)
_NAV_KEYS = [
    "dashboard", "clients", "vehicles", "drivers", "depots",
    "orders", "carriers", "optimization", "map", "tracking",
    "scenarios", "translation", "reports", "logs", "notifications", "settings",
]


class NavButton(QFrame):
    """
    Bouton sidebar : indicateur actif + icône SVG Lucide + label.
    QFrame composite pour un rendu parfait des icônes.
    """
    def __init__(self, icon_key: str, label: str, index: int, parent=None):
        super().__init__(parent)
        self.nav_index  = index
        self._icon_key  = icon_key
        self._label_txt = label
        self._active    = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(label)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # Left active bar
        self._bar = QFrame()
        self._bar.setFixedSize(3, 44)
        self._bar.setStyleSheet("background:transparent;border:none;")
        row.addWidget(self._bar)

        row.addSpacing(13)

        # SVG icon via QLabel+QPixmap
        self._icon_lbl = _svg_icon_label(icon_key, TEXT2, 18)
        row.addWidget(self._icon_lbl)

        row.addSpacing(11)

        # Text
        self._text_lbl = QLabel(label)
        self._text_lbl.setFont(QFont("Segoe UI", 12))
        self._text_lbl.setStyleSheet(
            f"color:{TEXT2};background:transparent;border:none;"
        )
        row.addWidget(self._text_lbl, 1)

        self._set_style(False)

    def _set_style(self, active: bool):
        ic_color  = ACCENT if active else TEXT2
        txt_style = (
            f"color:{ACCENT};background:transparent;border:none;font-weight:600;"
            if active else
            f"color:{TEXT2};background:transparent;border:none;"
        )
        bar_style = f"background:{ACCENT};border:none;" if active else "background:transparent;border:none;"
        bg        = _accent_highlight_rgba(ACCENT, 0.10) if active else "transparent"

        self.setStyleSheet(f"QFrame{{background:{bg};}}")
        self._bar.setStyleSheet(bar_style)
        self._text_lbl.setStyleSheet(txt_style)

        # Re-render icon with new colour
        pm = _make_svg_pixmap(self._icon_key, ic_color, 18)
        self._icon_lbl.setPixmap(pm)

    def set_active(self, active: bool):
        self._active = active
        self._set_style(active)

    def set_label(self, text: str):
        self._text_lbl.setText(text)
        self.setToolTip(text)

    def set_collapsed(self, collapsed: bool):
        self._text_lbl.setVisible(not collapsed)

    # ── mouse events ──────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)

    def _on_click(self):
        pass   # overridden per-instance below

    def enterEvent(self, event):
        if not self._active:
            self.setStyleSheet(f"QFrame{{background:{HOVER};}}")
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._active:
            self.setStyleSheet("QFrame{background:transparent;}")
        super().leaveEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CityPulse Logistics — Optimisation de Tournées")
        self.setMinimumSize(1100, 700)
        self.resize(1440, 900)
        self.current_user    = None
        self._sidebar_open   = True
        self._nav_btns       = []      # list of NavButton
        init_database()
        # Lire le thème et la langue sauvegardés
        self._current_theme = self._load_saved_theme()
        self._current_lang  = self._load_saved_lang()
        from PyQt6.QtWidgets import QApplication
        qss = get_stylesheet(self._current_theme)
        QApplication.instance().setStyleSheet(qss)
        self.setStyleSheet(qss)
        self._show_login()
        self._setup_shortcuts()

    def _load_saved_theme(self) -> str:
        try:
            from app.paths import settings_json_path
            import json, os
            path = settings_json_path()
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("system", {}).get("theme", "dark")
        except Exception:
            pass
        return "dark"

    def _load_saved_lang(self) -> str:
        try:
            from app.paths import settings_json_path
            import json, os
            path = settings_json_path()
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                lang = data.get("system", {}).get("ui_lang", "fr")
                from app.i18n import LANG_CODES
                return lang if lang in LANG_CODES else "fr"
        except Exception:
            pass
        return "fr"

    def _apply_theme(self, theme: str = "dark"):
        """Change le thème global (appelé depuis SettingsWidget)."""
        from PyQt6.QtWidgets import QApplication
        from .styles import THEMES
        self._current_theme = theme
        p = THEMES.get(theme, THEMES["dark"])
        bg   = p["bg_main"]
        bg2  = p["bg_sidebar"]
        brd  = p["border"]
        qss = get_stylesheet(theme)
        QApplication.instance().setStyleSheet(qss)
        self.setStyleSheet(qss)

        # Re-apply hardcoded main-window element styles
        if hasattr(self, "_central"):
            self._central.setStyleSheet(f"background:{bg};")
        if hasattr(self, "_sidebar"):
            self._sidebar.setStyleSheet(
                f"QFrame#sidebar{{background:{bg2};border-right:1px solid {brd};}}"
            )
        if hasattr(self, "_logo_row"):
            self._logo_row.setStyleSheet(
                f"QFrame{{background:{bg2};border-bottom:1px solid {brd};}}"
            )
        if hasattr(self, "_nav_area"):
            self._nav_area.setStyleSheet(f"background:{bg2};border:none;")
        if hasattr(self, "_nav_widget"):
            self._nav_widget.setStyleSheet(f"background:{bg2};")
        if hasattr(self, "_sidebar_footer"):
            self._sidebar_footer.setStyleSheet(
                f"QFrame{{background:{bg2};border-top:1px solid {brd};}}"
            )
        if hasattr(self, "_page_stack_host"):
            self._page_stack_host.setStyleSheet(
                f"QWidget#pageStackHost{{background:{bg};}}"
            )
        if hasattr(self, "stack"):
            self.stack.setStyleSheet(f"QStackedWidget{{background:{bg};}}")
        self.update()

    def _apply_language(self, lang: str):
        """Change la langue de l'interface (appelé depuis SettingsWidget)."""
        from app.i18n import tr, LANG_CODES
        if lang not in LANG_CODES:
            lang = "fr"
        self._current_lang = lang

        # Sidebar — mettre à jour les labels des boutons
        for btn, key in zip(self._nav_btns, _NAV_KEYS):
            btn.set_label(tr(f"nav.{key}", lang))

        # Breadcrumb — page courante
        if hasattr(self, "stack"):
            idx = self.stack.currentIndex()
            name = self._get_page_name(idx)
            if hasattr(self, "_page_title"):
                self._page_title.setText(name)
            if hasattr(self, "_topbar"):
                self._topbar.refresh_breadcrumb(name)

        # Menu bar — reconstruire avec la nouvelle langue
        if hasattr(self, "menuBar"):
            self.menuBar().clear()
            self._build_menu_bar()

        # Barre de statut — recalculer
        self._update_status_counts()

        # Propager à chaque page widget
        if hasattr(self, "stack"):
            for i in range(self.stack.count()):
                w = self.stack.widget(i)
                if hasattr(w, "retranslate_ui"):
                    try:
                        w.retranslate_ui(lang)
                    except Exception:
                        pass

    def _get_page_name(self, idx: int) -> str:
        """Retourne le nom de la page traduit dans la langue courante."""
        from app.i18n import tr
        lang = getattr(self, "_current_lang", "fr")
        if 0 <= idx < len(_NAV_KEYS):
            return tr(f"page.{_NAV_KEYS[idx]}", lang)
        return ""

    # ── Login ────────────────────────────────────────────────────────────────
    def _show_login(self):
        self.login_widget = LoginWidget()
        self.login_widget.login_success.connect(self._on_login)
        self.setCentralWidget(self.login_widget)
        self.statusBar().showMessage("Veuillez vous connecter")

    def _on_login(self, user):
        self.current_user = user
        log_action("SESSION_START", f"Session démarrée pour {user['username']}",
                   user_id=user["id"])
        self._build_main_ui()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(600, lambda: self.notify(
            f"Bienvenue, {user['full_name']} — session active", "info"
        ))

    # ── Build UI ─────────────────────────────────────────────────────────────
    def _build_main_ui(self):
        central = QWidget()
        self._central = central
        central.setStyleSheet(f"background:{BG};")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ════════════════════════════════════════════════════════════════════
        # SIDEBAR
        # ════════════════════════════════════════════════════════════════════
        self._sidebar = QFrame()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(SIDEBAR_EXPANDED)
        self._sidebar.setStyleSheet(
            f"QFrame#sidebar {{background:{BG2};border-right:1px solid {BORDER};}}"
        )
        self._sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sb = QVBoxLayout(self._sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        # ── Logo row ──────────────────────────────────────────────────────
        logo_row = QFrame()
        self._logo_row = logo_row
        logo_row.setFixedHeight(56)
        logo_row.setStyleSheet(
            f"QFrame{{background:{BG2};border-bottom:1px solid {BORDER};}}"
        )
        lr = QHBoxLayout(logo_row)
        lr.setContentsMargins(12, 0, 8, 0)
        lr.setSpacing(8)

        # Logo badge — icône camion Lucide sur fond accent
        badge = QLabel()
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:{ACCENT};border-radius:8px;border:none;padding:0;"
        )
        _pm_logo = _make_svg_pixmap("logo-truck", "#0D1B2A", 20)
        badge.setPixmap(_pm_logo)
        lr.addWidget(badge)

        self._logo_text = QLabel("CityPulse")
        self._logo_text.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._logo_text.setStyleSheet(f"color:{TEXT};background:transparent;border:none;")
        lr.addWidget(self._logo_text, 1)

        # Toggle button
        self._toggle_btn = QToolButton()
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setText("◀")
        self._toggle_btn.setToolTip("Réduire/Agrandir le menu")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"QToolButton{{background:transparent;border:none;color:{MUTED};"
            "font-size:12px;border-radius:4px;}}"
            f"QToolButton:hover{{background:{HOVER};color:{TEXT};}}"
        )
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        lr.addWidget(self._toggle_btn)
        sb.addWidget(logo_row)

        # ── Nav items ─────────────────────────────────────────────────────
        nav_area = QScrollArea()
        self._nav_area = nav_area
        nav_area.setWidgetResizable(True)
        nav_area.setFrameShape(QFrame.Shape.NoFrame)
        nav_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        nav_area.setStyleSheet(f"background:{BG2};border:none;")

        nav_widget = QWidget()
        self._nav_widget = nav_widget
        nav_widget.setStyleSheet(f"background:{BG2};")
        nav_vbox = QVBoxLayout(nav_widget)
        nav_vbox.setContentsMargins(0, 8, 0, 8)
        nav_vbox.setSpacing(1)

        self._nav_btns = []
        for icon_key, label, idx in NAV_ITEMS:
            btn = NavButton(icon_key, label, idx)
            def _wire(b, i):
                def _handler():
                    self._nav_to(i)
                b._on_click = _handler
            _wire(btn, idx)
            nav_vbox.addWidget(btn)
            self._nav_btns.append(btn)

        nav_vbox.addStretch()
        nav_area.setWidget(nav_widget)
        sb.addWidget(nav_area, 1)

        # ── Footer ────────────────────────────────────────────────────────
        footer = QFrame()
        self._sidebar_footer = footer
        footer.setStyleSheet(
            f"QFrame{{background:{BG2};border-top:1px solid {BORDER};}}"
        )
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(4)

        self._user_name_lbl = QLabel(self.current_user["full_name"])
        self._user_name_lbl.setStyleSheet(
            f"color:{TEXT};font-size:12px;font-weight:600;background:transparent;border:none;"
        )
        self._user_name_lbl.setWordWrap(True)
        self._user_role_lbl = QLabel(self.current_user["role"].capitalize())
        self._user_role_lbl.setStyleSheet(
            f"color:{MUTED};font-size:10px;background:transparent;border:none;"
        )
        fl.addWidget(self._user_name_lbl)
        fl.addWidget(self._user_role_lbl)

        fb_row = QHBoxLayout()
        fb_row.setSpacing(6)

        # Copilot button — bot icon + text
        copilot_btn = QPushButton()
        copilot_btn.setFixedHeight(30)
        copilot_btn.setToolTip("Copilot IA (Ctrl+Shift+C)")
        copilot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copilot_btn.setStyleSheet(
            f"QPushButton{{background:{CARD};color:{ACCENT};"
            f"border:1px solid {BORDER};border-radius:6px;"
            "font-size:11px;font-weight:600;padding:0 8px;}}"
            f"QPushButton:hover{{background:{HOVER};}}"
        )
        _cb_layout = QHBoxLayout(copilot_btn)
        _cb_layout.setContentsMargins(8, 0, 8, 0)
        _cb_layout.setSpacing(6)
        _cb_ic = QLabel()
        _cb_ic.setFixedSize(14, 14)
        _cb_ic.setStyleSheet("background:transparent;border:none;padding:0;")
        _cb_ic.setPixmap(_make_svg_pixmap("bot", ACCENT, 14))
        _cb_layout.addWidget(_cb_ic)
        _cb_txt = QLabel("Copilot")
        _cb_txt.setStyleSheet(f"color:{ACCENT};background:transparent;border:none;font-size:11px;font-weight:600;")
        _cb_layout.addWidget(_cb_txt)
        self._copilot_btn_txt = _cb_txt
        copilot_btn.clicked.connect(self._toggle_copilot)
        fb_row.addWidget(copilot_btn, 1)

        # Logout button — logout icon
        logout_btn = QPushButton()
        logout_btn.setFixedSize(30, 30)
        logout_btn.setToolTip("Déconnexion")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{DANGER};"
            f"border:1px solid {DANGER};border-radius:6px;padding:0;}}"
            f"QPushButton:hover{{background:rgba(255,71,87,31);}}"
        )
        _lo_layout = QHBoxLayout(logout_btn)
        _lo_layout.setContentsMargins(0, 0, 0, 0)
        _lo_ic = QLabel()
        _lo_ic.setFixedSize(16, 16)
        _lo_ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _lo_ic.setStyleSheet("background:transparent;border:none;padding:0;")
        _lo_ic.setPixmap(_make_svg_pixmap("log-out", DANGER, 16))
        _lo_layout.addWidget(_lo_ic, alignment=Qt.AlignmentFlag.AlignCenter)
        logout_btn.clicked.connect(self._logout)
        fb_row.addWidget(logout_btn)

        fl.addLayout(fb_row)
        sb.addWidget(footer)

        root.addWidget(self._sidebar)

        # ════════════════════════════════════════════════════════════════════
        # RIGHT PANEL
        # ════════════════════════════════════════════════════════════════════
        right = QWidget()
        right.setObjectName("rightPanel")
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────
        self._topbar = TopBar(main_window=self)
        self._topbar.refresh_user(self.current_user)

        # Compat: _page_title kept for legacy code that sets it directly
        self._page_title = self._topbar._page_lbl
        self._status_counts = self._topbar._counts_lbl

        rl.addWidget(self._topbar)

        # ── Page stack (marges « gouttière » pour aérer le contenu) ───────
        self._page_stack_host = QWidget()
        self._page_stack_host.setObjectName("pageStackHost")
        self._page_stack_host.setStyleSheet(f"QWidget#pageStackHost{{background:{BG};}}")
        _psh = QVBoxLayout(self._page_stack_host)
        _psh.setContentsMargins(20, 8, 20, 20)
        _psh.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"QStackedWidget{{background:{BG};}}")

        self.dashboard_w    = DashboardWidget(self)
        self.clients_w      = ClientsWidget(self)
        self.vehicles_w     = VehiclesWidget(self)
        self.drivers_w      = DriversWidget(self)
        self.depots_w       = DepotsWidget(self)
        self.orders_w       = OrdersWidget(self)
        self.carriers_w     = CarriersWidget(self)
        self.optimization_w = OptimizationWidget(self)
        self.map_w          = MapWidget(self)
        self.tracking_w     = TrackingWidget(self)
        self.scenarios_w    = ScenariosWidget(self)
        self.translation_w  = TranslationWidget(self)
        self.reports_w      = ReportsWidget(self)
        self.logs_w          = LogsWidget(self)
        self.notifications_w = NotificationsWidget(self)
        self.settings_w      = SettingsWidget(self)

        self.optimization_w.routes_ready.connect(self._on_routes_ready)
        self.tracking_w.reoptimization_done.connect(self._on_routes_ready)
        self.scenarios_w.compare_map_requested.connect(self._on_scenario_compare_map)
        self.notifications_w.navigate_request.connect(self._nav_to)
        self.tracking_w.route_updated.connect(self._on_tracking_route_updated)
        self.tracking_w.center_on_vehicle.connect(self._on_center_on_vehicle)
        self.map_w.marker_clicked.connect(self._on_map_marker_clicked)

        for w in [self.dashboard_w, self.clients_w, self.vehicles_w,
                  self.drivers_w, self.depots_w, self.orders_w,
                  self.carriers_w, self.optimization_w, self.map_w,
                  self.tracking_w, self.scenarios_w, self.translation_w,
                  self.reports_w, self.logs_w, self.notifications_w,
                  self.settings_w]:
            self.stack.addWidget(w)

        _psh.addWidget(self.stack, 1)
        rl.addWidget(self._page_stack_host, 1)

        # ── Status bar ────────────────────────────────────────────────────
        sb2 = self.statusBar()
        sb2.setFixedHeight(24)
        sb2.setStyleSheet(
            f"QStatusBar{{background:{BG2};color:{MUTED};"
            f"border-top:1px solid {BORDER};font-size:11px;}}"
        )
        self._status_user = QLabel(
            f"  {self.current_user['full_name']}  |  "
            f"{self.current_user['role'].capitalize()}"
        )
        self._status_user.setStyleSheet(f"color:{MUTED};font-size:11px;")
        sb2.addWidget(self._status_user)
        sb2.addPermanentWidget(QLabel(
            "F5 Actualiser  |  Ctrl+N Optimisation  |  F11 Plein écran  |  Ctrl+Shift+C Copilot  "
        ))

        root.addWidget(right, 1)
        self.setCentralWidget(central)

        # Copilot dock
        self.copilot_dock = CopilotDockWidget(main_window=self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.copilot_dock)
        self.copilot_dock.command_ready.connect(self.dispatch_copilot_command)
        self.copilot_dock.hide()

        # Opacity effect for page fade-in (0→1, 150ms)
        self._opacity_effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(150)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Timer 30s pour rafraîchir les notifications
        self._notif_timer = QTimer(self)
        self._notif_timer.setInterval(30_000)
        self._notif_timer.timeout.connect(self._refresh_notifications)
        self._notif_timer.start()

        self._build_menu_bar()
        self._update_status_counts()
        saved = get_user_session(self.current_user["id"])
        self._nav_to(saved if saved is not None else 0)
        # Appliquer la langue sauvegardée après construction complète de l'UI
        self._apply_language(self._current_lang)

    # ── Menu bar ─────────────────────────────────────────────────────────────
    def _build_menu_bar(self):
        from app.i18n import tr
        lang = getattr(self, "_current_lang", "fr")
        mb = self.menuBar()
        mb.setStyleSheet(
            f"QMenuBar{{background:{BG2};color:{TEXT};font-size:12px;border:none;}}"
            f"QMenuBar::item{{background:transparent;padding:4px 10px;}}"
            f"QMenuBar::item:selected{{background:{HOVER};border-radius:4px;}}"
            f"QMenu{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:6px;padding:4px;}}"
            f"QMenu::item{{padding:6px 20px;border-radius:4px;}}"
            f"QMenu::item:selected{{background:{HOVER};}}"
            f"QMenu::separator{{height:1px;background:{BORDER};margin:4px 10px;}}"
        )

        # ── Fichier ────────────────────────────────────────────────────────
        file_menu = mb.addMenu(tr("menu.file", lang))

        act_demo = QAction(tr("menu.load_demo", lang), self)
        act_demo.setShortcut("Ctrl+D")
        act_demo.triggered.connect(self._open_demo_loader)
        file_menu.addAction(act_demo)

        file_menu.addSeparator()

        act_export = QAction(tr("menu.export_pdf", lang), self)
        act_export.triggered.connect(lambda: self._nav_to(12))
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_quit = QAction(tr("menu.quit", lang), self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── Outils ────────────────────────────────────────────────────────
        tools_menu = mb.addMenu(tr("menu.tools", lang))

        for key, idx in [
            ("drivers", 3), ("orders", 5), ("carriers", 6),
            ("optimization", 7), ("map", 8), ("scenarios", 10),
            ("translation", 11), ("logs", 13), ("notifications", 14),
            ("settings", 15),
        ]:
            act = QAction(tr(f"nav.{key}", lang), self)
            act.triggered.connect(lambda _, i=idx: self._nav_to(i))
            tools_menu.addAction(act)

        # ── Aide ──────────────────────────────────────────────────────────
        help_menu = mb.addMenu(tr("menu.help", lang))

        act_help = QAction(tr("menu.help_guide", lang), self)
        act_help.triggered.connect(lambda: show_help(self, "dashboard"))
        help_menu.addAction(act_help)

        act_about = QAction(tr("menu.about", lang), self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _open_demo_loader(self):
        from .demo_loader import DemoLoaderDialog
        dlg = DemoLoaderDialog(main_window=self, parent=self)
        dlg.exec()

    # ── Sidebar toggle ───────────────────────────────────────────────────────
    def _toggle_sidebar(self):
        self._sidebar_open = not self._sidebar_open
        target = SIDEBAR_EXPANDED if self._sidebar_open else SIDEBAR_COLLAPSED

        self._anim = QPropertyAnimation(self._sidebar, b"minimumWidth")
        self._anim.setDuration(180)
        self._anim.setStartValue(self._sidebar.width())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
        self._anim.start()

        anim2 = QPropertyAnimation(self._sidebar, b"maximumWidth")
        anim2.setDuration(180)
        anim2.setStartValue(self._sidebar.width())
        anim2.setEndValue(target)
        anim2.setEasingCurve(QEasingCurve.Type.InOutQuart)
        anim2.start()
        self._anim2 = anim2  # keep reference

        self._toggle_btn.setText("▶" if not self._sidebar_open else "◀")
        self._logo_text.setVisible(self._sidebar_open)
        self._user_name_lbl.setVisible(self._sidebar_open)
        self._user_role_lbl.setVisible(self._sidebar_open)
        if hasattr(self, "_copilot_btn_txt"):
            self._copilot_btn_txt.setVisible(self._sidebar_open)
        for btn in self._nav_btns:
            btn.set_collapsed(not self._sidebar_open)

    # ── Navigation ───────────────────────────────────────────────────────────
    def get_active_page_title(self) -> str:
        if not hasattr(self, "stack"):
            return ""
        idx = self.stack.currentIndex()
        if 0 <= idx < len(PAGE_NAMES):
            return PAGE_NAMES[idx]
        return ""

    def dispatch_copilot_command(self, cmd: dict):
        """Exécute une action proposée par le Copilot (navigation, optimisation, commande)."""
        if not cmd:
            return
        action = cmd.get("action")
        try:
            if action == "navigate":
                idx = cmd.get("page_index")
                if idx is not None:
                    self._nav_to(int(idx))
                    return
                page = (cmd.get("page") or "").lower().strip()
                aliases = {
                    "dashboard": 0, "tableau": 0, "clients": 1, "vehicules": 2, "véhicules": 2,
                    "chauffeurs": 3, "drivers": 3, "depots": 4, "dépôts": 4,
                    "commandes": 5, "orders": 5, "transporteurs": 6, "carriers": 6,
                    "optimisation": 7, "optimization": 7, "carte": 8, "map": 8,
                    "suivi": 9, "tracking": 9, "scenarios": 10, "scénarios": 10,
                    "traduction": 11, "translation": 11, "rapports": 12, "reports": 12,
                    "journal": 13, "logs": 13,
                    "notifications": 14, "notification": 14,
                    "parametres": 15, "paramètres": 15, "settings": 15,
                }
                if page in aliases:
                    self._nav_to(aliases[page])
            elif action == "optimize":
                self._nav_to(7)
            elif action == "create_order":
                self._nav_to(5)
                show_toast(self, "Page Commandes ouverte — créez une nouvelle commande.", "info")
        except Exception:
            import logging
            logging.getLogger(__name__).exception("dispatch_copilot_command")

    def _nav_to(self, index: int):
        if index is None:
            index = 0
        index = max(0, min(index, len(PAGE_NAMES) - 1))
        for btn in self._nav_btns:
            btn.set_active(btn.nav_index == index)

        # Masquer immédiatement avant de changer de page + refresh
        # pour éviter le flash de contenu en cours de reconstruction
        if hasattr(self, "_fade_anim"):
            self._fade_anim.stop()
        if hasattr(self, "_opacity_effect"):
            self._opacity_effect.setOpacity(0.0)

        self.stack.setCurrentIndex(index)
        name = self._get_page_name(index) or PAGE_NAMES[index]
        if hasattr(self, "_page_title"):
            self._page_title.setText(name)
        if hasattr(self, "_topbar"):
            self._topbar.refresh_breadcrumb(name)
        if self.current_user:
            save_user_session(self.current_user["id"], index)
        w = self.stack.currentWidget()
        if hasattr(w, "refresh_data"):
            w.refresh_data()
        self._update_status_counts()
        # Délai 60ms pour laisser Matplotlib et QtWebEngine vider leur file
        # de paint events avant de révéler la page (sinon flash de contenu partiel)
        _has_async = (
            hasattr(w, "_canvas") or hasattr(w, "_web") or hasattr(w, "_map_view")
            or hasattr(w, "_fig") or hasattr(w, "web_view")
        )
        delay = 80 if _has_async else 30
        QTimer.singleShot(delay, self._start_page_fade)

    def _start_page_fade(self):
        if hasattr(self, "_fade_anim"):
            self._fade_anim.stop()
            self._fade_anim.start()

    def _update_status_counts(self):
        try:
            from app.i18n import tr
            lang = getattr(self, "_current_lang", "fr")
            conn = get_connection()
            c = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
            v = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
            d = conn.execute("SELECT COUNT(*) FROM depots").fetchone()[0]
            o = conn.execute("SELECT COUNT(*) FROM algo_results").fetchone()[0]
            conn.close()
            text = (
                f"{tr('status.clients', lang)}: {c}  ·  "
                f"{tr('status.vehicles', lang)}: {v}  ·  "
                f"{tr('status.depots', lang)}: {d}  ·  "
                f"{tr('status.opts', lang)}: {o}"
            )
            self._status_counts.setText(text)
            if hasattr(self, "_topbar"):
                self._topbar.set_counts(text)
        except Exception:
            pass

    def _refresh_notifications(self):
        if hasattr(self, "_topbar"):
            self._topbar.bell.refresh_from_db()

    # ── Actions ──────────────────────────────────────────────────────────────
    def notify(self, message: str, level: str = "info"):
        show_toast(self, message, level, theme="dark")

    def _logout(self):
        reply = QMessageBox.question(
            self, "Déconnexion", "Voulez-vous vraiment vous déconnecter ",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            log_action("LOGOUT", f"Déconnexion de {self.current_user['username']}",
                       user_id=self.current_user["id"])
            self.current_user = None
            self._show_login()

    def _toggle_copilot(self):
        self.copilot_dock.setVisible(not self.copilot_dock.isVisible())

    def _on_tracking_route_updated(self, vehicle_id: int, stops_json: str):
        """Rafraîchit la carte quand un bloc Gantt est déplacé/verrouillé."""
        try:
            if hasattr(self, "map_w"):
                self.map_w.refresh_data()
        except Exception:
            pass

    def _on_center_on_vehicle(self, vehicle_id: int):
        """Navigue vers la carte et centre sur le véhicule sélectionné."""
        self._nav_to(8)

    def _on_map_marker_clicked(self, table: str, id_: int):
        """Naviguer vers la page correspondant au marqueur cliqué sur la carte."""
        nav = {
            "clients": 1, "vehicles": 2, "depots": 4, "orders": 5,
        }.get(table, -1)
        if nav >= 0:
            self._nav_to(nav)

    def _on_routes_ready(self, result):
        try:
            if hasattr(self, "map_w") and result.get("routes"):
                self.map_w.display_routes(result)
            if hasattr(self, "tracking_w") and result.get("routes"):
                self.tracking_w.set_routes(result)
            if hasattr(self, "dashboard_w"):
                self.dashboard_w.refresh_data()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Erreur _on_routes_ready")

    def _on_scenario_compare_map(self, payload: dict):
        try:
            if hasattr(self, "map_w"):
                self.map_w.apply_dual_scenario_routes(
                    payload.get("left") or {},
                    payload.get("right") or {},
                )
                self._nav_to(8)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("_on_scenario_compare_map")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self._toggle_copilot)
        QShortcut(QKeySequence("Ctrl+N"),       self).activated.connect(lambda: self._nav_to(7))
        QShortcut(QKeySequence("F5"),           self).activated.connect(self._refresh_current)
        QShortcut(QKeySequence("F11"),          self).activated.connect(self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"),       self).activated.connect(
            lambda: self.showNormal() if self.isFullScreen() else None
        )
        QShortcut(QKeySequence("Ctrl+\\"),      self).activated.connect(self._toggle_sidebar)
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self).activated.connect(
                lambda _=False, x=i - 1: self._nav_to(x)
            )

    def _refresh_current(self):
        w = self.stack.currentWidget() if hasattr(self, "stack") else None
        if w and hasattr(w, "refresh_data"):
            w.refresh_data()

    def closeEvent(self, event):
        """Demande confirmation si un thread de calcul est encore actif."""
        running = []
        if hasattr(self, "optimization_w"):
            w = self.optimization_w
            if hasattr(w, "_thread") and w._thread and w._thread.isRunning():
                running.append("Optimisation en cours")
            if hasattr(w, "_week_thread") and w._week_thread and w._week_thread.isRunning():
                running.append("Planification semaine en cours")

        if running:
            msg = QMessageBox(self)
            msg.setWindowTitle("Fermeture — calcul en cours")
            msg.setText(
                "<b>Un calcul est encore actif :</b><br>"
                + "<br>".join(f"• {r}" for r in running)
                + "<br><br>Fermer maintenant peut corrompre la base de données."
            )
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setIcon(QMessageBox.Icon.Warning)
            btn_wait  = msg.addButton("Attendre la fin", QMessageBox.ButtonRole.RejectRole)
            btn_force = msg.addButton("Fermer quand même", QMessageBox.ButtonRole.DestructiveRole)
            msg.setDefaultButton(btn_wait)
            msg.exec()
            if msg.clickedButton() == btn_wait:
                event.ignore()
                return
            # Force stop threads before closing
            try:
                if hasattr(self, "optimization_w"):
                    w = self.optimization_w
                    if hasattr(w, "_thread") and w._thread:
                        w._thread.terminate()
                    if hasattr(w, "_week_thread") and w._week_thread:
                        w._week_thread.terminate()
            except Exception:
                pass

        event.accept()

    def _show_about(self):
        conn = get_connection()
        c = conn.execute("SELECT COUNT(*) FROM clients WHERE archived=0").fetchone()[0]
        v = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        d = conn.execute("SELECT COUNT(*) FROM depots").fetchone()[0]
        o = conn.execute("SELECT COUNT(*) FROM algo_results").fetchone()[0]
        u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        QMessageBox.about(self, "À propos — CityPulse Logistics",
            "<h2>CityPulse Logistics</h2>"
            "<p style='color:#888;'>Version 1.2.0 — 2026</p>"
            "<p>Plateforme professionnelle d'optimisation de tournées VRP.</p>"
            f"<p><b>Base :</b> {c} clients · {v} véhicules · "
            f"{d} dépôts · {o} optimisations · {u} utilisateurs</p>"
            "<p><b>Moteurs :</b> Glouton (Nearest Neighbor), 2-opt, OR-Tools</p>"
            "<p><b>IA :</b> Mistral LLM, KMeans, Anomaly Detection, Forecast</p>"
        )
