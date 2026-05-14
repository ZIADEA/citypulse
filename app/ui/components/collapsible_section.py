"""collapsible_section.py — Section repliable avec animation 150 ms."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import (
  Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QSize
)
from PyQt6.QtGui import QFont

C = {
  "bg":   "#112240",
  "bg2":   "#0A1628",
  "accent": "#00D4FF",
  "text":  "#E8F4FD",
  "text2":  "#8899AA",
  "border": "#1E3A5F",
  "hover":  "#1A3A5C",
}


class CollapsibleSection(QWidget):
  def __init__(self, title: str, collapsed: bool = False, parent=None):
    super().__init__(parent)
    self._collapsed = collapsed
    self._content_h = 0
    self._current_title = title

    root = QVBoxLayout(self)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # Header button
    self._header = QPushButton()
    self._header.setFixedHeight(40)
    self._header.setCursor(Qt.CursorShape.PointingHandCursor)
    self._header.setStyleSheet(
      f"QPushButton{{background:{C['bg2']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:6px;"
      "text-align:left;padding:0 12px;font-size:13px;font-weight:600;}}"
      f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
    )
    self._update_header_text(title)
    self._header.clicked.connect(self._toggle)
    root.addWidget(self._header)

    # Content wrapper
    self._content_frame = QFrame()
    self._content_frame.setStyleSheet(
      f"QFrame{{background:{C['bg']};border:1px solid {C['border']};"
      "border-top:none;border-bottom-left-radius:6px;border-bottom-right-radius:6px;padding:0;}}"
    )
    self._inner = QVBoxLayout(self._content_frame)
    self._inner.setContentsMargins(12, 8, 12, 8)
    self._inner.setSpacing(6)
    root.addWidget(self._content_frame)

    if collapsed:
      self._content_frame.setMaximumHeight(0)
      self._content_frame.setVisible(False)

  def _update_header_text(self, title: str):
    arrow = ">" if self._collapsed else "-"
    self._header.setText(f" {arrow} {title}")

  def set_title(self, title: str):
    self._current_title = title
    self._update_header_text(title)

  def _toggle(self):
    self._collapsed = not self._collapsed
    self._update_header_text(self._current_title)

    target_h = 0 if self._collapsed else self._content_frame.sizeHint().height()
    if not self._collapsed:
      self._content_frame.setVisible(True)
      self._content_frame.setMaximumHeight(0)

    anim = QPropertyAnimation(self._content_frame, b"maximumHeight", self)
    anim.setDuration(150)
    anim.setStartValue(self._content_frame.maximumHeight())
    anim.setEndValue(target_h if not self._collapsed else 0)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
    if self._collapsed:
      anim.finished.connect(lambda: self._content_frame.setVisible(False))
    self._anim = anim
    anim.start()

  def add_widget(self, widget: QWidget):
    self._inner.addWidget(widget)

  def content_layout(self) -> QVBoxLayout:
    return self._inner
