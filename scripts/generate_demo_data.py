#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_demo_data.py — Générateur de données de démo CityPulse Logistics
==========================================================================
Usage :
  python scripts/generate_demo_data.py --dataset casablanca --db citypulse.db --reset
  python scripts/generate_demo_data.py --dataset paris     --db citypulse.db --append
  python scripts/generate_demo_data.py --dataset benchmark --db citypulse.db
  python scripts/generate_demo_data.py --dataset all       --export ./demo_data/ --reset

Script autonome (sans Qt). Faker optionnel (listes hardcodées en fallback).
"""

import argparse
import csv
import hashlib
import json
import math
import os
import random
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Setup path ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from faker import Faker
    _fk_fr = Faker("fr_FR")
    _fk_ar = Faker("ar_AA")
    HAS_FAKER = True
except ImportError:
    HAS_FAKER = False

RNG = random.Random(42)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════

_MOROCCAN_FIRST = [
    "Omar","Youssef","Hassan","Ahmed","Khalid","Mohamed","Rachid","Hamza",
    "Nizar","Soufiane","Reda","Amine","Mehdi","Bilal","Ilyes","Zakaria",
    "Fatima","Aicha","Khadija","Loubna","Nezha","Samira","Houda","Sara",
    "Leila","Nadia","Imane","Oumaima",
]
_MOROCCAN_LAST = [
    "Benali","Elmrabet","Alaoui","Benomar","Tazi","Fadili","Berrada",
    "Chafi","Benmoussa","Rhziouan","Lahlou","Benkirane","Essaadi",
    "Mansouri","El Amrani","Belkaid","Benabdallah","Hajji","Saidi","Taleb",
    "El Idrissi","Ouahbi","Ziani","Mrani","Sefiani","Bensouda",
]
_FRENCH_FIRST = [
    "Thomas","Nicolas","Mathieu","Pierre","Julien","Antoine","François",
    "Sophie","Claire","Marie","Isabelle","Nathalie","Céline","Camille",
]
_FRENCH_LAST = [
    "Martin","Bernard","Dubois","Thomas","Robert","Richard","Petit",
    "Durand","Leroy","Moreau","Simon","Laurent","Lefebvre","Michel",
]

_STREET_TYPES_MA = ["Avenue","Boulevard","Rue","Impasse","Résidence","Quartier"]
_STREET_NAMES_MA = [
    "Mohammed V","Hassan II","Zerktouni","Anfa","des FAR","Mers Sultan",
    "Driss Slaoui","Roudani","Abdelmoumen","Oum Errabia","Bir Anzarane",
    "Allal Ben Abdellah","Ibn Rochd","Al Massira","Sidi Belyout",
]
_SUPERMARCHES = [
    "Marjane","Label Vie","Carrefour Express","BIM Maroc","Asswak Salam",
    "Acima","Electroplanet","Marjane Market","MyMarket","Costo",
]
_RESTAURANTS = [
    "La Sqala","Rick's Café","Le Petit Rocher","Café Maure","Snack Tanger",
    "Restaurant Al Mounia","Pizza Hut","McDonald's","Bacha Coffee","La Taverne",
    "Dar Zitoun","L'Entrecôte","La Villa Blanche","Sunset Lounge","Brasserie du Parc",
    "Taj Palace","Oasis Restaurant","Le Cabestan","La Bodega","Cla Cla",
]
_PHARMACIES = [
    "Pharmacie Centrale","Pharmacie Anfa","Pharmacie du Maarif",
    "Pharmacie Hay Hassani","Pharmacie Sidi Belyout","Pharmacie El Fida",
    "Pharmacie Atlas","Pharmacie Zerktouni","Pharmacie Ain Diab",
    "Pharmacie CFC","Pharmacie Ben M'Sick","Pharmacie Sidi Maarouf",
]
_BUREAUX = [
    "Cabinet Audit Maroc","BMCE Finance","Attijariwafa HO","CIH Bank",
    "Office Chérifien des Phosphates","Maroc Telecom","RAM Office",
    "Agence OCP","ONCF Bureau","Lydec Direction","Délégation Commerce",
    "CNSS Agence","ANAPEC Bureau","Barid Al Maghrib HO","ONSSA Bureau",
    "Ministère délégué","Wilaya Grand Casablanca",
]

# ── Zones géographiques Casablanca ────────────────────────────────────────────
_CSB_AREAS = [
    {"name": "Anfa",         "lat": 33.593, "lon": -7.666, "r": 0.015},
    {"name": "Maarif",       "lat": 33.578, "lon": -7.638, "r": 0.010},
    {"name": "CFC",          "lat": 33.608, "lon": -7.573, "r": 0.012},
    {"name": "Hay Hassani",  "lat": 33.556, "lon": -7.647, "r": 0.018},
    {"name": "Sidi Maarouf", "lat": 33.551, "lon": -7.641, "r": 0.015},
    {"name": "Centre Ville", "lat": 33.596, "lon": -7.619, "r": 0.010},
    {"name": "Ben M'Sick",   "lat": 33.558, "lon": -7.582, "r": 0.014},
    {"name": "Ain Diab",     "lat": 33.590, "lon": -7.668, "r": 0.012},
    {"name": "Derb Omar",    "lat": 33.582, "lon": -7.612, "r": 0.010},
    {"name": "Ain Chok",     "lat": 33.530, "lon": -7.625, "r": 0.015},
    {"name": "Sidi Bernoussi","lat":33.607, "lon": -7.537, "r": 0.014},
    {"name": "Hay Mohammadi","lat": 33.565, "lon": -7.572, "r": 0.013},
    {"name": "Lissasfa",     "lat": 33.532, "lon": -7.677, "r": 0.016},
    {"name": "Bouskoura",    "lat": 33.489, "lon": -7.638, "r": 0.014},
]

_VEH_STATUSES = ["disponible","disponible","disponible","en service","maintenance"]
_LOG_ACTIONS  = [
    "CLIENT_CREATE","CLIENT_UPDATE","VEHICLE_UPDATE","ROUTE_CREATE",
    "OPTIMIZE_RUN","LOGIN","LOGOUT","SESSION_START","ORDER_CREATE",
    "ORDER_UPDATE","REPORT_GENERATE","DRIVER_CREATE","SETTINGS_UPDATE",
]

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def _rnd_coord(lat_c: float, lon_c: float, radius: float) -> tuple:
    angle = RNG.uniform(0, 2 * math.pi)
    r     = radius * math.sqrt(RNG.random())
    return round(lat_c + r * math.cos(angle), 6), round(lon_c + r * math.sin(angle), 6)

def _rnd_name_ma() -> str:
    return f"{RNG.choice(_MOROCCAN_FIRST)} {RNG.choice(_MOROCCAN_LAST)}"

def _rnd_name_fr() -> str:
    return f"{RNG.choice(_FRENCH_FIRST)} {RNG.choice(_FRENCH_LAST)}"

def _rnd_phone_ma() -> str:
    return f"+212 {RNG.randint(6,7)}{RNG.randint(0,9)}-{RNG.randint(100000,999999)}"

def _rnd_email(name: str, domain: str = "gmail.com") -> str:
    slug = name.lower().replace(" ", ".").replace("'", "")
    return f"{slug}{RNG.randint(1,99)}@{domain}"

def _hash_pw(password: str, salt: str = None):
    if salt is None:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return pw_hash, salt

def _now_offset(days: int = 0, hours: int = 0) -> str:
    dt = datetime.now() - timedelta(days=days, hours=hours)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def _date_offset(days: int = 0) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def _time_add(base_min: int, offset_min: int) -> str:
    total = base_min + offset_min
    return f"{total // 60:02d}:{total % 60:02d}"

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a  = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _box_geojson(lat_c, lon_c, r_lat=0.02, r_lon=0.03) -> str:
    coords = [
        [lon_c - r_lon, lat_c - r_lat],
        [lon_c + r_lon, lat_c - r_lat],
        [lon_c + r_lon, lat_c + r_lat],
        [lon_c - r_lon, lat_c + r_lat],
        [lon_c - r_lon, lat_c - r_lat],
    ]
    return json.dumps({"type": "Polygon", "coordinates": [coords]})

def _plate_ma() -> str:
    n = RNG.randint(10000, 99999)
    c = RNG.choice("ABCDEGHIJKLMNPQRSTVWYZ")
    return f"MA-{n}-{c}"

def _plate_fr() -> str:
    n = RNG.randint(100, 999)
    letters = "".join(RNG.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=2))
    dept = RNG.randint(10, 95)
    return f"{n}-{letters}-{dept}"

def _lic_num() -> str:
    return f"DL{RNG.randint(10000000, 99999999)}"

def progress(msg: str, step: int = 0, total: int = 0, cb=None):
    """Affiche la progression (print ou callback)."""
    if cb:
        cb(msg, step, total)
    else:
        pct = f" [{step}/{total}]" if total else ""
        print(f"  > {msg}{pct}")

# ═══════════════════════════════════════════════════════════════════════════════
# CONNEXION / MIGRATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def _apply_migrations(db_path: str):
    """Applique init_database() + run_migrations() via db_manager."""
    import app.database.db_manager as _dbm
    orig_path     = _dbm.DB_PATH
    _dbm.DB_PATH  = os.path.abspath(db_path)
    try:
        _dbm.init_database()
        _dbm.run_migrations()
    finally:
        _dbm.DB_PATH = orig_path

def _reset_tables(conn: sqlite3.Connection, keep_users: bool = True):
    """Supprime les données métier (garde le schéma et optionnellement les users)."""
    tables_to_clear = [
        "route_stops","routes","carrier_shipments","orders",
        "team_members","teams","driver_unavailabilities","drivers",
        "arrets","tournees","anomalies","algo_results",
        "recurring_order_templates","ai_conversations","reports_history",
        "zones","notifications","scenarios",
        "clients","carriers","vehicles","depots",
        "distance_cache","translation_history","translation_glossary","logs",
    ]
    if not keep_users:
        tables_to_clear.append("users")
    for t in tables_to_clear:
        try:
            conn.execute(f"DELETE FROM {t}")
        except Exception:
            pass
    conn.commit()
    print("  OK - Tables videes")

def _has_table(conn, name: str) -> bool:
    r = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0]
    return r > 0

# ═══════════════════════════════════════════════════════════════════════════════
# GÉNÉRATEURS CASABLANCA
# ═══════════════════════════════════════════════════════════════════════════════

def _gen_users_casablanca(conn: sqlite3.Connection) -> list:
    users = [
        ("admin",      "admin",   "administrateur", "Admin Système",      "admin@citypulse.ma",   "+212 5-220-00001"),
        ("planificateur","demo123","planner",        "Khalid Tazi",        "k.tazi@citypulse.ma",  "+212 6-1234-5678"),
        ("dispatcher", "demo123", "dispatcher",     "Loubna El Amrani",   "l.elamrani@citypulse.ma","+212 6-8765-4321"),
    ]
    ids = []
    for username, pwd, role, full_name, email, phone in users:
        pw_hash, salt = _hash_pw(pwd)
        perms = json.dumps({"*": ["*"]}) if role == "administrateur" else json.dumps({})
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO users "
                "(username,password_hash,salt,role,full_name,email,last_login,created_at)"
                " VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (username, pw_hash, salt, role, full_name, email)
            )
            # Try to add new columns if migration applied
            for col, val in [("phone", phone), ("permissions", perms), ("is_active", 1)]:
                try:
                    conn.execute(f"UPDATE users SET {col}=? WHERE username=?", (val, username))
                except Exception:
                    pass
            uid = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0]
            ids.append(uid)
        except Exception:
            pass
    conn.commit()
    return ids

def _gen_depots_casablanca(conn: sqlite3.Connection) -> list:
    depots = [
        {
            "name": "Dépôt Ain Diab",
            "address": "Boulevard de la Corniche, Ain Diab, Casablanca",
            "lat": 33.5893, "lon": -7.6681,
            "opening": "06:00", "closing": "22:00",
            "manager": "Hassan Alaoui", "phone": "+212 5-222-11001",
            "bays": 6, "capacity": 5000, "cross_dock": 0,
        },
        {
            "name": "Dépôt Sidi Maarouf",
            "address": "Zone Industrielle Sidi Maarouf, Casablanca",
            "lat": 33.5500, "lon": -7.6387,
            "opening": "05:00", "closing": "23:00",
            "manager": "Fatima Benali", "phone": "+212 5-222-22002",
            "bays": 10, "capacity": 10000, "cross_dock": 1,
        },
        {
            "name": "Dépôt Ain Sebaa",
            "address": "Route d'El Jadida, Ain Sebaa, Casablanca",
            "lat": 33.6028, "lon": -7.5361,
            "opening": "07:00", "closing": "21:00",
            "manager": "Youssef Elmrabet", "phone": "+212 5-222-33003",
            "bays": 4, "capacity": 3000, "cross_dock": 0,
        },
    ]
    ids = []
    for d in depots:
        cur = conn.execute(
            "INSERT INTO depots (name,address,latitude,longitude,opening_time,closing_time,"
            "storage_capacity,created_at) VALUES (?,?,?,?,?,?,?,datetime('now'))",
            (d["name"], d["address"], d["lat"], d["lon"],
             d["opening"], d["closing"], d["capacity"])
        )
        did = cur.lastrowid
        for col, val in [
            ("manager_name", d["manager"]), ("phone", d["phone"]),
            ("open_time", d["opening"]), ("close_time", d["closing"]),
            ("max_vehicles", 20), ("loading_bays", d["bays"]),
            ("loading_time_minutes", 30), ("is_cross_dock", d["cross_dock"]),
        ]:
            try:
                conn.execute(f"UPDATE depots SET {col}=? WHERE id=?", (val, did))
            except Exception:
                pass
        ids.append(did)
    conn.commit()
    return ids

def _gen_vehicles_casablanca(conn: sqlite3.Connection, depot_ids: list) -> list:
    d1, d2, d3 = depot_ids[0], depot_ids[1], depot_ids[2]
    now   = datetime.now()
    exp_y = (now + timedelta(days=365)).strftime("%Y-%m-%d")
    exp_ct= (now + timedelta(days=180)).strftime("%Y-%m-%d")

    vehicles = [
        # registration, type, capacity_kg, capacity_m3, speed, cost_km, depot_id, status
        # + brand, model, year, vehicle_type, fuel_type, co2, adr, zfe
        (_plate_ma(),"frigo",  800,12.0,80,0.85,d1,"disponible","Renault","Master",2022,"van","diesel",0.28,1,1),
        (_plate_ma(),"frigo",  800,12.0,80,0.85,d1,"disponible","Renault","Master",2023,"van","diesel",0.28,1,1),
        (_plate_ma(),"fourgon",500, 8.0,90,0.65,d2,"disponible","Mercedes","Sprinter",2021,"van","diesel",0.22,0,1),
        (_plate_ma(),"fourgon",500, 8.0,90,0.65,d2,"en service","Mercedes","Sprinter",2022,"van","diesel",0.22,0,1),
        (_plate_ma(),"fourgon",500, 8.0,90,0.65,d3,"disponible","Mercedes","Sprinter",2023,"van","diesel",0.21,0,1),
        (_plate_ma(),"camionnette",200,4.0,80,0.45,d1,"disponible","Citroën","Berlingo",2023,"van","diesel",0.19,0,1),
        (_plate_ma(),"camionnette",200,4.0,80,0.45,d2,"disponible","Citroën","Berlingo",2022,"van","electric",0.05,0,1),
        ("VELO-001", "velo",    60, 0.5,25,0.08,d1,"disponible","Babboe","Cargo",2024,"velo","electricite",0.00,0,1),
    ]
    ids = []
    for v in vehicles:
        reg,vtype,cap_kg,cap_m3,speed,cost,depot,status,brand,model,year,vtype2,fuel,co2,adr,zfe = v
        cur = conn.execute(
            "INSERT INTO vehicles (registration,type,capacity_kg,capacity_m3,"
            "max_speed_kmh,cost_per_km,depot_id,status,total_km,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
            (reg, vtype, cap_kg, cap_m3, speed, cost, depot, status,
             RNG.randint(10000, 180000))
        )
        vid = cur.lastrowid
        for col, val in [
            ("registration_plate", reg), ("brand", brand), ("model", model),
            ("year", year), ("vehicle_type", vtype2), ("fuel_type", fuel),
            ("co2_per_km", co2), ("allowed_adr", adr), ("allowed_zfe", zfe),
            ("insurance_expiry", exp_y), ("technical_inspection_expiry", exp_ct),
            ("cost_per_hour", 15.0), ("cost_fixed_daily", 50.0),
            ("speed_highway", 110), ("speed_national", 80),
            ("speed_urban", 45), ("reload_allowed", 1),
        ]:
            try:
                conn.execute(f"UPDATE vehicles SET {col}=? WHERE id=?", (val, vid))
            except Exception:
                pass
        ids.append(vid)
    conn.commit()
    return ids

def _gen_drivers_casablanca(conn: sqlite3.Connection, depot_ids: list, vehicle_ids: list) -> list:
    if not _has_table(conn, "drivers"):
        return []
    drivers_data = [
        ("Omar",    "Benali",    "B","CDI", depot_ids[0], vehicle_ids[0]),
        ("Youssef", "Elmrabet",  "C","CDI", depot_ids[0], vehicle_ids[1]),
        ("Hassan",  "Alaoui",    "C","CDI", depot_ids[1], vehicle_ids[2]),
        ("Ahmed",   "Benomar",   "B","CDD", depot_ids[1], vehicle_ids[3]),
        ("Khalid",  "Tazi",      "C","CDI", depot_ids[2], vehicle_ids[4]),
        ("Mohamed", "Fadili",    "B","CDI", depot_ids[0], vehicle_ids[5]),
        ("Rachid",  "Berrada",   "B","CDI", depot_ids[1], vehicle_ids[6]),
        ("Hamza",   "Chafi",     "B","CDD", depot_ids[0], vehicle_ids[7]),
    ]
    now = datetime.now()
    ids = []
    for fn, ln, lic_cat, contract, home_depot, veh_id in drivers_data:
        lic_exp = (now + timedelta(days=RNG.randint(180, 1825))).strftime("%Y-%m-%d")
        qualifs = json.dumps(
            RNG.sample(["ADR","FRIGO","POIDS_LOURD","MATIÈRES_DANGEREUSES","ECO_CONDUITE"], k=RNG.randint(1,3))
        )
        cur = conn.execute("""
            INSERT INTO drivers
            (first_name,last_name,phone,email,license_number,license_category,
             license_expiry,qualifications,contract_type,home_depot_id,vehicle_id,
             work_start_time,work_end_time,lunch_time,lunch_duration_minutes,
             max_daily_hours,archived,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,datetime('now'))
        """, (
            fn, ln,
            _rnd_phone_ma(),
            _rnd_email(f"{fn} {ln}", "citypulse.ma"),
            _lic_num(), lic_cat, lic_exp, qualifs, contract,
            home_depot, veh_id,
            "07:00","17:00","12:00",60,10.0,
        ))
        ids.append(cur.lastrowid)
    conn.commit()
    return ids

def _gen_teams_casablanca(conn: sqlite3.Connection, driver_ids: list) -> list:
    if not _has_table(conn, "teams") or not driver_ids:
        return []
    teams = [
        ("Équipe Nord",  driver_ids[0], "Zone Ain Diab, Anfa, CFC"),
        ("Équipe Sud",   driver_ids[4], "Zone Sidi Maarouf, Hay Hassani, Ain Chok"),
    ]
    team_ids = []
    for name, mgr, desc in teams:
        cur = conn.execute(
            "INSERT INTO teams (name,manager_driver_id,description,archived,created_at)"
            " VALUES (?,?,?,0,datetime('now'))",
            (name, mgr, desc)
        )
        team_ids.append(cur.lastrowid)
    # team_members
    members = [(team_ids[0], driver_ids[:4]), (team_ids[1], driver_ids[4:])]
    for tid, dids in members:
        for did in dids:
            try:
                conn.execute(
                    "INSERT INTO team_members (team_id,driver_id,joined_at)"
                    " VALUES (?,?,datetime('now'))",
                    (tid, did)
                )
            except Exception:
                pass
    conn.commit()
    return team_ids

def _gen_clients_casablanca(conn: sqlite3.Connection) -> list:
    """80 clients dans les quartiers réels de Casablanca."""
    clients = []

    # 24 supermarchés : 200-1000 kg, 06h-10h
    _sm_used: dict = {}
    def _sm_name(i):
        base = f"{_SUPERMARCHES[i % len(_SUPERMARCHES)]} {_CSB_AREAS[i % len(_CSB_AREAS)]['name']}"
        _sm_used[base] = _sm_used.get(base, 0) + 1
        return base if _sm_used[base] == 1 else f"{base} #{_sm_used[base]}"
    for i in range(24):
        name = _sm_name(i)
        area = _CSB_AREAS[i % len(_CSB_AREAS)]
        lat, lon = _rnd_coord(area["lat"], area["lon"], area["r"])
        clients.append({
            "name": name, "lat": lat, "lon": lon,
            "demand_kg": round(RNG.uniform(200, 1000), 1),
            "ready": 360, "due": 600,    # 06:00-10:00
            "service": RNG.randint(20, 45),
            "client_type": "supermarche", "priority": 1,
            "tags": "alimentaire,supermarche",
            "company": _SUPERMARCHES[i % len(_SUPERMARCHES)],
        })

    # 20 restaurants : 20-80 kg, 08h-12h ou 14h-18h
    for i in range(20):
        area = RNG.choice(_CSB_AREAS)
        lat, lon = _rnd_coord(area["lat"], area["lon"], area["r"])
        morning = RNG.random() > 0.5
        clients.append({
            "name": f"{_RESTAURANTS[i % len(_RESTAURANTS)]} {area['name']} #{i+1}",
            "lat": lat, "lon": lon,
            "demand_kg": round(RNG.uniform(20, 80), 1),
            "ready": 480 if morning else 840,
            "due":   720 if morning else 1080,
            "service": RNG.randint(10, 20),
            "client_type": "restaurant", "priority": 2,
            "tags": "alimentaire,restaurant",
            "company": RNG.choice(_RESTAURANTS),
        })

    # 16 bureaux : 5-30 kg, 08h-17h
    for i in range(16):
        area = RNG.choice(_CSB_AREAS)
        lat, lon = _rnd_coord(area["lat"], area["lon"], area["r"])
        clients.append({
            "name": f"{_BUREAUX[i % len(_BUREAUX)]} - {area['name']}",
            "lat": lat, "lon": lon,
            "demand_kg": round(RNG.uniform(5, 30), 1),
            "ready": 480, "due": 1020,
            "service": RNG.randint(10, 20),
            "client_type": "bureau", "priority": 3,
            "tags": "bureautique",
            "company": "",
        })

    # 12 pharmacies : 10-50 kg, 09h-13h ou 15h-19h
    for i in range(12):
        area = RNG.choice(_CSB_AREAS)
        lat, lon = _rnd_coord(area["lat"], area["lon"], area["r"])
        morning = RNG.random() > 0.5
        clients.append({
            "name": f"{_PHARMACIES[i % len(_PHARMACIES)]} {area['name']}",
            "lat": lat, "lon": lon,
            "demand_kg": round(RNG.uniform(10, 50), 1),
            "ready": 540 if morning else 900,
            "due":   780 if morning else 1140,
            "service": RNG.randint(10, 15),
            "client_type": "pharmacie", "priority": 2,
            "tags": "sante,pharmacie",
            "company": "",
        })

    # 8 particuliers : 5-20 kg, 10h-14h
    for i in range(8):
        area = RNG.choice(_CSB_AREAS)
        lat, lon = _rnd_coord(area["lat"], area["lon"], area["r"])
        name = _rnd_name_ma()
        clients.append({
            "name": name,
            "lat": lat, "lon": lon,
            "demand_kg": round(RNG.uniform(5, 20), 1),
            "ready": 600, "due": 840,
            "service": 10,
            "client_type": "particulier", "priority": 4,
            "tags": "particulier",
            "company": "",
        })

    ids = []
    for i, c in enumerate(clients):
        street  = f"{RNG.choice(_STREET_TYPES_MA)} {RNG.choice(_STREET_NAMES_MA)}, {RNG.choice([a['name'] for a in _CSB_AREAS])}, Casablanca"
        phone   = _rnd_phone_ma()
        email   = _rnd_email(c["name"])
        cur = conn.execute("""
            INSERT INTO clients
            (cust_no,name,address,latitude,longitude,demand_kg,ready_time,due_time,
             service_time,priority,client_type,phone,email,archived,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,datetime('now'))
        """, (
            i + 1, c["name"][:80], street,
            c["lat"], c["lon"], c["demand_kg"],
            c["ready"], c["due"], c["service"],
            c["priority"], c["client_type"], phone, email,
        ))
        cid = cur.lastrowid
        for col, val in [
            ("tags", c.get("tags","")), ("company_name", c.get("company","")),
            ("service_duration_minutes", c["service"]),
            ("punctuality_factor", round(RNG.uniform(0.8, 1.2), 2)),
        ]:
            try:
                conn.execute(f"UPDATE clients SET {col}=? WHERE id=?", (val, cid))
            except Exception:
                pass
        ids.append(cid)
    conn.commit()
    return ids

def _gen_carriers_casablanca(conn: sqlite3.Connection) -> list:
    if not _has_table(conn, "carriers"):
        return []
    carriers = [
        ("DHL Maroc","Ali Skalli","+212 5-222-50001","dhl@dhl.ma",
         "https://www.dhl.ma","Casablanca,Rabat,Marrakech","fourgon,camion",
         1.80, 0.05, 25.0, 4.2, 0.94),
        ("Amana Express","Sara Bensouda","+212 5-222-50002","contact@amana.ma",
         "https://www.amana.ma","Maroc complet","fourgon,moto",
         1.50, 0.08, 15.0, 3.8, 0.88),
        ("CTM Messagerie","Driss Lahlou","+212 5-222-50003","messagerie@ctm.ma",
         "https://www.ctm.ma","Maroc, Espagne","camion",
         1.20, 0.04, 20.0, 3.5, 0.82),
    ]
    ids = []
    for name,contact,phone,email,website,zones,vtypes,cpkm,cpkg,cfixed,rating,otr in carriers:
        cur = conn.execute("""
            INSERT INTO carriers
            (name,contact_name,phone,email,website,zones_covered,vehicle_types,
             cost_per_km,cost_per_kg,cost_fixed,rating,on_time_rate,archived,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,datetime('now'))
        """, (name,contact,phone,email,website,zones,vtypes,cpkm,cpkg,cfixed,rating,otr))
        ids.append(cur.lastrowid)
    conn.commit()
    return ids

def _gen_orders_casablanca(conn: sqlite3.Connection, client_ids: list,
                            vehicle_ids: list, driver_ids: list,
                            depot_ids: list, user_ids: list,
                            n: int = 200) -> list:
    if not _has_table(conn, "orders"):
        return []
    statuses = (
        ["pending"] * 50 + ["assigned"] * 20 +
        ["delivered"] * 20 + ["failed"] * 10
    )
    random.shuffle(statuses)
    statuses = (statuses * (n // 100 + 1))[:n]

    goods_cats = ["alimentaire","pharmaceutique","bureautique","electronique","textile","standard"]
    op_types   = ["delivery","delivery","delivery","delivery","pickup"]

    ids = []
    for i in range(n):
        ref    = f"ORD-2026-{i+1:06d}"
        cid    = RNG.choice(client_ids)
        status = statuses[i]
        sched  = _date_offset(-RNG.randint(0, 14))
        op     = RNG.choice(op_types)
        qty    = round(RNG.uniform(5, 200), 1)
        prio   = RNG.randint(1, 5)
        cat    = RNG.choice(goods_cats)
        tw_s   = f"{RNG.randint(6,14):02d}:00"
        tw_e   = f"{int(tw_s[:2])+4:02d}:00"

        veh_id = RNG.choice(vehicle_ids) if status in ("assigned","delivered","failed") else None
        drv_id = RNG.choice(driver_ids)  if (status in ("assigned","delivered","failed") and driver_ids) else None
        dep_id = RNG.choice(depot_ids)
        created_by = RNG.choice(user_ids) if user_ids else None

        actual_arr = _now_offset(days=RNG.randint(0,13)) if status == "delivered" else None
        failure    = RNG.choice(["client absent","adresse incorrecte","refus de livraison"]) if status == "failed" else None

        try:
            cur = conn.execute("""
                INSERT INTO orders
                (reference,client_id,vehicle_id,driver_id,depot_id,operation_type,
                 status,quantity_kg,units_count,goods_category,priority,
                 time_window_start,time_window_end,scheduled_date,
                 actual_arrival,failure_reason,visit_duration_minutes,
                 archived,created_at,updated_at,created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,datetime('now'),datetime('now'),?)
            """, (
                ref, cid, veh_id, drv_id, dep_id, op, status,
                qty, RNG.randint(1, 10), cat, prio,
                tw_s, tw_e, sched,
                actual_arr, failure, RNG.randint(10, 30),
                created_by,
            ))
            ids.append(cur.lastrowid)
        except Exception:
            pass

    # 15 commandes récurrentes
    for i in range(min(15, len(ids))):
        try:
            conn.execute("UPDATE orders SET is_recurring=1 WHERE id=?", (ids[i],))
        except Exception:
            pass

    conn.commit()
    return ids

def _gen_recurring_templates(conn: sqlite3.Connection, client_ids: list, n: int = 5):
    if not _has_table(conn, "recurring_order_templates"):
        return
    rec_types = ["weekly","monthly","daily"]
    for i in range(n):
        cid = RNG.choice(client_ids)
        try:
            conn.execute("""
                INSERT INTO recurring_order_templates
                (name,client_id,operation_type,quantity_kg,units_count,goods_category,
                 time_window_start,time_window_end,visit_duration_minutes,priority,
                 recurrence_type,recurrence_days,is_active,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,datetime('now'))
            """, (
                f"Gabarit récurrent #{i+1}",
                cid, "delivery",
                round(RNG.uniform(20, 150), 1),
                RNG.randint(1, 5), "alimentaire",
                "08:00","12:00", 20, RNG.randint(1,3),
                RNG.choice(rec_types),
                ",".join(str(d) for d in sorted(RNG.sample(range(5), k=RNG.randint(1, 3)))),
            ))
        except Exception:
            pass
    conn.commit()

def _gen_algo_results(conn: sqlite3.Connection, depot_ids: list,
                       n_days: int = 30) -> list:
    algos = [
        ("Glouton (Nearest Neighbor)", 320, 0.25, 5, 72),
        ("2-opt",                       270, 0.20, 8, 81),
        ("OR-Tools VRPTW",              220, 0.16, 45, 89),
    ]
    ids = []
    for day in range(n_days, -1, -1):
        for algo_name, base_dist, base_co2, base_cpu, base_rate in algos:
            n_runs = RNG.randint(1, 2)
            for _ in range(n_runs):
                dist    = base_dist * RNG.uniform(0.75, 1.35)
                co2     = dist * base_co2 * RNG.uniform(0.9, 1.1)
                cost    = dist * RNG.uniform(0.6, 0.9) + 50
                cpu     = base_cpu * RNG.uniform(0.5, 2.0) * 1000
                rate    = base_rate * RNG.uniform(0.85, 1.05)
                n_cli   = RNG.randint(8, 25)
                created = _now_offset(days=day, hours=RNG.randint(0, 8))
                try:
                    cur = conn.execute("""
                        INSERT INTO algo_results
                        (algorithm,client_count,vehicle_count,total_distance,total_duration,
                         total_cost,cpu_time_ms,respect_rate,distance_source,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        algo_name, n_cli, RNG.randint(2, 6),
                        round(dist, 2), round(dist / 45 * 60, 1),
                        round(cost, 2), round(cpu, 0),
                        round(min(rate, 100), 1),
                        "haversine", created,
                    ))
                    aid = cur.lastrowid
                    for col, val in [
                        ("co2_total", round(co2, 2)),
                        ("cost_total", round(cost, 2)),
                        ("on_time_rate", round(min(rate, 100), 1)),
                        ("vrp_mode", "standard"),
                        ("stops_count", n_cli),
                    ]:
                        try:
                            conn.execute(f"UPDATE algo_results SET {col}=? WHERE id=?", (val, aid))
                        except Exception:
                            pass
                    ids.append(aid)
                except Exception:
                    pass
    conn.commit()
    return ids

