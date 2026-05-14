"""
lucide_icons.py — Icônes vectorielles Lucide (stroke) → QPixmap / QIcon.
Même principe que la sidebar MainWindow, réutilisable pour boutons d’action.
"""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

_TRANSPARENT = QColor(0, 0, 0, 0)  # Python 3.14 : Qt.GlobalColor.transparent crashe

try:
    from PyQt6.QtSvg import QSvgRenderer

    _HAS_SVG = True
except ImportError:
    QSvgRenderer = None  # type: ignore
    _HAS_SVG = False

# Chemins stroke-only, viewBox 0 0 24 24 (jeu Lucide)
_PATHS: dict[str, str] = {
    "pencil": (
        "M12 20h9 M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"
    ),
    "map": (
        "M1 6v16l7-4 8 4 7-4V2l-7 4-8-4-7 4z M8 2v16 M16 6v16"
    ),
    "trash-2": (
        "M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
        " M10 11v6 M14 11v6"
    ),
    "calendar": (
        "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"
    ),
    "copy": (
        "M20 8h-10a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10a2 2 0 0 0-2-2Z"
        " M12 2h6a2 2 0 0 1 2 2v6"
    ),
    "file-text": (
        "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
        " M14 2v6h6 M16 13H8 M16 17H8 M10 9H8"
    ),
    "package": (
        "M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z M3 6h18 M16 10a4 4 0 1 1-8 0"
    ),
    "archive": (
        "M21 8v13H3V8 M1 3h22v5H1z M10 12h4"
    ),
    "bell": (
        "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9 M10.3 21a1.94 1.94 0 0 0 3.4 0"
    ),
    "log-out": (
        "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9"
    ),
    "user": (
        "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"
    ),
    "help-circle": (
        "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"
        " M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"
        " M12 17h.01"
    ),
    "eye": (
        "M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"
        " M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"
    ),
    "search": (
        "M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16z M21 21l-4.35-4.35"
    ),
    "maximize": (
        "M8 3H5a2 2 0 0 0-2 2v3 M21 8V5a2 2 0 0 0-2-2h-3"
        " M3 16v3a2 2 0 0 0 2 2h3 M16 21h3a2 2 0 0 0 2-2v-3"
    ),
    "download": (
        "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3"
    ),
    "columns": (
        "M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"
        " M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7 M12 3v18"
    ),
    "move": (
        "M5 9l-3 3 3 3 M9 5l3-3 3 3 M15 19l-3 3-3-3 M19 9l3 3-3 3"
        " M2 12h20 M12 2v20"
    ),
    "square": (
        "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
    ),
    "crosshair": (
        "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"
        " M22 12h-4 M6 12H2 M12 6V2 M12 22v-4"
    ),
    "globe": (
        "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"
        " M2 12h20"
        " M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
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
}


def lucide_pixmap(key: str, color: str, size: int = 18) -> QPixmap:
    d = _PATHS.get(key, "")
    if not d or not _HAS_SVG:
        pm = QPixmap(size, size)
        pm.fill(_TRANSPARENT)
        return pm
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">'
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
        "stroke-linecap=\"round\" stroke-linejoin=\"round\"/></svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size, size)
    pm.fill(_TRANSPARENT)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def lucide_icon(key: str, color: str, size: int = 18) -> QIcon:
    return QIcon(lucide_pixmap(key, color, size))


def lucide_icon_size(size: int = 18) -> QSize:
    return QSize(size, size)


def apply_action_button(btn, lucide_key: str, icon_color: str, bg: str, hover_bg: str, icon_px: int = 16) -> None:
    """Bouton icône seule : fond + survol QSS, pictogramme Lucide coloré."""
    btn.setText("")
    btn.setIcon(lucide_icon(lucide_key, icon_color, icon_px))
    btn.setIconSize(QSize(icon_px, icon_px))
    btn.setStyleSheet(
        f"QPushButton{{background:{bg};border:none;border-radius:4px;padding:4px;}}"
        f"QPushButton:hover{{background:{hover_bg};}}"
    )
