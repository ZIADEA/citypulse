import numpy as np
from ..database.db_manager import get_connection


def forecast_demand(days_ahead=7):
    """Forecast delivery demand for the next N days based on historical data."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT DATE(created_at) as day, SUM(client_count) as total_clients
           FROM algo_results GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 30"""
    ).fetchall()
    conn.close()

    if len(rows) < 3:
        return {
            "forecast": [{"day": f"J+{i+1}", "predicted_deliveries": 0} for i in range(days_ahead)],
            "message": "Pas assez de données historiques. Lancez quelques optimisations d'abord."
        }

    values = [r["total_clients"] for r in reversed(rows)]
    arr = np.array(values, dtype=float)

    # Simple moving average + trend
    window = min(7, len(arr))
    moving_avg = np.mean(arr[-window:])
    if len(arr) > 1:
        trend = (arr[-1] - arr[0]) / len(arr)
    else:
        trend = 0

    forecast = []
    for i in range(days_ahead):
        predicted = max(0, moving_avg + trend * (i + 1))
        forecast.append({
            "day": f"J+{i+1}",
            "predicted_deliveries": round(predicted),
        })

    return {
        "forecast": forecast,
        "historical_avg": round(moving_avg),
        "trend": "hausse" if trend > 0 else "baisse" if trend < 0 else "stable",
    }
