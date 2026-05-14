"""
anomaly_detection.py — Détection d'anomalies dans les résultats d'optimisation
===============================================================================
Améliorations Phase 5 :
 - Score de sévérité (low / medium / high) selon z-score
 - Description lisible de chaque anomalie (quelle métrique, écart)
 - Double méthode : IsolationForest + Z-score univarié
 - Retourne anomalies triées par sévérité décroissante
"""

import logging
from collections import defaultdict

import numpy as np

logger = logging.getLogger(__name__)

try:
  from sklearn.ensemble import IsolationForest
  HAS_SKLEARN = True
except ImportError:
  HAS_SKLEARN = False


def detect_anomalies(records: list[dict]) -> list[dict]:
  """
  Détecte les tournées statistiquement anormales.

  Paramètres
  ----------
  records : list[dict] avec clés :
    total_distance, total_cost, avg_delay, algorithm, created_at

  Retourne
  --------
  list[dict] triée par sévérité, chaque anomalie contient :
    index, record, algorithm, created_at,
    anomaly_type, severity (low/medium/high),
    description, scores {distance_z, cost_z, delay_z}
  """
  if len(records) < 5:
    return []

  features = np.array([
    [
      float(r.get("total_distance", 0) or 0),
      float(r.get("total_cost",   0) or 0),
      float(r.get("avg_delay",   0) or 0),
    ]
    for r in records
  ], dtype=float)

  # ── Méthode 1 : IsolationForest ───────────────────────────────────────────
  iso_flags = np.ones(len(records), dtype=int)
  if HAS_SKLEARN:
    try:
      iso = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
      iso_flags = iso.fit_predict(features)  # -1 = anomalie
    except Exception:
      logger.exception("IsolationForest échoué — fallback z-score seul")

  # ── Méthode 2 : Z-scores par métrique ─────────────────────────────────────
  means = features.mean(axis=0)
  stds = features.std(axis=0)
  stds[stds == 0] = 1.0  # éviter division par zéro
  zscores = np.abs((features - means) / stds)  # shape (N, 3)

  LABELS = ["distance", "coût", "retard"]

  anomalies = []
  for i, r in enumerate(records):
    is_iso_anomaly = (iso_flags[i] == -1)
    max_z     = float(zscores[i].max())
    worst_metric  = int(zscores[i].argmax())

    # Un enregistrement est anomalie si IsolationForest OU z > 2.5
    if not is_iso_anomaly and max_z < 2.5:
      continue

    # Sévérité
    if max_z >= 3.5 or (is_iso_anomaly and max_z >= 2.5):
      severity = "high"
    elif max_z >= 2.5:
      severity = "medium"
    else:
      severity = "low"

    # Description lisible
    metric_val = features[i, worst_metric]
    mean_val  = means[worst_metric]
    ecart_pct = ((metric_val - mean_val) / max(mean_val, 0.001)) * 100
    direction = "supérieur" if ecart_pct > 0 else "inférieur"
    description = (
      f"La {LABELS[worst_metric]} ({metric_val:.1f}) est "
      f"{abs(ecart_pct):.0f}% {direction} à la moyenne "
      f"({mean_val:.1f}) — z={zscores[i, worst_metric]:.2f}"
    )

    anomalies.append({
      "index":    i,
      "record":    r,
      "algorithm":  r.get("algorithm", ""),
      "created_at":  r.get("created_at", ""),
      "anomaly_type": "isolation_forest" if is_iso_anomaly else "zscore",
      "severity":   severity,
      "description": description,
      "scores": {
        "distance_z": round(float(zscores[i, 0]), 2),
        "cost_z":   round(float(zscores[i, 1]), 2),
        "delay_z":  round(float(zscores[i, 2]), 2),
        "max_z":   round(max_z, 2),
      },
    })

  # Trier par sévérité décroissante
  severity_order = {"high": 0, "medium": 1, "low": 2}
  anomalies.sort(key=lambda a: (severity_order.get(a["severity"], 3), -a["scores"]["max_z"]))
  return anomalies


def zscore_anomalies(values: list[float]) -> list[int]:
  """Détecte les indices anormaux dans une liste scalaire (z > 2)."""
  if len(values) < 3:
    return []
  arr = np.array(values, dtype=float)
  mean = arr.mean()
  std = arr.std()
  if std == 0:
    return []
  return [i for i, v in enumerate(arr) if abs((v - mean) / std) > 2.0]


