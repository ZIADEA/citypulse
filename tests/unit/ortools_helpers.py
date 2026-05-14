"""Helpers partagés pour les tests OR-Tools (aucun réseau)."""
BASE_LAT, BASE_LON = 33.5731, -7.5898


def make_clients(n, base_lat=BASE_LAT, base_lon=BASE_LON):
    return [
        {
            "name": f"C{i+1}",
            "latitude": base_lat + (i - n // 2) * 0.01,
            "longitude": base_lon + (i - n // 2) * 0.01,
            "demand_kg": 15,
            "ready_time": 60,
            "due_time": 900,
            "service_time": 10,
        }
        for i in range(n)
    ]


def depot():
    return {"latitude": BASE_LAT, "longitude": BASE_LON}


def vehicles(n=2, cap=500):
    return [
        {"capacity_kg": cap, "cost_per_km": 0.5, "co2_per_km": 0.25, "registration": f"V{i+1}"}
        for i in range(n)
    ]
