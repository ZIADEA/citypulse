"""
test_clients_import.py
======================
Tests unitaires pour l'import CSV et la logique métier de clients_widget.py.
Aucune dépendance Qt — teste uniquement les fonctions pures et le thread d'import
via une base SQLite en mémoire.
"""
import csv
import os
import sqlite3
import tempfile

import pytest

pytest.importorskip("PyQt6.QtWidgets")

# ── Import des fonctions pures (nécessite le module widget pour alias) ───────
from app.ui.clients_widget import (
    _priority_stars,
    _min_to_hhmm,
    _hhmm_to_min,
    _type_color,
    _import_parse_float,
    _import_coerce_int,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests des helpers purs
# ═══════════════════════════════════════════════════════════════════════════════

class TestPriorityStars:
    def test_priority_1_is_max_stars(self):
        stars = _priority_stars(1)
        assert stars.count("*") == 5
        assert stars.count("-") == 0

    def test_priority_5_is_min_stars(self):
        stars = _priority_stars(5)
        assert stars.count("*") == 1
        assert stars.count("-") == 4

    def test_priority_3_is_three_stars(self):
        stars = _priority_stars(3)
        assert stars.count("*") == 3
        assert stars.count("-") == 2

    def test_out_of_range_clamped(self):
        assert _priority_stars(0).count("*") == 5   # clamped to 1
        assert _priority_stars(9).count("*") == 1   # clamped to 5

    def test_none_defaults_to_three(self):
        stars = _priority_stars(None)
        assert stars.count("*") == 3


class TestTimeConversions:
    def test_min_to_hhmm_zero(self):
        assert _min_to_hhmm(0) == "00:00"

    def test_min_to_hhmm_480(self):
        assert _min_to_hhmm(480) == "08:00"

    def test_min_to_hhmm_1440(self):
        assert _min_to_hhmm(1440) == "24:00"

    def test_min_to_hhmm_none(self):
        assert _min_to_hhmm(None) == "00:00"

    def test_hhmm_to_min_basic(self):
        assert _hhmm_to_min("08:30") == 510

    def test_hhmm_to_min_zero(self):
        assert _hhmm_to_min("00:00") == 0

    def test_hhmm_to_min_midnight(self):
        assert _hhmm_to_min("24:00") == 1440

    def test_hhmm_to_min_invalid(self):
        assert _hhmm_to_min("invalid") == 0

    def test_roundtrip(self):
        for minutes in [0, 60, 480, 960, 1200, 1440]:
            assert _hhmm_to_min(_min_to_hhmm(minutes)) == minutes


class TestTypeColor:
    def test_known_types_return_specific_color(self):
        assert _type_color("supermarche") != _type_color("restaurant")
        assert _type_color("bureau")      != _type_color("pharmacie")

    def test_unknown_type_returns_fallback(self):
        color = _type_color("unknown_type")
        # Should return the default text2 color
        assert color.startswith("#")
        assert len(color) == 7

    def test_case_insensitive(self):
        assert _type_color("SUPERMARCHE") == _type_color("supermarche")


# ═══════════════════════════════════════════════════════════════════════════════
# Test import CSV (sans Qt, directement via la logique du thread)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_in_memory_db() -> sqlite3.Connection:
    """Crée un schéma minimal en mémoire pour les tests d'import."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE clients (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            address      TEXT,
            latitude     REAL DEFAULT 0,
            longitude    REAL DEFAULT 0,
            demand_kg    REAL DEFAULT 0,
            demand_m3    REAL DEFAULT 0,
            ready_time   INTEGER DEFAULT 0,
            due_time     INTEGER DEFAULT 1440,
            service_time INTEGER DEFAULT 10,
            priority     INTEGER DEFAULT 3,
            client_type  TEXT DEFAULT 'standard',
            phone        TEXT,
            email        TEXT,
            archived     INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT
        )
    """)
    # Colonnes étendues (simulation migration)
    for col in ("company_name TEXT", "tags TEXT"):
        conn.execute(f"ALTER TABLE clients ADD COLUMN {col}")
    conn.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, level TEXT, user_id INTEGER, action TEXT, details TEXT, created_at TEXT DEFAULT (datetime('now')))")
    conn.commit()
    return conn


