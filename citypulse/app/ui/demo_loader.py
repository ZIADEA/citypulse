import os
import csv
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from ..database.db_manager import get_connection, log_action


SOLOMON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                           "archive", "solomon_dataset")


def parse_solomon_csv(filepath, max_rows=None):
    clients = []
    depot = None
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break
            if len(row) < 7:
                continue
            cust_no = int(row[0].strip())
            x = float(row[1].strip())
            y = float(row[2].strip())
            demand = float(row[3].strip())
            ready = int(row[4].strip())
            due = int(row[5].strip())
            service = int(row[6].strip())

            # Convert to GPS (Casablanca centered)
            lat = 33.5731 + (y - 50) * 0.01
            lon = -7.5898 + (x - 50) * 0.01

            entry = {
                "cust_no": cust_no,
                "name": f"Client {cust_no}",
                "latitude": lat,
                "longitude": lon,
                "demand_kg": demand,
                "ready_time": ready,
                "due_time": due,
                "service_time": service,
            }
            if cust_no == 1 and demand == 0:
                depot = {
                    "name": "Dépôt Solomon",
                    "latitude": lat,
                    "longitude": lon,
                }
            else:
                clients.append(entry)
    return depot, clients


def load_demo_scenario(main_window, scenario="10"):
    scenarios = {
        "10": (os.path.join(SOLOMON_DIR, "C1", "C101.csv"), 11),    # 10 clients + depot
        "50": (os.path.join(SOLOMON_DIR, "R1", "R101.csv"), 51),
        "100": (os.path.join(SOLOMON_DIR, "RC1", "RC101.csv"), None),
    }

    choices = ["10 clients (C101)", "50 clients (R101)", "100 clients (RC101)"]
    choice, ok = QInputDialog.getItem(
        main_window, "Charger données démo",
        "Choisissez un scénario :", choices, 0, False
    )
    if not ok:
        return

    if "10" in choice:
        key = "10"
    elif "50" in choice:
        key = "50"
    else:
        key = "100"

    filepath, max_rows = scenarios[key]
    if not os.path.exists(filepath):
        QMessageBox.warning(main_window, "Erreur",
                            f"Fichier non trouvé :\n{filepath}")
        return

    depot, clients = parse_solomon_csv(filepath, max_rows)

    conn = get_connection()
    # Clear existing clients for demo
    conn.execute("DELETE FROM clients")

    for c in clients:
        conn.execute(
            """INSERT INTO clients (cust_no, name, latitude, longitude, demand_kg,
               ready_time, due_time, service_time, client_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'demo')""",
            (c["cust_no"], c["name"], c["latitude"], c["longitude"],
             c["demand_kg"], c["ready_time"], c["due_time"], c["service_time"])
        )

    # Ensure depot exists
    if depot:
        conn.execute("UPDATE depots SET latitude=?, longitude=? WHERE id=1",
                     (depot["latitude"], depot["longitude"]))

    # Ensure at least 3 vehicles
    v_count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    if v_count < 3:
        for i in range(3 - v_count):
            conn.execute(
                """INSERT INTO vehicles (registration, type, capacity_kg, capacity_m3,
                   max_speed_kmh, cost_per_km, depot_id, status)
                   VALUES (?, 'fourgon', 200, 15, 60, 0.5, 1, 'disponible')""",
                (f"DEMO-{v_count + i + 1:03d}",)
            )

    conn.commit()
    conn.close()

    main_window.set_demo_mode(True)
    log_action("DEMO_LOAD", f"Scénario démo {key} clients chargé")

    QMessageBox.information(
        main_window, "Données démo chargées",
        f"{len(clients)} clients charges depuis Solomon {key}\n"
        f"Dépôt mis à jour.\nVéhicules de démo créés."
    )

    # Refresh views
    if hasattr(main_window, 'clients_w'):
        main_window.clients_w.refresh_data()
    if hasattr(main_window, 'dashboard_w'):
        main_window.dashboard_w.refresh_data()
