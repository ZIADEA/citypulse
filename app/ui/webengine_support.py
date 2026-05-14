"""
Probe PyQt6-WebEngine once per process; log the real failure (ImportError, DLL, etc.).

Qt 6 recommends initializing QtWebEngineCore before QtWebEngineWidgets.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

HAS_WEB = False
HAS_WEBCHANNEL = False

QWebEngineView: Any = None
QWebEngineSettings: Any = None
QWebChannel: Any = None

_failure_logged = False


def _log_webengine_failure(exc: BaseException) -> None:
    global _failure_logged
    if _failure_logged:
        return
    _failure_logged = True
    logger.warning(
        "PyQt6-WebEngine indisponible (%s: %s). Installez avec le même interpréteur que "
        'l\'application : "%s" -m pip install PyQt6-WebEngine',
        type(exc).__name__,
        exc,
        sys.executable,
        exc_info=True,
    )


try:
    from PyQt6.QtWebEngineCore import QWebEngineSettings as _QES
    from PyQt6.QtWebEngineWidgets import QWebEngineView as _QEV

    QWebEngineSettings = _QES
    QWebEngineView = _QEV
    HAS_WEB = True
except Exception as e:
    _log_webengine_failure(e)

try:
    from PyQt6.QtWebChannel import QWebChannel as _QC

    QWebChannel = _QC
    HAS_WEBCHANNEL = True
except Exception:
    HAS_WEBCHANNEL = False

WEBENGINE_FALLBACK_LABEL = (
    "PyQt6-WebEngine n'est pas disponible.\n\n"
    "Le détail de l'erreur est dans citypulse.log.\n"
    "Installez le paquet avec le même Python que pour lancer l'application :\n"
    f'  "{sys.executable}" -m pip install PyQt6-WebEngine'
)

WEBENGINE_FALLBACK_SHORT = (
    "Installez PyQt6-WebEngine dans le même environnement que python main.py "
    "(python -m pip install PyQt6-WebEngine). Détail dans citypulse.log."
)
