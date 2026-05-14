"""
cost_calculator.py — Calcul de coûts et conformité réglementaire
================================================================
Module Python pur (zéro Qt, zéro DB directe).

Fonctions publiques :
 calculate_route_cost(stops, vehicle, driver, fuel_price, toll_factor) → dict
 calculate_co2(distance_km, vehicle) → float
 calculate_eta_sequence(stops, departure_time, travel_times, traffic_factor) → list[str]
 check_rse_compliance(route_stops, driver, departure_time) → dict
 check_adr_compliance(orders, vehicle, driver) → dict
 check_zfe_compliance(route_stops, vehicle, zones) → dict
"""

import math
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Constantes réglementaires CE 561/2006 ─────────────────────────────────────
MAX_DAILY_DRIVE_H   = 9.0   # 9h de conduite max/jour (10h max 2×/sem)
MAX_WEEKLY_DRIVE_H  = 56.0   # 56h/semaine
MANDATORY_BREAK_H   = 0.75   # 45min après 4h30 de conduite
MAX_DRIVE_BEFORE_BREAK = 4.5   # 4h30 avant pause obligatoire

# ── Coefficients CO2 par type de motorisation (kg CO2/km) ─────────────────────
CO2_DEFAULTS = {
  "diesel":    0.27,
  "essence":    0.21,
  "electrique":  0.05,
  "hybride":    0.12,
  "gaz":      0.18,
  "gnv":      0.18,
  "glp":      0.16,
  "default":    0.25,
}

# ── Classes ADR et leur compatibilité ─────────────────────────────────────────
ADR_CLASSES = {
  "1": "Explosifs",
  "2": "Gaz",
  "3": "Liquides inflammables",
  "4.1": "Matières solides inflammables",
  "4.2": "Matières sujettes à inflammation spontanée",
  "4.3": "Matières hydro-réactives",
  "5.1": "Matières comburantes",
  "5.2": "Peroxydes organiques",
  "6.1": "Matières toxiques",
  "6.2": "Matières infectieuses",
  "7": "Matières radioactives",
  "8": "Matières corrosives",
  "9": "Matières dangereuses diverses",
}