def _suggestion_for(issue_type: str, detail: str) -> str:
  d = (detail or "").lower()
  if "coordon" in d or "(0,0)" in detail:
    return "Géocoder l'adresse ou saisir latitude/longitude correctes dans la fiche client."
  if "demande" in d and "négative" in d:
    return "Corriger le champ demande (kg) : valeur positive attendue."
  if "nulle" in d or "demande nulle" in d:
    return "Vérifier si le client est actif ; ajuster la demande ou archiver le point."
  if "créneau" in d or "fenêtre" in d:
    return "Réaligner ready_time / due_time (début avant fin) ou élargir le créneau."
  if "commande" in d or "order" in issue_type:
    return "Contrôler les commandes liées : erreur de saisie poids ou doublon."
  if "retard" in d or "delay" in d:
    return "Analyser les créneaux et la charge véhicule ; envisager une ré-optimisation."
  return "Examiner la fiche client et l'historique des commandes ; valider avec l'exploitation."


def detect_all(clients_data: list[dict], orders_data: list[dict]) -> list[dict]:
  """
  Anomalies croisées clients + commandes. Chaque entrée contient :
   entity_type, entity_id, name, severity, issue, suggestion, meta
  """
  results: list[dict] = []
  if not clients_data:
    return results

  demands = np.array([float(c.get("demand_kg") or 0) for c in clients_data], dtype=float)
  services = np.array([float(c.get("service_time") or 0) for c in clients_data], dtype=float)
  d_m, d_s = float(demands.mean()), max(float(demands.std()), 0.001)
  s_m, s_s = float(services.mean()), max(float(services.std()), 0.001)

  by_client_orders: dict[int, list[dict]] = defaultdict(list)
  for o in orders_data or []:
    cid = o.get("client_id")
    if cid is not None:
      by_client_orders[int(cid)].append(o)

  for c in clients_data:
    cid = int(c.get("id", -1))
    name = c.get("name", f"#{cid}")
    issues: list[tuple[str, str]] = []

    lat = float(c.get("latitude") or 0)
    lon = float(c.get("longitude") or 0)
    if lat == 0.0 and lon == 0.0:
      issues.append(("high", "Coordonnées (0,0) — client non localisé"))

    dk = float(c.get("demand_kg") or 0)
    if dk < 0:
      issues.append(("high", f"Demande négative : {dk} kg"))
    if dk == 0:
      issues.append(("low", "Demande nulle — livraison sans poids"))

    dz = abs((dk - d_m) / d_s)
    if dz > 2.5:
      issues.append(("medium", f"Demande anormale : {dk:.1f} kg (z={dz:.1f})"))

    st = float(c.get("service_time") or 0)
    sz = abs((st - s_m) / s_s)
    if sz > 2.5:
      issues.append(("medium", f"Durée service anormale : {st} min (z={sz:.1f})"))

    rt = c.get("ready_time")
    dt = c.get("due_time")
    if rt is not None and dt is not None:
      try:
        if float(rt) >= float(dt):
          issues.append(("high", f"Créneau inversé : début {rt} >= fin {dt}"))
      except (TypeError, ValueError):
        pass

    olist = by_client_orders.get(cid, [])
    if olist:
      total_kg = sum(float(x.get("quantity_kg") or x.get("weight_kg") or 0) for x in olist)
      if dk > 0 and total_kg > dk * 3:
        issues.append((
          "medium",
          f"Volume commandes ({total_kg:.0f} kg) >> demande client ({dk:.0f} kg)",
        ))

    for sev, msg in issues:
      results.append({
        "entity_type": "client",
        "entity_id": cid,
        "name": name,
        "severity": sev,
        "issue": msg,
        "suggestion": _suggestion_for("client", msg),
      })

  if orders_data and len(orders_data) >= 3:
    weights = [float(o.get("quantity_kg") or o.get("weight_kg") or 0) for o in orders_data]
    bad_idx = zscore_anomalies(weights)
    for i in bad_idx:
      o = orders_data[i]
      oid = o.get("id", i)
      results.append({
        "entity_type": "order",
        "entity_id": oid,
        "name": o.get("reference", str(oid)),
        "severity": "medium",
        "issue": f"Poids commande atypique : {weights[i]:.1f} kg",
        "suggestion": _suggestion_for("order", "poids"),
        "meta": {"client_id": o.get("client_id")},
      })

  severity_order = {"high": 0, "medium": 1, "low": 2}
  results.sort(key=lambda r: severity_order.get(r["severity"], 3))
  return results
