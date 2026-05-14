"""
optimization_service.py — Couche service entre l'UI et les moteurs VRP
=======================================================================
Responsabilités :
 1. Validation des inputs (clients, véhicules, dépôt)
 2. Pré-segmentation KMeans optionnelle (clustering avant optimisation)
 3. Dispatch vers le bon algorithme
 4. Persistance en BDD
 5. Détection d'anomalies post-optimisation
 6. Calcul du gain vs glouton
"""

import logging
import time
from ..engine.greedy import greedy_vrp
from ..engine.two_opt import two_opt_vrp
from ..engine.ortools_solver import ortools_vrp, ORTOOLS_AVAILABLE
from ..ai.clustering import cluster_clients, suggest_vehicle_assignment
from ..ai.anomaly_detection import detect_anomalies
from ..database.db_manager import db_connection, log_action

logger = logging.getLogger(__name__)

# ── Validation ────────────────────────────────────────────────────────────────

class ValidationError(Exception):
  pass


def validate_inputs(clients, vehicles, depot):
  """
  Vérifie que les inputs sont exploitables par les solveurs.
  Lève ValidationError avec un message lisible si un problème est détecté.
  """
  if not clients:
    raise ValidationError("Aucun client chargé. Importez des données ou utilisez le mode démo.")
  if not vehicles:
    raise ValidationError("Aucun véhicule disponible. Ajoutez au moins un véhicule.")
  if depot is None:
    raise ValidationError("Aucun dépôt configuré. Définissez un dépôt avant d'optimiser.")

  # Vérifier coordonnées dépôt
  if not (-90 <= depot.get("latitude", 0) <= 90) or not (-180 <= depot.get("longitude", 0) <= 180):
    raise ValidationError(f"Coordonnées du dépôt invalides : ({depot.get('latitude')}, {depot.get('longitude')})")

  # Vérifier clients
  bad_coords, bad_tw, bad_demand = [], [], []
  for i, c in enumerate(clients):
    lat, lon = c.get("latitude", 0), c.get("longitude", 0)
    if lat == 0 and lon == 0:
      bad_coords.append(c.get("name", f"client_{i}"))
    if c.get("due_time", 1440) < c.get("ready_time", 0):
      bad_tw.append(c.get("name", f"client_{i}"))
    if c.get("demand_kg", 0) < 0:
      bad_demand.append(c.get("name", f"client_{i}"))

  warnings = []
  if bad_coords:
    warnings.append(f"Coordonnées (0,0) pour : {', '.join(bad_coords[:3])}{'...' if len(bad_coords)>3 else ''}")
  if bad_tw:
    warnings.append(f"Fenêtres horaires inversées pour : {', '.join(bad_tw[:3])}")
  if bad_demand:
    warnings.append(f"Demande négative pour : {', '.join(bad_demand[:3])}")

  # Filtrer les clients invalides silencieusement (log warning)
  valid_clients = [
    c for c in clients
    if not (c.get("latitude", 0) == 0 and c.get("longitude", 0) == 0)
    and c.get("due_time", 1440) >= c.get("ready_time", 0)
  ]

  if not valid_clients:
    raise ValidationError("Tous les clients sont invalides après validation. Vérifiez vos données.")

  if warnings:
    for w in warnings:
      logger.warning("Validation: %s", w)

  return valid_clients, warnings


# ── Pré-segmentation KMeans ────────────────────────────────────────────────────

def apply_clustering_presegmentation(clients, vehicles):
  """
  Pré-segmente les clients par zone géographique avec KMeans.
  Retourne un dict {vehicle_idx: [clients]} pour guider l'optimisation.
  Utilisé quand n_clients >= 20 pour réduire le temps de calcul OR-Tools.
  """
  n_clusters = min(len(vehicles), len(clients))
  assignment = suggest_vehicle_assignment(clients, vehicles, n_clusters)
  return assignment


# ── Dispatcher principal ───────────────────────────────────────────────────────