REQUIRED_QUALIFICATIONS_BY_ADR = {
  "1": ["ADR", "HAZMAT"],
  "2": ["ADR"],
  "3": ["ADR"],
  "4.1": ["ADR"],
  "4.2": ["ADR"],
  "4.3": ["ADR"],
  "5.1": ["ADR"],
  "5.2": ["ADR", "HAZMAT"],
  "6.1": ["ADR", "HAZMAT"],
  "6.2": ["ADR", "HAZMAT"],
  "7":  ["ADR", "HAZMAT"],
  "8":  ["ADR"],
  "9":  ["ADR"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# CALCUL DU COÛT DE TOURNÉE
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_route_cost(
  stops: list,
  vehicle: dict,
  driver: dict = None,
  fuel_price: float = 1.85,
  toll_factor: float = 0.0,
) -> dict:
  """
  Calcule le coût total d'une tournée.

  Parameters
  ----------
  stops : list[dict]
    Arrêts avec 'distance_from_prev' (km) et optionnel 'arrival_time' (min).
  vehicle : dict
    Véhicule avec 'cost_per_km', 'cost_per_h', 'cost_fixed_day',
    'co2_per_km', 'fuel_consumption_l100km', 'motorisation'.
  driver : dict, optional
    Chauffeur avec 'work_start', 'work_end', taux horaire, heures supp.
  fuel_price : float
    Prix du carburant en €/litre.
  toll_factor : float
    Coût estimé des péages en €/km (0 = pas de péages).

  Returns
  -------
  dict with: fuel_cost, labor_cost, fixed_cost, toll_estimate,
        total_cost, cost_per_stop, cost_per_km, co2_kg
  """
  if not stops:
    return _zero_cost()

  deliveries = [s for s in stops if s.get("type") != "reload"]

  # Distance totale
  total_km = sum(float(s.get("distance_from_prev", 0)) for s in stops)

  # Durée totale (min)
  if deliveries:
    first_arr = deliveries[0].get("arrival_time", 0) or 0
    last_dep = deliveries[-1].get("departure_time") or (
      (deliveries[-1].get("arrival_time") or 0) +
      float((deliveries[-1].get("client") or {}).get("service_time", 10))
    )
    total_min = max(0, float(last_dep) - float(first_arr))
  else:
    total_min = 0.0
  total_h = total_min / 60.0

  # ── Coût carburant ───────────────────────────────────────────────
  consump_l100 = float(vehicle.get("fuel_consumption_l100km") or 12.0)
  motor = (vehicle.get("motorisation") or "diesel").lower()
  if "electrique" in motor:
    fuel_cost = total_km * float(vehicle.get("kwh_per_km", 0.25)) * 0.18 # €/kWh
  else:
    fuel_cost = (total_km / 100.0) * consump_l100 * fuel_price

  # ── Coût main d'œuvre ────────────────────────────────────────────
  if driver:
    hourly = float(driver.get("hourly_rate") or 15.0)
    ot1_h = float(driver.get("overtime1_hours") or 2.0)
    ot1_r = float(driver.get("overtime1_rate") or 1.25)
    ot2_r = float(driver.get("overtime2_rate") or 1.50)
    if total_h <= ot1_h:
      labor_cost = total_h * hourly
    elif total_h <= ot1_h * 2:
      labor_cost = ot1_h * hourly + (total_h - ot1_h) * hourly * ot1_r
    else:
      labor_cost = (ot1_h * hourly
             + ot1_h * hourly * ot1_r
             + (total_h - 2 * ot1_h) * hourly * ot2_r)
  else:
    labor_cost = total_h * 15.0

  # ── Coûts fixes ──────────────────────────────────────────────────
  fixed_day  = float(vehicle.get("cost_fixed_day") or 0.0)
  non_use_day = float(vehicle.get("cost_non_use_day") or 0.0)
  fixed_cost = fixed_day if total_km > 0 else non_use_day

  # ── Coût km (carburant + entretien) ─────────────────────────────
  cost_per_km_rate = float(vehicle.get("cost_per_km") or 0.5)
  km_cost   = total_km * cost_per_km_rate

  # ── Péages ───────────────────────────────────────────────────────
  toll_estimate = total_km * toll_factor

  total_cost = fuel_cost + labor_cost + fixed_cost + toll_estimate
  # Si cost_per_km couvre déjà carburant, on évite le double comptage
  # Convention: on utilise km_cost si fuel_consumption non renseigné
  if not vehicle.get("fuel_consumption_l100km"):
    fuel_cost = km_cost
    total_cost = km_cost + labor_cost + fixed_cost + toll_estimate

  n_stops = len(deliveries)
  co2 = calculate_co2(total_km, vehicle)

  return {
    "fuel_cost":   round(fuel_cost, 2),
    "labor_cost":   round(labor_cost, 2),
    "fixed_cost":   round(fixed_cost, 2),
    "toll_estimate": round(toll_estimate, 2),
    "total_cost":   round(total_cost, 2),
    "cost_per_stop": round(total_cost / n_stops, 2) if n_stops else 0.0,
    "cost_per_km":  round(total_cost / total_km, 2) if total_km else 0.0,
    "co2_kg":     round(co2, 3),
    "total_km":    round(total_km, 2),
    "total_h":    round(total_h, 2),
  }


def _zero_cost() -> dict:
  return {
    "fuel_cost": 0.0, "labor_cost": 0.0, "fixed_cost": 0.0,
    "toll_estimate": 0.0, "total_cost": 0.0,
    "cost_per_stop": 0.0, "cost_per_km": 0.0,
    "co2_kg": 0.0, "total_km": 0.0, "total_h": 0.0,
  }


# ═══════════════════════════════════════════════════════════════════════════════
# CALCUL CO2
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_co2(distance_km: float, vehicle: dict) -> float:
  """
  Calcule les émissions CO2 en kg.

  Parameters
  ----------
  distance_km : float
  vehicle : dict avec 'co2_per_km' (kg/km) ou 'motorisation'.

  Returns
  -------
  float — CO2 en kg
  """
  if distance_km <= 0:
    return 0.0

  if vehicle.get("co2_per_km"):
    return float(vehicle["co2_per_km"]) * distance_km

  motor = (vehicle.get("motorisation") or "diesel").strip().lower()
  factor = next(
    (v for k, v in CO2_DEFAULTS.items() if k in motor),
    CO2_DEFAULTS["default"],
  )
  # Ajustement par classe de poids (PTAC)
  ptac = float(vehicle.get("max_weight_kg") or vehicle.get("capacity_kg") or 0)
  if ptac > 12000:
    factor *= 1.6
  elif ptac > 7500:
    factor *= 1.35
  elif ptac > 3500:
    factor *= 1.15

  return round(factor * distance_km, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# CALCUL ETA (Estimated Time of Arrival)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_eta_sequence(
  stops: list,
  departure_time: str,
  travel_times: list = None,
  traffic_factor: float = 1.0,
) -> list:
  """
  Calcule la séquence d'ETA pour chaque arrêt.

  Parameters
  ----------
  stops : list[dict]
    Arrêts avec 'service_time' (min) et optionnel 'distance_from_prev' (km).
  departure_time : str
    Heure de départ ISO ou 'HH:MM'.
  travel_times : list[float], optional
    Durées de trajet entre arrêts consécutifs en secondes.
    Si absent, estimé à partir de distance_from_prev à 50 km/h.
  traffic_factor : float
    Multiplicateur de temps de trajet.

  Returns
  -------
  list[str] — ETA au format 'HH:MM' pour chaque arrêt
  """
  try:
    if "T" in departure_time:
      dt = datetime.fromisoformat(departure_time)
    else:
      today = datetime.now().date()
      h, m = map(int, departure_time.split(":"))
      dt  = datetime(today.year, today.month, today.day, h, m)
  except Exception:
    dt = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

  etas  = []
  cursor = dt

  for i, stop in enumerate(stops):
    # Temps de trajet
    if travel_times and i < len(travel_times):
      travel_s = float(travel_times[i]) * traffic_factor
    else:
      dist_km  = float(stop.get("distance_from_prev") or 0)
      avg_kmh  = 50.0
      travel_s = (dist_km / avg_kmh * 3600) * traffic_factor if dist_km else 0

    cursor += timedelta(seconds=travel_s)
    etas.append(cursor.strftime("%H:%M"))

    # Temps de service
    service_min = float(stop.get("service_time") or
              (stop.get("client") or {}).get("service_time") or 10)
    cursor += timedelta(minutes=service_min)

  return etas


# ═══════════════════════════════════════════════════════════════════════════════
# VÉRIFICATION CONFORMITÉ RSE
# ═══════════════════════════════════════════════════════════════════════════════

def check_rse_compliance(
  route_stops: list,
  driver: dict,
  departure_time: str = "08:00",
) -> dict:
  """
  Vérifie la conformité RSE (CE 561/2006) de la tournée.

  Parameters
  ----------
  route_stops : list[dict]
    Arrêts avec 'arrival_time' (min depuis minuit) et 'departure_time'.
  driver : dict
    Chauffeur avec 'max_drive_before_break_min', 'min_break_minutes',
    'min_daily_rest_minutes', 'work_start', 'work_end', 'max_daily_h'.

  Returns
  -------
  dict with: compliant (bool), violations (list[str]), warnings (list[str]),
        total_drive_h, total_work_h, breaks_count
  """
  violations: list = []
  warnings:  list = []

  if not route_stops:
    return _rse_ok(0, 0, 0)

  # Paramètres chauffeur
  max_drive_before_break = float(
    driver.get("max_drive_before_break_min") or (MAX_DRIVE_BEFORE_BREAK * 60)
  ) / 60.0
  min_break_h = float(driver.get("min_break_minutes") or 45) / 60.0
  min_rest_h = float(driver.get("min_daily_rest_minutes") or 660) / 60.0
  max_daily_h = float(driver.get("max_daily_h") or MAX_DAILY_DRIVE_H)

  # Reconstruction des plages de conduite
  deliveries = [s for s in route_stops if s.get("type", "delivery") == "delivery"]
  if not deliveries:
    return _rse_ok(0, 0, 0)

  # Durée totale de conduite (heuristique depuis les temps d'arrivée)
  total_drive_min = 0.0
  breaks_count  = 0
  consecutive_drive = 0.0

  for i in range(len(deliveries)):
    s = deliveries[i]
    arr = float(s.get("arrival_time") or 0)
    dep = float(s.get("departure_time") or arr + 10)
    svc = dep - arr

    # Trajet vers ce stop
    if i == 0:
      try:
        h, m = map(int, departure_time.split(":"))
        dep_min = h * 60 + m
      except Exception:
        dep_min = 8 * 60
      travel = max(0, arr - dep_min)
    else:
      prev_dep = float(deliveries[i-1].get("departure_time") or 0)
      travel  = max(0, arr - prev_dep)

    consecutive_drive += travel / 60.0
    total_drive_min  += travel

    if consecutive_drive >= max_drive_before_break:
      # Vérifier si une pause est prévue (approximation : temps de service > 45min)
      if svc / 60.0 >= min_break_h:
        consecutive_drive = 0.0
        breaks_count += 1
      else:
        violations.append(
          f"Arrêt {i+1}: conduite consécutive de "
          f"{consecutive_drive:.1f}h sans pause suffisante "
          f"(max {max_drive_before_break}h)"
        )

  total_drive_h = total_drive_min / 60.0
  total_work_h = total_drive_h + sum(
    float(s.get("departure_time", 0) or 0) - float(s.get("arrival_time", 0) or 0)
    for s in deliveries
  ) / 60.0

  # Vérification durée journalière
  if total_drive_h > MAX_DAILY_DRIVE_H:
    violations.append(
      f"Durée de conduite journalière dépassée: {total_drive_h:.1f}h "
      f"(max réglementaire: {MAX_DAILY_DRIVE_H}h)"
    )
  elif total_drive_h > max_daily_h:
    warnings.append(
      f"Durée de conduite proche de la limite: {total_drive_h:.1f}h / {max_daily_h}h"
    )

  if total_work_h > 13.0:
    violations.append(
      f"Amplitude journalière excessive: {total_work_h:.1f}h (max 13h)"
    )

  return {
    "compliant":   len(violations) == 0,
    "violations":  violations,
    "warnings":   warnings,
    "total_drive_h": round(total_drive_h, 2),
    "total_work_h": round(total_work_h, 2),
    "breaks_count": breaks_count,
    "regulation":  "CE 561/2006",
  }


def _rse_ok(drive, work, breaks):
  return {
    "compliant": True, "violations": [], "warnings": [],
    "total_drive_h": drive, "total_work_h": work,
    "breaks_count": breaks, "regulation": "CE 561/2006",
  }


# ═══════════════════════════════════════════════════════════════════════════════
# VÉRIFICATION CONFORMITÉ ADR
# ═══════════════════════════════════════════════════════════════════════════════

def check_adr_compliance(
  orders: list,
  vehicle: dict,
  driver: dict = None,
) -> dict:
  """
  Vérifie si le véhicule et le chauffeur sont conformes pour transporter
  les matières dangereuses listées dans les commandes.

  Parameters
  ----------
  orders : list[dict] avec 'adr_class' (str), 'reference'.
  vehicle : dict avec 'allowed_adr' (bool), 'vehicle_type'.
  driver : dict avec 'qualifications' (JSON list ou str).

  Returns
  -------
  dict with: compliant, violations, warnings, adr_classes_found
  """
  violations: list = []
  warnings:  list = []

  adr_orders = [o for o in (orders or []) if (o.get("adr_class") or "").strip()
         not in ("", "none", "aucune", "None")]

  if not adr_orders:
    return {"compliant": True, "violations": [], "warnings": [],
        "adr_classes_found": []}

  adr_classes = list({o.get("adr_class", "").strip() for o in adr_orders})

  # Vérification véhicule
  if not vehicle.get("allowed_adr"):
    violations.append(
      f"Véhicule '{vehicle.get('registration', '')}' non habilité ADR — "
      f"classes requises: {', '.join(adr_classes)}"
    )

  # Vérification chauffeur
  if driver:
    drv_quals = _parse_qualifications(driver)
    for adr_cls in adr_classes:
      required = REQUIRED_QUALIFICATIONS_BY_ADR.get(adr_cls, ["ADR"])
      missing = [q for q in required if q not in drv_quals]
      if missing:
        violations.append(
          f"Chauffeur '{driver.get('last_name', '')}' : "
          f"qualification(s) manquante(s) pour ADR classe {adr_cls}: "
          f"{', '.join(missing)}"
        )
  else:
    warnings.append("Aucun chauffeur assigné — conformité ADR chauffeur non vérifiée.")

  # Vérification de compatibilité inter-classes
  dangerous_combos = [("1", "3"), ("1", "5.1"), ("5.2", "3"), ("6.2", "3")]
  for a, b in dangerous_combos:
    if a in adr_classes and b in adr_classes:
      violations.append(
        f"Incompatibilité ADR: classes {a} et {b} ne peuvent coexister dans le même véhicule."
      )

  return {
    "compliant":    len(violations) == 0,
    "violations":    violations,
    "warnings":     warnings,
    "adr_classes_found": adr_classes,
  }


def _parse_qualifications(driver: dict) -> set:
  """Retourne l'ensemble des qualifications du chauffeur."""
  raw = driver.get("qualifications") or ""
  if isinstance(raw, list):
    return set(raw)
  if isinstance(raw, str) and raw.startswith("["):
    try:
      import json
      return set(json.loads(raw))
    except Exception:
      pass
  return {q.strip() for q in raw.replace(",", " ").split() if q.strip()}


# ═══════════════════════════════════════════════════════════════════════════════
# VÉRIFICATION CONFORMITÉ ZFE
# ═══════════════════════════════════════════════════════════════════════════════

def check_zfe_compliance(
  route_stops: list,
  vehicle: dict,
  zones: list = None,
) -> dict:
  """
  Vérifie si le véhicule est autorisé à circuler dans les zones ZFE
  traversées par la tournée.

  Parameters
  ----------
  route_stops : list[dict]
    Arrêts avec 'client' contenant 'latitude', 'longitude'.
  vehicle : dict
    Avec 'allowed_zfe' (bool) et 'motorisation'.
  zones : list[dict]
    Zones avec 'zone_type' ('zfe'), 'latitude', 'longitude', 'radius_km'.

  Returns
  -------
  dict with: compliant, violations, warnings, zfe_zones_entered
  """
  violations: list = []
  warnings:  list = []

  zfe_zones = [z for z in (zones or [])
         if (z.get("zone_type") or "").lower() in ("zfe", "exclusion")]

  if not zfe_zones:
    return {"compliant": True, "violations": [], "warnings": [],
        "zfe_zones_entered": []}

  def _dist_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * \
      math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(max(0, a)))

  entered_zones = []
  motor = (vehicle.get("motorisation") or "diesel").strip().lower()
  is_clean = any(m in motor for m in ("electrique", "hybride", "hydrogene"))
  allowed = bool(vehicle.get("allowed_zfe"))

  for stop in route_stops:
    client = stop.get("client") or stop
    lat = client.get("latitude")
    lon = client.get("longitude")
    if not (lat and lon):
      continue

    for z in zfe_zones:
      zlat = z.get("latitude"); zlon = z.get("longitude")
      if not (zlat and zlon):
        continue
      radius = float(z.get("radius_km") or 1.0)
      d   = _dist_km(lat, lon, zlat, zlon)
      if d <= radius:
        zname = z.get("name") or f"ZFE@{zlat:.3f},{zlon:.3f}"
        if zname not in entered_zones:
          entered_zones.append(zname)
        if not allowed and not is_clean:
          violations.append(
            f"Véhicule '{vehicle.get('registration', '')}' "
            f"({motor}) non autorisé en {zname} "
            f"(stop: {client.get('name', '')})"
          )
        elif not is_clean and allowed:
          warnings.append(
            f"Véhicule '{vehicle.get('registration', '')}' "
            f"autorisé en {zname} mais motorisation thermique — "
            "vérifier Crit'Air."
          )

  return {
    "compliant":    len(violations) == 0,
    "violations":    violations,
    "warnings":     warnings,
    "zfe_zones_entered": entered_zones,
  }
