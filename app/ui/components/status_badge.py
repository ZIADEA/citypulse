"""status_badge.py — Badge de statut coloré."""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

_STYLES: dict[str, tuple[str, str]] = {
  "success": ("#00FF88", "rgba(0,255,136,38)"),
  "warning": ("#FFB800", "rgba(255,184,0,38)"),
  "danger": ("#FF4757", "rgba(255,71,87,38)"),
  "info":  ("#00D4FF", "rgba(0,212,255,38)"),
  "neutral": ("#8899AA", "rgba(136,153,170,38)"),
  "pending": ("#FFB800", "rgba(255,184,0,38)"),
  "active": ("#00FF88", "rgba(0,255,136,38)"),
}
_DEFAULT = ("#8899AA", "rgba(136,153,170,38)")


class StatusBadge(QLabel):
  def __init__(self, status: str = "neutral", text: str = "", parent=None):
    super().__init__(parent)
    self.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.update_status(status, text or status.capitalize())

  def update_status(self, status: str, text: str = ""):
    color, bg = _STYLES.get(status.lower(), _DEFAULT)
    label = text or status.capitalize()
    self.setText(label)
    self.setStyleSheet(
      f"color:{color};background:{bg};border:1px solid {color};"
      "border-radius:10px;padding:2px 10px;font-size:11px;font-weight:600;"
    )
