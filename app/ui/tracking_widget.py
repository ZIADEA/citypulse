"""
tracking_widget.py — Suivi en temps réel v3.0
===============================================
Layout QVBoxLayout principal :
  ┌─ Barre simulation : > Pause Stop Fast×2 FastFast×5 | slider | HH:MM ─────────┐
  ├─ Barre météo : QComboBox + OWM + traffic_factor ──────────────────┤
  ├─ 5 KPICards mini (véhicules actifs, livraisons, retards, km, CO2) ┤
  └─ QSplitter 70/30 ─────────────────────────────────────────────────┘
       GAUCHE QTabWidget :
          Gantt (GanttWidget QPainter pur)
          Tableau (QTableWidget + QTimer 1s)
       DROITE Incidents :
         Notifications non lues + signalement + bandeau re-optim

Signaux :
  route_updated(vehicle_id: int, stops_json: str)  → MapWidget
  center_on_vehicle(vehicle_id: int)               → MapWidget
  reoptimization_done(dict)                        → OptimizationWidget
"""

# ── stdlib ─────────────────────────────────────────────────────────────────────
import json
import logging
from datetime import datetime, date, timedelta
from collections import deque

# ── PyQt6 ──────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFrame, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QSizePolicy, QToolTip, QMenu, QMessageBox,
    QDialog, QFormLayout, QTextEdit, QLineEdit, QFileDialog,
)
from PyQt6.QtCore import (
    Qt, QTimer, QRect, QPoint, QSize, pyqtSignal, QMimeData,
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QFontMetrics, QCursor, QDragEnterEvent, QDropEvent,
    QMouseEvent, QWheelEvent, QAction,
)

# ── Local ──────────────────────────────────────────────────────────────────────
from ..database.db_manager import get_connection, log_action
from .components.confirm_dialog import _dialog_qss
from ..engine.traffic_adjuster import get_traffic_coefficient, classify_day_type
from .toast import show_toast
from .help_dialog import show_help
from .lucide_icons import apply_action_button
from .components import KPICard, ConfirmDialog, StatusBadge

try:
    import keyring as _keyring; HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

try:
    import requests as _requests; HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.units import cm as rl_cm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

logger = logging.getLogger(__name__)

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "bg":     "#0D1B2A", "panel":  "#112240", "input":  "#1A2E4A",
    "accent": "#00D4FF", "success":"#00FF88", "warning":"#FFB800",
    "danger": "#FF4757", "text":   "#E8F4FD", "text2":  "#8899AA",
    "border": "#1E3A5F", "hover":  "#1A3A5C", "orange": "#FF8C00",
    "purple": "#8B5CF6",
}

# Gantt couleurs blocs
G = {
    "travel":   "#1A6CF6",   # trajet → bleu
    "visit":    "#00CC66",   # visite → vert
    "pause":    "#5A6A7A",   # pause  → gris
    "reload":   "#FF8C00",   # rechargement → orange
    "delay":    "#FF4757",   # retard → rouge (hachures)
    "locked":   "#8B5CF6",   # tournée verrouillée
}

# Plage horaire Gantt
GANTT_START_H = 6   # 06:00
GANTT_END_H   = 20  # 20:00
GANTT_MINS    = (GANTT_END_H - GANTT_START_H) * 60   # 840 min

ROW_H   = 48     # hauteur ligne véhicule (px)
HDR_H   = 32     # hauteur entête timeline
LEFT_W  = 110    # largeur colonne labels véhicules

_BTN_S = (
    "QPushButton{{background:{bg};color:{fg};border:{br};border-radius:5px;"
    "font-size:{fs};padding:{pad};}}"
    "QPushButton:hover{{background:{hv};}}"
)


def _sim_btn(label: str, tip: str, min_w: int = 36) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(30)
    btn.setMinimumWidth(min_w)
    btn.setToolTip(tip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        _BTN_S.format(
            bg=C["input"], fg=C["text"], br=f"1px solid {C['border']}",
            fs="13px", pad="0 8px", hv=C["hover"]
        )
    )
    return btn


# ═══════════════════════════════════════════════════════════════════════════════
# GANTT WIDGET — QPainter pur
# ═══════════════════════════════════════════════════════════════════════════════

