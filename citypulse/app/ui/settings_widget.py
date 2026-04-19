from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QFormLayout, QSpinBox, QComboBox, QLineEdit, QCheckBox, QDoubleSpinBox,
    QMessageBox, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ..database.db_manager import get_connection, log_action, hash_password
from .help_dialog import show_help
from .toast import show_toast
import json, os

_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "settings.json")


class SettingsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        _header = QHBoxLayout()
        title = QLabel("Param\u00e8tres & Configuration")
        title.setObjectName("heading")
        _header.addWidget(title)
        _header.addStretch()
        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "settings"))
        _header.addWidget(help_btn)
        layout.addLayout(_header)

        # IA Configuration
        ia_group = QGroupBox("Configuration IA")
        ia_layout = QFormLayout(ia_group)

        self.default_algo = QComboBox()
        self.default_algo.addItems(["Glouton", "2-opt", "OR-Tools"])
        ia_layout.addRow("Algorithme par défaut", self.default_algo)

        self.ortools_time = QSpinBox()
        self.ortools_time.setRange(5, 300)
        self.ortools_time.setValue(30)
        self.ortools_time.setSuffix(" s")
        ia_layout.addRow("Limite temps OR-Tools", self.ortools_time)

        self.twoopt_iter = QSpinBox()
        self.twoopt_iter.setRange(100, 5000)
        self.twoopt_iter.setValue(1000)
        ia_layout.addRow("Itérations max 2-opt", self.twoopt_iter)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Minimiser distance", "Minimiser coût", "Minimiser retards", "Mixte"])
        ia_layout.addRow("Priorité d'optimisation", self.priority_combo)
        layout.addWidget(ia_group)

        # Translation Configuration
        trad_group = QGroupBox("Configuration Traduction")
        trad_layout = QFormLayout(trad_group)

        self.api_combo = QComboBox()
        self.api_combo.addItems(["Google Translate (deep-translator)", "DeepL", "LibreTranslate"])
        trad_layout.addRow("API de traduction", self.api_combo)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Optionnel (Google gratuit)")
        trad_layout.addRow("Clé API", self.api_key)

        self.source_lang = QComboBox()
        self.source_lang.addItems(["Français", "English", "العربية", "Español", "Deutsch"])
        trad_layout.addRow("Langue source par défaut", self.source_lang)

        self.target_lang = QComboBox()
        self.target_lang.addItems(["Français", "English", "العربية", "Español", "Deutsch"])
        self.target_lang.setCurrentIndex(1)
        trad_layout.addRow("Langue cible par défaut", self.target_lang)

        self.offline_check = QCheckBox("Activer le mode hors-ligne")
        trad_layout.addRow(self.offline_check)
        layout.addWidget(trad_group)

        # Map Configuration
        map_group = QGroupBox("Configuration Carte")
        map_layout = QFormLayout(map_group)

        self.tile_provider = QComboBox()
        self.tile_provider.addItems(["CartoDB Dark", "OpenStreetMap", "CartoDB Light"])
        map_layout.addRow("Fournisseur de tuiles", self.tile_provider)

        self.default_zoom = QSpinBox()
        self.default_zoom.setRange(1, 18)
        self.default_zoom.setValue(12)
        map_layout.addRow("Zoom initial", self.default_zoom)

        self.show_labels = QCheckBox("Afficher labels clients")
        self.show_labels.setChecked(True)
        map_layout.addRow(self.show_labels)

        self.show_order = QCheckBox("Afficher numéros d'ordre")
        self.show_order.setChecked(True)
        map_layout.addRow(self.show_order)
        layout.addWidget(map_group)

        # System Configuration
        sys_group = QGroupBox("Configuration Système")
        sys_layout = QFormLayout(sys_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Blanc", "Noir"])
        self.theme_combo.currentTextChanged.connect(self._change_theme)
        sys_layout.addRow("Thème", self.theme_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Français", "English"])
        sys_layout.addRow("Langue interface", self.lang_combo)

        self.alert_threshold = QSpinBox()
        self.alert_threshold.setRange(1, 60)
        self.alert_threshold.setValue(5)
        self.alert_threshold.setSuffix(" min")
        sys_layout.addRow("Seuil alerte retard", self.alert_threshold)

        self.maint_km = QDoubleSpinBox()
        self.maint_km.setRange(1000, 100000)
        self.maint_km.setValue(10000)
        self.maint_km.setSuffix(" km")
        sys_layout.addRow("Seuil maintenance", self.maint_km)
        layout.addWidget(sys_group)

        # User Management (admin only)
        user_group = QGroupBox("Gestion Utilisateurs (Admin)")
        user_layout = QFormLayout(user_group)

        self.new_user = QLineEdit()
        self.new_user.setPlaceholderText("Nom d'utilisateur")
        user_layout.addRow("Nouvel utilisateur", self.new_user)

        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("Mot de passe")
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        user_layout.addRow("Mot de passe", self.new_password)

        self.new_role = QComboBox()
        self.new_role.addItems(["gestionnaire", "superviseur", "chauffeur", "administrateur"])
        user_layout.addRow("Rôle", self.new_role)

        create_user_btn = QPushButton("Créer utilisateur")
        create_user_btn.setObjectName("primaryBtn")
        create_user_btn.clicked.connect(self._create_user)
        user_layout.addRow(create_user_btn)
        layout.addWidget(user_group)

        # Save button
        save_btn = QPushButton("Sauvegarder les parametres")
        save_btn.setObjectName("primaryBtn")
        save_btn.setMinimumHeight(44)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _change_theme(self, theme):
        mapped = "dark" if theme == "Noir" else "light"
        self.main_window._apply_theme(mapped)

    def _create_user(self):
        username = self.new_user.text().strip()
        password = self.new_password.text()
        role = self.new_role.currentText()

        if not username or not password:
            QMessageBox.warning(self, "Erreur", "Nom et mot de passe requis.")
            return

        if len(password) < 4:
            QMessageBox.warning(self, "Erreur", "Mot de passe trop court (min 4 caractères).")
            return

        pw_hash, salt = hash_password(password)
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, full_name) VALUES (?,?,?,?,?)",
                (username, pw_hash, salt, role, username)
            )
            conn.commit()
            QMessageBox.information(self, "Succès", f"Utilisateur '{username}' créé avec le rôle '{role}'.")
            log_action("USER_CREATE", f"Utilisateur '{username}' créé ({role})",
                       user_id=self.main_window.current_user["id"])
            self.new_user.clear()
            self.new_password.clear()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible de créer l'utilisateur: {e}")
        conn.close()

    def _save_settings(self):
        data = {
            "default_algo": self.default_algo.currentIndex(),
            "ortools_time": self.ortools_time.value(),
            "twoopt_iter": self.twoopt_iter.value(),
            "priority": self.priority_combo.currentIndex(),
            "api_combo": self.api_combo.currentIndex(),
            "source_lang": self.source_lang.currentIndex(),
            "target_lang": self.target_lang.currentIndex(),
            "offline": self.offline_check.isChecked(),
            "tile_provider": self.tile_provider.currentIndex(),
            "default_zoom": self.default_zoom.value(),
            "show_labels": self.show_labels.isChecked(),
            "show_order": self.show_order.isChecked(),
            "theme": self.theme_combo.currentText(),
            "lang": self.lang_combo.currentIndex(),
            "alert_threshold": self.alert_threshold.value(),
            "maint_km": self.maint_km.value(),
        }
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            log_action("SETTINGS_SAVE", "Paramètres sauvegardés",
                       user_id=self.main_window.current_user["id"] if self.main_window.current_user else None)
            show_toast(self.window(), "Paramètres sauvegardés avec succès", "success")
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible de sauvegarder: {e}")

    def _load_settings(self):
        if not os.path.exists(_SETTINGS_FILE):
            return
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.default_algo.setCurrentIndex(data.get("default_algo", 0))
            self.ortools_time.setValue(data.get("ortools_time", 30))
            self.twoopt_iter.setValue(data.get("twoopt_iter", 1000))
            self.priority_combo.setCurrentIndex(data.get("priority", 0))
            self.api_combo.setCurrentIndex(data.get("api_combo", 0))
            self.source_lang.setCurrentIndex(data.get("source_lang", 0))
            self.target_lang.setCurrentIndex(data.get("target_lang", 1))
            self.offline_check.setChecked(data.get("offline", False))
            self.tile_provider.setCurrentIndex(data.get("tile_provider", 0))
            self.default_zoom.setValue(data.get("default_zoom", 12))
            self.show_labels.setChecked(data.get("show_labels", True))
            self.show_order.setChecked(data.get("show_order", True))
            saved_theme = data.get("theme", "Blanc")
            if saved_theme == "Dark":
                saved_theme = "Noir"
            elif saved_theme == "Light":
                saved_theme = "Blanc"
            self.theme_combo.setCurrentText(saved_theme)
            self.lang_combo.setCurrentIndex(data.get("lang", 0))
            self.alert_threshold.setValue(data.get("alert_threshold", 5))
            self.maint_km.setValue(data.get("maint_km", 10000))
        except Exception:
            pass

    def refresh_data(self):
        self._load_settings()
