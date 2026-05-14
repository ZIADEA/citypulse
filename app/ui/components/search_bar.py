"""search_bar.py — Barre de recherche avec debounce 300 ms."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

C = {
  "bg_input": "#1A2E4A",
  "accent":  "#00D4FF",
  "text":   "#E8F4FD",
  "text2":  "#8899AA",
  "border":  "#1E3A5F",
  "hover":  "#1A3A5C",
}


class SearchBar(QWidget):
  search_changed = pyqtSignal(str)

  def __init__(self, placeholder: str = "Rechercher…", parent=None):
    super().__init__(parent)
    self._debounce = QTimer(self)
    self._debounce.setSingleShot(True)
    self._debounce.setInterval(300)
    self._debounce.timeout.connect(self._emit)

    row = QHBoxLayout(self)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)

    # Search icon (emoji retiré)
    icon = QLabel("MAG")
    icon.setFixedWidth(32)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setStyleSheet(
      f"background:{C['bg_input']};border:1px solid {C['border']};"
      "border-right:none;border-top-left-radius:6px;border-bottom-left-radius:6px;font-size:13px;"
    )
    row.addWidget(icon)

    self._edit = QLineEdit()
    self._edit.setPlaceholderText(placeholder)
    self._edit.setStyleSheet(
      f"QLineEdit{{background:{C['bg_input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-left:none;border-right:none;"
      "border-radius:0;padding:6px 10px;font-size:13px;min-height:34px;}}"
      f"QLineEdit:focus{{border-color:{C['accent']};}}"
    )
    self._edit.textChanged.connect(self._on_text)
    row.addWidget(self._edit, 1)

    self._clear_btn = QPushButton("X")
    self._clear_btn.setFixedWidth(32)
    self._clear_btn.setToolTip("Effacer la recherche")
    self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._clear_btn.setStyleSheet(
      f"QPushButton{{background:{C['bg_input']};color:{C['text2']};"
      f"border:1px solid {C['border']};border-left:none;"
      "border-top-right-radius:6px;border-bottom-right-radius:6px;font-size:11px;}}"
      f"QPushButton:hover{{color:{C['text']};background:{C['hover']};}}"
    )
    self._clear_btn.setVisible(False)
    self._clear_btn.clicked.connect(self.clear)
    row.addWidget(self._clear_btn)

  def _on_text(self, text: str):
    self._clear_btn.setVisible(bool(text))
    self._debounce.start()

  def _emit(self):
    self.search_changed.emit(self._edit.text())

  def clear(self):
    self._edit.clear()
    self._clear_btn.setVisible(False)
    self.search_changed.emit("")

  def set_placeholder(self, text: str):
    self._edit.setPlaceholderText(text)

  def get_text(self) -> str:
    return self._edit.text()

  def text(self) -> str:
    """Alias Qt-style — le code ne doit pas utiliser _input (n'existe pas)."""
    return self._edit.text()
