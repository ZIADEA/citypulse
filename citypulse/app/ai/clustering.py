import numpy as np

try:
    from sklearn.cluster import KMeans
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def cluster_clients(clients, n_clusters=3):
    if not HAS_SKLEARN or not clients:
        return {}

    coords = np.array([[c["latitude"], c["longitude"]] for c in clients])
    n_clusters = min(n_clusters, len(clients))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(coords)
    centers = kmeans.cluster_centers_

    clusters = {}
    for i, label in enumerate(labels):
        label = int(label)
        if label not in clusters:
            clusters[label] = {
                "clients": [],
                "center": {"latitude": float(centers[label][0]),
                           "longitude": float(centers[label][1])},
            }
        clusters[label]["clients"].append(clients[i])

    return clusters
