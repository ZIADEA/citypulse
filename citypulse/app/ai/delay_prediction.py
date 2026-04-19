import numpy as np

try:
    from sklearn.linear_model import LinearRegression
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from ..database.db_manager import get_connection


def predict_delay(distance, traffic_coeff, weather_coeff, hour=12):
    """Predict delay based on historical data using simple regression."""
    if not HAS_SKLEARN:
        # Fallback simple estimation
        return max(0, (traffic_coeff * weather_coeff - 1.0) * distance * 0.5)

    conn = get_connection()
    rows = conn.execute(
        """SELECT total_distance, traffic_coeff, weather_coeff, avg_delay
           FROM algo_results WHERE avg_delay IS NOT NULL LIMIT 100"""
    ).fetchall()
    conn.close()

    if len(rows) < 3:
        return max(0, (traffic_coeff * weather_coeff - 1.0) * distance * 0.5)

    X = np.array([[r["total_distance"], r["traffic_coeff"], r["weather_coeff"]] for r in rows])
    y = np.array([r["avg_delay"] for r in rows])

    model = LinearRegression()
    model.fit(X, y)

    prediction = model.predict([[distance, traffic_coeff, weather_coeff]])[0]
    return max(0, prediction)


def predict_delay_confidence(distance, traffic_coeff, weather_coeff):
    delay = predict_delay(distance, traffic_coeff, weather_coeff)
    confidence = 0.8 if delay < 10 else 0.6 if delay < 30 else 0.4
    return {
        "predicted_delay_min": round(delay, 1),
        "confidence": confidence,
        "risk_level": "faible" if delay < 5 else "moyen" if delay < 15 else "élevé",
    }
