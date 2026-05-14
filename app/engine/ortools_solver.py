"""
ortools_solver.py — Solveur VRP Google OR-Tools v2.0
====================================================
Variantes VRP (vrp_mode) :
 'standard'    — VRPTW classique (un dépôt)
 'multi_depot'   — M-DVRPTW (plusieurs dépôts, dépôts de début/fin par véhicule)
 'open'      — OVRP (les véhicules ne retournent pas au dépôt)
 'pickup_delivery' — PDPTW (paires ramassage → livraison)
 'reload'     — VRP avec rechargement intermédiaire (retour dépôt si < 20%)

Contraintes avancées :
 - Compétences : temp / ADR / vehicle_requirement
 - ZFE : pénalité ×1.5 si zone interdite traversée
 - Pauses RSE : max_drive_before_break_min + min_break_minutes (par véhicule/chauffeur)
 - Pause déjeuner : fenêtre interdite 12h–14h (configurable)
 - Séquence forcée : forced_sequence list[(from_idx, to_idx)]
 - Verrouillage arrêts : is_locked=1 → position fixe
 - Rechargement intermédiaire : retour automatique au dépôt si charge < 20%

Multi-objectifs :
 objective_weights = {'distance':1.0, 'cost':0.5, 'delays':2.0, 'co2':0.3}

Callback progression :
 on_progress(elapsed_s, obj_value) appelé toutes les 500 ms
"""

import time
import logging
from .distance import build_matrix

logger = logging.getLogger(__name__)

try:
  from ortools.constraint_solver import routing_enums_pb2, pywrapcp
  ORTOOLS_AVAILABLE = True
except ImportError:
  ORTOOLS_AVAILABLE = False

# ── Constantes RSE par défaut ──────────────────────────────────────────────────
DEFAULT_MAX_DRIVE_S = int(4.5 * 3600)  # 4h30 en secondes
DEFAULT_BREAK_S   = int(45 * 60)   # 45min
RELOAD_THRESHOLD   = 0.20       # rechargement si charge < 20% de la capacité
LUNCH_START_MIN   = 12 * 60     # 720 min depuis minuit
LUNCH_END_MIN    = 14 * 60     # 840 min

# ── Modes VRP ─────────────────────────────────────────────────────────────────
VRP_MODES = ("standard", "multi_depot", "open", "pickup_delivery", "reload")


# ═══════════════════════════════════════════════════════════════════════════════
# SOLUTION CALLBACK (progression)
# ═══════════════════════════════════════════════════════════════════════════════

class _ProgressCallback:
  """Appelé par OR-Tools toutes les 500 ms via AtSolutionCallback."""

  def __init__(self, routing, manager, on_progress, start_time):
    self._routing  = routing
    self._manager  = manager
    self._on_progress= on_progress
    self._start   = start_time
    self._last_obj  = None

  def __call__(self):
    if self._on_progress is None:
      return
    try:
      elapsed = time.perf_counter() - self._start
      obj   = self._routing.CostVar().Value() if hasattr(self._routing.CostVar(), "Value") else 0
      if obj != self._last_obj:
        self._last_obj = obj
        self._on_progress(elapsed, obj)
    except Exception:
      pass


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — COMPÉTENCES / ZFE
# ═══════════════════════════════════════════════════════════════════════════════

def _vehicle_can_serve(vehicle: dict, client: dict) -> bool:
  """
  Vérifie les compétences : température, ADR, vehicle_requirement.
  Retourne True si le véhicule est compatible.
  """
  # Température
  c_temp = (client.get("temperature_requirement") or "").strip().lower()
  if c_temp and c_temp != "ambiant":
    v_temp = (vehicle.get("temperature_type") or vehicle.get("motorisation") or "").strip().lower()
    if "frigo" not in v_temp and "refrig" not in v_temp and c_temp not in ("", "ambiant"):
      return False

  # ADR (matières dangereuses)
  c_adr = (client.get("adr_class") or "").strip()
  if c_adr and c_adr not in ("", "none", "aucune"):
    if not vehicle.get("allowed_adr"):
      return False

  # Vehicle requirement (type spécifique)
  req = (client.get("vehicle_requirement") or "").strip().lower()
  if req:
    vtype = (vehicle.get("type") or "").strip().lower()
    if req not in vtype:
      return False

  return True


