"""
db_manager.py — Gestionnaire SQLite de CityPulse Logistics
===========================================================
Système de migrations versionné : schema_version (id, version, applied_at, description)
Chaque migration = fonction migrate_XXX(conn) numérotée 001 à 021.
run_migrations() applique automatiquement les migrations manquantes dans l'ordre.
"""

import sqlite3
import os
import hashlib
import secrets
import logging
import json
from contextlib import contextmanager
from datetime import datetime, timedelta

from ..paths import project_root

logger_db = logging.getLogger("citypulse.db")


class _Row(sqlite3.Row):
  """sqlite3.Row étendu avec .get() pour compatibilité dict."""
  def get(self, key, default=None):
    try:
      return self[key]
    except IndexError:
      return default

DB_PATH = os.path.join(project_root(), "citypulse.db")

# ── Permissions par rôle ───────────────────────────────────────────────────────
_ROLE_PERMISSIONS = {
  "admin":     {"*": ["*"]},
  "administrateur": {"*": ["*"]},  # alias legacy
  "planner": {
    "clients":   ["read", "write"],
    "vehicles":   ["read", "write"],
    "depots":    ["read", "write"],
    "orders":    ["read", "write"],
    "routes":    ["read", "write"],
    "drivers":   ["read", "write"],
    "optimization": ["read", "write"],
    "reports":   ["read", "write"],
    "scenarios":  ["read", "write"],
    "translation": ["read", "write"],
    "settings":   ["read"],
    "logs":     ["read"],
    "users":    [],
  },
  "gestionnaire": {  # alias legacy
    "clients":   ["read", "write"],
    "vehicles":   ["read", "write"],
    "depots":    ["read", "write"],
    "orders":    ["read", "write"],
    "routes":    ["read", "write"],
    "drivers":   ["read", "write"],
    "optimization": ["read", "write"],
    "reports":   ["read", "write"],
  },
  "dispatcher": {
    "clients":   ["read"],
    "vehicles":   ["read"],
    "depots":    ["read"],
    "orders":    ["read", "status_update"],
    "routes":    ["read", "status_update"],
    "drivers":   ["read"],
    "optimization": ["read"],
    "reports":   ["read"],
    "settings":   ["read"],
    "logs":     ["read"],
  },
  "viewer": {"*": ["read"]},
}


# ══════════════════════════════════════════════════════════════════════════════
# CONNEXION
# ══════════════════════════════════════════════════════════════════════════════

def get_connection(db_path=None):
  path = db_path or DB_PATH
  conn = sqlite3.connect(path)
  conn.row_factory = _Row
  conn.execute("PRAGMA journal_mode=WAL")
  conn.execute("PRAGMA foreign_keys=ON")
  return conn


@contextmanager
def db_connection(db_path=None):
  """Context manager — commit auto, rollback sur exception, fermeture garantie."""
  conn = get_connection(db_path)
  try:
    yield conn
    conn.commit()
  except Exception:
    conn.rollback()
    logger_db.exception("Erreur SQLite — rollback effectué")
    raise
  finally:
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS MIGRATION
# ══════════════════════════════════════════════════════════════════════════════

def _add_column_safe(conn, table: str, column: str, definition: str) -> bool:
  """Ajoute une colonne si elle n'existe pas. Retourne True si ajoutée."""
  try:
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    return True
  except Exception as e:
    msg = str(e).lower()
    if "duplicate column" in msg or "already exists" in msg:
      return False
    raise


