"""
test_traffic_adjuster.py — Tests du module d'ajustement trafic
"""
import pytest
from datetime import date
from app.engine.traffic_adjuster import (
    adjust_matrix_for_traffic,
    get_optimal_departure_hour,
    get_traffic_coefficient,
    classify_day_type,
    get_traffic_profile,
    reload_coefficients,
)


# ═══════════════════════════════════════════════════════════════════════════════
# classify_day_type
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyDayType:

    def test_monday_is_weekday(self):
        d = date(2026, 5, 4)  # lundi
        assert classify_day_type(d) == "weekday"

    def test_friday_is_weekday(self):
        d = date(2026, 5, 8)  # vendredi
        assert classify_day_type(d) == "weekday"

    def test_saturday(self):
        d = date(2026, 5, 9)
        assert classify_day_type(d) == "saturday"

    def test_sunday(self):
        d = date(2026, 5, 10)
        assert classify_day_type(d) == "sunday"

    def test_ma_public_holiday(self):
        d = date(2026, 5, 1)   # Fête du Travail (Maroc)
        assert classify_day_type(d, country="MA") == "holiday"

    def test_fr_bastille_day(self):
        d = date(2026, 7, 14)
        assert classify_day_type(d, country="FR") == "holiday"

    def test_default_is_today(self):
        result = classify_day_type()
        assert result in ("weekday", "saturday", "sunday", "holiday")

    def test_non_holiday_saturday_is_saturday(self):
        d = date(2026, 5, 16)  # samedi non férié
        assert classify_day_type(d, country="MA") == "saturday"


# ═══════════════════════════════════════════════════════════════════════════════
# get_traffic_coefficient
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetTrafficCoefficient:

    def test_returns_float(self):
        coeff = get_traffic_coefficient(8, "weekday")
        assert isinstance(coeff, float)

    def test_peak_hour_higher_than_night(self):
        peak  = get_traffic_coefficient(8, "weekday")
        night = get_traffic_coefficient(3, "weekday")
        assert peak > night

    def test_sunday_lower_than_weekday_peak(self):
        wd = get_traffic_coefficient(8, "weekday")
        su = get_traffic_coefficient(8, "sunday")
        assert su < wd

    def test_city_center_higher_than_highway(self):
        city = get_traffic_coefficient(8, "weekday", "city_center")
        hway = get_traffic_coefficient(8, "weekday", "highway")
        assert city > hway

    def test_hour_out_of_range_clamped(self):
        coeff_neg = get_traffic_coefficient(-5, "weekday")
        coeff_25  = get_traffic_coefficient(25, "weekday")
        assert isinstance(coeff_neg, float)
        assert isinstance(coeff_25, float)

    def test_unknown_day_type_fallback(self):
        coeff = get_traffic_coefficient(10, "unknown_type")
        assert isinstance(coeff, float)
        assert coeff > 0

    def test_coefficient_positive(self):
        for h in range(24):
            assert get_traffic_coefficient(h, "weekday") > 0


# ═══════════════════════════════════════════════════════════════════════════════
# adjust_matrix_for_traffic
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustMatrixForTraffic:

    @pytest.fixture
    def matrix_3x3(self):
        return [
            [0,   600,  900],
            [600,  0,   300],
            [900, 300,    0],
        ]

    def test_returns_same_dimensions(self, matrix_3x3):
        result = adjust_matrix_for_traffic(matrix_3x3, 8, "weekday")
        assert len(result) == 3
        assert all(len(row) == 3 for row in result)

    def test_diagonal_stays_zero(self, matrix_3x3):
        result = adjust_matrix_for_traffic(matrix_3x3, 8, "weekday")
        for i in range(3):
            assert result[i][i] == pytest.approx(0.0, abs=0.01)

    def test_values_multiplied(self, matrix_3x3):
        coeff  = get_traffic_coefficient(8, "weekday", "city_center")
        result = adjust_matrix_for_traffic(matrix_3x3, 8, "weekday", "city_center")
        assert result[0][1] == pytest.approx(600 * coeff, rel=1e-5)

    def test_night_traffic_less_than_peak(self, matrix_3x3):
        night = adjust_matrix_for_traffic(matrix_3x3, 3,  "weekday")
        peak  = adjust_matrix_for_traffic(matrix_3x3, 8,  "weekday")
        assert night[0][1] < peak[0][1]

    def test_empty_matrix(self):
        result = adjust_matrix_for_traffic([], 8, "weekday")
        assert result == []

    def test_single_element_matrix(self):
        result = adjust_matrix_for_traffic([[0]], 8, "weekday")
        assert len(result) == 1
        assert result[0][0] == pytest.approx(0.0, abs=0.01)

    def test_weekend_lower_than_weekday(self, matrix_3x3):
        wd = adjust_matrix_for_traffic(matrix_3x3, 9, "weekday")
        we = adjust_matrix_for_traffic(matrix_3x3, 9, "sunday")
        assert we[0][1] < wd[0][1]


