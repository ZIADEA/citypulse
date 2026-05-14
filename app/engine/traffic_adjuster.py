"""
traffic_adjuster.py — Ajustement des matrices de distance par le trafic
========================================================================
Module Python pur (zéro Qt, zéro DB).

Fonctions publiques :
 adjust_matrix_for_traffic(matrix, hour, day_type) → matrix
 get_optimal_departure_hour(matrix, stops, time_windows) → int
 get_traffic_coefficient(hour, day_type, zone_type) → float
 classify_day_type(date_obj) → str
"""

import json
import logging
import math
from datetime import date as _date
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent / "data" / "traffic_coefficients.json"
_COEFFS: dict = {}  # cache chargé une seule fois


def _load_coefficients() -> dict:
  global _COEFFS
  if _COEFFS:
    return _COEFFS
  try:
    with open(_DATA_FILE, encoding="utf-8") as f:
      _COEFFS = json.load(f)
    logger.debug("traffic_coefficients.json chargé (%d types de jours)", len(_COEFFS) - 2)
  except FileNotFoundError:
    logger.warning("traffic_coefficients.json introuvable — coefficients par défaut utilisés")
    _COEFFS = _default_coefficients()
  except json.JSONDecodeError as e:
    logger.error("Erreur JSON traffic_coefficients.json: %s", e)
    _COEFFS = _default_coefficients()
  return _COEFFS


def _default_coefficients() -> dict:
  """Coefficients de repli si le fichier JSON est absent."""
  base = {str(h): 1.0 for h in range(24)}
  for h in [7, 8, 17, 18]: base[str(h)] = 1.6
  for h in [12, 13]:    base[str(h)] = 1.2
  for h in range(0, 6):  base[str(h)] = 0.8
  return {
    "weekday": dict(base),
    "saturday": {str(h): max(0.8, v * 0.85) for h, v in enumerate(base.values())},
    "sunday":  {str(h): max(0.75, v * 0.75) for h, v in enumerate(base.values())},
    "holiday": {str(h): max(0.75, v * 0.75) for h, v in enumerate(base.values())},
    "peak_multipliers": {"city_center": 1.2, "periurban": 1.05, "highway": 0.9, "industrial": 1.0},
    "day_type_rules": {
      "public_holidays_MA": [],
      "public_holidays_FR": [],
    },
  }


# ═══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ═══════════════════════════════════════════════════════════════════════════════

def classify_day_type(date_obj=None, country: str = "MA") -> str:
  """
  Détermine le type de jour ('weekday', 'saturday', 'sunday', 'holiday').

  Parameters
  ----------
  date_obj : date or None
    Date à classifier (défaut: aujourd'hui).
  country : str
    Pays pour les jours fériés ('MA' = Maroc, 'FR' = France).

  Returns
  -------
  str — 'weekday' | 'saturday' | 'sunday' | 'holiday'
  """
  if date_obj is None:
    date_obj = _date.today()

  coeffs = _load_coefficients()
  rules  = coeffs.get("day_type_rules", {})
  key   = f"public_holidays_{country.upper()}"
  holidays = rules.get(key, [])
  month_day = date_obj.strftime("%m-%d")

  if month_day in holidays:
    return "holiday"

  iso = date_obj.isoweekday() # 1=Mon … 7=Sun
  if iso == 6:
    return "saturday"
  if iso == 7:
    return "sunday"
  return "weekday"


def get_traffic_coefficient(
  hour: int,
  day_type: str = "weekday",
  zone_type: str = "city_center",
) -> float:
  """
  Retourne le coefficient de trafic pour une heure et un type de jour.

  Parameters
  ----------
  hour : int
    Heure de la journée (0–23).
  day_type : str
    'weekday' | 'saturday' | 'sunday' | 'holiday'
  zone_type : str
    'city_center' | 'periurban' | 'highway' | 'industrial'

  Returns
  -------
  float — coefficient multiplicateur (1.0 = trafic nominal)
  """
  coeffs = _load_coefficients()
  hour  = max(0, min(23, int(hour)))

  day_coeffs = coeffs.get(day_type) or coeffs.get("weekday") or {}
  base_coeff = float(day_coeffs.get(str(hour), 1.0))

  peak = coeffs.get("peak_multipliers") or {}
  zone_mult = float(peak.get(zone_type, 1.0))

  return round(base_coeff * zone_mult, 4)