def _ensure_schema_version_table(conn):
  conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
      id     INTEGER PRIMARY KEY AUTOINCREMENT,
      version   INTEGER NOT NULL UNIQUE,
      applied_at TEXT  DEFAULT (datetime('now')),
      description TEXT
    )
  """)
  conn.commit()


def _get_current_version(conn) -> int:
  """
  Lit la version courante depuis schema_version (nouveau) ou schema_migrations (legacy).
  Permet la transition transparente des BDD existantes.
  """
  _ensure_schema_version_table(conn)
  try:
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    v = row[0] if row and row[0] is not None else 0
    if v > 0:
      return v
  except Exception:
    pass
  try:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return row[0] if row and row[0] is not None else 0
  except Exception:
    return 0


def _mark_applied(conn, version: int, description: str = ""):
  conn.execute(
    "INSERT OR IGNORE INTO schema_version (version, description) VALUES (?,?)",
    (version, description)
  )
  conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# INITIALISATION — tables de base (créées au premier lancement)
# ══════════════════════════════════════════════════════════════════════════════

def init_database(db_path=None):
  """Crée les tables de base si elles n'existent pas, puis insère les données par défaut."""
  conn = get_connection(db_path)
  c = conn.cursor()

  c.execute("""CREATE TABLE IF NOT EXISTS users (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    salt       TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'gestionnaire',
    full_name    TEXT,
    email      TEXT,
    avatar_path   TEXT,
    language     TEXT DEFAULT 'fr',
    theme      TEXT DEFAULT 'dark',
    failed_attempts INTEGER DEFAULT 0,
    locked_until   TEXT,
    last_login    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS depots (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    address     TEXT,
    latitude     REAL NOT NULL,
    longitude    REAL NOT NULL,
    opening_time   TEXT DEFAULT '08:00',
    closing_time   TEXT DEFAULT '18:00',
    storage_capacity REAL,
    created_at    TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS clients (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cust_no   INTEGER,
    name     TEXT NOT NULL,
    address   TEXT,
    latitude   REAL NOT NULL,
    longitude  REAL NOT NULL,
    demand_kg  REAL DEFAULT 0,
    demand_m3  REAL DEFAULT 0,
    ready_time  INTEGER DEFAULT 0,
    due_time   INTEGER DEFAULT 1440,
    service_time INTEGER DEFAULT 10,
    priority   INTEGER DEFAULT 3,
    client_type TEXT DEFAULT 'standard',
    contact   TEXT,
    phone    TEXT,
    email    TEXT,
    instructions TEXT,
    archived   INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS vehicles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    registration       TEXT UNIQUE,
    type           TEXT DEFAULT 'fourgon',
    capacity_kg       REAL DEFAULT 1000,
    capacity_m3       REAL DEFAULT 10,
    max_speed_kmh      REAL DEFAULT 60,
    cost_per_km       REAL DEFAULT 0.5,
    depot_id         INTEGER,
    status          TEXT DEFAULT 'disponible',
    driver_name       TEXT,
    total_km         REAL DEFAULT 0,
    maintenance_km_threshold REAL DEFAULT 10000,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (depot_id) REFERENCES depots(id)
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS scenarios (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    description  TEXT,
    client_count INTEGER,
    vehicle_count INTEGER,
    traffic_coeff REAL DEFAULT 1.0,
    weather_coeff REAL DEFAULT 1.0,
    algorithm   TEXT,
    data_json   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS tournees (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id     INTEGER,
    vehicle_id     INTEGER,
    algorithm      TEXT NOT NULL,
    total_distance_km  REAL,
    total_duration_min REAL,
    total_cost     REAL,
    clients_served   INTEGER,
    respect_rate    REAL,
    avg_delay_min    REAL,
    cpu_time_ms     REAL,
    traffic_coeff    REAL DEFAULT 1.0,
    weather_coeff    REAL DEFAULT 1.0,
    route_json     TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS arrets (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    tournee_id  INTEGER NOT NULL,
    client_id  INTEGER,
    visit_order INTEGER NOT NULL,
    arrival_time REAL,
    departure_time REAL,
    delay_min  REAL DEFAULT 0,
    status    TEXT DEFAULT 'planifie',
    FOREIGN KEY (tournee_id) REFERENCES tournees(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS algo_results (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    algorithm     TEXT NOT NULL,
    client_count   INTEGER,
    vehicle_count   INTEGER,
    total_distance  REAL,
    total_duration  REAL,
    total_cost    REAL,
    cpu_time_ms    REAL,
    respect_rate   REAL,
    avg_delay     REAL,
    gain_vs_greedy  REAL,
    fleet_utilization REAL,
    traffic_coeff   REAL DEFAULT 1.0,
    weather_coeff   REAL DEFAULT 1.0,
    details_json   TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS translation_history (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_lang   TEXT NOT NULL,
    target_lang   TEXT NOT NULL,
    source_text   TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    quality_score  REAL,
    validated    INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS logs (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    level   TEXT NOT NULL DEFAULT 'INFO',
    user_id  INTEGER,
    action   TEXT NOT NULL,
    details  TEXT,
    created_at TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS notifications (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    type    TEXT NOT NULL,
    title   TEXT NOT NULL,
    message  TEXT,
    is_read  INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS anomalies (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    tournee_id  INTEGER,
    anomaly_type TEXT NOT NULL,
    description TEXT,
    severity   TEXT DEFAULT 'warning',
    created_at  TEXT DEFAULT (datetime('now'))
  )""")

  c.execute("""CREATE TABLE IF NOT EXISTS user_sessions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL UNIQUE,
    last_page_index INTEGER DEFAULT 0,
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  )""")

  # Utilisateur admin par défaut
  c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
  if c.fetchone()[0] == 0:
    salt  = secrets.token_hex(16)
    pw_hash = hashlib.sha256(("admin" + salt).encode()).hexdigest()
    c.execute(
      "INSERT INTO users (username, password_hash, salt, role, full_name) VALUES (?,?,?,?,?)",
      ("admin", pw_hash, salt, "admin", "Administrateur")
    )

  # Dépôt Casablanca par défaut
  c.execute("SELECT COUNT(*) FROM depots")
  if c.fetchone()[0] == 0:
    c.execute(
      "INSERT INTO depots (name, address, latitude, longitude) VALUES (?,?,?,?)",
      ("Dépôt Casablanca", "Casablanca, Maroc", 33.5731, -7.5898)
    )

  conn.commit()
  conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# MIGRATIONS 001 → 021
