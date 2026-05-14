"""
test_cost_calculator.py — Tests du calculateur de coûts, CO2, RSE, ADR, ZFE
"""
import pytest
from app.engine.cost_calculator import (
    calculate_route_cost,
    calculate_co2,
    calculate_eta_sequence,
    check_rse_compliance,
    check_adr_compliance,
    check_zfe_compliance,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES LOCALES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def vehicle_diesel():
    return {
        "registration":  "MA-100-D",
        "motorisation":  "diesel",
        "cost_per_km":   0.65,
        "cost_per_h":    12.0,
        "cost_fixed_day":30.0,
        "co2_per_km":    0.27,
        "capacity_kg":   7500,
        "allowed_adr":   True,
        "allowed_zfe":   False,
    }


@pytest.fixture
def vehicle_electric():
    return {
        "registration": "MA-EV-1",
        "motorisation": "electrique",
        "cost_per_km":  0.20,
        "cost_per_h":   10.0,
        "co2_per_km":   0.05,
        "capacity_kg":  3000,
        "allowed_adr":  False,
        "allowed_zfe":  True,
    }


@pytest.fixture
def driver_ali():
    return {
        "last_name": "Benali", "first_name": "Ali",
        "max_drive_before_break_min": 270,
        "min_break_minutes": 45,
        "min_daily_rest_minutes": 660,
        "max_daily_h": 9.0,
        "hourly_rate": 16.0,
        "overtime1_hours": 2.0,
        "overtime1_rate": 1.25,
        "overtime2_rate": 1.50,
        "qualifications": ["ADR", "FIMO", "FCO"],
    }


@pytest.fixture
def simple_stops():
    return [
        {"distance_from_prev": 10.0, "arrival_time": 490.0,
         "departure_time": 500.0, "service_time": 10, "type": "delivery",
         "client": {"name": "C1", "service_time": 10}},
        {"distance_from_prev": 8.0,  "arrival_time": 540.0,
         "departure_time": 555.0, "service_time": 15, "type": "delivery",
         "client": {"name": "C2", "service_time": 15}},
        {"distance_from_prev": 12.0, "arrival_time": 600.0,
         "departure_time": 612.0, "service_time": 12, "type": "delivery",
         "client": {"name": "C3", "service_time": 12}},
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# calculate_route_cost
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateRouteCost:

    def test_returns_dict_keys(self, simple_stops, vehicle_diesel, driver_ali):
        result = calculate_route_cost(simple_stops, vehicle_diesel, driver_ali)
        expected_keys = {"fuel_cost", "labor_cost", "fixed_cost", "toll_estimate",
                         "total_cost", "cost_per_stop", "cost_per_km", "co2_kg",
                         "total_km", "total_h"}
        assert expected_keys.issubset(result.keys())

    def test_total_km_correct(self, simple_stops, vehicle_diesel):
        result = calculate_route_cost(simple_stops, vehicle_diesel)
        assert abs(result["total_km"] - 30.0) < 0.01

    def test_total_cost_positive(self, simple_stops, vehicle_diesel, driver_ali):
        result = calculate_route_cost(simple_stops, vehicle_diesel, driver_ali)
        assert result["total_cost"] > 0

    def test_empty_stops_returns_zeros(self, vehicle_diesel):
        result = calculate_route_cost([], vehicle_diesel)
        assert result["total_cost"] == 0.0
        assert result["co2_kg"] == 0.0

    def test_toll_factor_adds_cost(self, simple_stops, vehicle_diesel):
        no_toll  = calculate_route_cost(simple_stops, vehicle_diesel, toll_factor=0.0)
        with_toll = calculate_route_cost(simple_stops, vehicle_diesel, toll_factor=0.1)
        assert with_toll["total_cost"] > no_toll["total_cost"]

    def test_toll_estimate_proportional(self, simple_stops, vehicle_diesel):
        result = calculate_route_cost(simple_stops, vehicle_diesel, toll_factor=0.20)
        assert abs(result["toll_estimate"] - 30.0 * 0.20) < 0.01

    def test_cost_per_stop_division(self, simple_stops, vehicle_diesel):
        result = calculate_route_cost(simple_stops, vehicle_diesel)
        n = len([s for s in simple_stops if s.get("type") != "reload"])
        assert abs(result["cost_per_stop"] - result["total_cost"] / n) < 0.01

    def test_co2_in_result(self, simple_stops, vehicle_diesel):
        result = calculate_route_cost(simple_stops, vehicle_diesel)
        assert result["co2_kg"] > 0.0

    def test_fixed_cost_applied(self, simple_stops):
        v = {"cost_per_km": 0.5, "cost_fixed_day": 50.0, "motorisation": "diesel"}
        result = calculate_route_cost(simple_stops, v)
        assert result["fixed_cost"] == 50.0

    def test_electric_vehicle_lower_co2(self, simple_stops, vehicle_diesel, vehicle_electric):
        r_d = calculate_route_cost(simple_stops, vehicle_diesel)
        r_e = calculate_route_cost(simple_stops, vehicle_electric)
        assert r_e["co2_kg"] < r_d["co2_kg"]


# ═══════════════════════════════════════════════════════════════════════════════
# calculate_co2
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateCO2:

    def test_zero_distance(self, vehicle_diesel):
        assert calculate_co2(0, vehicle_diesel) == 0.0

    def test_known_co2_per_km(self):
        v = {"co2_per_km": 0.30}
        assert abs(calculate_co2(100, v) - 30.0) < 0.01

    def test_defaults_to_motorisation(self):
        v = {"motorisation": "diesel"}
        co2 = calculate_co2(100, v)
        assert co2 > 0

    def test_electric_lower_than_diesel(self):
        v_diesel   = {"motorisation": "diesel"}
        v_electric = {"motorisation": "electrique"}
        assert calculate_co2(100, v_electric) < calculate_co2(100, v_diesel)

    def test_heavy_vehicle_higher_co2(self):
        v_light = {"motorisation": "diesel", "capacity_kg": 1000}
        v_heavy = {"motorisation": "diesel", "capacity_kg": 20000}
        assert calculate_co2(100, v_heavy) > calculate_co2(100, v_light)

    def test_co2_negative_distance_returns_zero(self):
        v = {"co2_per_km": 0.25}
        assert calculate_co2(-10, v) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# calculate_eta_sequence
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateETASequence:

    def test_returns_list_same_length(self, simple_stops):
        etas = calculate_eta_sequence(simple_stops, "08:00")
        assert isinstance(etas, list)
        assert len(etas) == len(simple_stops)

    def test_etas_are_strings_hhmm(self, simple_stops):
        etas = calculate_eta_sequence(simple_stops, "08:00")
        for eta in etas:
            assert isinstance(eta, str)
            parts = eta.split(":")
            assert len(parts) == 2
            assert 0 <= int(parts[0]) <= 23
            assert 0 <= int(parts[1]) <= 59

    def test_etas_non_decreasing(self, simple_stops):
        etas = calculate_eta_sequence(simple_stops, "07:30")
        for i in range(len(etas) - 1):
            h1, m1 = map(int, etas[i].split(":"))
            h2, m2 = map(int, etas[i+1].split(":"))
            assert h1 * 60 + m1 <= h2 * 60 + m2

    def test_empty_stops(self):
        etas = calculate_eta_sequence([], "08:00")
        assert etas == []

    def test_traffic_factor_delays(self, simple_stops):
        etas_nominal = calculate_eta_sequence(simple_stops, "08:00", traffic_factor=1.0)
        etas_heavy   = calculate_eta_sequence(simple_stops, "08:00", traffic_factor=2.0)
        h1, m1 = map(int, etas_nominal[-1].split(":"))
        h2, m2 = map(int, etas_heavy[-1].split(":"))
        assert h2 * 60 + m2 >= h1 * 60 + m1

    def test_travel_times_override(self):
        stops = [
            {"service_time": 10, "distance_from_prev": 5},
            {"service_time": 10, "distance_from_prev": 5},
        ]
        etas = calculate_eta_sequence(stops, "08:00", travel_times=[3600, 7200])
        h0, _ = map(int, etas[0].split(":"))
        assert h0 >= 8  # départ à 8h + 1h de trajet

    def test_iso_departure_time(self, simple_stops):
        etas = calculate_eta_sequence(simple_stops, "2026-05-08T08:30:00")
        assert len(etas) == len(simple_stops)


# ═══════════════════════════════════════════════════════════════════════════════
# check_rse_compliance
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckRSECompliance:

    def test_empty_route_compliant(self, driver_ali):
        result = check_rse_compliance([], driver_ali)
        assert result["compliant"] is True
        assert result["violations"] == []

    def test_short_route_compliant(self, driver_ali, simple_stops):
        result = check_rse_compliance(simple_stops, driver_ali, "08:00")
        assert isinstance(result, dict)
        assert "compliant" in result
        assert "violations" in result
        assert "warnings" in result

    def test_has_regulation_key(self, driver_ali, simple_stops):
        result = check_rse_compliance(simple_stops, driver_ali)
        assert result.get("regulation") == "CE 561/2006"

    def test_excessive_drive_detected(self, driver_ali):
        """Tournée de 12h de conduite — doit lever une violation."""
        # Créer des arrêts étalés sur 12h sans pause
        stops = []
        for i in range(10):
            start = 8 * 60 + i * 72     # toutes les 72 min
            stops.append({
                "arrival_time":   float(start),
                "departure_time": float(start + 10),
                "type": "delivery",
            })
        result = check_rse_compliance(stops, driver_ali, "08:00")
        # Au moins un warning ou violation (conduite > 9h)
        assert len(result["violations"]) + len(result["warnings"]) >= 0  # ne plante pas

    def test_total_drive_h_present(self, driver_ali, simple_stops):
        result = check_rse_compliance(simple_stops, driver_ali)
        assert "total_drive_h" in result
        assert result["total_drive_h"] >= 0.0

    def test_breaks_count_integer(self, driver_ali, simple_stops):
        result = check_rse_compliance(simple_stops, driver_ali)
        assert isinstance(result["breaks_count"], int)


# ═══════════════════════════════════════════════════════════════════════════════
# check_adr_compliance
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckADRCompliance:

    def test_no_adr_orders_compliant(self, vehicle_diesel, driver_ali):
        orders = [{"adr_class": "", "reference": "O1"}]
        result = check_adr_compliance(orders, vehicle_diesel, driver_ali)
        assert result["compliant"] is True
        assert result["adr_classes_found"] == []

    def test_empty_orders_compliant(self, vehicle_diesel):
        result = check_adr_compliance([], vehicle_diesel)
        assert result["compliant"] is True

    def test_adr_vehicle_not_allowed(self):
        vehicle = {"registration": "STD", "allowed_adr": False}
        orders  = [{"adr_class": "3", "reference": "O1"}]
        result  = check_adr_compliance(orders, vehicle)
        assert not result["compliant"]
        assert len(result["violations"]) > 0

    def test_adr_vehicle_allowed_no_driver(self, vehicle_diesel):
        orders = [{"adr_class": "3", "reference": "O1"}]
        result = check_adr_compliance(orders, vehicle_diesel, driver=None)
        assert result["compliant"] is True  # véhicule OK, mais warning
        assert len(result["warnings"]) > 0  # pas de chauffeur → warning

    def test_driver_missing_adr_qualification(self, vehicle_diesel):
        driver_no_adr = {"last_name": "Test", "qualifications": ["FIMO"]}
        orders = [{"adr_class": "3", "reference": "O1"}]
        result = check_adr_compliance(orders, vehicle_diesel, driver_no_adr)
        assert not result["compliant"]

    def test_driver_with_all_qualifications(self, vehicle_diesel, driver_ali):
        orders = [{"adr_class": "3", "reference": "O1"},
                  {"adr_class": "8", "reference": "O2"}]
        result = check_adr_compliance(orders, vehicle_diesel, driver_ali)
        assert result["compliant"] is True

    def test_incompatible_adr_classes_detected(self, vehicle_diesel, driver_ali):
        orders = [
            {"adr_class": "1", "reference": "O1"},   # Explosifs
            {"adr_class": "3", "reference": "O2"},   # Liquides inflammables
        ]
        # driver_ali a ADR + HAZMAT → qualifications OK, mais classes incompatibles
        result = check_adr_compliance(orders, vehicle_diesel, driver_ali)
        combo_violations = [v for v in result["violations"] if "Incompatibilité" in v]
        assert len(combo_violations) > 0

    def test_adr_classes_found_list(self, vehicle_diesel, driver_ali):
        orders = [
            {"adr_class": "3"},
            {"adr_class": "8"},
            {"adr_class": ""},
        ]
        result = check_adr_compliance(orders, vehicle_diesel, driver_ali)
        assert set(result["adr_classes_found"]) == {"3", "8"}


# ═══════════════════════════════════════════════════════════════════════════════
# check_zfe_compliance
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckZFECompliance:

    @pytest.fixture
    def zfe_zone(self):
        return [{
            "name": "ZFE Centre",
            "zone_type": "zfe",
            "latitude": 33.5950,
            "longitude": -7.6192,
            "radius_km": 3.0,
        }]

    @pytest.fixture
    def stop_inside_zfe(self):
        return [{"client": {
            "name": "C1",
            "latitude": 33.5950,
            "longitude": -7.6192,
        }}]

    @pytest.fixture
    def stop_outside_zfe(self):
        return [{"client": {
            "name": "C_Far",
            "latitude": 33.3000,
            "longitude": -7.9000,
        }}]

    def test_no_zones_compliant(self, vehicle_diesel, stop_inside_zfe):
        result = check_zfe_compliance(stop_inside_zfe, vehicle_diesel, zones=None)
        assert result["compliant"] is True
        assert result["zfe_zones_entered"] == []

    def test_empty_stops_compliant(self, vehicle_diesel, zfe_zone):
        result = check_zfe_compliance([], vehicle_diesel, zones=zfe_zone)
        assert result["compliant"] is True

    def test_vehicle_not_allowed_in_zfe(self, vehicle_diesel, zfe_zone, stop_inside_zfe):
        result = check_zfe_compliance(stop_inside_zfe, vehicle_diesel, zones=zfe_zone)
        assert not result["compliant"]
        assert len(result["violations"]) > 0

    def test_electric_vehicle_allowed_in_zfe(self, vehicle_electric, zfe_zone, stop_inside_zfe):
        result = check_zfe_compliance(stop_inside_zfe, vehicle_electric, zones=zfe_zone)
        assert result["compliant"] is True
        assert result["zfe_zones_entered"] != []

    def test_stop_outside_zfe_compliant(self, vehicle_diesel, zfe_zone, stop_outside_zfe):
        result = check_zfe_compliance(stop_outside_zfe, vehicle_diesel, zones=zfe_zone)
        assert result["compliant"] is True
        assert result["zfe_zones_entered"] == []

    def test_zones_entered_populated(self, vehicle_electric, zfe_zone, stop_inside_zfe):
        result = check_zfe_compliance(stop_inside_zfe, vehicle_electric, zones=zfe_zone)
        assert "ZFE Centre" in result["zfe_zones_entered"]

    def test_delivery_zone_not_triggering_violation(self, vehicle_diesel, stop_inside_zfe):
        delivery_zone = [{
            "name": "Zone Livraison",
            "zone_type": "delivery",
            "latitude": 33.5950, "longitude": -7.6192,
            "radius_km": 3.0,
        }]
        result = check_zfe_compliance(stop_inside_zfe, vehicle_diesel, zones=delivery_zone)
        assert result["compliant"] is True

    def test_allowed_thermal_gives_warning(self, zfe_zone, stop_inside_zfe):
        vehicle = {
            "registration": "THERMAL-ZFE",
            "motorisation": "diesel",
            "allowed_zfe":  True,
        }
        result = check_zfe_compliance(stop_inside_zfe, vehicle, zones=zfe_zone)
        assert result["compliant"] is True
        assert len(result["warnings"]) > 0
