import numpy as np

try:
    from sklearn.ensemble import IsolationForest
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def detect_anomalies(records):
    """
    Detect anomalous deliveries based on cost, distance, delay.
    records: list of dicts with keys 'total_distance', 'total_cost', 'avg_delay'
    """
    if not HAS_SKLEARN or len(records) < 5:
        return []

    features = np.array([
        [r.get("total_distance", 0), r.get("total_cost", 0), r.get("avg_delay", 0)]
        for r in records
    ])

    iso = IsolationForest(contamination=0.1, random_state=42)
    predictions = iso.fit_predict(features)

    anomalies = []
    for i, pred in enumerate(predictions):
        if pred == -1:
            anomalies.append({
                "index": i,
                "record": records[i],
                "anomaly_type": "statistical_outlier",
                "severity": "warning",
            })
    return anomalies


def zscore_anomalies(values):
    if len(values) < 3:
        return []
    arr = np.array(values, dtype=float)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return []
    zscores = np.abs((arr - mean) / std)
    return [i for i, z in enumerate(zscores) if z > 2.0]