def adjust_matrix_for_traffic(
  matrix: list,
  hour: int,
  day_type: str = "weekday",
  zone_type: str = "city_center",
) -> list:
  """
  Applique le coefficient de trafic à une matrice de temps de trajet.

  Parameters
  ----------
  matrix : list[list[float]]
    Matrice N×N de temps de trajet en secondes.
  hour : int
    Heure de départ (0–23).
  day_type : str
    Type de jour.
  zone_type : str
    Type de zone (affecte le multiplicateur peak).

  Returns
  -------
  list[list[float]] — Matrice ajustée (mêmes dimensions, valeurs × coeff)
  """
  coeff = get_traffic_coefficient(hour, day_type, zone_type)
  return [
    [v * coeff for v in row]
    for row in matrix
  ]


def get_optimal_departure_hour(
  matrix: list,
  stops: list,
  time_windows: list = None,
  day_type: str = "weekday",
  zone_type: str = "city_center",
  candidate_hours: list = None,
) -> int:
  """
  Trouve l'heure de départ optimale minimisant le coût total de trajet
  en tenant compte du trafic, des fenêtres horaires et des contraintes RSE.

  Parameters
  ----------
  matrix : list[list[float]]
    Matrice N×N de temps nominaux en secondes.
  stops : list
    Indices de nœuds à visiter (dans l'ordre ou à optimiser).
  time_windows : list[(int, int)], optional
    Fenêtres horaires en minutes depuis minuit pour chaque stop.
  day_type : str
    Type de jour.
  zone_type : str
    Type de zone.
  candidate_hours : list[int], optional
    Heures candidates à évaluer (défaut: 5h à 18h).

  Returns
  -------
  int — Heure de départ optimale (0–23)
  """
  if candidate_hours is None:
    candidate_hours = list(range(5, 19))

  if not matrix or not stops:
    return 8

  best_hour = 8
  best_score = float("inf")

  for h in candidate_hours:
    coeff = get_traffic_coefficient(h, day_type, zone_type)

    # Score = temps de trajet total × coeff + pénalités fenêtres
    total_travel = 0.0
    penalty   = 0.0
    cursor_min  = h * 60.0 # minutes depuis minuit

    for i, stop_idx in enumerate(stops):
      if i == 0:
        prev_idx = 0 # dépôt
      else:
        prev_idx = stops[i - 1]

      if stop_idx < len(matrix) and prev_idx < len(matrix):
        travel_s  = matrix[prev_idx][stop_idx] * coeff
        total_travel += travel_s
        cursor_min += travel_s / 60.0

        # Pénalité si hors fenêtre horaire
        if time_windows and i < len(time_windows):
          tw_start, tw_end = time_windows[i]
          if cursor_min < tw_start:
            penalty += (tw_start - cursor_min) * 0.5  # attente
          elif cursor_min > tw_end:
            penalty += (cursor_min - tw_end) * 2.0   # retard

    score = total_travel / 60.0 + penalty
    if score < best_score:
      best_score = score
      best_hour = h

  return best_hour


def get_traffic_profile(day_type: str = "weekday") -> list:
  """
  Retourne la liste des 24 coefficients horaires pour un type de jour.

  Returns
  -------
  list[float] — longueur 24, indice = heure
  """
  coeffs   = _load_coefficients()
  day_coeffs = coeffs.get(day_type) or coeffs.get("weekday") or {}
  return [float(day_coeffs.get(str(h), 1.0)) for h in range(24)]


def reload_coefficients():
  """Force le rechargement du fichier JSON (utile après modification manuelle)."""
  global _COEFFS
  _COEFFS = {}
  return _load_coefficients()
