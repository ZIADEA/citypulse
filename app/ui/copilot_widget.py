"""
CityPulse — Assistant Copilot (QDockWidget)
 • MistralWorker — QThread + db_stats + repli local
 • Chips suggestions, bandeau commande (Exécuter / Ignorer), signal command_ready
 • Onglet Analyse globale (texte + export PDF), persistance ai_conversations
"""
from __future__ import annotations

import html
import json
import logging
import re
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
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
  QGridLayout,
  QTabWidget,
  QFileDialog,
  QMessageBox,
)

from ..database.db_manager import get_connection

logger = logging.getLogger(__name__)

try:
  from reportlab.lib.pagesizes import A4
  from reportlab.pdfgen import canvas as rl_canvas
  HAS_REPORTLAB = True
except ImportError:
  HAS_REPORTLAB = False


class MistralWorker(QThread):
  response_ready = pyqtSignal(str)
  error_occurred = pyqtSignal(str)

  def __init__(
    self,
    user_message: str,
    history: list[dict],
    db_stats: Optional[dict],
    language: str = "fr",
    parent: Optional[QWidget] = None,
  ) -> None:
    super().__init__(parent)
    self._user_message = user_message
    self._history = history
    self._db_stats = db_stats
    self._language = language

  def run(self) -> None:
    try:
      from ..ai.mistral_client import send_message, get_fallback_response

      reply = send_message(
        user_message=self._user_message,
        history=self._history,
        db_stats=self._db_stats,
        language=self._language,
      )
      self.response_ready.emit(reply)
    except Exception as exc:
      logger.warning("MistralWorker: %s", exc)
      self.error_occurred.emit(str(exc))


_CHAT_CSS = """
body {
  font-family: 'Segoe UI', Arial, sans-serif;
  font-size: 13px;
  margin: 0;
  padding: 4px;
  background-color: transparent;
  color: #E8F4F8;
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
  background-color: #0A4A6E;
  color: #E8F4F8;
  border-bottom-right-radius: 4px;
}
.bubble.assistant {
  background-color: #162840;
  color: #E8F4F8;
  border: 1px solid #1E3A50;
  border-bottom-left-radius: 4px;
}
.bubble.error {
  background-color: #2A1515;
  color: #FF9999;
  border-bottom-left-radius: 4px;
}
"""