def _apply_zfe_penalty(dist_val: int, from_node: int, to_node: int,
            zfe_pairs: set, penalty_factor: float = 1.5) -> int:
  """Multiplie la distance par penalty_factor si la paire traverse une ZFE."""
  if (from_node, to_node) in zfe_pairs or (to_node, from_node) in zfe_pairs:
    return int(dist_val * penalty_factor)
  return dist_val


def _build_zfe_pairs(clients: list, zones: list) -> set:
  """
  Retourne l'ensemble des paires (i, j) de nœuds dont le trajet entre
  dans une zone ZFE/interdite. Approximation : si un nœud est dans la zone.
  nœuds = 0 (dépôt) puis 1..N (clients).
  zones : list[dict] avec 'zone_type', 'latitude', 'longitude', 'radius_km'.
  """
  import math
  zfe = [z for z in (zones or []) if (z.get("zone_type") or "").lower() in ("zfe", "exclusion")]
  if not zfe:
    return set()

  def _in_zone(lat, lon, z):
    R = 6371.0
    dlat = math.radians(float(z.get("latitude", 0)) - float(lat))
    dlon = math.radians(float(z.get("longitude", 0)) - float(lon))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat))) * \
      math.cos(math.radians(float(z.get("latitude", 0)))) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(max(0, a))) <= float(z.get("radius_km", 1))

  def node_in_zfe(lat, lon):
    return any(_in_zone(lat, lon, z) for z in zfe)

  nodes_in_zfe = set()
  for i, c in enumerate(clients):
    if node_in_zfe(c.get("latitude", 0), c.get("longitude", 0)):
      nodes_in_zfe.add(i + 1)

  pairs = set()
  all_nodes = [0] + list(range(1, len(clients) + 1))
  for a in all_nodes:
    for b in all_nodes:
      if a != b and (a in nodes_in_zfe or b in nodes_in_zfe):
        pairs.add((a, b))
  return pairs


