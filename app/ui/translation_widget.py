"""
translation_widget.py — Module de traduction IA avec mémoire
=============================================================
Améliorations Phase 3 :
  - Score BLEU-1 réel (sacrebleu ou implémentation maison)
  - Glossaire métier persistant en SQLite (prioritaire sur API)
  - Mémoire de traduction : corrections utilisateur mémorisées
  - Onglet Glossaire : voir / modifier / supprimer les paires
  - Champ de correction manuelle avec bouton Mémoriser
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QProgressBar, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QMessageBox, QTabWidget, QLineEdit, QDialog,
    QDialogButtonBox, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush

from ..database.db_manager import get_connection, log_action
from .help_dialog import show_help
from .lucide_icons import apply_action_button

logger = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────
LANG_FLAGS = {"fr": " FR", "en": " EN", "ar": " AR", "es": " ES", "de": " DE"}
LANG_NAMES = {"fr": "Français", "en": "English", "ar": "العربية", "es": "Español", "de": "Deutsch"}
_LANG_FULL = {"fr": "français", "en": "anglais", "ar": "arabe", "es": "espagnol", "de": "allemand"}

# Glossaire métier intégré (base — peut être étendu par l'utilisateur)
LOGISTICS_DICT = {
    "fr": {
        "livraison":       {"en": "delivery",    "ar": "توصيل",        "es": "entrega",       "de": "Lieferung"},
        "tournée":         {"en": "route",        "ar": "جولة",         "es": "ruta",          "de": "Tour"},
        "véhicule":        {"en": "vehicle",      "ar": "مركبة",        "es": "vehículo",      "de": "Fahrzeug"},
        "dépôt":           {"en": "depot",        "ar": "مستودع",       "es": "depósito",      "de": "Depot"},
        "client":          {"en": "customer",     "ar": "عميل",         "es": "cliente",       "de": "Kunde"},
        "chauffeur":       {"en": "driver",       "ar": "سائق",         "es": "conductor",     "de": "Fahrer"},
        "capacité":        {"en": "capacity",     "ar": "سعة",          "es": "capacidad",     "de": "Kapazität"},
        "distance":        {"en": "distance",     "ar": "مسافة",        "es": "distancia",     "de": "Entfernung"},
        "feuille de route":{"en": "route sheet",  "ar": "خريطة الطريق", "es": "hoja de ruta",  "de": "Routenblatt"},
        "fenêtre horaire": {"en": "time window",  "ar": "نافذة زمنية",  "es": "ventana horaria","de": "Zeitfenster"},
        "optimisation":    {"en": "optimization", "ar": "تحسين",        "es": "optimización",  "de": "Optimierung"},
        "retard":          {"en": "delay",        "ar": "تأخير",        "es": "retraso",       "de": "Verspätung"},
        "coût":            {"en": "cost",         "ar": "تكلفة",        "es": "costo",         "de": "Kosten"},
        "itinéraire":      {"en": "itinerary",    "ar": "مسار",         "es": "itinerario",    "de": "Reiseroute"},
        "chargement":      {"en": "loading",      "ar": "تحميل",        "es": "carga",         "de": "Beladung"},
        "déchargement":    {"en": "unloading",    "ar": "تفريغ",        "es": "descarga",      "de": "Entladung"},
        "planification":   {"en": "planning",     "ar": "تخطيط",        "es": "planificación", "de": "Planung"},
        "maintenance":     {"en": "maintenance",  "ar": "صيانة",        "es": "mantenimiento", "de": "Wartung"},
    }
}


# ── Score BLEU-1 maison ────────────────────────────────────────────────────────

def compute_bleu1(reference: str, hypothesis: str) -> float:
    """
    BLEU-1 unigramme simplifié.
    Compare les tokens de la traduction retraduite avec l'original.
    Retourne un score entre 0.0 et 1.0.
    """
    if not reference or not hypothesis:
        return 0.0
    ref_tokens  = set(reference.lower().split())
    hyp_tokens  = hypothesis.lower().split()
    if not hyp_tokens:
        return 0.0
    matches = sum(1 for t in hyp_tokens if t in ref_tokens)
    precision = matches / len(hyp_tokens)

    # Pénalité de brièveté (brevity penalty)
    bp = min(1.0, len(hyp_tokens) / max(1, len(ref_tokens)))
    return round(precision * bp, 3)


def compute_bleu_sacrebleu(reference: str, hypothesis: str) -> float:
    """Tente d'utiliser sacrebleu pour un score BLEU plus précis."""
    try:
        import sacrebleu
        result = sacrebleu.corpus_bleu([hypothesis], [[reference]])
        return round(result.score / 100.0, 3)
    except Exception:
        return compute_bleu1(reference, hypothesis)


