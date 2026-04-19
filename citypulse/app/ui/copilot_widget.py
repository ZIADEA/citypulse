"""
CityPulse — Module Assistant Copilot (QDockWidget)
Contient :
  • MistralWorker  — QThread dédié aux appels API (non-bloquant)
  • CopilotDockWidget — Panneau de chat rétractable (côté droit)
"""
from __future__ import annotations

import html
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QLineEdit,
    QPushButton,
    QLabel,
    QComboBox,
    QFrame,
    QSizePolicy,
)


# ═══════════════════════════════════════════════════════════════════
#  MistralWorker — QThread pour les appels API non-bloquants
# ═══════════════════════════════════════════════════════════════════
class MistralWorker(QThread):
    """Thread dédié à l'appel synchrone de l'API Mistral.

    Signals:
        response_ready(str) : réponse textuelle de Mistral
        error_occurred(str) : message d'erreur en cas d'échec
    """

    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        user_message: str,
        history: list[dict],
        main_window=None,
        language: str = "fr",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._user_message = user_message
        self._history = history
        self._main_window = main_window
        self._language = language

    def run(self) -> None:
        try:
            from ..ai.mistral_client import send_message

            reply = send_message(
                user_message=self._user_message,
                history=self._history,
                main_window=self._main_window,
                language=self._language,
            )
            self.response_ready.emit(reply)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


# ═══════════════════════════════════════════════════════════════════
#  CSS interne pour les bulles de chat
# ═══════════════════════════════════════════════════════════════════
_CHAT_CSS = """
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    margin: 0;
    padding: 4px;
    background-color: transparent;
    color: #2c2c2c;
}
.msg-row { margin: 6px 0; display: flex; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.bubble {
    max-width: 85%;
    padding: 10px 14px;
    border-radius: 14px;
    line-height: 1.45;
    word-wrap: break-word;
}
.bubble.user {
    background-color: #3a3a3a;
    color: #ffffff;
    border-bottom-right-radius: 4px;
}
.bubble.assistant {
    background-color: #ecedf2;
    color: #2c2c2c;
    border-bottom-left-radius: 4px;
}
.bubble.error {
    background-color: #e8e8e8;
    color: #555555;
    border-bottom-left-radius: 4px;
}
.typing {
    color: #6c6c6c;
    font-style: italic;
    padding: 6px 14px;
}
"""

