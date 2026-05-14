"""
route_analyzer.py — Analyse de patterns sur routes / arrêts / chauffeurs (pur Python).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Optional


def _parse_dt(val: Any) -> Optional[datetime]:
  if val is None:
    return None
  if isinstance(val, datetime):
    return val
  s = str(val).strip()
  if not s:
    return None
  for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M"):
    try:
      return datetime.strptime(s[:19], fmt)
    except ValueError:
      continue
  try:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
  except ValueError:
    return None


def _minutes_diff(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
  if a is None or b is None:
    return None
  return (b - a).total_seconds() / 60.0


class RouteAnalyzer:
  """Insights : écarts durées réelles vs planifiées, retards, regroupements possibles."""

  @staticmethod
  def analyze_patterns(
    routes: list[dict],
    stops: list[dict],
    drivers: Optional[list[dict]] = None,
  ) -> dict[str, Any]:
    drivers = drivers or []
    drv_by_id = {int(d["id"]): d for d in drivers if d.get("id") is not None}

    stops_by_route: dict[int, list[dict]] = defaultdict(list)
    for s in stops or []:
      rid = s.get("route_id")
      if rid is not None:
        stops_by_route[int(rid)].append(s)
    for rid in stops_by_route:
      stops_by_route[rid].sort(key=lambda x: int(x.get("stop_order") or 0))

    delay_samples: list[float] = []
    planned_dur: list[float] = []
    actual_dur: list[float] = []
    per_driver_delays: dict[int, list[float]] = defaultdict(list)
    geo_groups: list[dict[str, Any]] = []

    for r in routes or []:
      rid = int(r.get("id", -1))
      if rid < 0:
        continue
      drv_id = r.get("driver_id")
      if drv_id is not None:
        drv_id = int(drv_id)

      rs = stops_by_route.get(rid, [])

      for st in rs:
        p_start = _parse_dt(st.get("planned_arrival") or st.get("arrival_time"))
        p_end = _parse_dt(st.get("planned_departure") or st.get("departure_time"))
        a_arr = _parse_dt(st.get("actual_arrival"))
        a_dep = _parse_dt(st.get("actual_departure"))

        pd_min = _minutes_diff(p_start, p_end)
        if pd_min is not None and pd_min > 0:
          planned_dur.append(pd_min)
        ad_min = _minutes_diff(a_arr, a_dep)
        if ad_min is not None and ad_min > 0:
          actual_dur.append(ad_min)
        if pd_min and ad_min:
          delay_samples.append(ad_min - pd_min)

        if p_start and a_arr:
          late = (a_arr - p_start).total_seconds() / 60.0
          if drv_id is not None:
            per_driver_delays[drv_id].append(late)
          elif late > 1:
            delay_samples.append(late)

        lat = st.get("latitude")
        lon = st.get("longitude")
        cid = st.get("client_id")
        if lat is not None and lon is not None and cid is not None:
          geo_groups.append({
            "client_id": int(cid),
            "latitude": float(lat),
            "longitude": float(lon),
            "route_id": rid,
          })

    avg_plan = sum(planned_dur) / len(planned_dur) if planned_dur else 0.0
    avg_act = sum(actual_dur) / len(actual_dur) if actual_dur else 0.0
    avg_delay_stop = sum(delay_samples) / len(delay_samples) if delay_samples else 0.0

    driver_insights = []
    for did, vals in per_driver_delays.items():
      if not vals:
        continue
      avg_l = sum(vals) / len(vals)
      dname = drv_by_id.get(did, {}).get("first_name", "") or ""
      dname = (dname + " " + (drv_by_id.get(did, {}).get("last_name") or "")).strip() or f"driver #{did}"
      driver_insights.append({
        "driver_id": did,
        "name": dname,
        "avg_lateness_min": round(avg_l, 1),
        "samples": len(vals),
      })
    driver_insights.sort(key=lambda x: -abs(x["avg_lateness_min"]))

    grouping_hint = RouteAnalyzer._suggest_groupings(geo_groups)

    return {
      "summary": {
        "routes_analyzed": len(routes or []),
        "stops_analyzed": len(stops or []),
        "avg_planned_visit_min": round(avg_plan, 1),
        "avg_actual_visit_min": round(avg_act, 1),
        "avg_duration_delta_min": round(avg_act - avg_plan, 1) if planned_dur and actual_dur else None,
        "avg_lateness_min": round(avg_delay_stop, 1) if delay_samples else None,
      },
      "driver_punctuality": driver_insights[:15],
      "grouping_suggestions": grouping_hint,
      "notes": (
        "Comparer actual_arrival à planned_arrival pour affiner les retards ; "
        "des écarts positifs récurrents indiquent des temps de service sous-estimés."
      ),
    }

  @staticmethod
  def _suggest_groupings(points: list[dict]) -> list[dict]:
    """Regroupe clients proches (< 0.02° ~ 2 km) visités sur routes différentes."""
    if len(points) < 2:
      return []
    suggestions = []
    for i, a in enumerate(points):
      for b in points[i + 1 :]:
        if a["client_id"] == b["client_id"]:
          continue
        if a["route_id"] == b["route_id"]:
          continue
        dlat = abs(a["latitude"] - b["latitude"])
        dlon = abs(a["longitude"] - b["longitude"])
        if dlat < 0.02 and dlon < 0.02:
          suggestions.append({
            "client_a": a["client_id"],
            "client_b": b["client_id"],
            "hint": "Proximité géographique — envisager mutualisation sur une même tournée",
          })
    return suggestions[:50]
