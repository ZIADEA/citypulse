"""confirm_dialog.py — Boîte de confirmation réutilisable."""
from PyQt6.QtWidgets import (
  QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

C = {
  "bg":   "#112240",
  "border": "#1E3A5F",
  "accent": "#00D4FF",
  "danger": "#FF4757",
  "warning": "#FFB800",
  "success": "#00FF88",
  "text":  "#E8F4FD",
  "text2":  "#8899AA",
  "hover":  "#1A3A5C",
  "bg_input":"#1A2E4A",
}

_ICONS = {
  # Emoji retirés : on utilise des pictogrammes texte simples.
  "warning": ("!", C["warning"]),
  "danger": ("DEL", C["danger"]),
  "info":  ("i", C["accent"]),
  "success": ("OK", C["success"]),
}

# Texte sur fond accent (aligné sur THEMES["dark"]["accent_text"] dans styles.py)
_ACCENT_FG = "#0D1B2A"


def _dialog_qss() -> str:
  """QSS embarqué : boutons #primaryBtn / #secondaryBtn / #dangerBtn / #ghostBtn / #iconBtn lisibles si le QSS global est cassé."""
  r6 = (
    "border-top-left-radius:6px;border-top-right-radius:6px;"
    "border-bottom-left-radius:6px;border-bottom-right-radius:6px;"
  )
  r4 = (
    "border-top-left-radius:4px;border-top-right-radius:4px;"
    "border-bottom-left-radius:4px;border-bottom-right-radius:4px;"
  )
  at = _ACCENT_FG
  return (
    f"QDialog{{background:{C['bg']};border:1px solid {C['border']};"
    f"border-top-left-radius:12px;border-top-right-radius:12px;"
    f"border-bottom-left-radius:12px;border-bottom-right-radius:12px;"
    f"color:{C['text']};}}"
    f"QPushButton#primaryBtn{{"
    f"background-color:{C['accent']};color:{at};border:none;{r6}"
    f"padding:6px 18px;font-size:13px;font-weight:600;min-height:32px;}}"
    f"QPushButton#primaryBtn:default{{background-color:{C['accent']};color:{at};}}"
    f"QPushButton#primaryBtn:hover{{"
    f"background-color:{C['accent']};border:1px solid {C['text2']};color:{at};}}"
    f"QPushButton#primaryBtn:pressed{{background-color:{C['accent']};color:{at};}}"
    f"QPushButton#primaryBtn:disabled{{"
    f"background-color:{C['border']};color:{C['text2']};border:none;{r6}}}"
    f"QPushButton#secondaryBtn{{"
    f"background-color:{C['bg_input']};color:{C['text']};"
    f"border:1px solid {C['border']};{r6}"
    f"padding:6px 16px;font-size:13px;font-weight:500;min-height:32px;}}"
    f"QPushButton#secondaryBtn:default{{"
    f"background-color:{C['bg_input']};color:{C['text']};border:1px solid {C['border']};}}"
    f"QPushButton#secondaryBtn:hover{{"
    f"background-color:{C['hover']};border-color:{C['accent']};color:{C['text']};}}"
    f"QPushButton#secondaryBtn:pressed{{"
    f"background-color:{C['bg_input']};color:{C['text']};border:1px solid {C['border']};}}"
    f"QPushButton#secondaryBtn:disabled{{"
    f"background-color:{C['bg']};color:{C['text2']};border:1px solid {C['border']};}}"
    f"QPushButton#dangerBtn{{"
    f"background-color:transparent;color:{C['danger']};"
    f"border:1px solid {C['danger']};{r6}"
    f"padding:6px 16px;font-size:13px;font-weight:500;min-height:32px;}}"
    f"QPushButton#dangerBtn:default{{"
    f"background-color:transparent;color:{C['danger']};border:1px solid {C['danger']};}}"
    f"QPushButton#dangerBtn:hover{{"
    f"background-color:rgba(255,71,87,0.15);color:{C['danger']};border:1px solid {C['danger']};}}"
    f"QPushButton#dangerBtn:pressed{{"
    f"background-color:rgba(255,71,87,0.22);color:{C['danger']};}}"
    f"QPushButton#dangerBtn:disabled{{"
    f"background-color:{C['bg']};color:{C['text2']};border:1px solid {C['border']};}}"
    f"QPushButton#ghostBtn{{"
    f"background-color:transparent;color:{C['text2']};border:none;{r6}"
    f"padding:6px 12px;font-size:12px;min-height:28px;}}"
    f"QPushButton#ghostBtn:hover{{background-color:{C['hover']};color:{C['text']};}}"
    f"QPushButton#ghostBtn:pressed{{background-color:{C['hover']};color:{C['text']};}}"
    f"QPushButton#ghostBtn:disabled{{background-color:transparent;color:{C['text2']};}}"
    f"QPushButton#iconBtn{{"
    f"background-color:transparent;color:{C['text2']};border:none;{r4}padding:4px;min-width:28px;min-height:28px;}}"
    f"QPushButton#iconBtn:hover{{background-color:{C['hover']};color:{C['text']};}}"
    f"QPushButton#iconBtn:pressed{{background-color:{C['hover']};color:{C['text']};}}"
    f"QPushButton#iconBtn:disabled{{background-color:transparent;color:{C['text2']};}}"
    f"QDialog QDialogButtonBox QPushButton{{"
    f"background-color:{C['bg_input']};color:{C['text']};border:1px solid {C['border']};{r6}"
    f"padding:7px 18px;font-size:12px;min-width:72px;min-height:32px;}}"
    f"QDialog QDialogButtonBox QPushButton:hover{{"
    f"background-color:{C['hover']};color:{C['text']};border-color:{C['accent']};}}"
    f"QDialog QDialogButtonBox QPushButton:pressed{{"
    f"background-color:{C['bg_input']};color:{C['text']};}}"
    f"QDialog QDialogButtonBox QPushButton:disabled{{"
    f"background-color:{C['bg']};color:{C['text2']};border-color:{C['border']};}}"
  )


def dialog_base_qss() -> str:
  """Même QSS que `_dialog_qss()` — à fusionner sur la racine des QDialog lourds utilisant des boutons nommés."""
  return _dialog_qss()


def light_dialog_buttons_qss() -> str:
  """QPushButton + #primaryBtn sur fond clair (aide, import colonnes) — contraste garanti sans forcer le thème sombre."""
  return (
    "QPushButton{background-color:#ECEFF1;color:#1A1A2E;border:1px solid #B0BEC5;"
    "border-top-left-radius:6px;border-top-right-radius:6px;"
    "border-bottom-left-radius:6px;border-bottom-right-radius:6px;"
    "padding:8px 16px;font-size:13px;font-weight:500;min-height:32px;}"
    "QPushButton:hover{background-color:#CFD8DC;color:#1A1A2E;border-color:#1565C0;}"
    "QPushButton:pressed{background-color:#B0BEC5;color:#1A1A2E;}"
    "QPushButton:disabled{background-color:#F5F5F5;color:#9E9E9E;border-color:#E0E0E0;}"
    "QPushButton#primaryBtn{background-color:#1565C0;color:#FFFFFF;border:none;font-weight:600;}"
    "QPushButton#primaryBtn:hover{background-color:#1565C0;border:1px solid #0D47A1;color:#FFFFFF;}"
    "QPushButton#primaryBtn:pressed{background-color:#0D47A1;color:#FFFFFF;}"
    "QPushButton#primaryBtn:disabled{background-color:#CFD8DC;color:#78909C;border:none;}"
  )


class ConfirmDialog(QDialog):
  def __init__(
    self,
    parent,
    title: str,
    message: str,
    type_: str = "warning",
    confirm_text: str = "Confirmer",
    cancel_text: str = "Annuler",
  ):
    super().__init__(parent)
    self.setWindowTitle(title)
    self.setModal(True)
    self.setMinimumWidth(380)
    self.setStyleSheet(_dialog_qss())

    root = QVBoxLayout(self)
    root.setContentsMargins(24, 24, 24, 20)
    root.setSpacing(16)

    # Icon + title
    header = QHBoxLayout()
    icon_str, icon_color = _ICONS.get(type_, _ICONS["warning"])
    icon_lbl = QLabel(icon_str)
    icon_lbl.setStyleSheet("font-size:28px;background:transparent;border:none;")
    header.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)
    header.addSpacing(12)

    title_lbl = QLabel(title)
    title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    title_lbl.setStyleSheet(
      f"color:{icon_color};background:transparent;border:none;"
    )
    title_lbl.setWordWrap(True)
    header.addWidget(title_lbl, 1)
    root.addLayout(header)

    # Separator
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:{C['border']};border:none;")
    root.addWidget(sep)

    # Message
    msg_lbl = QLabel(message)
    msg_lbl.setWordWrap(True)
    msg_lbl.setStyleSheet(
      f"color:{C['text']};font-size:13px;background:transparent;border:none;"
    )
    root.addWidget(msg_lbl)

    # Buttons
    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    btn_row.addStretch()

    cancel = QPushButton(cancel_text)
    cancel.setObjectName("secondaryBtn")
    cancel.setFixedHeight(36)
    cancel.setCursor(Qt.CursorShape.PointingHandCursor)
    cancel.clicked.connect(self.reject)
    btn_row.addWidget(cancel)

    btn_name = "dangerBtn" if type_ == "danger" else "primaryBtn"
    confirm = QPushButton(confirm_text)
    confirm.setObjectName(btn_name)
    confirm.setFixedHeight(36)
    confirm.setCursor(Qt.CursorShape.PointingHandCursor)
    confirm.clicked.connect(self.accept)
    btn_row.addWidget(confirm)
    root.addLayout(btn_row)

  @staticmethod
  def ask(
    parent,
    title: str,
    message: str,
    type_: str = "warning",
    confirm_text: str = "Confirmer",
    cancel_text: str = "Annuler",
  ) -> bool:
    dlg = ConfirmDialog(parent, title, message, type_, confirm_text, cancel_text)
    return dlg.exec() == QDialog.DialogCode.Accepted
