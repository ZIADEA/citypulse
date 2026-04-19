DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #f7f8fa;
    color: #2c2c2c;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #ffffff;
    color: #2c2c2c;
    border-bottom: 1px solid #d8dce3;
}
QMenuBar::item:selected { background-color: #e8e8ed; }
QMenu {
    background-color: #ffffff;
    color: #2c2c2c;
    border: 1px solid #d8dce3;
}
QMenu::item:selected { background-color: #e8e8ed; }
QStatusBar {
    background-color: #ffffff;
    color: #6c6c6c;
    border-top: 1px solid #d8dce3;
}

/* Top Header Bar (e-Prelude / Minitab inspired) */
#headerBar {
    background-color: #ffffff;
    border-bottom: 1px solid #d8dce3;
}
#appTitle {
    color: #1a1a1a;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 0 4px;
}
#headerUser {
    color: #555555;
    font-size: 11px;
    font-weight: 500;
    padding: 0 12px;
}
#headerBtn {
    background-color: transparent;
    color: #2c2c2c;
    border: none;
    border-radius: 0px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 500;
}
#headerBtn:hover {
    background-color: #ecedf2;
    color: #1a1a1a;
}
#headerBtnDanger {
    background-color: transparent;
    color: #888888;
    border: none;
    border-radius: 0px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 500;
}
#headerBtnDanger:hover {
    background-color: #f0f0f0;
    color: #2c2c2c;
}

/* Navigation Tab Bar */
#navBar {
    background-color: #e8eaf0;
    border-bottom: 1px solid #c8ccd3;
}
#navBtn {
    background-color: transparent;
    color: #555555;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 500;
    margin: 0px 0px;
}
#navBtn:hover {
    background-color: #dcdee5;
    color: #1a1a1a;
}
#navBtn:checked {
    background-color: #ffffff;
    color: #1a1a1a;
    font-weight: 600;
    border-bottom: 2px solid #2c2c2c;
}

/* Cards */
.card {
    background-color: #ffffff;
    border: 1px solid #d8dce3;
    border-radius: 10px;
    padding: 16px;
}
.card-title {
    color: #6c6c6c;
    font-size: 11px;
    text-transform: uppercase;
}
.card-value {
    color: #2c2c2c;
    font-size: 28px;
    font-weight: bold;
}
.card-accent { /* no accent border */ }

/* Tables — Excel / Minitab exact spreadsheet style */
QTableWidget, QTableView {
    background-color: #ffffff;
    alternate-background-color: #ffffff;
    color: #000000;
    gridline-color: #D4D4D4;
    border: 1px solid #B0B0B0;
    border-radius: 0px;
    selection-background-color: #ffffff;
    selection-color: #000000;
    font-size: 12px;
    font-family: 'Segoe UI', 'Calibri', sans-serif;
    outline: 0;
}
QTableWidget::item, QTableView::item {
    padding: 2px 4px;
    border: none;
    border-radius: 0px;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #F2F2F2;
    color: #000000;
    border: 2px solid #107C41;
    border-radius: 0px;
}
QTableWidget::item:focus, QTableView::item:focus {
    background-color: #ffffff;
    color: #000000;
    border: 2px solid #107C41;
    border-radius: 0px;
}
/* Inline edit field — seamless like Excel */
QTableWidget QLineEdit, QTableView QLineEdit {
    background-color: #ffffff;
    color: #000000;
    border: 2px solid #107C41;
    border-radius: 0px;
    padding: 0px;
    margin: 0px;
    selection-background-color: #107C41;
    selection-color: #ffffff;
}
/* Column headers — flat grey like Excel */
QHeaderView::section:horizontal {
    background-color: #E6E6E6;
    color: #000000;
    padding: 4px 6px;
    border: none;
    border-right: 1px solid #C0C0C0;
    border-bottom: 1px solid #B0B0B0;
    font-weight: 600;
    font-size: 11px;
}
QHeaderView::section:horizontal:hover {
    background-color: #E6E6E6;
}
QHeaderView::section:horizontal:pressed {
    background-color: #D9D9D9;
}
/* Row number headers — left side like Excel */
QHeaderView::section:vertical {
    background-color: #E6E6E6;
    color: #444444;
    padding: 2px 8px;
    border: none;
    border-right: 1px solid #C0C0C0;
    border-bottom: 1px solid #D4D4D4;
    font-size: 11px;
    font-weight: 400;
    min-width: 40px;
}
QHeaderView::section:vertical:hover {
    background-color: #E6E6E6;
}
/* Corner button (top-left) */
QTableCornerButton::section {
    background-color: #E6E6E6;
    border: none;
    border-right: 1px solid #C0C0C0;
    border-bottom: 1px solid #B0B0B0;
}