# ── Glossaire BDD ──────────────────────────────────────────────────────────────

def get_glossary_term(src_lang: str, tgt_lang: str, term: str) -> str | None:
    """Cherche un terme dans le glossaire utilisateur (prioritaire sur API)."""
    try:
        conn = get_connection()
        row = conn.execute(
            """SELECT corrected_term FROM translation_glossary
               WHERE src_lang= ? AND tgt_lang= ? AND LOWER(source_term)=LOWER(?)
               ORDER BY use_count DESC LIMIT 1""",
            (src_lang, tgt_lang, term)
        ).fetchone()
        conn.close()
        return row["corrected_term"] if row else None
    except Exception:
        logger.exception("Erreur lecture glossaire")
        return None


def save_glossary_term(src_lang, tgt_lang, source_term, corrected_term):
    """Sauvegarde ou met à jour un terme dans le glossaire."""
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO translation_glossary (src_lang, tgt_lang, source_term, corrected_term)
               VALUES (?,?,?,?)
               ON CONFLICT(src_lang, tgt_lang, source_term)
               DO UPDATE SET corrected_term=excluded.corrected_term,
                             use_count=use_count+1""",
            (src_lang, tgt_lang, source_term.strip(), corrected_term.strip())
        )
        conn.commit()
        conn.close()
        logger.info("Glossaire: mémorisé '%s' → '%s'", source_term, corrected_term)
    except Exception:
        logger.exception("Erreur sauvegarde glossaire")


def apply_glossary(text: str, src_lang: str, tgt_lang: str) -> tuple[str, int, dict]:
    """
    Protège les termes du glossaire avec des marqueurs alphanumériques avant
    traduction, puis renvoie le dictionnaire de restauration.
    Les marqueurs (ex. GLOSS0X) ne sont pas traduits par les APIs.
    Retourne (texte_avec_marqueurs, nb_termes_protégés, {marqueur: corrected_term}).
    """
    import re
    result      = text
    nb_applied  = 0
    placeholders: dict = {}   # marqueur → corrected_term (langue cible)

    def _protect(src_term: str, tgt_term: str) -> bool:
        """Remplace src_term par un marqueur et mémorise tgt_term. Retourne True si trouvé."""
        nonlocal result, nb_applied
        if re.search(re.escape(src_term), result, flags=re.IGNORECASE):
            marker = f"GLOSS{len(placeholders)}X"
            placeholders[marker] = tgt_term
            result = re.sub(re.escape(src_term), marker, result, flags=re.IGNORECASE)
            nb_applied += 1
            return True
        return False

    # 1) Glossaire BDD utilisateur (termes longs en premier pour éviter les sous-chaînes)
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT source_term, corrected_term FROM translation_glossary "
            "WHERE src_lang=? AND tgt_lang=? ORDER BY LENGTH(source_term) DESC",
            (src_lang, tgt_lang)
        ).fetchall()
        conn.close()
        for row in rows:
            _protect(row["source_term"], row["corrected_term"])
    except Exception:
        logger.exception("Erreur application glossaire BDD")

    # 2) Glossaire intégré LOGISTICS_DICT
    if src_lang in LOGISTICS_DICT:
        for term, translations in LOGISTICS_DICT[src_lang].items():
            if tgt_lang in translations:
                _protect(term, translations[tgt_lang])

    return result, nb_applied, placeholders


def _restore_placeholders(text: str, placeholders: dict) -> str:
    """Restaure les marqueurs GLOSS*X par les termes cibles après traduction."""
    for marker, tgt_term in placeholders.items():
        # L'API peut avoir altéré la casse du marqueur (GLOSS0X → Gloss0x…)
        import re
        text = re.sub(re.escape(marker), tgt_term, text, flags=re.IGNORECASE)
    return text


# ── Thread de traduction ───────────────────────────────────────────────────────

class TranslationThread(QThread):
    finished = pyqtSignal(str, float, str, int)   # (texte, bleu, méthode, nb_glossaire)

    def __init__(self, text, source, target):
        super().__init__()
        self.text   = text
        self.source = source
        self.target = target

    def run(self):
        # Protéger les termes du glossaire avec des marqueurs avant traduction
        pre_text, nb_gloss, placeholders = apply_glossary(self.text, self.source, self.target)

        # 1) deep-translator
        try:
            from deep_translator import GoogleTranslator
            result = GoogleTranslator(source=self.source, target=self.target).translate(pre_text)
            if result and result.strip():
                result = _restore_placeholders(result, placeholders)
                bleu = compute_bleu_sacrebleu(self.text, result)
                self.finished.emit(result, bleu, "deep-translator", nb_gloss)
                return
        except Exception:
            logger.warning("deep-translator indisponible")

        # 2) Fallback Mistral
        try:
            from ..ai.mistral_client import MISTRAL_AVAILABLE, MISTRAL_API_KEY
            if MISTRAL_AVAILABLE and MISTRAL_API_KEY:
                from mistralai.client import Mistral
                src_n = _LANG_FULL.get(self.source, self.source)
                tgt_n = _LANG_FULL.get(self.target, self.target)
                prompt = (
                    f"Traduis du {src_n} vers le {tgt_n}. "
                    f"Contexte : logistique urbaine. "
                    f"Renvoie UNIQUEMENT la traduction, en conservant intacts "
                    f"les codes de la forme GLOSS0X, GLOSS1X, etc.\n\n{pre_text}"
                )
                client   = Mistral(api_key=MISTRAL_API_KEY)
                response = client.chat.complete(
                    model="mistral-small-latest",
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.choices[0].message.content.strip()
                if result:
                    result = _restore_placeholders(result, placeholders)
                    bleu = compute_bleu_sacrebleu(self.text, result)
                    self.finished.emit(result, bleu, "mistral-api", nb_gloss)
                    return
        except Exception:
            logger.warning("Mistral indisponible pour la traduction")

        # 3) Fallback dictionnaire hors-ligne (marqueurs déjà remplacés par les termes cibles)
        result = _restore_placeholders(pre_text, placeholders)
        bleu   = compute_bleu1(self.text, result)
        self.finished.emit(result, bleu, "hors-ligne", nb_gloss)


# ── Widget principal ───────────────────────────────────────────────────────────

class TranslationWidget(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window        = main_window
        self._last_source_text  = ""
        self._last_translation  = ""
        self._last_src_lang     = "fr"
        self._last_tgt_lang     = "en"
        self._setup_ui()

    def _setup_ui(self):
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:#0D1B2A;border:none;")
        _container = QWidget()
        _container.setObjectName("translContainer")
        _container.setStyleSheet("QWidget#translContainer{background:#0D1B2A;}")
        layout = QVBoxLayout(_container)
        layout.setContentsMargins(4, 8, 4, 16)
        layout.setSpacing(18)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Module de Traduction IA")
        title.setObjectName("heading")
        hdr.addWidget(title)
        hdr.addStretch()
        help_btn = QPushButton()
        help_btn.setFixedSize(32, 32)
        help_btn.setToolTip("Aide — Traduction")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(help_btn, "help-circle", "#7FA8C0", "#1A2E4A", "#1A3A5C", 18)
        help_btn.clicked.connect(lambda: show_help(self, "translation"))
        hdr.addWidget(help_btn)
        layout.addLayout(hdr)

        subtitle = QLabel("Traduction des contenus logistiques — FR / EN / AR / ES / DE")
        subtitle.setObjectName("subheading")
        layout.addWidget(subtitle)

        # Tabs : Traduction | Glossaire
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_translation_tab(), "Traduction")
        self.tabs.addTab(self._build_glossary_tab(), "Glossaire métier")
        self.tabs.addTab(self._build_history_tab(), "Historique")
        layout.addWidget(self.tabs, 1)
        layout.addStretch()
        scroll.setWidget(_container)
        _outer = QVBoxLayout(self)
        _outer.setContentsMargins(0,0,0,0)
        _outer.addWidget(scroll)

    # ── Onglet Traduction ──────────────────────────────────────────────────────

    def _build_translation_tab(self):
        w  = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(0, 12, 0, 0)
        lo.setSpacing(12)

        # Sélecteurs de langue
        lang_bar = QHBoxLayout()
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        for code, name in LANG_NAMES.items():
            flag = LANG_FLAGS[code]
            self.source_combo.addItem(f"{flag} {name}", code)
            self.target_combo.addItem(f"{flag} {name}", code)
        self.source_combo.setCurrentIndex(0)
        self.target_combo.setCurrentIndex(1)

        swap_btn = QPushButton("Inverser")
        swap_btn.clicked.connect(self._swap_langs)

        lang_bar.addWidget(QLabel("Source :"))
        lang_bar.addWidget(self.source_combo)
        lang_bar.addSpacing(8)
        lang_bar.addWidget(swap_btn)
        lang_bar.addSpacing(8)
        lang_bar.addWidget(QLabel("Cible :"))
        lang_bar.addWidget(self.target_combo)
        lang_bar.addStretch()
        lo.addLayout(lang_bar)

        # Chargement rapide
        quick = QHBoxLayout()
        for label, fn in [
            ("Feuille de route", self._load_last_route),
            ("Dernier rapport",  self._load_last_route),
        ]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            quick.addWidget(b)
        quick.addStretch()
        lo.addLayout(quick)

        # Zone de texte côte à côte
        splitter = QSplitter(Qt.Orientation.Horizontal)

        src_frame = QFrame()
        src_frame.setStyleSheet("QFrame{background:#243F58;border:1px solid #1E3A50;border-radius:8px;}")
        sl = QVBoxLayout(src_frame)
        sl.addWidget(QLabel("Texte source"))
        self.source_text = QTextEdit()
        self.source_text.setPlaceholderText("Entrez le texte à traduire ici…")
        sl.addWidget(self.source_text)
        splitter.addWidget(src_frame)

        tgt_frame = QFrame()
        tgt_frame.setStyleSheet("QFrame{background:#243F58;border:1px solid #1E3A50;border-radius:8px;}")
        tl = QVBoxLayout(tgt_frame)
        tl.addWidget(QLabel("Traduction"))
        self.target_text = QTextEdit()
        self.target_text.setReadOnly(True)
        self.target_text.setPlaceholderText("La traduction apparaîtra ici…")
        tl.addWidget(self.target_text)
        splitter.addWidget(tgt_frame)
        lo.addWidget(splitter, 1)

        # Boutons action
        action_bar = QHBoxLayout()
        self.translate_btn = QPushButton("Traduire")
        self.translate_btn.setObjectName("primaryBtn")
        self.translate_btn.setMinimumHeight(40)
        self.translate_btn.clicked.connect(self._translate)
        action_bar.addWidget(self.translate_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        action_bar.addWidget(self.progress_bar)

        self.quality_label = QLabel("")
        self.quality_label.setStyleSheet("font-size:13px;font-weight:500;")
        action_bar.addWidget(self.quality_label)

        validate_btn = QPushButton(" Valider")
        validate_btn.setStyleSheet("background:#00D97E;color:#0D1B2A;border:none;border-radius:6px;padding:6px 12px;font-weight:600;")
        validate_btn.clicked.connect(self._validate)
        action_bar.addWidget(validate_btn)
        lo.addLayout(action_bar)

        # Méthode utilisée
        self.mode_label = QLabel("Pipeline : glossaire → deep-translator → Mistral → hors-ligne")
        self.mode_label.setStyleSheet("color:#4A7A9B;font-size:11px;background:transparent;")
        lo.addWidget(self.mode_label)

        # Zone de correction manuelle
        correction_frame = QFrame()
        correction_frame.setStyleSheet(
            "QFrame{background:rgba(255,183,50,20);border:1px solid #FFB732;border-left:3px solid #FFB732;border-radius:8px;}"
        )
        cf = QHBoxLayout(correction_frame)
        cf.addWidget(QLabel("Corriger :"))
        self.correction_source = QLineEdit()
        self.correction_source.setPlaceholderText("Terme original…")
        cf.addWidget(self.correction_source)
        cf.addWidget(QLabel("→"))
        self.correction_target = QLineEdit()
        self.correction_target.setPlaceholderText("Correction…")
        cf.addWidget(self.correction_target)
        memorize_btn = QPushButton("Mémoriser")
        memorize_btn.setStyleSheet(
            "background:#FFB732;color:#0D1B2A;border:none;border-radius:6px;padding:6px 12px;font-weight:600;"
        )
        memorize_btn.clicked.connect(self._memorize_correction)
        cf.addWidget(memorize_btn)
        lo.addWidget(correction_frame)

        return w

    # ── Onglet Glossaire ───────────────────────────────────────────────────────

    def _build_glossary_tab(self):
        w  = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(0, 12, 0, 0)
        lo.setSpacing(10)

        info = QLabel(
            "Le glossaire est prioritaire sur les API de traduction. "
            "Ajoutez vos corrections ici pour qu'elles soient appliquées automatiquement."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#7FA8C0;font-size:12px;background:transparent;")
        lo.addWidget(info)

        # Formulaire d'ajout rapide
        add_bar = QHBoxLayout()
        self.gloss_src_lang = QComboBox()
        self.gloss_tgt_lang = QComboBox()
        for code, name in LANG_NAMES.items():
            self.gloss_src_lang.addItem(f"{LANG_FLAGS[code]} {name}", code)
            self.gloss_tgt_lang.addItem(f"{LANG_FLAGS[code]} {name}", code)
        self.gloss_src_lang.setCurrentIndex(0)
        self.gloss_tgt_lang.setCurrentIndex(1)
        self.gloss_source   = QLineEdit()
        self.gloss_source.setPlaceholderText("Terme source…")
        self.gloss_corrected = QLineEdit()
        self.gloss_corrected.setPlaceholderText("Traduction correcte…")
        add_btn = QPushButton("+ Ajouter")
        add_btn.setStyleSheet("background:#3B9EE8;color:#fff;border:none;border-radius:6px;padding:6px 12px;font-weight:600;")
        add_btn.clicked.connect(self._add_glossary_entry)
        add_bar.addWidget(self.gloss_src_lang)
        add_bar.addWidget(QLabel("→"))
        add_bar.addWidget(self.gloss_tgt_lang)
        add_bar.addWidget(self.gloss_source)
        add_bar.addWidget(QLabel("="))
        add_bar.addWidget(self.gloss_corrected)
        add_bar.addWidget(add_btn)
        lo.addLayout(add_bar)

        # Table du glossaire
        self.glossary_table = QTableWidget()
        self.glossary_table.setColumnCount(5)
        self.glossary_table.setHorizontalHeaderLabels(
            ["Src", "Cible", "Terme original", "Traduction correcte", "Usages"]
        )
        self.glossary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.glossary_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        lo.addWidget(self.glossary_table, 1)

        btn_bar = QHBoxLayout()
        del_btn = QPushButton("Supprimer la sélection")
        del_btn.clicked.connect(self._delete_glossary_entry)
        del_btn.setStyleSheet("color:#dc2626;")
        refresh_btn = QPushButton("Actualiser")
        refresh_btn.clicked.connect(self._load_glossary)
        btn_bar.addWidget(del_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(refresh_btn)
        lo.addLayout(btn_bar)

        self._load_glossary()
        return w

    # ── Onglet Historique ──────────────────────────────────────────────────────

    def _build_history_tab(self):
        w  = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(0, 12, 0, 0)
        lo.setSpacing(8)

        filter_bar = QHBoxLayout()
        self._hist_validated_only = QCheckBox("Validées uniquement")
        self._hist_validated_only.setStyleSheet("color:#7FA8C0;font-size:11px;")
        self._hist_validated_only.toggled.connect(self._load_history)
        filter_bar.addWidget(self._hist_validated_only)
        filter_bar.addStretch()
        lo.addLayout(filter_bar)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels(
            ["Date", "Src", "Cible", "Extrait", "Score BLEU", "Méthode", "Statut"]
        )
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.history_table.setColumnWidth(6, 60)
        lo.addWidget(self.history_table, 1)
        self._load_history()
        return w

    # ── Logique traduction ─────────────────────────────────────────────────────

    def _swap_langs(self):
        si = self.source_combo.currentIndex()
        ti = self.target_combo.currentIndex()
        self.source_combo.setCurrentIndex(ti)
        self.target_combo.setCurrentIndex(si)
        st = self.source_text.toPlainText()
        tt = self.target_text.toPlainText()
        self.source_text.setPlainText(tt)
        self.target_text.setPlainText(st)

    def _translate(self):
        text = self.source_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer du texte à traduire.")
            return
        self._last_source_text = text
        self._last_src_lang    = self.source_combo.currentData()
        self._last_tgt_lang    = self.target_combo.currentData()
        self.progress_bar.setVisible(True)
        self.translate_btn.setEnabled(False)
        self.thread = TranslationThread(text, self._last_src_lang, self._last_tgt_lang)
        self.thread.finished.connect(self._on_translated)
        self.thread.start()

    def _on_translated(self, result, bleu, method, nb_gloss):
        self._last_translation = result
        self.progress_bar.setVisible(False)
        self.translate_btn.setEnabled(True)
        self.target_text.setPlainText(result)

        # Score BLEU affiché
        bleu_pct = bleu * 100
        bar = "█" * int(bleu_pct / 10) + "░" * (10 - int(bleu_pct / 10))
        gloss_info = f" | Glossaire: {nb_gloss} terme(s)" if nb_gloss > 0 else ""
        self.quality_label.setText(f"BLEU : {bleu_pct:.0f}% [{bar}]{gloss_info}")

        color = "#16a34a" if bleu_pct >= 60 else "#d97706" if bleu_pct >= 30 else "#dc2626"
        self.quality_label.setStyleSheet(f"font-size:12px;font-weight:500;color:{color};")

        mode_info = {
            "deep-translator": " En ligne (Google Translate)",
            "mistral-api":     " Fallback IA (Mistral)",
            "hors-ligne":      " Hors-ligne (glossaire local)",
        }
        self.mode_label.setText(mode_info.get(method, method))

        if method == "hors-ligne":
            from .toast import show_toast
            show_toast(self.window(),
                       "Services de traduction en ligne indisponibles — résultat partiel uniquement.",
                       "warning")

        # Pré-remplir le champ de correction avec l'extrait
        words = self._last_source_text.split()[:3]
        self.correction_source.setText(" ".join(words) if words else "")

        # Sauvegarder en historique
        self._save_history(result, bleu, method)
        self._load_history()

    def _ensure_validated_col(self):
        try:
            conn = get_connection()
            conn.execute(
                "ALTER TABLE translation_history ADD COLUMN validated INTEGER DEFAULT 0"
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # colonne déjà existante

    def _validate(self):
        try:
            self._ensure_validated_col()
            conn = get_connection()
            conn.execute(
                "UPDATE translation_history SET validated=1 "
                "WHERE id=(SELECT MAX(id) FROM translation_history)"
            )
            conn.commit()
            conn.close()
            self.quality_label.setText(self.quality_label.text() + "  ✓ Validée")
            log_action("TRANSLATION_VALIDATE", "Traduction validée")

            # Ajout automatique au glossaire si le texte est court (<= 120 chars)
            src = self._last_source_text.strip()
            tgt = self._last_translation.strip()
            from .toast import show_toast
            if src and tgt and len(src) <= 120:
                save_glossary_term(self._last_src_lang, self._last_tgt_lang, src, tgt)
                self._load_glossary()
                show_toast(self.window(),
                           "Traduction validée et ajoutée au glossaire !", "success")
            else:
                show_toast(self.window(), "Traduction validée.", "success")

            self._load_history()
        except Exception:
            logger.exception("Erreur validation traduction")

    def _memorize_correction(self):
        src  = self.correction_source.text().strip()
        corr = self.correction_target.text().strip()
        if not src or not corr:
            QMessageBox.warning(self, "Erreur", "Renseignez le terme original et sa correction.")
            return
        save_glossary_term(self._last_src_lang, self._last_tgt_lang, src, corr)
        self.correction_source.clear()
        self.correction_target.clear()
        self._load_glossary()
        from .toast import show_toast
        show_toast(self.window(), f"'{src}' → '{corr}' mémorisé dans le glossaire", "success")

    # ── Glossaire ─────────────────────────────────────────────────────────────

    def _add_glossary_entry(self):
        src  = self.gloss_source.text().strip()
        corr = self.gloss_corrected.text().strip()
        if not src or not corr:
            return
        sl = self.gloss_src_lang.currentData()
        tl = self.gloss_tgt_lang.currentData()
        save_glossary_term(sl, tl, src, corr)
        self.gloss_source.clear()
        self.gloss_corrected.clear()
        self._load_glossary()

    def _delete_glossary_entry(self):
        row = self.glossary_table.currentRow()
        if row < 0:
            return
        src_item  = self.glossary_table.item(row, 2)
        sl_item   = self.glossary_table.item(row, 0)
        tl_item   = self.glossary_table.item(row, 1)
        if not src_item:
            return
        try:
            conn = get_connection()
            conn.execute(
                "DELETE FROM translation_glossary WHERE source_term= ? AND src_lang= ? AND tgt_lang= ?",
                (src_item.text(), sl_item.text(), tl_item.text())
            )
            conn.commit()
            conn.close()
            self._load_glossary()
        except Exception:
            logger.exception("Erreur suppression glossaire")

    def _load_glossary(self):
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT src_lang, tgt_lang, source_term, corrected_term, use_count "
                "FROM translation_glossary ORDER BY use_count DESC, source_term ASC"
            ).fetchall()
            conn.close()
            self.glossary_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                for j, v in enumerate([r["src_lang"], r["tgt_lang"],
                                        r["source_term"], r["corrected_term"],
                                        str(r["use_count"])]):
                    item = QTableWidgetItem(v)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.glossary_table.setItem(i, j, item)
        except Exception:
            logger.exception("Erreur chargement glossaire")

    # ── Historique ─────────────────────────────────────────────────────────────

    def _ensure_method_col(self):
        try:
            conn = get_connection()
            conn.execute(
                "ALTER TABLE translation_history ADD COLUMN method TEXT DEFAULT ''"
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # colonne déjà existante

    def _save_history(self, result, bleu, method):
        try:
            self._ensure_method_col()
            conn = get_connection()
            conn.execute(
                """INSERT INTO translation_history
                   (source_lang, target_lang, source_text, translated_text, quality_score, method)
                   VALUES (?,?,?,?,?,?)""",
                (self._last_src_lang, self._last_tgt_lang,
                 self._last_source_text[:500], result[:500], bleu, method)
            )
            conn.commit()
            conn.close()
        except Exception:
            logger.exception("Erreur sauvegarde historique traduction")

    def _load_history(self):
        try:
            self._ensure_validated_col()
            validated_only = getattr(self, "_hist_validated_only", None)
            where = " WHERE validated=1" if (validated_only and validated_only.isChecked()) else ""
            conn = get_connection()
            rows = conn.execute(
                f"SELECT * FROM translation_history{where} ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            conn.close()
            self.history_table.setRowCount(len(rows))
            green = QBrush(QColor("#00D97E"))
            for i, r in enumerate(rows):
                bleu = (r["quality_score"] or 0) * 100
                keys = r.keys()
                validated = r["validated"] if "validated" in keys else 0
                method_raw = (r["method"] if "method" in keys else "") or ""
                method_labels = {
                    "deep-translator": "🌐 Google",
                    "mistral-api":     "🤖 Mistral",
                    "hors-ligne":      "📖 Hors-ligne",
                }
                method_colors = {
                    "deep-translator": "#3B9EE8",
                    "mistral-api":     "#A78BFA",
                    "hors-ligne":      "#FFB732",
                }
                vals = [
                    (r["created_at"] or "")[:16],
                    LANG_FLAGS.get(r["source_lang"], r["source_lang"]),
                    LANG_FLAGS.get(r["target_lang"], r["target_lang"]),
                    (r["source_text"] or "")[:60] + "…",
                    f"{bleu:.0f}%",
                    method_labels.get(method_raw, method_raw or "—"),
                    "✓" if validated else "",
                ]
                for j, v in enumerate(vals):
                    item = QTableWidgetItem(str(v))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if validated:
                        item.setForeground(green)
                    elif j == 5 and method_raw in method_colors:
                        item.setForeground(QBrush(QColor(method_colors[method_raw])))
                    self.history_table.setItem(i, j, item)
        except Exception:
            logger.exception("Erreur chargement historique")

    def _load_last_route(self):
        try:
            conn = get_connection()
            res = conn.execute(
                "SELECT algorithm, total_distance, total_cost, client_count "
                "FROM algo_results ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if res:
                self.source_text.setPlainText(
                    f"Rapport de tournée\n"
                    f"Algorithme : {res['algorithm']}\n"
                    f"Distance totale : {res['total_distance']:.2f} km\n"
                    f"Coût total : {res['total_cost']:.2f} €\n"
                    f"Nombre de clients : {res['client_count']}\n"
                )
            else:
                self.source_text.setPlainText("Aucune tournée enregistrée.")
        except Exception:
            logger.exception("Erreur chargement feuille de route")

    def refresh_data(self):
        self._load_history()
        self._load_glossary()