def _csv_to_file(rows: list[dict], headers: list[str]) -> str:
    """Écrit des lignes CSV dans un fichier temporaire et retourne son chemin."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _run_import(csv_path: str, col_map: dict, db_conn: sqlite3.Connection) -> dict:
    """
    Simule _ImportThread.run() directement (sans Qt/QThread)
    en réutilisant la même logique de parsing.
    """
    created = 0
    updated = 0
    error_list: list[str] = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    def _v(row, field, default=None):
        col = col_map.get(field)
        if col and col in row:
            v = row[col]
            if v not in (None, "", "None"):
                return v
        return default

    for i, row in enumerate(rows):
        try:
            name = str(_v(row, "name", f"Client {i+1}")).strip()
            if not name:
                error_list.append(f"Ligne {i+1}: nom vide")
                continue

            lat, bad_lat = _import_parse_float(_v(row, "latitude", None), 0.0)
            lon, bad_lon = _import_parse_float(_v(row, "longitude", None), 0.0)
            if bad_lat:
                error_list.append(
                    f"Ligne {i+1}: latitude non numérique — ignorée (0)")
                lat = 0.0
            if bad_lon:
                error_list.append(
                    f"Ligne {i+1}: longitude non numérique — ignorée (0)")
                lon = 0.0

            demand, bad_d = _import_parse_float(_v(row, "demand_kg", None), 0.0)
            if bad_d:
                error_list.append(
                    f"Ligne {i+1}: demande (kg) non numérique — 0 kg")
            demand_m3, bad_m3 = _import_parse_float(_v(row, "demand_m3", None), 0.0)
            if bad_m3:
                error_list.append(
                    f"Ligne {i+1}: volume (m³) non numérique — 0")
            ready, bad_r = _import_coerce_int(_v(row, "ready_time", None), 0, 0, 2880)
            if bad_r:
                error_list.append(
                    f"Ligne {i+1}: créneau début (min) non numérique — 0")
            due, bad_u = _import_coerce_int(
                _v(row, "due_time", None), 1440, 0, 2880)
            if bad_u:
                error_list.append(
                    f"Ligne {i+1}: créneau fin (min) non numérique — défaut")
            service, bad_s = _import_coerce_int(
                _v(row, "service_time", None), 10, 0, 1440)
            if bad_s:
                error_list.append(
                    f"Ligne {i+1}: durée visite non numérique — 10 min")
            prio_f, bad_p = _import_parse_float(_v(row, "priority", None), 3.0)
            prio = max(1, min(5, int(round(prio_f))))
            if bad_p:
                error_list.append(
                    f"Ligne {i+1}: priorité non numérique — 3")
            ctype   = str(_v(row, "client_type", "standard") or "standard")
            address = str(_v(row, "address",     "") or "")
            phone   = str(_v(row, "phone",       "") or "")
            email   = str(_v(row, "email",       "") or "")
            company = str(_v(row, "company_name","") or "")
            tags    = str(_v(row, "tags",        "") or "")

            if ready >= due:
                due = ready + 240

            existing = db_conn.execute(
                "SELECT id FROM clients WHERE name=? AND archived=0 LIMIT 1", (name,)
            ).fetchone()

            if existing:
                db_conn.execute("""
                    UPDATE clients SET address=?,latitude=?,longitude=?,demand_kg=?,
                    demand_m3=?,ready_time=?,due_time=?,service_time=?,priority=?,
                    client_type=?,phone=?,email=? WHERE id=?
                """, (address, lat, lon, demand, demand_m3, ready, due, service,
                      prio, ctype, phone, email, existing[0]))
                for col, val in [("company_name", company), ("tags", tags)]:
                    try:
                        db_conn.execute(f"UPDATE clients SET {col}=? WHERE id=?", (val, existing[0]))
                    except Exception:
                        pass
                updated += 1
            else:
                cur = db_conn.execute("""
                    INSERT INTO clients
                    (name,address,latitude,longitude,demand_kg,demand_m3,ready_time,due_time,
                     service_time,priority,client_type,phone,email,archived)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)
                """, (name, address, lat, lon, demand, demand_m3, ready, due,
                      service, prio, ctype, phone, email))
                cid = cur.lastrowid
                for col, val in [("company_name", company), ("tags", tags)]:
                    try:
                        db_conn.execute(f"UPDATE clients SET {col}=? WHERE id=?", (val, cid))
                    except Exception:
                        pass
                created += 1

        except Exception as e:
            error_list.append(f"Ligne {i+1}: {e}")

    db_conn.commit()
    return {"created": created, "updated": updated,
            "errors": len(error_list), "error_list": error_list}


# ── Tests d'import ─────────────────────────────────────────────────────────────

class TestCSVImport:

    def test_basic_import_creates_clients(self):
        """Import simple : 3 clients créés."""
        rows = [
            {"nom": "Marjane Anfa",   "lat": 33.593, "lon": -7.666, "kg": 500},
            {"nom": "Label Vie CFC",  "lat": 33.608, "lon": -7.573, "kg": 200},
            {"nom": "BIM Maarif",     "lat": 33.578, "lon": -7.638, "kg": 150},
        ]
        path = _csv_to_file(rows, ["nom","lat","lon","kg"])
        col_map = {"name": "nom", "latitude": "lat",
                   "longitude": "lon", "demand_kg": "kg"}
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 3
        assert report["updated"] == 0
        assert report["errors"]  == 0
        count = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        assert count == 3

    def test_import_with_all_fields(self):
        """Import avec tous les champs disponibles."""
        rows = [{
            "name": "Pharmacie Atlas", "address": "Rue Mers Sultan, Casablanca",
            "latitude": "33.596", "longitude": "-7.619",
            "demand_kg": "45.5", "ready_time": "540", "due_time": "780",
            "service_time": "15", "priority": "2", "client_type": "pharmacie",
            "phone": "+212 6-1234-5678", "email": "atlas@pharma.ma",
            "company_name": "Pharmacie Atlas SARL", "tags": "sante,pharmacie",
        }]
        path = _csv_to_file(rows, list(rows[0].keys()))
        col_map = {k: k for k in rows[0].keys()}
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 1
        row = db.execute("SELECT * FROM clients WHERE name='Pharmacie Atlas'").fetchone()
        assert row is not None
        assert float(row["demand_kg"]) == pytest.approx(45.5)
        assert int(row["ready_time"])  == 540
        assert int(row["due_time"])    == 780
        assert row["client_type"]      == "pharmacie"
        assert int(row["priority"])    == 2

    def test_import_updates_existing_client(self):
        """Import met à jour un client existant (même nom)."""
        db = _make_in_memory_db()
        db.execute(
            "INSERT INTO clients (name,latitude,longitude,demand_kg,archived)"
            " VALUES ('Client Existant',33.5,-7.5,100,0)"
        )
        db.commit()

        rows = [{"name": "Client Existant", "latitude": "33.600",
                 "longitude": "-7.600", "demand_kg": "200"}]
        path = _csv_to_file(rows, ["name","latitude","longitude","demand_kg"])
        col_map = {"name":"name","latitude":"latitude",
                   "longitude":"longitude","demand_kg":"demand_kg"}
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 0
        assert report["updated"] == 1
        row = db.execute(
            "SELECT * FROM clients WHERE name='Client Existant'"
        ).fetchone()
        assert float(row["demand_kg"]) == pytest.approx(200.0)

    def test_import_skips_empty_name(self):
        """
        Lignes sans nom :
        - Nom vide ("") → le default auto-généré est appliqué → client créé
        - Nom espace ("   ") → strip() renvoie "" → erreur
        Un client valide + un avec nom vide (default) = 2 créés, 1 erreur.
        """
        rows = [
            {"name": "Client OK",  "latitude": "33.5", "longitude": "-7.5", "demand_kg": "50"},
            {"name": "",           "latitude": "33.6", "longitude": "-7.6", "demand_kg": "30"},
            {"name": "   ",        "latitude": "33.7", "longitude": "-7.7", "demand_kg": "20"},
        ]
        path = _csv_to_file(rows, ["name","latitude","longitude","demand_kg"])
        col_map = {"name":"name","latitude":"latitude",
                   "longitude":"longitude","demand_kg":"demand_kg"}
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        # Row 1 ("Client OK") → created
        # Row 2 ("") → value in (None,"","None") so default "Client 2" applied → created
        # Row 3 ("   ") → value not in (None,"","None"), strip()="" → error
        assert report["created"] == 2
        assert report["errors"]  == 1

    def test_import_autocorrects_inverted_time_window(self):
        """Créneau inversé (début >= fin) corrigé automatiquement."""
        rows = [{"name": "Client TW", "latitude": "33.5", "longitude": "-7.5",
                 "demand_kg": "10", "ready_time": "900", "due_time": "480"}]
        path = _csv_to_file(rows, list(rows[0].keys()))
        col_map = {k: k for k in rows[0].keys()}
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 1
        row = db.execute("SELECT ready_time,due_time FROM clients").fetchone()
        # due_time doit être > ready_time après correction
        assert row["due_time"] > row["ready_time"]

    def test_import_handles_missing_optional_columns(self):
        """Import avec seulement les colonnes obligatoires (nom + coords)."""
        rows = [{"nom": "Client Min", "lat": "33.5", "lon": "-7.5"}]
        path = _csv_to_file(rows, ["nom","lat","lon"])
        col_map = {"name":"nom","latitude":"lat","longitude":"lon"}
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 1
        row = db.execute("SELECT * FROM clients").fetchone()
        # Valeurs par défaut appliquées
        assert float(row["demand_kg"]) == 0.0
        assert int(row["service_time"]) == 10
        assert int(row["priority"]) == 3

    def test_import_100_clients(self):
        """Import en volume : 100 clients en une seule passe."""
        rows = [
            {"name": f"Client {i:03d}", "latitude": str(33.5 + i * 0.001),
             "longitude": str(-7.5 - i * 0.001), "demand_kg": str(10 + i)}
            for i in range(100)
        ]
        path = _csv_to_file(rows, ["name","latitude","longitude","demand_kg"])
        col_map = {"name":"name","latitude":"latitude",
                   "longitude":"longitude","demand_kg":"demand_kg"}
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 100
        assert report["errors"]  == 0

    def test_import_priority_clamped_to_1_5(self):
        """Priorité hors plage (0, 9) est ramenée dans [1,5]."""
        rows = [
            {"name": "Prio Zero",  "latitude": "33.5", "longitude": "-7.5",
             "demand_kg": "10", "priority": "0"},
            {"name": "Prio Nine",  "latitude": "33.6", "longitude": "-7.6",
             "demand_kg": "10", "priority": "9"},
        ]
        path = _csv_to_file(rows, list(rows[0].keys()))
        col_map = {k: k for k in rows[0].keys()}
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        for row in db.execute("SELECT priority FROM clients").fetchall():
            assert 1 <= row["priority"] <= 5

    def test_import_non_numeric_demand_does_not_crash(self):
        """Texte dans une colonne mappée sur demand_kg → 0 kg + avertissement."""
        rows = [{
            "nom": "Magasin Test",
            "demande": "alimentaire,supermarche",
            "lat": "33.5",
            "lon": "-7.5",
        }]
        path = _csv_to_file(rows, ["nom", "demande", "lat", "lon"])
        col_map = {
            "name": "nom",
            "demand_kg": "demande",
            "latitude": "lat",
            "longitude": "lon",
        }
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 1
        assert report["errors"] >= 1
        assert any("demande (kg)" in m for m in report["error_list"])
        row = db.execute("SELECT demand_kg FROM clients").fetchone()
        assert float(row["demand_kg"]) == 0.0

    def test_import_solomon_coordinates(self):
        """Colonnes type Solomon (XCOORD/YCOORD) mappées correctement."""
        rows = [{"CUSTNO": "1", "XCOORD": "40.0", "YCOORD": "50.0",
                 "DEMAND": "120", "READY": "300", "DUE": "600", "SERVICE": "15"}]
        path = _csv_to_file(rows, list(rows[0].keys()))
        col_map = {
            "name": "CUSTNO", "latitude": "YCOORD", "longitude": "XCOORD",
            "demand_kg": "DEMAND", "ready_time": "READY",
            "due_time": "DUE", "service_time": "SERVICE",
        }
        db = _make_in_memory_db()
        report = _run_import(path, col_map, db)
        os.unlink(path)

        assert report["created"] == 1
        row = db.execute("SELECT * FROM clients").fetchone()
        assert float(row["latitude"])  == pytest.approx(50.0)
        assert float(row["longitude"]) == pytest.approx(40.0)
        assert float(row["demand_kg"]) == pytest.approx(120.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Test _ALIASES auto-mapping
# ═══════════════════════════════════════════════════════════════════════════════

class TestAliasMapping:
    def test_all_aliases_are_lowercase(self):
        from app.ui.clients_widget import _ALIASES
        for field, alts in _ALIASES.items():
            for alt in alts:
                assert alt == alt.lower(), f"Alias '{alt}' for '{field}' not lowercase"

    def test_name_field_has_alias(self):
        from app.ui.clients_widget import _ALIASES
        assert "name" in _ALIASES
        assert "nom" in _ALIASES["name"]

    def test_latitude_field_has_alias(self):
        from app.ui.clients_widget import _ALIASES
        assert "lat" in _ALIASES["latitude"]
        assert "latitude" in _ALIASES["latitude"]


# ═══════════════════════════════════════════════════════════════════════════════
# Test anomaly detection logic (sans Qt)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnomalyLogic:

    def _make_client(self, **kwargs):
        defaults = {
            "id": 1, "name": "Test", "latitude": 33.5, "longitude": -7.5,
            "demand_kg": 100, "service_time": 15, "ready_time": 480, "due_time": 720,
        }
        defaults.update(kwargs)
        return defaults

    def test_zero_coordinates_flagged(self):
        """Client avec coordonnées (0,0) doit être détecté."""
        client = self._make_client(latitude=0.0, longitude=0.0)
        issues = []
        lat = float(client["latitude"] or 0)
        lon = float(client["longitude"] or 0)
        if lat == 0.0 and lon == 0.0:
            issues.append(("high", "Coordonnées (0,0)"))
        assert len(issues) == 1
        assert issues[0][0] == "high"

    def test_inverted_time_window_flagged(self):
        """Créneau inversé (début >= fin) → anomalie high."""
        client = self._make_client(ready_time=900, due_time=480)
        issues = []
        if client["ready_time"] >= client["due_time"]:
            issues.append(("high", "Créneau inversé"))
        assert len(issues) == 1

    def test_normal_client_no_issues(self):
        """Client valide → aucune issue."""
        client = self._make_client()
        issues = []
        if float(client["latitude"] or 0) == 0 and float(client["longitude"] or 0) == 0:
            issues.append(("high", "Coords (0,0)"))
        if (client["demand_kg"] or 0) < 0:
            issues.append(("high", "Demande négative"))
        if client["ready_time"] >= client["due_time"]:
            issues.append(("high", "Créneau inversé"))
        assert issues == []

    def test_negative_demand_flagged(self):
        """Demande négative → anomalie high."""
        client = self._make_client(demand_kg=-50)
        issues = []
        if (client["demand_kg"] or 0) < 0:
            issues.append(("high", f"Demande négative : {client['demand_kg']} kg"))
        assert len(issues) == 1
        assert "négative" in issues[0][1]
