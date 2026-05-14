"""topbar.py — Barre supérieure : fil d'Ariane + NotificationBell + user + déco."""
import logging
from PyQt6.QtWidgets import (
  QWidget, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt
from .notification_bell import NotificationBell
from ..lucide_icons import lucide_icon, lucide_icon_size, lucide_pixmap

logger = logging.getLogger(__name__)

C = {
  "bg":    "#162840",
  "bg2":   "#162840",
  "accent": "#00D4FF",
  "text":   "#E8F4FD",
  "text2":  "#7FA8C0",
  "border": "#1E3A5F",
  "hover":  "#2A4A66",
  "danger": "#FF4757",
}


class TopBar(QWidget):
  """
  Barre supérieure h=48px :
   [Accueil › Page] ── stretch ── [Counts] [Bell] [User] [Logout]
  """

  def __init__(self, main_window, parent=None):
    super().__init__(parent)
    self.main_window = main_window
    self.setObjectName("topBar")
    self.setFixedHeight(48)
    self.setStyleSheet(
      f"QWidget#topBar{{background:{C['bg']};border-bottom:1px solid {C['border']};}}"
    )

    row = QHBoxLayout(self)
    row.setContentsMargins(20, 0, 12, 0)
    row.setSpacing(8)

    # ── Breadcrumb ──────────────────────────────────────────────────────
    self._home_lbl = QLabel("CityPulse")
    self._home_lbl.setStyleSheet(
      f"color:{C['accent']};font-size:13px;font-weight:700;"
      "background:transparent;border:none;"
    )
    row.addWidget(self._home_lbl)

    self._sep_lbl = QLabel("›")
    self._sep_lbl.setObjectName("breadcrumbSep")
    row.addWidget(self._sep_lbl)

    self._page_lbl = QLabel("Tableau de bord")
    self._page_lbl.setObjectName("breadcrumb")
    row.addWidget(self._page_lbl)

    row.addStretch()

    # ── Status counts ───────────────────────────────────────────────────
    self._counts_lbl = QLabel()
    self._counts_lbl.setStyleSheet(
      f"color:{C['text2']};font-size:11px;background:transparent;border:none;"
    )
    row.addWidget(self._counts_lbl)

    _sep = QLabel("│")
    _sep.setStyleSheet(f"color:{C['border']};background:transparent;border:none;")
    row.addWidget(_sep)

    # ── Notification bell ───────────────────────────────────────────────
    self.bell = NotificationBell(main_window=main_window)
    row.addWidget(self.bell)

    _sep2 = QLabel("│")
    _sep2.setStyleSheet(f"color:{C['border']};background:transparent;border:none;")
    row.addWidget(_sep2)

    # ── User info (icône Lucide + nom, sans emoji) ─────────────────────
    self._user_row = QWidget()
    self._user_row.setStyleSheet("background:transparent;")
    ur = QHBoxLayout(self._user_row)
    ur.setContentsMargins(0, 0, 0, 0)
    ur.setSpacing(6)
    self._user_icon = QLabel()
    self._user_icon.setPixmap(lucide_pixmap("user", C["text"], 16))
    self._user_icon.setStyleSheet("background:transparent;")
    self._user_lbl = QLabel()
    self._user_lbl.setStyleSheet(
      f"color:{C['text']};font-size:13px;font-weight:600;"
      "background:transparent;border:none;"
    )
    ur.addWidget(self._user_icon)
    ur.addWidget(self._user_lbl)
    row.addWidget(self._user_row)

    self._role_lbl = QLabel()
    self._role_lbl.setStyleSheet(
      f"color:{C['text2']};font-size:11px;background:transparent;border:none;"
    )
    row.addWidget(self._role_lbl)

    _sep3 = QLabel("│")
    _sep3.setStyleSheet(f"color:{C['border']};background:transparent;border:none;")
    row.addWidget(_sep3)

    # ── Logout (pictogramme Lucide) ────────────────────────────────────
    self._logout_btn = QPushButton("")
    self._logout_btn.setIcon(lucide_icon("log-out", C["danger"], 18))
    self._logout_btn.setIconSize(lucide_icon_size(18))
    self._logout_btn.setFixedSize(36, 36)
    self._logout_btn.setToolTip("Déconnexion")
    self._logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._logout_btn.setStyleSheet(
      f"QPushButton{{background:transparent;"
      f"border:1px solid {C['danger']};border-radius:6px;padding:0;}}"
      f"QPushButton:hover{{background:rgba(255,71,87,31);}}"
    )
    if hasattr(main_window, "_logout"):
      self._logout_btn.clicked.connect(main_window._logout)
    row.addWidget(self._logout_btn)

  # ── Public API ────────────────────────────────────────────────────────────
  def refresh_breadcrumb(self, page_name: str):
    self._page_lbl.setText(page_name)

  def refresh_user(self, user: dict):
    name = user.get("full_name") or user.get("username", "")
    role = user.get("role", "").capitalize()
    self._user_lbl.setText(name)
    self._role_lbl.setText(f"({role})")

  def set_counts(self, text: str):
    self._counts_lbl.setText(text)