# ══════════════════════════════════════════════════════════════════════════════

def migrate_001(conn):
  """Cache OSRM des matrices de distances."""
  conn.execute("""CREATE TABLE IF NOT EXISTS distance_cache (
    cache_key TEXT PRIMARY KEY,
    dist_json TEXT NOT NULL,
    time_json TEXT NOT NULL,
    source   TEXT DEFAULT 'osrm',
    created_at TEXT DEFAULT (datetime('now'))
  )""")


def migrate_002(conn):
  """Glossaire de traduction utilisateur (prioritaire sur l'API)."""
  conn.execute("""CREATE TABLE IF NOT EXISTS translation_glossary (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    src_lang    TEXT NOT NULL,
    tgt_lang    TEXT NOT NULL,
    source_term  TEXT NOT NULL,
    corrected_term TEXT NOT NULL,
    use_count   INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(src_lang, tgt_lang, source_term)
  )""")


def migrate_003(conn):
  """Source de la matrice de distances dans algo_results."""
  _add_column_safe(conn, "algo_results", "distance_source", "TEXT DEFAULT 'haversine'")


def migrate_004(conn):
  """Colonnes étendues — clients."""
  cols = [
    ("company_name",       "TEXT"),
    ("contact_phone",      "TEXT"),
    ("contact_email",      "TEXT"),
    ("access_code",       "TEXT"),
    ("notes",          "TEXT"),
    ("photo_url",        "TEXT"),
    ("service_duration_minutes", "INTEGER DEFAULT 15"),
    ("preferred_driver_id",   "INTEGER"),
    ("vehicle_requirement",   "TEXT"),
    ("tags",           "TEXT"),
    ("punctuality_factor",    "REAL DEFAULT 1.0"),
    ("delay_penalty_per_hour",  "REAL DEFAULT 0.0"),
    ("is_recurring",       "INTEGER DEFAULT 0"),
    ("recurrence_pattern",    "TEXT"),
    ("website_client_id",    "TEXT"),
    ("adr_class",        "TEXT"),
    ("time_window2_start",    "TEXT"),
    ("time_window2_end",     "TEXT"),
  ]
  for col, defn in cols:
    _add_column_safe(conn, "clients", col, defn)


def migrate_005(conn):
  """Colonnes étendues — vehicles (caractéristiques complètes + conformité)."""
  cols = [
    ("registration_plate",      "TEXT"),
    ("brand",             "TEXT"),
    ("model",             "TEXT"),
    ("year",             "INTEGER"),
    ("vehicle_type",         "TEXT DEFAULT 'van'"),
    ("fuel_type",           "TEXT DEFAULT 'diesel'"),
    ("co2_per_km",          "REAL DEFAULT 0.21"),
    ("max_height_cm",         "INTEGER"),
    ("max_width_cm",         "INTEGER"),
    ("max_length_cm",         "INTEGER"),
    ("max_weight_kg",         "REAL"),
    ("insurance_expiry",       "TEXT"),
    ("technical_inspection_expiry",  "TEXT"),
    ("insurance_number",       "TEXT"),
    ("allowed_adr",          "INTEGER DEFAULT 0"),
    ("allowed_zfe",          "INTEGER DEFAULT 1"),
    ("daily_km_limit",        "REAL"),
    ("open_start",          "INTEGER DEFAULT 0"),
    ("open_stop",           "INTEGER DEFAULT 0"),
    ("reload_allowed",        "INTEGER DEFAULT 1"),
    ("cost_per_hour",         "REAL DEFAULT 15.0"),
    ("cost_fixed_daily",       "REAL DEFAULT 50.0"),
    ("speed_highway",         "REAL DEFAULT 110"),
    ("speed_national",        "REAL DEFAULT 80"),
    ("speed_urban",          "REAL DEFAULT 45"),
    ("speed_zone30",         "REAL DEFAULT 25"),
    ("photo_url",           "TEXT"),
  ]
  for col, defn in cols:
    _add_column_safe(conn, "vehicles", col, defn)


def migrate_006(conn):
  """Colonnes étendues — depots (infos opérationnelles)."""
  cols = [
    ("manager_name",       "TEXT"),
    ("phone",           "TEXT"),
    ("open_time",         "TEXT DEFAULT '06:00'"),
    ("close_time",        "TEXT DEFAULT '20:00'"),
    ("max_vehicles",       "INTEGER DEFAULT 50"),
    ("loading_bays",       "INTEGER DEFAULT 4"),
    ("loading_time_minutes",   "INTEGER DEFAULT 30"),
    ("unloading_time_per_kg",   "REAL DEFAULT 0.001"),
    ("notes",           "TEXT"),
    ("photo_url",         "TEXT"),
    ("is_cross_dock",       "INTEGER DEFAULT 0"),
  ]
  for col, defn in cols:
    _add_column_safe(conn, "depots", col, defn)


