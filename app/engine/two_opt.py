"""
two_opt.py — Optimisation locale 2-opt pour VRPTW
===================================================
Corrections clés par rapport à l'ancienne version :
 1. Validation des fenêtres horaires après chaque swap (bug critique corrigé)
 2. Utilise time_s OSRM pour les calculs d'arrivée
 3. Sélection selon dist_km (minimiser la distance)
"""

import time
import logging
from .distance import build_matrix
from .greedy import greedy_vrp, _empty_result

logger = logging.getLogger(__name__)


# ── Validation fenêtres horaires ───────────────────────────────────────────────
def _is_feasible(route_indices, dist_km, time_s, clients, coeff):
  """
  Vérifie qu'une séquence route_indices respecte toutes les fenêtres horaires.
  route_indices : [0, c1, c2, ..., cn, 0] (0 = dépôt)
  """
  current_time = 0.0
  for k in range(1, len(route_indices) - 1):
    prev_i = route_indices[k - 1]
    curr_i = route_indices[k]
    travel_min = (time_s[prev_i][curr_i] * coeff) / 60.0
    current_time += travel_min
    ci = curr_i - 1 # index client
    ready  = clients[ci].get("ready_time", 0)
    due   = clients[ci].get("due_time", 1440)
    service = clients[ci].get("service_time", 10)
    if current_time < ready:
      current_time = ready
    if current_time > due:
      return False  # Violation détectée → swap refusé
    current_time += service
  return True


# ── Distance d'une route ───────────────────────────────────────────────────────
def _route_distance(route, dist_km):
  return sum(dist_km[route[i]][route[i + 1]] for i in range(len(route) - 1))


# ── Amélioration 2-opt avec feasibility check ─────────────────────────────────
def two_opt_improve(route_indices, dist_km, time_s, clients, coeff, max_iter=1000):
  """
  2-opt classique — n'accepte un swap que si :
   1. La nouvelle distance est meilleure
   2. Les fenêtres horaires sont respectées (correction bug critique)
  """
  best_distance = _route_distance(route_indices, dist_km)
  convergence  = [best_distance]
  improved   = True
  iterations  = 0

  while improved and iterations < max_iter:
    improved = False
    for i in range(1, len(route_indices) - 1):
      for j in range(i + 1, len(route_indices)):
        new_route = (
          route_indices[:i]
          + route_indices[i:j + 1][::-1]
          + route_indices[j + 1:]
        )
        new_dist = _route_distance(new_route, dist_km)

        # ── Condition 1 : meilleure distance ──
        if new_dist >= best_distance - 1e-10:
          continue

        # ── Condition 2 : fenêtres horaires respectées ──
        if not _is_feasible(new_route, dist_km, time_s, clients, coeff):
          continue

        route_indices = new_route
        best_distance = new_dist
        improved   = True
        convergence.append(best_distance)
        break

      if improved:
        break
    iterations += 1

  return route_indices, best_distance, convergence


# ── Calcul des timings sur une route optimisée ────────────────────────────────
def _build_route_stops(opt_route, dist_km, time_s, clients, coeff, vehicle):
  """Reconstruit la liste des arrêts avec timings précis."""
  stops    = []
  current_time = 0.0
  load     = 0.0
  on_time   = 0
  total_delay = 0.0

  for k in range(1, len(opt_route) - 1):
    prev_i = opt_route[k - 1]
    curr_i = opt_route[k]
    ci   = curr_i - 1 # index client

    travel_min  = (time_s[prev_i][curr_i] * coeff) / 60.0
    dist_leg   = dist_km[prev_i][curr_i]
    arrival   = current_time + travel_min
    ready    = clients[ci].get("ready_time", 0)
    due     = clients[ci].get("due_time", 1440)
    service   = clients[ci].get("service_time", 10)

    if arrival < ready:
      arrival = ready
    delay = max(0.0, arrival - due)
    current_time = arrival + service
    load += clients[ci].get("demand_kg", 0)

    if delay == 0:
      on_time += 1
    total_delay += delay

    stops.append({
      "client_index":    ci,
      "client":       clients[ci],
      "arrival_time":    arrival,
      "departure_time":   current_time,
      "delay":       delay,
      "distance_from_prev": dist_leg,
      "type":        "delivery",
    })

  return stops, load, current_time, on_time, total_delay


# ── Point d'entrée principal ───────────────────────────────────────────────────
def two_opt_vrp(clients, depot, vehicles, traffic_coeff=1.0, weather_coeff=1.0,
        max_iterations=1000):
  if not clients:
    return _empty_result("2-opt (Amélioration locale)", 0, traffic_coeff, weather_coeff)

  start_time = time.perf_counter()
  coeff = traffic_coeff * weather_coeff

  # Solution initiale glouton
  greedy_result = greedy_vrp(clients, depot, vehicles, traffic_coeff, weather_coeff)
  dist_km, time_s, source = build_matrix(clients, depot)
  logger.info("2-opt — source distance: %s", source)

  all_convergence = []
  improved_routes = []
  total_distance = 0.0
  total_cost   = 0.0
  total_delay   = 0.0
  clients_served = 0
  on_time_count  = 0

  for gr in greedy_result["routes"]:
    if not gr["route"]:
      improved_routes.append(gr)
      continue

    vehicle   = gr["vehicle"]
    route_indices = [0] + [r["client_index"] + 1 for r in gr["route"]] + [0]

    opt_route, opt_dist, convergence = two_opt_improve(
      route_indices, dist_km, time_s, clients, coeff, max_iterations
    )
    all_convergence.extend(convergence)

    stops, load, end_time, on_time, route_delay = _build_route_stops(
      opt_route, dist_km, time_s, clients, coeff, vehicle
    )

    on_time_count += on_time
    total_delay  += route_delay
    clients_served += len(stops)

    last_i   = opt_route[-2]
    return_min = (time_s[last_i][0] * coeff) / 60.0
    total_distance += opt_dist
    total_cost   += opt_dist * vehicle.get("cost_per_km", 0.5)

    improved_routes.append({
      "vehicle":    vehicle,
      "vehicle_index": gr["vehicle_index"],
      "route":     stops,
      "distance_km":  opt_dist,
      "load_kg":    load,
      "duration_min": end_time + return_min,
    })

  cpu_time   = (time.perf_counter() - start_time) * 1000
  respect_rate = (on_time_count / clients_served * 100) if clients_served > 0 else 0.0
  avg_delay  = (total_delay / clients_served)     if clients_served > 0 else 0.0
  greedy_dist = greedy_result["total_distance_km"]
  gain     = ((greedy_dist - total_distance) / greedy_dist * 100) if greedy_dist > 0 else 0.0

  return {
    "algorithm":     "2-opt (Amélioration locale)",
    "routes":       improved_routes,
    "total_distance_km": total_distance,
    "total_cost":     total_cost,
    "total_duration_min": sum(r["duration_min"] for r in improved_routes),
    "clients_served":   clients_served,
    "clients_total":   len(clients),
    "respect_rate":    respect_rate,
    "avg_delay_min":   avg_delay,
    "cpu_time_ms":    cpu_time,
    "gain_vs_greedy":   gain,
    "convergence":    all_convergence,
    "traffic_coeff":   traffic_coeff,
    "weather_coeff":   weather_coeff,
    "distance_source":  source,
  }
