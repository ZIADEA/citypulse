"""
styles.py — Thèmes CityPulse Logistics
=======================================
Deux thèmes : 'dark' (défaut) et 'light'.
Usage : get_stylesheet(theme='dark') | get_stylesheet(theme='light')
"""

# ── Palettes ──────────────────────────────────────────────────────────────────
THEMES: dict[str, dict] = {
    "dark": {
        "bg_main":     "#0D1B2A",
        "bg_sidebar":  "#162840",
        "bg_panel":    "#243F58",
        "bg_input":    "#1A2E4A",
        "bg_header":   "#162840",   # en-têtes de tableau (= bg_sidebar en dark)
        "accent":      "#00D4FF",
        "success":     "#00FF88",
        "warning":     "#FFB800",
        "danger":      "#FF4757",
        "text":        "#E8F4FD",
        "text_sec":    "#7FA8C0",
        "border":      "#1E3A5F",
        "hover":       "#2A4A66",
        "accent_dim":  "rgba(0,212,255,31)",
        "success_dim": "rgba(0,255,136,31)",
        "warning_dim": "rgba(255,184,0,31)",
        "danger_dim":  "rgba(255,71,87,31)",
        "accent_text": "#FFFFFF",
    },
    # Thème clair professionnel — palette grise type Minitab/Windows
    # La sidebar reste sombre (charbon #363B44) car les couleurs des NavButton
    # sont hardcodées pour du texte clair dans main_window.py.
    "light": {
        "bg_main":     "#EBEDF0",   # fond app — gris argenté
        "bg_sidebar":  "#363B44",   # sidebar charbon — nav lisible (texte clair hardcodé)
        "bg_panel":    "#FFFFFF",   # cartes et panneaux — blanc
        "bg_input":    "#FAFBFC",   # champs de saisie — blanc cassé
        "bg_header":   "#E4E6EA",   # en-têtes de tableau — argent clair
        "accent":      "#2878C8",   # bleu acier professionnel
        "success":     "#1E7A3A",   # vert forêt
        "warning":     "#B05800",   # ambre
        "danger":      "#B02020",   # rouge foncé
        "text":        "#1A202C",   # noir ardoise (contenu)
        "text_sec":    "#5A6472",   # gris moyen
        "border":      "#C2C7CF",   # bordure argent
        "hover":       "#E1E4E8",   # survol (zones de contenu)
        "accent_dim":  "rgba(40,120,200,35)",
        "success_dim": "rgba(30,122,58,30)",
        "warning_dim": "rgba(176,88,0,30)",
        "danger_dim":  "rgba(176,32,32,30)",
        "accent_text": "#FFFFFF",
    },
}