/* Formula bar — Minitab worksheet style */
#formulaBar {
    background-color: #ffffff;
    border: 1px solid #b0b4bc;
    border-radius: 0px;
    padding: 0px;
    margin: 0px;
}
#cellRef {
    background-color: #f0f1f4;
    color: #1a1a1a;
    border: none;
    border-right: 1px solid #b0b4bc;
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    min-width: 70px;
    max-width: 70px;
}
#cellContent {
    background-color: #ffffff;
    color: #1a1a1a;
    border: none;
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
    padding: 3px 8px;
}

/* Buttons — outline style (SolidWorks / Prelude) */
QPushButton {
    background-color: #ffffff;
    color: #2c2c2c;
    border: 1px solid #2c2c2c;
    border-radius: 0px;
    padding: 8px 20px;
    font-weight: 600;
}
QPushButton:hover { background-color: #f0f0f0; }
QPushButton:pressed { background-color: #e0e0e0; }
QPushButton#primaryBtn { background-color: #ffffff; color: #2c2c2c; border: 1px solid #2c2c2c; }
QPushButton#primaryBtn:hover { background-color: #f0f0f0; }
QPushButton#successBtn { background-color: #ffffff; color: #2c2c2c; border: 1px solid #2c2c2c; }
QPushButton#successBtn:hover { background-color: #f0f0f0; }
QPushButton#dangerBtn { background-color: #ffffff; color: #888888; border: 1px solid #aaaaaa; }
QPushButton#dangerBtn:hover { background-color: #f5f5f5; }

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    color: #2c2c2c;
    border: 1px solid #c8ccd3;
    border-radius: 5px;
    padding: 8px 12px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #3a3a3a;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #2c2c2c;
    selection-background-color: #3a3a3a;
    selection-color: #ffffff;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #d8dce3;
    border-radius: 6px;
    background-color: #f7f8fa;
}
QTabBar::tab {
    background-color: #ecedf2;
    color: #666666;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #2c2c2c;
    font-weight: bold;
    border-bottom: 2px solid #2c2c2c;
}

/* Scrollbar */
QScrollBar:vertical {
    background-color: #f0f1f4;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #b8bcc5;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background-color: #8a8e98; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background-color: #f0f1f4;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background-color: #b8bcc5;
    border-radius: 5px;
    min-width: 30px;
}

/* Progress Bar */
QProgressBar {
    background-color: #e0e2e8;
    border: none;
    border-radius: 5px;
    text-align: center;
    color: #2c2c2c;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #3a3a3a;
    border-radius: 5px;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #d8dce3;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    color: #2c2c2c;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: #3a3a3a;
}

/* Radio & Check */
QRadioButton, QCheckBox { color: #2c2c2c; spacing: 8px; }
QRadioButton::indicator, QCheckBox::indicator {
    width: 18px; height: 18px;
    border: 2px solid #b8bcc5;
    border-radius: 9px;
    background-color: #ffffff;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator:checked, QCheckBox::indicator:checked {
    background-color: #3a3a3a;
    border-color: #3a3a3a;
}

/* Splitter */
QSplitter::handle { background-color: #d8dce3; width: 2px; }

/* ToolTip */
QToolTip {
    background-color: #2c2c2c;
    color: #ffffff;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
}

/* Label */
QLabel { color: #2c2c2c; }
QLabel#heading { font-size: 22px; font-weight: bold; color: #1a1a1a; }
QLabel#subheading { font-size: 14px; color: #6c6c6c; }

/* Dock Widget */
QDockWidget {
    color: #2c2c2c;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #ecedf2;
    padding: 8px;
    border-bottom: 1px solid #d8dce3;
}
"""

LIGHT_STYLE = DARK_STYLE

# ═══════════════════════════════════════════════════════════════════
#  REAL DARK THEME — Production-grade dark mode
# ═══════════════════════════════════════════════════════════════════
REAL_DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}
QMenuBar::item:selected { background-color: #313244; }
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
}
QMenu::item:selected { background-color: #313244; }
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
}

/* Header Bar */
#headerBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
}
#appTitle {
    color: #cdd6f4;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 0 4px;
}
#headerUser {
    color: #a6adc8;
    font-size: 11px;
    font-weight: 500;
    padding: 0 12px;
}
#headerBtn {
    background-color: transparent;
    color: #cdd6f4;
    border: none;
    border-radius: 0px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 500;
}
#headerBtn:hover {
    background-color: #313244;
    color: #ffffff;
}
#headerBtnDanger {
    background-color: transparent;
    color: #a6adc8;
    border: none;
    border-radius: 0px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 500;
}
#headerBtnDanger:hover {
    background-color: #45475a;
    color: #f38ba8;
}

/* Navigation Tab Bar */
#navBar {
    background-color: #11111b;
    border-bottom: 1px solid #313244;
}
#navBtn {
    background-color: transparent;
    color: #a6adc8;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 500;
    margin: 0px;
}
#navBtn:hover {
    background-color: #313244;
    color: #cdd6f4;
}
#navBtn:checked {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-weight: 600;
    border-bottom: 2px solid #89b4fa;
}

/* Cards */
.card {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 16px;
}

/* Tables */
QTableWidget, QTableView {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #45475a;
    border-radius: 0px;
    selection-background-color: #1e1e2e;
    selection-color: #cdd6f4;
    font-size: 12px;
    font-family: 'Segoe UI', 'Calibri', sans-serif;
    outline: 0;
}
QTableWidget::item, QTableView::item {
    padding: 2px 4px;
    border: none;
    border-radius: 0px;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #313244;
    color: #cdd6f4;
    border: 2px solid #89b4fa;
    border-radius: 0px;
}
QTableWidget::item:focus, QTableView::item:focus {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 2px solid #89b4fa;
    border-radius: 0px;
}
QTableWidget QLineEdit, QTableView QLineEdit {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 2px solid #89b4fa;
    border-radius: 0px;
    padding: 0px;
    margin: 0px;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QHeaderView::section:horizontal {
    background-color: #313244;
    color: #cdd6f4;
    padding: 4px 6px;
    border: none;
    border-right: 1px solid #45475a;
    border-bottom: 1px solid #45475a;
    font-weight: 600;
    font-size: 11px;
}
QHeaderView::section:vertical {
    background-color: #313244;
    color: #a6adc8;
    padding: 2px 8px;
    border: none;
    border-right: 1px solid #45475a;
    border-bottom: 1px solid #313244;
    font-size: 11px;
    font-weight: 400;
    min-width: 40px;
}
QTableCornerButton::section {
    background-color: #313244;
    border: none;
    border-right: 1px solid #45475a;
    border-bottom: 1px solid #45475a;
}

/* Formula bar */
#formulaBar {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 0px;
    padding: 0px;
    margin: 0px;
}
#cellRef {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    border-right: 1px solid #45475a;
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    min-width: 70px;
    max-width: 70px;
}
#cellContent {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: none;
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
    padding: 3px 8px;
}

/* Buttons */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 0px;
    padding: 8px 20px;
    font-weight: 600;
}
QPushButton:hover { background-color: #45475a; color: #ffffff; }
QPushButton:pressed { background-color: #585b70; }
QPushButton#primaryBtn { background-color: #313244; color: #89b4fa; border: 1px solid #89b4fa; }
QPushButton#primaryBtn:hover { background-color: #45475a; }
QPushButton#successBtn { background-color: #313244; color: #a6e3a1; border: 1px solid #a6e3a1; }
QPushButton#successBtn:hover { background-color: #45475a; }
QPushButton#dangerBtn { background-color: #313244; color: #f38ba8; border: 1px solid #585b70; }
QPushButton#dangerBtn:hover { background-color: #45475a; color: #f38ba8; }

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 8px 12px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #89b4fa;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 6px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-weight: bold;
    border-bottom: 2px solid #89b4fa;
}

/* Scrollbar */
QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background-color: #585b70; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background-color: #181825;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 5px;
    min-width: 30px;
}

/* Progress Bar */
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 5px;
    text-align: center;
    color: #cdd6f4;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 5px;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    color: #cdd6f4;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: #89b4fa;
}

/* Radio & Check */
QRadioButton, QCheckBox { color: #cdd6f4; spacing: 8px; }
QRadioButton::indicator, QCheckBox::indicator {
    width: 18px; height: 18px;
    border: 2px solid #45475a;
    border-radius: 9px;
    background-color: #313244;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator:checked, QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

/* Splitter */
QSplitter::handle { background-color: #313244; width: 2px; }

/* ToolTip */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px;
}

/* Labels */
QLabel { color: #cdd6f4; }
QLabel#heading { font-size: 22px; font-weight: bold; color: #cdd6f4; }
QLabel#subheading { font-size: 14px; color: #a6adc8; }

/* Dock Widget */
QDockWidget {
    color: #cdd6f4;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #181825;
    padding: 8px;
    border-bottom: 1px solid #313244;
}
"""