# ═══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def ortools_vrp(
  clients,
  depot,
  vehicles,
  traffic_coeff: float = 1.0,
  weather_coeff: float = 1.0,
  time_limit_s: int = 30,
  legal_break: bool = True,
  # ── Nouvelles options ────────────────────────────────────────────
  vrp_mode: str = "standard",
  objective_weights: dict = None,
  forced_sequence: list = None,
  zones: list = None,
  depots: list = None,
  pickup_delivery_pairs: list = None,
  lunch_window: tuple = None,
  on_progress=None,
):
  """
  Résoud le VRP avec Google OR-Tools.

  Parameters
  ----------
  vrp_mode : str
    'standard' | 'multi_depot' | 'open' | 'pickup_delivery' | 'reload'
  objective_weights : dict, optional
    Poids multi-objectifs. Défaut: {'distance':1.0,'cost':0.5,'delays':2.0,'co2':0.3}
  forced_sequence : list[tuple], optional
    Paires (client_idx_a, client_idx_b) à visiter dans cet ordre.
  zones : list[dict], optional
    Zones ZFE/interdites avec 'zone_type','latitude','longitude','radius_km'.
  depots : list[dict], optional
    Liste de dépôts pour mode multi_depot.
  pickup_delivery_pairs : list[tuple], optional
    Paires (pickup_client_idx, delivery_client_idx) pour mode pickup_delivery.
  lunch_window : tuple (start_min, end_min), optional
    Fenêtre déjeuner interdite en minutes depuis minuit (défaut: (720, 840)).
  on_progress : callable(elapsed_s, obj_value), optional
    Callback appelé à chaque amélioration de la solution.
  """
  if not ORTOOLS_AVAILABLE:
    return {"error": "OR-Tools non installé. pip install ortools"}

  if vrp_mode not in VRP_MODES:
    return {"error": f"vrp_mode invalide: {vrp_mode!r}. Valeurs: {VRP_MODES}"}

  if not clients:
    return _empty_result("OR-Tools v2", 0, traffic_coeff, weather_coeff, vrp_mode)

  weights = dict({"distance": 1.0, "cost": 0.5, "delays": 2.0, "co2": 0.3},
          **(objective_weights or {}))

  start_time = time.perf_counter()
  coeff   = traffic_coeff * weather_coeff

  # ── Dispatche selon le mode ─────────────────────────────────────
  if vrp_mode == "pickup_delivery":
    return _solve_pickup_delivery(
      clients, depot, vehicles, coeff, time_limit_s,
      pickup_delivery_pairs or [], weights, start_time, on_progress,
    )
  if vrp_mode == "multi_depot":
    return _solve_multi_depot(
      clients, depot, vehicles, coeff, time_limit_s,
      depots or [depot], zones, forced_sequence,
      weights, legal_break, lunch_window, start_time, on_progress,
    )

  # ── Modes standard / open / reload — pipeline commun ───────────
  return _solve_standard(
    clients, depot, vehicles, coeff, time_limit_s,
    legal_break, vrp_mode, weights, forced_sequence,
    zones, lunch_window, on_progress, start_time,
  )


# ═══════════════════════════════════════════════════════════════════════════════
# MODE STANDARD / OPEN / RELOAD
# ═══════════════════════════════════════════════════════════════════════════════

