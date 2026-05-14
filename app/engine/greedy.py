"""
greedy.py — Algorithme glouton VRPTW (Nearest Neighbor)
=========================================================
Utilise build_matrix() pour les distances routières OSRM
et time_s pour calculer les arrivées exactes.
"""

import time
import logging
from .distance import build_matrix

logger = logging.getLogger(__name__)


def greedy_vrp(clients, depot, vehicles, traffic_coeff=1.0, weather_coeff=1.0):
  """
  Nearest Neighbor greedy pour VRPTW.

  Retourne un dict de résultats complet compatible avec OptimizationService.
  """
  if not clients:
    return _empty_result("Glouton (Nearest Neighbor)", 0, traffic_coeff, weather_coeff)

  start_time = time.perf_counter()
  coeff = traffic_coeff * weather_coeff

  dist_km, time_s, source = build_matrix(clients, depot)
  logger.info("Greedy — source distance: %s", source)

  n_clients = len(clients)
  visited = [False] * n_clients
  routes = []
  total_distance = 0.0
  total_cost = 0.0
  total_delay = 0.0
  clients_served = 0
  on_time_count = 0

  for v_idx, vehicle in enumerate(vehicles):
    if all(visited):
      break

    route = []
    load = 0.0
    current = 0     # indice dépôt dans la matrice
    current_time = 0.0  # minutes depuis départ
    route_dist = 0.0

    while True:
      best_client = -1
      best_time = float("inf")

      for i in range(n_clients):
        if visited[i]:
          continue
        ci = i + 1 # offset dépôt
        new_load = load + clients[i].get("demand_kg", 0)
        if new_load > vehicle.get("capacity_kg", 1000):
          continue

        # Temps de trajet en minutes (depuis time_s OSRM × coeff)
        travel_min = (time_s[current][ci] * coeff) / 60.0
        arrival = current_time + travel_min
        ready  = clients[i].get("ready_time", 0)
        if arrival < ready:
          arrival = ready

        # Sélectionner selon le temps (plus fidèle aux fenêtres horaires)
        if travel_min < best_time:
          best_time = travel_min
          best_client = i

      if best_client == -1:
        break

      ci = best_client + 1
      travel_min = (time_s[current][ci] * coeff) / 60.0
      dist_leg  = dist_km[current][ci]
      arrival  = current_time + travel_min
      ready   = clients[best_client].get("ready_time", 0)
      due    = clients[best_client].get("due_time", 1440)
      service  = clients[best_client].get("service_time", 10)

      if arrival < ready:
        arrival = ready
      delay = max(0.0, arrival - due)

      visited[best_client] = True
      load     += clients[best_client].get("demand_kg", 0)
      route_dist  += dist_leg
      current_time = arrival + service
      current    = ci

      if delay == 0:
        on_time_count += 1
      total_delay  += delay
      clients_served += 1

      route.append({
        "client_index":   best_client,
        "client":      clients[best_client],
        "arrival_time":   arrival,
        "departure_time":  current_time,
        "delay":       delay,
        "distance_from_prev": dist_leg,
        "type":        "delivery",
      })

    # Retour au dépôt
    return_dist = dist_km[current][0] if route else 0.0
    return_time = (time_s[current][0] * coeff) / 60.0 if route else 0.0
    route_dist += return_dist
    total_distance += route_dist
    total_cost   += route_dist * vehicle.get("cost_per_km", 0.5)

    routes.append({
      "vehicle":    vehicle,
      "vehicle_index": v_idx,
      "route":     route,
      "distance_km":  route_dist,
      "load_kg":    load,
      "duration_min": (current_time + return_time) if route else 0.0,
    })

  cpu_time   = (time.perf_counter() - start_time) * 1000
  respect_rate = (on_time_count / clients_served * 100) if clients_served > 0 else 0.0
  avg_delay  = (total_delay / clients_served)     if clients_served > 0 else 0.0

  return {
    "algorithm":    "Glouton (Nearest Neighbor)",
    "routes":      routes,
    "total_distance_km": total_distance,
    "total_cost":    total_cost,
    "total_duration_min": sum(r["duration_min"] for r in routes),
    "clients_served":  clients_served,
    "clients_total":  n_clients,
    "respect_rate":   respect_rate,
    "avg_delay_min":  avg_delay,
    "cpu_time_ms":   cpu_time,
    "traffic_coeff":  traffic_coeff,
    "weather_coeff":  weather_coeff,
    "distance_source": source,
  }


def _empty_result(algo_name, n_clients, traffic_coeff, weather_coeff):
  return {
    "algorithm": algo_name,
    "routes": [],
    "total_distance_km": 0.0,
    "total_cost": 0.0,
    "total_duration_min": 0.0,
    "clients_served": 0,
    "clients_total": n_clients,
    "respect_rate": 0.0,
    "avg_delay_min": 0.0,
    "cpu_time_ms": 0.0,
    "traffic_coeff": traffic_coeff,
    "weather_coeff": weather_coeff,
    "distance_source": "none",
  }
