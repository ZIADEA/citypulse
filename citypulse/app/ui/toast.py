"""
Système de notifications toast non-intrusives.
Affiche des bandeaux temporaires en bas à droite de la fenêtre principale.
"""

from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont


class ToastNotification(QLabel):
    """Bandeau de notification éphémère style macOS / Windows 11."""

    STYLES = {
        "info":    ("background-color: #323248; color: #cdd6f4; border-left: 4px solid #89b4fa;",
                    "background-color: #f0f4ff; color: #1a1a1a; border-left: 4px solid #2563eb;"),
        "success": ("background-color: #1e3a2e; color: #a6e3a1; border-left: 4px solid #a6e3a1;",
                    "background-color: #f0fdf4; color: #166534; border-left: 4px solid #22c55e;"),
        "warning": ("background-color: #3a3520; color: #f9e2af; border-left: 4px solid #f9e2af;",
                    "background-color: #fffbeb; color: #92400e; border-left: 4px solid #f59e0b;"),
        "error":   ("background-color: #3a1e28; color: #f38ba8; border-left: 4px solid #f38ba8;",
                    "background-color: #fef2f2; color: #991b1b; border-left: 4px solid #ef4444;"),
    }

    _active_toasts: list = []

    def __init__(self, parent: QWidget, message: str, level: str = "info",
                 duration_ms: int = 3500, theme: str = "light"):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setText(message)
        self.setFont(QFont("Segoe UI", 11))

        dark_style, light_style = self.STYLES.get(level, self.STYLES["info"])
        base = dark_style if theme == "dark" else light_style

        self.setStyleSheet(
            f"{base} border-radius: 6px; padding: 12px 18px; "
            f"border-top: none; border-right: none; border-bottom: none;"
        )
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)
        self.adjustSize()
        self.setFixedHeight(max(self.sizeHint().height(), 44))

        # Position — stack above existing toasts
        offset_y = 12
        for t in ToastNotification._active_toasts:
            if t.isVisible():
                offset_y += t.height() + 8
        ToastNotification._active_toasts.append(self)

        pw = parent.width()
        ph = parent.height()
        self.move(pw - self.width() - 20, ph - self.height() - offset_y)

        # Opacity animation
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(250)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(400)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self._cleanup)

        self.show()
        self.raise_()
        self._fade_in.start()

        QTimer.singleShot(duration_ms, self._start_fade_out)

    def _start_fade_out(self):
        self._fade_out.start()

    def _cleanup(self):
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
        self.deleteLater()


def show_toast(parent: QWidget, message: str, level: str = "info",
               duration_ms: int = 3500, theme: str = "light"):
    """Shortcut to display a toast notification.

    level: "info" | "success" | "warning" | "error"
    """
    return ToastNotification(parent, message, level, duration_ms, theme)
