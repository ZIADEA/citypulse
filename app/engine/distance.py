"""
distance.py — Moteur de calcul de distances CityPulse Logistics
================================================================
Priorité 1 : Matrice OSRM (distances et temps routiers réels)
Priorité 2 : Cache SQLite (évite les appels réseau répétés)
Priorité 3 : Fallback Haversine si OSRM inaccessible (mode offline)

Retourne TOUJOURS deux matrices séparées :
  dist_km : distances en kilomètres (pour le coût)
  time_s  : temps de trajet en secondes (pour les fenêtres horaires)
"""

import math
import json
import hashlib
import logging
import os
import sqlite3

try:
  import requests
  REQUESTS_AVAILABLE = True
except ImportError:
  REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Configuration OSRM ────────────────────────────────────────────────────────
OSRM_BASE_URL = os.environ.get(
  "CITYPULSE_OSRM_URL",
  "http://router.project-osrm.org"
)
OSRM_TIMEOUT = int(os.environ.get("CITYPULSE_OSRM_TIMEOUT", "10"))

# ── Cache SQLite ───────────────────────────────────────────────────────────────
_CACHE_DB = os.path.join(
  os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
  "citypulse.db"
)


def _ensure_cache_table(conn):
  conn.execute("""
    CREATE TABLE IF NOT EXISTS distance_cache (
      cache_key TEXT PRIMARY KEY,
      dist_json TEXT NOT NULL,
      time_json TEXT NOT NULL,
      source   TEXT DEFAULT 'osrm',
      created_at TEXT DEFAULT (datetime('now'))
    )
  """)
  conn.commit()


def _cache_key(nodes):
  coords = [(round(n["latitude"], 6), round(n["longitude"], 6)) for n in nodes]
  raw = json.dumps(coords, sort_keys=True)
  return hashlib.sha256(raw.encode()).hexdigest()


def _read_cache(key):
  try:
    conn = sqlite3.connect(_CACHE_DB)
    _ensure_cache_table(conn)
    row = conn.execute(
      "SELECT dist_json, time_json FROM distance_cache WHERE cache_key= ?",
      (key,)
    ).fetchone()
    conn.close()
    if row:
      return json.loads(row[0]), json.loads(row[1])
  except Exception:
    logger.exception("Erreur lecture cache distance")
  return None


def _write_cache(key, dist_km, time_s, source="osrm"):
  try:
    conn = sqlite3.connect(_CACHE_DB)
    _ensure_cache_table(conn)
    conn.execute(
      """INSERT OR REPLACE INTO distance_cache
        (cache_key, dist_json, time_json, source)
        VALUES (?,?,?,?)""",
      (key, json.dumps(dist_km), json.dumps(time_s), source)
    )
    conn.commit()
    conn.close()
  except Exception:
    logger.exception("Erreur écriture cache distance")


# ── Haversine (fallback offline) ───────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
  R = 6371.0
  phi1, phi2 = math.radians(lat1), math.radians(lat2)
  dphi = math.radians(lat2 - lat1)
  dlam = math.radians(lon2 - lon1)
  a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
  return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _haversine_matrices(nodes):
  n = len(nodes)
  ASSUMED_SPEED_KMH = 50.0
  dist_km = [[0.0] * n for _ in range(n)]
  time_s = [[0.0] * n for _ in range(n)]
  for i in range(n):
    for j in range(i + 1, n):
      d = haversine(
        nodes[i]["latitude"], nodes[i]["longitude"],
        nodes[j]["latitude"], nodes[j]["longitude"]
      )
      t = (d / ASSUMED_SPEED_KMH) * 3600
      dist_km[i][j] = dist_km[j][i] = d
      time_s[i][j] = time_s[j][i] = t
  return dist_km, time_s


# ── OSRM ───────────────────────────────────────────────────────────────────────
def _osrm_matrices(nodes):
  if not REQUESTS_AVAILABLE:
    logger.warning("requests non installé — fallback Haversine")
    return None

  coords_str = ";".join(
    f"{n['longitude']},{n['latitude']}" for n in nodes
  )
  url = f"{OSRM_BASE_URL}/table/v1/driving/{coords_str}"
  params = {"annotations": "distance,duration"}

  try:
    resp = requests.get(url, params=params, timeout=OSRM_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "Ok":
      logger.warning("OSRM code non-OK : %s", data.get("code"))
      return None

    durations = data.get("durations")
    distances = data.get("distances")

    if not durations or not distances:
      logger.warning("OSRM: matrices manquantes dans la réponse")
      return None

    n = len(nodes)
    dist_km = [[distances[i][j] / 1000.0 for j in range(n)] for i in range(n)]
    time_s = [[durations[i][j]      for j in range(n)] for i in range(n)]

    for i in range(n):
      dist_km[i][i] = 0.0
      time_s[i][i] = 0.0

    return dist_km, time_s

  except Exception as e:
    logger.warning("OSRM inaccessible (%s) — fallback Haversine", type(e).__name__)
  return None


# ── Interface publique principale ──────────────────────────────────────────────
def build_matrix(clients, depot, use_cache=True):
  """
  Point d'entrée principal.

  Returns
  -------
  dist_km : list[list[float]] distances routières en km
  time_s : list[list[float]] temps de trajet en secondes
  source : str 'osrm' | 'haversine' | 'cache'

  nodes[0] = dépôt, nodes[1..N] = clients
  """
  nodes = [depot] + clients

  if use_cache:
    key = _cache_key(nodes)
    cached = _read_cache(key)
    if cached:
      logger.debug("Distance matrix depuis cache (%d nœuds)", len(nodes))
      return cached[0], cached[1], "cache"

  result = _osrm_matrices(nodes)
  if result:
    dist_km, time_s = result
    if use_cache:
      _write_cache(key, dist_km, time_s, "osrm")
    logger.info("Distance matrix OSRM (%d nœuds)", len(nodes))
    return dist_km, time_s, "osrm"

  logger.warning("Fallback Haversine — distances approximatives")
  dist_km, time_s = _haversine_matrices(nodes)
  if use_cache:
    _write_cache(key, dist_km, time_s, "haversine")
  return dist_km, time_s, "haversine"


# ── Compatibilité rétrograde ─────────────────────────────────────────────────
def build_distance_matrix(clients, depot):
  """Conservée pour compatibilité — retourne uniquement dist_km."""
  dist_km, _, _ = build_matrix(clients, depot)
  return dist_km


def build_time_matrix(clients, depot, coeff=1.0):
  """Retourne la matrice de temps (secondes × coeff) pour OR-Tools."""
  _, time_s, _ = build_matrix(clients, depot)
  n = len(time_s)
  return [[int(time_s[i][j] * coeff) for j in range(n)] for i in range(n)]


def invalidate_cache(clients, depot):
  nodes = [depot] + clients
  key = _cache_key(nodes)
  try:
    conn = sqlite3.connect(_CACHE_DB)
    conn.execute("DELETE FROM distance_cache WHERE cache_key= ?", (key,))
    conn.commit()
    conn.close()
  except Exception:
    logger.exception("Erreur invalidation cache distance")


def euclidean_distance(x1, y1, x2, y2):
  return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
