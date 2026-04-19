from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QLinearGradient, QColor


class SplashScreen(QWidget):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Central card
        card = QWidget()
        card.setObjectName("splashCard")
        card.setStyleSheet("""
            #splashCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1e2e, stop:0.5 #1a1a2e, stop:1 #0d1117);
                border-radius: 20px;
                border: 1px solid rgba(137, 180, 250, 0.2);
            }
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(48, 40, 48, 32)
        cl.setSpacing(8)

        # Logo / Brand
        logo = QLabel("CP")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("""
            font-size: 48px; font-weight: 900; color: #89b4fa;
            font-family: 'Segoe UI', sans-serif;
            letter-spacing: 8px;
        """)
        cl.addWidget(logo)

        title = QLabel("CityPulse Logistics")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 22px; font-weight: 700; color: #cdd6f4;
            font-family: 'Segoe UI', sans-serif;
            letter-spacing: 2px;
        """)
        cl.addWidget(title)

        subtitle = QLabel("Optimisation de Tournées Véhiculées")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 11px; color: #6c7086; letter-spacing: 1px;")
        cl.addWidget(subtitle)

        cl.addSpacing(24)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: #313244;
                border: none;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #89b4fa, stop:1 #cba6f7);
                border-radius: 1px;
            }
        """)
        cl.addWidget(self.progress)

        cl.addSpacing(8)

        # Status label
        self.status = QLabel("Initialisation...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("font-size: 10px; color: #585b70;")
        cl.addWidget(self.status)

        cl.addSpacing(16)

        version = QLabel("v5.0  —  OR-Tools · PyQt6 · SQLite")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("font-size: 9px; color: #45475a;")
        cl.addWidget(version)

        layout.addWidget(card)

        # Fade-in animation
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0)
        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(400)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Progress animation steps
        self._step = 0
        self._steps = [
            (15, "Connexion à la base de données..."),
            (35, "Chargement des modules IA..."),
            (55, "Initialisation de l'interface..."),
            (75, "Préparation du moteur cartographique..."),
            (90, "Vérification des données..."),
            (100, "Prêt !"),
        ]
        self._timer = QTimer()
        self._timer.timeout.connect(self._advance)

    def start(self):
        self._center_on_screen()
        self.show()
        self._fade_in.start()
        self._timer.start(350)

    def _center_on_screen(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    def _advance(self):
        if self._step >= len(self._steps):
            self._timer.stop()
            # Fade out then signal finished
            self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
            self._fade_out.setDuration(300)
            self._fade_out.setStartValue(1.0)
            self._fade_out.setEndValue(0.0)
            self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
            self._fade_out.finished.connect(self._done)
            self._fade_out.start()
            return
        val, msg = self._steps[self._step]
        self.progress.setValue(val)
        self.status.setText(msg)
        self._step += 1

    def _done(self):
        self.close()
        self.finished.emit()
