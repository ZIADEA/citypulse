"""
demand_forecast.py — Prévision de demande (EWMA, saisonnalité hebdo, ARIMA optionnel)
======================================================================================
Aucun accès BDD : l'appelant charge les séries et passe history_data / clients_data.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
  from statsmodels.tsa.arima.model import ARIMA as _ARIMA

  HAS_STATSMODELS = True
except ImportError:
  HAS_STATSMODELS = False


def _parse_date(s: str) -> datetime:
  for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
    try:
      return datetime.strptime(str(s)[:10], fmt)
    except ValueError:
      continue
  return datetime.now()


def _day_series(history: list[dict]) -> tuple[np.ndarray, list[datetime]]:
  """Agrège par jour : history items avec 'date' et 'quantity'|'qty'|'demand'|'actual'."""
  by_day: dict[str, float] = defaultdict(float)
  for row in history:
    d = str(row.get("date") or row.get("day") or "")[:10]
    if not d:
      continue
    v = row.get("quantity")
    if v is None:
      v = row.get("qty")
    if v is None:
      v = row.get("demand")
    if v is None:
      v = row.get("actual")
    by_day[d] += float(v or 0)
  dates_sorted = sorted(by_day.keys())
  vals = np.array([by_day[k] for k in dates_sorted], dtype=float)
  dts = [_parse_date(k) for k in dates_sorted]
  return vals, dts


def _weekday_factors(dts: list[datetime], values: np.ndarray) -> np.ndarray:
  """Facteurs par jour de semaine (0=lun .. 6=dim), moyenne 1.0."""
  if len(values) == 0:
    return np.ones(7)
  sums = np.zeros(7)
  counts = np.zeros(7)
  for dt, v in zip(dts, values):
    w = dt.weekday()
    sums[w] += v
    counts[w] += 1
  overall = float(values.mean()) if values.mean() > 0 else 1.0
  fac = np.ones(7)
  for w in range(7):
    if counts[w] > 0:
      fac[w] = max(0.1, (sums[w] / counts[w]) / overall)
  fac = fac / fac.mean()
  return fac


def _ewma(series: np.ndarray, span: int = 7) -> float:
  if series.size == 0:
    return 0.0
  if series.size == 1:
    return float(series[0])
  alpha = 2.0 / (span + 1)
  s = float(series[0])
  for x in series[1:]:
    s = alpha * float(x) + (1 - alpha) * s
  return s


def _deseasonalize(dts: list[datetime], values: np.ndarray, fac: np.ndarray) -> np.ndarray:
  out = np.zeros_like(values)
  for i, (dt, v) in enumerate(zip(dts, values)):
    w = dt.weekday()
    out[i] = float(v) / max(0.05, fac[w])
  return out


def _arima_forecast_next(deseasonalized: np.ndarray, horizon: int) -> Optional[np.ndarray]:
  if not HAS_STATSMODELS or deseasonalized.size < 14:
    return None
  try:
    model = _ARIMA(deseasonalized, order=(1, 1, 1))
    fit = model.fit()
    fc = fit.forecast(steps=horizon)
    return np.asarray(fc, dtype=float)
  except Exception:
    logger.debug("ARIMA forecast skipped", exc_info=True)
    return None


class ForecastEngine:
  """Prévisions sans E/S : EWMA + saisonnalité calendaire ; ARIMA si statsmodels."""

  def __init__(self, ewma_span: int = 7) -> None:
    self.ewma_span = ewma_span

  def predict_client_demand(
    self,
    client_id: int,
    history_data: list[dict],
    days: int = 7,
  ) -> list[dict]:
    """
    history_data : [{date, quantity|qty|demand|actual}, ...]
    Retour : [{date, day_label, predicted, lower, upper, client_id}, ...]
    """
    values, dts = _day_series(history_data)
    return self._forecast_series(client_id, values, dts, days)

  def predict_fleet_demand(self, clients_data: list[dict], days: int = 7) -> dict:
    """
    clients_data : [{id, history: [...], demand_kg}, ...]
    Agrège les prévisions par client puis somme par jour.
    """
    if not clients_data:
      today = datetime.now()
      empty_fc = []
      for i in range(1, days + 1):
        d = today + timedelta(days=i)
        empty_fc.append({
          "date": d.strftime("%Y-%m-%d"),
          "day_label": d.strftime("%d/%m"),
          "predicted": 0.0,
          "lower": 0.0,
          "upper": 0.0,
        })
      return {
        "forecast": empty_fc,
        "by_client": {},
        "historical_avg": 0.0,
        "trend": "stable",
        "message": "Aucun client fourni.",
      }

    by_client: dict[int, list[dict]] = {}
    all_hist: list[dict] = []

    for c in clients_data:
      cid = int(c.get("id", -1))
      hist = c.get("history") or []
      if not hist and c.get("demand_kg") is not None:
        d0 = datetime.now().strftime("%Y-%m-%d")
        hist = [{"date": d0, "quantity": float(c.get("demand_kg") or 0)}]
      fc = self.predict_client_demand(cid, hist, days=days)
      by_client[cid] = fc
      for h in hist:
        all_hist.append(dict(h))

    agg_by_date: dict[str, dict[str, float]] = {}
    for cid, fc_list in by_client.items():
      for row in fc_list:
        d = row["date"]
        if d not in agg_by_date:
          agg_by_date[d] = {"p": 0.0, "l": 0.0, "u": 0.0}
        agg_by_date[d]["p"] += row["predicted"]
        agg_by_date[d]["l"] += row["lower"]
        agg_by_date[d]["u"] += row["upper"]

    forecast = []
    for i in range(1, days + 1):
      dd = datetime.now() + timedelta(days=i)
      d = dd.strftime("%Y-%m-%d")
      if d in agg_by_date:
        forecast.append({
          "date": d,
          "day_label": dd.strftime("%d/%m"),
          "predicted": round(agg_by_date[d]["p"], 1),
          "lower": max(0.0, round(agg_by_date[d]["l"], 1)),
          "upper": round(agg_by_date[d]["u"], 1),
        })
      else:
        forecast.append({
          "date": d,
          "day_label": dd.strftime("%d/%m"),
          "predicted": 0.0,
          "lower": 0.0,
          "upper": 0.0,
        })

    v_all, dts_all = _day_series(all_hist)
    hist_avg = float(v_all.mean()) if v_all.size else 0.0
    trend = "stable"
    if v_all.size > 2:
      t = float(np.polyfit(np.arange(v_all.size), v_all, 1)[0])
      if t > 0.05 * max(hist_avg, 1):
        trend = "hausse"
      elif t < -0.05 * max(hist_avg, 1):
        trend = "baisse"

    msg = None
    if sum(len(c.get("history") or []) for c in clients_data) < 3:
      msg = "Historique court : prévision indicative (EWMA + saisonnalité)."

    return {
      "forecast": forecast,
      "by_client": by_client,
      "historical_avg": round(hist_avg, 2),
      "trend": trend,
      "message": msg,
    }

  def _forecast_series(
    self,
    client_id: int,
    values: np.ndarray,
    dts: list[datetime],
    days: int,
  ) -> list[dict]:
    today = datetime.now()
    if values.size < 1:
      out = []
      for i in range(1, days + 1):
        d = today + timedelta(days=i)
        out.append({
          "date": d.strftime("%Y-%m-%d"),
          "day_label": d.strftime("%d/%m"),
          "predicted": 0.0,
          "lower": 0.0,
          "upper": 0.0,
          "client_id": client_id,
        })
      return out

    fac = _weekday_factors(dts, values)
    des = _deseasonalize(dts, values, fac)
    ew = _ewma(des, self.ewma_span)
    std = float(np.std(values[-min(14, len(values)) :])) if values.size else 0.0

    ar_fc = _arima_forecast_next(des, days)
    out: list[dict] = []

    for h in range(1, days + 1):
      fut = today + timedelta(days=h)
      w = fut.weekday()
      base = float(ar_fc[h - 1]) if ar_fc is not None and h <= len(ar_fc) else ew
      pred = max(0.0, base * fac[w])
      unc = std * (1.0 + 0.05 * h)
      out.append({
        "date": fut.strftime("%Y-%m-%d"),
        "day_label": fut.strftime("%d/%m"),
        "predicted": round(pred, 2),
        "lower": max(0.0, round(pred - unc, 2)),
        "upper": round(pred + unc, 2),
        "client_id": client_id,
      })

    return out


def forecast_from_algo_results_history(
  historical: list[dict],
  days_ahead: int = 7,
) -> dict:
  """
  Compatibilité dashboard : historical = [{date, actual}, ...] (séries agrégées).
  Retour aligné sur l'ancien forecast_demand().
  """
  hist_in = [{"date": h["date"], "quantity": float(h.get("actual", 0))} for h in historical]
  engine = ForecastEngine()
  pseudo = [{"id": -1, "history": hist_in}]
  pack = engine.predict_fleet_demand(pseudo, days=days_ahead)
  if len(historical) < 3:
    pack["message"] = (
      pack.get("message")
      or "Données insuffisantes. Lancez quelques optimisations d'abord."
    )
  pack["historical"] = historical
  pack["historical_avg"] = pack.get("historical_avg", 0)
  return pack
