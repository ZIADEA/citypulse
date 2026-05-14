"""data_validator.py — Validation et génération de données stress test (pur Python)"""
import random
import logging

logger = logging.getLogger(__name__)


def generate_stress_test_clients(n=15):
    rng = random.Random(42)
    base_lat, base_lon = 33.5731, -7.5898
    anomaly_types = [
        "ok","ok","ok","ok","ok",
        "coords_zero","coords_zero",
        "tw_inverted","tw_inverted",
        "neg_demand","overflow",
        "duplicate","duplicate","ok","ok",
    ]
    clients = []
    for i in range(min(n, len(anomaly_types))):
        atype = anomaly_types[i]
        lat = base_lat + rng.uniform(-0.08, 0.08)
        lon = base_lon + rng.uniform(-0.08, 0.08)
        if atype == "coords_zero":
            lat, lon = 0.0, 0.0
            name = f"CLIENT_COORDS_NULLES_{i}"
        elif atype == "tw_inverted":
            name = f"CLIENT_TW_INVERSEE_{i}"
        elif atype == "neg_demand":
            name = f"CLIENT_DEMANDE_NEG_{i}"
        elif atype == "overflow":
            name = f"CLIENT_SURCHARGE_{i}"
        elif atype == "duplicate":
            name = "CLIENT_DOUBLON"
        else:
            name = f"Client Test {i+1}"
        ready = rng.randint(0, 400)
        due   = ready + rng.randint(60, 300)
        clients.append({
            "cust_no":      i + 1,
            "name":         name,
            "latitude":     lat,
            "longitude":    lon,
            "demand_kg":    -50.0 if atype == "neg_demand" else
                            9999.0 if atype == "overflow" else
                            rng.uniform(20, 150),
            "ready_time":   due + 60 if atype == "tw_inverted" else ready,
            "due_time":     ready - 30 if atype == "tw_inverted" else due,
            "service_time": rng.randint(5, 20),
            "_anomaly":     atype,
        })
    return clients


def validate_clients(clients):
    valid, report = [], []
    seen_names = {}
    for c in clients:
        issues, rejected = [], False
        if c.get("latitude", 0) == 0 and c.get("longitude", 0) == 0:
            issues.append("Coordonnées (0,0)")
            rejected = True
        if c.get("due_time", 1440) < c.get("ready_time", 0):
            issues.append(f"Fenêtre inversée ({c.get('ready_time')}>{c.get('due_time')})")
            rejected = True
        if c.get("demand_kg", 0) < 0:
            issues.append(f"Demande négative ({c['demand_kg']} kg → 1 kg)")
            c = {**c, "demand_kg": 1.0}
        if c.get("demand_kg", 0) > 5000:
            issues.append(f"Demande excessive ({c['demand_kg']} kg)")
        name = c.get("name", "")
        if name in seen_names:
            issues.append(f"Doublon '{name}'")
        else:
            seen_names[name] = True
        if issues:
            report.append({
                "client": c.get("name", ""),
                "issues": ", ".join(issues),
                "action": "Rejeté" if rejected else "Corrigé/Avertissement",
            })
        if not rejected:
            valid.append(c)
    return valid, report
