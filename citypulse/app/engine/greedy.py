import time
from .distance import build_distance_matrix


def greedy_vrp(clients, depot, vehicles, traffic_coeff=1.0, weather_coeff=1.0):
    """
    Nearest Neighbor greedy algorithm for VRPTW.
    Returns routes per vehicle with metrics.
    """
    start_time = time.perf_counter()
    coeff = traffic_coeff * weather_coeff
    dist_matrix = build_distance_matrix(clients, depot)
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
        current = 0  # depot index
        current_time = 0.0
        route_dist = 0.0

        while True:
            best_client = -1
            best_dist = float('inf')
            for i in range(n_clients):
                if visited[i]:
                    continue
                ci = i + 1  # offset by 1 for depot
                d = dist_matrix[current][ci]
                new_load = load + clients[i].get("demand_kg", 0)
                if new_load > vehicle.get("capacity_kg", 1000):
                    continue
                if d < best_dist:
                    best_dist = d
                    best_client = i

            if best_client == -1:
                break

            ci = best_client + 1
            travel_time = (best_dist / vehicle.get("max_speed_kmh", 60)) * 60 * coeff
            arrival = current_time + travel_time
            ready = clients[best_client].get("ready_time", 0)
            due = clients[best_client].get("due_time", 1440)
            service = clients[best_client].get("service_time", 10)

            if arrival < ready:
                arrival = ready
            delay = max(0, arrival - due)

            visited[best_client] = True
            load += clients[best_client].get("demand_kg", 0)
            route_dist += best_dist
            current_time = arrival + service
            current = ci

            if delay == 0:
                on_time_count += 1
            total_delay += delay
            clients_served += 1

            route.append({
                "client_index": best_client,
                "client": clients[best_client],
                "arrival_time": arrival,
                "departure_time": current_time,
                "delay": delay,
                "distance_from_prev": best_dist,
            })

        # Return to depot
        if route:
            return_dist = dist_matrix[current][0]
            route_dist += return_dist
            total_distance += route_dist
            total_cost += route_dist * vehicle.get("cost_per_km", 0.5)

        routes.append({
            "vehicle": vehicle,
            "vehicle_index": v_idx,
            "route": route,
            "distance_km": route_dist,
            "load_kg": load,
            "duration_min": current_time + (dist_matrix[current][0] / vehicle.get("max_speed_kmh", 60)) * 60 * coeff if route else 0,
        })

    cpu_time = (time.perf_counter() - start_time) * 1000
    respect_rate = (on_time_count / clients_served * 100) if clients_served > 0 else 0
    avg_delay = (total_delay / clients_served) if clients_served > 0 else 0

    return {
        "algorithm": "Glouton (Nearest Neighbor)",
        "routes": routes,
        "total_distance_km": total_distance,
        "total_cost": total_cost,
        "total_duration_min": sum(r["duration_min"] for r in routes),
        "clients_served": clients_served,
        "clients_total": n_clients,
        "respect_rate": respect_rate,
        "avg_delay_min": avg_delay,
        "cpu_time_ms": cpu_time,
        "traffic_coeff": traffic_coeff,
        "weather_coeff": weather_coeff,
    }