def migrate_007(conn):
  """Colonnes étendues — algo_results (CO2, véhicules utilisés, scénario)."""
  cols = [
    ("co2_total",     "REAL"),
    ("cost_total",     "REAL"),
    ("vehicles_used",   "INTEGER"),
    ("stops_count",    "INTEGER"),
    ("on_time_rate",    "REAL"),
    ("scenario_name",   "TEXT"),
    ("created_by",     "INTEGER"),
    ("objective_weights", "TEXT"),
    ("vrp_mode",      "TEXT DEFAULT 'standard'"),
  ]
  for col, defn in cols:
    _add_column_safe(conn, "algo_results", col, defn)


def migrate_008(conn):
  """Colonnes étendues — users (phone, permissions, is_active, website_user_id)."""
  cols = [
    ("phone",      "TEXT"),
    ("permissions",   "TEXT"),
    ("is_active",    "INTEGER DEFAULT 1"),
    ("website_user_id", "TEXT"),
  ]
  for col, defn in cols:
    _add_column_safe(conn, "users", col, defn)


def migrate_009(conn):
  """Table drivers — chauffeurs avec contraintes légales et planning."""
  conn.execute("""CREATE TABLE IF NOT EXISTS drivers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name         TEXT NOT NULL,
    last_name          TEXT NOT NULL,
    company_name        TEXT,
    phone            TEXT,
    email            TEXT,
    photo_url          TEXT,
    license_number       TEXT,
    license_category      TEXT,
    license_expiry       TEXT,
    qualifications       TEXT,
    contract_type        TEXT DEFAULT 'CDI',
    work_start_time       TEXT DEFAULT '07:00',
    work_end_time        TEXT DEFAULT '17:00',
    lunch_time         TEXT DEFAULT '12:00',
    lunch_duration_minutes   INTEGER DEFAULT 60,
    max_daily_hours       REAL DEFAULT 10.0,
    overtime_level1_hours    REAL DEFAULT 1.0,
    overtime_level1_rate    REAL DEFAULT 1.25,
    overtime_level2_hours    REAL DEFAULT 2.0,
    overtime_level2_rate    REAL DEFAULT 1.5,
    max_drive_before_break_min INTEGER DEFAULT 270,
    min_break_minutes      INTEGER DEFAULT 45,
    min_daily_rest_minutes   INTEGER DEFAULT 660,
    home_depot_id        INTEGER,
    vehicle_id         INTEGER,
    zone_assignment       TEXT,
    notes            TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    archived          INTEGER DEFAULT 0,
    FOREIGN KEY (home_depot_id) REFERENCES depots(id),
    FOREIGN KEY (vehicle_id)  REFERENCES vehicles(id)
  )""")


def migrate_010(conn):
  """Table driver_unavailabilities — absences et indisponibilités chauffeurs."""
  conn.execute("""CREATE TABLE IF NOT EXISTS driver_unavailabilities (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id INTEGER NOT NULL,
    date    TEXT NOT NULL,
    reason   TEXT,
    notes   TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (driver_id) REFERENCES drivers(id)
  )""")


def migrate_011(conn):
  """Tables teams et team_members — équipes de chauffeurs."""
  conn.execute("""CREATE TABLE IF NOT EXISTS teams (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    manager_driver_id INTEGER,
    description    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    archived     INTEGER DEFAULT 0,
    FOREIGN KEY (manager_driver_id) REFERENCES drivers(id)
  )""")
  conn.execute("""CREATE TABLE IF NOT EXISTS team_members (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id  INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    joined_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (team_id)  REFERENCES teams(id),
    FOREIGN KEY (driver_id) REFERENCES drivers(id)
  )""")


def migrate_012(conn):
  """Table orders — commandes/ordres de livraison ou collecte."""
  conn.execute("""CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    reference          TEXT UNIQUE,
    client_id          INTEGER NOT NULL,
    vehicle_id         INTEGER,
    driver_id          INTEGER,
    depot_id          INTEGER,
    operation_type       TEXT DEFAULT 'delivery',
    status           TEXT DEFAULT 'pending',
    quantity_kg         REAL DEFAULT 0,
    volume_m3          REAL DEFAULT 0,
    units_count         INTEGER DEFAULT 1,
    goods_category       TEXT DEFAULT 'standard',
    adr_class          TEXT,
    temperature_required    TEXT DEFAULT 'ambient',
    declared_value       REAL,
    time_window_start      TEXT,
    time_window_end       TEXT,
    time_window2_start     TEXT,
    time_window2_end      TEXT,
    planned_arrival       TEXT,
    actual_arrival       TEXT,
    actual_departure      TEXT,
    visit_duration_minutes   INTEGER DEFAULT 15,
    visit_duration_per_kg_seconds REAL DEFAULT 0,
    priority          INTEGER DEFAULT 5,
    delivery_notes       TEXT,
    access_instructions     TEXT,
    proof_photo_path      TEXT,
    signature_path       TEXT,
    failure_reason       TEXT,
    is_recurring        INTEGER DEFAULT 0,
    parent_order_id       INTEGER,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    scheduled_date       TEXT,
    created_by         INTEGER,
    archived          INTEGER DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
    FOREIGN KEY (driver_id) REFERENCES drivers(id),
    FOREIGN KEY (depot_id)  REFERENCES depots(id)
  )""")


