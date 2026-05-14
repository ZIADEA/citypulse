"""pagination_bar.py — Barre de pagination."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal

C = {
  "bg":   "#112240",
  "accent": "#00D4FF",
  "text":  "#E8F4FD",
  "text2":  "#8899AA",
  "border": "#1E3A5F",
  "hover":  "#1A3A5C",
  "bg_input":"#1A2E4A",
}
_BTN = (
  f"QPushButton{{background:#112240;color:#E8F4FD;"
  f"border:1px solid #1E3A5F;border-radius:5px;"
  "padding:4px 10px;font-size:12px;min-width:30px;}}"
  f"QPushButton:hover{{background:#1A3A5C;border-color:#00D4FF;}}"
  "QPushButton:disabled{color:#8899AA;border-color:#1E3A5F;}"
)


class PaginationBar(QWidget):
  page_changed = pyqtSignal(int, int, int) # page, offset, limit

  def __init__(self, page_size: int = 20, parent=None):
    super().__init__(parent)
    self._page = 0
    self._total = 0
    self._limit = page_size

    row = QHBoxLayout(self)
    row.setContentsMargins(0, 4, 0, 4)
    row.setSpacing(6)
    row.addStretch()

    self._info_lbl = QLabel()
    self._info_lbl.setStyleSheet(
      f"color:{C['text2']};font-size:11px;background:transparent;border:none;"
    )
    row.addWidget(self._info_lbl)

    row.addSpacing(12)

    self._first_btn = QPushButton("«")
    self._first_btn.setToolTip("Première page")
    self._prev_btn = QPushButton("‹")
    self._prev_btn.setToolTip("Page précédente")
    self._next_btn = QPushButton("›")
    self._next_btn.setToolTip("Page suivante")
    self._last_btn = QPushButton("»")
    self._last_btn.setToolTip("Dernière page")

    for btn in (self._first_btn, self._prev_btn, self._next_btn, self._last_btn):
      btn.setStyleSheet(_BTN)
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      row.addWidget(btn)

    self._first_btn.clicked.connect(lambda: self._go(0))
    self._prev_btn.clicked.connect(lambda: self._go(self._page - 1))
    self._next_btn.clicked.connect(lambda: self._go(self._page + 1))
    self._last_btn.clicked.connect(lambda: self._go(self._max_page()))

    row.addSpacing(8)

    size_lbl = QLabel("Lignes :")
    size_lbl.setStyleSheet(
      f"color:{C['text2']};font-size:11px;background:transparent;border:none;"
    )
    row.addWidget(size_lbl)

    self._size_combo = QComboBox()
    self._size_combo.addItems(["10", "20", "50", "100"])
    self._size_combo.setCurrentText(str(page_size))
    self._size_combo.setFixedWidth(60)
    self._size_combo.setStyleSheet(
      f"QComboBox{{background:{C['bg_input']};color:{C['text']};"
      f"border:1px solid {C['border']};border-radius:5px;"
      "padding:3px 6px;font-size:12px;min-height:28px;}}"
    )
    self._size_combo.currentTextChanged.connect(self._on_size_change)
    row.addWidget(self._size_combo)

    self._refresh()

  def _max_page(self) -> int:
    if self._limit <= 0:
      return 0
    return max(0, (self._total - 1) // self._limit)

  def _go(self, page: int):
    page = max(0, min(page, self._max_page()))
    if page == self._page and self._total > 0:
      return
    self._page = page
    self._refresh()
    self.page_changed.emit(self._page, self._page * self._limit, self._limit)

  def _on_size_change(self, text: str):
    try:
      self._limit = int(text)
    except ValueError:
      return
    self._page = 0
    self._refresh()
    self.page_changed.emit(0, 0, self._limit)

  def _refresh(self):
    total_pages = self._max_page() + 1 if self._total > 0 else 1
    start = self._page * self._limit + 1 if self._total > 0 else 0
    end  = min(start + self._limit - 1, self._total)
    self._info_lbl.setText(
      f"{start}–{end} sur {self._total} (page {self._page + 1}/{total_pages})"
    )
    self._first_btn.setEnabled(self._page > 0)
    self._prev_btn.setEnabled(self._page > 0)
    self._next_btn.setEnabled(self._page < self._max_page())
    self._last_btn.setEnabled(self._page < self._max_page())

  def update_total(self, total: int):
    self._total = max(0, total)
    self._page = min(self._page, self._max_page())
    self._refresh()
