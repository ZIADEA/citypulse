import time
import random
from .distance import build_distance_matrix
from .greedy import greedy_vrp


def two_opt_improve(route_indices, dist_matrix):
    improved = True
    best_distance = _route_distance(route_indices, dist_matrix)
    convergence = [best_distance]
    iteration = 0

    while improved:
        improved = False
        for i in range(1, len(route_indices) - 1):
            for j in range(i + 1, len(route_indices)):
                new_route = route_indices[:i] + route_indices[i:j + 1][::-1] + route_indices[j + 1:]
                new_dist = _route_distance(new_route, dist_matrix)
                if new_dist < best_distance - 1e-10:
                    route_indices = new_route
                    best_distance = new_dist
                    improved = True
                    convergence.append(best_distance)
                    break
            if improved:
                break
        iteration += 1

    return route_indices, best_distance, convergence


def _route_distance(route, dist_matrix):
    d = 0.0
    for i in range(len(route) - 1):
        d += dist_matrix[route[i]][route[i + 1]]
    return d


def two_opt_vrp(clients, depot, vehicles, traffic_coeff=1.0, weather_coeff=1.0, max_iterations=1000):
    start_time = time.perf_counter()
    coeff = traffic_coeff * weather_coeff

    # Start from greedy solution
    greedy_result = greedy_vrp(clients, depot, vehicles, traffic_coeff, weather_coeff)
    dist_matrix = build_distance_matrix(clients, depot)

    all_convergence = []
    improved_routes = []
    total_distance = 0.0
    total_cost = 0.0
    total_delay = 0.0
    clients_served = 0
    on_time_count = 0

    for gr in greedy_result["routes"]:
        if not gr["route"]:
            improved_routes.append(gr)
            continue

        vehicle = gr["vehicle"]
        # Build index list: depot -> clients -> depot
        route_indices = [0] + [r["client_index"] + 1 for r in gr["route"]] + [0]

        opt_route, opt_dist, convergence = two_opt_improve(route_indices, dist_matrix)
        all_convergence.extend(convergence)

        # Rebuild route with timing
        route_clients = []
        current_time = 0.0
        load = 0.0
        for k in range(1, len(opt_route) - 1):
            ci = opt_route[k] - 1  # client index
            d = dist_matrix[opt_route[k - 1]][opt_route[k]]
            travel_time = (d / vehicle.get("max_speed_kmh", 60)) * 60 * coeff
            arrival = current_time + travel_time
            ready = clients[ci].get("ready_time", 0)
            due = clients[ci].get("due_time", 1440)
            service = clients[ci].get("service_time", 10)

            if arrival < ready:
                arrival = ready
            delay = max(0, arrival - due)
            current_time = arrival + service
            load += clients[ci].get("demand_kg", 0)

            if delay == 0:
                on_time_count += 1
            total_delay += delay
            clients_served += 1

            route_clients.append({
                "client_index": ci,
                "client": clients[ci],
                "arrival_time": arrival,
                "departure_time": current_time,
                "delay": delay,
                "distance_from_prev": d,
            })

        return_dist = dist_matrix[opt_route[-2]][0]
        total_distance += opt_dist
        total_cost += opt_dist * vehicle.get("cost_per_km", 0.5)

        improved_routes.append({
            "vehicle": vehicle,
            "vehicle_index": gr["vehicle_index"],
            "route": route_clients,
            "distance_km": opt_dist,
            "load_kg": load,
            "duration_min": current_time + (return_dist / vehicle.get("max_speed_kmh", 60)) * 60 * coeff,
        })

    cpu_time = (time.perf_counter() - start_time) * 1000
    respect_rate = (on_time_count / clients_served * 100) if clients_served > 0 else 0
    avg_delay = (total_delay / clients_served) if clients_served > 0 else 0
    greedy_dist = greedy_result["total_distance_km"]
    gain = ((greedy_dist - total_distance) / greedy_dist * 100) if greedy_dist > 0 else 0

    return {
        "algorithm": "2-opt (Amélioration locale)",
        "routes": improved_routes,
        "total_distance_km": total_distance,
        "total_cost": total_cost,
        "total_duration_min": sum(r["duration_min"] for r in improved_routes),
        "clients_served": clients_served,
        "clients_total": len(clients),
        "respect_rate": respect_rate,
        "avg_delay_min": avg_delay,
        "cpu_time_ms": cpu_time,
        "gain_vs_greedy": gain,
        "convergence": all_convergence,
        "traffic_coeff": traffic_coeff,
        "weather_coeff": weather_coeff,
    }