class GanttWidget(QWidget):
    """
    Gantt chart QPainter pur.
    Supporte : zoom molette, drag & drop blocs, hover tooltip, clic droit menu.
    """
    block_moved     = pyqtSignal(int, int, int)   # vehicle_idx, block_idx, new_start_min
    block_locked    = pyqtSignal(int, bool)        # vehicle_idx, locked
    block_cancelled = pyqtSignal(int, int)         # vehicle_idx, block_idx

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._vehicles: list[dict]  = []   # [{label, color, blocks, locked}]
        self._sim_min: float        = 0.0  # minutes depuis 06:00
        self._zoom: float           = 1.0  # 1.0 = normal, 2.0 = x2
        self._scroll_x: int         = 0    # décalage horizontal en px
        self._hover_block           = None # (v_idx, b_idx)
        self._drag_block            = None # (v_idx, b_idx, drag_start_x)
        self._drag_orig_start       = 0
        self._undo_stack: deque     = deque(maxlen=20)
        self._locked: set[int]      = set()

        self.setStyleSheet(f"background:{C['bg']};border:1px solid {C['border']};border-radius:6px;")

    def _required_height(self) -> int:
        return HDR_H + max(len(self._vehicles), 4) * ROW_H

    # ── Données ────────────────────────────────────────────────────────

    def set_data(self, vehicles: list):
        """
        vehicles : list[dict] avec clés :
          label      str
          color      str (hex)
          blocks     list[dict] : type, start_min, dur_min, label, client_idx
          locked     bool
        """
        self._vehicles = vehicles
        self.setFixedHeight(self._required_height())
        self.update()

    def set_sim_time(self, minutes_since_start: float):
        """minutes_since_start depuis 06:00."""
        self._sim_min = minutes_since_start
        self.update()

    # ── Geometry helpers ────────────────────────────────────────────────

    def _min_to_x(self, minutes: float) -> int:
        frac = (minutes - 0) / GANTT_MINS
        total_w = (self.width() - LEFT_W) * self._zoom
        return LEFT_W + int(frac * total_w) - self._scroll_x

    def _x_to_min(self, x: int) -> float:
        total_w = (self.width() - LEFT_W) * self._zoom
        return ((x + self._scroll_x - LEFT_W) / total_w) * GANTT_MINS

    def _row_y(self, v_idx: int) -> int:
        return HDR_H + v_idx * ROW_H

    def _block_rect(self, v_idx: int, block: dict) -> QRect:
        x1 = self._min_to_x(block["start_min"])
        x2 = self._min_to_x(block["start_min"] + block["dur_min"])
        y  = self._row_y(v_idx) + 4
        return QRect(x1, y, max(x2 - x1, 4), ROW_H - 8)

    # ── Painting ────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(C["bg"]))

        # Header timeline
        self._draw_header(p, w)

        # Lignes véhicules
        for v_idx, veh in enumerate(self._vehicles):
            self._draw_vehicle_row(p, v_idx, veh, w)

        # Ligne rouge heure simulation
        self._draw_sim_line(p, h)

        p.end()

    def _draw_header(self, p: QPainter, w: int):
        p.fillRect(0, 0, w, HDR_H, QColor(C["panel"]))
        p.setPen(QColor(C["border"]))
        p.drawLine(0, HDR_H - 1, w, HDR_H - 1)

        font = QFont("Segoe UI", 8)
        p.setFont(font)
        p.setPen(QColor(C["text2"]))

        # Pas adaptatif : 30 min si assez d'espace, sinon 60 min
        available_w = max(w - LEFT_W, 1)
        px_per_30min = available_w * self._zoom * 30 / GANTT_MINS
        step = 30 if px_per_30min >= 44 else 60
        label_half = 22   # demi-largeur de la boîte de texte

        for i in range(0, GANTT_MINS + 1, step):
            x = self._min_to_x(i)
            if x < LEFT_W + label_half or x > w - label_half: continue
            total_h = GANTT_START_H * 60 + i
            hh, mm  = divmod(total_h, 60)
            lbl     = f"{hh:02d}:{mm:02d}"
            p.setPen(QColor(C["text2"]))
            p.drawText(x - label_half, 2, label_half * 2, HDR_H - 4,
                       Qt.AlignmentFlag.AlignCenter, lbl)
            p.setPen(QColor(C["border"]))
            p.drawLine(x, HDR_H - 6, x, HDR_H)

        # Colonne labels (redessiner par-dessus pour masquer le débord gauche)
        p.fillRect(0, 0, LEFT_W, HDR_H, QColor(C["panel"]))
        p.setPen(QColor(C["text2"]))
        p.drawText(0, 0, LEFT_W, HDR_H, Qt.AlignmentFlag.AlignCenter, "Véhicule")

    def _draw_vehicle_row(self, p: QPainter, v_idx: int, veh: dict, w: int):
        y   = self._row_y(v_idx)
        col = QColor(C["hover"]) if v_idx % 2 == 0 else QColor(C["bg"])
        p.fillRect(0, y, w, ROW_H, col)

        # Séparateur horizontal
        p.setPen(QPen(QColor(C["border"]), 1))
        p.drawLine(0, y + ROW_H - 1, w, y + ROW_H - 1)

        # Label véhicule (colonne gauche)
        label_color = C["purple"] if veh.get("locked") else C["text"]
        p.setPen(QColor(label_color))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(2, y, LEFT_W - 4, ROW_H, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   veh.get("label", ""))

        # Séparateur vertical label/timeline
        p.setPen(QPen(QColor(C["border"]), 1))
        p.drawLine(LEFT_W, y, LEFT_W, y + ROW_H)

        # Blocs
        for b_idx, block in enumerate(veh.get("blocks", [])):
            self._draw_block(p, v_idx, b_idx, block, veh.get("locked", False))

    def _draw_block(self, p: QPainter, v_idx: int, b_idx: int, block: dict, locked: bool):
        rect = self._block_rect(v_idx, block)
        if rect.right() < LEFT_W or rect.left() > self.width():
            return   # hors écran

        btype = block.get("type", "travel")
        is_hover = self._hover_block == (v_idx, b_idx)

        base_color = G.get(btype, G["travel"])
        if locked:
            base_color = G["locked"]

        color = QColor(base_color)
        if is_hover:
            color = color.lighter(130)

        # Fond bloc
        radius = 4
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()),
                            float(rect.width()), float(rect.height()), radius, radius)
        p.fillPath(path, QBrush(color))

        # Hachures pour retard
        if btype == "delay":
            hatch_pen = QPen(QColor(255, 71, 87, 160), 1.5)
            p.setPen(hatch_pen)
            step = 6
            x0, y0, x1, y1 = rect.left(), rect.top(), rect.right(), rect.bottom()
            for offset in range(0, (x1 - x0) + (y1 - y0), step):
                p.drawLine(max(x0, x0 + offset - (y1 - y0)), min(y1, y0 + offset ),
                           min(x1, x0 + offset ), max(y0, y1 - (x1 - x0) + offset))

        # Bordure
        border_col = color.darker(150) if not is_hover else QColor(C["accent"])
        p.setPen(QPen(border_col, 1))
        p.drawPath(path)

        # Texte si bloc assez large
        if rect.width() > 35:
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("Segoe UI", 7))
            lbl = block.get("label", btype[:3].upper())[:12]
            p.drawText(rect.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignCenter, lbl)

    def _draw_sim_line(self, p: QPainter, h: int):
        x = self._min_to_x(self._sim_min)
        if x < LEFT_W or x > self.width():
            return
        pen = QPen(QColor("#FF0040"), 2, Qt.PenStyle.SolidLine)
        p.setPen(pen)
        p.drawLine(x, HDR_H, x, h)
        # Triangle indicateur
        tri = QPainterPath()
        tri.moveTo(x - 6, HDR_H)
        tri.lineTo(x + 6, HDR_H)
        tri.lineTo(x, HDR_H + 10)
        tri.closeSubpath()
        p.fillPath(tri, QBrush(QColor("#FF0040")))

    # ── Mouse events ────────────────────────────────────────────────────

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.pos()
        found = self._block_at(pos)
        if found != self._hover_block:
            self._hover_block = found
            self.update()
        if found:
            v_idx, b_idx = found
            block = self._vehicles[v_idx]["blocks"][b_idx]
            start_h = int(GANTT_START_H + block["start_min"] // 60)
            start_m = int(block["start_min"] % 60)
            dur = block["dur_min"]
            tip = (
                f"<b>{block.get('label', block['type'])}</b><br>"
                f"Début : {start_h:02d}:{start_m:02d}<br>"
                f"Durée : {int(dur)} min<br>"
                f"Type : {block['type']}"
            )
            if block.get("client"):
                tip += f"<br>Client : {block['client']}"
            QToolTip.showText(QCursor.pos(), tip, self)

        # Drag logic
        if self._drag_block and e.buttons() & Qt.MouseButton.LeftButton:
            v_idx, b_idx, drag_start_x = self._drag_block
            delta_px  = pos.x() - drag_start_x
            total_w   = (self.width() - LEFT_W) * self._zoom
            delta_min = (delta_px / total_w) * GANTT_MINS if total_w > 0 else 0
            new_start = max(0, self._drag_orig_start + delta_min)
            new_start = min(new_start, GANTT_MINS - 10)
            self._vehicles[v_idx]["blocks"][b_idx]["start_min"] = new_start
            self.update()

    def mousePressEvent(self, e: QMouseEvent):
        pos = e.pos()
        found = self._block_at(pos)
        if not found:
            return
        v_idx, b_idx = found
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_block = (v_idx, b_idx, pos.x())
            self._drag_orig_start = self._vehicles[v_idx]["blocks"][b_idx]["start_min"]
        elif e.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(v_idx, b_idx, e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._drag_block and e.button() == Qt.MouseButton.LeftButton:
            v_idx, b_idx, _ = self._drag_block
            new_start = self._vehicles[v_idx]["blocks"][b_idx]["start_min"]
            if abs(new_start - self._drag_orig_start) > 1:
                if ConfirmDialog.ask(
                    self, "Déplacer bloc",
                    f"Déplacer cet arrêt à {GANTT_START_H:02d}:00 + {int(new_start)} min ",
                    "warning"
                ):
                    self._push_undo(v_idx, b_idx, self._drag_orig_start)
                    self.block_moved.emit(v_idx, b_idx, int(new_start))
                    log_action("GANTT_BLOCK_MOVED",
                               f"Véhicule {v_idx} bloc {b_idx} → {int(new_start)} min")
                else:
                    self._vehicles[v_idx]["blocks"][b_idx]["start_min"] = self._drag_orig_start
                    self.update()
            self._drag_block = None

    def wheelEvent(self, e: QWheelEvent):
        delta = e.angleDelta().y()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if delta > 0 else 0.87
            self._zoom = max(0.5, min(8.0, self._zoom * factor))
        else:
            self._scroll_x = max(0, self._scroll_x - delta // 4)
        self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Z and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._undo()
        super().keyPressEvent(e)

    # ── Context menu ────────────────────────────────────────────────────

    def _show_context_menu(self, v_idx: int, b_idx: int, pos: QPoint):
        veh   = self._vehicles[v_idx]
        block = veh["blocks"][b_idx]
        locked = veh.get("locked", False)

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};"
            "border-radius:6px;padding:4px;}}"
            f"QMenu::item{{padding:6px 18px;border-radius:4px;}}"
            f"QMenu::item:selected{{background:{C['hover']};}}"
        )
        act_detail   = QAction(" Détails arrêt", self)
        act_cancel   = QAction(" Annuler cet arrêt", self)
        act_reassign = QAction("↔ Réaffecter à un autre véhicule", self)
        act_lock     = QAction(f"{' Déverrouiller' if locked else ' Verrouiller'} tournée", self)

        act_detail.triggered.connect(lambda: self._show_block_detail(v_idx, b_idx))
        act_cancel.triggered.connect(lambda: self._cancel_block(v_idx, b_idx))
        act_reassign.triggered.connect(lambda: self._reassign_block(v_idx, b_idx))
        act_lock.triggered.connect(lambda: self._toggle_lock(v_idx))

        menu.addAction(act_detail)
        menu.addSeparator()
        menu.addAction(act_cancel)
        menu.addAction(act_reassign)
        menu.addSeparator()
        menu.addAction(act_lock)
        menu.exec(pos)

    def _show_block_detail(self, v_idx: int, b_idx: int):
        block = self._vehicles[v_idx]["blocks"][b_idx]
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Détails du bloc")
        dlg.setText(
            f"Type : {block.get('type', '')}\n"
            f"Label : {block.get('label', '')}\n"
            f"Début : {GANTT_START_H:02d}:00 + {int(block['start_min'])} min\n"
            f"Durée : {int(block['dur_min'])} min\n"
            f"Client : {block.get('client', '—')}"
        )
        dlg.exec()

    def _cancel_block(self, v_idx: int, b_idx: int):
        block = self._vehicles[v_idx]["blocks"][b_idx]
        if not ConfirmDialog.ask(self, "Annuler arrêt",
                                 f"Supprimer l'arrêt « {block.get('label', '')} » ", "danger"):
            return
        self._push_undo(v_idx, b_idx, block["start_min"])
        self._vehicles[v_idx]["blocks"].pop(b_idx)
        self.update()
        log_action("GANTT_BLOCK_CANCELLED", f"Véhicule {v_idx} bloc {b_idx} annulé")
        self.block_cancelled.emit(v_idx, b_idx)

    def _reassign_block(self, v_idx: int, b_idx: int):
        if len(self._vehicles) < 2:
            show_toast(self.window(), "Un seul véhicule disponible.", "info"); return
        block = self._vehicles[v_idx]["blocks"].pop(b_idx)
        targets = [i for i in range(len(self._vehicles)) if i != v_idx]
        target  = targets[0]
        self._vehicles[target]["blocks"].append(block)
        self.update()
        log_action("GANTT_BLOCK_REASSIGNED", f"Bloc réaffecté → véhicule {target}")

    def _toggle_lock(self, v_idx: int):
        veh = self._vehicles[v_idx]
        veh["locked"] = not veh.get("locked", False)
        self.block_locked.emit(v_idx, veh["locked"])
        self.update()

    # ── Undo ────────────────────────────────────────────────────────────

    def _push_undo(self, v_idx: int, b_idx: int, orig_start: float):
        self._undo_stack.append((v_idx, b_idx, orig_start))

    def _undo(self):
        if not self._undo_stack:
            show_toast(self.window(), "Rien à annuler.", "info"); return
        v_idx, b_idx, orig_start = self._undo_stack.pop()
        if v_idx < len(self._vehicles) and b_idx < len(self._vehicles[v_idx]["blocks"]):
            self._vehicles[v_idx]["blocks"][b_idx]["start_min"] = orig_start
            self.update()
            show_toast(self.window(), "Annulation effectuée (Ctrl+Z).", "info")

    # ── Hit-test ────────────────────────────────────────────────────────

    def _block_at(self, pos: QPoint):
        for v_idx, veh in enumerate(self._vehicles):
            for b_idx, block in enumerate(veh.get("blocks", [])):
                if self._block_rect(v_idx, block).contains(pos):
                    return (v_idx, b_idx)
        return None

    def sizeHint(self) -> QSize:
        rows = max(len(self._vehicles), 3)
        return QSize(800, HDR_H + rows * ROW_H + 20)


# ═══════════════════════════════════════════════════════════════════════════════
# TRACKING WIDGET PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class TrackingWidget(QWidget):

    route_updated      = pyqtSignal(int, str)   # vehicle_id, stops_json
    center_on_vehicle  = pyqtSignal(int)         # vehicle_id
    reoptimization_done= pyqtSignal(dict)        # result_dict

    def __init__(self, main_window):
        super().__init__()
        self.main_window        = main_window
        self._routes_data: list = []    # résultat injecté par OptimizationWidget
        self._gantt_vehicles: list = []
        self._sim_running    = False
        self._sim_speed      = 1        # ×1, ×2, ×5
        self._sim_min        = 0.0      # minutes simulées depuis 06:00
        self._sim_timer      = QTimer(self)
        self._sim_timer.setInterval(1000)
        self._sim_timer.timeout.connect(self._sim_tick)
        self._traffic_factor = 1.0
        self._last_result: dict = {}
        self._week_plan_data: list = []   # données semaine injectées depuis OptimizationWidget
        self._setup_ui()
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(5000)
        self._live_timer.timeout.connect(self._update_table_live)
        self._live_timer.start()
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(60_000)
        self._sync_timer.timeout.connect(self._pull_web_confirmations)
        self._sync_timer.start()

    # ══════════════════════════════════════════════════════════════════════
    # CONSTRUCTION UI
    # ══════════════════════════════════════════════════════════════════════

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sim_bar())
        root.addWidget(self._build_week_bar())   # barre sélecteur jours — masquée par défaut
        root.addWidget(self._build_weather_bar())
        root.addWidget(self._build_kpi_bar())
        root.addWidget(self._build_splitter(), 1)

    # ── Barre simulation ────────────────────────────────────────────────

    def _build_sim_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            f"QFrame{{background:{C['panel']};border-bottom:1px solid {C['border']};}}"
        )
        lo = QHBoxLayout(bar); lo.setContentsMargins(10, 4, 10, 4); lo.setSpacing(6)

        self._btn_play  = _sim_btn("Play",  "Démarrer simulation", 48)
        self._btn_pause = _sim_btn("Pause", "Pause / Reprendre",   52)
        self._btn_stop  = _sim_btn("Stop",  "Arrêter",             48)
        self._btn_x2    = _sim_btn("×2",    "Vitesse ×2",          36)
        self._btn_x5    = _sim_btn("×5",    "Vitesse ×5",          36)

        self._btn_play.clicked.connect(self._sim_play)
        self._btn_pause.clicked.connect(self._sim_pause)
        self._btn_stop.clicked.connect(self._sim_stop)
        self._btn_x2.clicked.connect(lambda: self._set_speed(2))
        self._btn_x5.clicked.connect(lambda: self._set_speed(5))

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{C['border']};")

        self._sim_slider = QSlider(Qt.Orientation.Horizontal)
        self._sim_slider.setRange(0, GANTT_MINS)
        self._sim_slider.setValue(0)
        self._sim_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{background:{C['input']};height:4px;border-radius:2px;}}"
            f"QSlider::handle:horizontal{{background:{C['accent']};width:14px;height:14px;"
            "margin:-5px 0;border-radius:7px;}}"
            f"QSlider::sub-page:horizontal{{background:{C['accent']};border-radius:2px;}}"
        )
        self._sim_slider.sliderMoved.connect(self._slider_moved)

        self._sim_time_lbl = QLabel("06:00")
        self._sim_time_lbl.setFixedWidth(50)
        self._sim_time_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:14px;font-weight:700;"
            "font-family:Consolas,monospace;background:transparent;"
        )
        self._speed_lbl = QLabel("×1")
        self._speed_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;background:transparent;min-width:24px;"
        )

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color:{C['border']};")

        self._btn_report = QPushButton("📄 Rapport")
        self._btn_report.setFixedHeight(30)
        self._btn_report.setToolTip(
            "Génère un rapport PDF :\n"
            "• Vue semaine : rapport détaillé des 5 jours\n"
            "• Vue jour : rapport de la tournée en cours"
        )
        self._btn_report.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['accent']};"
            f"border:1px solid {C['border']};border-radius:5px;"
            "font-size:11px;font-weight:600;padding:0 10px;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
        )
        self._btn_report.clicked.connect(self._generate_tracking_report)

        for w in [self._btn_play, self._btn_pause, self._btn_stop,
                  sep, self._btn_x2, self._btn_x5, self._speed_lbl]:
            lo.addWidget(w)
        lo.addWidget(self._sim_slider, 1)
        lo.addWidget(self._sim_time_lbl)
        lo.addWidget(sep2)
        lo.addWidget(self._btn_report)
        return bar

    # ── Barre sélecteur semaine ──────────────────────────────────────────

    def _build_week_bar(self) -> QFrame:
        """Barre de navigation entre les jours d'une planification semaine."""
        self._week_bar = QFrame()
        self._week_bar.setVisible(False)
        self._week_bar.setFixedHeight(42)
        self._week_bar.setStyleSheet(
            f"QFrame{{background:#0D2238;border-bottom:2px solid {C['accent']};}}"
        )
        lo = QHBoxLayout(self._week_bar)
        lo.setContentsMargins(12, 4, 12, 4)
        lo.setSpacing(8)

        icon_lbl = QLabel("📅")
        icon_lbl.setStyleSheet("background:transparent;font-size:14px;")
        lo.addWidget(icon_lbl)

        title = QLabel("Planification semaine :")
        title.setStyleSheet(
            f"color:{C['accent']};font-weight:700;font-size:12px;background:transparent;"
        )
        lo.addWidget(title)

        self._week_day_cb = QComboBox()
        self._week_day_cb.setMinimumWidth(280)
        self._week_day_cb.setFixedHeight(28)
        self._week_day_cb.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['accent']};border-radius:4px;"
            "padding:2px 8px;font-size:12px;font-weight:600;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
            f"border:1px solid {C['border']};}}"
        )
        self._week_day_cb.currentIndexChanged.connect(self._on_week_day_changed)
        lo.addWidget(self._week_day_cb)

        btn_style = (
            f"QPushButton{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;"
            "font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
            f"QPushButton:disabled{{color:{C['text2']};background:{C['bg']};}}"
        )
        self._btn_prev_day = QPushButton("◀")
        self._btn_prev_day.setFixedSize(28, 28)
        self._btn_prev_day.setToolTip("Jour précédent")
        self._btn_prev_day.setStyleSheet(btn_style)
        self._btn_prev_day.clicked.connect(
            lambda: self._week_day_cb.setCurrentIndex(
                max(0, self._week_day_cb.currentIndex() - 1)
            )
        )
        lo.addWidget(self._btn_prev_day)

        self._btn_next_day = QPushButton("▶")
        self._btn_next_day.setFixedSize(28, 28)
        self._btn_next_day.setToolTip("Jour suivant")
        self._btn_next_day.setStyleSheet(btn_style)
        self._btn_next_day.clicked.connect(
            lambda: self._week_day_cb.setCurrentIndex(
                min(self._week_day_cb.count() - 1,
                    self._week_day_cb.currentIndex() + 1)
            )
        )
        lo.addWidget(self._btn_next_day)

        lo.addSpacing(12)

        self._week_info_lbl = QLabel("")
        self._week_info_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;background:transparent;"
        )
        lo.addWidget(self._week_info_lbl)

        lo.addStretch()

        close_btn = QPushButton("✕ Quitter vue semaine")
        close_btn.setFixedHeight(26)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:4px;font-size:11px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{C['danger']};border-color:{C['danger']};}}"
        )
        close_btn.clicked.connect(self._clear_week_plan)
        lo.addWidget(close_btn)

        return self._week_bar

    # ── Méthodes planification semaine ────────────────────────────────────

    def set_week_plan(self, pending_week_plan: list):
        """Charge les données de planification semaine et affiche le sélecteur de jour."""
        self._week_plan_data = [
            r for r in pending_week_plan
            if r.get("algo_results_full") and r.get("best_algo")
        ]

        self._week_day_cb.blockSignals(True)
        self._week_day_cb.clear()

        day_names_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        for day_result in self._week_plan_data:
            day_str   = day_result.get("date", "?")
            best_algo = day_result.get("best_algo", "")
            n_served  = day_result.get("n_served", 0)
            n_orders  = day_result.get("n_orders", 0)
            try:
                d = datetime.strptime(day_str, "%Y-%m-%d").date()
                label = (
                    f"{day_names_fr[d.weekday()]} {d.strftime('%d/%m/%Y')} "
                    f"— {n_served}/{n_orders} cde — {best_algo.upper()}"
                )
            except Exception:
                label = day_str
            self._week_day_cb.addItem(label)

        self._week_day_cb.blockSignals(False)
        self._week_bar.setVisible(bool(self._week_plan_data))

        if self._week_plan_data:
            self._on_week_day_changed(0)

    def _on_week_day_changed(self, index: int):
        """Charge le résultat du jour sélectionné dans le Gantt."""
        if not self._week_plan_data or index < 0 or index >= len(self._week_plan_data):
            return

        day_result = self._week_plan_data[index]
        best_algo  = day_result.get("best_algo", "")
        full       = day_result.get("algo_results_full", {})
        result     = full.get(best_algo, {})

        self._btn_prev_day.setEnabled(index > 0)
        self._btn_next_day.setEnabled(index < len(self._week_plan_data) - 1)

        n_srv = day_result.get("n_served", 0)
        n_ord = day_result.get("n_orders", 0)
        km    = result.get("total_distance_km", 0)
        self._week_info_lbl.setText(
            f"{n_srv}/{n_ord} commandes · {km:.1f} km"
        )

        if result:
            self.set_routes(result)

    def _clear_week_plan(self):
        """Masque la barre semaine et revient en mode tournée simple."""
        self._week_plan_data = []
        self._week_day_cb.blockSignals(True)
        self._week_day_cb.clear()
        self._week_day_cb.blockSignals(False)
        self._week_bar.setVisible(False)

    # ── Barre météo ──────────────────────────────────────────────────────

    def _build_weather_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(38)
        bar.setStyleSheet(
            f"QFrame{{background:{C['bg']};border-bottom:1px solid {C['border']};}}"
        )
        lo = QHBoxLayout(bar); lo.setContentsMargins(12, 4, 12, 4); lo.setSpacing(8)

        lbl = QLabel("Météo :")
        lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        self._weather_cb = QComboBox()
        self._weather_cb.setFixedWidth(170)
        self._weather_cb.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:2px 6px;font-size:11px;}}"
            f"QComboBox::drop-down{{border:none;}}"
        )
        for label, tf in [
            (" Ensoleillé ×1.0", 1.0), (" Pluie légère ×1.1", 1.1),
            (" Pluie forte ×1.25", 1.25), (" Neige ×1.6", 1.6),
        ]:
            self._weather_cb.addItem(label, tf)
        self._weather_cb.currentIndexChanged.connect(self._on_weather_change)

        owm_btn = QPushButton(" Météo réelle")
        owm_btn.setFixedHeight(26)
        owm_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['accent']};"
            f"border:1px solid {C['border']};border-radius:4px;font-size:11px;padding:0 8px;}}"
            f"QPushButton:hover{{background:{C['hover']};}}"
        )
        owm_btn.setEnabled(HAS_REQUESTS)
        owm_btn.setToolTip("Nécessite une clé OpenWeatherMap" if not HAS_REQUESTS else "Météo en temps réel")
        owm_btn.clicked.connect(self._fetch_owm_weather)

        lbl_tf = QLabel("Trafic :")
        lbl_tf.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
        self._traffic_lbl = QLabel("×1.00")
        self._traffic_lbl.setStyleSheet(f"color:{C['warning']};font-size:11px;font-weight:700;background:transparent;")

        auto_btn = QPushButton("Auto")
        auto_btn.setFixedHeight(24)
        auto_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:3px;font-size:10px;padding:0 6px;}}"
        )
        auto_btn.clicked.connect(self._auto_traffic)

        lo.addWidget(lbl); lo.addWidget(self._weather_cb)
        lo.addWidget(owm_btn)
        lo.addSpacing(16)
        lo.addWidget(lbl_tf); lo.addWidget(self._traffic_lbl); lo.addWidget(auto_btn)
        lo.addStretch()

        self._weather_status = QLabel("")
        self._weather_status.setStyleSheet(f"color:{C['text2']};font-size:10px;background:transparent;")
        lo.addWidget(self._weather_status)
        lo.addSpacing(4)
        _hb = QPushButton()
        _hb.setFixedSize(28, 28)
        _hb.setToolTip("Aide — Suivi en temps réel")
        _hb.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_action_button(_hb, "help-circle", "#7FA8C0", C["bg"], C["panel"], 16)
        _hb.clicked.connect(lambda: show_help(self, "tracking"))
        lo.addWidget(_hb)
        return bar

    # ── KPI Bar ──────────────────────────────────────────────────────────

    def _build_kpi_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(118)
        bar.setStyleSheet(f"QFrame{{background:{C['panel']};border-bottom:1px solid {C['border']};}}")
        lo = QHBoxLayout(bar); lo.setContentsMargins(12, 6, 12, 6); lo.setSpacing(4)

        self._kpi_active   = KPICard("Véhicules actifs",  "—", icon="")
        self._kpi_done     = KPICard("Livraisons",        "—", icon="")
        self._kpi_late     = KPICard("En retard",         "—", icon="")
        self._kpi_km       = KPICard("Km parcourus",      "—", icon="")
        self._kpi_co2      = KPICard("CO₂ (kg)",          "—", icon="")

        for k in [self._kpi_active, self._kpi_done, self._kpi_late, self._kpi_km, self._kpi_co2]:
            lo.addWidget(k)
        return bar

    # ── Splitter 70/30 ────────────────────────────────────────────────────

    def _build_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{C['border']};width:2px;}}")

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([700, 300])
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        return splitter

    # ── Panneau gauche — QTabWidget ──────────────────────────────────────

    def _build_left_panel(self) -> QTabWidget:
        self._left_tabs = QTabWidget()
        self._left_tabs.setStyleSheet(
            f"QTabWidget::pane{{background:{C['bg']};border:none;}}"
            f"QTabBar::tab{{background:{C['panel']};color:{C['text2']};padding:8px 14px;"
            "border-top-left-radius:6px;border-top-right-radius:6px;margin-right:2px;font-size:12px;}"
            f"QTabBar::tab:selected{{background:{C['accent']};color:{C['bg']};font-weight:700;}}"
            f"QTabBar::tab:hover{{background:{C['hover']};color:{C['text']};}}"
        )
        self._left_tabs.addTab(self._build_gantt_tab(),  "  Gantt")
        self._left_tabs.addTab(self._build_table_tab(),  "  Tableau")
        return self._left_tabs

    # ── Gantt tab ─────────────────────────────────────────────────────────

    def _build_gantt_tab(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(0, 4, 0, 0); lo.setSpacing(4)

        # Barre d'outils Gantt
        toolbar = QHBoxLayout(); toolbar.setContentsMargins(8, 0, 8, 0); toolbar.setSpacing(6)
        lock_btn = QPushButton(" Verrouiller sélection")
        unlock_btn = QPushButton(" Déverrouiller tout")
        zoom_in  = QPushButton("+")
        zoom_in.setToolTip("Zoom avant sur le Gantt")
        zoom_out = QPushButton("-")
        zoom_out.setToolTip("Zoom arrière sur le Gantt")
        zoom_reset = QPushButton("Reset Zoom")
        for btn in [lock_btn, unlock_btn, zoom_in, zoom_out, zoom_reset]:
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                f"QPushButton{{background:{C['input']};color:{C['text']};"
                f"border:1px solid {C['border']};border-radius:4px;font-size:11px;padding:0 8px;}}"
                f"QPushButton:hover{{background:{C['hover']};border-color:{C['accent']};}}"
            )
            toolbar.addWidget(btn)
        toolbar.addStretch()
        hint = QLabel("Ctrl+Z annuler | Molette zoom | Drag déplacer | Clic droit menu")
        hint.setStyleSheet(f"color:{C['text2']};font-size:10px;background:transparent;")
        toolbar.addWidget(hint)
        lo.addLayout(toolbar)

        zoom_in.clicked.connect(lambda: self._gantt_zoom(1.2))
        zoom_out.clicked.connect(lambda: self._gantt_zoom(0.83))
        zoom_reset.clicked.connect(lambda: self._gantt_zoom_reset())
        lock_btn.clicked.connect(self._lock_all)
        unlock_btn.clicked.connect(self._unlock_all)

        # GanttWidget dans un QScrollArea vertical
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea{{background:{C['bg']};border:none;}}")

        self._gantt = GanttWidget()
        self._gantt.block_moved.connect(self._on_block_moved)
        self._gantt.block_locked.connect(self._on_block_locked)
        self._gantt.block_cancelled.connect(self._on_block_cancelled)
        scroll.setWidget(self._gantt)
        lo.addWidget(scroll, 1)
        return w

    # ── Table tab ─────────────────────────────────────────────────────────

    def _build_table_tab(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(8, 6, 8, 6); lo.setSpacing(6)

        sub = QLabel("Double-clic sur un véhicule → centrer sur la carte | Mise à jour toutes les secondes")
        sub.setStyleSheet(f"color:{C['text2']};font-size:10px;background:transparent;")
        lo.addWidget(sub)

        self._table = QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            "Véhicule", "Chauffeur", "Statut", "Progression",
            "Prochain arrêt", "Arrivée est.", "Retard (min)", "Charge kg", "CO₂ kg",
        ])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed);  self._table.setColumnWidth(0, 110)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed);  self._table.setColumnWidth(1, 100)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed);  self._table.setColumnWidth(2, 90)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for col in [3, 5, 6, 7, 8]:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(36)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_table_double_click)
        self._table.setStyleSheet(
            f"QTableWidget{{background:{C['bg']};color:{C['text']};"
            f"gridline-color:{C['border']};border:none;alternate-background-color:#0F2035;}}"
            f"QTableWidget::item:selected{{background:{C['hover']};color:{C['accent']};}}"
            f"QHeaderView::section{{background:{C['panel']};color:{C['text2']};"
            f"border:1px solid {C['border']};padding:4px 6px;font-size:11px;font-weight:600;}}"
        )
        lo.addWidget(self._table, 1)
        return w

    # ── Panneau droit — Incidents ─────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        w = QWidget(); lo = QVBoxLayout(w); lo.setContentsMargins(8, 8, 8, 8); lo.setSpacing(8)
        w.setStyleSheet(f"QWidget{{background:{C['panel']};border-left:1px solid {C['border']};}}")

        # Titre
        t = QLabel(" Incidents & Notifications")
        t.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:700;background:transparent;")
        lo.addWidget(t)

        # Bouton signaler
        sig_btn = QPushButton("+ Signaler un incident")
        sig_btn.setObjectName("primaryBtn"); sig_btn.setFixedHeight(32)
        sig_btn.clicked.connect(self._report_incident)
        lo.addWidget(sig_btn)

        # Bandeau re-optimisation
        self._reoptim_banner = QFrame()
        self._reoptim_banner.setVisible(False)
        self._reoptim_banner.setStyleSheet(
            f"QFrame{{background:rgba(255,183,0,31);border:1px solid {C['warning']};"
            "border-radius:6px;padding:8px;}}"
        )
        relo = QVBoxLayout(self._reoptim_banner); relo.setContentsMargins(6,4,6,4); relo.setSpacing(4)
        self._reoptim_lbl = QLabel("Un arrêt a été annulé. Re-optimiser ")
        self._reoptim_lbl.setWordWrap(True)
        self._reoptim_lbl.setStyleSheet(f"color:{C['warning']};font-size:11px;background:transparent;")
        relo.addWidget(self._reoptim_lbl)
        reoptim_btn = QPushButton(" Re-optimiser maintenant")
        reoptim_btn.setFixedHeight(28)
        reoptim_btn.setStyleSheet(
            f"QPushButton{{background:{C['warning']};color:{C['bg']};border:none;"
            "border-radius:4px;font-weight:700;font-size:11px;padding:0 8px;}}"
        )
        reoptim_btn.clicked.connect(self._reoptimize)
        relo.addWidget(reoptim_btn)
        lo.addWidget(self._reoptim_banner)

        # Scroll notifications
        notif_scroll = QScrollArea()
        notif_scroll.setWidgetResizable(True)
        notif_scroll.setFrameShape(QFrame.Shape.NoFrame)
        notif_scroll.setStyleSheet(f"QScrollArea{{background:{C['panel']};border:none;}}")
        self._notif_container = QWidget()
        self._notif_container.setStyleSheet(f"background:{C['panel']};")
        self._notif_lo = QVBoxLayout(self._notif_container)
        self._notif_lo.setContentsMargins(0, 0, 0, 0)
        self._notif_lo.setSpacing(4)
        self._notif_lo.addStretch()
        notif_scroll.setWidget(self._notif_container)
        lo.addWidget(notif_scroll, 1)

        # Bouton marquer lu
        mark_btn = QPushButton(" Tout marquer lu")
        mark_btn.setFixedHeight(28)
        mark_btn.setStyleSheet(
            f"QPushButton{{background:{C['input']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:4px;font-size:11px;}}"
            f"QPushButton:hover{{background:{C['hover']};}}"
        )
        mark_btn.clicked.connect(self._mark_all_read)
        lo.addWidget(mark_btn)
        return w

    # ══════════════════════════════════════════════════════════════════════
    # DONNÉES : injection depuis OptimizationWidget
    # ══════════════════════════════════════════════════════════════════════

    def retranslate_ui(self, lang: str):
        _tab_labels = {
            "fr": ["  Gantt", "  Tableau"],
            "en": ["  Gantt", "  Table"],
            "ar": ["  غانت", "  الجدول"],
            "es": ["  Gantt", "  Tabla"],
            "de": ["  Gantt", "  Tabelle"],
        }
        labels = _tab_labels.get(lang, _tab_labels["fr"])
        if hasattr(self, "_left_tabs"):
            for i, lbl in enumerate(labels):
                if i < self._left_tabs.count():
                    self._left_tabs.setTabText(i, lbl)

    def refresh_data(self):
        self._load_notifications()
        self._refresh_table_data()

    # ── Rapport PDF ──────────────────────────────────────────────────────

    def _generate_tracking_report(self):
        """Génère un rapport PDF : semaine détaillée ou journée selon le contexte."""
        if not HAS_REPORTLAB:
            show_toast(self.window(), "reportlab non installé — pip install reportlab", "error")
            return

        if self._week_plan_data:
            self._report_week()
        elif self._last_result.get("routes"):
            self._report_single_day()
        else:
            show_toast(self.window(), "Aucune donnée à exporter — lancez une optimisation.", "info")

    def _pdf_styles(self):
        """Retourne (styles, H1, H2, H3, NORM, SMALL) prêts à l'emploi."""
        styles = getSampleStyleSheet()
        H1 = ParagraphStyle("h1", parent=styles["Heading1"],
                            fontSize=15, spaceAfter=6,
                            textColor=rl_colors.HexColor("#00D4FF"))
        H2 = ParagraphStyle("h2", parent=styles["Heading2"],
                            fontSize=12, spaceAfter=4,
                            textColor=rl_colors.HexColor("#E8F4FD"))
        H3 = ParagraphStyle("h3", parent=styles["Heading3"],
                            fontSize=10, spaceAfter=2,
                            textColor=rl_colors.HexColor("#8899AA"))
        NORM  = ParagraphStyle("norm",  parent=styles["Normal"],
                               fontSize=9, textColor=rl_colors.HexColor("#E8F4FD"))
        SMALL = ParagraphStyle("small", parent=styles["Normal"],
                               fontSize=8, textColor=rl_colors.HexColor("#8899AA"))
        return styles, H1, H2, H3, NORM, SMALL

    def _pdf_stops_table(self, routes: list) -> "Table | None":
        """Construit le tableau reportlab des arrêts depuis une liste de routes."""
        rows = [["Véhicule", "Client", "Arrivée", "Délai\n(min)", "Charge\n(kg)", "Dist.\n(km)", "Type"]]
        for route in routes:
            veh = route.get("vehicle") or {}
            reg = veh.get("registration", "?")
            for stop in route.get("route", []):
                client = stop.get("client") or {}
                arr    = stop.get("arrival_time", 0)
                h, m   = divmod(int(arr), 60)
                delay  = stop.get("delay", 0)
                delay_s = f"{delay:.0f}" if delay > 0 else "—"
                rows.append([
                    reg[:14],
                    (client.get("name", "?"))[:28],
                    f"{h:02d}:{m:02d}",
                    delay_s,
                    f"{client.get('demand_kg', 0):.0f}",
                    f"{stop.get('distance_from_prev', 0):.2f}",
                    stop.get("type", "livraison"),
                ])
        if len(rows) == 1:
            return None
        tbl = Table(rows, repeatRows=1,
                    colWidths=[2.8*rl_cm, 5.2*rl_cm, 1.6*rl_cm,
                               1.4*rl_cm, 1.6*rl_cm, 1.5*rl_cm, 1.8*rl_cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), rl_colors.HexColor("#162840")),
            ("TEXTCOLOR",      (0, 0), (-1, 0), rl_colors.HexColor("#00D4FF")),
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID",           (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#1E3A5F")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [rl_colors.HexColor("#0D1B2A"), rl_colors.HexColor("#0F2035")]),
            ("TEXTCOLOR",      (0, 1), (-1, -1), rl_colors.HexColor("#E8F4FD")),
            ("ALIGN",          (2, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("ROWHEIGHT",      (0, 0), (-1, -1), 14),
        ]))
        return tbl

    def _report_single_day(self):
        """Rapport PDF pour une tournée (optimisation jour unique)."""
        result   = self._last_result
        algo     = result.get("algorithm", "Optimisation")
        date_str = datetime.now().strftime("%d/%m/%Y")
        default  = f"suivi_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le rapport de tournée", default, "PDF (*.pdf)"
        )
        if not path:
            return

        try:
            _, H1, H2, H3, NORM, SMALL = self._pdf_styles()
            doc   = SimpleDocTemplate(path, pagesize=A4,
                                      leftMargin=1.5*rl_cm, rightMargin=1.5*rl_cm,
                                      topMargin=2*rl_cm, bottomMargin=2*rl_cm)
            elems = []

            elems.append(Paragraph(f"Rapport de tournée — {date_str}", H1))
            elems.append(Paragraph(
                f"Algorithme : <b>{algo}</b> · "
                f"Distance totale : <b>{result.get('total_distance_km', 0):.1f} km</b> · "
                f"Commandes : <b>{result.get('clients_served', 0)}</b>",
                NORM
            ))
            elems.append(Spacer(1, 0.3*rl_cm))
            elems.append(HRFlowable(width="100%", thickness=1,
                                    color=rl_colors.HexColor("#00D4FF")))
            elems.append(Spacer(1, 0.3*rl_cm))

            routes = [r for r in result.get("routes", []) if r.get("route")]
            elems.append(Paragraph(f"{len(routes)} véhicule(s) mobilisé(s)", H2))

            # Résumé par véhicule
            veh_rows = [["Véhicule", "Arrêts", "Dist. (km)", "Charge (kg)", "Durée (min)"]]
            for r in routes:
                veh = r.get("vehicle") or {}
                veh_rows.append([
                    veh.get("registration", "?"),
                    str(len(r.get("route", []))),
                    f"{r.get('distance_km', 0):.1f}",
                    f"{r.get('load_kg', 0):.0f}",
                    f"{r.get('duration_min', 0):.0f}",
                ])
            veh_tbl = Table(veh_rows, repeatRows=1,
                            colWidths=[3*rl_cm, 2*rl_cm, 2.5*rl_cm, 2.5*rl_cm, 2.5*rl_cm])
            veh_tbl.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), rl_colors.HexColor("#162840")),
                ("TEXTCOLOR",   (0, 0), (-1, 0), rl_colors.HexColor("#00D4FF")),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1), 9),
                ("GRID",        (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#1E3A5F")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [rl_colors.HexColor("#0D1B2A"), rl_colors.HexColor("#0F2035")]),
                ("TEXTCOLOR",   (0, 1), (-1, -1), rl_colors.HexColor("#E8F4FD")),
                ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ]))
            elems.append(veh_tbl)
            elems.append(Spacer(1, 0.4*rl_cm))

            # Détail tous les arrêts
            elems.append(Paragraph("Détail des arrêts", H2))
            tbl = self._pdf_stops_table(routes)
            if tbl:
                elems.append(tbl)
            else:
                elems.append(Paragraph("(aucun arrêt)", NORM))

            elems.append(Spacer(1, 0.4*rl_cm))
            elems.append(HRFlowable(width="100%", thickness=0.5,
                                    color=rl_colors.HexColor("#1E3A5F")))
            elems.append(Paragraph(
                f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} · CityPulse Logistics",
                SMALL
            ))

            doc.build(elems)
            show_toast(self.window(), f"Rapport généré ({len(routes)} véhicule(s)).", "success")
            log_action("EXPORT", f"Rapport suivi journée → {path}")

        except Exception as exc:
            logger.exception("Erreur rapport PDF journée")
            show_toast(self.window(), f"Erreur PDF : {exc}", "error")

    def _report_week(self):
        """Rapport PDF détaillé pour la planification semaine (tous les jours)."""
        default = f"rapport_semaine_{datetime.now().strftime('%Y%m%d')}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le rapport semaine", default, "PDF (*.pdf)"
        )
        if not path:
            return

        try:
            _, H1, H2, H3, NORM, SMALL = self._pdf_styles()
            doc   = SimpleDocTemplate(path, pagesize=A4,
                                      leftMargin=1.5*rl_cm, rightMargin=1.5*rl_cm,
                                      topMargin=2*rl_cm, bottomMargin=2*rl_cm)
            elems = []
            day_names_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

            # ── Page de garde ──────────────────────────────────────────────
            elems.append(Paragraph("Rapport de planification — Semaine", H1))
            total_days  = len(self._week_plan_data)
            total_srv   = sum(r.get("n_served", 0) for r in self._week_plan_data)
            total_ord   = sum(r.get("n_orders", 0) for r in self._week_plan_data)
            total_km    = sum(
                r.get("algo_results_full", {}).get(r.get("best_algo", ""), {})
                 .get("total_distance_km", 0)
                for r in self._week_plan_data
            )
            if self._week_plan_data:
                first_day = self._week_plan_data[0].get("date", "?")
                last_day  = self._week_plan_data[-1].get("date", "?")
                try:
                    d1 = datetime.strptime(first_day, "%Y-%m-%d").strftime("%d/%m/%Y")
                    d2 = datetime.strptime(last_day,  "%Y-%m-%d").strftime("%d/%m/%Y")
                    period = f"{d1} → {d2}"
                except Exception:
                    period = f"{first_day} → {last_day}"
            else:
                period = "—"

            elems.append(Paragraph(
                f"Période : <b>{period}</b> · {total_days} jour(s) · "
                f"<b>{total_srv}/{total_ord}</b> commandes · "
                f"<b>{total_km:.1f} km</b> total",
                NORM
            ))
            elems.append(Spacer(1, 0.3*rl_cm))
            elems.append(HRFlowable(width="100%", thickness=2,
                                    color=rl_colors.HexColor("#00D4FF")))
            elems.append(Spacer(1, 0.4*rl_cm))

            # ── Récapitulatif semaine ──────────────────────────────────────
            elems.append(Paragraph("Récapitulatif par jour", H2))
            recap_rows = [["Jour", "Date", "Algo", "Cdes planif.", "Distance (km)",
                           "Véhicules", "Taux srv %"]]
            for dr in self._week_plan_data:
                best   = dr.get("best_algo", "")
                res    = dr.get("algo_results_full", {}).get(best, {})
                d_str  = dr.get("date", "?")
                try:
                    d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
                    jour  = day_names_fr[d_obj.weekday()]
                    d_fmt = d_obj.strftime("%d/%m")
                except Exception:
                    jour, d_fmt = "?", d_str
                n_srv   = dr.get("n_served", 0)
                n_ord   = dr.get("n_orders", 0)
                km      = res.get("total_distance_km", 0)
                n_veh   = len([r for r in res.get("routes", []) if r.get("route")])
                taux    = f"{n_srv/n_ord*100:.0f}%" if n_ord > 0 else "—"
                recap_rows.append([jour, d_fmt, best.upper(),
                                   f"{n_srv}/{n_ord}", f"{km:.1f}",
                                   str(n_veh), taux])

            recap_tbl = Table(recap_rows, repeatRows=1,
                              colWidths=[1.2*rl_cm, 1.6*rl_cm, 2.4*rl_cm,
                                         2.2*rl_cm, 2.6*rl_cm, 2*rl_cm, 1.8*rl_cm])
            recap_tbl.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1, 0), rl_colors.HexColor("#162840")),
                ("TEXTCOLOR",      (0, 0), (-1, 0), rl_colors.HexColor("#00D4FF")),
                ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",       (0, 0), (-1, -1), 8),
                ("GRID",           (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#1E3A5F")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [rl_colors.HexColor("#0D1B2A"), rl_colors.HexColor("#0F2035")]),
                ("TEXTCOLOR",      (0, 1), (-1, -1), rl_colors.HexColor("#E8F4FD")),
                ("ALIGN",          (2, 0), (-1, -1), "CENTER"),
            ]))
            elems.append(recap_tbl)
            elems.append(Spacer(1, 0.5*rl_cm))

            # ── Détail jour par jour ───────────────────────────────────────
            for dr in self._week_plan_data:
                best  = dr.get("best_algo", "")
                res   = dr.get("algo_results_full", {}).get(best, {})
                d_str = dr.get("date", "?")
                n_srv = dr.get("n_served", 0)
                n_ord = dr.get("n_orders", 0)
                km    = res.get("total_distance_km", 0)

                try:
                    d_obj  = datetime.strptime(d_str, "%Y-%m-%d").date()
                    d_long = (f"{day_names_fr[d_obj.weekday()]} "
                              f"{d_obj.strftime('%d/%m/%Y')}")
                except Exception:
                    d_long = d_str

                elems.append(HRFlowable(width="100%", thickness=1,
                                        color=rl_colors.HexColor("#1E3A5F")))
                elems.append(Spacer(1, 0.2*rl_cm))
                elems.append(Paragraph(
                    f"📅 {d_long}  ·  {best.upper()}  ·  "
                    f"{n_srv}/{n_ord} commandes  ·  {km:.1f} km",
                    H2
                ))

                routes = [r for r in res.get("routes", []) if r.get("route")]
                if not routes:
                    elems.append(Paragraph("(aucune tournée ce jour)", NORM))
                    elems.append(Spacer(1, 0.3*rl_cm))
                    continue

                # Résumé véhicules du jour
                for route in routes:
                    veh    = route.get("vehicle") or {}
                    n_stop = len(route.get("route", []))
                    ld     = route.get("load_kg", 0)
                    dur    = route.get("duration_min", 0)
                    d_km   = route.get("distance_km", 0)
                    elems.append(Paragraph(
                        f"  🚛 <b>{veh.get('registration','?')}</b> "
                        f"— {n_stop} arrêt(s) · {d_km:.1f} km · "
                        f"{ld:.0f} kg · {dur:.0f} min",
                        H3
                    ))

                elems.append(Spacer(1, 0.2*rl_cm))

                # Tableau détaillé des arrêts
                tbl = self._pdf_stops_table(routes)
                if tbl:
                    elems.append(tbl)
                elems.append(Spacer(1, 0.4*rl_cm))

            # ── Pied de page ───────────────────────────────────────────────
            elems.append(HRFlowable(width="100%", thickness=0.5,
                                    color=rl_colors.HexColor("#1E3A5F")))
            elems.append(Paragraph(
                f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} · CityPulse Logistics",
                SMALL
            ))

            doc.build(elems)
            show_toast(
                self.window(),
                f"Rapport semaine généré ({total_days} jours · {total_srv} commandes).",
                "success"
            )
            log_action("EXPORT", f"Rapport suivi semaine → {path}")

        except Exception as exc:
            logger.exception("Erreur rapport PDF semaine")
            show_toast(self.window(), f"Erreur PDF : {exc}", "error")

    def set_routes(self, result: dict):
        """Appelé par OptimizationWidget.routes_ready signal."""
        self._last_result = result
        self._routes_data = result.get("routes", [])
        self._build_gantt_data()
        self._refresh_table_data()
        self._update_kpis()

    def _build_gantt_data(self):
        colors_cycle = [
            "#1A6CF6", "#00CC66", "#FF8C00", "#8B5CF6",
            "#00D4FF", "#FF4757", "#FFB800", "#00FF88",
        ]
        vehicles = []
        for i, route in enumerate(self._routes_data):
            veh   = route.get("vehicle", {})
            stops = [s for s in route.get("route", []) if s.get("type") in ("delivery", "reload")]
            blocks = []
            cursor = 0.0   # minutes since 06:00

            for stop in stops:
                # Bloc trajet
                d_km   = stop.get("distance_from_prev", 0)
                speed  = float(veh.get("speed_urban_kmh") or 40)
                travel_min = (d_km / speed * 60) * self._traffic_factor if d_km else 5
                if travel_min > 0:
                    blocks.append({
                        "type": "travel", "start_min": cursor,
                        "dur_min": travel_min, "label": "Trajet",
                        "client": "",
                    })
                    cursor += travel_min

                # Bloc visite ou rechargement
                if stop.get("type") == "reload":
                    blocks.append({
                        "type": "reload", "start_min": cursor,
                        "dur_min": 15, "label": "Rechargement",
                        "client": "",
                    })
                    cursor += 15
                else:
                    c       = stop.get("client") or {}
                    svc_min = float(c.get("service_time", 10))
                    arr_min = float(stop.get("arrival_time", cursor))
                    due_min = float(c.get("due_time", 1440))
                    is_late = arr_min > due_min

                    blocks.append({
                        "type": "delay" if is_late else "visit",
                        "start_min": cursor,
                        "dur_min": svc_min,
                        "label": c.get("name", "Client")[:14],
                        "client": c.get("name", ""),
                        "client_idx": stop.get("client_index"),
                    })
                    cursor += svc_min

                # Pause RSE si > 270 min depuis 06:00 et aucune pause encore
                if cursor > 270 and not any(b["type"] == "pause" for b in blocks):
                    blocks.append({
                        "type": "pause", "start_min": cursor,
                        "dur_min": 45, "label": "Pause RSE",
                        "client": "",
                    })
                    cursor += 45

            reg = veh.get("registration", f"V{i+1}")
            vehicles.append({
                "label":  reg,
                "color":  colors_cycle[i % len(colors_cycle)],
                "blocks": blocks,
                "locked": route.get("is_locked", False),
                "vehicle_id": veh.get("id", i),
            })

        self._gantt_vehicles = vehicles
        self._gantt.set_data(vehicles)

    def _refresh_table_data(self):
        routes = self._routes_data
        self._table.setRowCount(len(routes))
        for r, route in enumerate(routes):
            veh    = route.get("vehicle", {})
            stops  = [s for s in route.get("route", []) if s.get("type") == "delivery"]
            done   = sum(1 for s in stops if s.get("arrival_time", 0) <= self._sim_min + GANTT_START_H * 60)
            total  = len(stops)
            late   = sum(1 for s in stops if s.get("delay", 0) > 0)
            load   = route.get("load_kg", 0)
            dist   = route.get("distance_km", 0)
            co2    = route.get("co2_kg", dist * 0.25)

            # Prochain arrêt
            upcoming = next(
                (s for s in stops if s.get("arrival_time", 0) > self._sim_min + GANTT_START_H * 60),
                None
            )
            next_client = (upcoming.get("client") or {}).get("name", "—") if upcoming else " Terminé"
            next_eta    = f"{int(upcoming.get('arrival_time', 0)//60):02d}:{int(upcoming.get('arrival_time', 0)%60):02d}" if upcoming else "—"

            status_variant = "success" if not late else "warning"
            if total and done == total:
                status_text, status_variant = "Terminé", "success"
            elif done > 0:
                status_text, status_variant = "En cours", "info"
            else:
                status_text, status_variant = "En attente", "default"

            def _it(v, color=None, bold=False):
                it = QTableWidgetItem(str(v or ""))
                it.setFlags(Qt.ItemFlag(it.flags().value & ~Qt.ItemFlag.ItemIsEditable.value))
                if color: it.setForeground(QColor(color))
                if bold:
                    f = it.font(); f.setBold(True); it.setFont(f)
                return it

            reg_it = _it(veh.get("registration", f"V{r+1}"), C["accent"], True)
            reg_it.setData(Qt.ItemDataRole.UserRole, veh.get("id", r))
            self._table.setItem(r, 0, reg_it)
            self._table.setItem(r, 1, _it(veh.get("driver_name") or "—"))

            badge = StatusBadge(status_text, status_variant)
            bw = QWidget(); bl = QHBoxLayout(bw); bl.setContentsMargins(4,2,4,2)
            bl.addWidget(badge); bl.addStretch()
            self._table.setCellWidget(r, 2, bw)

            prog = f"{done}/{total}"
            prog_color = C["success"] if done == total else C["warning"] if late else C["text"]
            self._table.setItem(r, 3, _it(prog, prog_color))
            self._table.setItem(r, 4, _it(next_client))
            self._table.setItem(r, 5, _it(next_eta))

            delay_total = sum(s.get("delay", 0) for s in stops)
            self._table.setItem(r, 6, _it(
                f"{delay_total:.0f}" if delay_total else "—",
                C["danger"] if delay_total > 0 else C["success"]
            ))
            self._table.setItem(r, 7, _it(f"{load:.0f}"))
            self._table.setItem(r, 8, _it(f"{co2:.1f}"))

    def _update_kpis(self):
        routes = self._routes_data
        active = sum(1 for r in routes if any(s.get("type") == "delivery" for s in r.get("route", [])))
        done   = sum(sum(1 for s in r.get("route", []) if s.get("type") == "delivery") for r in routes)
        late   = sum(sum(1 for s in r.get("route", []) if s.get("delay", 0) > 0) for r in routes)
        km     = sum(r.get("distance_km", 0) for r in routes)
        co2    = sum(r.get("co2_kg", r.get("distance_km", 0) * 0.25) for r in routes)

        self._kpi_active.update(str(active))
        self._kpi_done.update(str(done))
        self._kpi_late.update(str(late) if late else "0")
        self._kpi_km.update(f"{km:.0f}")
        self._kpi_co2.update(f"{co2:.1f}")

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION
    # ══════════════════════════════════════════════════════════════════════

    def _sim_play(self):
        if not self._routes_data:
            show_toast(self.window(), "Aucun résultat d'optimisation. Lancez le moteur d'abord.", "info")
            return
        self._sim_running = True
        self._sim_timer.start()
        self._btn_play.setStyleSheet(
            _BTN_S.format(bg=C["success"], fg=C["bg"], br="none", fs="14px", pad="0", hv=C["success"])
        )

    def _sim_pause(self):
        self._sim_running = not self._sim_running
        if self._sim_running:
            self._sim_timer.start()
        else:
            self._sim_timer.stop()

    def _sim_stop(self):
        self._sim_running = False
        self._sim_timer.stop()
        self._sim_min = 0.0
        self._sim_slider.setValue(0)
        self._sim_time_lbl.setText("06:00")
        self._gantt.set_sim_time(0)
        self._btn_play.setStyleSheet(
            _BTN_S.format(bg=C["input"], fg=C["text"], br=f"1px solid {C['border']}", fs="14px", pad="0", hv=C["hover"])
        )

    def _set_speed(self, speed: int):
        self._sim_speed = speed
        self._speed_lbl.setText(f"×{speed}")

    def _slider_moved(self, val: int):
        self._sim_min = float(val)
        self._update_sim_display()

    def _sim_tick(self):
        if not self._sim_running:
            return
        self._sim_min = min(self._sim_min + self._sim_speed, float(GANTT_MINS))
        self._sim_slider.setValue(int(self._sim_min))
        self._update_sim_display()
        if self._sim_min >= GANTT_MINS:
            self._sim_stop()
            show_toast(self.window(), "Simulation terminée — fin de journée.", "info")

    def _update_sim_display(self):
        total_min = int(GANTT_START_H * 60 + self._sim_min)
        hh, mm    = divmod(total_min, 60)
        self._sim_time_lbl.setText(f"{hh:02d}:{mm:02d}")
        self._gantt.set_sim_time(self._sim_min)

    def _update_table_live(self):
        if self._routes_data:
            self._refresh_table_data()

    # ══════════════════════════════════════════════════════════════════════
    # MÉTÉO / TRAFIC
    # ══════════════════════════════════════════════════════════════════════

    def _on_weather_change(self):
        tf = self._weather_cb.currentData() or 1.0
        self._traffic_factor = tf
        self._traffic_lbl.setText(f"×{tf:.2f}")
        if hasattr(self, "_gantt_vehicles"):
            self._build_gantt_data()

    def _auto_traffic(self):
        today    = date.today()
        day_type = classify_day_type(today)
        hour     = datetime.now().hour
        coeff    = get_traffic_coefficient(hour, day_type, "city_center")
        self._traffic_factor = coeff
        self._traffic_lbl.setText(f"×{coeff:.2f}")
        if hasattr(self, "_gantt_vehicles"):
            self._build_gantt_data()

    def _fetch_owm_weather(self):
        try:
            from ..services import weather_service as ws
            conn = get_connection()
            row = conn.execute("SELECT * FROM depots ORDER BY id LIMIT 1").fetchone()
            conn.close()
            lat = float(row["latitude"]) if row else 33.5731
            lon = float(row["longitude"]) if row else -7.5898
            key = ws.resolve_owm_api_key()
            if not key:
                show_toast(self.window(), "Clé OpenWeatherMap absente (keyring).", "info")
                return
            cur = ws.get_current(lat, lon, key)
            if not cur:
                show_toast(self.window(), "Météo indisponible.", "error")
                return
            tf = ws.get_traffic_factor(cur)
            self._traffic_factor = tf
            self._traffic_lbl.setText(f"×{tf:.2f}")
            cond = (cur.get("main") or "").capitalize()
            temp = cur.get("temp", 0)
            self._weather_status.setText(f"OWM: {cond}, {temp}°C")
            if hasattr(self, "_gantt_vehicles"):
                self._build_gantt_data()
            show_toast(self.window(), f"Météo: {cond} {temp}°C → ×{tf:.2f}", "success")
        except Exception as e:
            show_toast(self.window(), f"Erreur météo: {e}", "error")

    # ══════════════════════════════════════════════════════════════════════
    # NOTIFICATIONS / INCIDENTS
    # ══════════════════════════════════════════════════════════════════════

    def _load_notifications(self):
        # Vider
        for i in reversed(range(self._notif_lo.count() - 1)):
            w = self._notif_lo.itemAt(i).widget()
            if w: w.deleteLater()

        try:
            conn  = get_connection()
            notifs = conn.execute("""
                SELECT * FROM notifications WHERE is_read=0
                ORDER BY created_at DESC LIMIT 20
            """).fetchall()
            conn.close()
        except Exception:
            notifs = []

        if not notifs:
            empty = QLabel("Aucune notification non lue ")
            empty.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;padding:8px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._notif_lo.insertWidget(0, empty)
            return

        sev_colors = {"critical": C["danger"], "warning": C["warning"], "info": C["accent"]}
        for notif in notifs:
            card = self._make_notif_card(notif, sev_colors)
            self._notif_lo.insertWidget(self._notif_lo.count() - 1, card)

    def _make_notif_card(self, notif, sev_colors: dict) -> QFrame:
        card = QFrame()
        keys  = notif.keys()
        sev   = notif["severity"] if "severity" in keys else "info"
        col   = sev_colors.get(sev, C["text2"])
        card.setStyleSheet(
            f"QFrame{{background:{C['bg']};border-left:3px solid {col};"
            f"border-radius:4px;padding:4px 6px;margin:1px 0;}}"
        )
        lo = QVBoxLayout(card); lo.setContentsMargins(4, 2, 4, 2); lo.setSpacing(2)
        t_row = QHBoxLayout()
        ntype = notif["type"] if "type" in keys else "INFO"
        t_lbl = QLabel(str(ntype or "INFO").upper())
        t_lbl.setStyleSheet(f"color:{col};font-size:9px;font-weight:700;background:transparent;")
        created = notif["created_at"] if "created_at" in keys else ""
        dt_lbl = QLabel(str(created or "")[:16])
        dt_lbl.setStyleSheet(f"color:{C['text2']};font-size:9px;background:transparent;")
        t_row.addWidget(t_lbl); t_row.addStretch(); t_row.addWidget(dt_lbl)
        lo.addLayout(t_row)
        nmsg  = (notif["message"] if "message" in keys else "") or ""
        msg   = QLabel(str(nmsg))
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color:{C['text']};font-size:10px;background:transparent;")
        lo.addWidget(msg)
        return card

    def _mark_all_read(self):
        try:
            conn = get_connection()
            conn.execute("UPDATE notifications SET is_read=1 WHERE is_read=0")
            conn.commit(); conn.close()
            log_action("NOTIFICATIONS_READ_ALL", "Toutes notifications marquées lues")
        except Exception:
            pass
        self._load_notifications()

    def _report_incident(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Signaler un incident")
        dlg.resize(400, 260)
        dlg.setStyleSheet(
            _dialog_qss()
            + f"QDialog{{background:{C['bg']};color:{C['text']};}}"
        )
        lo = QFormLayout(dlg); lo.setSpacing(8); lo.setContentsMargins(16, 16, 16, 12)
        lo.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        type_cb = QComboBox()
        type_cb.addItems(["Accident", "Panne véhicule", "Embouteillage", "Colis endommagé",
                          "Accès refusé", "Client absent", "Autre"])
        type_cb.setStyleSheet(
            f"QComboBox{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:4px 8px;}}"
        )
        veh_le = QLineEdit(); veh_le.setPlaceholderText("Immatriculation")
        veh_le.setStyleSheet(
            f"QLineEdit{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:4px 8px;}}"
        )
        desc_te = QTextEdit(); desc_te.setMaximumHeight(70)
        desc_te.setPlaceholderText("Description détaillée…")
        desc_te.setStyleSheet(
            f"QTextEdit{{background:{C['input']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:4px;padding:4px;}}"
        )

        lo.addRow("Type :", type_cb)
        lo.addRow("Véhicule :", veh_le)
        lo.addRow("Description :", desc_te)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Annuler"); cancel.setObjectName("secondaryBtn"); cancel.setFixedHeight(30)
        cancel.clicked.connect(dlg.reject)
        send = QPushButton("Envoyer"); send.setObjectName("primaryBtn"); send.setFixedHeight(30)
        def _send():
            title = type_cb.currentText()
            msg   = f"{title} — {veh_le.text()} : {desc_te.toPlainText()}"
            try:
                conn = get_connection()
                conn.execute("""
                    INSERT INTO notifications (type, title, message, severity, is_read)
                    VALUES (?,?,?,?,0)
                """, ("INCIDENT", title, msg[:500], "warning"))
                conn.commit(); conn.close()
                log_action("INCIDENT_REPORTED", msg[:200])
            except Exception:
                pass
            show_toast(self.window(), "Incident signalé.", "success")
            dlg.accept()
            self._load_notifications()
        send.clicked.connect(_send)
        btn_row.addStretch(); btn_row.addWidget(cancel); btn_row.addWidget(send)
        lo.addRow("", btn_row)
        dlg.exec()

    def _reoptimize(self):
        """Retire les arrêts annulés puis émet reoptimization_done pour déclencher un nouveau run."""
        if not self._last_result:
            show_toast(self.window(), "Aucune tournée chargée à re-optimiser.", "error")
            return
        self._reoptim_banner.setVisible(False)
        # Nettoyer les blocs annulés de chaque route
        result = json.loads(json.dumps(self._last_result))  # deep copy
        for route in result.get("routes", []):
            route["stops"] = [
                s for s in route.get("stops", [])
                if not s.get("cancelled", False)
            ]
        show_toast(self.window(), "Re-optimisation envoyée à l'OptimizationWidget…", "info")
        self.reoptimization_done.emit(result)
        log_action("TRACKING_REOPTIMIZE", f"Re-optimisation depuis suivi: {len(result.get('routes', []))} routes")

    def _show_reoptim_banner(self, msg: str = "Un arrêt a été annulé."):
        self._reoptim_lbl.setText(f"{msg} Re-optimiser la tournée ")
        self._reoptim_banner.setVisible(True)

    # ══════════════════════════════════════════════════════════════════════
    # SIGNAUX GANTT → CARTE
    # ══════════════════════════════════════════════════════════════════════

    def _on_block_moved(self, v_idx: int, b_idx: int, new_start_min: int):
        if v_idx < len(self._gantt_vehicles):
            vid = self._gantt_vehicles[v_idx].get("vehicle_id", v_idx)
            stops_json = json.dumps({"block_idx": b_idx, "new_start_min": new_start_min})
            self.route_updated.emit(vid, stops_json)
            self._show_reoptim_banner("Un bloc a été déplacé.")

    def _on_block_cancelled(self, v_idx: int, b_idx: int):
        self._show_reoptim_banner("Un arrêt a été annulé.")

    def _on_block_locked(self, v_idx: int, locked: bool):
        if v_idx < len(self._gantt_vehicles):
            vid = self._gantt_vehicles[v_idx].get("vehicle_id", v_idx)
            stops_json = json.dumps({"locked": locked})
            self.route_updated.emit(vid, stops_json)

    # ══════════════════════════════════════════════════════════════════════
    # GESTION DU CYCLE DE VIE DES TIMERS
    # ══════════════════════════════════════════════════════════════════════

    def hideEvent(self, event):
        """Arrête les timers quand la page est cachée (navigation vers une autre page)."""
        self._live_timer.stop()
        self._sim_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """Redémarre le timer de mise à jour quand la page redevient visible."""
        if not self._live_timer.isActive():
            self._live_timer.start()
        super().showEvent(event)

    def _pull_web_confirmations(self):
        """Timer 60s — récupère les confirmations chauffeur depuis le portail web et met à jour la BDD desktop."""
        try:
            from ..services.django_sync_service import get_django_service
            from ..database.db_manager import get_connection, log_action
            svc = get_django_service()
            if not svc.base_url or not svc.secret_key:
                return
            confirmations = svc.pull_confirmations()
            if not confirmations:
                return
            updated = 0
            conn = get_connection()
            for c in confirmations:
                status_web = c.get("status", "")
                order_ref  = c.get("order_ref", "")
                order_id   = c.get("order_id_ext", "")
                if not (status_web and (order_ref or order_id)):
                    continue
                # Mapper statut web → statut desktop
                STATUS_MAP = {
                    "delivered": "delivered", "completed": "delivered",
                    "livre": "delivered", "livré": "delivered",
                    "failed": "failed", "echec": "failed", "échoué": "failed",
                    "in_progress": "in_progress", "en_cours": "in_progress",
                    "assigned": "assigned", "assigné": "assigned",
                    "pending": "pending",
                }
                desktop_status = STATUS_MAP.get(status_web)
                if not desktop_status:
                    continue
                # Mettre à jour par référence ou par id
                if order_ref:
                    cur = conn.execute(
                        "UPDATE orders SET status=? WHERE reference=? AND status NOT IN ('delivered','failed','cancelled')",
                        (desktop_status, order_ref),
                    )
                    updated += cur.rowcount
                elif order_id and order_id.isdigit():
                    cur = conn.execute(
                        "UPDATE orders SET status=? WHERE id=? AND status NOT IN ('delivered','failed','cancelled')",
                        (desktop_status, int(order_id)),
                    )
                    updated += cur.rowcount
            conn.commit()
            conn.close()
            if updated:
                log_action("WEB_SYNC_CONFIRMATIONS", f"{updated} commande(s) mise(s) à jour depuis le portail web")
                import logging
                logging.getLogger(__name__).info("pull_confirmations: %d commandes mises à jour", updated)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("_pull_web_confirmations échoué", exc_info=True)

    def _on_table_double_click(self, idx):
        row = idx.row()
        it  = self._table.item(row, 0)
        if it:
            vid = it.data(Qt.ItemDataRole.UserRole)
            if vid is not None:
                self.center_on_vehicle.emit(int(vid))

    def _gantt_zoom(self, factor: float):
        self._gantt._zoom = max(0.5, min(8.0, self._gantt._zoom * factor))
        self._gantt.update()

    def _gantt_zoom_reset(self):
        self._gantt._zoom = 1.0; self._gantt._scroll_x = 0
        self._gantt.update()

    def _lock_all(self):
        for i in range(len(self._gantt._vehicles)):
            self._gantt._vehicles[i]["locked"] = True
            self._gantt._locked.add(i)
            self._gantt.block_locked.emit(i, True)
        self._gantt.update()

    def _unlock_all(self):
        for i in range(len(self._gantt._vehicles)):
            self._gantt._vehicles[i]["locked"] = False
        self._gantt._locked.clear()
        for i in range(len(self._gantt._vehicles)):
            self._gantt.block_locked.emit(i, False)
        self._gantt.update()
