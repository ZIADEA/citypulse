#!/usr/bin/env python3
"""
Vérification d’environnement pour CityPulse Logistics (dev ou post-install).

Contrôles : Python >= 3.11, PyQt6, WebEngine, OR-Tools, SQLite, écriture disque,
keyring, connectivité OSRM public (HTTP).
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _fail(msg: str) -> None:
    print(f"  [!!] {msg}")


def main() -> int:
    print("CityPulse — vérification d’environnement\n")
    failed = False

    if sys.version_info < (3, 11):
        _fail(f"Python >= 3.11 requis (actuel : {sys.version.split()[0]})")
        failed = True
    else:
        _ok(f"Python {sys.version.split()[0]}")

    try:
        importlib.import_module("PyQt6.QtCore")
        _ok("PyQt6")
    except Exception as e:
        _fail(f"PyQt6 : {e}")
        failed = True

    try:
        importlib.import_module("PyQt6.QtWebEngineWidgets")
        _ok("PyQt6 QtWebEngineWidgets")
    except Exception as e:
        _fail(f"PyQt6-WebEngine : {e}")
        failed = True

    try:
        importlib.import_module("ortools")
        _ok("OR-Tools (ortools)")
    except Exception as e:
        _fail(f"ortools : {e}")
        failed = True

    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("SELECT 1")
        conn.close()
        _ok("SQLite3")
    except Exception as e:
        _fail(f"SQLite : {e}")
        failed = True

    try:
        d = tempfile.mkdtemp(prefix="citypulse_write_")
        p = os.path.join(d, "probe.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(p)
        os.rmdir(d)
        _ok("Écriture dans un dossier temporaire")
    except Exception as e:
        _fail(f"Écriture disque : {e}")
        failed = True

    try:
        importlib.import_module("keyring")
        _ok("keyring")
    except Exception as e:
        _fail(f"keyring : {e}")
        failed = True

    url = os.environ.get("CITYPULSE_OSRM_URL", "http://router.project-osrm.org").rstrip("/")
    test_url = f"{url}/route/v1/driving/-7.5898,33.5731;-7.6,33.58?overview=false"
    try:
        req = urllib.request.Request(test_url, headers={"User-Agent": "CityPulse-check/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
        data = json.loads(body.decode("utf-8", errors="replace"))
        if data.get("code") == "Ok" and resp.status == 200:
            _ok(f"OSRM HTTP ({url})")
        else:
            _fail(f"OSRM réponse inattendue ({resp.status}, code={data.get('code')!r})")
            failed = True
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _fail("OSRM : limite de débit (429) — réessayez plus tard")
            failed = True
        else:
            _fail(f"OSRM HTTP {e.code}")
            failed = True
    except Exception as e:
        _fail(f"OSRM / réseau : {e}")
        failed = True

    print()
    if failed:
        print("Résultat : des problèmes ont été détectés.")
        return 1
    print("Résultat : environnement utilisable pour CityPulse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