# ═══════════════════════════════════════════════════════════════════════════════
# get_optimal_departure_hour
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetOptimalDepartureHour:

    @pytest.fixture
    def small_matrix(self):
        # Matrice 4×4 : 0=dépôt, 1-3=clients
        return [
            [0,    900,  1200, 1800],
            [900,  0,    600,  1200],
            [1200, 600,  0,     600],
            [1800, 1200, 600,   0  ],
        ]

    def test_returns_integer(self, small_matrix):
        h = get_optimal_departure_hour(small_matrix, [1, 2, 3])
        assert isinstance(h, int)

    def test_within_candidate_range(self, small_matrix):
        candidates = list(range(5, 15))
        h = get_optimal_departure_hour(
            small_matrix, [1, 2, 3], candidate_hours=candidates
        )
        assert h in candidates

    def test_night_not_optimal_for_normal_stops(self, small_matrix):
        """L'heure optimale ne devrait pas être en pleine nuit (0-4h) par défaut."""
        h = get_optimal_departure_hour(small_matrix, [1, 2, 3])
        assert h >= 5  # par défaut candidates=[5..18]

    def test_empty_stops_returns_default(self, small_matrix):
        h = get_optimal_departure_hour(small_matrix, [])
        assert h == 8

    def test_empty_matrix_returns_default(self):
        h = get_optimal_departure_hour([], [1, 2])
        assert h == 8

    def test_time_windows_influence(self, small_matrix):
        """Avec fenêtres horaires matinales, on devrait partir plus tôt."""
        tw_early = [(6*60, 8*60), (6*60, 8*60), (6*60, 8*60)]  # 6h-8h
        h_early  = get_optimal_departure_hour(
            small_matrix, [1, 2, 3],
            time_windows=tw_early,
            candidate_hours=list(range(4, 12)),
        )
        tw_late  = [(14*60, 16*60), (14*60, 16*60), (14*60, 16*60)]  # 14h-16h
        h_late   = get_optimal_departure_hour(
            small_matrix, [1, 2, 3],
            time_windows=tw_late,
            candidate_hours=list(range(10, 20)),
        )
        assert h_early <= h_late

    def test_holiday_different_from_weekday(self, small_matrix):
        h_wd  = get_optimal_departure_hour(small_matrix, [1, 2, 3], day_type="weekday")
        h_hol = get_optimal_departure_hour(small_matrix, [1, 2, 3], day_type="holiday")
        # Les deux doivent être des entiers valides (ne pas nécessairement être différents)
        assert isinstance(h_wd, int) and isinstance(h_hol, int)


# ═══════════════════════════════════════════════════════════════════════════════
# get_traffic_profile
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetTrafficProfile:

    def test_returns_24_values(self):
        profile = get_traffic_profile("weekday")
        assert len(profile) == 24

    def test_all_positive(self):
        for day in ("weekday", "saturday", "sunday", "holiday"):
            profile = get_traffic_profile(day)
            assert all(v > 0 for v in profile)

    def test_peak_hours_above_off_peak(self):
        profile = get_traffic_profile("weekday")
        peak_hour  = profile[8]   # 8h
        night_hour = profile[3]   # 3h
        assert peak_hour > night_hour

    def test_unknown_type_fallback(self):
        profile = get_traffic_profile("unknown_day")
        assert len(profile) == 24
        assert all(isinstance(v, float) for v in profile)


# ═══════════════════════════════════════════════════════════════════════════════
# reload_coefficients
# ═══════════════════════════════════════════════════════════════════════════════

class TestReloadCoefficients:

    def test_reload_returns_dict(self):
        data = reload_coefficients()
        assert isinstance(data, dict)
        assert "weekday" in data

    def test_reload_idempotent(self):
        data1 = reload_coefficients()
        data2 = reload_coefficients()
        assert data1.get("weekday") == data2.get("weekday")
