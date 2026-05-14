from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QStackedWidget, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont, QColor
from ..database.db_manager import get_connection, verify_password, hash_password, log_action
from .lucide_icons import lucide_icon
from datetime import datetime, timedelta

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "bg":      "#0D1B2A",
    "card":    "#111E2E",
    "panel":   "#162840",
    "border":  "#1E3A50",
    "accent":  "#00D4FF",
    "text":    "#E8F4F8",
    "text2":   "#7FA8C0",
    "input":   "#0A1628",
    "danger":  "#FF4757",
    "success": "#00FF88",
}

_CARD_QSS = f"""
QFrame#loginCard {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 20px;
}}
QLineEdit {{
    background: {C['input']};
    color: {C['text']};
    border: 2px solid #2E5F88;
    border-radius: 8px;
    padding: 0 12px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 2px solid {C['accent']};
    background: #0D2035;
}}
QLineEdit::placeholder {{
    color: {C['text2']};
}}
"""

_BTN_PRIMARY = f"""
QPushButton {{
    background: {C['accent']};
    color: #0D1B2A;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 700;
    padding: 0 24px;
}}
QPushButton:hover {{ background: #33DDFF; }}
QPushButton:pressed {{ background: #00B8D9; }}
"""

_BTN_LINK = f"""
QPushButton {{
    color: {C['accent']};
    font-size: 12px;
    font-weight: 600;
    border: none;
    background: transparent;
    text-decoration: underline;
}}
QPushButton:hover {{ color: #33DDFF; }}
"""

_BTN_EYE = f"""
QPushButton {{
    background: transparent;
    color: {C['text2']};
    border: none;
    font-size: 15px;
    padding: 0 6px;
}}
QPushButton:hover {{ color: {C['text']}; }}
"""

_SEP_QSS = f"background: {C['border']}; border: none;"


