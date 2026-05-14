# CityPulse Logistics v5.41

> **Système d'optimisation de tournées de livraison avec Intelligence Artificielle embarquée**
>
> Application desktop Python (PyQt6) + portail web Django pour la gestion complète des tournées VRP en logistique urbaine.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Fonctionnalités principales](#fonctionnalités-principales)
3. [Architecture du projet](#architecture-du-projet)
4. [Prérequis système](#prérequis-système)
5. [Installation — Application desktop](#installation--application-desktop)
6. [Lancer l'application desktop](#lancer-lapplication-desktop)
7. [Installation — Portail web Django](#installation--portail-web-django)
8. [Lancer le portail web](#lancer-le-portail-web)
9. [Déploiement web (Vercel / Railway)](#déploiement-web-vercel--railway)
10. [Connexion bureau ↔ portail web](#connexion-bureau--portail-web)
11. [Workflow d'optimisation](#workflow-doptimisation)
12. [API REST — Contrat de synchronisation](#api-rest--contrat-de-synchronisation)
13. [Données de démonstration](#données-de-démonstration)
14. [Tests](#tests)
15. [Clés API et secrets](#clés-api-et-secrets)
16. [Build & packaging Windows](#build--packaging-windows)
17. [Pages de l'application](#pages-de-lapplication)
18. [Rôles utilisateurs](#rôles-utilisateurs)
19. [Stack technique](#stack-technique)
20. [FAQ / Dépannage](#faq--dépannage)

---

## Vue d'ensemble

CityPulse Logistics est une solution complète en deux parties :

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| **Application desktop** | Python 3.11 + PyQt6 | Planification VRP, gestion flotte/clients/chauffeurs, IA, rapports multilingues |
| **Portail web** | Django 5 + Tailwind CSS | Accès mobile chauffeurs (tournées, confirmation livraison) et clients (suivi commandes) |

Les deux composants communiquent via une **API REST sécurisée** (header `X-CityPulse-Secret`).

**Identifiants desktop par défaut :** `admin / admin`

---

## Fonctionnalités principales

### Optimisation VRP
- **3 algorithmes** comparés en temps réel : Greedy (Nearest Neighbor), 2-opt (amélioration locale), OR-Tools 9.7+ (exact)
- **5 modes VRP** : standard, multi-dépôts, open (sans retour dépôt), pickup & delivery, rechargement intermédiaire
- **Contraintes avancées** : fenêtres horaires (VRPTW), pauses RSE (réglementation CE 561/2006), zones ZFE, compétences ADR/FIMO/CACES, séquences forcées, déjeuner 12h-14h
- **Multi-objectifs** pondérés : distance, coût, CO₂, respect des créneaux

### Planification jour / semaine
- **Mode jour** : optimiser toutes les commandes `pending` pour une date sélectionnée
- **Mode semaine** : planifier automatiquement les commandes sur N jours (2 stratégies : distribuer ou respecter les dates prévues)
- **Confirmation du plan** (`✅ Confirmer le plan`) : persiste routes + arrêts en base, assigne chauffeur + véhicule, bloque les calendriers, crée une notification

### Suivi en temps réel (Gantt)
- Gantt QPainter haute performance : déplacement drag & drop, Ctrl+Z, zoom molette
- Simulation ×1/×2/×5, slider temporel 06h-20h
- Vue semaine : barre de sélection des jours planifiés avec infos (commandes, km, algo)
- Incidents, re-optimisation à chaud, météo réelle OWM

### Carte Leaflet interactive
- Routes colorées par véhicule, clients, dépôts, zones GeoJSON (ZFE, livraison, exclusion)
- Comparaison split de deux scénarios côte à côte
- Géocodage asynchrone Nominatim, bannière météo temps réel

### Rapports multilingues (FR/EN/AR/ES/DE)
- Roadbook chauffeur (PDF + QR code par arrêt)
- Bon de livraison (BL), CMR, document ADR, manifeste de chargement
- Rapport KPI, performances chauffeurs, conformité RSE, évaluation transporteurs
- Export XLSX multi-onglets, snapshot JSON complet de la base

### IA embarquée
- **Copilot Mistral AI** : chat contextuel avec actions (`navigate`, `optimize`, `create_order`), analyse globale exportable en PDF
- **KMeans pré-segmentation** : regroupement géographique avant optimisation (≥20 clients)
- **IsolationForest + Z-score** : détection d'anomalies sur clients et historique runs
- **Prévision demande** : EWMA + saisonnalité + ARIMA optionnel (`statsmodels`)

### Internationalisation
- Interface en **5 langues** : Français, English, العربية, Español, Deutsch
- Changement instantané sans redémarrage (Paramètres → Entreprise → Langue de l'interface)

---

## Architecture du projet

```
Tour/
├── main.py                         # Point d'entrée — splash, migrations, MainWindow
├── build.py                        # Build PyInstaller + rapport SHA256
├── citypulse.spec                  # Spec PyInstaller onedir
├── installer.iss                   # Script Inno Setup 6
├── README_DEPLOYMENT.md            # Guide déploiement complet
├── requirements.txt                # Dépendances Python
├── settings.json                   # Config persistée (entreprise, carte, optimisation, API…)
├── citypulse.db                    # SQLite auto-créée au premier lancement
├── citypulse.log                   # Logs JSON structurés
├── data/                           # Données packagées + photos (data/photos/)
├── assets/                         # icon.ico, logo.png
├── app/
│   ├── paths.py                    # project_root() — dev + frozen PyInstaller
│   ├── i18n.py                     # Internationalisation — tr(key, lang), 5 langues
│   ├── ai/
│   │   ├── anomaly_detection.py    # IsolationForest + Z-score
│   │   ├── clustering.py           # KMeans + DBSCAN + GeoClusterer
│   │   ├── demand_forecast.py      # EWMA + saisonnalité + ARIMA
│   │   ├── route_analyzer.py       # Analyse patterns routes/chauffeurs
│   │   └── mistral_client.py       # Client Mistral AI (keyring, context, fallback)
│   ├── database/
│   │   └── db_manager.py           # get_connection(), log_action(), init_database()
│   ├── engine/
│   │   ├── distance.py             # build_matrix() : OSRM → cache SQLite → Haversine
│   │   ├── greedy.py               # Nearest Neighbor O(n²v)
│   │   ├── two_opt.py              # Amélioration locale 2-opt + feasibility check
│   │   ├── ortools_solver.py       # OR-Tools VRPTW — 5 modes, ZFE, RSE, multi-obj
│   │   ├── cost_calculator.py      # Coûts, CO₂, ETA, conformité RSE/ADR/ZFE
│   │   └── traffic_adjuster.py     # Coefficients trafic horaires + heure optimale
│   ├── services/
│   │   ├── optimization_service.py # Orchestration VRP, validation, save_plan()
│   │   ├── weather_service.py      # OWM cache TTL 15 min (sans Qt)
│   │   ├── report_service.py       # PDF/XLSX/JSON — BL, CMR, ADR, manifeste, KPI…
│   │   └── django_sync_service.py  # Client HTTP Django (sans Qt)
│   ├── ui/
│   │   ├── main_window.py          # MainWindow, sidebar Lucide, TopBar, Copilot
│   │   ├── styles.py               # Thèmes dark/light (get_stylesheet)
│   │   ├── components/             # KPICard, StatusBadge, SearchBar, PaginationBar…
│   │   ├── dashboard_widget.py     # Tableau de bord — KPIs, graphiques, météo, alertes
│   │   ├── clients_widget.py       # Clients — CRUD paginé, import, géocodage, carte
│   │   ├── vehicles_widget.py      # Véhicules — 7 onglets, alertes docs, calendrier
│   │   ├── drivers_widget.py       # Chauffeurs — 4 onglets, indispos, équipes, perf
│   │   ├── depots_widget.py        # Dépôts — carte Leaflet, rayon couverture
│   │   ├── orders_widget.py        # Commandes — 5 KPIs, templates récurrents, lot
│   │   ├── carriers_widget.py      # Transporteurs — sous-traitance, simulation, éval
│   │   ├── optimization_widget.py  # Optimisation — mode jour/semaine, 5 onglets résultats
│   │   ├── map_widget.py           # Carte Leaflet — routes, zones, météo, split scénarios
│   │   ├── tracking_widget.py      # Suivi Gantt — simulation, semaine, incidents, PDF
│   │   ├── scenarios_widget.py     # Scénarios — comparaison, what-if, import/export JSON
│   │   ├── reports_widget.py       # Rapports — aperçu PDF natif, XLSX, planification
│   │   ├── translation_widget.py   # Traduction — 5 langues, glossaire, score BLEU
│   │   ├── logs_widget.py          # Journal — audit trail complet, export CSV
│   │   ├── notifications_widget.py # Notifications — filtres, détail, résumé journalier
│   │   └── settings_widget.py      # Paramètres — 5 onglets, snapshot BDD, OSRM, Mistral
│   └── utils/
│       ├── photo_storage.py        # Photos véhicules/chauffeurs → data/photos/
│       ├── data_validator.py       # Validation données entrantes
│       └── bleu.py                 # Score BLEU-1
├── scripts/
│   └── generate_demo_data.py       # CLI autonome — 3 datasets démo (Casablanca/Paris/Benchmark)
├── tests/
│   ├── conftest.py                 # Fixtures partagées (db_memory, clients_10/50, qtapp…)
│   ├── unit/                       # 17 fichiers — algos VRP, IA, services (sans réseau)
│   ├── integration/                # DB, optimisation, rapports
│   └── ui/                         # Widgets PyQt6 (importorskip si absent)
├── citypulse-web/                  # Portail web Django
│   ├── manage.py
│   ├── requirements.txt
│   ├── vercel.json
│   ├── SYNC_API.md                 # Contrat API REST complet
│   └── apps/
│       ├── accounts/               # Utilisateurs (role, desktop_id)
│       ├── api/                    # Endpoints REST (sync, confirmations, create_web_user)
│       ├── routes/                 # Tournées chauffeurs
│       └── tracking/               # Suivi livraisons (preuves, photos)
└── README_DEPLOYMENT.md            # Guide PyInstaller / Inno Setup / OSRM
```

---

## Prérequis système

| Élément | Version minimale | Notes |
|---------|-----------------|-------|
| Python | **3.11+** | `python --version` |
| pip | 23+ | `python -m pip install --upgrade pip` |
| Windows | 10 / 11 | Desktop conçu pour Windows ; portail web multiplateforme |
| OSRM | API publique ou locale | Distances routières réalistes |

---

## Installation — Application desktop

### 1. Cloner ou extraire le projet

```bash
git clone <url-du-repo> Tour
cd Tour
```

### 2. Créer un environnement virtuel (recommandé)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

> **PyQt6-WebEngine** (carte Leaflet + aperçu PDF) doit être installé dans le **même interpréteur** :
> ```bash
> python -m pip install PyQt6-WebEngine
> ```
> Si la carte reste grise, consulter `citypulse.log`.

### 4. Vérifier l'environnement (optionnel)

```bash
python scripts/check_environment.py
```

Vérifie Python, PyQt6, WebEngine, OR-Tools, SQLite, accès disque, keyring, OSRM public.

### 5. Vérifier OR-Tools

```bash
python -c "from ortools.constraint_solver import routing_enums_pb2; print('OR-Tools OK')"
```

---

## Lancer l'application desktop

```bash
python main.py
```

Au premier lancement :
- `citypulse.db` est créée avec toutes les migrations (21 migrations)
- Le compte `admin / admin` est créé automatiquement
- L'interface s'ouvre sur le **Tableau de bord**

### Identifiants par défaut

| Utilisateur | Mot de passe | Rôle |
|-------------|-------------|------|
| `admin` | `admin` | Administrateur — accès complet |
| `planificateur` | `admin` | Planner — optimisation, rapports |
| `dispatcher` | `admin` | Dispatcher — clients, commandes, suivi |

> Créer ou modifier les comptes dans **Paramètres → Utilisateurs**.

---

## Installation — Portail web Django

### 1. Se placer dans le dossier web

```bash
cd citypulse-web
```

### 2. Créer un environnement virtuel dédié

```bash
python -m venv .venv-web
.venv-web\Scripts\activate
```

### 3. Installer les dépendances web

```bash
pip install -r requirements.txt
```

### 4. Créer le fichier `.env`

```bash
copy .env.example .env
```

Contenu minimal :

```env
SECRET_KEY_DJANGO=<generer-avec-secrets.token_hex(32)>
CITYPULSE_API_SECRET=<meme-valeur-que-dans-keyring-desktop>
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

### 5. Appliquer les migrations et créer le superutilisateur

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## Lancer le portail web

```bash
cd citypulse-web
python manage.py runserver
```

Portail accessible sur : **http://127.0.0.1:8000**

### Pages disponibles

| URL | Description | Accès |
|-----|-------------|-------|
| `/` | Tableau de bord ou redirection | Connecté |
| `/accounts/login/` | Connexion | Public |
| `/driver/` | Mes tournées du jour | Chauffeur |
| `/driver/route/<id>/` | Détail tournée + carte + confirmation | Chauffeur |
| `/client/` | Mes commandes | Client |
| `/track/<ref>/` | Suivi commande public | Public |
| `/admin/` | Administration Django | Superuser |
| `/api/health/` | Health check API | Header secret |

### Comptes de démonstration (portail web)

Après `python manage.py seed_demo` :

| Rôle | Identifiant | Mot de passe |
|------|-------------|-------------|
| Chauffeur | `souleymane.diallo` | `Livraison2026` |
| Client | `amina.benali` | `Suivi2026` |

---

## Déploiement web (Vercel / Railway)

### Vercel

1. Variables d'environnement (Settings → Environment Variables) :
   - `SECRET_KEY_DJANGO`, `CITYPULSE_API_SECRET`, `DEBUG=False`, `ALLOWED_HOSTS=<domaine>`
2. Déployer depuis `citypulse-web/` avec le `vercel.json` fourni.

### Railway

```bash
python manage.py migrate && python manage.py collectstatic --noinput && gunicorn citypulse_web.wsgi
```

### Production locale (Windows)

```bash
pip install waitress
python manage.py collectstatic
waitress-serve --port=8000 citypulse_web.wsgi:application
```

---

## Connexion bureau ↔ portail web

### Configuration

1. **Paramètres → Sauvegarde** → saisir l'URL Django → **Tester connexion** (doit afficher ✅)
2. La **clé secrète** (`CITYPULSE_API_SECRET`) est stockée dans le keyring OS (`citypulse_django` / `django_api_secret`). Elle doit être identique à la variable `.env` côté Django.
3. Une fois configurée, la synchro est **entièrement automatique** : chaque confirmation de plan envoie les données vers le portail sans action supplémentaire.

### Fonctionnalités synchronisées

| Action desktop | Effet côté web |
|---------------|----------------|
| Exporter clients (Paramètres) | `POST /api/sync/clients/` |
| **✅ Confirmer le plan** | `POST /api/sync/routes/` — tournées poussées vers portail chauffeur |
| **✅ Confirmer le plan** | `POST /api/deliveries/confirm/` — statut + ETA + chauffeur par commande |
| **Timer 60s (page Suivi)** | `GET /api/deliveries/confirmations/` — confirmations chauffeur → statut desktop |
| Importer preuves | `GET /api/deliveries/proofs/` — photos + signatures |
| 🌐 sur un client/chauffeur | `POST /api/users/create/` — crée ou met à jour le compte web |

---

## Workflow d'optimisation

### Mode jour

```
1. Page Optimisation — sélectionner la date
2. Cocher les algorithmes (Greedy / 2-opt / OR-Tools)
3. Configurer : météo, trafic, mode VRP, objectifs, options avancées
4. [🚀 Lancer l'optimisation]
   → Résultats dans les 5 onglets (Comparaison / Détail véhicules / Graphiques /
     Simulation coûts / Conformité RSE-ADR-ZFE)
5. [✅ Confirmer le plan]
   → Routes sauvegardées en base (routes + route_stops)
   → Commandes passées en "assigned" avec vehicle_id + driver_id
   → Calendriers chauffeurs et véhicules bloqués pour ce jour
   → Notification créée dans la cloche
   → **Synchro web automatique** : routes poussées vers le portail chauffeur
     (`POST /api/sync/routes/`) + statut/ETA/chauffeur envoyé au portail client
     (`POST /api/deliveries/confirm/`) pour chaque commande du plan
6. [🗺 Carte] → visualiser les routes
7. [📍 Suivi] → Gantt avec simulation
   → Timer 60s : récupère les confirmations de livraison depuis le portail web
     et met à jour automatiquement le statut des commandes dans le desktop
```

### Mode semaine

```
1. Page Optimisation → basculer sur "Par semaine"
2. Sélectionner la date de début + nombre de jours (1-14)
3. Choisir : "Distribuer toutes les commandes" ou "Respecter les dates prévues"
4. [Analyser] → calcule les tournées pour chaque jour (dry run)
   → Tableau récapitulatif jour par jour (algo, commandes, km)
   → Double-clic sur un jour → popup détail (4 onglets)
5. [✅ Valider]
   → Même effet que "Confirmer le plan" × N jours
6. [📍 Suivi] → barre de sélection des jours + Gantt par journée
7. [📄 Rapport PDF] → rapport 5 jours détaillé
8. [📤 CSV] → export toutes les tournées semaine
```

### Assignation chauffeur / véhicule

L'assignation est **permanente** par véhicule :
1. **Page Véhicules → fiche → onglet Chauffeur** : sélectionner le chauffeur
2. **Page Chauffeurs → onglet Indisponibilités** : marquer les jours d'absence
3. Lors de l'optimisation : les véhicules dont le chauffeur est indisponible ce jour sont **exclus automatiquement** (log `⚠` visible)

---

## API REST — Contrat de synchronisation

Header requis sur tous les endpoints protégés :
```
X-CityPulse-Secret: <CITYPULSE_API_SECRET>
```

| Méthode | URL | Description |
|---------|-----|-------------|
| `GET` | `/api/health/` | Health check |
| `POST` | `/api/sync/clients/` | Synchroniser les clients |
| `POST` | `/api/sync/routes/` | Synchroniser les tournées |
| `GET` | `/api/deliveries/confirmations/` | Récupérer les confirmations |
| `GET` | `/api/deliveries/proofs/` | Récupérer les preuves photo/signature |
| `POST` | `/api/deliveries/confirm/` | Enregistrer une confirmation (chauffeur) |
| `POST` | `/api/users/create/` | Créer/mettre à jour un compte web |

> Documentation complète : `citypulse-web/SYNC_API.md`

---

## Données de démonstration

### Via l'interface (recommandé)

**Fichier → Charger données de démo** (`Ctrl+D`)

| Dataset | Contenu |
|---------|---------|
| **Casablanca** | 3 dépôts · 13 véhicules · 13 chauffeurs · 2 équipes · 80 clients · 200 commandes · 30j routes · 5 zones · 20 notifs · 3 scénarios |
| **Paris** | 2 dépôts · 5 véhicules · 5 chauffeurs · 50 clients · 80 commandes |
| **Benchmark** | 1 dépôt · 20 véhicules · 20 chauffeurs · 500 clients (tests de performance) |

> Chaque véhicule a un chauffeur assigné. Les qualifications (ADR, FIMO, permis poids lourd) sont configurées selon le type de véhicule.

### Via la ligne de commande

```bash
python scripts/generate_demo_data.py --dataset casablanca --db citypulse.db --reset
python scripts/generate_demo_data.py --dataset paris      --db citypulse.db --append
python scripts/generate_demo_data.py --dataset benchmark  --db citypulse.db
python scripts/generate_demo_data.py --dataset all        --export ./demo_data/ --reset
```

### Portail web Django

```bash
cd citypulse-web
python manage.py seed_demo
```

Crée : chauffeur `souleymane.diallo` / `Livraison2026`, client `amina.benali` / `Suivi2026`, tournées + historique 5 jours.

---

## Tests

```bash
# Suite complète
pytest tests/ -v --timeout=90

# Par catégorie
pytest tests/unit/ -v          # Algos VRP, IA, services (sans réseau)
pytest tests/integration/ -v   # DB, optimisation, rapports
pytest tests/ui/ -v            # Widgets PyQt6

# Un fichier spécifique
pytest tests/unit/test_greedy.py -v
pytest tests/unit/test_ortools_standard.py -v

# Couverture de code
pip install pytest-cov
pytest tests/ --cov=app --cov-report=html
```

**Organisation :**

| Dossier | Fichiers | Durée approx. |
|---------|---------|---------------|
| `tests/unit/` | 17 fichiers — greedy, 2opt, ortools (4 modes), distance, anomaly, clustering, forecast, analyzer, mistral, photo, cost, rse, traffic, weather, django | ~20s |
| `tests/integration/` | db_manager, optimization_service, report_service | ~30s |
| `tests/ui/` | login, clients, orders, dashboard | ~15s |

---

## Clés API et secrets

Toutes les clés sont stockées dans le **keyring OS Windows** (Credential Manager).

| Service keyring | Username | Contenu |
|----------------|----------|---------|
| `citypulse_django` | `django_api_secret` | Secret partagé avec le portail web |
| `citypulse` | `mistral_api_key` | Clé Mistral AI (Copilot) |
| `citypulse_owm` | `citypulse` | Clé OpenWeatherMap (météo) |
| `citypulse_carrier` | `<carrier_id>` | Clés API transporteurs (tracking) |

### Sources des clés API

| API | Usage | Obtenir |
|-----|-------|---------|
| **OSRM** | Matrices distances/temps routières | Instance publique ou locale Docker |
| **Mistral AI** | Copilot IA, analyse, traduction fallback | console.mistral.ai |
| **OpenWeatherMap** | Météo dashboard, carte, Gantt | openweathermap.org/api |

### OSRM local (recommandé en production)

```bash
# Docker — carte Maroc
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/morocco-latest.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/morocco-latest.osrm
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/morocco-latest.osrm
docker run -t -i -p 5000:5000 -v "${PWD}:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/morocco-latest.osrm
```

Puis : **Paramètres → Sauvegarde → OSRM URL** : `http://localhost:5000`

---

## Build & packaging Windows

### Générer l'exécutable

```bash
pip install pyinstaller pillow
python build.py
```

Ce script : vérifie les imports → nettoie `dist/` et `build/` → génère l'icône → lance PyInstaller (`citypulse.spec` onedir) → vérifie l'exe → calcule SHA256 → `build_report.txt`.

Exécutable : `dist/citypulse/citypulse.exe`
Fichiers utilisateur (`citypulse.db`, `settings.json`, `citypulse.log`) créés à côté de l'exe.

### Créer l'installateur Windows

1. Installer [Inno Setup 6](https://jrsoftware.org/isinfo.php)
2. Ouvrir `installer.iss` → Compiler → `installer_output/CityPulseSetup.exe`

---

## Pages de l'application

| # | Page | Description |
|---|------|-------------|
| 0 | **Tableau de bord** | 5 KPIs, graphiques Matplotlib, mini-météo OWM 48px, alertes documents, logs récents, navigation rapide |
| 1 | **Clients** | Table paginée 100/page, import CSV/Excel avec mapping colonnes, géocodage Nominatim asynchrone, vue carte Leaflet, détection anomalies Z-score |
| 2 | **Véhicules** | Fiche 7 onglets (identité, capacités, vitesses, coûts, chauffeur, documents, dispo & stats), alertes assurance/CT ≤30j, calendrier indisponibilités, stats flotte camembert |
| 3 | **Chauffeurs** | 4 onglets : fiche (permis, qualifs ADR/FIMO/CACES, horaires légaux RSE), indisponibilités + remplacement auto, équipes CRUD, performances Matplotlib |
| 4 | **Dépôts** | CRUD + géocodage, minimap Leaflet avec rayon couverture, stats (véhicules, clients, tournées), vue carte globale |
| 5 | **Commandes** | 5 KPIs, table paginée 80/page, dialogue 4 onglets, templates récurrents + génération semaine, import/export CSV/Excel, actions en lot (réassigner, livré, archiver) |
| 6 | **Transporteurs** | 4 onglets : fiche carriers (StarRating, clé API keyring), expéditions (refresh HTTP), simulation flotte vs sous-traitance (camembert), évaluation PDF/Excel |
| 7 | **Optimisation** | Mode **Par jour** / **Par semaine** ; 3 algos comparés ; 5 modes VRP ; météo/trafic auto ; 5 onglets résultats (Comparaison, Détail véhicules, Graphiques, Simulation coûts, Conformité RSE/ADR/ZFE) ; **✅ Confirmer le plan** |
| 8 | **Carte** | Leaflet interactif, couches activables (clients, dépôts, zones, véhicules, heatmap), bascule fond de carte, bannière météo, comparaison split 2 scénarios, géocodage adresse |
| 9 | **Suivi** | Gantt QPainter (blocs colorés, hover, clic droit, drag & drop, Ctrl+Z) ; simulation ×1/×2/×5 ; **barre sélection journée** (mode semaine) ; météo réelle OWM ; incidents ; **📄 Rapport PDF** (jour ou semaine) |
| 10 | **Scénarios** | QSplitter table/détail, tags + description éditables, comparaison 2 scénarios (tableau + barres Matplotlib), what-if, import/export JSON, envoi vers carte split |
| 11 | **Traduction** | Traduction logistique FR/EN/AR/ES/DE (Google Translate / Mistral / hors-ligne), glossaire CRUD, score BLEU sacrebleu, historique avec méthode et validation |
| 12 | **Rapports** | QSplitter catégories/aperçu, 6 catégories (Opérationnels, Analytiques, Clients, Transporteurs, Conformité, Documents légaux), aperçu PDF natif (`QPdfView`), langue du rapport sélectionnable, planification automatique |
| 13 | **Journal** | Audit trail complet (log_action), filtre 30j par défaut, résolution username, export CSV |
| 14 | **Notifications** | Filtres type/sévérité/non-lus, panneau détail 280px, liens navigation vers les pages, résumé journalier automatique |
| 15 | **Paramètres** | 5 onglets (Entreprise, Carte, Rapports, Utilisateurs, Sauvegarde) + barre 💾 fixée en bas ; thème dark/light ; langue UI ; snapshot BDD ; OSRM URL + test ; Mistral ; CRUD utilisateurs |

---

## Rôles utilisateurs

### Application desktop

| Rôle | Accès |
|------|-------|
| `admin` / `administrateur` | Toutes les pages, gestion utilisateurs, snapshot BDD |
| `planner` | Optimisation, carte, scénarios, rapports, traduction |
| `dispatcher` | Clients, véhicules, commandes, chauffeurs, suivi, notifications |
| `viewer` | Lecture seule sur toutes les pages |

### Portail web Django

| Rôle | Pages accessibles |
|------|------------------|
| `driver` | `/driver/` — Mes tournées, carte Leaflet, confirmation + photo |
| `client` | `/client/` — Mes commandes, suivi timeline |
| `admin` (superuser) | `/admin/` + toutes pages + API |

---

## Stack technique

| Couche | Technologies | Version |
|--------|-------------|---------|
| GUI desktop | PyQt6, PyQt6-WebEngine, Leaflet.js, Matplotlib | 6.5+ |
| Algorithmes VRP | Google OR-Tools, scikit-learn (KMeans, IsolationForest), NetworkX | 9.7+ |
| IA / LLM | Mistral AI SDK (`mistralai`), deep-translator, sacrebleu, statsmodels (optionnel) | — |
| Données | pandas, openpyxl, SQLite3 | 2.0+ |
| Rapports | reportlab, qrcode, Pillow | 4.0+ |
| Météo / Réseau | requests, OpenWeatherMap, OSRM | — |
| Sécurité | keyring (OS Credential Manager), hashlib SHA-256+salt | 24.0+ |
| Environnement | python-dotenv | 1.0+ |
| Portail web | Django 5, django-allauth, Tailwind CSS (CDN), SQLite (dev) / PostgreSQL (prod) | 5.0+ |
| Déploiement web | Vercel, Railway, waitress (Windows) | — |
| Tests | pytest, pytest-qt, pytest-timeout, Faker | 7.4+ |
| Packaging | PyInstaller 6 (onedir), Inno Setup 6 | — |

---

## FAQ / Dépannage

### La carte Leaflet ne s'affiche pas (tuiles grises)

```bash
python -c "from PyQt6.QtWebEngineWidgets import QWebEngineView; print('WebEngine OK')"
# Si erreur DLL : installer les redistribuables VC++ https://aka.ms/vs/17/release/vc_redist.x64.exe
```

### OR-Tools non disponible

```bash
pip install ortools
python -c "from ortools.constraint_solver import routing_enums_pb2; print('OK')"
```

### Le Copilot IA ne répond pas

1. Vérifier la clé Mistral dans **Paramètres → Entreprise → Clé API Mistral**
2. Vérifier que `mistralai` est installé : `pip install mistralai`

### Le portail web retourne 401 Unauthorized

Vérifier que `CITYPULSE_API_SECRET` dans `.env` correspond à la valeur dans le keyring :
```python
import keyring
print(keyring.get_password("citypulse_django", "django_api_secret"))
```

### Les véhicules n'ont pas de chauffeur après l'import démo

Dans **Page Véhicules → fiche → onglet Chauffeur**, assigner le chauffeur puis enregistrer.
Le calendrier chauffeur affichera automatiquement les journées en orange après confirmation du plan.

### Une commande reste "En attente" après avoir confirmé un plan

Deux causes possibles :

**1. Le client n'était pas dans l'optimisation** — l'algorithme ne peut assigner que les clients réellement inclus dans une tournée. Vérifier que :
- Le client a des coordonnées valides (lat/lon non nuls)
- Sa demande en kg est inférieure à la capacité du plus grand véhicule
- Sa fenêtre horaire est compatible avec les créneaux disponibles

**2. L'optimisation est lancée sur un nombre limité de clients** — si la capacité totale de la flotte est inférieure à la demande totale, certains clients resteront non-routés. Augmenter la flotte ou lancer une optimisation sur un sous-ensemble de clients.

> Note : depuis la v5.41, `save_plan()` cherche n'importe quelle commande pending du client (toute date confondue, en donnant la priorité à la date du plan), ce qui évite les faux "En attente" liés à une date non concordante.

### La demande d'un client dépasse la capacité maximale de la flotte

L'algorithme exclut silencieusement ce client. Vérifier la valeur du champ **Demande kg** dans la fiche client et la comparer à la colonne **Cap. kg** dans **Page Véhicules**.

### La base de données est corrompue

```bash
# Via l'app : Paramètres → Sauvegarde → Vérifier intégrité BDD
# En ligne de commande :
python -c "import sqlite3; c=sqlite3.connect('citypulse.db'); print(c.execute('PRAGMA integrity_check').fetchone())"
```

### Réinitialiser complètement

```bash
del citypulse.db
python main.py    # recréée avec admin/admin
# Recharger les données : Fichier → Charger données de démo (Ctrl+D)
```

### Erreur Unicode sur Windows (console)

```bash
set PYTHONIOENCODING=utf-8
python main.py
```

### OSRM non disponible — fallback automatique

Si OSRM est inaccessible, `distance.py` bascule automatiquement sur le **cache SQLite** puis sur **Haversine** (vol d'oiseau ×1.3). La colonne `distance_source` dans `algo_results` indique la source utilisée.

### Changer le secret API partagé desktop ↔ web

```python
import secrets; print(secrets.token_hex(32))
```
1. Coller dans `citypulse-web/.env` → redémarrer Django
2. **Paramètres → Sauvegarde → Clé secrète Django** → coller → Sauvegarder

### Internationalisation (5 langues)

**Paramètres → Entreprise → Langue de l'interface** — changement instantané sans redémarrage.
Les rapports PDF ont leur propre sélecteur de langue dans **Page Rapports → Langue du rapport**.

---

## Binôme & encadrement

| Rôle | Nom |
|------|-----|
| Étudiant | DJERI-ALASSANI OUBENOUPOU |
| Étudiant | SOULEYMANE DIALLO |
| Encadrant | Pr. Bakkas B. |
| Établissement | ENSAM — Université Moulay Ismaïl, Meknès |
| Année | 2025 – 2026 |

---

*CityPulse Logistics v5.41 — Guide déploiement : `README_DEPLOYMENT.md` · Contrat API REST : `citypulse-web/SYNC_API.md`*