def run_optimization(algo, clients, depot, vehicles,
           traffic_coeff=1.0, weather_coeff=1.0,
           params=None, use_clustering=False,
           greedy_result_ref=None):
  """
  Lance un algorithme d'optimisation VRP complet.

  Paramètres
  ----------
  algo      : 'greedy' | '2opt' | 'ortools'
  clients     : liste de dicts clients (déjà validés)
  depot      : dict dépôt
  vehicles    : liste de dicts véhicules
  traffic_coeff  : float
  weather_coeff  : float
  params     : dict avec max_iterations, time_limit, legal_break
  use_clustering : bool — pré-segmenter les clients par zone avant optimisation
  greedy_result_ref : dict — résultat glouton existant pour calcul du gain

  Retourne
  --------
  result : dict complet avec routes, métriques, anomalies
  """
  if params is None:
    params = {}

  t_start = time.perf_counter()

  # Clustering pré-segmentation (si activé et assez de clients)
  cluster_info = None
  if use_clustering and len(clients) >= 20:
    try:
      cluster_info = apply_clustering_presegmentation(clients, vehicles)
      logger.info("Clustering: %d zones détectées", len(cluster_info))
    except Exception:
      logger.exception("Erreur clustering — désactivé pour cette run")
      cluster_info = None

  # Tri par priorité : commandes urgentes (priorité 1) servies en premier
  clients = sorted(clients, key=lambda c: c.get("priority", 3))

  # Dispatch algorithme
  if algo == "greedy":
    result = greedy_vrp(clients, depot, vehicles, traffic_coeff, weather_coeff)

  elif algo == "2opt":
    result = two_opt_vrp(
      clients, depot, vehicles,
      traffic_coeff, weather_coeff,
      params.get("max_iterations", 1000)
    )

  elif algo == "ortools":
    if not ORTOOLS_AVAILABLE:
      raise ValidationError("OR-Tools non installé. Lancez : pip install ortools")
    result = ortools_vrp(
      clients, depot, vehicles,
      traffic_coeff, weather_coeff,
      params.get("time_limit", 30),
      params.get("legal_break", True),
    )
  else:
    raise ValidationError(f"Algorithme inconnu : {algo}")

  # Calcul gain vs glouton
  if greedy_result_ref and algo != "greedy":
    g_dist = greedy_result_ref.get("total_distance_km", 0)
    r_dist = result.get("total_distance_km", 0)
    result["gain_vs_greedy"] = ((g_dist - r_dist) / g_dist * 100) if g_dist > 0 else 0.0
  elif "gain_vs_greedy" not in result:
    result["gain_vs_greedy"] = 0.0

  # Attacher infos clustering
  if cluster_info:
    result["cluster_info"] = {
      str(v_idx): [c.get("name", str(c.get("id", i))) for i, c in enumerate(c_list)]
      for v_idx, c_list in cluster_info.items()
    }

  result["total_elapsed_ms"] = (time.perf_counter() - t_start) * 1000
  return result


# ── Persistance ────────────────────────────────────────────────────────────────

