"""
Build Windows onedir (PyInstaller) + rapport SHA256.

Usage (depuis la racine du dépôt) :
  python build.py

Prérequis : pip install -r requirements.txt (PyInstaller >= 6, Pillow pour l’icône).
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist" / "citypulse"
BUILD = ROOT / "build"
SPEC = ROOT / "citypulse.spec"
REPORT = ROOT / "build_report.txt"
ICON = ROOT / "assets" / "icon.ico"


def _ensure_icon() -> None:
    ICON.parent.mkdir(parents=True, exist_ok=True)
    if ICON.is_file():
        return
    try:
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise SystemExit(
            "Pillow est requis pour générer assets/icon.ico : pip install Pillow"
        ) from e

    size = 256
    img = Image.new("RGBA", (size, size), (13, 27, 42, 255))
    draw = ImageDraw.Draw(img)
    margin = 24
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=40,
        fill=(0, 212, 255, 255),
    )
    img.save(ICON, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def _check_imports() -> list[str]:
    errors: list[str] = []
    checks = [
        ("PyQt6", "PyQt6"),
        ("PyQt6.QtWebEngineWidgets", "PyQt6-WebEngine"),
        ("PyQt6.QtWebEngineCore", "PyQt6-WebEngine"),
        ("ortools", "ortools"),
        ("keyring", "keyring"),
        ("PIL", "Pillow"),
    ]
    for mod, pip_hint in checks:
        try:
            __import__(mod)
        except Exception as e:
            errors.append(f"  • {mod} -> pip install {pip_hint}  ({e})")
    return errors


def _clean() -> None:
    if BUILD.is_dir():
        shutil.rmtree(BUILD, ignore_errors=True)
    if (ROOT / "dist" / "citypulse").is_dir():
        shutil.rmtree(ROOT / "dist" / "citypulse", ignore_errors=True)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    errs = _check_imports()
    if errs:
        print("Imports manquants ou invalides :\n" + "\n".join(errs))
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller manquant : pip install 'pyinstaller>=6.0'")
        return 1

    if not SPEC.is_file():
        print(f"Spec introuvable : {SPEC}")
        return 1
    if not (ROOT / "settings.json").is_file():
        print("Avertissement : settings.json absent — le build continuera sans ce data.")

    _ensure_icon()
    _clean()

    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--clean"]
    print(" ", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT))
    if r.returncode != 0:
        print("PyInstaller a échoué.")
        return r.returncode

    exe = DIST / "citypulse.exe"
    if not exe.is_file():
        print(f"Exe attendu introuvable : {exe}")
        return 2

    digest = _sha256(exe)
    lines = [
        f"Build CityPulse Logistics — {datetime.now(timezone.utc).isoformat()}",
        f"Executable : {exe}",
        f"SHA256     : {digest}",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"Rapport écrit : {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