def _build_qss(p: dict) -> str:
    return f"""
/* ═══════════════════════════════════════════════════════════════════════
   BASE
═══════════════════════════════════════════════════════════════════════ */
QWidget {{
    background-color: {p['bg_main']};
    color: {p['text']};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}
QFrame {{
    background-color: transparent;
    border: none;
}}
QStackedWidget {{
    background-color: {p['bg_main']};
}}
#pageStackHost {{
    background-color: {p['bg_main']};
}}
#rightPanel {{
    background-color: {p['bg_main']};
}}
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QScrollBar:vertical {{
    width: 13px;
    background: {p['bg_panel']};
    border-radius: 6px;
    margin: 3px 2px 3px 0;
}}
QScrollBar::handle:vertical {{
    background: {p['border']};
    border-radius: 5px;
    min-height: 36px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p['text_sec']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    border: none;
}}
QScrollBar:horizontal {{
    height: 13px;
    background: {p['bg_panel']};
    border-radius: 6px;
    margin: 0 3px 2px 3px;
}}
QScrollBar::handle:horizontal {{
    background: {p['border']};
    border-radius: 5px;
    min-width: 36px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p['text_sec']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    border: none;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════════════════════════════ */
#sidebar {{
    background-color: {p['bg_sidebar']};
    border-right: 1px solid {p['border']};
}}
#navItem {{
    background-color: transparent;
    border: none;
    min-height: 52px;
    max-height: 52px;
    padding: 0;
    border-radius: 0;
}}
#navItem:hover {{
    background-color: {p['hover']};
}}
#navItemActive {{
    background-color: {p['accent_dim']};
}}

/* ═══════════════════════════════════════════════════════════════════════
   TOPBAR
═══════════════════════════════════════════════════════════════════════ */
#topBar {{
    background-color: {p['bg_panel']};
    border-bottom: 1px solid {p['border']};
    min-height: 48px;
    max-height: 48px;
}}
#breadcrumb {{
    color: {p['text']};
    font-size: 14px;
    font-weight: 600;
    background: transparent;
    border: none;
}}
#breadcrumbSep {{
    color: {p['text_sec']};
    background: transparent;
    border: none;
    font-size: 12px;
}}
#headerBar {{
    background-color: {p['bg_sidebar']};
    border-bottom: 1px solid {p['border']};
}}
#appTitle {{
    color: {p['accent']};
    font-size: 15px;
    font-weight: 700;
}}

/* ═══════════════════════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════════════════════ */
#primaryBtn {{
    background-color: {p['accent']};
    color: {p['accent_text']};
    border: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 34px;
}}
#primaryBtn:default {{
    background-color: {p['accent']};
    color: {p['accent_text']};
}}
#primaryBtn:hover {{
    background-color: {p['accent']};
    border: 1px solid {p['text_sec']};
    color: {p['accent_text']};
}}
#primaryBtn:pressed {{
    background-color: {p['accent']};
    color: {p['accent_text']};
}}
#primaryBtn:disabled {{
    background-color: {p['border']};
    color: {p['text_sec']};
    border: none;
}}
#secondaryBtn {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 34px;
}}
#secondaryBtn:default {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
}}
#secondaryBtn:hover {{
    background-color: {p['hover']};
    border-color: {p['accent']};
    color: {p['text']};
}}
#secondaryBtn:pressed {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border-color: {p['border']};
}}
#secondaryBtn:disabled {{
    background-color: {p['bg_panel']};
    color: {p['text_sec']};
    border-color: {p['border']};
}}
#dangerBtn {{
    background-color: transparent;
    color: {p['danger']};
    border: 1px solid {p['danger']};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 34px;
}}
#dangerBtn:default {{
    background-color: transparent;
    color: {p['danger']};
    border: 1px solid {p['danger']};
}}
#dangerBtn:hover {{
    background-color: {p['danger_dim']};
    color: {p['danger']};
    border: 1px solid {p['danger']};
}}
#dangerBtn:pressed {{
    background-color: {p['danger_dim']};
    color: {p['danger']};
}}
#dangerBtn:disabled {{
    background-color: {p['bg_panel']};
    color: {p['text_sec']};
    border: 1px solid {p['border']};
}}
#ghostBtn {{
    background-color: transparent;
    color: {p['text_sec']};
    border: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}}
#ghostBtn:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
#ghostBtn:pressed {{
    background-color: {p['hover']};
    color: {p['text']};
}}
#ghostBtn:disabled {{
    background-color: transparent;
    color: {p['text_sec']};
}}
#iconBtn {{
    background-color: transparent;
    color: {p['text_sec']};
    border: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
    padding: 4px;
}}
#iconBtn:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
#iconBtn:pressed {{
    background-color: {p['hover']};
    color: {p['text']};
}}
#iconBtn:disabled {{
    background-color: transparent;
    color: {p['text_sec']};
}}

/* ═══════════════════════════════════════════════════════════════════════
   TABLES
═══════════════════════════════════════════════════════════════════════ */
QTableWidget {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    gridline-color: {p['border']};
    selection-background-color: {p['accent_dim']};
    selection-color: {p['text']};
    font-size: 12px;
    alternate-background-color: {p['bg_input']};
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 10px;
    border: none;
}}
QTableWidget::item:hover {{
    background-color: {p['hover']};
}}
QTableWidget::item:selected {{
    background-color: {p['accent_dim']};
    color: {p['text']};
}}
QHeaderView::section {{
    background-color: {p.get('bg_header', p['bg_sidebar'])};
    color: {p['text']};
    border: none;
    border-bottom: 2px solid {p['border']};
    border-right: 1px solid {p['border']};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}
QHeaderView::section:hover {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QTableCornerButton::section {{
    background-color: {p.get('bg_header', p['bg_sidebar'])};
    border: none;
}}

/* ═══════════════════════════════════════════════════════════════════════
   FORMS
═══════════════════════════════════════════════════════════════════════ */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    min-height: 38px;
    selection-background-color: {p['accent']};
    selection-color: {p['accent_text']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {p['accent']};
}}
QLineEdit:disabled {{
    color: {p['text_sec']};
    background-color: {p['bg_panel']};
}}
QComboBox {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    min-height: 38px;
    min-width: 120px;
}}
QComboBox:focus {{
    border: 1px solid {p['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    selection-background-color: {p['accent_dim']};
    selection-color: {p['text']};
    padding: 4px;
    outline: none;
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 38px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {p['accent']};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {p['bg_panel']};
    border: none;
    width: 20px;
}}
QDateEdit, QTimeEdit {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 38px;
}}
QDateEdit:focus, QTimeEdit:focus {{
    border: 1px solid {p['accent']};
}}
QDateEdit::drop-down, QTimeEdit::drop-down {{
    border: none;
    width: 24px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════════════════════ */
QTabWidget::pane {{
    background-color: {p['bg_panel']};
    border: 1px solid {p['border']};
    border-top-left-radius: 0;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    border-bottom-left-radius: 6px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {p['text_sec']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 20px;
    font-size: 12px;
    font-weight: 500;
}}
QTabBar::tab:hover {{
    color: {p['text']};
    background-color: {p['hover']};
}}
QTabBar::tab:selected {{
    color: {p['accent']};
    border-bottom: 2px solid {p['accent']};
    font-weight: 600;
}}

/* ═══════════════════════════════════════════════════════════════════════
   PROGRESS BAR
═══════════════════════════════════════════════════════════════════════ */
QProgressBar {{
    background-color: {p['bg_input']};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {p['accent']}, stop:1 {p['success']});
    border-radius: 4px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SCROLLBAR (8px fine)
═══════════════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p['border']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p['text_sec']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {p['border']};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p['text_sec']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ═══════════════════════════════════════════════════════════════════════
   TYPOGRAPHY
═══════════════════════════════════════════════════════════════════════ */
QLabel {{
    color: {p['text']};
    background: transparent;
    border: none;
}}
#heading {{
    color: {p['text']};
    font-size: 20px;
    font-weight: 700;
    background: transparent;
}}
#subheading {{
    color: {p['text_sec']};
    font-size: 12px;
    background: transparent;
}}
#caption {{
    color: {p['text_sec']};
    font-size: 11px;
    background: transparent;
}}

/* ═══════════════════════════════════════════════════════════════════════
   GROUP BOX
═══════════════════════════════════════════════════════════════════════ */
QGroupBox {{
    background-color: {p['bg_panel']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px;
    padding-top: 24px;
    font-size: 12px;
    font-weight: 600;
    color: {p['text_sec']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    left: 12px;
    color: {p['text_sec']};
    font-size: 11px;
    font-weight: 700;
    background: {p['bg_panel']};
    border-radius: 4px;
}}
QGroupBox QLineEdit,
QGroupBox QTextEdit,
QGroupBox QPlainTextEdit,
QGroupBox QComboBox,
QGroupBox QSpinBox,
QGroupBox QDoubleSpinBox,
QGroupBox QDateEdit,
QGroupBox QTimeEdit {{
    max-width: 480px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   CHECKBOX / RADIO
═══════════════════════════════════════════════════════════════════════ */
QCheckBox {{
    color: {p['text']};
    spacing: 8px;
    font-size: 13px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {p['border']};
    border-radius: 4px;
    background: {p['bg_input']};
}}
QCheckBox::indicator:hover {{
    border-color: {p['accent']};
}}
QCheckBox::indicator:checked {{
    background-color: {p['accent']};
    border-color: {p['accent']};
}}
QRadioButton {{
    color: {p['text']};
    spacing: 8px;
    font-size: 13px;
    background: transparent;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {p['border']};
    border-radius: 8px;
    background: {p['bg_input']};
}}
QRadioButton::indicator:checked {{
    background-color: {p['accent']};
    border-color: {p['accent']};
}}

/* ═══════════════════════════════════════════════════════════════════════
   SLIDER
═══════════════════════════════════════════════════════════════════════ */
QSlider::groove:horizontal {{
    height: 4px;
    background: {p['border']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: {p['accent']};
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {p['accent']};
    border-radius: 2px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   SPLITTER
═══════════════════════════════════════════════════════════════════════ */
QSplitter::handle {{
    background-color: {p['border']};
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}

/* ═══════════════════════════════════════════════════════════════════════
   MENUBAR / MENU
═══════════════════════════════════════════════════════════════════════ */
QMenuBar {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border-bottom: 1px solid {p['border']};
    font-size: 13px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
}}
QMenuBar::item:selected {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QMenu {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 4px;
    font-size: 13px;
}}
QMenu::item {{
    padding: 8px 24px 8px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QMenu::separator {{
    height: 1px;
    background: {p['border']};
    margin: 4px 8px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   TOOLBAR
═══════════════════════════════════════════════════════════════════════ */
QToolBar {{
    background-color: {p['bg_panel']};
    border: none;
    border-bottom: 1px solid {p['border']};
    spacing: 4px;
    padding: 4px;
}}
QToolBar::separator {{
    background: {p['border']};
    width: 1px;
    margin: 4px 6px;
}}

/* ═══════════════════════════════════════════════════════════════════════
   STATUS BAR
═══════════════════════════════════════════════════════════════════════ */
QStatusBar {{
    background-color: {p['bg_panel']};
    color: {p['text_sec']};
    border-top: 1px solid {p['border']};
    font-size: 11px;
}}
QStatusBar::item {{ border: none; }}

/* ═══════════════════════════════════════════════════════════════════════
   TREE & LIST
═══════════════════════════════════════════════════════════════════════ */
QTreeWidget, QListWidget {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    alternate-background-color: {p['bg_input']};
    outline: none;
    font-size: 13px;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 6px 8px;
    border: none;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background-color: {p['hover']};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {p['accent_dim']};
    color: {p['text']};
}}

/* ═══════════════════════════════════════════════════════════════════════
   MESSAGE BOX
═══════════════════════════════════════════════════════════════════════ */
QMessageBox {{
    background-color: {p['bg_panel']};
    color: {p['text']};
}}
QMessageBox QLabel {{
    color: {p['text']};
    font-size: 13px;
}}
QMessageBox QPushButton {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 7px 20px;
    font-size: 12px;
    min-width: 80px;
}}
QMessageBox QPushButton:hover {{
    background-color: {p['hover']};
    border-color: {p['accent']};
    color: {p['text']};
}}
QMessageBox QPushButton:pressed {{
    background-color: {p['bg_input']};
    color: {p['text']};
}}
QMessageBox QPushButton:disabled {{
    background-color: {p['bg_panel']};
    color: {p['text_sec']};
    border-color: {p['border']};
}}

/* QDialogButtonBox : boutons standard (OK/Annuler/Fermer) lisibles sur fond dialogue */
QDialog QDialogButtonBox QPushButton {{
    background-color: {p['bg_input']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 7px 18px;
    font-size: 12px;
    min-width: 72px;
    min-height: 32px;
}}
QDialog QDialogButtonBox QPushButton:hover {{
    background-color: {p['hover']};
    color: {p['text']};
    border-color: {p['accent']};
}}
QDialog QDialogButtonBox QPushButton:pressed {{
    background-color: {p['bg_input']};
    color: {p['text']};
}}
QDialog QDialogButtonBox QPushButton:disabled {{
    background-color: {p['bg_panel']};
    color: {p['text_sec']};
    border-color: {p['border']};
}}

/* ═══════════════════════════════════════════════════════════════════════
   DOCK WIDGET
═══════════════════════════════════════════════════════════════════════ */
QDockWidget {{
    background-color: {p['bg_panel']};
    color: {p['text']};
}}
QDockWidget::title {{
    background-color: {p['bg_sidebar']};
    border-bottom: 1px solid {p['border']};
    padding: 8px 14px;
    font-weight: 600;
    color: {p['text']};
    text-align: left;
}}

/* ═══════════════════════════════════════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {p['bg_panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
}}
"""


