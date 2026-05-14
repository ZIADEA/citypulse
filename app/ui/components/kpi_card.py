"""kpi_card.py — Carte KPI animée au survol."""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

C = {
  "bg":   "#112240",
  "hover":  "#1A3A5C",
  "accent": "#00D4FF",
  "success": "#00FF88",
  "warning": "#FFB800",
  "danger": "#FF4757",
  "text":  "#E8F4FD",
  "text2":  "#8899AA",
  "border": "#1E3A5F",
}


class KPICard(QFrame):
  def __init__(
    self,
    title: str,
    value: str,
    unit: str = "",
    # Emoji retiré : pictogramme texte.
    icon: str = "KPI",
    trend: str = "",
    trend_up: bool = True,
    parent=None,
  ):
    super().__init__(parent)
    self.setMinimumSize(200, 110)
    self.setCursor(Qt.CursorShape.PointingHandCursor)
    self._normal_style = (
      f"QFrame{{background:{C['bg']};border:1px solid {C['border']};"
      "border-radius:10px;padding:0;}}"
    )
    self._hover_style = (
      f"QFrame{{background:{C['hover']};border:1px solid {C['accent']};"
      "border-radius:10px;padding:0;}}"
    )
    self.setStyleSheet(self._normal_style)

    root = QVBoxLayout(self)
    root.setContentsMargins(16, 14, 16, 14)
    root.setSpacing(6)

    # Header: icon + title
    header = QHBoxLayout()
    header.setSpacing(8)
    self._icon_lbl = QLabel(icon)
    self._icon_lbl.setStyleSheet("font-size:18px;background:transparent;border:none;")
    header.addWidget(self._icon_lbl)
    self._title_lbl = QLabel(title)
    self._title_lbl.setStyleSheet(
      f"color:{C['text2']};font-size:11px;font-weight:600;"
      "background:transparent;border:none;"
    )
    header.addWidget(self._title_lbl, 1)
    root.addLayout(header)

    # Value row
    val_row = QHBoxLayout()
    val_row.setSpacing(4)
    self._value_lbl = QLabel(str(value))
    self._value_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    self._value_lbl.setStyleSheet(
      f"color:{C['text']};background:transparent;border:none;"
    )
    val_row.addWidget(self._value_lbl)
    if unit:
      self._unit_lbl = QLabel(unit)
      self._unit_lbl.setStyleSheet(
        f"color:{C['text2']};font-size:12px;background:transparent;border:none;"
      )
      self._unit_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom)
      val_row.addWidget(self._unit_lbl)
    val_row.addStretch()
    root.addLayout(val_row)

    # Trend
    self._trend_lbl = QLabel()
    self._trend_lbl.setStyleSheet("background:transparent;border:none;font-size:11px;")
    root.addWidget(self._trend_lbl)
    self._set_trend(trend, trend_up)

  def _set_trend(self, trend: str, trend_up: bool):
    if not trend:
      self._trend_lbl.setText("")
      return
    color = C["success"] if trend_up else C["danger"]
    arrow = "+" if trend_up else "-"
    self._trend_lbl.setText(f'<span style="color:{color};">{arrow} {trend}</span>')

  def update(self, value: str, trend: str = "", trend_up: bool = True):
    self._value_lbl.setText(str(value))
    self._set_trend(trend, trend_up)

  def set_value(self, value: str, trend: str = "", trend_up: bool = True):
    """Alias de update() — nom explicite pour les compteurs métier."""
    self.update(value, trend, trend_up)

  def enterEvent(self, event):
    self.setStyleSheet(self._hover_style)
    super().enterEvent(event)

  def leaveEvent(self, event):
    self.setStyleSheet(self._normal_style)
    super().leaveEvent(event)