def migrate_013(conn):
  """Table routes — tournées planifiées (remplace tournees, plus riche)."""
  conn.execute("""CREATE TABLE IF NOT EXISTS routes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    algo_result_id INTEGER,
    vehicle_id   INTEGER NOT NULL,
    driver_id    INTEGER,
    depot_start_id INTEGER,
    depot_end_id  INTEGER,
    planned_date  TEXT NOT NULL,
    status     TEXT DEFAULT 'planned',
    is_locked    INTEGER DEFAULT 0,
    total_km    REAL,
    total_duration_min REAL,
    total_cost   REAL,
    co2_kg     REAL,
    stops_count   INTEGER,
    on_time_count  INTEGER,
    notes      TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (vehicle_id)   REFERENCES vehicles(id),
    FOREIGN KEY (driver_id)   REFERENCES drivers(id),
    FOREIGN KEY (depot_start_id) REFERENCES depots(id),
    FOREIGN KEY (depot_end_id)  REFERENCES depots(id)
  )""")


def migrate_014(conn):
  """Table route_stops — arrêts individuels sur une route."""
  conn.execute("""CREATE TABLE IF NOT EXISTS route_stops (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id        INTEGER NOT NULL,
    order_id        INTEGER,
    stop_type        TEXT DEFAULT 'delivery',
    stop_order       INTEGER NOT NULL,
    planned_arrival     TEXT,
    planned_departure    TEXT,
    actual_arrival     TEXT,
    actual_departure    TEXT,
    duration_min      INTEGER DEFAULT 15,
    distance_from_prev_km  REAL,
    status         TEXT DEFAULT 'pending',
    notes          TEXT,
    is_locked        INTEGER DEFAULT 0,
    FOREIGN KEY (route_id) REFERENCES routes(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
  )""")


def migrate_015(conn):
  """Tables carriers et carrier_shipments — transporteurs externes."""
  conn.execute("""CREATE TABLE IF NOT EXISTS carriers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    contact_name    TEXT,
    phone        TEXT,
    email        TEXT,
    website       TEXT,
    zones_covered    TEXT,
    vehicle_types    TEXT,
    cost_per_km     REAL,
    cost_per_kg     REAL,
    cost_fixed     REAL,
    rating       REAL DEFAULT 3.0,
    on_time_rate    REAL,
    api_tracking_url  TEXT,
    api_key_encrypted  TEXT,
    notes        TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    archived      INTEGER DEFAULT 0
  )""")
  conn.execute("""CREATE TABLE IF NOT EXISTS carrier_shipments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    carrier_id     INTEGER NOT NULL,
    order_id      INTEGER NOT NULL,
    tracking_number  TEXT,
    status       TEXT DEFAULT 'pending',
    estimated_delivery TEXT,
    actual_delivery  TEXT,
    cost        REAL,
    notes       TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (carrier_id) REFERENCES carriers(id),
    FOREIGN KEY (order_id)  REFERENCES orders(id)
  )""")


def migrate_016(conn):
  """Extension de notifications — severity, related_table, related_id, user_id, action_url."""
  cols = [
    ("severity",   "TEXT DEFAULT 'info'"),
    ("related_table", "TEXT"),
    ("related_id",  "INTEGER"),
    ("user_id",    "INTEGER"),
    ("action_url",  "TEXT"),
  ]
  for col, defn in cols:
    _add_column_safe(conn, "notifications", col, defn)


def migrate_017(conn):
  """Table zones — zones géographiques GeoJSON (ZFE, livraison, exclusion…)."""
  conn.execute("""CREATE TABLE IF NOT EXISTS zones (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    zone_type  TEXT DEFAULT 'delivery',
    geojson   TEXT NOT NULL,
    color    TEXT DEFAULT '#FF6B6B',
    description TEXT,
    is_active  INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
  )""")


def migrate_018(conn):
  """Extension de scenarios — tags, config_json, results_json, created_by."""
  cols = [
    ("tags",     "TEXT"),
    ("config_json", "TEXT"),
    ("results_json", "TEXT"),
    ("created_by",  "INTEGER"),
  ]
  for col, defn in cols:
    _add_column_safe(conn, "scenarios", col, defn)


def migrate_019(conn):
  """Table reports_history — historique des rapports générés."""
  conn.execute("""CREATE TABLE IF NOT EXISTS reports_history (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type   TEXT NOT NULL,
    parameters_json TEXT,
    file_path    TEXT,
    file_size_kb  INTEGER,
    generated_at  TEXT DEFAULT (datetime('now')),
    generated_by  INTEGER,
    FOREIGN KEY (generated_by) REFERENCES users(id)
  )""")


