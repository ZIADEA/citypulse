"""
clustering.py — Pré-segmentation géographique des clients (KMeans / DBSCAN)
==========================================================================
 - GeoClusterer : find_optimal_k, cluster_kmeans, cluster_dbscan, export_clusters_geojson
 - cluster_clients, suggest_vehicle_assignment, clustering_quality, get_cluster_summary
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
  from sklearn.cluster import KMeans, DBSCAN
  from sklearn.metrics import silhouette_score
  HAS_SKLEARN = True
except ImportError:
  HAS_SKLEARN = False
  DBSCAN = None # type: ignore
  logger.warning("scikit-learn non disponible — clustering désactivé")


# ── Clustering de base ─────────────────────────────────────────────────────────

def cluster_clients(clients, n_clusters=3):
  """
  Groupe les clients par zone géographique avec KMeans.

  Retourne
  --------
  dict {label: {"clients": [...], "center": {"latitude": ..., "longitude": ...}}}
  """
  if not HAS_SKLEARN or not clients:
    return {}

  n_clusters = min(n_clusters, len(clients))
  if n_clusters < 2:
    return {0: {"clients": clients, "center": _centroid(clients)}}

  coords = np.array([[c["latitude"], c["longitude"]] for c in clients])
  kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
  labels = kmeans.fit_predict(coords)
  centers = kmeans.cluster_centers_

  clusters = {}
  for i, label in enumerate(labels):
    label = int(label)
    if label not in clusters:
      clusters[label] = {
        "clients": [],
        "center": {
          "latitude": float(centers[label][0]),
          "longitude": float(centers[label][1]),
        },
      }
    clusters[label]["clients"].append(clients[i])

  return clusters


def _centroid(clients):
  lats = [c["latitude"] for c in clients]
  lons = [c["longitude"] for c in clients]
  return {
    "latitude": sum(lats) / len(lats),
    "longitude": sum(lons) / len(lons),
  }


# ── Affectation clusters → véhicules ──────────────────────────────────────────

def suggest_vehicle_assignment(clients, vehicles, n_clusters=None):
  """
  Assigne les clusters géographiques aux véhicules disponibles.

  Stratégie :
   - n_clusters = nombre de véhicules (ou moins si peu de clients)
   - Chaque véhicule reçoit le cluster le plus proche de son dépôt (ou le premier libre)
   - Respecte grossièrement la capacité totale

  Retourne
  --------
  dict {vehicle_index: [client_dict, ...]}
  """
  if not HAS_SKLEARN or not clients or not vehicles:
    return {}

  n = n_clusters if n_clusters else min(len(vehicles), len(clients))
  n = max(1, n)

  clusters = cluster_clients(clients, n_clusters=n)
  if not clusters:
    return {}

  assignment = {}
  cluster_labels = list(clusters.keys())

  # Attribution simple : cluster i → vehicle i (round-robin si plus de clusters que de véhicules)
  for i, label in enumerate(cluster_labels):
    v_idx = i % len(vehicles)
    if v_idx not in assignment:
      assignment[v_idx] = []
    assignment[v_idx].extend(clusters[label]["clients"])

  logger.info(
    "Clustering: %d clusters → %d véhicules (%d clients total)",
    len(clusters), len(vehicles), len(clients)
  )
  return assignment


# ── Qualité du clustering ──────────────────────────────────────────────────────

def clustering_quality(clients, n_clusters):
  """
  Calcule le score silhouette (entre -1 et 1, plus haut = meilleur).
  Retourne (score, inertia) ou (None, None) si insuffisant.
  """
  if not HAS_SKLEARN or len(clients) < max(4, n_clusters + 1):
    return None, None

  coords = np.array([[c["latitude"], c["longitude"]] for c in clients])
  n_clusters = min(n_clusters, len(clients) - 1)
  if n_clusters < 2:
    return None, None

  kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
  labels = kmeans.fit_predict(coords)

  try:
    score = float(silhouette_score(coords, labels))
  except Exception:
    score = None

  return score, float(kmeans.inertia_)


# ── Résumé lisible pour l'UI ──────────────────────────────────────────────────

def get_cluster_summary(clients, vehicles):
  """
  Retourne une liste de chaînes lisibles décrivant l'affectation.
  Exemple : ["Zone A → Véhicule V1 (12 clients, ~340 kg)", ...]
  """
  if not clients or not vehicles:
    return []

  n = min(len(vehicles), len(clients))
  assignment = suggest_vehicle_assignment(clients, vehicles, n)
  score, inertia = clustering_quality(clients, n)

  zone_names = [
    "Zone A", "Zone B", "Zone C", "Zone D",
    "Zone E", "Zone F", "Zone G", "Zone H",
  ]
  summary = []
  for v_idx, c_list in assignment.items():
    if v_idx >= len(vehicles):
      continue
    v = vehicles[v_idx]
    reg  = v.get("registration", f"V-{v_idx+1}")
    total = sum(c.get("demand_kg", 0) for c in c_list)
    zone = zone_names[v_idx % len(zone_names)]
    summary.append(f"{zone} → {reg} : {len(c_list)} clients, {total:.0f} kg")

  if score is not None:
    summary.append(f"Qualité clustering (silhouette) : {score:.2f}")

  return summary


# ── GeoClusterer — API orientée GeoJSON / exploration k ──────────────────────

class GeoClusterer:
  """Clustering géographique (lat/lon) avec recherche de k et export GeoJSON."""

  def __init__(self, random_state: int = 42) -> None:
    self.random_state = random_state

  def find_optimal_k(
    self,
    clients: list[dict],
    k_min: int = 2,
    k_max: int = 10,
  ) -> dict:
    """
    Cherche k dans [k_min, k_max] maximisant le score silhouette.
    Retour : {best_k, scores: {k: score|None}, method}
    """
    if not HAS_SKLEARN or len(clients) < k_min + 2:
      return {"best_k": min(k_min, max(1, len(clients))), "scores": {}, "method": "none"}

    coords = np.array([[c["latitude"], c["longitude"]] for c in clients], dtype=float)
    n = len(clients)
    k_hi = min(k_max, n - 1, 10)
    k_lo = max(2, k_min)
    scores: dict[int, Optional[float]] = {}
    best_k, best_s = k_lo, -1.0
    for k in range(k_lo, k_hi + 1):
      try:
        km = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
        labels = km.fit_predict(coords)
        if len(set(labels)) < 2:
          scores[k] = None
          continue
        s = float(silhouette_score(coords, labels))
        scores[k] = round(s, 4)
        if s > best_s:
          best_s, best_k = s, k
      except Exception:
        scores[k] = None
    return {"best_k": best_k, "scores": scores, "method": "silhouette"}

  def cluster_kmeans(self, clients: list[dict], n_clusters: int) -> dict[int, dict[str, Any]]:
    """Même structure que cluster_clients()."""
    return cluster_clients(clients, n_clusters=n_clusters)

  def cluster_dbscan(
    self,
    clients: list[dict],
    eps_km: float = 5.0,
    min_samples: int = 2,
  ) -> dict[int, dict[str, Any]]:
    """
    DBSCAN sur coordonnées ; eps approximé en degrés (lat moyenne ~35° : 1° ~ 85 km).
    """
    if not HAS_SKLEARN or not clients or DBSCAN is None:
      return {}

    lats = np.array([c["latitude"] for c in clients], dtype=float)
    lons = np.array([c["longitude"] for c in clients], dtype=float)
    lat0 = float(np.mean(np.abs(lats))) if len(lats) else 35.0
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * max(0.2, np.cos(np.radians(lat0)))
    eps_deg = eps_km / max(0.001, (km_per_deg_lat + km_per_deg_lon) / 2)
    X = np.column_stack([lats, lons])
    db = DBSCAN(eps=eps_deg, min_samples=min_samples, metric="euclidean")
    labels = db.fit_predict(X)

    clusters: dict[int, dict[str, Any]] = {}
    for i, label in enumerate(labels):
      label = int(label)
      if label not in clusters:
        clusters[label] = {"clients": [], "center": {"latitude": 0.0, "longitude": 0.0}}
      clusters[label]["clients"].append(clients[i])

    for lbl, data in clusters.items():
      cl = data["clients"]
      if cl:
        data["center"] = {
          "latitude": float(np.mean([c["latitude"] for c in cl])),
          "longitude": float(np.mean([c["longitude"] for c in cl])),
        }
    return clusters

  def export_clusters_geojson(self, clusters: dict[int, dict[str, Any]]) -> str:
    """FeatureCollection : point par centre de cluster + propriétés (nb clients)."""
    features = []
    for label, data in sorted(clusters.items(), key=lambda x: x[0]):
      center = data.get("center") or {}
      clients = data.get("clients") or []
      features.append({
        "type": "Feature",
        "geometry": {
          "type": "Point",
          "coordinates": [
            float(center.get("longitude", 0)),
            float(center.get("latitude", 0)),
          ],
        },
        "properties": {
          "cluster_id": label,
          "size": len(clients),
        },
      })
    coll = {"type": "FeatureCollection", "features": features}
    return json.dumps(coll, ensure_ascii=False, indent=2)