_QSS_CACHE: dict[str, str] = {}


def get_stylesheet(theme: str = "dark") -> str:
    _QSS_CACHE.clear()
    if theme not in _QSS_CACHE:
        p = THEMES.get(theme, THEMES["dark"])
        _QSS_CACHE[theme] = _build_qss(p)
    return _QSS_CACHE[theme]


def get_dark_stylesheet() -> str:
    return get_stylesheet("dark")


def get_light_stylesheet() -> str:
    return get_stylesheet("light")


# ── Backward-compat exports (widgets import C / COLORS / DARK_STYLE) ──────────
_D = THEMES["dark"]
C = {
    "bg":          _D["bg_main"],
    "bg2":         _D["bg_sidebar"],
    "bg3":         _D["bg_panel"],
    "card":        _D["bg_panel"],
    "hover":       _D["hover"],
    "accent":      _D["accent"],
    "accent_dark": "#009EC0",
    "accent_orange": "#FF6B35",
    "text":        _D["text"],
    "text2":       _D["text_sec"],
    "muted":       _D["text_sec"],
    "success":     _D["success"],
    "danger":      _D["danger"],
    "warning":     _D["warning"],
    "info":        "#3B9EE8",
    "border":      _D["border"],
    "border2":     _D["border"],
    "purple":      "#8B5CF6",
}
COLORS = C
DARK_STYLE = get_stylesheet("dark")
LIGHT_STYLE = get_stylesheet("light")
REAL_DARK_STYLE = DARK_STYLE
