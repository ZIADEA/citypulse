"""empty_state.py — État vide illustré."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

C = {
  "text":  "#E8F4FD",
  "text2": "#8899AA",
  "accent": "#00D4FF",
}


class EmptyState(QWidget):
  def __init__(
    self,
    # Emoji retiré : pictogramme texte.
    icon: str = "EMPTY",
    title: str = "Aucune donnée",
    subtitle: str = "",
    action_text: str = "",
    action_callback=None,
    parent=None,
  ):
    super().__init__(parent)
    root = QVBoxLayout(self)
    root.setContentsMargins(40, 40, 40, 40)
    root.setSpacing(12)
    root.setAlignment(Qt.AlignmentFlag.AlignCenter)

    icon_lbl = QLabel(icon)
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl.setStyleSheet(
      "font-size:52px;background:transparent;border:none;"
    )
    root.addWidget(icon_lbl)

    title_lbl = QLabel(title)
    title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_lbl.setStyleSheet(
      f"color:{C['text']};background:transparent;border:none;"
    )
    root.addWidget(title_lbl)

    if subtitle:
      sub_lbl = QLabel(subtitle)
      sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
      sub_lbl.setWordWrap(True)
      sub_lbl.setStyleSheet(
        f"color:{C['text2']};font-size:12px;background:transparent;border:none;"
      )
      root.addWidget(sub_lbl)

    if action_text and action_callback:
      root.addSpacing(8)
      btn = QPushButton(action_text)
      btn.setObjectName("primaryBtn")
      btn.setFixedHeight(38)
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      btn.clicked.connect(action_callback)
      root.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