def migrate_020(conn):
  """Table ai_conversations — historique des conversations Copilote Mistral."""
  conn.execute("""CREATE TABLE IF NOT EXISTS ai_conversations (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    messages_json TEXT NOT NULL,
    context_json TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  )""")


def migrate_021(conn):
  """Table recurring_order_templates — gabarits de commandes récurrentes."""
  conn.execute("""CREATE TABLE IF NOT EXISTS recurring_order_templates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    client_id        INTEGER NOT NULL,
    operation_type     TEXT DEFAULT 'delivery',
    quantity_kg       REAL,
    volume_m3        REAL,
    units_count       INTEGER,
    goods_category     TEXT,
    time_window_start    TEXT,
    time_window_end     TEXT,
    visit_duration_minutes INTEGER DEFAULT 15,
    priority        INTEGER DEFAULT 5,
    recurrence_type     TEXT,
    recurrence_days     TEXT,
    recurrence_day_of_month INTEGER,
    is_active        INTEGER DEFAULT 1,
    notes          TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id)
  )""")


# Registre ordonné des migrations (numéro → (fonction, description))
_MIGRATIONS = {
  1: (migrate_001, "Cache OSRM des matrices de distances"),
  2: (migrate_002, "Glossaire de traduction utilisateur"),
  3: (migrate_003, "Colonne distance_source dans algo_results"),
  4: (migrate_004, "Colonnes étendues clients"),
  5: (migrate_005, "Colonnes étendues vehicles (conformité, vitesses, coûts)"),
  6: (migrate_006, "Colonnes étendues depots (opérationnel)"),
  7: (migrate_007, "Colonnes étendues algo_results (CO2, scénario)"),
  8: (migrate_008, "Colonnes étendues users (phone, permissions, is_active)"),
  9: (migrate_009, "Table drivers"),
  10: (migrate_010, "Table driver_unavailabilities"),
  11: (migrate_011, "Tables teams et team_members"),
  12: (migrate_012, "Table orders"),
  13: (migrate_013, "Table routes"),
  14: (migrate_014, "Table route_stops"),
  15: (migrate_015, "Tables carriers et carrier_shipments"),
  16: (migrate_016, "Extension notifications (severity, related_table, user_id)"),
  17: (migrate_017, "Table zones GeoJSON"),
  18: (migrate_018, "Extension scenarios (tags, config_json, results_json)"),
  19: (migrate_019, "Table reports_history"),
  20: (migrate_020, "Table ai_conversations"),
  21: (migrate_021, "Table recurring_order_templates"),
}


def run_migrations(db_path=None):
  """
  Applique toutes les migrations manquantes dans l'ordre.
  Idempotent : peut être appelé plusieurs fois sans effet.
  À appeler au démarrage, après init_database().
  """
  conn = get_connection(db_path)
  try:
    _ensure_schema_version_table(conn)
    current = _get_current_version(conn)
    applied = 0

    for version in sorted(_MIGRATIONS.keys()):
      if version <= current:
        continue
      fn, description = _MIGRATIONS[version]
      try:
        fn(conn)
        conn.commit()
        _mark_applied(conn, version, description)
        applied += 1
        logger_db.info("Migration %03d appliquée : %s", version, description)
      except Exception as e:
        msg = str(e).lower()
        if "duplicate column" in msg or "already exists" in msg or "table" in msg:
          # Migration partiellement appliquée — on la marque quand même
          conn.commit()
          _mark_applied(conn, version, description + " (partielle)")
          logger_db.warning("Migration %03d partielle (colonne/table existante)", version)
        else:
          logger_db.exception("Erreur critique migration %03d : %s", version, e)
          raise

    if applied:
      logger_db.info("%d migration(s) appliquée(s)", applied)
  finally:
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(password, salt=None):
  if salt is None:
    salt = secrets.token_hex(16)
  pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()
  return pw_hash, salt


def verify_password(password, stored_hash, salt):
  pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()
  return secrets.compare_digest(pw_hash, stored_hash)


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING AUDIT
# ══════════════════════════════════════════════════════════════════════════════

def log_action(action, details=None, level="INFO", user_id=None):
  """Enregistre une action dans la table logs. Ne lève jamais d'exception."""
  try:
    conn = get_connection()
    conn.execute(
      "INSERT INTO logs (level, user_id, action, details) VALUES (?,?,?,?)",
      (level, user_id, action, details)
    )
    conn.commit()
    conn.close()
  except Exception:
    pass


