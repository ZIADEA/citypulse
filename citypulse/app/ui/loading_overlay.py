from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QFont


class LoadingOverlay(QWidget):
    """Semi-transparent overlay with animated spinner text shown over a parent widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        self.hide()

        self._angle = 0
        self._message = "Chargement..."
        self._dots = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self, message="Chargement..."):
        self._message = message
        self._dots = 0
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self._timer.start(400)

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._dots = (self._dots + 1) % 4
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Semi-transparent backdrop
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # Central rounded card
        card_w, card_h = 280, 100
        cx = (self.width() - card_w) // 2
        cy = (self.height() - card_h) // 2
        p.setBrush(QColor(30, 30, 46, 240))
        p.setPen(QColor(137, 180, 250, 80))
        p.drawRoundedRect(cx, cy, card_w, card_h, 12, 12)

        # Animated dots
        dots_str = "." * self._dots
        text = f"{self._message}{dots_str}"
        p.setPen(QColor(205, 214, 244))
        p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        p.drawText(cx, cy, card_w, card_h, Qt.AlignmentFlag.AlignCenter, text)

        p.end()

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
