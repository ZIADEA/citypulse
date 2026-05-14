"""section_header.py — En-tête de section avec ligne accent."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

C = {
  "accent": "#00D4FF",
  "text":  "#E8F4FD",
  "text2": "#8899AA",
  "border": "#1E3A5F",
  "hover": "#1A3A5C",
  "bg":   "#112240",
}


class SectionHeader(QWidget):
  def __init__(
    self,
    title: str,
    subtitle: str = "",
    action_text: str = "",
    action_callback=None,
    parent=None,
  ):
    super().__init__(parent)
    root = QVBoxLayout(self)
    root.setContentsMargins(0, 0, 0, 12)
    root.setSpacing(6)

    top = QHBoxLayout()
    top.setSpacing(12)

    # Left: accent bar + title block
    bar = QFrame()
    bar.setFixedSize(4, 32 if subtitle else 22)
    bar.setStyleSheet(
      f"background:{C['accent']};border-radius:2px;border:none;"
    )
    top.addWidget(bar, alignment=Qt.AlignmentFlag.AlignVCenter)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    self._title_lbl = QLabel(title)
    self._title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    self._title_lbl.setStyleSheet(
      f"color:{C['text']};background:transparent;border:none;"
    )
    text_col.addWidget(self._title_lbl)

    self._subtitle_lbl: QLabel | None = None
    if subtitle:
      self._subtitle_lbl = QLabel(subtitle)
      self._subtitle_lbl.setStyleSheet(
        f"color:{C['text2']};font-size:11px;background:transparent;border:none;"
      )
      text_col.addWidget(self._subtitle_lbl)
    top.addLayout(text_col, 1)

    if action_text and action_callback:
      btn = QPushButton(action_text)
      btn.setObjectName("secondaryBtn")
      btn.setFixedHeight(32)
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      btn.clicked.connect(action_callback)
      top.addWidget(btn)

    root.addLayout(top)

    # Separator
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:{C['border']};border:none;")
    root.addWidget(sep)

  def set_title(self, title: str):
    self._title_lbl.setText(title)

  def set_subtitle(self, subtitle: str):
    if self._subtitle_lbl is not None:
      self._subtitle_lbl.setText(subtitle)