def log_action_structured(action, details=None, level="INFO", user_id=None,
             extra: dict | None = None):
  """Version enrichie : log BDD + JSON structuré vers le logger Python."""
  try:
    with db_connection() as conn:
      conn.execute(
        "INSERT INTO logs (level, user_id, action, details) VALUES (?,?,?,?)",
        (level, user_id, action, details)
      )
    record = {"level": level, "action": action, "details": details, "user_id": user_id}
    if extra:
      record.update(extra)
    logger_db.info(json.dumps(record, ensure_ascii=False))
  except Exception:
    logger_db.exception("Erreur log_action_structured — action=%s", action)


# ══════════════════════════════════════════════════════════════════════════════
# AFFECTATION VÉHICULE ↔ CHAUFFEUR (synchronisation 1-pour-1)
# ══════════════════════════════════════════════════════════════════════════════

def assign_driver_to_vehicle(driver_id, vehicle_id, conn=None):
    """
    Synchronise de façon atomique vehicles.driver_id ↔ drivers.vehicle_id.

    Règles :
    - Un véhicule ne peut avoir qu'un seul chauffeur à la fois.
    - Un chauffeur ne peut conduire qu'un seul véhicule à la fois.
    - Si driver_id=None  → le véhicule est libéré (plus de chauffeur).
    - Si vehicle_id=None → le chauffeur est libéré (plus de véhicule).

    conn : connexion existante (pas de commit/close dans ce cas).
    Si conn=None, la fonction ouvre+commit+close sa propre connexion.

    Retourne un dict {
        "old_driver_id"  : ancien chauffeur du véhicule (ou None),
        "old_vehicle_id" : ancien véhicule du chauffeur (ou None),
    } pour permettre à l'UI d'afficher un avertissement.
    """
    _own = conn is None
    if _own:
        conn = get_connection()
    info = {"old_driver_id": None, "old_vehicle_id": None}
    try:
        # ── Lire les affectations actuelles ──────────────────────────────
        if vehicle_id is not None:
            row = conn.execute(
                "SELECT driver_id FROM vehicles WHERE id=?", (vehicle_id,)
            ).fetchone()
            info["old_driver_id"] = row["driver_id"] if row else None

        if driver_id is not None:
            row = conn.execute(
                "SELECT vehicle_id FROM drivers WHERE id=?", (driver_id,)
            ).fetchone()
            info["old_vehicle_id"] = row["vehicle_id"] if row else None

        # ── Libérer les anciennes liaisons des deux côtés ─────────────────
        old_did = info["old_driver_id"]
        old_vid = info["old_vehicle_id"]

        if old_did and old_did != driver_id:
            # L'ancien chauffeur du véhicule perd son véhicule
            conn.execute(
                "UPDATE drivers SET vehicle_id=NULL WHERE id=?", (old_did,)
            )
        if old_vid and old_vid != vehicle_id:
            # L'ancien véhicule du chauffeur perd son chauffeur
            conn.execute(
                "UPDATE vehicles SET driver_id=NULL WHERE id=?", (old_vid,)
            )

        # ── Appliquer la nouvelle affectation ─────────────────────────────
        if vehicle_id is not None:
            conn.execute(
                "UPDATE vehicles SET driver_id=? WHERE id=?", (driver_id, vehicle_id)
            )
        if driver_id is not None:
            conn.execute(
                "UPDATE drivers SET vehicle_id=? WHERE id=?", (vehicle_id, driver_id)
            )

        if _own:
            conn.commit()
    finally:
        if _own:
            conn.close()
    return info


def get_driver_vehicle_info(driver_id=None, vehicle_id=None):
    """
    Retourne les infos d'affectation courante.
    - driver_id fourni → renvoie le véhicule assigné à ce chauffeur
    - vehicle_id fourni → renvoie le chauffeur assigné à ce véhicule
    """
    conn = get_connection()
    result = {}
    try:
        if driver_id is not None:
            row = conn.execute(
                """SELECT v.id, v.registration, v.type
                   FROM vehicles v
                   JOIN drivers d ON d.vehicle_id = v.id
                   WHERE d.id=?""",
                (driver_id,),
            ).fetchone()
            result["vehicle"] = dict(row) if row else None

        if vehicle_id is not None:
            row = conn.execute(
                """SELECT d.id, d.first_name, d.last_name, d.license_number
                   FROM drivers d
                   JOIN vehicles v ON v.driver_id = d.id
                   WHERE v.id=?""",
                (vehicle_id,),
            ).fetchone()
            result["driver"] = dict(row) if row else None
    finally:
        conn.close()
    return result


# SESSIONS UTILISATEURS
# ══════════════════════════════════════════════════════════════════════════════

def save_user_session(user_id, page_index):
  try:
    conn = get_connection()
    conn.execute(
      """INSERT INTO user_sessions (user_id, last_page_index, updated_at)
        VALUES (?,?,datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
        last_page_index=excluded.last_page_index,
        updated_at=excluded.updated_at""",
      (user_id, page_index),
    )
    conn.commit()
    conn.close()
  except Exception:
    pass