class LoginWidget(QWidget):
    login_success = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._pw_visible = False
        self._setup_ui()

    # ── Construction UI ────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet(f"background: {C['bg']};")
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Carte centrale ─────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(420)
        card.setStyleSheet(_CARD_QSS)
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(0)
        card_lay.setContentsMargins(40, 36, 40, 36)

        # ── En-tête logo ───────────────────────────────────────────────────
        card_lay.addLayout(self._build_header())
        card_lay.addSpacing(24)
        card_lay.addWidget(self._hline())
        card_lay.addSpacing(20)

        # ── Pages (connexion / inscription) ────────────────────────────────
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("border: none; background: transparent;")
        self.pages.addWidget(self._build_login_page())
        self.pages.addWidget(self._build_signup_page())
        card_lay.addWidget(self.pages, 1)

        card_lay.addSpacing(20)
        card_lay.addWidget(self._hline())
        card_lay.addSpacing(14)

        # ── Fonctionnalités (zone qui était vide) ──────────────────────────
        card_lay.addLayout(self._build_features())
        card_lay.addSpacing(20)
        card_lay.addWidget(self._hline())
        card_lay.addSpacing(14)

        # ── Lien toggle connexion / inscription ────────────────────────────
        card_lay.addLayout(self._build_toggle_bar())

        root.addWidget(card)

        # Version bas de page
        ver = QLabel("CityPulse Logistics v5.37  •  © 2025")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(f"color: {C['text2']}; font-size: 11px; background: transparent;")
        root.addSpacing(10)
        root.addWidget(ver)

    # ── Blocs de construction ─────────────────────────────────────────────────

    def _build_header(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(6)

        # Cercle logo
        circle = QFrame()
        circle.setFixedSize(64, 64)
        circle.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {C['accent']}, stop:1 #0080A0);"
            f"border-radius: 32px; border: none;"
        )
        inner = QLabel("CP", circle)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        inner.setGeometry(0, 0, 64, 64)
        inner.setStyleSheet(f"background: transparent; border: none; color: #0D1B2A;")

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(circle)
        lay.addLayout(row)

        title = QLabel("CityPulse")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {C['text']}; border: none;")
        lay.addWidget(title)

        sub = QLabel("Logistics Optimizer")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {C['accent']}; font-size: 13px; letter-spacing: 1px; border: none;")
        lay.addWidget(sub)

        return lay

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(self._field_label("Identifiant"))
        self.login_username = self._input("Entrez votre identifiant")
        lay.addWidget(self.login_username)

        lay.addSpacing(4)
        lay.addWidget(self._field_label("Mot de passe"))
        self.login_password, pw_row = self._password_input("Entrez votre mot de passe")
        lay.addLayout(pw_row)

        lay.addSpacing(8)

        login_btn = QPushButton("Se connecter")
        login_btn.setStyleSheet(_BTN_PRIMARY)
        login_btn.setFixedHeight(44)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self._do_login)
        self.login_password.returnPressed.connect(self._do_login)
        lay.addWidget(login_btn)

        self.login_error = QLabel("")
        self.login_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_error.setStyleSheet(f"color: {C['danger']}; font-size: 12px; border: none;")
        self.login_error.setWordWrap(True)
        lay.addWidget(self.login_error)

        return page

    def _build_signup_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(self._field_label("Nom complet"))
        self.signup_fullname = self._input("Nom et prénom")
        lay.addWidget(self.signup_fullname)

        lay.addWidget(self._field_label("Identifiant"))
        self.signup_username = self._input("Choisissez un identifiant")
        lay.addWidget(self.signup_username)

        lay.addWidget(self._field_label("Mot de passe"))
        self.signup_password, sp_row = self._password_input("Choisissez un mot de passe")
        lay.addLayout(sp_row)

        lay.addSpacing(6)

        signup_btn = QPushButton("Créer mon compte")
        signup_btn.setStyleSheet(_BTN_PRIMARY)
        signup_btn.setFixedHeight(44)
        signup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        signup_btn.clicked.connect(self._do_signup)
        self.signup_password.returnPressed.connect(self._do_signup)
        lay.addWidget(signup_btn)

        self.signup_error = QLabel("")
        self.signup_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signup_error.setStyleSheet(f"color: {C['danger']}; font-size: 12px; border: none;")
        self.signup_error.setWordWrap(True)
        lay.addWidget(self.signup_error)

        return page

    def _build_features(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(8)

        features = [
            ("map",        "Optimisation de tournées multi-algorithmes"),
            ("crosshair",  "Suivi en temps réel avec Gantt interactif"),
            ("help-circle","Copilote IA — analyse et suggestions"),
        ]
        for icon_key, text in features:
            row = QHBoxLayout()
            row.setSpacing(10)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(lucide_icon(icon_key, C["accent"], 14).pixmap(QSize(14, 14)))
            icon_lbl.setFixedWidth(20)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet("background: transparent; border: none;")

            txt = QLabel(text)
            txt.setStyleSheet(f"color: {C['text2']}; font-size: 12px; background: transparent; border: none;")
            txt.setWordWrap(True)

            row.addWidget(icon_lbl)
            row.addWidget(txt, 1)
            lay.addLayout(row)

        return lay

    def _build_toggle_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.setSpacing(4)

        self.toggle_label = QLabel("Pas encore de compte ?")
        self.toggle_label.setStyleSheet(f"color: {C['text2']}; font-size: 12px; border: none;")
        row.addWidget(self.toggle_label)

        self.toggle_btn = QPushButton("Créer un compte")
        self.toggle_btn.setStyleSheet(_BTN_LINK)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_page)
        row.addWidget(self.toggle_btn)

        return row

    # ── Helpers widgets ────────────────────────────────────────────────────────

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C['text2']}; font-size: 12px; font-weight: 600; border: none;")
        return lbl

    @staticmethod
    def _input_qss() -> str:
        return (
            f"QLineEdit{{background:{C['input']};color:{C['text']};"
            f"border:2px solid #3A7AAA;border-radius:8px;padding:0 12px;font-size:13px;}}"
            f"QLineEdit:focus{{border:2px solid {C['accent']};background:#0D2035;}}"
            f"QLineEdit::placeholder{{color:{C['text2']};}}"
        )

    def _input(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(46)
        edit.setStyleSheet(self._input_qss())
        return edit

    def _password_input(self, placeholder: str):
        """Retourne (QLineEdit, QHBoxLayout contenant l'input + bouton œil)."""
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(46)
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setStyleSheet(self._input_qss())

        eye = QPushButton()
        eye.setIcon(lucide_icon("eye", C["text2"], 16))
        eye.setIconSize(QSize(16, 16))
        eye.setFixedSize(46, 46)
        eye.setStyleSheet(_BTN_EYE)
        eye.setToolTip("Afficher / masquer")
        eye.setCursor(Qt.CursorShape.PointingHandCursor)

        def _toggle():
            if edit.echoMode() == QLineEdit.EchoMode.Password:
                edit.setEchoMode(QLineEdit.EchoMode.Normal)
                eye.setIcon(lucide_icon("eye", C["accent"], 16))
                eye.setIconSize(QSize(16, 16))
            else:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
                eye.setIcon(lucide_icon("eye", C["text2"], 16))
                eye.setIconSize(QSize(16, 16))

        eye.clicked.connect(_toggle)

        row = QHBoxLayout()
        row.setSpacing(4)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        row.addWidget(eye)
        return edit, row

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(_SEP_QSS)
        return line

    # ── Logique ────────────────────────────────────────────────────────────────

    def _toggle_page(self):
        if self.pages.currentIndex() == 0:
            self.pages.setCurrentIndex(1)
            self.toggle_label.setText("Déjà un compte ?")
            self.toggle_btn.setText("Se connecter")
            self.signup_error.setText("")
        else:
            self.pages.setCurrentIndex(0)
            self.toggle_label.setText("Pas encore de compte ?")
            self.toggle_btn.setText("Créer un compte")
            self.login_error.setText("")

    def _do_login(self):
        username = self.login_username.text().strip()
        password = self.login_password.text()

        if not username or not password:
            self.login_error.setText("Veuillez remplir tous les champs.")
            return

        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if row is None:
            self.login_error.setText("Identifiant ou mot de passe incorrect.")
            conn.close()
            return

        if row["locked_until"]:
            lock_time = datetime.fromisoformat(row["locked_until"])
            if datetime.now() < lock_time:
                remaining = int((lock_time - datetime.now()).total_seconds())
                self.login_error.setText(f"Compte bloqué. Réessayez dans {remaining}s.")
                conn.close()
                return

        if not verify_password(password, row["password_hash"], row["salt"]):
            attempts = row["failed_attempts"] + 1
            if attempts >= 5:
                lock_until = (datetime.now() + timedelta(seconds=30)).isoformat()
                conn.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (attempts, lock_until, row["id"])
                )
                self.login_error.setText("Trop de tentatives. Compte bloqué 30s.")
            else:
                conn.execute(
                    "UPDATE users SET failed_attempts = ? WHERE id = ?",
                    (attempts, row["id"])
                )
                self.login_error.setText(f"Mot de passe incorrect ({5 - attempts} essais restants).")
            conn.commit()
            conn.close()
            return

        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), row["id"])
        )
        conn.commit()
        conn.close()

        log_action("LOGIN", f"Utilisateur {username} connecté", user_id=row["id"])

        user = {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "full_name": row["full_name"] or row["username"],
            "email": row["email"],
            "language": row["language"],
            "theme": row["theme"],
        }
        self.login_success.emit(user)

    def _do_signup(self):
        fullname = self.signup_fullname.text().strip()
        username = self.signup_username.text().strip()
        password = self.signup_password.text()

        if not fullname or not username or not password:
            self.signup_error.setText("Veuillez remplir tous les champs.")
            return

        if len(username) < 3:
            self.signup_error.setText("L'identifiant doit contenir au moins 3 caractères.")
            return

        if len(password) < 4:
            self.signup_error.setText("Le mot de passe doit contenir au moins 4 caractères.")
            return

        conn = get_connection()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()

        if existing:
            self.signup_error.setText("Cet identifiant est déjà utilisé.")
            conn.close()
            return

        pw_hash, salt = hash_password(password)
        conn.execute(
            """INSERT INTO users (username, password_hash, salt, role, full_name)
               VALUES (?, ?, ?, 'gestionnaire', ?)""",
            (username, pw_hash, salt, fullname)
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        log_action("SIGNUP", f"Nouveau compte créé : {username}", user_id=row["id"])

        user = {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "full_name": row["full_name"] or row["username"],
            "email": row["email"],
            "language": row["language"],
            "theme": row["theme"],
        }
        self.login_success.emit(user)
