"""
weather_service.py — OpenWeatherMap (sans Qt)
Cache mémoire TTL 15 min, facteurs trafic, alertes itinéraire.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

TTL_SECONDS = 900

try:
  import requests

  HAS_REQUESTS = True
except ImportError:
  HAS_REQUESTS = False

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def _cache_get(key: str) -> Any:
  with _lock:
    row = _cache.get(key)
    if not row:
      return None
    exp, val = row
    if time.monotonic() > exp:
      del _cache[key]
      return None
    return val


def _cache_set(key: str, val: Any) -> None:
  with _lock:
    _cache[key] = (time.monotonic() + TTL_SECONDS, val)


def resolve_owm_api_key(explicit: Optional[str] = None) -> Optional[str]:
  if explicit:
    return explicit.strip() or None
  try:
    import keyring
    k = keyring.get_password("citypulse_owm", "api_key")
    if k and k.strip():
      return k.strip()
    k = keyring.get_password("citypulse", "owm_api_key")
    if k and k.strip():
      return k.strip()
  except Exception:
    logger.debug("keyring OWM indisponible", exc_info=True)
  import os
  k = os.getenv("OPENWEATHERMAP_API_KEY") or os.getenv("OWM_API_KEY")
  if k and k.strip():
    return k.strip()
  return None


def get_current(lat: float, lng: float, api_key: Optional[str]) -> Optional[dict]:
  """
  Météo courante. Retourne None si pas de clé ou erreur.
  dict : temp, feels_like, humidity, wind_speed, description, main, icon, raw (optionnel)
  """
  if not api_key or not HAS_REQUESTS:
    return None
  key = f"cur:{round(lat, 4)}:{round(lng, 4)}:{api_key[:8]}"
  hit = _cache_get(key)
  if hit is not None:
    return hit
  try:
    url = "https://api.openweathermap.org/data/2.5/weather"
    r = requests.get(
      url,
      params={
        "lat": lat,
        "lon": lng,
        "appid": api_key,
        "units": "metric",
        "lang": "fr",
      },
      timeout=8,
    )
    if r.status_code != 200:
      logger.warning("OWM current HTTP %s", r.status_code)
      return None
    d = r.json()
    w = (d.get("weather") or [{}])[0]
    m = d.get("main") or {}
    wind = d.get("wind") or {}
    out = {
      "temp": round(float(m.get("temp", 0)), 1),
      "feels_like": round(float(m.get("feels_like", m.get("temp", 0))), 1),
      "humidity": int(m.get("humidity", 0) or 0),
      "wind_speed": round(float(wind.get("speed", 0) or 0), 1),
      "description": (w.get("description") or "").capitalize(),
      "main": (w.get("main") or "").lower(),
      "icon": w.get("main") or "",
      "id": w.get("id"),
    }
    _cache_set(key, out)
    return out
  except Exception:
    logger.exception("get_current OWM")
    return None


def get_forecast_5days(lat: float, lng: float, api_key: Optional[str]) -> list[dict]:
  """Prévisions 5 jours (agrégation journalière depuis liste 3h). Liste vide si pas de clé."""
  if not api_key or not HAS_REQUESTS:
    return []
  key = f"fc:{round(lat, 4)}:{round(lng, 4)}:{api_key[:8]}"
  hit = _cache_get(key)
  if hit is not None:
    return hit
  try:
    url = "https://api.openweathermap.org/data/2.5/forecast"
    r = requests.get(
      url,
      params={
        "lat": lat,
        "lon": lng,
        "appid": api_key,
        "units": "metric",
        "lang": "fr",
      },
      timeout=10,
    )
    if r.status_code != 200:
      return []
    d = r.json()
    by_day: dict[str, list[float]] = defaultdict(list)
    mains: dict[str, str] = {}
    descs: dict[str, str] = {}
    for it in d.get("list") or []:
      dt_txt = str(it.get("dt_txt", ""))[:10]
      if not dt_txt:
        continue
      temp = float((it.get("main") or {}).get("temp", 0))
      by_day[dt_txt].append(temp)
      w = (it.get("weather") or [{}])[0]
      mains[dt_txt] = (w.get("main") or "").lower()
      descs[dt_txt] = w.get("description") or ""
    out: list[dict] = []
    for day in sorted(by_day.keys())[:5]:
      temps = by_day[day]
      out.append({
        "date": day,
        "temp_min": round(min(temps), 1),
        "temp_max": round(max(temps), 1),
        "main": mains.get(day, ""),
        "description": (descs.get(day) or "").capitalize(),
      })
    _cache_set(key, out)
    return out
  except Exception:
    logger.exception("get_forecast_5days OWM")
    return []


def get_traffic_factor(weather: Optional[dict]) -> float:
  """
  Coefficient impact route (1.0 = normal … 1.5 = conditions difficiles).
  """
  if not weather:
    return 1.0
  main = (weather.get("main") or "").lower()
  wind = float(weather.get("wind_speed") or 0)
  w_id = weather.get("id")
  base = 1.0
  if main in ("snow",):
    base = 1.45
  elif main in ("thunderstorm",):
    base = 1.4
  elif main in ("rain", "drizzle"):
    base = 1.15
  elif main in ("mist", "fog", "haze", "smoke"):
    base = 1.12
  elif main in ("extreme",):
    base = 1.5
  if w_id and int(w_id) >= 200 and int(w_id) < 300:
    base = max(base, 1.35)
  if wind >= 15:
    base = min(1.5, base + 0.08)
  elif wind >= 10:
    base = min(1.5, base + 0.04)
  return round(max(1.0, min(1.5, base)), 3)


def get_route_alerts(stops_coords: list[tuple[float, float]], api_key: Optional[str]) -> list[str]:
  """
  Alertes texte par segment géographique (météo locale par arrêt, dédupliquée).
  stops_coords : [(lat, lng), ...]
  """
  if not api_key or not stops_coords:
    return []
  seen: set[tuple[float, float]] = set()
  alerts: list[str] = []
  for lat, lng in stops_coords:
    k = (round(lat, 2), round(lng, 2))
    if k in seen:
      continue
    seen.add(k)
    w = get_current(lat, lng, api_key)
    if not w:
      continue
    fac = get_traffic_factor(w)
    if fac >= 1.25:
      alerts.append(
        f"Zone ({k[0]:.2f},{k[1]:.2f}) : {w.get('description', '')} "
        f"(facteur ~×{fac:.2f}, vent {w.get('wind_speed', 0)} m/s)"
      )
    elif w.get("main") in ("rain", "snow", "thunderstorm"):
      alerts.append(
        f"Zone ({k[0]:.2f},{k[1]:.2f}) : {w.get('description', '')}"
      )
  return alerts[:25]
