"""star_rating.py — Widget de notation par étoiles (/)."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

C = {
  "warning": "#FFB800",
  "text2":  "#8899AA",
}


class StarRating(QWidget):
  rating_changed = pyqtSignal(int)

  def __init__(self, rating: int = 0, max_stars: int = 5,
         read_only: bool = False, parent=None):
    super().__init__(parent)
    self._rating  = max(0, min(rating, max_stars))
    self._max   = max_stars
    self._read_only = read_only
    self._hovering = -1

    row = QHBoxLayout(self)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(2)

    self._stars: list[QLabel] = []
    for i in range(max_stars):
      lbl = QLabel("-")
      lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
      lbl.setFixedSize(24, 24)
      lbl.setStyleSheet("font-size:18px;background:transparent;border:none;")
      if not read_only:
        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
      lbl.setProperty("star_idx", i)
      self._stars.append(lbl)
      row.addWidget(lbl)

    self._refresh()

  def _refresh(self, hover: int = -1):
    active = hover if hover >= 0 else self._rating - 1
    for i, lbl in enumerate(self._stars):
      if i <= active:
        lbl.setText("*")
        lbl.setStyleSheet(
          f"font-size:18px;color:{C['warning']};"
          "background:transparent;border:none;"
        )
      else:
        lbl.setText("-")
        lbl.setStyleSheet(
          f"font-size:18px;color:{C['text2']};"
          "background:transparent;border:none;"
        )

  def set_rating(self, rating: int):
    self._rating = max(0, min(rating, self._max))
    self._refresh()

  def get_rating(self) -> int:
    return self._rating

  def mousePressEvent(self, event):
    if self._read_only:
      return
    pos = event.position().toPoint()
    for i, lbl in enumerate(self._stars):
      if lbl.geometry().contains(pos):
        new_rating = i + 1
        if self._rating == new_rating:
          new_rating = 0
        self._rating = new_rating
        self._refresh()
        self.rating_changed.emit(self._rating)
        break
    super().mousePressEvent(event)

  def mouseMoveEvent(self, event):
    if self._read_only:
      return
    pos = event.position().toPoint()
    hover = -1
    for i, lbl in enumerate(self._stars):
      if lbl.geometry().contains(pos):
        hover = i
        break
    self._refresh(hover)
    super().mouseMoveEvent(event)

  def leaveEvent(self, event):
    self._refresh()
    super().leaveEvent(event)
