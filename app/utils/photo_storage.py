"""
Stockage local des photos utilisateur (véhicules, chauffeurs) sous data/photos/.
Chemins enregistrés en relatif à project_root() (PyInstaller : dossier de l’exe).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..paths import project_root

ALLOWED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


def is_allowed_image_filename(path: str) -> bool:
    return Path(path).suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def ensure_photos_dir() -> str:
    d = os.path.join(project_root(), "data", "photos")
    os.makedirs(d, exist_ok=True)
    return d


def resolve_stored_photo(stored: str | None) -> str | None:
    """Retourne un chemin absolu lisible localement, ou None (URL http / introuvable)."""
    if not stored:
        return None
    s = str(stored).strip()
    if not s:
        return None
    if s.lower().startswith(("http://", "https://")):
        return None
    root = os.path.normpath(project_root())
    if os.path.isabs(s):
        ap = os.path.normpath(s)
        return ap if os.path.isfile(ap) else None
    rel = s.replace("/", os.sep)
    full = os.path.normpath(os.path.join(root, rel))
    if not full.startswith(root):
        return None
    return full if os.path.isfile(full) else None


def save_user_photo(src_path: str, prefix: str, entity_id: int) -> str:
    """
    Copie src_path vers data/photos/{prefix}_{id}_{stem}{ext}.
    Retourne le chemin relatif posix (ex. data/photos/vehicle_3_img.jpg).
    """
    src = os.path.normpath(os.path.abspath(src_path))
    if not os.path.isfile(src):
        raise FileNotFoundError(src_path)
    ext = Path(src).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"Extension non autorisée : {ext}")
    stem = Path(src).stem
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in stem)[:80]
    name = f"{prefix}_{int(entity_id)}_{safe}{ext}"
    dest = os.path.join(ensure_photos_dir(), name)
    shutil.copy2(src, dest)
    return f"data/photos/{name}".replace("\\", "/")


def finalize_stored_path(raw: str | None, prefix: str, entity_id: int) -> str:
    """
    - Vide -> ''
    - URL http(s) -> inchangé
    - Chemin déjà sous data/photos/ et fichier présent -> relatif normalisé
    - Fichier local (absolu ou relatif à la racine projet) -> copie dans data/photos
    - Sinon -> '' (fichier manquant)
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if s.lower().startswith(("http://", "https://")):
        return s
    norm = s.replace("\\", "/")
    if norm.startswith("data/photos/"):
        if resolve_stored_photo(norm):
            return norm
        return ""
    if os.path.isabs(s):
        src = os.path.normpath(s)
    else:
        src = os.path.normpath(os.path.join(project_root(), s.replace("/", os.sep)))
    if os.path.isfile(src):
        return save_user_photo(src, prefix, entity_id)
    return ""
