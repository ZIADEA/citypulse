from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class EmptyState(QWidget):
    """A beautiful empty-state placeholder for pages with no data."""

    def __init__(self, icon_pixmap=None, title="Aucune donnée",
                 subtitle="", action_text="", action_callback=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 60, 40, 60)

        # Icon
        if icon_pixmap:
            icon_label = QLabel()
            icon_label.setPixmap(icon_pixmap)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)
        else:
            # Large text icon
            icon_lbl = QLabel("📂")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet("font-size: 48px; border: none;")
            layout.addWidget(icon_lbl)

        # Title
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
        t.setStyleSheet("color: #6c6c6c; border: none;")
        layout.addWidget(t)

        # Subtitle
        if subtitle:
            s = QLabel(subtitle)
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setWordWrap(True)
            s.setStyleSheet("color: #999999; font-size: 12px; border: none;")
            layout.addWidget(s)

        # Action button
        if action_text and action_callback:
            btn = QPushButton(action_text)
            btn.setObjectName("primaryBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(40)
            btn.setMaximumWidth(260)
            btn.clicked.connect(action_callback)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
