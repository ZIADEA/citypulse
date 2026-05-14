"""loading_spinner.py — Spinner QPainter pur (arc tournant)."""
import math
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont

C = {
  "accent": "#00D4FF",
  "text2": "#8899AA",
  "bg":   "rgba(13,27,42,217)",
}


class LoadingSpinner(QWidget):
  def __init__(self, parent=None, size: int = 48):
    super().__init__(parent)
    self._size = size
    self._angle = 0
    self._running = False
    self._msg = ""

    self._timer = QTimer(self)
    self._timer.setInterval(50)
    self._timer.timeout.connect(self._tick)

    root = QVBoxLayout(self)
    root.setAlignment(Qt.AlignmentFlag.AlignCenter)
    root.setSpacing(10)

    self._arc_placeholder = QWidget()
    self._arc_placeholder.setFixedSize(size, size)
    root.addWidget(self._arc_placeholder, alignment=Qt.AlignmentFlag.AlignCenter)

    self._msg_lbl = QLabel()
    self._msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._msg_lbl.setStyleSheet(
      f"color:{C['text2']};font-size:12px;background:transparent;border:none;"
    )
    root.addWidget(self._msg_lbl)
    self.hide()

  def start(self, msg: str = "Chargement…"):
    self._msg = msg
    self._msg_lbl.setText(msg)
    self._running = True
    self._timer.start()
    self.show()
    self.raise_()

  def stop(self):
    self._running = False
    self._timer.stop()
    self.hide()

  def _tick(self):
    self._angle = (self._angle + 12) % 360
    self._arc_placeholder.update()

  def paintEvent(self, event):
    if not self._running:
      return
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background overlay (if parented)
    painter.fillRect(self.rect(), QColor(13, 27, 42, 180))

    s = self._size
    cx = self.width() // 2 - s // 2
    cy = self.height() // 2 - s // 2 - 15
    rect = QRectF(cx, cy, s, s)

    # Background arc
    pen = QPen(QColor(30, 58, 95), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawArc(rect, 0, 360 * 16)

    # Foreground arc (spinning)
    pen2 = QPen(QColor(0, 212, 255), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen2)
    start_angle = (90 - self._angle) * 16
    painter.drawArc(rect, start_angle, 270 * 16)

    painter.end()