def _gen_routes_and_stops(conn: sqlite3.Connection,
                           algo_ids: list, vehicle_ids: list,
                           driver_ids: list, depot_ids: list,
                           order_ids: list, client_ids: list,
                           n_days: int = 30):
    if not _has_table(conn, "routes"):
        return
    delivered_orders = list(order_ids[:40]) if order_ids else []

    for day in range(n_days, -1, -1):
        date_str = _date_offset(day)
        n_routes = RNG.randint(4, 7)
        status_r = "completed" if day > 3 else ("planned" if day > 0 else "in_progress")

        for _ in range(n_routes):
            vid    = RNG.choice(vehicle_ids)
            did    = RNG.choice(driver_ids) if driver_ids else None
            dep_id = RNG.choice(depot_ids)
            aid    = RNG.choice(algo_ids) if algo_ids else None
            n_stops= RNG.randint(4, 9)
            dist   = round(RNG.uniform(40, 200), 2)
            dur    = round(dist / 50 * 60 + n_stops * 15, 0)
            cost   = round(dist * 0.7 + 50, 2)
            co2    = round(dist * 0.22, 2)

            try:
                cur = conn.execute("""
                    INSERT INTO routes
                    (algo_result_id,vehicle_id,driver_id,depot_start_id,depot_end_id,
                     planned_date,status,total_km,total_duration_min,total_cost,co2_kg,
                     stops_count,on_time_count,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
                """, (
                    aid, vid, did, dep_id, dep_id,
                    date_str, status_r,
                    dist, dur, cost, co2,
                    n_stops, int(n_stops * 0.85),
                ))
                route_id = cur.lastrowid

                # route_stops
                cum_dist = 0.0
                plan_min = 420  # start 07:00
                for stop_ord in range(1, n_stops + 1):
                    oid       = RNG.choice(delivered_orders) if delivered_orders else None
                    seg_dist  = round(RNG.uniform(2, 20), 2)
                    cum_dist += seg_dist
                    plan_min += int(seg_dist / 40 * 60) + 15
                    plan_arr  = f"{date_str} {plan_min//60:02d}:{plan_min%60:02d}:00"
                    plan_dep  = f"{date_str} {(plan_min+15)//60:02d}:{(plan_min+15)%60:02d}:00"
                    sts       = "completed" if status_r == "completed" else "pending"

                    try:
                        conn.execute("""
                            INSERT INTO route_stops
                            (route_id,order_id,stop_type,stop_order,planned_arrival,
                             planned_departure,actual_arrival,actual_departure,
                             duration_min,distance_from_prev_km,status)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            route_id, oid, "delivery", stop_ord,
                            plan_arr, plan_dep,
                            plan_arr if sts == "completed" else None,
                            plan_dep if sts == "completed" else None,
                            15, seg_dist, sts,
                        ))
                    except Exception:
                        pass
            except Exception:
                pass
    conn.commit()

def _gen_carrier_shipments(conn: sqlite3.Connection,
                            carrier_ids: list, order_ids: list, n: int = 20):
    if not _has_table(conn, "carrier_shipments") or not carrier_ids:
        return
    for i in range(n):
        oid   = RNG.choice(order_ids) if order_ids else None
        cid   = RNG.choice(carrier_ids)
        track = f"{''.join(RNG.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))}"
        status = RNG.choice(["pending","in_transit","delivered","failed"])
        est   = _date_offset(-RNG.randint(-7, 7))
        actual= _date_offset(-RNG.randint(0, 3)) if status == "delivered" else None
        cost  = round(RNG.uniform(15, 120), 2)
        try:
            conn.execute("""
                INSERT INTO carrier_shipments
                (carrier_id,order_id,tracking_number,status,estimated_delivery,
                 actual_delivery,cost,created_at)
                VALUES (?,?,?,?,?,?,?,datetime('now'))
            """, (cid, oid, track, status, est, actual, cost))
        except Exception:
            pass
    conn.commit()

def _gen_zones_casablanca(conn: sqlite3.Connection):
    if not _has_table(conn, "zones"):
        return
    zones = [
        ("ZFE Centre-Ville", "zfe",      33.596, -7.619, 0.012, 0.015, "#FF6B6B",
         "Zone à Faibles Émissions — Centre historique de Casablanca"),
        ("Zone Livraison Anfa",  "delivery", 33.593, -7.666, 0.018, 0.020, "#4ECDC4",
         "Zone de livraison prioritaire Anfa / Ain Diab"),
        ("Zone Livraison Sidi Maarouf","delivery",33.551,-7.641,0.020,0.022,"#45B7D1",
         "Zone industrielle Sidi Maarouf"),
        ("Zone Exclusion Port",  "exclusion",33.602,-7.614,0.010,0.012,"#FF4757",
         "Zone portuaire — accès restreint"),
        ("Zone Livraison CFC",   "delivery", 33.608, -7.573, 0.015, 0.015, "#96CEB4",
         "Casablanca Finance City — livraisons de bureau"),
    ]
    for name, ztype, lat, lon, rlat, rlon, color, desc in zones:
        try:
            conn.execute("""
                INSERT INTO zones (name,zone_type,geojson,color,description,is_active,created_at)
                VALUES (?,?,?,?,?,1,datetime('now'))
            """, (name, ztype, _box_geojson(lat, lon, rlat, rlon), color, desc))
        except Exception:
            pass
    conn.commit()

def _gen_notifications(conn: sqlite3.Connection, user_ids: list, n: int = 20):
    notif_templates = [
        ("warning","critical","Assurance véhicule expirant",
         "L'assurance du véhicule MA-12345-A expire dans 15 jours","vehicles",1),
        ("warning","warning","CT véhicule à renouveler",
         "Contrôle technique du MA-23456-B dû dans 30 jours","vehicles",2),
        ("info","info","Nouveau client ajouté",
         "Un nouveau client a été ajouté : Marjane Anfa","clients",1),
        ("order","info","Commande ORD-2026-000042 livrée",
         "La commande a été livrée avec succès","orders",42),
        ("order","warning","Commande ORD-2026-000077 échouée",
         "Livraison échouée : client absent","orders",77),
        ("route","info","Tournée planifiée",
         "5 nouvelles tournées planifiées pour demain","routes",1),
        ("system","info","Synchronisation terminée",
         "Données synchronisées avec le serveur web","logs",1),
        ("warning","warning","Anomalie détectée",
         "Distance anormale détectée dans la tournée #12","anomalies",1),
        ("order","info","10 nouvelles commandes",
         "10 commandes reçues depuis le portail web","orders",50),
        ("driver","warning","Chauffeur indisponible",
         "Omar Benali est absent demain","drivers",1),
    ]
    for i in range(n):
        t = notif_templates[i % len(notif_templates)]
        uid = RNG.choice(user_ids) if user_ids else None
        created = _now_offset(days=RNG.randint(0, 7), hours=RNG.randint(0, 23))
        try:
            cur = conn.execute("""
                INSERT INTO notifications
                (type,title,message,is_read,created_at)
                VALUES (?,?,?,0,?)
            """, (t[0], t[2], t[3], created))
            nid = cur.lastrowid
            for col, val in [
                ("severity", t[1]), ("related_table", t[4]),
                ("related_id", t[5]), ("user_id", uid),
            ]:
                try:
                    conn.execute(f"UPDATE notifications SET {col}=? WHERE id=?", (val, nid))
                except Exception:
                    pass
        except Exception:
            pass
    conn.commit()

def _gen_scenarios(conn: sqlite3.Connection):
    scenarios = [
        {
            "name": "Scénario Centre-Ville Casablanca",
            "description": "Optimisation des livraisons dans le périmètre centre",
            "algorithm": "OR-Tools VRPTW",
            "n_clients": 30, "n_vehicles": 4,
        },
        {
            "name": "Scénario Périphérie Casablanca",
            "description": "Livraisons zones industrielles et résidentielles",
            "algorithm": "2-opt",
            "n_clients": 50, "n_vehicles": 6,
        },
        {
            "name": "Scénario Complet 80 clients",
            "description": "Plan journalier complet avec toutes les contraintes",
            "algorithm": "OR-Tools VRPTW",
            "n_clients": 80, "n_vehicles": 8,
        },
    ]
    for s in scenarios:
        cfg = json.dumps({
            "algorithm": s["algorithm"],
            "time_limit": 30,
            "use_clustering": True,
        })
        try:
            conn.execute("""
                INSERT INTO scenarios
                (name,description,client_count,vehicle_count,algorithm,data_json,created_at)
                VALUES (?,?,?,?,?,?,datetime('now'))
            """, (
                s["name"], s["description"],
                s["n_clients"], s["n_vehicles"],
                s["algorithm"], cfg,
            ))
        except Exception:
            pass
    conn.commit()

def _gen_logs(conn: sqlite3.Connection, user_ids: list, n: int = 150):
    for i in range(n):
        action  = RNG.choice(_LOG_ACTIONS)
        uid     = RNG.choice(user_ids) if user_ids else None
        created = _now_offset(days=RNG.randint(0, 30), hours=RNG.randint(0, 23))
        details = f"Action {action} #{RNG.randint(1,100)} — opération réussie"
        try:
            conn.execute(
                "INSERT INTO logs (level,user_id,action,details,created_at) VALUES (?,?,?,?,?)",
                ("INFO", uid, action, details, created)
            )
        except Exception:
            pass
    conn.commit()

def _gen_ai_conversations(conn: sqlite3.Connection, user_ids: list):
    if not _has_table(conn, "ai_conversations"):
        return
    convs = [
        [
            {"role":"user","content":"Analyse mes tournées de la semaine dernière."},
            {"role":"assistant","content":"Analyse complète : la tournée du lundi était la plus efficace avec 87% de respect des créneaux et 210 km parcourus pour 12 livraisons."},
            {"role":"user","content":"Comment réduire les coûts de 10% ?"},
            {"role":"assistant","content":"Recommandations : 1) Regrouper les clients Anfa le mardi, 2) Utiliser le vélo cargo pour les petites livraisons CFC, 3) Démarrer les tournées à 6h30 pour éviter les bouchons."},
        ],
        [
            {"role":"user","content":"Quels clients ont des retards récurrents ?"},
            {"role":"assistant","content":"3 clients présentent des retards systématiques : Pharmacie Centrale (créneaux trop serrés), Restaurant Al Mounia (accès difficile), Bureau CFC (pas de place de livraison)."},
        ],
    ]
    for i, msgs in enumerate(convs):
        uid = RNG.choice(user_ids) if user_ids else None
        try:
            conn.execute("""
                INSERT INTO ai_conversations
                (user_id,messages_json,context_json,created_at,updated_at)
                VALUES (?,?,?,datetime('now'),datetime('now'))
            """, (uid, json.dumps(msgs), json.dumps({"city": "Casablanca"})))
        except Exception:
            pass
    conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# DATASET CASABLANCA
# ═══════════════════════════════════════════════════════════════════════════════

def generate_casablanca(conn: sqlite3.Connection, cb=None) -> dict:
    total = 15
    def p(msg, s): progress(msg, s, total, cb)

    p("Utilisateurs (3)",          1);  user_ids     = _gen_users_casablanca(conn)
    p("Dépôts (3)",                2);  depot_ids    = _gen_depots_casablanca(conn)
    p("Véhicules (8)",             3);  vehicle_ids  = _gen_vehicles_casablanca(conn, depot_ids)
    p("Chauffeurs (8)",            4);  driver_ids   = _gen_drivers_casablanca(conn, depot_ids, vehicle_ids)
    p("Équipes (2)",               5);  _gen_teams_casablanca(conn, driver_ids)
    p("Clients (80)",              6);  client_ids   = _gen_clients_casablanca(conn)
    p("Transporteurs (3)",         7);  carrier_ids  = _gen_carriers_casablanca(conn)
    p("Historique algo (30j)",     8);  algo_ids     = _gen_algo_results(conn, depot_ids, 30)
    p("Commandes (200)",           9);  order_ids    = _gen_orders_casablanca(
                                            conn, client_ids, vehicle_ids,
                                            driver_ids, depot_ids, user_ids)
    p("Gabarits récurrents (5)",   10); _gen_recurring_templates(conn, client_ids)
    p("Routes + arrêts (30j)",     11); _gen_routes_and_stops(
                                            conn, algo_ids, vehicle_ids,
                                            driver_ids, depot_ids, order_ids, client_ids)
    p("Expéditions transporteurs (20)",12); _gen_carrier_shipments(conn, carrier_ids, order_ids)
    p("Zones GeoJSON (5)",         13); _gen_zones_casablanca(conn)
    p("Notifications (20)",        14); _gen_notifications(conn, user_ids)
    p("Scénarios + logs + IA",     15)
    _gen_scenarios(conn)
    _gen_logs(conn, user_ids)
    _gen_ai_conversations(conn, user_ids)

    return {
        "depot_ids": depot_ids, "vehicle_ids": vehicle_ids,
        "driver_ids": driver_ids, "client_ids": client_ids,
        "order_ids": order_ids, "algo_ids": algo_ids,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# DATASET PARIS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_paris(conn: sqlite3.Connection, cb=None) -> dict:
    progress("Dépôts Paris (2)", 1, 6, cb)
    paris_depots = [
        ("Dépôt Rungis","MIN de Rungis, 94150 Rungis",48.7474,2.3539,"05:00","22:00",8000),
        ("Dépôt Gennevilliers","Av. du Marché, 92230 Gennevilliers",48.9208,2.3012,"06:00","20:00",4000),
    ]
    dep_ids = []
    for name,addr,lat,lon,op,cl,cap in paris_depots:
        cur = conn.execute(
            "INSERT INTO depots (name,address,latitude,longitude,opening_time,closing_time,"
            "storage_capacity,created_at) VALUES (?,?,?,?,?,?,?,datetime('now'))",
            (name,addr,lat,lon,op,cl,cap))
        dep_ids.append(cur.lastrowid)

    progress("Véhicules Paris (5)", 2, 6, cb)
    veh_ids = []
    for i in range(5):
        cur = conn.execute(
            "INSERT INTO vehicles (registration,type,capacity_kg,capacity_m3,max_speed_kmh,"
            "cost_per_km,depot_id,status,created_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
            (_plate_fr(),"fourgon",400,6.0,90,0.70,
             dep_ids[i%2],"disponible"))
        veh_ids.append(cur.lastrowid)

    progress("Clients Paris (50)", 3, 6, cb)
    paris_areas = [
        (48.8566,2.3522,0.08),(48.8738,2.2950,0.06),(48.8323,2.3317,0.05),
        (48.8800,2.3390,0.05),(48.8603,2.3477,0.04),
    ]
    cli_ids = []
    for i in range(50):
        ac = paris_areas[i % len(paris_areas)]
        lat,lon = _rnd_coord(ac[0],ac[1],ac[2])
        cur = conn.execute(
            "INSERT INTO clients (cust_no,name,address,latitude,longitude,demand_kg,"
            "ready_time,due_time,service_time,priority,client_type,archived,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,0,datetime('now'))",
            (i+1,f"Client Paris {i+1}",f"Rue de Paris {i+1}, Paris",
             lat,lon,round(RNG.uniform(10,150),1),
             480,1020,RNG.randint(10,25),RNG.randint(1,4),"bureau"))
        cli_ids.append(cur.lastrowid)

    progress("Commandes Paris (80)", 4, 6, cb)
    algo_ids = _gen_algo_results(conn, dep_ids, 14)
    ord_ids  = []
    if _has_table(conn, "orders"):
        statuses_p = (["pending"]*40+["delivered"]*24+["assigned"]*16)[:80]
        for i in range(80):
            ref = f"PAR-2026-{i+1:05d}"
            try:
                cur = conn.execute(
                    "INSERT INTO orders (reference,client_id,depot_id,status,quantity_kg,"
                    "scheduled_date,archived,created_at,updated_at)"
                    " VALUES (?,?,?,?,?,?,0,datetime('now'),datetime('now'))",
                    (ref,RNG.choice(cli_ids),RNG.choice(dep_ids),
                     statuses_p[i],round(RNG.uniform(5,100),1),
                     _date_offset(-RNG.randint(0,7))))
                ord_ids.append(cur.lastrowid)
            except Exception:
                pass

    progress("Logs Paris", 5, 6, cb)
    user_ids = [r[0] for r in conn.execute("SELECT id FROM users LIMIT 3").fetchall()]
    _gen_logs(conn, user_ids, n=40)

    progress("Paris terminé", 6, 6, cb)
    conn.commit()
    return {"depot_ids": dep_ids, "vehicle_ids": veh_ids, "client_ids": cli_ids}

# ═══════════════════════════════════════════════════════════════════════════════
# DATASET BENCHMARK (500 clients, 20 véhicules, 1 dépôt, sans créneaux)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_benchmark(conn: sqlite3.Connection, cb=None) -> dict:
    progress("Dépôt benchmark", 1, 4, cb)
    cur = conn.execute(
        "INSERT INTO depots (name,address,latitude,longitude,opening_time,closing_time,"
        "created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("Dépôt Benchmark","Zone industrielle benchmark",33.5731,-7.5898,"00:00","23:59"))
    dep_id = cur.lastrowid

    progress("Véhicules benchmark (20)", 2, 4, cb)
    veh_ids = []
    for i in range(20):
        cur = conn.execute(
            "INSERT INTO vehicles (registration,type,capacity_kg,capacity_m3,max_speed_kmh,"
            "cost_per_km,depot_id,status,created_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
            (f"BM-{i+1:03d}","fourgon",500,8.0,90,0.65,dep_id,"disponible"))
        veh_ids.append(cur.lastrowid)

    progress("Clients benchmark (500)", 3, 4, cb)
    cli_ids = []
    for i in range(500):
        lat, lon = _rnd_coord(33.5731, -7.5898, 0.35)
        cur = conn.execute(
            "INSERT INTO clients (cust_no,name,address,latitude,longitude,demand_kg,"
            "ready_time,due_time,service_time,priority,client_type,archived,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,0,datetime('now'))",
            (i+1,f"BM Client {i+1}",f"Adresse {i+1}",lat,lon,
             round(RNG.uniform(10,200),1),0,1440,10,3,"standard"))
        cli_ids.append(cur.lastrowid)

    progress("Algo results benchmark", 4, 4, cb)
    _gen_algo_results(conn, [dep_id], 7)
    conn.commit()
    return {"depot_ids": [dep_id], "vehicle_ids": veh_ids, "client_ids": cli_ids}

# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT CSV / EXCEL
# ═══════════════════════════════════════════════════════════════════════════════

def export_to_csv(conn: sqlite3.Connection, export_dir: str):
    Path(export_dir).mkdir(parents=True, exist_ok=True)
    tables = [
        "clients","vehicles","depots","drivers","teams","team_members",
        "orders","routes","route_stops","carriers","carrier_shipments",
        "zones","notifications","scenarios","algo_results","logs",
    ]
    for t in tables:
        try:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            if not rows:
                continue
            fpath = os.path.join(export_dir, f"{t}.csv")
            with open(fpath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([d[0] for d in conn.execute(f"SELECT * FROM {t}").description or []])
                writer.writerows([list(r) for r in rows])
            print(f"  → {t}.csv ({len(rows)} lignes)")
        except Exception as e:
            print(f"  ✗ {t}: {e}")

    # Excel si openpyxl disponible
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for t in tables:
            try:
                rows = conn.execute(f"SELECT * FROM {t} LIMIT 5000").fetchall()
                if not rows:
                    continue
                ws = wb.create_sheet(t[:31])
                cols = [d[0] for d in conn.execute(f"SELECT * FROM {t} LIMIT 1").description or []]
                ws.append(cols)
                for r in rows:
                    ws.append(list(r))
            except Exception:
                pass
        xlsx_path = os.path.join(export_dir, "demo_data_citypulse.xlsx")
        wb.save(xlsx_path)
        print(f"  → demo_data_citypulse.xlsx")
    except ImportError:
        print("  (openpyxl non disponible — Excel ignoré)")

# ═══════════════════════════════════════════════════════════════════════════════
# CLI PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Générateur de données de démo CityPulse Logistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dataset",
        choices=["casablanca","paris","benchmark","all"],
        default="casablanca", help="Dataset à générer (défaut: casablanca)")
    parser.add_argument("--db",
        default="citypulse.db", help="Chemin vers la base SQLite (défaut: citypulse.db)")
    parser.add_argument("--reset", action="store_true",
        help="Vider les tables avant insertion")
    parser.add_argument("--append", action="store_true",
        help="Ajouter aux données existantes sans vider")
    parser.add_argument("--export", metavar="DIR",
        help="Dossier d'export CSV/Excel")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  CityPulse Logistics -- Generateur de demo")
    print(f"  Dataset : {args.dataset.upper()}  |  DB : {db_path}")
    print(f"{sep}\n")

    # 1. Migrations
    print("[*] Application des migrations...")
    try:
        _apply_migrations(db_path)
        print("    OK - Migrations appliquees")
    except Exception as e:
        print(f"    ERREUR migrations : {e}")
        sys.exit(1)

    conn = _open_db(db_path)

    # 2. Reset si demandé
    if args.reset:
        print("[!] Reinitialisation des tables...")
        _reset_tables(conn, keep_users=False)

    # 3. Génération
    datasets = ["casablanca","paris","benchmark"] if args.dataset == "all" else [args.dataset]

    for ds in datasets:
        print(f"\n[>] Generation dataset : {ds.upper()}")
        if ds == "casablanca":
            generate_casablanca(conn)
        elif ds == "paris":
            generate_paris(conn)
        elif ds == "benchmark":
            generate_benchmark(conn)

    # 4. Export
    if args.export:
        print(f"\n[F] Export vers {args.export}...")
        export_to_csv(conn, args.export)

    conn.close()

    # Résumé
    conn2 = _open_db(db_path)
    print("\n[=] Resume final :")
    summary_tables = ["clients","vehicles","drivers","orders","routes",
                      "algo_results","notifications","logs"]
    for t in summary_tables:
        try:
            n = conn2.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:<22} {n:>5} lignes")
        except Exception:
            pass
    conn2.close()
    print("\n[OK] Termine.\n")


if __name__ == "__main__":
    main()
