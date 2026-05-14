# CityPulse Logistics — Présentation détaillée de l'application
### Binôme : DJERI-ALASSANI OUBENOUPOU & SOULEYMANE DIALLO | Encadrant : Pr. Bakkas B.
### ENSAM — Université Moulay Ismaïl, Meknès | Version 5.41 | 2025–2026

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture en couches](#2-architecture-en-couches)
3. [Base de données — 24 tables, 21 migrations](#3-base-de-données--24-tables-21-migrations)
4. [Algorithmes VRP — Le moteur d'optimisation](#4-algorithmes-vrp--le-moteur-doptimisation)
5. [Modules d'Intelligence Artificielle](#5-modules-dintelligence-artificielle)
6. [Interface utilisateur — 16 pages](#6-interface-utilisateur--16-pages)
7. [Services backend (Desktop)](#7-services-backend-desktop)
8. [Portail web Django — Architecture et API REST](#8-portail-web-django--architecture-et-api-rest)
9. [Sécurité](#9-sécurité)
10. [Tests et qualité](#10-tests-et-qualité)
11. [Packaging et déploiement](#11-packaging-et-déploiement)
12. [Stack technique complète](#12-stack-technique-complète)

---

## 1. Vue d'ensemble

**CityPulse Logistics** est une application desktop Python complète d'optimisation de tournées de véhicules (VRP — *Vehicle Routing Problem*) avec intelligence artificielle embarquée. Elle est conçue pour les PME de transport et logistique qui doivent planifier quotidiennement des dizaines à plusieurs centaines de livraisons.

### Ce que fait l'application

```
PROBLÈME ENTRANT :
  80 clients  ×  8 véhicules  ×  3 dépôts  ×  créneaux horaires  ×  ADR  ×  ZFE
  → espace de solutions : > 10^80  (NP-difficile)

SOLUTION EN 30 SECONDES :
  Greedy    → 847 km   91% créneaux respectés   < 1 s
  2-opt     → 712 km   93% créneaux respectés   ~ 5 s
  OR-Tools  → 681 km   97% créneaux respectés   ≤ 30 s  (budget configurable)
```

### Les deux composants

| Composant | Public cible | Technologies |
|-----------|-------------|--------------|
| **Application desktop** (16 pages) | Planificateur, dispatcher, responsable logistique | Python 3.11, PyQt6 6.5+, SQLite |
| **Portail web** | Chauffeurs (terrain) + clients (suivi) | Django 5, HTML/Tailwind, PostgreSQL/SQLite |

Les deux composants communiquent via une **API REST sécurisée** (header `X-CityPulse-Secret`) avec synchronisation automatique toutes les 60 secondes.

---

## 2. Architecture en couches

L'application suit un modèle strictement en quatre couches avec des règles d'importation qu'on ne viole jamais :

```
┌──────────────────────────────────────────────────────────────────┐
│   COUCHE UI  —  app/ui/                                          │
│   PyQt6 · 16 widgets de pages · composants réutilisables        │
│   Règle : aucune logique métier, aucun accès BDD direct         │
├──────────────────────────────────────────────────────────────────┤
│   COUCHE SERVICES  —  app/services/                              │
│   optimization_service · report_service                          │
│   weather_service · django_sync_service                          │
│   Règle : orchestre, valide, persiste                           │
├───────────────────────────┬──────────────────────────────────────┤
│   MOTEUR VRP              │   MODULES IA                         │
│   app/engine/             │   app/ai/                            │
│   greedy · two_opt        │   mistral_client · clustering        │
│   ortools_solver          │   anomaly_detection                  │
│   cost_calculator         │   demand_forecast                    │
│   distance · traffic_adj. │   route_analyzer                     │
│   Règle : zéro Qt, zéro BDD               (même règle)         │
├──────────────────────────────────────────────────────────────────┤
│   BASE DE DONNÉES  —  app/database/db_manager.py                 │
│   get_connection() · log_action() · init_database()              │
│   SQLite · 24 tables · 21 migrations automatiques               │
└──────────────────────────────────────────────────────────────────┘
```

### Pourquoi cette séparation ?

- **Testabilité** : `engine/` et `ai/` s'exécutent sans Qt ni base de données → tests unitaires rapides sans mocks complexes.
- **Réutilisabilité** : les algorithmes peuvent être appelés depuis la CLI, des scripts ou un futur serveur.
- **Maintenance** : un bug dans l'UI n'affecte pas les algorithmes, et vice versa.
- **Résultat** : 193 tests passent en < 90 secondes.

### Pattern widget PyQt6 (toutes les pages)

```python
class FooWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()          # construction UI uniquement, jamais de requête BDD

    def _setup_ui(self): ...      # widgets, layouts, connexions signaux

    def refresh_data(self):       # requêtes BDD + mise à jour UI
        ...                       # appelé par MainWindow à chaque navigation

    def retranslate_ui(self, lang: str):   # i18n — 5 langues
        from app.i18n import tr
        ...
```

### Pattern threading (toute opération > 50 ms)

```python
class FooThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error    = pyqtSignal(str)

    def run(self):
        try:
            result = do_heavy_work()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))   # jamais raise, toujours émettre error
```

### Pattern base de données

```python
from app.database.db_manager import get_connection, log_action

conn = get_connection()
conn.execute("UPDATE clients SET name=? WHERE id=?", (name, client_id))
conn.commit()
conn.close()
log_action("CLIENT_UPDATE", f"Client #{client_id} modifié")   # OBLIGATOIRE
```

Règles absolues : `get_connection()` uniquement (jamais `sqlite3.connect()` direct), `log_action()` après toute mutation, soft delete `archived=1` pour les clients.

---

## 3. Base de données — 24 tables, 21 migrations

### Schéma général

```
depots ─────────────┬─────────────── drivers
                    │                    │
                    ├── vehicles ─────────┤
                    │       │             │
clients ─── orders ─┤   routes ───── route_stops
                    │       │
               scenarios   algo_results

carriers ─── carrier_shipments
drivers ──── driver_unavailabilities
drivers ──── teams / team_members
zones (GeoJSON : ZFE, livraison, exclusion)
notifications · logs · user_sessions · ai_conversations · reports_history
recurring_order_templates · distance_cache · translation_glossary
```

### Tables créées à l'initialisation

| Table | Colonnes clés |
|-------|--------------|
| `users` | `username`, `password_hash`, `salt`, `role`, `is_active`, `permissions` (JSON) |
| `clients` | `name`, `latitude`, `longitude`, `demand_kg`, `demand_m3`, `ready_time`, `due_time`, `priority`, `client_type`, `adr_class`, `tags`, `archived` |
| `vehicles` | `registration`, `brand`, `type`, `fuel_type`, `capacity_kg`, `co2_per_km`, `fuel_consumption_l100km`, `allowed_adr`, `allowed_zfe`, `driver_id`, `depot_id` |
| `depots` | `name`, `address`, `latitude`, `longitude`, `opening_time`, `closing_time`, `manager_name`, `loading_bays`, `coverage_radius_km` |
| `scenarios` | `name`, `description`, `tags`, `data_json`, `config_json`, `results_json`, `algorithm`, `client_count`, `vehicle_count` |
| `logs` | `action`, `details`, `user_id`, `created_at` — audit trail complet |
| `notifications` | `type`, `title`, `message`, `is_read`, `severity`, `related_table`, `related_id`, `action_url` |

### Tables ajoutées par migrations (001–021)

| Migration | Table(s) | Contenu |
|-----------|----------|---------|
| 001 | `distance_cache` | Cache OSRM — clé SHA-256 → `dist_json`, `time_json` |
| 002 | `translation_glossary` | Corrections utilisateur — `use_count`, prioritaire sur l'API |
| 003–008 | colonnes étendues | `clients` (company_name, tags, adr_class, time_window2…), `vehicles` (insurance_expiry, co2_per_km, vitesses par type), `depots`, `users`, `notifications`, `algo_results` |
| 009 | `drivers` | Chauffeurs — contrat, horaires légaux, qualifications JSON, dépôt |
| 010 | `driver_unavailabilities` | Absences et congés |
| 011 | `teams` / `team_members` | Équipes de chauffeurs |
| 012 | `orders` | Commandes — reference, status, adr_class, priority, operation_type |
| 013 | `routes` | Tournées planifiées — co2_kg, is_locked, driver_id |
| 014 | `route_stops` | Arrêts — stop_order, planned_arrival, actual_arrival, status, delay_min |
| 015 | `carriers` / `carrier_shipments` | Transporteurs externes |
| 016 | extension `notifications` | severity, related_table, related_id, action_url |
| 017 | `zones` | Zones GeoJSON (ZFE, livraison, exclusion) |
| 018 | `vehicle_unavailabilities` | Créée à la volée par le calendrier véhicule |
| 019 | `reports_history` | Historique rapports générés (25 derniers) |
| 020 | `ai_conversations` | Historique chat Copilote Mistral par user_id |
| 021 | `recurring_order_templates` | Gabarits commandes récurrentes |

### Initialisation automatique

Au premier lancement, `main.py` appelle :
```python
init_database(conn)      # crée les tables de base
run_migrations(conn)     # applique les 21 migrations idempotentes
```
Les migrations sont idempotentes (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` équivalent via `try/except`), ce qui permet des mises à jour sans perte de données.

---

## 4. Algorithmes VRP — Le moteur d'optimisation

### Formulation mathématique (VRPTW)

Soit G=(V,A) un graphe complet, K l'ensemble des véhicules de capacité Q.

**Variables :** x_ijk ∈ {0,1} (le véhicule k emprunte l'arc i→j), t_ik ≥ 0 (heure d'arrivée)

**Objectif multi-critères (configurable par sliders) :**
```
min  w_d × Σ c_ij × x_ijk  +  w_c × Σ cost_k  +  w_e × Σ co2_k
```

**Contraintes :**
```
(C1) Σ x_ijk = 1        ∀i  — visite unique
(C2) Σ x_0jk = 1        ∀k  — départ et retour au dépôt
(C3) Σ d_i × x_ijk ≤ Q  ∀k  — capacité
(C4) a_i ≤ t_ik ≤ b_i   ∀i,k — créneaux horaires
(C5) t_ik + s_i + τ_ij ≤ t_jk + M(1-x_ijk)  — cohérence temporelle
(C6) conduite ≥ 270 min ⟹ pause 45 min  — RSE CE 561/2006
```

### Algorithme 1 — Greedy Nearest Neighbor (`engine/greedy.py`)

Complexité : **O(n² × v)**

```
Pour chaque véhicule k :
  1. Trier les clients par priorité (priority ASC — 1=urgent)
  2. Partir du dépôt
  3. Répéter :
       - Trouver le client non visité le plus proche (Haversine)
       - Si charge + demand_kg ≤ capacity_kg : ajouter à la route
       - Sinon : passer au véhicule suivant
  4. Retourner toutes les routes
```

Résultat : solution en **< 1 seconde** même pour 500 clients. Sert de référence (*baseline*) pour mesurer le gain des autres algorithmes.

### Algorithme 2 — Amélioration locale 2-opt (`engine/two_opt.py`)

Complexité : **O(n²) par itération**

```
Entrée : route du Greedy, matrice de distances
Répéter jusqu'à convergence (ou max_iterations) :
  Pour chaque paire (i, j) d'arêtes :
    Si inverser le segment [i..j] réduit la distance totale :
      Appliquer l'inversion
      improved = True
Retourner la meilleure route + liste de convergence
```

Amélioration typique : **-10% à -20%** de distance par rapport au Greedy. La liste `convergence[]` est utilisée par l'UI pour afficher la courbe de convergence.

### Algorithme 3 — Google OR-Tools (`engine/ortools_solver.py`)

Complexité : NP-difficile, budget temps configurable (5 à 300 secondes).

**Configuration des dimensions :**
```python
# Dimension capacité
routing.AddDimensionWithVehicleCapacity(cap_cb, 0, capacities, True, "Capacity")

# Dimension temporelle (minutes depuis minuit)
routing.AddDimension(tw_cb, slack_max=120, max_time=1440, False, "Time")
for i, (a, b) in enumerate(time_windows):
    time_dim.CumulVar(manager.NodeToIndex(i)).SetRange(a, b)

# Pauses RSE (CE 561/2006)
drive_dim.SetBreakIntervalsOfVehicle([
    routing.solver().FixedDurationIntervalVar(270, 270, 45, False, f"break_{v}")
], v_idx, [])
```

**5 modes VRP disponibles :**

| Mode | Paramètre | Description |
|------|-----------|-------------|
| Standard | `standard` | VRPTW classique, un dépôt |
| Multi-dépôts | `multi_depot` | M-DVRPTW, chaque véhicule part de son dépôt |
| Ouvert | `open` | OVRP : retour dépôt supprimé |
| Pickup-Delivery | `pickup_delivery` | PDPTW : paires précédence + même véhicule |
| Rechargement | `reload` | Retour partiel si charge < 20% |

**Contraintes avancées :**
- **ZFE** : `_build_zfe_pairs()` → pénalité ×1,5 dans la matrice de coûts pour les véhicules non autorisés
- **Compétences** : `_vehicle_can_serve(v, c)` → `SetAllowedVehiclesForIndex()` selon ADR, température, type de véhicule
- **Séquences forcées** : `routing.solver().Add(NextVar(a) == b)`
- **Multi-objectifs** : coût arc = distance×w_d + coût×w_c + CO2×w_co2

### Matrice de distances — stratégie 3 niveaux (`engine/distance.py`)

```
Paire (i,j) demandée
        ↓
Clé SHA-256 calculée
        ↓
┌─ Cache SQLite (distance_cache) ─────────────────────────────┐
│  hit → retourner (dist, time) immédiatement                 │
│  miss ↓                                                     │
├─ OSRM HTTP request (timeout 2s) ────────────────────────────┤
│  succès → sauvegarder dans SQLite → retourner               │
│  échec / timeout ↓                                          │
└─ Haversine × 1,3 (toujours disponible, hors-ligne) ────────┘
       → distance_source = "haversine" loggée dans algo_results
```

### Calcul des coûts (`engine/cost_calculator.py`)

Pour chaque route, après optimisation :

```python
result = calculate_route_cost(stops, vehicle, driver, fuel_price, toll_factor)
# Retourne :
{
  "fuel_cost":    distance_km × fuel_l100km / 100 × fuel_price,
  "labor_cost":   total_hours × driver_hourly_rate,
  "fixed_cost":   vehicle.cost_fixed_daily,
  "toll_estimate": distance_km × toll_factor,
  "co2_kg":       calculate_co2(distance_km, vehicle),  # selon motorisation + PTAC
  "total_cost":   somme de tout,
  "cost_per_km":  total_cost / distance_km,
  "total_km":     distance totale,
  "total_h":      durée totale
}
```

### Ajustement trafic (`engine/traffic_adjuster.py`)

Coefficients par heure et type de jour (JSON) :
```json
{ "weekday":  { "7": 1.55, "8": 1.75, "17": 1.80, ... },
  "saturday": { ... },
  "peak_multipliers": { "city_center": 1.2, "highway": 0.9 } }
```

Fonctions clés :
- `classify_day_type(date, country)` → weekday / saturday / sunday / holiday (jours fériés MA + FR)
- `get_traffic_coefficient(hour, day_type, zone_type)` → facteur multiplicateur
- `get_optimal_departure_hour(matrix, stops, time_windows)` → minimise pénalités créneaux

---

## 5. Modules d'Intelligence Artificielle

Tous dans `app/ai/` — zéro import PyQt6, zéro accès direct à la BDD.

### 5.1 Mistral AI Copilot (`ai/mistral_client.py`)

Copilote conversationnel en langage naturel, intégré dans un dock PyQt6.

**Construction du contexte métier :**
```python
def build_context(db_stats: dict) -> str:
    return f"""Tu es le copilote IA de CityPulse Logistics.
Contexte actuel :
- {db_stats['clients_count']} clients actifs
- {db_stats['vehicles_count']} véhicules disponibles
- {db_stats['orders_pending']} commandes en attente
- Meilleure run : {db_stats['best_algo']} à {db_stats['best_dist']:.1f} km
Réponds en {db_stats['lang']} de façon concise et orientée action."""
```

**Détection d'actions (`parse_command`) :**
Si la réponse contient une intention logistique, le système propose un bandeau *Exécuter / Ignorer* :
- `navigate` → navigation vers une page de l'app
- `optimize` → lancement d'une optimisation
- `create_order` → création d'une commande

**Persistance :** table `ai_conversations` (messages JSON par user_id).
**Langues :** FR / EN / AR / ES / DE (mapping LANG_MAP).
**Fallback :** réponses hors-ligne sans clé API (get_fallback_response).

### 5.2 Clustering géographique (`ai/clustering.py`)

```python
class GeoClusterer:
    def find_optimal_k(self, coords, k_max=15):
        # Score silhouette pour k = 2..k_max → k optimal
    
    def cluster_kmeans(self, clients, k):
        # KMeans scikit-learn, retourne clusters + centroïdes
    
    def cluster_dbscan(self, clients, eps_km=2.0, min_samples=3):
        # DBSCAN pour clusters géographiques naturels
    
    def export_clusters_geojson(self, clusters):
        # GeoJSON pour affichage Leaflet
```

Usage : pré-grouper les clients avant l'optimisation VRP → réduction de la complexité et tournées géographiquement cohérentes.

### 5.3 Détection d'anomalies (`ai/anomaly_detection.py`)

```python
def detect_all(clients_data, orders_data):
    # IsolationForest sur (demand_kg, service_time, latitude, longitude)
    # Z-score bivarié sur demand_kg et service_time
    # Retourne : list[{client_id, anomaly_type, severity, suggestion}]
```

Détecte : demandes atypiques, adresses géographiquement incohérentes, créneaux horaires impossibles, scores de ponctualité aberrants.

### 5.4 Prévision de demande (`ai/demand_forecast.py`)

```python
class ForecastEngine:
    def predict_client_demand(self, client_id, horizon_days=30):
        # EWMA (Exponentially Weighted Moving Average)
        # + composant saisonnier hebdomadaire
        # + ARIMA si statsmodels disponible
    
    def forecast_from_algo_results_history(self, series):
        # Pour l'UI : prend une série temporelle en paramètre
```

### 5.5 Analyse de patterns de routes (`ai/route_analyzer.py`)

```python
class RouteAnalyzer:
    def analyze_patterns(self, routes, stops, drivers):
        # Durées planifiées vs réelles par chauffeur
        # Taux de retard par zone géographique
        # Corrélations retard/conditions/heure
        # Retourne : {driver_stats, zone_stats, time_patterns}
```

---

## 6. Interface utilisateur — 16 pages

Navigation : `self.main_window._nav_to(index)` — sidebar Lucide icons + TopBar fil d'Ariane + menu bar.

| # | Page | Widget | Points clés |
|---|------|--------|------------|
| 0 | Tableau de bord | `DashboardWidget` | 5 KPICards, 2 graphiques Matplotlib, météo OWM 48px, alertes docs, anomalies détectées |
| 1 | Clients | `ClientsWidget` | Table 100/page, import CSV/Excel avec mapping, géocodage Nominatim, vue carte Leaflet, détection anomalies |
| 2 | Véhicules | `VehiclesWidget` | Fiche 7 onglets, alertes assurance/CT (30j), calendrier indisponibilités, stats flotte + camembert |
| 3 | Chauffeurs | `DriversWidget` | 4 onglets : table+fiche, calendrier indispos, équipes CRUD, performances Matplotlib |
| 4 | Dépôts | `DepotsWidget` | Géocodage, minimap Leaflet (rayon couverture), vue carte globale multi-dépôts |
| 5 | Commandes | `OrdersWidget` | 5 KPICards, table paginée, templates récurrents, actions en lot, BL PDF |
| 6 | Transporteurs | `CarriersWidget` | 4 onglets : table, expéditions, simulation flotte vs S/T, évaluation |
| 7 | Optimisation | `OptimizationWidget` | 3 algos × 5 modes, 5 onglets résultats, planificateur semaine, conformité RSE/ADR/ZFE |
| 8 | Carte | `MapWidget` | Leaflet interactif, zones GeoJSON, météo, comparaison split scénarios |
| 9 | Suivi temps réel | `TrackingWidget` | Gantt QPainter, simulation ×1/×2/×5, incidents, synchro web 60s |
| 10 | Scénarios | `ScenariosWidget` | Sauvegarde, comparaison, what-if, import/export JSON, QSplitter table/détail |
| 11 | Traduction | `TranslationWidget` | FR/EN/AR/ES/DE, glossaire, score BLEU, validation méthode |
| 12 | Rapports | `ReportsWidget` | 15 types documents, 5 langues, aperçu QPdfView, historique 25 derniers, planification auto |
| 13 | Journal | `LogsWidget` | Audit trail complet, filtre dates (30j), résolution username, export CSV |
| 14 | Notifications | `NotificationsWidget` | Filtres, détail 280px, liens navigation, résumé journalier QTimer |
| 15 | Paramètres | `SettingsWidget` | 5 onglets : Entreprise, Carte, Rapports, Utilisateurs, Sauvegarde |

### Composants réutilisables (`app/ui/components/`)

| Composant | Signal émis | Description |
|-----------|------------|-------------|
| `KPICard` | — | Valeur, unité, icône, tendance, hover |
| `StatusBadge` | — | success / warning / danger / info / pending / active |
| `SearchBar` | `search_changed(str)` | Debounce 300 ms |
| `PaginationBar` | `page_changed(page, offset, limit)` | SQL LIMIT/OFFSET |
| `StarRating` | `rating_changed(int)` | Notation 1–5 étoiles |
| `NotificationBell` | — | Badge numérique + dropdown 5 notifs |
| `ConfirmDialog` | — | Dialog standardisé avec QSS intégré |
| `CollapsibleSection` | — | ▶/▼ cliquable, animation 150 ms |
| `LoadingSpinner` | — | QPainter arc tournant, QTimer 50 ms |
| `TopBar` | — | Fil d'Ariane + cloche + user + déconnexion |
| `SectionHeader` | — | Titre + sous-titre + bouton action + ligne accent |

### Internationalisation (`app/i18n.py`)

5 langues : `fr` / `en` / `ar` / `es` / `de`

```python
LANG_CODES = ["fr", "en", "ar", "es", "de"]

def tr(key: str, lang: str = "fr") -> str:
    # Retourne la traduction de la clé dans la langue demandée
    # Clés : nav.*, page.*, section.*, drivers.tab.*, settings.tab.*
```

Chaque widget de page implémente `retranslate_ui(lang)` — appelé par `MainWindow._apply_language(lang)` quand l'utilisateur change la langue dans Paramètres. La langue est persistée dans `settings.json` (`system.ui_lang`).

### Thème et styles (`app/ui/styles.py`)

Deux thèmes complets : **dark** (défaut) et **light**.

```
Dark :  fond #0D1B2A · sidebar #162840 · panels #243F58 · accent #00D4FF · text2 #7FA8C0
Light : fond #F0F4F8 · accent #1565C0
```

Boutons nommés : `#primaryBtn`, `#secondaryBtn`, `#dangerBtn`, `#ghostBtn`, `#iconBtn`.
Changement de thème : `MainWindow._apply_theme(theme)` — re-style en cascade.

---

## 7. Services backend (Desktop)

### 7.1 Service d'optimisation (`services/optimization_service.py`)

Fonction principale : `run_optimization(clients, vehicles, depots, params)`

**Flux d'exécution :**
```
1. validate_inputs()           — vérifications pré-run (clients avec coords, véhicules dispo)
2. build_matrix()              — matrice distances (3 niveaux : cache → OSRM → Haversine)
3. Trier clients par priority  — priority 1 = urgent = servi en premier
4. Filtrer véhicules           — exclure si chauffeur indisponible le jour planifié
5. Appeler l'algo sélectionné  — greedy / two_opt / ortools_solver
6. calculate_route_cost()      — coûts, CO2, ETA par route
7. check_rse/adr/zfe_compliance() — conformité réglementaire
8. save_result()               — INSERT dans algo_results
9. Retourner result dict       — routes, stats, compliance
```

**`save_plan(result, planned_date)` — confirmation officielle :**

```
1. INSERT routes (une par véhicule actif)
   → algorithm, planned_date, total_km, total_cost, co2_kg, driver_id

2. INSERT route_stops (un par client)
   → stop_order, planned_arrival (HH:MM), client_id, order_id

3. UPDATE orders (assignation commandes)
   → Requête CASE WHEN pour priorité : date exacte > NULL > autre date
   → Second pass : commandes restantes pour tous les clients routés

4. INSERT vehicle_unavailabilities (bloque le calendrier)

5. INSERT notification (confirmation dans la cloche)

6. _sync_plan_to_web()
   → sync_routes() vers portail chauffeur
   → push_delivery_tracking() vers portail client (statut + ETA + chauffeur)
```

**Planificateur hebdomadaire (`_WeeklyPlannerDialog` + `_WeekPlanThread`) :**
- Distribue toutes les commandes `pending` sur N jours par priorité décroissante
- Respecte `scheduled_date` par commande
- Filtre `driver_unavailabilities` par jour
- Appelle `save_plan()` pour chaque jour de la semaine

### 7.2 Service météo (`services/weather_service.py`)

Cache mémoire TTL 15 minutes — aucun import Qt.

| Fonction | Comportement |
|----------|-------------|
| `get_current(lat, lng, api_key)` | `dict` ou `None` si pas de clé/erreur |
| `get_forecast_5days(lat, lng, api_key)` | `list[dict]` — liste vide sans clé |
| `get_traffic_factor(weather)` | `float` 1.0–1.5 (pluie×1.1, vent×1.2, neige×1.4, orage×1.5) |
| `get_route_alerts(stops_coords, api_key)` | `list[str]` — alertes texte par tronçon |
| `resolve_owm_api_key()` | Keyring `citypulse_owm` fallback `citypulse` |

Intégration UI : bandeau HTML Leaflet (MapWidget), mini-widget 48px (DashboardWidget), bandeau warning si facteur > 1.1 (OptimizationWidget), ajustement durées Gantt (TrackingWidget).

### 7.3 Service de rapports (`services/report_service.py`)

Classe `ReportService` — 15 types de documents, 5 langues (FR/EN/AR/ES/DE).

Chaque méthode `generate_*` accepte `lang="fr"` et utilise un dictionnaire `_RL_DATA[lang][key]` (~80 clés).

| Document | Format | Description |
|----------|--------|-------------|
| `generate_driver_roadbook()` | PDF | Arrêts + QR codes JSON + signature |
| `generate_fleet_daily_report()` | PDF | Graphique km/véhicule + tableau comparatif |
| `generate_kpi_report()` | PDF/XLSX | Évolution quotidienne + comparaison S-1 |
| `generate_algo_comparison_report()` | PDF | Tableau algo_results + graphique |
| `generate_delivery_note()` | PDF | **BL** : expéditeur, destinataire, quantités, signature |
| `generate_cmr()` | PDF | **CMR** international : cases 1–3, 6, 11–13, 18, 23–24 |
| `generate_cmr_from_optimization_route()` | PDF | CMR depuis résultat VRP en mémoire |
| `generate_adr_document()` | PDF | Désignation ONU, classe, groupe emballage |
| `generate_load_manifest()` | PDF | Poids, volume, taux remplissage, visa chef de quai |
| `generate_load_manifest_from_optimization_route()` | PDF | Depuis route en mémoire |
| `generate_rse_compliance_report()` | PDF | Durées conduite vs réglementation par chauffeur |
| `generate_carrier_report()` | PDF | Synthèse transporteurs |
| `generate_driver_performance_report()` | PDF/XLSX | Agrégation routes × drivers |
| `export_to_excel()` | XLSX | 6 onglets : Clients, Véhicules, Chauffeurs, Commandes, Tournées, Journal |
| `generate_full_snapshot()` | JSON | Dump complet multi-tables (sauvegarde BDD) |

Chaque export réussi → `reports_history` INSERT + `log_action()`.

### 7.4 Service Django (`services/django_sync_service.py`)

Client HTTP — header `X-CityPulse-Secret`, timeout 10s, erreurs capturées.

```python
class DjangoSyncService:
    def health_check(self) -> bool
    def sync_clients(self, data: list) -> dict   # POST /api/sync/clients/
    def sync_routes(self, data: list) -> dict    # POST /api/sync/routes/
    def pull_confirmations(self) -> list[dict]   # GET /api/deliveries/confirmations/
    def pull_proofs(self) -> list[dict]          # GET /api/deliveries/proofs/
    def push_delivery_tracking(self, orders)     # POST /api/deliveries/confirm/ par commande
```

**Synchronisation automatique :** `TrackingWidget._sync_timer` (QTimer 60s) appelle `_pull_web_confirmations()` qui met à jour `orders.status` dans le desktop à partir des confirmations chauffeur web.

---

## 8. Portail web Django — Architecture et API REST

### Technologies

```
Django 5 + django-allauth + Tailwind CSS (CDN)
Base de données : SQLite (développement) / PostgreSQL (production)
Serveur WSGI : waitress (Windows) / gunicorn (Linux)
Déploiement : Vercel / Railway / Fly.io
```

### Structure du projet web

```
citypulse-web/
├── manage.py
├── vercel.json                 # Déploiement Vercel serverless
├── requirements.txt
├── apps/
│   ├── api/                   # Endpoints REST sync desktop↔web
│   │   └── views.py           # sync_clients, sync_routes, confirm, proofs...
│   ├── routes/                # Dashboard chauffeur
│   │   ├── views.py           # Liste tournées + détail arrêts
│   │   └── templates/
│   ├── tracking/              # Confirmations + preuves photo
│   │   └── models.py          # DeliveryTracking, DeliveryProof
│   └── accounts/              # Authentification django-allauth
└── templates/                 # Base HTML + composants Tailwind
```

### Endpoints API REST

| Méthode | URL | Auth | Description |
|---------|-----|------|-------------|
| `GET` | `/api/health/` | — | Health check public |
| `POST` | `/api/sync/clients/` | Secret | Synchroniser la liste clients |
| `POST` | `/api/sync/routes/` | Secret | Synchroniser les tournées planifiées |
| `GET` | `/api/deliveries/confirmations/` | Secret | Récupérer confirmations chauffeurs |
| `GET` | `/api/deliveries/proofs/` | Secret | Récupérer preuves photo/signature |
| `POST` | `/api/deliveries/confirm/` | Chauffeur | Chauffeur confirme une livraison |
| `POST` | `/api/users/create/` | Secret | Créer/MAJ un compte web |

**Sécurité API :** header `X-CityPulse-Secret` vérifié sur toutes les routes sync. Clé stockée dans keyring (`citypulse_django` / `django_api_secret`) côté desktop, dans variable d'environnement `CITYPULSE_API_SECRET` côté Django.

**Correction importante (v5.41) :** `sync_clients` vérifie `isinstance(payload, list)` avant `.get()` pour éviter `AttributeError 500` quand le payload est une liste JSON.

### Vues chauffeur et client

**Dashboard chauffeur (`/driver/`) :**
- Liste des tournées assignées au chauffeur connecté
- Détail d'une tournée : arrêts ordonnés, adresses, créneaux, carte Leaflet
- Bouton de confirmation livraison (statut + photo optionnelle)

**Suivi client (`/client/`) :**
- Liste des commandes avec ETA, statut coloré, chauffeur assigné
- Page de suivi public (sans connexion) via numéro de référence

**Création de comptes depuis le desktop :**
- Bouton 🌐 sur chaque fiche chauffeur/client → `POST /api/users/create/`
- Identifiants générés automatiquement (prénom.nom + mot de passe sécurisé)
- Affichés à l'opérateur pour communication

---

## 9. Sécurité

### Mots de passe utilisateurs

```python
# Hachage SHA-256 avec sel aléatoire (db_manager.py)
def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return h, salt
```

### Clés API — Windows Credential Manager (keyring)

| Service | Username | Contenu |
|---------|----------|---------|
| `citypulse` | `mistral_api_key` | Clé API Mistral AI |
| `citypulse_owm` | `citypulse` | Clé OpenWeatherMap |
| `citypulse_django` | `django_api_secret` | Secret partagé portail Django |
| `citypulse_carrier` | `<carrier_id>` | Clé API tracking par transporteur |

Les clés ne sont **jamais** écrites en clair dans les fichiers, la BDD ou les logs.

### Audit trail complet

Chaque mutation BDD → `log_action(action, details)` → table `logs` (action, details, user_id, created_at). Consultable depuis la page Journal (index 13) avec filtres, export CSV.

### Soft delete

Les clients ne sont jamais supprimés physiquement : `archived=1`. Filtre standard : `WHERE archived=0`.

### Rôles utilisateurs

`admin` / `planner` / `dispatcher` / `viewer` — permissions JSON par compte. Seuls les admins voient l'onglet Utilisateurs dans les Paramètres.

---

## 10. Tests et qualité

### Organisation

```
tests/
├── conftest.py           # Fixtures partagées (db_memory, db_populated, clients_10/50,
│                         # vehicles_3, drivers_3, orders_20/30, zones_2, qtapp...)
├── unit/                 # 17 fichiers — aucun appel réseau, SQLite :memory:
│   ├── test_greedy.py
│   ├── test_two_opt.py
│   ├── test_distance.py
│   ├── test_ortools_standard.py
│   ├── test_ortools_mdvrp.py
│   ├── test_ortools_open.py
│   ├── test_ortools_pickup.py
│   ├── test_cost_calculator.py
│   ├── test_rse_compliance.py
│   ├── test_traffic_adjuster.py
│   ├── test_anomaly.py
│   ├── test_clustering.py
│   ├── test_demand_forecast.py
│   ├── test_route_analyzer.py
│   ├── test_mistral_helpers.py
│   ├── test_weather_service.py    # mock HTTP
│   ├── test_django_sync_service.py
│   ├── test_photo_storage.py      # tmp_path
│   ├── test_clients_import.py
│   ├── test_validation.py
│   └── test_bleu.py
├── integration/
│   ├── test_db_manager.py
│   ├── test_optimization_service.py
│   └── test_report_service.py
└── ui/                    # pytest-qt (importorskip si PyQt6 absent)
    ├── test_login_widget.py
    ├── test_clients_widget.py
    ├── test_orders_widget.py
    └── test_dashboard_widget.py
```

### Objectifs de couverture

| Module | Cible |
|--------|-------|
| `engine/` | ~100% |
| `database/` | ~90% |
| `services/` | ~85% |
| `utils/` | ~80% |
| `ai/` | ~75% |
| `ui/` | ~50% |

### Exécution

```bash
pytest tests/ -v                     # tous les tests
pytest tests/ -v --timeout=90        # avec timeout global
pytest tests/unit/test_greedy.py -v  # test spécifique
pytest -k "ortools" -v               # filtrage par nom
```

**Total : 193+ tests en < 90 secondes** (pytest-timeout configuré).

Les dépendances optionnelles sont gérées : `pytest.importorskip("PyQt6")` pour les tests UI, `pytest.mark.skipif(not ORTOOLS_AVAILABLE)` pour OR-Tools.

---

## 11. Packaging et déploiement

### Application desktop — PyInstaller (Windows)

```bash
python build.py
```

**`build.py` :**
1. Vérification des imports critiques
2. Nettoyage `dist/` et `build/`
3. Génération icône PIL si `assets/icon.ico` absent
4. `pyinstaller citypulse.spec`
5. Vérification de l'exe produit
6. SHA-256 → `build_report.txt`

**`citypulse.spec` (onedir) :**
- `datas` : `settings.json`, `data/`, `assets/`, `app/ui/components/`
- `hiddenimports` : WebEngine, OR-Tools, keyring backends Windows
- `excludes` : tkinter, tests
- Version Windows `1.0.0.0` / ProductName `CityPulse Logistics`

**`installer.iss` (Inno Setup 6) :**
- Menu Démarrer + raccourci Bureau (optionnel)
- Désinstalleur propre

### Portail web — Vercel / Railway

```bash
cd citypulse-web
cp .env.example .env
# Renseigner : SECRET_KEY_DJANGO, CITYPULSE_API_SECRET, DATABASE_URL
python manage.py migrate
python manage.py runserver    # développement
waitress-serve --port=8000 config.wsgi:application  # production Windows
```

### `app/paths.py` — Chemins dev vs frozen

```python
def project_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent   # PyInstaller : à côté de l'exe
    return Path(__file__).parent.parent       # développement : racine du projet
```

Tous les fichiers utilisateur (BDD, photos, settings, logs) sont relatifs à `project_root()`.

---

## 12. Stack technique complète

### Desktop

| Couche | Bibliothèque | Version | Usage |
|--------|-------------|---------|-------|
| GUI | PyQt6 | 6.5+ | Interface 16 pages, signaux/slots |
| Cartographie | PyQt6-WebEngine + Leaflet.js | 6.5+ | Cartes interactives intégrées |
| Graphiques | Matplotlib | 3.7+ | KPIs, Gantt (via QPainter), radars, histogrammes |
| VRP | Google OR-Tools | 9.7+ | Solveur VRP industriel (LNS + GLS) |
| ML | scikit-learn | 1.3+ | KMeans, IsolationForest, silhouette |
| Graphes | NetworkX | 3.1+ | Structures de graphes |
| IA | Mistral AI SDK | — | Copilote conversationnel |
| Prévisions | statsmodels | optionnel | ARIMA demande |
| Traduction | deep-translator | — | FR/EN/AR/ES/DE |
| Qualité trad. | sacrebleu | — | Score BLEU maison |
| Données | pandas | 2.0+ | Import/export, manipulation |
| Excel | openpyxl | — | Import/export .xlsx |
| BDD | SQLite3 | natif | 24 tables, 21 migrations |
| PDF | reportlab | 4.0+ | 15 types de documents |
| QR codes | qrcode | — | QR codes dans roadbooks |
| Images | Pillow | — | Génération icône, photos |
| Réseau | requests | — | OSRM, OWM, Django API |
| Météo | OpenWeatherMap | — | Météo temps réel + trafic |
| Sécurité | keyring | 24.0+ | OS Credential Manager |
| Hash | hashlib | natif | SHA-256 + sel mots de passe |
| Tests | pytest + pytest-qt + pytest-timeout + Faker | 7.4+ | 193 tests, < 90s |
| Packaging | PyInstaller 6 | 6+ | .exe Windows onedir |
| Installateur | Inno Setup 6 | 6 | Installateur Windows |

### Portail web

| Technologie | Usage |
|-------------|-------|
| Django 5 | Framework web, ORM, admin |
| django-allauth | Authentification complète |
| Tailwind CSS (CDN) | UI responsive sans build step |
| waitress / gunicorn | Serveur WSGI production |
| PostgreSQL | Base de données production |
| Vercel / Railway | Hébergement cloud PaaS |

### Variables d'environnement

| Variable | Description |
|----------|-------------|
| `SECRET_KEY_DJANGO` | Clé secrète Django |
| `CITYPULSE_API_SECRET` | Clé partagée desktop↔web |
| `DEBUG` | `True` dev / `False` prod |
| `DATABASE_URL` | PostgreSQL prod / SQLite dev |
| `ALLOWED_HOSTS` | Domaines autorisés |

---

## Résumé des chiffres clés

| Métrique | Valeur |
|----------|--------|
| Pages UI | 16 |
| Algorithmes VRP | 3 (Greedy, 2-opt, OR-Tools) |
| Modes VRP | 5 (VRPTW, MDVRPTW, OVRP, PDPTW, VRPR) |
| Modules IA | 5 (Mistral, KMeans, IsolationForest, ARIMA, RouteAnalyzer) |
| Tables SQLite | 24 |
| Migrations | 21 |
| Types de documents générés | 15 |
| Langues | 5 (FR, EN, AR, ES, DE) |
| Tests automatisés | 193+ |
| Durée suite de tests | < 90 secondes |
| Composants réutilisables | 11 |
| Endpoints API REST | 7 |
| Version | v5.41 |

---

*CityPulse Logistics v5.41 — ENSAM Meknès — Année universitaire 2025–2026*
*DJERI-ALASSANI OUBENOUPOU & SOULEYMANE DIALLO — Encadrant : Pr. Bakkas B.*
