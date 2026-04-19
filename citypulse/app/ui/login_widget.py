from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QStackedWidget
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from ..database.db_manager import get_connection, verify_password, hash_password, log_action
from datetime import datetime, timedelta


class LoginWidget(QWidget):
    login_success = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Card container
        card = QFrame()
        card.setFixedSize(420, 540)
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d8dce3;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(40, 32, 40, 32)

        # Logo / Title
        title = QLabel("CityPulse")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2c2c2c; border: none;")
        card_layout.addWidget(title)

        subtitle = QLabel("Logistics Optimizer")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #6c6c6c; font-size: 14px; border: none;")
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(12)

        # ── Stacked pages: Login (0) / Sign Up (1) ──
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("border: none;")

        # ── Page Login ──
        login_page = QWidget()
        lp = QVBoxLayout(login_page)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.setSpacing(10)

        lbl_user = QLabel("Identifiant")
        lbl_user.setStyleSheet("color: #6c6c6c; font-size: 12px; border: none;")
        lp.addWidget(lbl_user)
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("Entrez votre identifiant")
        self.login_username.setMinimumHeight(40)
        lp.addWidget(self.login_username)

        lbl_pw = QLabel("Mot de passe")
        lbl_pw.setStyleSheet("color: #6c6c6c; font-size: 12px; border: none;")
        lp.addWidget(lbl_pw)
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Entrez votre mot de passe")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.setMinimumHeight(40)
        self.login_password.returnPressed.connect(self._do_login)
        lp.addWidget(self.login_password)

        lp.addSpacing(6)

        login_btn = QPushButton("Se connecter")
        login_btn.setObjectName("primaryBtn")
        login_btn.setMinimumHeight(42)
        login_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self._do_login)
        lp.addWidget(login_btn)

        self.login_error = QLabel("")
        self.login_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_error.setStyleSheet("color: #888888; font-size: 12px; border: none;")
        lp.addWidget(self.login_error)

        lp.addStretch()
        self.pages.addWidget(login_page)

        # ── Page Sign Up ──
        signup_page = QWidget()
        sp = QVBoxLayout(signup_page)
        sp.setContentsMargins(0, 0, 0, 0)
        sp.setSpacing(10)

        lbl_new_name = QLabel("Nom complet")
        lbl_new_name.setStyleSheet("color: #6c6c6c; font-size: 12px; border: none;")
        sp.addWidget(lbl_new_name)
        self.signup_fullname = QLineEdit()
        self.signup_fullname.setPlaceholderText("Nom et prenom")
        self.signup_fullname.setMinimumHeight(40)
        sp.addWidget(self.signup_fullname)

        lbl_new_user = QLabel("Identifiant")
        lbl_new_user.setStyleSheet("color: #6c6c6c; font-size: 12px; border: none;")
        sp.addWidget(lbl_new_user)
        self.signup_username = QLineEdit()
        self.signup_username.setPlaceholderText("Choisissez un identifiant")
        self.signup_username.setMinimumHeight(40)
        sp.addWidget(self.signup_username)

        lbl_new_pw = QLabel("Mot de passe")
        lbl_new_pw.setStyleSheet("color: #6c6c6c; font-size: 12px; border: none;")
        sp.addWidget(lbl_new_pw)
        self.signup_password = QLineEdit()
        self.signup_password.setPlaceholderText("Choisissez un mot de passe")
        self.signup_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.signup_password.setMinimumHeight(40)
        self.signup_password.returnPressed.connect(self._do_signup)
        sp.addWidget(self.signup_password)

        sp.addSpacing(6)

        signup_btn = QPushButton("Creer un compte")
        signup_btn.setObjectName("primaryBtn")
        signup_btn.setMinimumHeight(42)
        signup_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        signup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        signup_btn.clicked.connect(self._do_signup)
        sp.addWidget(signup_btn)

        self.signup_error = QLabel("")
        self.signup_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signup_error.setStyleSheet("color: #888888; font-size: 12px; border: none;")
        sp.addWidget(self.signup_error)

        sp.addStretch()
        self.pages.addWidget(signup_page)

        card_layout.addWidget(self.pages, 1)

        # ── Toggle link ──
        toggle_bar = QHBoxLayout()
        toggle_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toggle_label = QLabel("Pas encore de compte ?")
        self.toggle_label.setStyleSheet("color: #6c6c6c; font-size: 12px; border: none;")
        toggle_bar.addWidget(self.toggle_label)

        self.toggle_btn = QPushButton("Creer un compte")
        self.toggle_btn.setStyleSheet(
            "QPushButton { color: #2c2c2c; font-size: 12px; font-weight: bold; "
            "border: none; background: transparent; text-decoration: underline; }"
            "QPushButton:hover { color: #555555; }"
        )
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_page)
        toggle_bar.addWidget(self.toggle_btn)

        card_layout.addLayout(toggle_bar)

        layout.addWidget(card)

    def _toggle_page(self):
        if self.pages.currentIndex() == 0:
            self.pages.setCurrentIndex(1)
            self.toggle_label.setText("Deja un compte ?")
            self.toggle_btn.setText("Se connecter")
            self.signup_error.setText("")
        else:
            self.pages.setCurrentIndex(0)
            self.toggle_label.setText("Pas encore de compte ?")
            self.toggle_btn.setText("Creer un compte")
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

        # Check lock
        if row["locked_until"]:
            lock_time = datetime.fromisoformat(row["locked_until"])
            if datetime.now() < lock_time:
                remaining = int((lock_time - datetime.now()).total_seconds())
                self.login_error.setText(f"Compte bloque. Reessayez dans {remaining}s.")
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
                self.login_error.setText("Trop de tentatives. Compte bloque 30s.")
            else:
                conn.execute(
                    "UPDATE users SET failed_attempts = ? WHERE id = ?",
                    (attempts, row["id"])
                )
                self.login_error.setText(f"Mot de passe incorrect ({5 - attempts} essais restants).")
            conn.commit()
            conn.close()
            return

        # Success
        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), row["id"])
        )
        conn.commit()
        conn.close()

        log_action("LOGIN", f"Utilisateur {username} connecte", user_id=row["id"])

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
            self.signup_error.setText("L'identifiant doit contenir au moins 3 caracteres.")
            return

        if len(password) < 4:
            self.signup_error.setText("Le mot de passe doit contenir au moins 4 caracteres.")
            return

        conn = get_connection()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()

        if existing:
            self.signup_error.setText("Cet identifiant est deja utilise.")
            conn.close()
            return

        pw_hash, salt = hash_password(password)
        conn.execute(
            """INSERT INTO users (username, password_hash, salt, role, full_name)
               VALUES (?, ?, ?, 'gestionnaire', ?)""",
            (username, pw_hash, salt, fullname)
        )
        conn.commit()

        # Retrieve the new user
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        log_action("SIGNUP", f"Nouveau compte cree: {username}", user_id=row["id"])

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
