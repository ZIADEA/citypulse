import time
from .distance import build_distance_matrix

try:
    from ortools.constraint_solver import routing_enums_pb2, pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False


def ortools_vrp(clients, depot, vehicles, traffic_coeff=1.0, weather_coeff=1.0, time_limit_s=30):
    if not ORTOOLS_AVAILABLE:
        return {"error": "OR-Tools non installé. Installez avec: pip install ortools"}

    start_time = time.perf_counter()
    coeff = traffic_coeff * weather_coeff
    dist_matrix = build_distance_matrix(clients, depot)
    n = len(clients) + 1  # +1 for depot
    num_vehicles = len(vehicles)

    # Scale distances to integers (meters)
    int_dist = [[int(dist_matrix[i][j] * 1000) for j in range(n)] for i in range(n)]

    # Time matrix in minutes (scaled to int seconds)
    avg_speed = sum(v.get("max_speed_kmh", 60) for v in vehicles) / len(vehicles)
    int_time = [[int(dist_matrix[i][j] / avg_speed * 3600 * coeff) for j in range(n)] for i in range(n)]

    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int_dist[from_node][to_node]

    transit_cb_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    # Capacity constraint
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        if from_node == 0:
            return 0
        return int(clients[from_node - 1].get("demand_kg", 0))

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    caps = [int(v.get("capacity_kg", 1000)) for v in vehicles]
    routing.AddDimensionWithVehicleCapacity(demand_cb_idx, 0, caps, True, "Capacity")

    # Time windows
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel = int_time[from_node][to_node]
        service = 0
        if from_node > 0:
            service = int(clients[from_node - 1].get("service_time", 10) * 60)
        return travel + service

    time_cb_idx = routing.RegisterTransitCallback(time_callback)
    max_time = 24 * 3600
    routing.AddDimension(time_cb_idx, max_time, max_time, False, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")

    # Set time windows
    for i in range(n):
        index = manager.NodeToIndex(i)
        if i == 0:
            time_dimension.CumulVar(index).SetRange(0, max_time)
        else:
            ready = int(clients[i - 1].get("ready_time", 0) * 60)
            due = int(clients[i - 1].get("due_time", 1440) * 60)
            due = min(due, max_time)
            time_dimension.CumulVar(index).SetRange(ready, due)

    for v in range(num_vehicles):
        start_index = routing.Start(v)
        time_dimension.CumulVar(start_index).SetRange(0, max_time)
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(routing.End(v)))

    # Allow dropping visits with penalty
    penalty = 100000
    for i in range(1, n):
        routing.AddDisjunction([manager.NodeToIndex(i)], penalty)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = time_limit_s

    solution = routing.SolveWithParameters(search_params)

    if not solution:
        cpu_time = (time.perf_counter() - start_time) * 1000
        return {
            "algorithm": "OR-Tools (Google VRP Solver)",
            "routes": [],
            "total_distance_km": 0, "total_cost": 0, "total_duration_min": 0,
            "clients_served": 0, "clients_total": len(clients),
            "respect_rate": 0, "avg_delay_min": 0, "cpu_time_ms": cpu_time,
            "error": "Aucune solution trouvée",
            "traffic_coeff": traffic_coeff, "weather_coeff": weather_coeff,
        }

    # Extract solution
    routes = []
    total_distance = 0.0
    total_cost = 0.0
    total_delay = 0.0
    clients_served = 0
    on_time_count = 0

    for v_idx in range(num_vehicles):
        route = []
        index = routing.Start(v_idx)
        route_dist = 0.0
        load = 0.0
        prev_index = index

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node > 0:
                ci = node - 1
                d = dist_matrix[manager.IndexToNode(prev_index)][node]
                time_var = time_dimension.CumulVar(index)
                arrival_s = solution.Value(time_var)
                arrival_min = arrival_s / 60.0
                ready = clients[ci].get("ready_time", 0)
                due = clients[ci].get("due_time", 1440)
                service = clients[ci].get("service_time", 10)
                delay = max(0, arrival_min - due)

                load += clients[ci].get("demand_kg", 0)
                route_dist += d

                if delay == 0:
                    on_time_count += 1
                total_delay += delay
                clients_served += 1

                route.append({
                    "client_index": ci,
                    "client": clients[ci],
                    "arrival_time": arrival_min,
                    "departure_time": arrival_min + service,
                    "delay": delay,
                    "distance_from_prev": d,
                })

            prev_index = index
            index = solution.Value(routing.NextVar(index))

        # Return to depot distance
        last_node = manager.IndexToNode(prev_index)
        if route:
            route_dist += dist_matrix[last_node][0]

        total_distance += route_dist
        total_cost += route_dist * vehicles[v_idx].get("cost_per_km", 0.5)

        duration = 0
        if route:
            duration = route[-1]["departure_time"] + (dist_matrix[last_node][0] / vehicles[v_idx].get("max_speed_kmh", 60)) * 60 * coeff

        routes.append({
            "vehicle": vehicles[v_idx],
            "vehicle_index": v_idx,
            "route": route,
            "distance_km": route_dist,
            "load_kg": load,
            "duration_min": duration,
        })

    cpu_time = (time.perf_counter() - start_time) * 1000
    respect_rate = (on_time_count / clients_served * 100) if clients_served > 0 else 0
    avg_delay = (total_delay / clients_served) if clients_served > 0 else 0

    return {
        "algorithm": "OR-Tools (Google VRP Solver)",
        "routes": routes,
        "total_distance_km": total_distance,
        "total_cost": total_cost,
        "total_duration_min": sum(r["duration_min"] for r in routes),
        "clients_served": clients_served,
        "clients_total": len(clients),
        "respect_rate": respect_rate,
        "avg_delay_min": avg_delay,
        "cpu_time_ms": cpu_time,
        "traffic_coeff": traffic_coeff,
        "weather_coeff": weather_coeff,
    }