_HTML_TEMPLATE = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CHAT_CSS}</style></head>
<body>{{content}}</body></html>"""

# ═══════════════════════════════════════════════════════════════════
#  Langues disponibles
# ═══════════════════════════════════════════════════════════════════
LANG_MAP: dict[str, str] = {
    "fr": "FR - Français",
    "en": "EN - English",
    "ar": "AR - العربية",
    "es": "ES - Español",
    "de": "DE - Deutsch",
}


# ═══════════════════════════════════════════════════════════════════
#  CopilotDockWidget — Interface de chat
# ═══════════════════════════════════════════════════════════════════
class CopilotDockWidget(QDockWidget):
    """Panneau rétractable intégrant un chatbot Mistral AI."""

    def __init__(self, main_window, parent: Optional[QWidget] = None) -> None:
        super().__init__("Assistant Copilot", parent or main_window)
        self.main_window = main_window

        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setMinimumWidth(340)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )

        # ── État interne ──
        self._history: list[dict] = []       # messages {role, content}
        self._html_parts: list[str] = []     # fragments HTML des bulles
        self._worker: Optional[MistralWorker] = None
        self._language: str = "fr"

        self._build_ui()

    # ── Construction de l'interface ────────────────────────────────
    def _build_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── Header ──
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background-color: #ecedf2; border-radius: 8px; padding: 4px; }"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)
        title = QLabel("CityPulse Copilot")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c2c2c;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        # Sélecteur de langue
        self.lang_combo = QComboBox()
        self.lang_combo.setFixedWidth(130)
        for code, label in LANG_MAP.items():
            self.lang_combo.addItem(label, code)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        h_layout.addWidget(self.lang_combo)

        # Bouton effacer
        clear_btn = QPushButton("Effacer")
        clear_btn.setToolTip("Effacer la conversation")
        clear_btn.setFixedSize(75, 32)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_chat)
        h_layout.addWidget(clear_btn)

        layout.addWidget(header)

        # ── Zone de chat ──
        self.chat_view = QTextBrowser()
        self.chat_view.setOpenExternalLinks(False)
        self.chat_view.setStyleSheet(
            "QTextBrowser { background-color: #ffffff; border: 1px solid #d8dce3; "
            "border-radius: 8px; }"
        )
        layout.addWidget(self.chat_view, 1)

        # ── Message d'accueil ──
        self._show_welcome()

        # ── Indicateur de chargement ──
        self.typing_label = QLabel("L'assistant ecrit...")
        self.typing_label.setStyleSheet(
            "color: #6c6c6c; font-style: italic; padding: 2px 8px;"
        )
        self.typing_label.setVisible(False)
        layout.addWidget(self.typing_label)

        # ── Zone de saisie ──
        input_frame = QFrame()
        input_frame.setStyleSheet(
            "QFrame { background-color: #ecedf2; border-radius: 8px; padding: 4px; }"
        )
        i_layout = QHBoxLayout(input_frame)
        i_layout.setContentsMargins(6, 4, 6, 4)
        i_layout.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Posez votre question...")
        self.input_field.setStyleSheet(
            "QLineEdit { background-color: #ffffff; border: 1px solid #d8dce3; "
            "border-radius: 6px; padding: 8px 12px; color: #2c2c2c; }"
            "QLineEdit:focus { border-color: #3a3a3a; }"
        )
        self.input_field.returnPressed.connect(self._on_send)
        i_layout.addWidget(self.input_field, 1)

        self.send_btn = QPushButton("Envoyer")
        self.send_btn.setToolTip("Envoyer")
        self.send_btn.setFixedSize(90, 36)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(
            "QPushButton { background-color: #ffffff; color: #2c2c2c; "
            "border: 1px solid #2c2c2c; border-radius: 0px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background-color: #f0f0f0; }"
            "QPushButton:disabled { background-color: #f5f5f5; color: #aaaaaa; border-color: #cccccc; }"
        )
        self.send_btn.clicked.connect(self._on_send)
        i_layout.addWidget(self.send_btn)

        layout.addWidget(input_frame)
        self.setWidget(container)

    # ── Message de bienvenue ──────────────────────────────────────
    def _show_welcome(self) -> None:
        welcome = (
            "Bonjour. Je suis <b>CityPulse Copilot</b>, votre assistant "
            "logistique. Posez-moi des questions sur vos tournees, clients, "
            "vehicules ou l'optimisation VRP."
        )
        self._html_parts = []
        self._append_bubble("assistant", welcome)
        self._refresh_view()

    # ── Gestion de la langue ──────────────────────────────────────
    def _on_lang_changed(self, index: int) -> None:
        self._language = self.lang_combo.itemData(index) or "fr"
        placeholders = {
            "fr": "Posez votre question...",
            "en": "Ask your question...",
            "ar": "...اطرح سؤالك",
            "es": "Haz tu pregunta...",
            "de": "Stellen Sie Ihre Frage...",
        }
        self.input_field.setPlaceholderText(
            placeholders.get(self._language, placeholders["fr"])
        )

    # ── Envoi d'un message ────────────────────────────────────────
    def _on_send(self) -> None:
        text = self.input_field.text().strip()
        if not text or self._worker is not None:
            return

        # Afficher la bulle utilisateur
        self._append_bubble("user", html.escape(text))
        self._refresh_view()

        # Préparer l'historique (on limite à 20 messages pour le contexte)
        self._history.append({"role": "user", "content": text})
        history_slice = self._history[-20:]

        # UI : bloquer la saisie + indicateur
        self.input_field.clear()
        self.send_btn.setEnabled(False)
        self.typing_label.setVisible(True)

        # Lancer le worker
        self._worker = MistralWorker(
            user_message=text,
            history=history_slice[:-1],  # ne pas dupliquer le dernier user msg
            main_window=self.main_window,
            language=self._language,
            parent=self,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    # ── Callbacks du worker ───────────────────────────────────────
    def _on_response(self, reply: str) -> None:
        self._history.append({"role": "assistant", "content": reply})
        safe_reply = html.escape(reply).replace("\n", "<br>")
        self._append_bubble("assistant", safe_reply)
        self._refresh_view()

    def _on_error(self, error_msg: str) -> None:
        safe_msg = html.escape(error_msg)
        self._append_bubble("error", f"Erreur : {safe_msg}")
        self._refresh_view()

    def _on_worker_done(self) -> None:
        self.send_btn.setEnabled(True)
        self.typing_label.setVisible(False)
        self._worker = None
        self.input_field.setFocus()

    # ── Effacer la conversation ───────────────────────────────────
    def _clear_chat(self) -> None:
        self._history.clear()
        self._show_welcome()

    # ── Helpers HTML ──────────────────────────────────────────────
    def _append_bubble(self, role: str, content: str) -> None:
        css_class = role  # "user", "assistant" ou "error"
        if role == "error":
            css_class_row = "assistant"
        else:
            css_class_row = role
        bubble = (
            f'<div class="msg-row {css_class_row}">'
            f'<div class="bubble {css_class}">{content}</div>'
            f"</div>"
        )
        self._html_parts.append(bubble)

    def _refresh_view(self) -> None:
        body = "\n".join(self._html_parts)
        full_html = _HTML_TEMPLATE.replace("{content}", body)
        self.chat_view.setHtml(full_html)
        # Scroll en bas
        sb = self.chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())