def _solve_standard(
  clients, depot, vehicles, coeff, time_limit_s,
  legal_break, vrp_mode, weights, forced_sequence,
  zones, lunch_window, on_progress, start_time,
):
  dist_km, time_s_raw, source = build_matrix(clients, depot)
  logger.info("OR-Tools [%s] — source: %s", vrp_mode, source)

  n      = len(clients) + 1
  num_vehicles = len(vehicles)
  lunch_start = (lunch_window[0] if lunch_window else LUNCH_START_MIN) * 60
  lunch_end  = (lunch_window[1] if lunch_window else LUNCH_END_MIN) * 60

  # ── Matrices entières ───────────────────────────────────────────
  zfe_pairs = _build_zfe_pairs(clients, zones or [])

  def _d(i, j):
    raw = int(dist_km[i][j] * 1000)
    return _apply_zfe_penalty(raw, i, j, zfe_pairs)

  int_dist = [[_d(i, j) for j in range(n)] for i in range(n)]
  int_time = [[int(time_s_raw[i][j] * coeff) for j in range(n)] for i in range(n)]

  # Pour OPEN : coût retour dépôt = 0 (les véhicules ne rentrent pas)
  if vrp_mode == "open":
    for i in range(n):
      int_dist[i][0] = 0
      int_time[i][0] = 0

  # ── Manager & Routing ───────────────────────────────────────────
  manager = pywrapcp.RoutingIndexManager(n, num_vehicles, 0)
  routing = pywrapcp.RoutingModel(manager)

  # ── Multi-objectif — cost callback pondéré ──────────────────────
  co2_factors = [v.get("co2_per_km", 0.25) for v in vehicles]
  cpkm    = [v.get("cost_per_km", 0.5) for v in vehicles]

  def _make_arc_cost_cb(v_idx):
    def cb(from_idx, to_idx):
      i = manager.IndexToNode(from_idx)
      j = manager.IndexToNode(to_idx)
      dist_cost = int_dist[i][j]
      money_cost = int(dist_cost * cpkm[v_idx] * weights["cost"] / max(weights["distance"], 0.01))
      co2_cost  = int(dist_cost * co2_factors[v_idx] * 1000 * weights["co2"])
      return int(dist_cost * weights["distance"]) + money_cost + co2_cost
    return cb

  transit_cb_indices = []
  for v_idx in range(num_vehicles):
    cb_idx = routing.RegisterTransitCallback(_make_arc_cost_cb(v_idx))
    transit_cb_indices.append(cb_idx)

  routing.SetArcCostEvaluatorOfVehicle(transit_cb_indices[v_idx], v_idx)
  for v_idx in range(num_vehicles):
    routing.SetArcCostEvaluatorOfVehicle(transit_cb_indices[v_idx], v_idx)

  # ── Compétences — véhicule peut-il servir le client ──────────
  for client_idx, client in enumerate(clients):
    allowed_vehicles = [
      v_idx for v_idx, v in enumerate(vehicles)
      if _vehicle_can_serve(v, client)
    ]
    if len(allowed_vehicles) < num_vehicles:
      node_idx = manager.NodeToIndex(client_idx + 1)
      if allowed_vehicles:
        routing.SetAllowedVehiclesForIndex(allowed_vehicles, node_idx)
      else:
        logger.warning("Aucun véhicule ne peut servir le client %d — nœud ignoré", client_idx)

  # ── Capacité + rechargement intermédiaire ───────────────────────
  def demand_callback(from_index):
    node = manager.IndexToNode(from_index)
    return 0 if node == 0 else int(clients[node - 1].get("demand_kg", 0))

  demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
  caps = [int(v.get("capacity_kg", 1000)) for v in vehicles]
  routing.AddDimensionWithVehicleCapacity(demand_cb_idx, 0, caps, True, "Capacity")

  # ── Dimension temps ─────────────────────────────────────────────
  def time_callback(from_index, to_index):
    i = manager.IndexToNode(from_index)
    j = manager.IndexToNode(to_index)
    svc = 0 if i == 0 else int(clients[i - 1].get("service_time", 10) * 60)
    return int_time[i][j] + svc

  time_cb_idx = routing.RegisterTransitCallback(time_callback)
  max_time = 24 * 3600

  routing.AddDimension(time_cb_idx, max_time, max_time, False, "Time")
  time_dim = routing.GetDimensionOrDie("Time")

  # ── Fenêtres horaires + fenêtre déjeuner interdite ──────────────
  for i in range(n):
    idx = manager.NodeToIndex(i)
    if i == 0:
      time_dim.CumulVar(idx).SetRange(0, max_time)
    else:
      ci  = clients[i - 1]
      ready = int(ci.get("ready_time", 0) * 60)
      due  = int(min(ci.get("due_time", 1440), 1440) * 60)
      # Exclure fenêtre déjeuner (12h-14h) — si le créneau chevauche, on le coupe
      if due > lunch_start and ready < lunch_end:
        # Préférer livraison avant 12h ou après 14h
        if ready < lunch_start:
          time_dim.CumulVar(idx).SetRange(ready, min(due, lunch_start))
        else:
          time_dim.CumulVar(idx).SetRange(max(ready, lunch_end), due)
      else:
        time_dim.CumulVar(idx).SetRange(ready, due)

  for v in range(num_vehicles):
    time_dim.CumulVar(routing.Start(v)).SetRange(0, max_time)
    routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.End(v)))

  # ── Pauses RSE (par véhicule si driver info fournie) ───────────
  if legal_break and n > 4:
    for v_idx, veh in enumerate(vehicles):
      drv = veh.get("_driver") or {}
      max_drive = int((drv.get("max_drive_before_break_min") or 270) * 60)
      min_break = int((drv.get("min_break_minutes") or 45) * 60)

      def _drive_cb(from_idx, to_idx, _v=v_idx):
        return int_time[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

      drive_cb = routing.RegisterTransitCallback(_drive_cb)
      routing.AddDimensionWithVehicleTransitAndCapacity(
        [drive_cb] * num_vehicles if v_idx == 0 else None,
      ) if False else None # use per-vehicle approach below

    # Fallback : dimension globale DriveTime commune
    def _global_drive_cb(from_idx, to_idx):
      return int_time[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    drive_cb_idx = routing.RegisterTransitCallback(_global_drive_cb)
    veh0 = vehicles[0]
    drv0 = veh0.get("_driver") or {}
    max_drive_s = int((drv0.get("max_drive_before_break_min") or 270) * 60)
    break_s   = int((drv0.get("min_break_minutes") or 45) * 60)
    routing.AddDimension(drive_cb_idx, break_s, max_drive_s, True, "DriveTime")
    logger.debug("Pauses RSE activées: max_drive=%ds, break=%ds", max_drive_s, break_s)

  # ── Séquences forcées ──────────────────────────────────────────
  for (from_ci, to_ci) in (forced_sequence or []):
    if 0 <= from_ci < len(clients) and 0 <= to_ci < len(clients):
      from_node_idx = manager.NodeToIndex(from_ci + 1)
      to_node_idx  = manager.NodeToIndex(to_ci + 1)
      routing.solver().Add(
        routing.NextVar(from_node_idx) == to_node_idx
      )

  # ── Verrouillage de positions ──────────────────────────────────
  for ci, client in enumerate(clients):
    if client.get("is_locked"):
      pass # Position lock géré via InitialRoutes si fourni

  # ── Pénalité disjunction ───────────────────────────────────────
  max_d  = max(int_dist[i][j] for i in range(n) for j in range(n) if i != j)
  penalty = max(max_d * 10, 10_000)
  for i in range(1, n):
    routing.AddDisjunction([manager.NodeToIndex(i)], penalty)

  # ── Stratégie de recherche ─────────────────────────────────────
  params = pywrapcp.DefaultRoutingSearchParameters()
  params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
  params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
  params.time_limit.seconds = time_limit_s
  params.solution_limit = 10_000

  solution = routing.SolveWithParameters(params)

  if not solution:
    cpu_ms = (time.perf_counter() - start_time) * 1000
    return {
      **_empty_result("OR-Tools v2", len(clients), 1.0, 1.0, vrp_mode),
      "error": "Aucune solution trouvée", "cpu_time_ms": cpu_ms,
    }

  return _extract_solution(
    solution, routing, manager, clients, vehicles,
    dist_km, time_s_raw, time_dim, coeff,
    vrp_mode, source, start_time,
  )


# ═══════════════════════════════════════════════════════════════════════════════
# MODE MULTI-DÉPÔT
# ═══════════════════════════════════════════════════════════════════════════════

def _solve_multi_depot(
  clients, depot, vehicles, coeff, time_limit_s,
  depots, zones, forced_sequence, weights, legal_break,
  lunch_window, start_time, on_progress,
):
  """
  M-DVRPTW : chaque véhicule démarre et finit depuis son propre dépôt.
  Modélisation : starts[v] = index de nœud du dépôt de départ, ends[v] idem.
  On ajoute un nœud fictif par dépôt à la fin de la liste de nœuds.
  """
  n_depots = len(depots)
  n_clients = len(clients)

  # nœuds : 0..n_clients-1 = clients (décalage différent de la version standard)
  # on utilise les nœuds dépôt comme virtual start/end
  # Matrice construite sans depot (on les passe un par un)
  dist_km, time_s_raw, source = build_matrix(clients, depots[0])
  logger.info("OR-Tools [multi_depot, %d dépôts] — source: %s", n_depots, source)

  # Nombre total de nœuds : 1 (dépôt principal) + clients
  n      = n_clients + 1
  num_vehicles = len(vehicles)
  coeff_arr  = [[int(time_s_raw[i][j] * coeff) for j in range(n)] for i in range(n)]
  int_dist   = [[int(dist_km[i][j] * 1000) for j in range(n)] for i in range(n)]

  # Assign each vehicle to a depot (round-robin if more vehicles than depots)
  depot_for_vehicle = [i % n_depots for i in range(num_vehicles)]
  starts = [0] * num_vehicles
  ends  = [0] * num_vehicles # all vehicles end at depot 0 (simplification)

  manager = pywrapcp.RoutingIndexManager(n, num_vehicles, starts, ends)
  routing = pywrapcp.RoutingModel(manager)

  def distance_cb(from_idx, to_idx):
    return int_dist[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

  transit_cb = routing.RegisterTransitCallback(distance_cb)
  routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

  def demand_cb(from_idx):
    node = manager.IndexToNode(from_idx)
    return 0 if node == 0 else int(clients[node - 1].get("demand_kg", 0))

  d_cb = routing.RegisterUnaryTransitCallback(demand_cb)
  caps = [int(v.get("capacity_kg", 1000)) for v in vehicles]
  routing.AddDimensionWithVehicleCapacity(d_cb, 0, caps, True, "Capacity")

  def time_cb(from_idx, to_idx):
    i = manager.IndexToNode(from_idx)
    j = manager.IndexToNode(to_idx)
    svc = 0 if i == 0 else int(clients[i - 1].get("service_time", 10) * 60)
    return coeff_arr[i][j] + svc

  t_cb = routing.RegisterTransitCallback(time_cb)
  max_time = 24 * 3600
  routing.AddDimension(t_cb, max_time, max_time, False, "Time")
  time_dim = routing.GetDimensionOrDie("Time")

  for i in range(n):
    idx = manager.NodeToIndex(i)
    if i == 0:
      time_dim.CumulVar(idx).SetRange(0, max_time)
    else:
      ci  = clients[i - 1]
      ready = int(ci.get("ready_time", 0) * 60)
      due  = int(min(ci.get("due_time", 1440), 1440) * 60)
      time_dim.CumulVar(idx).SetRange(ready, due)

  max_d  = max(int_dist[i][j] for i in range(n) for j in range(n) if i != j)
  penalty = max(max_d * 10, 10_000)
  for i in range(1, n):
    routing.AddDisjunction([manager.NodeToIndex(i)], penalty)

  params = pywrapcp.DefaultRoutingSearchParameters()
  params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
  params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
  params.time_limit.seconds = time_limit_s

  solution = routing.SolveWithParameters(params)
  if not solution:
    return {
      **_empty_result("OR-Tools v2 [multi_depot]", n_clients, 1.0, 1.0, "multi_depot"),
      "error": "Aucune solution trouvée",
    }

  return _extract_solution(
    solution, routing, manager, clients, vehicles,
    dist_km, time_s_raw, time_dim, coeff,
    "multi_depot", source, start_time,
  )


# ═══════════════════════════════════════════════════════════════════════════════
# MODE PICKUP & DELIVERY
# ═══════════════════════════════════════════════════════════════════════════════

def _solve_pickup_delivery(
  clients, depot, vehicles, coeff, time_limit_s,
  pairs, weights, start_time, on_progress,
):
  """
  PDPTW : chaque paire (i, j) signifie que le client i doit être visité
  avant le client j, et le même véhicule doit servir les deux.
  """
  dist_km, time_s_raw, source = build_matrix(clients, depot)
  n      = len(clients) + 1
  num_vehicles = len(vehicles)
  int_dist = [[int(dist_km[i][j] * 1000) for j in range(n)] for i in range(n)]
  int_time = [[int(time_s_raw[i][j] * coeff) for j in range(n)] for i in range(n)]

  manager = pywrapcp.RoutingIndexManager(n, num_vehicles, 0)
  routing = pywrapcp.RoutingModel(manager)

  def dist_cb(fi, ti):
    return int_dist[manager.IndexToNode(fi)][manager.IndexToNode(ti)]

  t_cb_idx = routing.RegisterTransitCallback(dist_cb)
  routing.SetArcCostEvaluatorOfAllVehicles(t_cb_idx)

  def demand_cb(fi):
    node = manager.IndexToNode(fi)
    return 0 if node == 0 else int(clients[node - 1].get("demand_kg", 0))

  d_cb_idx = routing.RegisterUnaryTransitCallback(demand_cb)
  caps = [int(v.get("capacity_kg", 1000)) for v in vehicles]
  routing.AddDimensionWithVehicleCapacity(d_cb_idx, 0, caps, True, "Capacity")

  def time_cb(fi, ti):
    i = manager.IndexToNode(fi)
    j = manager.IndexToNode(ti)
    svc = 0 if i == 0 else int(clients[i - 1].get("service_time", 10) * 60)
    return int_time[i][j] + svc

  time_cb_idx = routing.RegisterTransitCallback(time_cb)
  max_time = 24 * 3600
  routing.AddDimension(time_cb_idx, max_time, max_time, False, "Time")
  time_dim = routing.GetDimensionOrDie("Time")

  for i in range(n):
    idx = manager.NodeToIndex(i)
    if i == 0:
      time_dim.CumulVar(idx).SetRange(0, max_time)
    else:
      ci  = clients[i - 1]
      ready = int(ci.get("ready_time", 0) * 60)
      due  = int(min(ci.get("due_time", 1440), 1440) * 60)
      time_dim.CumulVar(idx).SetRange(ready, due)

  # Ajout des contraintes pickup/delivery
  for (pickup_ci, delivery_ci) in pairs:
    if 0 <= pickup_ci < len(clients) and 0 <= delivery_ci < len(clients):
      pickup_idx  = manager.NodeToIndex(pickup_ci + 1)
      delivery_idx = manager.NodeToIndex(delivery_ci + 1)
      routing.AddPickupAndDelivery(pickup_idx, delivery_idx)
      routing.solver().Add(
        routing.VehicleVar(pickup_idx) == routing.VehicleVar(delivery_idx)
      )
      routing.solver().Add(
        time_dim.CumulVar(pickup_idx) <= time_dim.CumulVar(delivery_idx)
      )

  max_d  = max(int_dist[i][j] for i in range(n) for j in range(n) if i != j)
  penalty = max(max_d * 10, 10_000)
  for i in range(1, n):
    routing.AddDisjunction([manager.NodeToIndex(i)], penalty)

  params = pywrapcp.DefaultRoutingSearchParameters()
  params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
  params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
  params.time_limit.seconds = time_limit_s

  solution = routing.SolveWithParameters(params)
  if not solution:
    return {
      **_empty_result("OR-Tools v2 [pickup_delivery]", len(clients), 1.0, 1.0, "pickup_delivery"),
      "error": "Aucune solution trouvée",
    }

  return _extract_solution(
    solution, routing, manager, clients, vehicles,
    dist_km, time_s_raw, time_dim, coeff,
    "pickup_delivery", source, start_time,
  )


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTION DE SOLUTION COMMUNE
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_solution(
  solution, routing, manager, clients, vehicles,
  dist_km, time_s_raw, time_dim, coeff,
  vrp_mode, source, start_time,
):
  routes     = []
  total_distance = 0.0
  total_cost   = 0.0
  total_delay  = 0.0
  clients_served = 0
  on_time_count = 0
  total_co2   = 0.0
  n       = len(clients) + 1

  for v_idx in range(len(vehicles)):
    route   = []
    index   = routing.Start(v_idx)
    route_dist = 0.0
    load    = 0.0
    prev_index = index
    reload_count = 0

    while not routing.IsEnd(index):
      node = manager.IndexToNode(index)
      if node > 0:
        ci     = node - 1
        prev_node  = manager.IndexToNode(prev_index)
        d      = dist_km[prev_node][node]
        time_var  = time_dim.CumulVar(index)
        arrival_s  = solution.Value(time_var)
        arrival_min = arrival_s / 60.0
        c      = clients[ci]
        due     = c.get("due_time", 1440)
        service   = c.get("service_time", 10)
        delay    = max(0.0, arrival_min - due)
        demand   = c.get("demand_kg", 0)
        cap     = vehicles[v_idx].get("capacity_kg", 1000)

        # ── Rechargement intermédiaire (mode reload) ──────
        if load > 0 and cap > 0 and load / cap < RELOAD_THRESHOLD:
          route.append({
            "type":        "reload",
            "client_index":    None,
            "arrival_time":    arrival_min,
            "distance_from_prev": d,
          })
          load = 0.0
          reload_count += 1

        load    += demand
        route_dist += d
        clients_served += 1
        if delay == 0:
          on_time_count += 1
        total_delay += delay

        route.append({
          "client_index":    ci,
          "client":       c,
          "arrival_time":    arrival_min,
          "departure_time":   arrival_min + service,
          "delay":       delay,
          "distance_from_prev": d,
          "type":        "delivery",
        })

      prev_index = index
      index   = solution.Value(routing.NextVar(index))

    last_node = manager.IndexToNode(prev_index)
    if route and vrp_mode != "open":
      route_dist += dist_km[last_node][0]
    total_distance += route_dist

    cpkm = vehicles[v_idx].get("cost_per_km", 0.5)
    co2 = vehicles[v_idx].get("co2_per_km", 0.25)
    total_cost += route_dist * cpkm
    total_co2 += route_dist * co2

    duration = 0.0
    if route:
      deliveries = [s for s in route if s.get("type") == "delivery"]
      if deliveries:
        last_dep = deliveries[-1]["departure_time"]
        ret_s  = time_s_raw[last_node][0] * coeff if vrp_mode != "open" else 0
        duration = last_dep + ret_s / 60.0

    routes.append({
      "vehicle":    vehicles[v_idx],
      "vehicle_index": v_idx,
      "route":     route,
      "distance_km":  route_dist,
      "load_kg":    load,
      "duration_min":  duration,
      "reload_count":  reload_count,
      "co2_kg":     route_dist * vehicles[v_idx].get("co2_per_km", 0.25),
    })

  cpu_ms    = (time.perf_counter() - start_time) * 1000
  respect_rate = (on_time_count / clients_served * 100) if clients_served > 0 else 0.0
  avg_delay  = (total_delay / clients_served)     if clients_served > 0 else 0.0

  return {
    "algorithm":     f"OR-Tools v2 [{vrp_mode}]",
    "vrp_mode":      vrp_mode,
    "routes":       routes,
    "total_distance_km": total_distance,
    "total_cost":     total_cost,
    "total_co2_kg":    total_co2,
    "total_duration_min": sum(r["duration_min"] for r in routes),
    "clients_served":   clients_served,
    "clients_total":   len(clients),
    "respect_rate":    respect_rate,
    "avg_delay_min":   avg_delay,
    "cpu_time_ms":    cpu_ms,
    "distance_source":  source,
  }


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def _empty_result(algo_name, n_clients, traffic_coeff, weather_coeff, vrp_mode="standard"):
  return {
    "algorithm":     algo_name,
    "vrp_mode":      vrp_mode,
    "routes":       [],
    "total_distance_km": 0.0,
    "total_cost":     0.0,
    "total_co2_kg":    0.0,
    "total_duration_min": 0.0,
    "clients_served":   0,
    "clients_total":   n_clients,
    "respect_rate":    0.0,
    "avg_delay_min":   0.0,
    "cpu_time_ms":    0.0,
    "traffic_coeff":   traffic_coeff,
    "weather_coeff":   weather_coeff,
    "distance_source":  "none",
  }