_HTML_TEMPLATE = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CHAT_CSS}</style></head>
<body>{{content}}</body></html>"""

LANG_MAP: dict[str, str] = {
  "fr": "FR - Français",
  "en": "EN - English",
  "ar": "AR - العربية",
  "es": "ES - Español",
  "de": "DE - Deutsch",
}

_QUICK_CHIPS: list[tuple[str, str]] = [
  ("Résumé de mon activité", "Fais un court résumé de mon activité logistique avec les chiffres du contexte."),
  ("Optimiser mes tournées", "Quelles étapes pour bien optimiser mes tournées avec CityPulse "),
  ("Ouvrir Optimisation", 'Réponds brièvement puis propose cette action JSON : {"action":"optimize"}'),
  ("Nouvelle commande", 'Je veux créer une commande. Réponds puis si pertinent : {"action":"create_order"}'),
  ("Clients & créneaux", "Quelles erreurs fréquentes sur les créneaux clients et comment les éviter "),
  ("Rapports & exports", "Comment exporter un rapport PDF ou Excel depuis CityPulse "),
]


class CopilotDockWidget(QDockWidget):
  command_ready = pyqtSignal(dict)

  def __init__(self, main_window, parent: Optional[QWidget] = None) -> None:
    super().__init__("Assistant Copilot", parent or main_window)
    self.main_window = main_window

    self.setAllowedAreas(
      Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
    )
    self.setMinimumWidth(360)
    self.setFeatures(
      QDockWidget.DockWidgetFeature.DockWidgetClosable
      | QDockWidget.DockWidgetFeature.DockWidgetMovable
      | QDockWidget.DockWidgetFeature.DockWidgetFloatable
    )

    self._history: list[dict] = []
    self._html_parts: list[str] = []
    self._worker: Optional[MistralWorker] = None
    self._analysis_worker: Optional[MistralWorker] = None
    self._language: str = "fr"
    self._pending_command: Optional[dict] = None

    self._build_ui()
    self._load_conversation_from_db()

  def _collect_db_stats(self) -> dict:
    stats: dict = {}
    try:
      conn = get_connection()
      row = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(demand_kg),0) AS total_kg "
        "FROM clients WHERE archived=0"
      ).fetchone()
      stats["clients_active"] = row["total"]
      stats["total_demand_kg"] = float(row["total_kg"] or 0)

      row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status='disponible' THEN 1 ELSE 0 END) AS dispo FROM vehicles"
      ).fetchone()
      stats["vehicles_total"] = row["total"]
      stats["vehicles_available"] = row["dispo"] or 0

      stats["depots"] = conn.execute("SELECT COUNT(*) AS n FROM depots").fetchone()["n"]

      last = conn.execute(
        "SELECT algorithm, total_distance, client_count "
        "FROM algo_results ORDER BY created_at DESC LIMIT 1"
      ).fetchone()
      if last:
        stats["last_optimization"] = {
          "algorithm": last["algorithm"],
          "total_distance": float(last["total_distance"] or 0),
          "client_count": int(last["client_count"] or 0),
        }
      conn.close()
    except Exception:
      logger.exception("Copilot _collect_db_stats")

    fn = getattr(self.main_window, "get_active_page_title", None)
    if callable(fn):
      title = fn()
      if title:
        stats["active_page"] = title
    return stats

  def _persist_conversation(self) -> None:
    user = getattr(self.main_window, "current_user", None)
    if not user:
      return
    uid = user["id"]
    try:
      conn = get_connection()
      payload = json.dumps(self._history, ensure_ascii=False) if self._history else "[]"
      row = conn.execute(
        "SELECT id FROM ai_conversations WHERE user_id= ? ORDER BY updated_at DESC LIMIT 1",
        (uid,),
      ).fetchone()
      if row:
        conn.execute(
          "UPDATE ai_conversations SET messages_json= ?, updated_at=datetime('now') WHERE id= ?",
          (payload, row["id"]),
        )
      else:
        conn.execute(
          "INSERT INTO ai_conversations (user_id, messages_json) VALUES (?,?)",
          (uid, payload),
        )
      conn.commit()
      conn.close()
    except Exception:
      logger.exception("Copilot persist")

  def _load_conversation_from_db(self) -> None:
    user = getattr(self.main_window, "current_user", None)
    if not user:
      return
    try:
      conn = get_connection()
      row = conn.execute(
        "SELECT messages_json FROM ai_conversations WHERE user_id= ? ORDER BY updated_at DESC LIMIT 1",
        (user["id"],),
      ).fetchone()
      conn.close()
      if row and row["messages_json"]:
        data = json.loads(row["messages_json"])
        if isinstance(data, list) and data:
          self._history = data
          self._html_parts = []
          for m in data:
            role = m.get("role", "assistant")
            raw = m.get("content", "")
            if role == "user":
              self._append_bubble("user", html.escape(raw).replace("\n", "<br>"))
            else:
              self._append_bubble("assistant", self._md_to_html(raw))
          self._refresh_view()
          return
    except Exception:
      logger.exception("Copilot load history")
    self._show_welcome()

  def _build_ui(self) -> None:
    outer = QWidget()
    outer.setObjectName("copilotOuter")
    outer.setStyleSheet(
      "QWidget#copilotOuter { background: #0D1B2A; }"
    )
    lo = QVBoxLayout(outer)
    lo.setContentsMargins(6, 6, 6, 6)
    lo.setSpacing(6)
    self.setStyleSheet(
      "QDockWidget { background: #0D1B2A; color: #E8F4F8; }"
      "QDockWidget::title { background: #162840; color: #E8F4F8; padding: 4px 8px; }"
    )

    header = QFrame()
    header.setStyleSheet(
      "QFrame { background-color: #162840; border-radius: 8px; padding: 4px;"
      " border: 1px solid #1E3A50; }"
    )
    h_layout = QHBoxLayout(header)
    h_layout.setContentsMargins(8, 4, 8, 4)
    title = QLabel("CityPulse Copilot")
    title.setStyleSheet("font-weight: bold; font-size: 14px; color: #E8F4F8;"
                        " background: transparent; border: none;")
    h_layout.addWidget(title)
    h_layout.addStretch()

    self.lang_combo = QComboBox()
    self.lang_combo.setFixedWidth(130)
    for code, label in LANG_MAP.items():
      self.lang_combo.addItem(label, code)
    self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
    h_layout.addWidget(self.lang_combo)

    clear_btn = QPushButton("Effacer")
    clear_btn.setToolTip("Effacer la conversation")
    clear_btn.setFixedSize(75, 32)
    clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    clear_btn.setStyleSheet(
      "QPushButton { background: #1A3A5C; color: #E8F4F8; border: 1px solid #1E3A50;"
      " border-radius: 5px; font-size: 12px; }"
      "QPushButton:hover { background: #FF4757; border-color: #FF4757; }"
    )
    clear_btn.clicked.connect(self._clear_chat)
    h_layout.addWidget(clear_btn)

    lo.addWidget(header)

    self.tabs = QTabWidget()
    self.tabs.setStyleSheet(
      "QTabWidget::pane { border: 1px solid #1E3A50; border-radius: 8px;"
      " background: #0D1B2A; }"
      "QTabBar::tab { background: #162840; color: #7FA8C0; padding: 6px 14px;"
      " border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }"
      "QTabBar::tab:selected { background: #00D4FF; color: #0D1B2A; font-weight: 700; }"
      "QTabBar::tab:hover { background: #1A3A5C; color: #E8F4F8; }"
    )

    chat_page = QWidget()
    c_lo = QVBoxLayout(chat_page)
    c_lo.setContentsMargins(0, 4, 0, 0)

    chips = QFrame()
    cg = QGridLayout(chips)
    cg.setContentsMargins(0, 0, 0, 0)
    cg.setSpacing(4)
    for i, (label, full) in enumerate(_QUICK_CHIPS):
      b = QPushButton(label)
      b.setCursor(Qt.CursorShape.PointingHandCursor)
      b.setStyleSheet(
        "QPushButton { font-size: 11px; padding: 4px 8px; border-radius: 12px; "
        "background: #1A3A5C; color: #E8F4F8; border: 1px solid #1E3A50; }"
        "QPushButton:hover { background: #0A4A6E; border-color: #00D4FF; color: #00D4FF; }"
      )
      b.clicked.connect(lambda _, t=full: self._send_text(t))
      cg.addWidget(b, i // 3, i % 3)
    c_lo.addWidget(chips)

    self._proposal_frame = QFrame()
    self._proposal_frame.setVisible(False)
    self._proposal_frame.setStyleSheet(
      "QFrame { background: #2A2010; border: 1px solid #C4A800; border-radius: 6px; }"
    )
    pr = QVBoxLayout(self._proposal_frame)
    self._proposal_label = QLabel()
    self._proposal_label.setWordWrap(True)
    self._proposal_label.setStyleSheet(
      "color: #FFD966; font-size: 12px; background: transparent; border: none;"
    )
    pr.addWidget(self._proposal_label)
    _btn_dark = (
      "QPushButton { border-radius: 5px; font-size: 12px; padding: 4px 12px; }"
    )
    pb = QHBoxLayout()
    self._btn_exec = QPushButton("Exécuter")
    self._btn_exec.setCursor(Qt.CursorShape.PointingHandCursor)
    self._btn_exec.setStyleSheet(
      _btn_dark + "QPushButton { background: #00D4FF; color: #0D1B2A; border: none; font-weight: 700; }"
      "QPushButton:hover { background: #33DEFF; }"
    )
    self._btn_exec.clicked.connect(self._execute_proposal)
    self._btn_ignore = QPushButton("Ignorer")
    self._btn_ignore.setCursor(Qt.CursorShape.PointingHandCursor)
    self._btn_ignore.setStyleSheet(
      _btn_dark + "QPushButton { background: #1A3A5C; color: #E8F4F8; border: 1px solid #1E3A50; }"
      "QPushButton:hover { background: #FF4757; border-color: #FF4757; }"
    )
    self._btn_ignore.clicked.connect(self._ignore_proposal)
    pb.addWidget(self._btn_exec)
    pb.addWidget(self._btn_ignore)
    pb.addStretch()
    pr.addLayout(pb)
    c_lo.addWidget(self._proposal_frame)

    self.chat_view = QTextBrowser()
    self.chat_view.setOpenExternalLinks(False)
    self.chat_view.setStyleSheet(
      "QTextBrowser { background-color: #0A1628; border: 1px solid #1E3A50; "
      "border-radius: 8px; color: #E8F4F8; }"
    )
    c_lo.addWidget(self.chat_view, 1)

    self.typing_label = QLabel("L'assistant écrit…")
    self.typing_label.setStyleSheet(
      "color: #7FA8C0; font-style: italic; padding: 2px 8px; background: transparent;"
    )
    self.typing_label.setVisible(False)
    c_lo.addWidget(self.typing_label)

    input_frame = QFrame()
    input_frame.setStyleSheet(
      "QFrame { background-color: #0D1B2A; border-radius: 8px; padding: 4px;"
      " border: 1px solid #1E3A50; }"
    )
    i_layout = QHBoxLayout(input_frame)
    i_layout.setContentsMargins(6, 4, 6, 4)
    self.input_field = QLineEdit()
    self.input_field.setPlaceholderText("Posez votre question…")
    self.input_field.setStyleSheet(
      "QLineEdit { background-color: #0A1628; border: 1px solid #1E3A50; "
      "border-radius: 6px; padding: 8px 12px; color: #E8F4F8; }"
      "QLineEdit:focus { border-color: #00D4FF; }"
    )
    self.input_field.returnPressed.connect(self._on_send)
    i_layout.addWidget(self.input_field, 1)
    self.send_btn = QPushButton("Envoyer")
    self.send_btn.setFixedSize(90, 36)
    self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.send_btn.setStyleSheet(
      "QPushButton { background: #00D4FF; color: #0D1B2A; border: none;"
      " border-radius: 6px; font-weight: 700; font-size: 13px; }"
      "QPushButton:hover { background: #33DEFF; }"
      "QPushButton:disabled { background: #1E3A50; color: #7FA8C0; }"
    )
    self.send_btn.clicked.connect(self._on_send)
    i_layout.addWidget(self.send_btn)
    c_lo.addWidget(input_frame)

    self.tabs.addTab(chat_page, "Chat")

    analysis = QWidget()
    a_lo = QVBoxLayout(analysis)
    self.analysis_edit = QTextBrowser()
    self.analysis_edit.setOpenExternalLinks(False)
    self.analysis_edit.setHtml(
      "<p style='color:#7FA8C0; font-style:italic;'>Synthèse globale : cliquez sur "
      "<b>Générer</b> pour interroger l'IA avec tout le contexte, puis exportez en PDF.</p>"
    )
    self.analysis_edit.setStyleSheet(
      "QTextBrowser { font-size: 12px; border: 1px solid #1E3A50; border-radius: 8px;"
      " background: #0A1628; color: #E8F4F8; }"
    )
    a_lo.addWidget(self.analysis_edit, 1)
    _ab_btn = (
      "QPushButton { border-radius: 5px; font-size: 12px; padding: 5px 14px;"
      " border: none; font-weight: 600; }"
    )
    ab = QHBoxLayout()
    self.btn_synth = QPushButton("Générer l'analyse")
    self.btn_synth.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_synth.setStyleSheet(
      _ab_btn + "QPushButton { background: #00D4FF; color: #0D1B2A; }"
      "QPushButton:hover { background: #33DEFF; }"
    )
    self.btn_synth.clicked.connect(self._run_global_analysis)
    self.btn_pdf = QPushButton("Exporter PDF")
    self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_pdf.setStyleSheet(
      _ab_btn + "QPushButton { background: #1A3A5C; color: #E8F4F8;"
      " border: 1px solid #1E3A50; }"
      "QPushButton:hover { background: #0A4A6E; }"
    )
    self.btn_pdf.clicked.connect(self._export_analysis_pdf)
    ab.addWidget(self.btn_synth)
    ab.addWidget(self.btn_pdf)
    ab.addStretch()
    a_lo.addLayout(ab)
    self.tabs.addTab(analysis, "Analyse globale")

    lo.addWidget(self.tabs, 1)
    self.setWidget(outer)

  def _on_lang_changed(self, index: int) -> None:
    self._language = self.lang_combo.itemData(index) or "fr"
    placeholders = {
      "fr": "Posez votre question…",
      "en": "Ask your question…",
      "ar": "...اطرح سؤالك",
      "es": "Haz tu pregunta…",
      "de": "Stellen Sie Ihre Frage…",
    }
    self.input_field.setPlaceholderText(
      placeholders.get(self._language, placeholders["fr"])
    )

  def _send_text(self, text: str) -> None:
    self.input_field.setText(text)
    self._on_send()

  def _show_welcome(self) -> None:
    welcome = (
      "Bonjour. Je suis <b>CityPulse Copilot</b>, votre assistant "
      "logistique. Utilisez les suggestions rapides ou posez une question."
    )
    self._html_parts = []
    self._history = []
    self._append_bubble("assistant", welcome)
    self._refresh_view()

  def _on_send(self) -> None:
    text = self.input_field.text().strip()
    if not text or self._worker is not None:
      return
    self._proposal_frame.setVisible(False)
    self._pending_command = None

    self._append_bubble("user", html.escape(text))
    self._refresh_view()

    self._history.append({"role": "user", "content": text})
    history_slice = self._history[-20:]

    self.input_field.clear()
    self.send_btn.setEnabled(False)
    self.typing_label.setVisible(True)

    self._worker = MistralWorker(
      user_message=text,
      history=history_slice[:-1],
      db_stats=self._collect_db_stats(),
      language=self._language,
      parent=self,
    )
    self._worker.response_ready.connect(self._on_response)
    self._worker.error_occurred.connect(self._on_error)
    self._worker.finished.connect(self._on_worker_done)
    self._worker.start()

  def _on_response(self, reply: str) -> None:
    self._history.append({"role": "assistant", "content": reply})
    self._append_bubble("assistant", self._md_to_html(reply))
    self._refresh_view()
    self._persist_conversation()
    self._maybe_show_proposal(reply)

  def _maybe_show_proposal(self, reply: str) -> None:
    from ..ai.mistral_client import parse_command

    cmd = parse_command(reply)
    if not cmd:
      return
    self._pending_command = cmd
    self._proposal_label.setText(
      f"Action proposée : <b>{cmd.get('action')}</b> — Exécuter dans l'application "
    )
    self._proposal_frame.setVisible(True)

  def _execute_proposal(self) -> None:
    if self._pending_command:
      self.command_ready.emit(dict(self._pending_command))
    self._proposal_frame.setVisible(False)
    self._pending_command = None

  def _ignore_proposal(self) -> None:
    self._proposal_frame.setVisible(False)
    self._pending_command = None

  def _on_error(self, error_msg: str) -> None:
    safe_msg = html.escape(error_msg)
    self._append_bubble("error", f"Erreur : {safe_msg}")
    self._refresh_view()

  def _on_worker_done(self) -> None:
    self.send_btn.setEnabled(True)
    self.typing_label.setVisible(False)
    self._worker = None
    self.input_field.setFocus()

  def _clear_chat(self) -> None:
    self._history.clear()
    self._proposal_frame.setVisible(False)
    self._pending_command = None
    self._show_welcome()
    self._persist_conversation()

  def _run_global_analysis(self) -> None:
    if self._analysis_worker is not None:
      return
    prompt = (
      "Rédige une analyse opérationnelle structurée (sections : flotte, clients, "
      "dernière optimisation, recommandations) en t'appuyant sur les statistiques fournies. "
      "Sois factuel et actionnable."
    )
    self.btn_synth.setEnabled(False)
    self.analysis_edit.setHtml("<p style='color:#7FA8C0; font-style:italic;'>Génération en cours…</p>")
    stats = self._collect_db_stats()
    self._analysis_worker = MistralWorker(
      user_message=prompt,
      history=[],
      db_stats=stats,
      language=self._language,
      parent=self,
    )
    self._analysis_worker.response_ready.connect(self._on_analysis_ready)
    self._analysis_worker.finished.connect(self._on_analysis_done)
    self._analysis_worker.start()

  def _on_analysis_ready(self, text: str) -> None:
    self.analysis_edit.setMarkdown(text)

  def _on_analysis_done(self) -> None:
    self.btn_synth.setEnabled(True)
    self._analysis_worker = None

  def _export_analysis_pdf(self) -> None:
    if not HAS_REPORTLAB:
      QMessageBox.warning(
        self,
        "Export PDF",
        "Le module reportlab n'est pas disponible. Installez-le avec pip.",
      )
      return
    path, _ = QFileDialog.getSaveFileName(
      self, "Exporter l'analyse", "", "PDF (*.pdf)"
    )
    if not path:
      return
    if not path.lower().endswith(".pdf"):
      path += ".pdf"
    text = self.analysis_edit.toPlainText()
    try:
      c = rl_canvas.Canvas(path, pagesize=A4)
      w, h = A4
      y = h - 50
      c.setFont("Helvetica-Bold", 14)
      c.drawString(40, y, "Analyse opérationnelle — CityPulse Copilot")
      y -= 30
      c.setFont("Helvetica", 11)
      for line in text.split("\n"):
        if not line.strip():
          y -= 6
          continue
        if y < 60:
          c.showPage()
          y = h - 50
          c.setFont("Helvetica", 11)
        while len(line) > 95:
          c.drawString(40, y, line[:95])
          line = "    " + line[95:]
          y -= 14
          if y < 60:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 11)
        c.drawString(40, y, line)
        y -= 14
      c.save()
      QMessageBox.information(self, "Export PDF", f"Fichier enregistré :\n{path}")
    except Exception as e:
      QMessageBox.critical(self, "Export PDF", str(e))

  def _md_to_html(self, text: str) -> str:
    result = []
    for line in text.split("\n"):
      escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
      if escaped.startswith("### "):
        result.append(f"<b>{escaped[4:]}</b><br>")
        continue
      if escaped.startswith("## "):
        result.append(f"<b>{escaped[3:]}</b><br>")
        continue
      if escaped.startswith("# "):
        result.append(f"<b>{escaped[2:]}</b><br>")
        continue
      if escaped.strip() in ("---", "***", "___"):
        result.append("<hr>")
        continue
      escaped = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", escaped)
      escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
      escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
      stripped = escaped.strip()
      if stripped.startswith("- ") or stripped.startswith("• "):
        escaped = "&nbsp;&nbsp;• " + stripped[2:]
      result.append(escaped + "<br>")
    return "".join(result)

  def _append_bubble(self, role: str, content: str) -> None:
    css_class = role
    css_class_row = "assistant" if role == "error" else role
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
    sb = self.chat_view.verticalScrollBar()
    sb.setValue(sb.maximum())