def save_plan(result: dict, planned_date: str) -> dict:
  """
  Persiste un résultat d'optimisation comme plan officiel pour une date donnée.

  Pour chaque véhicule actif :
    - INSERT INTO routes  (1 ligne par véhicule)
    - INSERT INTO route_stops (1 ligne par arrêt)
    - UPDATE orders SET status='assigned', vehicle_id, driver_id
    - INSERT OR IGNORE INTO vehicle_unavailabilities (bloque le calendrier véhicule)
  Après tout ça :
    - INSERT INTO notifications (confirmation plan)

  Retourne {routes: int, stops: int, orders_updated: int}
  """
  n_routes = 0
  n_stops  = 0
  n_orders = 0

  try:
    with db_connection() as conn:
      # ── Extensions colonnes routes si absentes ──────────────────────────
      for col_def in [
        "driver_id INTEGER",
        "algorithm TEXT",
        "total_cost REAL DEFAULT 0",
        "co2_kg REAL DEFAULT 0",
        "total_km REAL DEFAULT 0",
        "total_duration_min REAL DEFAULT 0",
        "stops_count INTEGER DEFAULT 0",
        "status TEXT DEFAULT 'planned'",
      ]:
        try:
          conn.execute(f"ALTER TABLE routes ADD COLUMN {col_def}")
        except Exception:
          pass

      # ── Extension colonnes orders si absentes ───────────────────────────
      for col_def in ["vehicle_id INTEGER", "driver_id INTEGER"]:
        try:
          conn.execute(f"ALTER TABLE orders ADD COLUMN {col_def}")
        except Exception:
          pass

      # ── Table vehicle_unavailabilities (créée à la volée si absente) ────
      conn.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_unavailabilities (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          vehicle_id INTEGER NOT NULL,
          date TEXT NOT NULL,
          reason TEXT DEFAULT '',
          UNIQUE(vehicle_id, date)
        )
      """)

      # ── Extension colonnes route_stops si absentes ──────────────────────
      for col_def in [
        "client_id INTEGER",
        "stop_type TEXT DEFAULT 'delivery'",
        "planned_arrival TEXT",
        "planned_departure TEXT",
        "distance_from_prev_km REAL DEFAULT 0",
        "status TEXT DEFAULT 'pending'",
        "is_locked INTEGER DEFAULT 0",
      ]:
        try:
          conn.execute(f"ALTER TABLE route_stops ADD COLUMN {col_def}")
        except Exception:
          pass

    algo      = result.get("algorithm", "")
    total_km  = result.get("total_distance_km", 0)
    total_cost = result.get("total_cost", 0)
    co2_kg    = result.get("total_co2_kg", result.get("co2_kg", 0))

    all_routed_client_ids: list[int] = []

    for route in result.get("routes", []):
      stops = [s for s in route.get("route", []) if s.get("type") == "delivery"]
      if not stops:
        continue

      vehicle   = route.get("vehicle", {})
      vid       = vehicle.get("id")
      driver_id = vehicle.get("driver_id") or vehicle.get("_driver", {}).get("id")
      if not vid:
        continue

      r_km      = route.get("distance_km", 0)
      r_dur     = route.get("duration_min", 0)
      r_cost    = route.get("cost", 0)

      with db_connection() as conn:
        # Supprimer les routes existantes non verrouillées pour ce véhicule/jour
        conn.execute(
          "DELETE FROM routes WHERE vehicle_id=? AND planned_date=? AND (is_locked IS NULL OR is_locked=0)",
          (int(vid), planned_date),
        )
        conn.execute(
          """INSERT INTO routes
             (vehicle_id, driver_id, planned_date, algorithm, status, is_locked,
              total_km, total_duration_min, total_cost, co2_kg, stops_count)
             VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
          (int(vid), driver_id, planned_date, algo, "planned", 0,
           r_km, r_dur, r_cost, co2_kg / max(len(result.get("routes", [])), 1),
           len(stops)),
        )
        route_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("DELETE FROM route_stops WHERE route_id=?", (route_id,))

        for i, stop in enumerate(stops):
          client    = stop.get("client") or {}
          cid       = client.get("id")
          order_id  = None

          if cid:
            cid_int = int(cid)
            all_routed_client_ids.append(cid_int)
            # Chercher la commande la plus pertinente pour ce client :
            # 1. schedulée pour cette date, 2. sans date, 3. toute autre date
            ord_row = conn.execute(
              """SELECT id FROM orders
                 WHERE client_id=? AND archived=0
                   AND status NOT IN ('delivered','cancelled','failed')
                 ORDER BY
                   CASE
                     WHEN scheduled_date=? THEN 0
                     WHEN scheduled_date IS NULL THEN 1
                     ELSE 2
                   END,
                   id DESC
                 LIMIT 1""",
              (cid_int, planned_date),
            ).fetchone()
            if ord_row:
              order_id = int(ord_row["id"])

          arr_min = float(stop.get("arrival_time") or 0)
          dep_min = float(stop.get("departure_time") or arr_min)
          arr_str = f"{int(arr_min // 60):02d}:{int(arr_min % 60):02d}"
          dep_str = f"{int(dep_min // 60):02d}:{int(dep_min % 60):02d}"

          conn.execute(
            """INSERT INTO route_stops
               (route_id, order_id, client_id, stop_type, stop_order,
                planned_arrival, planned_departure, distance_from_prev_km, status, is_locked)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (route_id, order_id, cid, "delivery", i + 1,
             arr_str, dep_str, stop.get("distance_from_prev", 0), "pending", 0),
          )
          n_stops += 1

          # Mettre à jour la commande trouvée par le stop
          if order_id:
            conn.execute(
              "UPDATE orders SET status='assigned', vehicle_id=?, driver_id=? WHERE id=?",
              (int(vid), driver_id, order_id),
            )
            n_orders += 1

        # Bloquer le calendrier véhicule
        try:
          conn.execute(
            "INSERT OR IGNORE INTO vehicle_unavailabilities (vehicle_id, date, reason) VALUES (?,?,?)",
            (int(vid), planned_date, "Tournée planifiée"),
          )
        except Exception:
          pass

      n_routes += 1

    # ── Second pass : assigner TOUTES les commandes non encore traitées ─────────
    # Pour chaque client présent dans le plan, assigner toutes ses commandes
    # en attente dont la date planifiée correspond (ou pas de date précise).
    # Ceci attrape les orders que le per-stop lookup n'a pas trouvés (doublons
    # client sur plusieurs routes, ou orders avec scheduled_date différente).
    if all_routed_client_ids:
      unique_cids = list(set(all_routed_client_ids))
      try:
        with db_connection() as conn:
          # Récupérer vehicle_id et driver_id pour chaque client via route_stops → routes
          for cid_int in unique_cids:
            row = conn.execute(
              """SELECT r.vehicle_id, r.driver_id
                 FROM route_stops rs
                 JOIN routes r ON r.id = rs.route_id
                 WHERE rs.client_id=? AND r.planned_date=?
                 ORDER BY rs.id DESC LIMIT 1""",
              (cid_int, planned_date),
            ).fetchone()
            if not row:
              continue
            vid_2nd    = row[0]
            drvid_2nd  = row[1]
            cur = conn.execute(
              """UPDATE orders SET status='assigned', vehicle_id=?, driver_id=?
                 WHERE client_id=? AND archived=0
                   AND status NOT IN ('assigned','delivered','cancelled','failed')
                   AND (scheduled_date=? OR scheduled_date IS NULL)""",
              (vid_2nd, drvid_2nd, cid_int, planned_date),
            )
            n_orders += cur.rowcount
      except Exception:
        logger.warning("second-pass order assignment échoué", exc_info=True)

    # ── Notification confirmation plan ──────────────────────────────────────
    try:
      with db_connection() as conn:
        conn.execute(
          """INSERT INTO notifications (type, title, message, is_read, severity, created_at)
             VALUES (?,?,?,0,?,datetime('now'))""",
          (
            "plan",
            f"Plan confirmé — {planned_date}",
            f"{n_routes} tournée(s), {n_stops} arrêt(s), {n_orders} commande(s) assignée(s).",
            "info",
          ),
        )
    except Exception:
      pass

    log_action(
      "PLAN_CONFIRMED",
      f"{planned_date} | {algo} | {n_routes} routes | {n_stops} arrêts | {n_orders} commandes",
    )
    logger.info("Plan confirmé: %s — %d routes, %d stops", planned_date, n_routes, n_stops)

    # ── Synchro web : routes chauffeurs + suivi clients ─────────────────────
    try:
      _sync_plan_to_web(result, planned_date)
    except Exception:
      logger.warning("sync web échoué (non bloquant)")

  except Exception:
    logger.exception("Erreur save_plan")

  return {"routes": n_routes, "stops": n_stops, "orders_updated": n_orders}


def _sync_plan_to_web(result: dict, planned_date: str) -> None:
  """Pousse le plan confirmé vers le portail web Django (non bloquant)."""
  try:
    from .django_sync_service import get_django_service
    svc = get_django_service()
    if not svc.base_url or not svc.secret_key:
      return

    routes_payload = []
    tracking_payload = []

    for route in result.get("routes", []):
      stops = [s for s in route.get("route", []) if s.get("type") == "delivery"]
      if not stops:
        continue
      vehicle  = route.get("vehicle", {})
      driver   = vehicle.get("_driver") or {}
      drv_name = driver.get("first_name", "") or ""

      route_stops_web = []
      for s in stops:
        client  = s.get("client") or {}
        arr_min = float(s.get("arrival_time") or 0)
        eta_str = f"{planned_date}T{int(arr_min // 60):02d}:{int(arr_min % 60):02d}:00"
        order_ref = str(s.get("order_ref") or client.get("id") or "")
        order_id  = str(s.get("order_id") or client.get("id") or "")
        route_stops_web.append({
          "client_name": client.get("name", ""),
          "address":     client.get("address", ""),
          "eta":         eta_str,
          "order_ref":   order_ref,
        })
        if order_ref:
          tracking_payload.append({
            "order_ref":        order_ref,
            "order_id_ext":     order_id,
            "status":           "assigned",
            "driver_first_name": drv_name,
            "eta":              eta_str,
          })

      routes_payload.append({
        "vehicle_id":  str(vehicle.get("id", "")),
        "driver_id":   str(driver.get("id", "")),
        "planned_date": planned_date,
        "stops":       route_stops_web,
      })

    if routes_payload:
      svc.sync_routes(routes_payload)
      logger.info("sync_routes web: %d routes envoyées", len(routes_payload))

    if tracking_payload:
      r = svc.push_delivery_tracking(tracking_payload)
      logger.info("push_delivery_tracking: %s", r)

  except Exception:
    logger.warning("_sync_plan_to_web: échec silencieux", exc_info=True)


def save_result(result, greedy_dist=0.0):
  """Sauvegarde le résultat en BDD dans algo_results."""
  try:
    fleet_count = len([r for r in result.get("routes", []) if r.get("route")])
    total_v   = len(result.get("routes", []))
    utilization = (fleet_count / total_v * 100) if total_v > 0 else 0.0
    g_dist   = greedy_dist or result.get("total_distance_km", 0)
    r_dist   = result.get("total_distance_km", 0)
    gain    = ((g_dist - r_dist) / g_dist * 100) if g_dist > 0 and r_dist > 0 else 0.0

    with db_connection() as conn:
      conn.execute(
        """INSERT INTO algo_results
          (algorithm, client_count, vehicle_count,
          total_distance, total_duration, total_cost,
          cpu_time_ms, respect_rate, avg_delay,
          gain_vs_greedy, fleet_utilization,
          traffic_coeff, weather_coeff, distance_source)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
          result.get("algorithm", ""),
          result.get("clients_total", 0),
          total_v,
          result.get("total_distance_km", 0),
          result.get("total_duration_min", 0),
          result.get("total_cost", 0),
          result.get("cpu_time_ms", 0),
          result.get("respect_rate", 0),
          result.get("avg_delay_min", 0),
          gain,
          utilization,
          result.get("traffic_coeff", 1.0),
          result.get("weather_coeff", 1.0),
          result.get("distance_source", "haversine"),
        )
      )
    # Marquer les commandes assignées (status pending → assigned)
    client_ids_served = []
    for route in result.get("routes", []):
        for stop in route.get("route", []):
            cid = (stop.get("client") or {}).get("id")
            if cid:
                client_ids_served.append(cid)
    if client_ids_served:
        placeholders = ",".join("?" * len(client_ids_served))
        with db_connection() as conn:
            conn.execute(
                f"UPDATE orders SET status='assigned' "
                f"WHERE client_id IN ({placeholders}) AND status='pending' AND archived=0",
                client_ids_served,
            )

    log_action(
      "OPTIMIZATION",
      f"{result.get('algorithm')}: {r_dist:.1f}km, "
      f"{result.get('cpu_time_ms', 0):.0f}ms, "
      f"{result.get('clients_served', 0)} clients"
    )
    logger.info("Résultat sauvegardé: %s", result.get("algorithm"))
  except Exception:
    logger.exception("Erreur sauvegarde résultat")


# ── Détection d'anomalies post-optimisation ────────────────────────────────────

def check_anomalies_after_run():
  """
  Appelle detect_anomalies sur les 20 derniers résultats en BDD.
  Retourne une liste d'anomalies (peut être vide).
  """
  try:
    with db_connection() as conn:
      rows = conn.execute(
        """SELECT total_distance, total_cost, avg_delay, algorithm, created_at
          FROM algo_results ORDER BY created_at DESC LIMIT 20"""
      ).fetchall()

    if not rows:
      return []

    records = [
      {
        "total_distance": r["total_distance"],
        "total_cost":   r["total_cost"],
        "avg_delay":   r["avg_delay"],
        "algorithm":   r["algorithm"],
        "created_at":   r["created_at"],
      }
      for r in rows
    ]
    return detect_anomalies(records)
  except Exception:
    logger.exception("Erreur détection anomalies")
    return []
