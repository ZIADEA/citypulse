from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QProgressBar, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help

# Offline dictionary of logistics terms
LOGISTICS_DICT = {
    "fr": {
        "livraison": {"en": "delivery", "ar": "توصيل", "es": "entrega", "de": "Lieferung"},
        "tournée": {"en": "route", "ar": "جولة", "es": "ruta", "de": "Tour"},
        "véhicule": {"en": "vehicle", "ar": "مركبة", "es": "vehículo", "de": "Fahrzeug"},
        "dépôt": {"en": "depot", "ar": "مستودع", "es": "depósito", "de": "Depot"},
        "client": {"en": "customer", "ar": "عميل", "es": "cliente", "de": "Kunde"},
        "chauffeur": {"en": "driver", "ar": "سائق", "es": "conductor", "de": "Fahrer"},
        "capacité": {"en": "capacity", "ar": "سعة", "es": "capacidad", "de": "Kapazität"},
        "distance": {"en": "distance", "ar": "مسافة", "es": "distancia", "de": "Entfernung"},
        "feuille de route": {"en": "roadmap", "ar": "خريطة الطريق", "es": "hoja de ruta", "de": "Routenplan"},
        "fenêtre horaire": {"en": "time window", "ar": "نافذة زمنية", "es": "ventana horaria", "de": "Zeitfenster"},
        "optimisation": {"en": "optimization", "ar": "تحسين", "es": "optimización", "de": "Optimierung"},
        "retard": {"en": "delay", "ar": "تأخير", "es": "retraso", "de": "Verspätung"},
        "coût": {"en": "cost", "ar": "تكلفة", "es": "costo", "de": "Kosten"},
        "itinéraire": {"en": "itinerary", "ar": "مسار", "es": "itinerario", "de": "Reiseroute"},
        "chargement": {"en": "loading", "ar": "تحميل", "es": "carga", "de": "Beladung"},
        "déchargement": {"en": "unloading", "ar": "تفريغ", "es": "descarga", "de": "Entladung"},
        "poids": {"en": "weight", "ar": "وزن", "es": "peso", "de": "Gewicht"},
        "volume": {"en": "volume", "ar": "حجم", "es": "volumen", "de": "Volumen"},
        "maintenance": {"en": "maintenance", "ar": "صيانة", "es": "mantenimiento", "de": "Wartung"},
        "planification": {"en": "planning", "ar": "تخطيط", "es": "planificación", "de": "Planung"},
    }
}

LANG_FLAGS = {"fr": "FR", "en": "EN", "ar": "AR", "es": "ES", "de": "DE"}
LANG_NAMES = {"fr": "Français", "en": "English", "ar": "العربية", "es": "Español", "de": "Deutsch"}


# Mapping langue → nom complet pour le prompt Mistral
_LANG_FULL = {"fr": "français", "en": "anglais", "ar": "arabe", "es": "espagnol", "de": "allemand"}


class TranslationThread(QThread):
    """Pipeline : deep-translator → Mistral API → dictionnaire hors-ligne."""

    # result text, quality score, method used
    finished = pyqtSignal(str, float, str)

    def __init__(self, text, source, target):
        super().__init__()
        self.text = text
        self.source = source
        self.target = target

    def run(self):
        # ── 1) deep-translator (Google) ──
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source=self.source, target=self.target)
            result = translator.translate(self.text)
            if result and result.strip():
                self.finished.emit(result, 0.90, "deep-translator")
                return
        except Exception:
            pass

        # ── 2) Fallback : Mistral API ──
        try:
            from ..ai.mistral_client import MISTRAL_AVAILABLE, MISTRAL_API_KEY
            if MISTRAL_AVAILABLE and MISTRAL_API_KEY:
                from mistralai.client import Mistral
                client = Mistral(api_key=MISTRAL_API_KEY)
                src_name = _LANG_FULL.get(self.source, self.source)
                tgt_name = _LANG_FULL.get(self.target, self.target)
                prompt = (
                    f"Traduis le texte suivant du {src_name} vers le {tgt_name}. "
                    f"Contexte : logistique urbaine et optimisation de tournées. "
                    f"Renvoie UNIQUEMENT la traduction, sans explication.\n\n"
                    f"{self.text}"
                )
                response = client.chat.complete(
                    model="mistral-small-latest",
                    messages=[{"role": "user", "content": prompt}],
                )
                result = response.choices[0].message.content.strip()
                if result:
                    self.finished.emit(result, 0.75, "mistral-api")
                    return
        except Exception:
            pass

        # ── 3) Fallback : dictionnaire hors-ligne ──
        result = self._offline_translate()
        self.finished.emit(result, 0.35, "hors-ligne")

    def _offline_translate(self):
        text = self.text.lower()
        if self.source in LOGISTICS_DICT:
            for term, translations in LOGISTICS_DICT[self.source].items():
                if self.target in translations:
                    text = text.replace(term, translations[self.target])
        return text


class TranslationWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        _header = QHBoxLayout()
        title = QLabel("Module de Traduction IA")
        title.setObjectName("heading")
        _header.addWidget(title)
        _header.addStretch()
        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Guide d'utilisation de cette page")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: show_help(self, "translation"))
        _header.addWidget(help_btn)
        layout.addLayout(_header)
        subtitle = QLabel("Traduction des contenus logistiques — FR / EN / AR / ES / DE")
        subtitle.setObjectName("subheading")
        layout.addWidget(subtitle)

        # Language selectors
        lang_bar = QHBoxLayout()
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        for code, name in LANG_NAMES.items():
            flag = LANG_FLAGS[code]
            self.source_combo.addItem(f"{flag} {name}", code)
            self.target_combo.addItem(f"{flag} {name}", code)
        self.source_combo.setCurrentIndex(0)  # FR
        self.target_combo.setCurrentIndex(1)  # EN

        swap_btn = QPushButton("Inverser")
        swap_btn.clicked.connect(self._swap_langs)

        lang_bar.addWidget(QLabel("Source :"))
        lang_bar.addWidget(self.source_combo)
        lang_bar.addWidget(swap_btn)
        lang_bar.addWidget(QLabel("Cible :"))
        lang_bar.addWidget(self.target_combo)
        lang_bar.addStretch()
        layout.addLayout(lang_bar)

        # Quick load buttons
        quick_bar = QHBoxLayout()
        load_route_btn = QPushButton("Charger derniere feuille de route")
        load_route_btn.clicked.connect(self._load_last_route)
        load_report_btn = QPushButton("Charger dernier rapport")
        load_report_btn.clicked.connect(self._load_last_report)
        quick_bar.addWidget(load_route_btn)
        quick_bar.addWidget(load_report_btn)
        quick_bar.addStretch()
        layout.addLayout(quick_bar)

        # Translation area (side by side)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        source_frame = QFrame()
        source_frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #d8dce3; border-radius: 8px; }")
        sl = QVBoxLayout(source_frame)
        sl.addWidget(QLabel("Texte source"))
        self.source_text = QTextEdit()
        self.source_text.setPlaceholderText("Entrez le texte à traduire ici...")
        sl.addWidget(self.source_text)
        splitter.addWidget(source_frame)

        target_frame = QFrame()
        target_frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #d8dce3; border-radius: 8px; }")
        tl = QVBoxLayout(target_frame)
        tl.addWidget(QLabel("Traduction"))
        self.target_text = QTextEdit()
        self.target_text.setReadOnly(True)
        self.target_text.setPlaceholderText("La traduction apparaîtra ici...")
        tl.addWidget(self.target_text)
        splitter.addWidget(target_frame)

        layout.addWidget(splitter, 1)

        # Translate button + progress
        action_bar = QHBoxLayout()
        self.translate_btn = QPushButton("Traduire")
        self.translate_btn.setObjectName("primaryBtn")
        self.translate_btn.setMinimumHeight(44)
        self.translate_btn.clicked.connect(self._translate)
        action_bar.addWidget(self.translate_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        action_bar.addWidget(self.progress_bar)

        self.quality_label = QLabel("")
        self.quality_label.setStyleSheet("font-size: 14px;")
        action_bar.addWidget(self.quality_label)

        validate_btn = QPushButton("Valider")
        validate_btn.setObjectName("successBtn")
        validate_btn.clicked.connect(self._validate)
        reject_btn = QPushButton("Rejeter et retraduire")
        reject_btn.clicked.connect(self._translate)
        action_bar.addWidget(validate_btn)
        action_bar.addWidget(reject_btn)
        layout.addLayout(action_bar)

        # Mode indicator
        self.mode_label = QLabel("Pipeline : deep-translator / Mistral API / dictionnaire local")
        self.mode_label.setStyleSheet("color: #6c6c6c; font-size: 11px;")
        layout.addWidget(self.mode_label)

        # History table
        hist_title = QLabel("Historique des traductions")
        hist_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(hist_title)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Source", "Cible", "Extrait", "Qualité"])
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.history_table.setMaximumHeight(200)
        layout.addWidget(self.history_table)

    def _swap_langs(self):
        s = self.source_combo.currentIndex()
        t = self.target_combo.currentIndex()
        self.source_combo.setCurrentIndex(t)
        self.target_combo.setCurrentIndex(s)
        st = self.source_text.toPlainText()
        tt = self.target_text.toPlainText()
        self.source_text.setPlainText(tt)
        self.target_text.setPlainText(st)

    def _translate(self):
        text = self.source_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer du texte à traduire.")
            return

        source = self.source_combo.currentData()
        target = self.target_combo.currentData()

        self.progress_bar.setVisible(True)
        self.translate_btn.setEnabled(False)

        self.thread = TranslationThread(text, source, target)
        self.thread.finished.connect(self._on_translated)
        self.thread.start()

    def _on_translated(self, result, quality, method):
        self.progress_bar.setVisible(False)
        self.translate_btn.setEnabled(True)
        self.target_text.setPlainText(result)

        score_bar = "|" * int(quality * 5)
        self.quality_label.setText(f"Qualité : {quality * 100:.0f}% [{score_bar}]")

        mode_map = {
            "deep-translator": ("Mode : en ligne (deep-translator / Google)", "color: #4a4a4a;"),
            "mistral-api":     ("Mode : fallback IA (Mistral API)",           "color: #2c2c2c;"),
            "hors-ligne":      ("Mode : hors-ligne (dictionnaire local)",     "color: #888888;"),
        }
        label_text, style = mode_map.get(method, mode_map["hors-ligne"])
        self.mode_label.setText(label_text)
        self.mode_label.setStyleSheet(style)

        # Save to history
        source = self.source_combo.currentData()
        target = self.target_combo.currentData()
        conn = get_connection()
        conn.execute(
            """INSERT INTO translation_history (source_lang, target_lang, source_text,
               translated_text, quality_score) VALUES (?,?,?,?,?)""",
            (source, target, self.source_text.toPlainText()[:500], result[:500], quality)
        )
        conn.commit()
        conn.close()
        self._load_history()

    def _validate(self):
        conn = get_connection()
        conn.execute(
            "UPDATE translation_history SET validated=1 WHERE id=(SELECT MAX(id) FROM translation_history)"
        )
        conn.commit()
        conn.close()
        self.quality_label.setText(self.quality_label.text() + " (Validee)")
        log_action("TRANSLATION_VALIDATE", "Traduction validée")

    def _load_last_route(self):
        conn = get_connection()
        last = conn.execute(
            "SELECT details_json FROM algo_results ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not last:
            results = conn.execute(
                "SELECT algorithm, total_distance, total_cost, client_count FROM algo_results ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if results:
                text = (
                    f"Rapport de tournée\n"
                    f"Algorithme : {results['algorithm']}\n"
                    f"Distance totale : {results['total_distance']:.2f} km\n"
                    f"Coût total : {results['total_cost']:.2f} €\n"
                    f"Nombre de clients : {results['client_count']}\n"
                )
                self.source_text.setPlainText(text)
            else:
                self.source_text.setPlainText("Aucune tournée enregistrée.")
        conn.close()

    def _load_last_report(self):
        self._load_last_route()

    def _load_history(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM translation_history ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        conn.close()
        self.history_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.history_table.setItem(r, 0, QTableWidgetItem(row["created_at"][:16]))
            self.history_table.setItem(r, 1, QTableWidgetItem(LANG_FLAGS.get(row["source_lang"], row["source_lang"])))
            self.history_table.setItem(r, 2, QTableWidgetItem(LANG_FLAGS.get(row["target_lang"], row["target_lang"])))
            self.history_table.setItem(r, 3, QTableWidgetItem(row["source_text"][:60] + "..."))
            quality = row["quality_score"] or 0
            self.history_table.setItem(r, 4, QTableWidgetItem(f"{quality * 100:.0f}%"))

    def refresh_data(self):
        self._load_history()
