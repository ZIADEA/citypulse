"""
Chemins racine projet — compatible exécutable PyInstaller (onedir).

En mode frozen, les données utilisateur (SQLite, settings.json, logs) sont
à côté de l’exécutable, pas dans _internal.
"""
from __future__ import annotations

import os
import sys


def project_root() -> str:
  if getattr(sys, "frozen", False):
    return os.path.dirname(os.path.abspath(sys.executable))
  # app/paths.py → parent = app, parent² = racine du dépôt
  return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def settings_json_path() -> str:
  return os.path.join(project_root(), "settings.json")