def get_user_session(user_id):
  try:
    conn = get_connection()
    row = conn.execute(
      "SELECT last_page_index FROM user_sessions WHERE user_id= ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["last_page_index"] if row else 0
  except Exception:
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

def has_permission(user_id: int, module: str, action: str) -> bool:
  """
  Vérifie si un utilisateur a la permission d'effectuer une action sur un module.

  Rôles : admin / administrateur → tout
      planner / gestionnaire → lecture+écriture sauf users
      dispatcher       → lecture + mise à jour statuts
      viewer         → lecture seule
  """
  try:
    conn = get_connection()
    row = conn.execute(
      "SELECT role, permissions FROM users WHERE id= ? AND is_active!=0",
      (user_id,)
    ).fetchone()
    conn.close()
    if not row:
      return False

    role = (row["role"] or "viewer").lower()

    # Permissions JSON personnalisées (surcharge le rôle)
    if row["permissions"]:
      try:
        custom = json.loads(row["permissions"])
        if module in custom:
          return action in custom[module]
        if "*" in custom:
          return action in custom["*"] or "*" in custom["*"]
      except Exception:
        pass

    perms = _ROLE_PERMISSIONS.get(role, {"*": ["read"]})

    # Wildcard admin
    if "*" in perms and "*" in perms["*"]:
      return True

    # Module spécifique
    allowed = perms.get(module, perms.get("*", []))
    return action in allowed or "*" in allowed

  except Exception:
    logger_db.exception("Erreur has_permission user=%s module=%s", user_id, module)
    return False


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS EXPIRANTS
# ══════════════════════════════════════════════════════════════════════════════

def get_expiring_documents(days_ahead: int = 30) -> list:
  """
  Retourne la liste des véhicules dont l'assurance ou le CT expire
  dans les prochains `days_ahead` jours.
  Chaque entrée : dict avec vehicle_id, registration, doc_type, expiry_date, days_left.
  """
  results = []
  today  = datetime.now().date()
  limit  = today + timedelta(days=days_ahead)

  try:
    conn = get_connection()
    try:
      rows = conn.execute(
        "SELECT id, registration, insurance_expiry, technical_inspection_expiry FROM vehicles"
      ).fetchall()
    except Exception:
      conn.close()
      return []
    conn.close()

    for row in rows:
      for doc_type, col in [("Assurance", "insurance_expiry"),
                  ("Contrôle technique", "technical_inspection_expiry")]:
        val = row[col]
        if not val:
          continue
        try:
          expiry = datetime.strptime(val[:10], "%Y-%m-%d").date()
          days_left = (expiry - today).days
          if days_left <= days_ahead:
            results.append({
              "vehicle_id":  row["id"],
              "registration": row["registration"] or f"V{row['id']}",
              "doc_type":   doc_type,
              "expiry_date": val[:10],
              "days_left":  days_left,
            })
        except ValueError:
          pass
  except Exception:
    logger_db.exception("Erreur get_expiring_documents")

  results.sort(key=lambda x: x["days_left"])
  return results


# ══════════════════════════════════════════════════════════════════════════════
# RÉFÉRENCE COMMANDE
# ══════════════════════════════════════════════════════════════════════════════

def generate_order_reference() -> str:
  """Génère une référence unique de commande : ORD-YYYY-XXXXXX."""
  year = datetime.now().year
  try:
    conn = get_connection()
    count = conn.execute(
      "SELECT COUNT(*) FROM orders WHERE reference LIKE ? ",
      (f"ORD-{year}-%",)
    ).fetchone()[0]
    conn.close()
  except Exception:
    count = 0
  seq = str(count + 1).zfill(6)
  return f"ORD-{year}-{seq}"


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

def create_notification(
  type_: str,
  title: str,
  message: str = "",
  severity: str = "info",
  related_table: str | None = None,
  related_id: int | None = None,
  user_id: int | None = None,
) -> int:
  """
  Crée une notification en base et loggue l'action.
  Retourne l'id de la notification créée, ou -1 en cas d'erreur.
  """
  try:
    with db_connection() as conn:
      cur = conn.execute(
        """INSERT INTO notifications
          (type, title, message, severity, related_table, related_id, user_id)
          VALUES (?,?,?,?,?,?,?)""",
        (type_, title, message, severity, related_table, related_id, user_id)
      )
      notif_id = cur.lastrowid
    log_action("NOTIFICATION_CREATE", f"{type_}: {title}", user_id=user_id)
    return notif_id
  except Exception:
    logger_db.exception("Erreur create_notification type=%s", type_)
    return -1


def get_unread_notifications_count(user_id: int | None = None) -> int:
  """Retourne le nombre de notifications non lues (optionnellement filtrées par utilisateur)."""
  try:
    conn = get_connection()
    if user_id is not None:
      count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE is_read=0 AND (user_id= ? OR user_id IS NULL)",
        (user_id,)
      ).fetchone()[0]
    else:
      count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE is_read=0"
      ).fetchone()[0]
    conn.close()
    return count
  except Exception:
    return 0
