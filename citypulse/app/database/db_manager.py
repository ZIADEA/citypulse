import sqlite3
import os
import hashlib
import secrets
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "citypulse.db")


def get_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path=None):
    conn = get_connection(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'gestionnaire',
        full_name TEXT,
        email TEXT,
        avatar_path TEXT,
        language TEXT DEFAULT 'fr',
        theme TEXT DEFAULT 'light',
        failed_attempts INTEGER DEFAULT 0,
        locked_until TEXT,
        last_login TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS depots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        opening_time TEXT DEFAULT '08:00',
        closing_time TEXT DEFAULT '18:00',
        storage_capacity REAL,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cust_no INTEGER,
        name TEXT NOT NULL,
        address TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        demand_kg REAL DEFAULT 0,
        demand_m3 REAL DEFAULT 0,
        ready_time INTEGER DEFAULT 0,
        due_time INTEGER DEFAULT 1440,
        service_time INTEGER DEFAULT 10,
        priority INTEGER DEFAULT 3,
        client_type TEXT DEFAULT 'standard',
        contact TEXT,
        phone TEXT,
        email TEXT,
        instructions TEXT,
        archived INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration TEXT UNIQUE,
        type TEXT DEFAULT 'fourgon',
        capacity_kg REAL DEFAULT 1000,
        capacity_m3 REAL DEFAULT 10,
        max_speed_kmh REAL DEFAULT 60,
        cost_per_km REAL DEFAULT 0.5,
        depot_id INTEGER,
        status TEXT DEFAULT 'disponible',
        driver_name TEXT,
        total_km REAL DEFAULT 0,
        maintenance_km_threshold REAL DEFAULT 10000,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (depot_id) REFERENCES depots(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS scenarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        client_count INTEGER,
        vehicle_count INTEGER,
        traffic_coeff REAL DEFAULT 1.0,
        weather_coeff REAL DEFAULT 1.0,
        algorithm TEXT,
        data_json TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS tournees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario_id INTEGER,
        vehicle_id INTEGER,
        algorithm TEXT NOT NULL,
        total_distance_km REAL,
        total_duration_min REAL,
        total_cost REAL,
        clients_served INTEGER,
        respect_rate REAL,
        avg_delay_min REAL,
        cpu_time_ms REAL,
        traffic_coeff REAL DEFAULT 1.0,
        weather_coeff REAL DEFAULT 1.0,
        route_json TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS arrets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournee_id INTEGER NOT NULL,
        client_id INTEGER,
        visit_order INTEGER NOT NULL,
        arrival_time REAL,
        departure_time REAL,
        delay_min REAL DEFAULT 0,
        status TEXT DEFAULT 'planifie',
        FOREIGN KEY (tournee_id) REFERENCES tournees(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS algo_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        algorithm TEXT NOT NULL,
        client_count INTEGER,
        vehicle_count INTEGER,
        total_distance REAL,
        total_duration REAL,
        total_cost REAL,
        cpu_time_ms REAL,
        respect_rate REAL,
        avg_delay REAL,
        gain_vs_greedy REAL,
        fleet_utilization REAL,
        traffic_coeff REAL DEFAULT 1.0,
        weather_coeff REAL DEFAULT 1.0,
        details_json TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS translation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_lang TEXT NOT NULL,
        target_lang TEXT NOT NULL,
        source_text TEXT NOT NULL,
        translated_text TEXT NOT NULL,
        quality_score REAL,
        validated INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level TEXT NOT NULL DEFAULT 'INFO',
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournee_id INTEGER,
        anomaly_type TEXT NOT NULL,
        description TEXT,
        severity TEXT DEFAULT 'warning',
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        last_page_index INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # Create default admin user if not exists
    c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        salt = secrets.token_hex(16)
        pw_hash = hashlib.sha256(("admin" + salt).encode()).hexdigest()
        c.execute(
            "INSERT INTO users (username, password_hash, salt, role, full_name) VALUES (?, ?, ?, ?, ?)",
            ("admin", pw_hash, salt, "administrateur", "Administrateur")
        )

    # Create default depot if not exists
    c.execute("SELECT COUNT(*) FROM depots")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO depots (name, address, latitude, longitude) VALUES (?, ?, ?, ?)",
            ("Dépôt Casablanca", "Casablanca, Maroc", 33.5731, -7.5898)
        )

    conn.commit()
    conn.close()


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return pw_hash, salt


def verify_password(password, stored_hash, salt):
    pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return secrets.compare_digest(pw_hash, stored_hash)


def log_action(action, details=None, level="INFO", user_id=None):
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO logs (level, user_id, action, details) VALUES (?, ?, ?, ?)",
            (level, user_id, action, details)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def save_user_session(user_id, page_index):
    """Persist the user's last active page index."""
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO user_sessions (user_id, last_page_index, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET last_page_index=excluded.last_page_index,
               updated_at=excluded.updated_at""",
            (user_id, page_index),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_user_session(user_id):
    """Return the saved page index for the user, or 0 if none."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT last_page_index FROM user_sessions WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()
        return row["last_page_index"] if row else 0
    except Exception:
        return 0
