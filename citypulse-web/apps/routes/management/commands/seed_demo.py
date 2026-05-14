"""
seed_demo.py — Peuple la base web avec des données de démonstration réalistes.
Crée 2 comptes :
  chauffeur : souleymane.diallo  / Livraison2026
  client    : amina.benali       / Suivi2026
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.routes.models import DriverRoute
from apps.tracking.models import DeliveryTracking

User = get_user_model()

TODAY = date.today()
NOW   = timezone.now()


# --Arrêts de tournée réalistes — Casablanca ──────────────────────────────────
STOPS_ROUTE_1 = [
    {
        "stop_order": 1,
        "client_name": "Société ALMADAR",
        "address": "23 Rue Ibn Sina, Maarif, Casablanca",
        "lat": 33.5897, "lon": -7.6231,
        "time_window": "08:00 – 10:00",
        "demand_kg": 320,
        "service_time_min": 15,
        "status": "livre",
        "order_ref": "ORD-20260512-0001",
        "notes": "Décharger côté quai B"
    },
    {
        "stop_order": 2,
        "client_name": "Pharmacie Centrale",
        "address": "7 Bd d'Anfa, Casablanca",
        "lat": 33.5931, "lon": -7.6345,
        "time_window": "09:00 – 11:30",
        "demand_kg": 45,
        "service_time_min": 10,
        "status": "livre",
        "order_ref": "ORD-20260512-0002",
        "notes": "Produits fragiles — manipulation avec soin"
    },
    {
        "stop_order": 3,
        "client_name": "Restaurant Le Mazagan",
        "address": "14 Rue de Foucauld, Centre, Casablanca",
        "lat": 33.5952, "lon": -7.6189,
        "time_window": "10:00 – 12:00",
        "demand_kg": 180,
        "service_time_min": 20,
        "status": "en_cours",
        "order_ref": "ORD-20260512-0003",
        "notes": "Livraison à la cuisine — demander M. Hassan"
    },
    {
        "stop_order": 4,
        "client_name": "Marjane Hay Hassani",
        "address": "Route de Médiouna, Hay Hassani, Casablanca",
        "lat": 33.5612, "lon": -7.6512,
        "time_window": "13:00 – 15:00",
        "demand_kg": 850,
        "service_time_min": 30,
        "status": "en_attente",
        "order_ref": "ORD-20260512-0004",
        "notes": "Accès quai 3 — badge requis"
    },
    {
        "stop_order": 5,
        "client_name": "École Privée Al Hidaya",
        "address": "Sidi Maarouf, Casablanca",
        "lat": 33.5489, "lon": -7.6334,
        "time_window": "14:00 – 16:00",
        "demand_kg": 95,
        "service_time_min": 12,
        "status": "en_attente",
        "order_ref": "ORD-20260512-0005",
        "notes": "Sonner à l'accueil principal"
    },
]

STOPS_ROUTE_2 = [
    {
        "stop_order": 1,
        "client_name": "Cabinet Médical Dr. Benali",
        "address": "12 Rue Moulay Youssef, Gauthier, Casablanca",
        "lat": 33.5874, "lon": -7.6402,
        "time_window": "08:30 – 10:00",
        "demand_kg": 28,
        "service_time_min": 8,
        "status": "livre",
        "order_ref": "ORD-20260512-0006",
        "notes": "Consommables médicaux — température ambiante"
    },
    {
        "stop_order": 2,
        "client_name": "Librairie El Maarif",
        "address": "Place Mohammed V, Casablanca",
        "lat": 33.5931, "lon": -7.6172,
        "time_window": "10:30 – 12:00",
        "demand_kg": 210,
        "service_time_min": 15,
        "status": "en_cours",
        "order_ref": "ORD-20260512-0007",
        "notes": ""
    },
    {
        "stop_order": 3,
        "client_name": "Hôtel Hyatt Regency",
        "address": "Place des Nations Unies, Casablanca",
        "lat": 33.5906, "lon": -7.6143,
        "time_window": "14:00 – 15:30",
        "demand_kg": 450,
        "service_time_min": 25,
        "status": "en_attente",
        "order_ref": "ORD-20260512-0008",
        "notes": "Livraison à l'entrée de service — côté est"
    },
]


# --Suivi livraisons pour le compte client ─────────────────────────────────────
DELIVERIES = [
    {
        "order_ref": "ORD-20260512-0001",
        "order_id_ext": "1",
        "status": "livre",
        "driver_first_name": "Souleymane",
        "eta_offset_hours": -3,
    },
    {
        "order_ref": "ORD-20260512-0002",
        "order_id_ext": "2",
        "status": "livre",
        "driver_first_name": "Souleymane",
        "eta_offset_hours": -2,
    },
    {
        "order_ref": "ORD-20260512-0003",
        "order_id_ext": "3",
        "status": "en_cours",
        "driver_first_name": "Souleymane",
        "eta_offset_hours": 1,
    },
    {
        "order_ref": "ORD-20260512-0004",
        "order_id_ext": "4",
        "status": "pending",
        "driver_first_name": "Souleymane",
        "eta_offset_hours": 3,
    },
    {
        "order_ref": "ORD-20260512-0005",
        "order_id_ext": "5",
        "status": "pending",
        "driver_first_name": "Souleymane",
        "eta_offset_hours": 5,
    },
    {
        "order_ref": "ORD-20260510-0031",
        "order_id_ext": "31",
        "status": "livre",
        "driver_first_name": "Mohamed",
        "eta_offset_hours": -48,
    },
    {
        "order_ref": "ORD-20260509-0018",
        "order_id_ext": "18",
        "status": "livre",
        "driver_first_name": "Khalid",
        "eta_offset_hours": -72,
    },
    {
        "order_ref": "ORD-20260508-0044",
        "order_id_ext": "44",
        "status": "echec",
        "driver_first_name": "Omar",
        "eta_offset_hours": -96,
    },
]


class Command(BaseCommand):
    help = "Crée les comptes démo et peuple la base avec des données réalistes"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== CityPulse Web - Seed demo ==="))

        # --Compte chauffeur ──────────────────────────────────────────────────
        driver_user, created = User.objects.update_or_create(
            username="souleymane.diallo",
            defaults={
                "first_name": "Souleymane",
                "last_name": "Diallo",
                "email": "souleymane.diallo@citypulse.ma",
                "role": "driver",
                "desktop_id": "3",
                "is_active": True,
            },
        )
        driver_user.set_password("Livraison2026")
        driver_user.save()
        lbl = "créé" if created else "mis à jour"
        self.stdout.write(self.style.SUCCESS(f"  [OK] Chauffeur {lbl} : souleymane.diallo / Livraison2026"))

        # --Compte client ─────────────────────────────────────────────────────
        client_user, created = User.objects.update_or_create(
            username="amina.benali",
            defaults={
                "first_name": "Amina",
                "last_name": "Benali",
                "email": "amina.benali@citypulse.ma",
                "role": "client",
                "desktop_id": "12",
                "is_active": True,
            },
        )
        client_user.set_password("Suivi2026")
        client_user.save()
        lbl = "créé" if created else "mis à jour"
        self.stdout.write(self.style.SUCCESS(f"  [OK]Client {lbl}   : amina.benali / Suivi2026"))

        # --Tournées du chauffeur (aujourd'hui) ───────────────────────────────
        DriverRoute.objects.filter(planned_date=TODAY).delete()

        route1 = DriverRoute.objects.create(
            vehicle_id_ext="VÉHICULE-001 · Mercedes Actros · 24T",
            driver_id_ext="3",
            planned_date=TODAY,
            stops_json=STOPS_ROUTE_1,
            driver=driver_user,
        )
        route2 = DriverRoute.objects.create(
            vehicle_id_ext="VÉHICULE-003 · Renault Master · 3.5T",
            driver_id_ext="3",
            planned_date=TODAY,
            stops_json=STOPS_ROUTE_2,
            driver=driver_user,
        )

        # Historique — 5 jours passés
        for delta in range(1, 6):
            d = TODAY - timedelta(days=delta)
            DriverRoute.objects.get_or_create(
                vehicle_id_ext="VÉHICULE-001 · Mercedes Actros · 24T",
                driver_id_ext="3",
                planned_date=d,
                defaults={
                    "stops_json": STOPS_ROUTE_1[:3],
                    "driver": driver_user,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"  [OK]Tournées créées : route #{route1.pk} ({len(STOPS_ROUTE_1)} arrêts) "
            f"+ route #{route2.pk} ({len(STOPS_ROUTE_2)} arrêts) + 5 jours d'historique"
        ))

        # --Suivi livraisons (pour le compte client) ─────────────────────────
        DeliveryTracking.objects.all().delete()
        for d in DELIVERIES:
            DeliveryTracking.objects.create(
                order_ref=d["order_ref"],
                order_id_ext=d["order_id_ext"],
                status=d["status"],
                driver_first_name=d["driver_first_name"],
                eta=NOW + timedelta(hours=d["eta_offset_hours"]),
            )
        self.stdout.write(self.style.SUCCESS(
            f"  [OK]{len(DELIVERIES)} livraisons créées dans DeliveryTracking"
        ))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("-- Identifiants de connexion --"))
        self.stdout.write(self.style.SUCCESS("  CHAUFFEUR  -> login : souleymane.diallo  |  mdp : Livraison2026"))
        self.stdout.write(self.style.SUCCESS("  CLIENT     -> login : amina.benali       |  mdp : Suivi2026"))
        self.stdout.write(self.style.SUCCESS("  URL        -> http://127.0.0.1:8000/accounts/login/"))
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("  Liens de suivi public (sans connexion) :"))
        for d in DELIVERIES[:5]:
            self.stdout.write(f"    http://127.0.0.1:8000/track/{d['order_ref']}/")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Seed termine ==="))
