# CityPulse Logistics v5.41

Application desktop Python d'optimisation de tournées (VRP) avec IA embarquée. Interface PyQt6, **16 pages** (index 0–15), 3 algorithmes VRP comparés en temps réel.

**Lancement :** `python main.py`  
**Tests :** `pytest tests/ -v` (193 collectés — + `test_photo_storage` ; v5.41 : corrections optimisation/scénarios + enrichissement rapport.tex (formulation VRPTW, diagrammes UML/déploiement/états/classes/IA/distance) (voir ci-dessous) ; v5.40 audit complet : corrections nav, SQL, signaux, async geocoding, logs, glossaire, rapports ; v5.35 i18n : `app/i18n.py` + `retranslate_ui(lang)` sur chaque page ; `system.ui_lang` 5 codes FR/EN/AR/ES/DE ; v5.34 transporteurs : `StarRating(rating, max_stars, read_only)` + `get_rating()` ; note tableau ★/☆ ; bouton « Simuler coûts… » → onglet simulation ; onglet « Simuler (flotte vs S/T)» ; v5.33 commandes inchangé ci-dessous : KPI `KPICard.set_value` ; statuts tolérants ; `StatusBadge` ; priorité ★/☆)  
**Identifiants par défaut :** `admin / admin`  
**Base de données :** `citypulse.db` (SQLite, créée automatiquement au premier lancement)

---

## ⚠️ Règle de mise à jour automatique de ce fichier

**À chaque modification apportée à l'application — même si le prompt ne le demande pas explicitement — Claude doit mettre à jour ce fichier `CLAUDE.md` pour refléter les changements effectués.**

Cela inclut, sans s'y limiter :
- Ajout ou suppression d'un fichier ou module → mettre à jour la **Structure du projet**
- Ajout d'une nouvelle table SQLite → mettre à jour **Tables SQLite clés**
- Ajout ou modification d'un algorithme, service, widget → mettre à jour la section concernée
- Changement de dépendance → mettre à jour le **Stack technique**
- Nouvelle convention introduite → mettre à jour **Conventions de code**
- Nouveau signal Qt ou nouveau flag de disponibilité → mettre à jour **Architecture en couches**
- Changement de version (`v5.0` → `v5.1`, etc.) → mettre à jour le titre et les métadonnées

Ce fichier est la **source de vérité** du projet. Il doit toujours rester synchronisé avec le code réel.

---

## Stack technique

| Couche | Technologies |
|--------|-------------|
| GUI | PyQt6 6.5+, PyQt6-WebEngine (Leaflet.js), Matplotlib |
| VRP | Google OR-Tools 9.7+, scikit-learn (KMeans, IsolationForest), NetworkX |
| IA/LLM | Mistral AI SDK, deep-translator, sacrebleu ; statsmodels optionnel (ARIMA prévisions) |
| Données | pandas, openpyxl, reportlab, SQLite3 |
| Sécurité | keyring (OS keyring pour clés API), hashlib SHA256+salt |
| Réseau | requests (OSRM, OWM `weather_service`, API Django `django_sync_service`) |
| Tests | pytest 7.4+, pytest-qt, pytest-timeout (90 s) |
| Packaging | PyInstaller 6+ (`citypulse.spec` onedir), `build.py`, Inno Setup `installer.iss`, `README_DEPLOYMENT.md` |

---

## Packaging & déploiement (Windows)

| Fichier | Rôle |
|---------|------|
| `app/paths.py` | `project_root()` / `settings_json_path()` — en mode PyInstaller, racine = dossier de `sys.executable` (données utilisateur à côté de l’exe). |
| `citypulse.spec` | PyInstaller **onedir** : `datas` (settings.json, data/, assets/, app/ui/components/), hiddenimports WebEngine + OR-Tools + keyring (+ `keyring.backends.Windows`), excludes tkinter/tests, icône `assets/icon.ico`, version Windows 1.0.0.0 / ProductName CityPulse Logistics. |
| `build.py` | Vérif imports, nettoyage dist/build, génération icône PIL si besoin, PyInstaller, vérif exe, SHA256 → `build_report.txt`. |
| `installer.iss` | Inno Setup 6 : AppName / AppVersion 1.0, menu Démarrer, raccourci Bureau (tâche optionnelle), désinstalleur. |
| `scripts/check_environment.py` | Python ≥3.11, PyQt6, WebEngine, OR-Tools, SQLite, écriture disque, keyring, test HTTP OSRM public. |
| `README_DEPLOYMENT.md` | Prérequis, build, installateur, première utilisation, OSRM local, clés API, FAQ. |

**Build :** `pip install -r requirements.txt` puis `python build.py` → `dist/citypulse/`. **Installateur :** compiler `installer.iss` après le build.

---

## Structure du projet

```
Tour/
├── main.py                        # Point d'entrée — vérif dépendances, splash, migrations, MainWindow
├── build.py                       # Build PyInstaller + rapport SHA256
├── citypulse.spec                 # Spec PyInstaller onedir
├── installer.iss                  # Script Inno Setup 6
├── README_DEPLOYMENT.md           # Guide déploiement / OSRM / API
├── requirements.txt
├── settings.json                  # Config persistée (entreprise, carte, optimisation, rapports, API, django, notif)
├── data/                          # Données packagées + photos utilisateur (`data/photos/`, `.gitkeep`)
├── assets/                        # icon.ico, logo.png (icône générée par build.py si absente)
├── citypulse.db                   # SQLite auto-créée
├── citypulse.log                  # Logs JSON structurés
├── app/
│   ├── paths.py                   # project_root(), settings_json_path() — dev + frozen PyInstaller
│   ├── i18n.py                    # Internationalisation UI — tr(key, lang), LANG_CODES, LANG_DISPLAY (5 langues)
│   ├── ai/                        # Modules IA/ML (pas de PyQt6 ni DB directe)
│   │   ├── anomaly_detection.py   # IsolationForest + Z-score + detect_all(clients, orders)
│   │   ├── clustering.py          # KMeans + GeoClusterer (k optimal, DBSCAN, GeoJSON)
│   │   ├── demand_forecast.py     # ForecastEngine : EWMA, saisonnalité, ARIMA si statsmodels
│   │   ├── route_analyzer.py      # RouteAnalyzer.analyze_patterns(routes, stops, drivers)
│   │   └── mistral_client.py      # Mistral keyring, build_context(db_stats), parse_command, fallback
│   ├── database/
│   │   └── db_manager.py          # get_connection(), log_action(), hash_password(), init_database()
│   ├── engine/                    # Algorithmes VRP — pas de PyQt6, pas de DB
│   │   ├── distance.py            # build_matrix() : OSRM → cache SQLite → Haversine
│   │   ├── greedy.py              # Nearest Neighbor O(n²v)
│   │   ├── two_opt.py             # Amélioration locale, retourne convergence[]
│   │   ├── ortools_solver.py      # VRP v2 : 5 modes, ZFE, RSE, séquences, multi-obj
│   │   ├── cost_calculator.py     # Coûts route, CO2, ETA, conformité RSE/ADR/ZFE
│   │   ├── traffic_adjuster.py    # Coefficients trafic horaires + heure départ optimale
│   │   └── data/
│   │       └── traffic_coefficients.json  # Coefficients par heure et type de jour
│   ├── services/
│   │   ├── optimization_service.py  # run_optimization(), validate_inputs(), save_result()
│   │   ├── weather_service.py       # OWM cache TTL 15 min, get_current/forecast, traffic factor, route alerts (sans Qt)
│   │   ├── django_sync_service.py   # DjangoSyncService : health_check, sync_clients/routes, pull_confirmations/proofs (sans Qt)
│   │   └── report_service.py        # ReportService : PDF/XLSX/JSON + generate_all_vehicles_pdf()
│   ├── ui/                        # Widgets PyQt6 (un fichier = un widget)
│   │   ├── dashboard_widget.py    # Dashboard v2 — 5 KPIs, 2 charts Mpl, mini météo 48px (OWM), alertes, logs, stats
│   │   ├── main_window.py         # MainWindow, sidebar Lucide, TopBar, #pageStackHost (gouttière), Copilot, fade-in ; _apply_language(lang), _NAV_KEYS, NavButton.set_label()
│   │   ├── copilot_widget.py      # Copilot QDock : chips, command_ready, analyse PDF, ai_conversations
│   │   ├── styles.py              # get_stylesheet(theme='dark'|'light') — deux thèmes complets
│   │   ├── lucide_icons.py        # Pictogrammes stroke Lucide → QPixmap/QIcon ; apply_action_button (icône seule)
│   │   ├── toast.py               # show_toast(window, msg, type)
│   │   ├── webengine_support.py   # HAS_WEB / QWebEngineView — probe PyQt6-WebEngine + log échec import
│   │   ├── help_dialog.py         # show_help(widget, page_key)
│   │   ├── loading_overlay.py     # LoadingOverlay(parent) — .start() / .stop()
│   │   ├── empty_state.py         # EmptyState legacy (préférer components/empty_state.py)
│   │   ├── import_dialog.py       # ColumnSelectionDialog — sélection colonnes import
│   │   ├── components/            # Bibliothèque de composants réutilisables
│   │   │   ├── __init__.py        # Exports : KPICard, StatusBadge, SearchBar, TopBar, …
│   │   │   ├── kpi_card.py        # KPICard — update() / set_value() (alias), tendance + hover, min 200×110
│   │   │   ├── status_badge.py    # StatusBadge(QLabel) — success/warning/danger/info/pending/active
│   │   │   ├── section_header.py  # SectionHeader — titre + sous-titre + bouton action + ligne accent
│   │   │   ├── search_bar.py      # SearchBar — _edit + get_text()/text(), search_changed(str), debounce 300ms
│   │   │   ├── confirm_dialog.py  # ConfirmDialog ; _dialog_qss() / dialog_base_qss() ; light_dialog_buttons_qss() (dialogs clairs)
│   │   │   ├── empty_state.py     # EmptyState — icône + titre + sous-titre + action
│   │   │   ├── notification_bell.py # NotificationBell — icône Lucide `bell` + badge numérique + dropdown 5 notifs
│   │   │   ├── loading_spinner.py # LoadingSpinner — QPainter arc tournant, QTimer 50ms
│   │   │   ├── pagination_bar.py  # PaginationBar — signal page_changed(page, offset, limit)
│   │   │   ├── collapsible_section.py # CollapsibleSection — ▶/▼ cliquable + animation 150ms
│   │   │   ├── star_rating.py     # StarRating — signal rating_changed(int), ★/☆ unicode
│   │   │   └── topbar.py          # TopBar — fil d'Ariane + NotificationBell + user (icône Lucide) + déconnexion h=48px
│   │   ├── demo_loader.py         # DemoLoaderDialog(QDialog) + legacy load_demo_scenario()
│   │   ├── vehicles_widget.py     # Page flotte v2 — bandeau alertes, table+StatusBadge,
│   │   │                          #  fiche 7 onglets, calendrier dispo, stats+camembert
│   │   ├── clients_widget.py      # Page clients v2 — table paginée, dialogue 5 onglets,
│   │   │                          #  import CSV/Excel+mapping, export CSV/XLS/JSON,
│   │   │                          #  géocodage Nominatim, Vue Carte Leaflet, anomalies
│   │   ├── drivers_widget.py      # Page chauffeurs v1 — QTabWidget 4 onglets :
│   │   │                          #  👤 table+fiche 5 onglets, bandeau alertes permis
│   │   │                          #  📅 calendrier indispos + suggestion remplacement
│   │   │                          #  👥 CRUD équipes + membres + manager
│   │   │                          #  📊 perf filtres + tableau + Matplotlib barres + CSV
│   │   ├── depots_widget.py       # Page dépôts v2 — table+SectionHeader, fiche 3 onglets
│   │   │                          #  (Infos, Carte Leaflet minimap, Stats), Vue globale
│   │   ├── orders_widget.py       # Page commandes v1 — 5 KPICards, table paginée+StatusBadge,
│   │   │                          #  dialogue 4 onglets (Commande, Marchandises, Créneaux,
│   │   │                          #  Assignation), templates récurrents CRUD, générer semaine,
│   │   │                          #  import/export CSV/Excel, actions en lot
│   │   ├── carriers_widget.py     # Page transporteurs v1 — QTabWidget 4 onglets :
│   │   │                          #  🚛 table+fiche 3 onglets (Infos, Capacités & Tarifs, Perf)
│   │   │                          #  📦 expéditions + refresh statuts HTTP (QThread)
│   │   │                          #  💰 simulation flotte vs sous-traitance + camembert Matplotlib
│   │   │                          #  📊 évaluation récap + barres Matplotlib + export PDF/Excel
│   │   ├── reports_widget.py      # Rapports v2 — QSplitter 30/70, QThread+LoadingOverlay,
│   │   │                          #  aperçu QWebEngineView, historique reports_history, timer 60s
│   │   ├── optimization_widget.py # Optimisation v3 + bandeau météo si facteur trafic > 1.1
│   │   ├── map_widget.py          # Carte Leaflet + bannière météo HTML ; `apply_dual_scenario_routes` (split compare)
│   │   ├── tracking_widget.py     # Suivi Gantt v3 + bouton 🌤 Météo réelle (`weather_service`)
│   │   ├── scenarios_widget.py    # Compare 2 scénarios, what-if, import/export JSON ; QSplitter table/détail ; `compare_map_requested`
│   │   ├── notifications_widget.py # Filtres, liste+détail 280px, résumé quotidien (QTimer), `navigate_request` → MainWindow
│   │   ├── translation_widget.py
│   │   ├── logs_widget.py
│   │   ├── settings_widget.py     # Paramètres v2 : QTabWidget 5 onglets + 💾 sticky ; CRUD users admin, snapshot BDD ; OSRM dans Sauvegarde ; Mistral dans Entreprise ; clés API (.env) ; sélecteur « Langue de l'interface » → _apply_language()
│   │   └── [*_widget.py]          # Autres : login, …
│   └── utils/
│       ├── bleu.py                # Calcul BLEU-1 maison
│       ├── data_validator.py      # Validation données entrantes
│       └── photo_storage.py       # Photos véhicules/chauffeurs → `data/photos/` (chemins relatifs à `project_root()`)
├── scripts/
│   └── generate_demo_data.py      # CLI autonome (sans Qt) — génère 3 datasets de démo
└── tests/
    ├── conftest.py                # db_memory, db_populated, depot_* , clients_10/50, vehicles_3,
    │                              #  driver_1, orders_20/30, route_sample, qtapp, drivers_3, zones_2
    ├── unit/                      # Tests unitaires — pas de réseau (requests mocké si besoin)
    │   ├── ortools_helpers.py     # Helpers OR-Tools partagés
    │   ├── test_greedy.py
    │   ├── test_two_opt.py
    │   ├── test_distance.py
    │   ├── test_bleu.py
    │   ├── test_validation.py
    │   ├── test_anomaly.py
    │   ├── test_clustering.py
    │   ├── test_demand_forecast.py
    │   ├── test_route_analyzer.py
    │   ├── test_mistral_helpers.py
    │   ├── test_photo_storage.py  # save_user_photo / finalize (tmp_path)
    │   ├── test_clients_import.py # importorskip PyQt6 si widget requis
    │   ├── test_ortools_mdvrp.py
    │   ├── test_ortools_standard.py
    │   ├── test_ortools_open.py
    │   ├── test_ortools_pickup.py
    │   ├── test_cost_calculator.py
    │   ├── test_rse_compliance.py
    │   ├── test_traffic_adjuster.py
    │   ├── test_weather_service.py # mock HTTP
    │   └── test_django_sync_service.py
    ├── integration/
    │   ├── test_db_manager.py
    │   ├── test_optimization_service.py
    │   └── test_report_service.py
    └── ui/                        # pytest-qt (importorskip si PyQt6 absent)
        ├── test_login_widget.py
        ├── test_clients_widget.py
        ├── test_orders_widget.py
        └── test_dashboard_widget.py
```

**Couverture cible (documentation) :** engine ~100 % · services ~85 % · ai ~75 % · db ~90 % · ui ~50 % — `pytest-cov` optionnel.

---

## Conventions de code

### Tests (`tests/`)
- Structure **`unit/`** · **`integration/`** · **`ui/`** ; `conftest.py` racine.
- Style **Arrange / Act / Assert** (commentaires `# Arrange` … si utile).
- **Pas d’appels réseau** : mocker `requests` / APIs ; SQLite via `tmp_path` (`db_memory`, `db_populated`).
- Durée suite ciblée **&lt; 90 s** (`pytest-timeout`). OR-Tools / PyQt6 : `skip` / `importorskip` si absents.

### Nommage
- **Classes :** PascalCase (`ClientsWidget`, `OptimizationThread`, `KPICard`)
- **Méthodes/fonctions :** snake_case (`refresh_data`, `build_matrix`)
- **Méthodes privées :** préfixe `_` (`_setup_ui`, `_on_result`, `_build_traffic_group`)
- **Constantes module :** UPPER_CASE (`ALGO_COLORS`, `LEAFLET_HTML`, `LOGISTICS_DICT`)
- **Palette locale :** dict `C = {"bg": "#0D1B2A", ...}` en tête de chaque widget

### Pattern widget PyQt6
Tout widget de page suit ce squelette strict :

```python
class FooWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._setup_ui()          # construction UI uniquement

    def _setup_ui(self):
        # construction des widgets, jamais de requêtes BDD ici
        pass

    def refresh_data(self):
        # requêtes BDD et mise à jour UI — appelé par MainWindow à chaque navigation
        pass
```

- `_setup_ui()` : construction uniquement, jamais de requêtes BDD
- `refresh_data()` : requêtes BDD et mise à jour de l'UI — toujours présente
- Navigation : `self.main_window._nav_to(index)` (index = numéro de page **0–15**)
- Toast : `show_toast(self.window(), "message", "success"|"error"|"info")`
- Aide : `show_help(self, "page_key")`
- Overlay chargement : `self._overlay.start("msg")` / `self._overlay.stop()`
- **Marges (v5.32)** : gouttière globale `#pageStackHost` dans `MainWindow` — dans `_setup_ui()` des pages, marges root modérées (souvent **4–8 px**) et **`setSpacing(14–18)`** entre en-tête / barres d’outils / table pour garder de l’air sans doubler les bords.

### Pattern base de données
```python
from ..database.db_manager import get_connection, log_action

# Lecture
conn = get_connection()
rows = conn.execute("SELECT * FROM clients WHERE archived=0").fetchall()
conn.close()

# Écriture — toujours suivie de log_action()
conn = get_connection()
conn.execute("UPDATE clients SET name=? WHERE id=?", (name, client_id))
conn.commit()
conn.close()
log_action("CLIENT_UPDATE", f"Client #{client_id} modifié")  # OBLIGATOIRE
```

- **Toujours** `get_connection()`, jamais `sqlite3.connect()` directement
- **Toujours** `log_action()` après toute mutation (audit trail légal)
- Soft delete : `archived=1` — ne jamais supprimer physiquement un client
- Filtre standard clients : `WHERE archived=0`
- Clés API : via `keyring`, jamais hardcodées

### Pattern threading (tâches longues)
```python
class FooThread(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error    = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("En cours…")
            result = do_heavy_work()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
```

- Jamais bloquer le thread principal Qt (toute op > ~50 ms → QThread)
- Toujours émettre `error` dans le `except`, ne jamais laisser l'exception remonter
- Garder une référence : `self._threads.append(thread)` avant `thread.start()`
- Connecter les signaux **avant** `.start()`

### Ordre des imports
```python
# 1. Stdlib
import logging, json, os

# 2. PyQt6
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# 3. Local (imports relatifs dans app/)
from ..database.db_manager import get_connection, log_action
from ..services.optimization_service import run_optimization
from .toast import show_toast
```

### Gestion des erreurs
- `ValidationError` (de `optimization_service`) → `QMessageBox.warning()` à l'utilisateur
- Exception inattendue → `logger.exception()` (loggée dans `citypulse.log`)
- Dépendances optionnelles : vérifier avant usage

```python
logger = logging.getLogger(__name__)   # en tête de chaque module

# Carte / aperçu PDF : importer depuis webengine_support (une seule sonde + log si échec)
from .webengine_support import HAS_WEB, QWebEngineView
```

Flags de disponibilité existants : `ORTOOLS_AVAILABLE` (ortools_solver.py), `HAS_MPL` (dashboard), `HAS_WEB` (`webengine_support.py` → map_widget, clients_widget, depots_widget, reports_widget), `HAS_REQUESTS` (clients_widget, depots_widget geocoder), `HAS_OPENPYXL` (clients_widget, orders_widget export Excel).

### Style QSS
- Styles globaux : `get_stylesheet(theme='dark'|'light')` dans `styles.py`, appliqué une seule fois dans `main.py`
- Changement de thème : `MainWindow._apply_theme(theme)` — applique la feuille de style globale **et** re-style les éléments hardcodés de la fenêtre principale (`_central`, `_sidebar`, `_logo_row`, `_nav_area`, `_nav_widget`, `_sidebar_footer`, `_page_stack_host`, `stack`) en utilisant `THEMES[theme]` ; sauvegarde dans `self._current_theme` (initialisé à `"dark"` dans `__init__`)
- Deux thèmes : **dark** (défaut — fond `#0D1B2A`, sidebar/panneaux `#162840` / `#243F58`, accent `#00D4FF`, texte secondaire `#7FA8C0`) et **light** (`#F0F4F8` / accent `#1565C0`)
- Backward-compat : `DARK_STYLE`, `LIGHT_STYLE`, `C`, `COLORS` restent exportés depuis `styles.py`
- **Boutons nommés (`#primaryBtn`, `#secondaryBtn`, `#dangerBtn`, `#ghostBtn`, `#iconBtn`)** : dans `styles.py`, chaque état pertinent (`:default`, `:hover`, `:pressed`, `:disabled`) définit explicitement `color` et `background-color` (palette `accent_text`, `text`, `text_sec`) pour éviter un texte hérité illisible ; coins arrondis via les quatre propriétés `border-*-radius` (pas de raccourci multi-valeurs). **`dark.accent_text = "#FFFFFF"`** (blanc) pour que le texte `#primaryBtn` reste lisible même si un ancêtre widget a un stylesheet local qui remplace le fond.
- **Sélecteurs QSS locaux scoped (v5.36)** : les conteneurs `QWidget` anonymes qui ont besoin d'une couleur de fond DOIVENT utiliser `widget.setObjectName("uniqName")` + `widget.setStyleSheet("QWidget#uniqName{background:...}")` plutôt que `widget.setStyleSheet("background:...")`. Sans le sélecteur de type+ID, la règle descend à TOUS les descendants QWidget (boutons inclus) et écrase le stylesheet global de l'application — causant du texte invisible. Motif utilisé dans `settings_widget._wrap_scroll` (`QWidget#_swInner`), `dashboard_widget` (`QWidget#dashContainer`), `translation_widget` (`QWidget#translContainer`), etc.
- **Dialogs sombres** : fusionner sur le `QDialog` (ou racine) `from app.ui.components.confirm_dialog import _dialog_qss` (alias `dialog_base_qss()`) **avant** les règles locales `QDialog{{background:…}}` dès que des boutons `#primaryBtn` / `#secondaryBtn` sont utilisés.
- **Dialogs à fond clair** (`import_dialog.py`, `help_dialog.py`) : ajouter `light_dialog_buttons_qss()` pour `#primaryBtn` et `QPushButton` standards sur fond `#ffffff`.
- **QDialogButtonBox** : règles globales dans `styles.py` (`QDialog QDialogButtonBox QPushButton`) + duplication dans `_dialog_qss()` pour les dialogues qui surchargent le QSS.
- Bouton principal : `btn.setObjectName("primaryBtn")`
- Bouton secondaire : `btn.setObjectName("secondaryBtn")`
- Bouton danger : `btn.setObjectName("dangerBtn")`
- Bouton fantôme : `btn.setObjectName("ghostBtn")`
- Bouton icône : `btn.setObjectName("iconBtn")`
- Titre de page : `label.setObjectName("heading")`
- Sous-titre : `label.setObjectName("subheading")`
- Légende : `label.setObjectName("caption")`
- Couleurs locales : dict `C = {...}` en tête du widget (même palette que `styles.py`)
- Composants réutilisables : `from app.ui.components import KPICard, SearchBar, ConfirmDialog, dialog_base_qss, light_dialog_buttons_qss, …`

---

## Architecture en couches

```
UI (app/ui/)             ← PyQt6 uniquement, pas de logique métier directe
    ↓
Services (app/services/) ← orchestration, validation, persistance
    ↓
Engine (app/engine/)     ← algos VRP, Python pur, zéro Qt/DB
AI (app/ai/)             ← modules ML, Python pur, zéro Qt/DB
    ↓ tous utilisent
Database (app/database/) ← accès SQLite centralisé via get_connection()
```

**Règle stricte :** `engine/` et `ai/` ne doivent jamais importer PyQt6 ni `app.database`.

### Modules IA (`app/ai/`) — v5.13
| Module | Rôle |
|--------|------|
| `demand_forecast.py` | `ForecastEngine.predict_client_demand`, `predict_fleet_demand` ; `forecast_from_algo_results_history()` pour l'UI (série passée en paramètre) |
| `clustering.py` | `GeoClusterer` : `find_optimal_k`, `cluster_kmeans`, `cluster_dbscan`, `export_clusters_geojson` |
| `anomaly_detection.py` | `detect_anomalies(records)` runs ; `detect_all(clients_data, orders_data)` + champ `suggestion` |
| `route_analyzer.py` | `RouteAnalyzer.analyze_patterns` : durées plan vs réel, retards par chauffeur, regroupements |
| `mistral_client.py` | `build_context(db_stats)`, `parse_command`, `get_fallback_response` ; `send_message(..., db_stats=)` |

### Signaux principaux
- `routes_ready = pyqtSignal(dict)` — émis par `OptimizationWidget` après chaque run, reçu par `MapWidget` et `TrackingWidget`
- `OptimizationThread` émet : `progress(str)`, `partial_result(str, dict)`, `finished(str, dict)`, `error(str, str)`, `compliance(str, dict)`
- `search_changed = pyqtSignal(str)` — émis par `SearchBar` avec debounce 300ms
- `page_changed = pyqtSignal(int, int, int)` — émis par `PaginationBar` (page, offset, limit)
- `rating_changed = pyqtSignal(int)` — émis par `StarRating`
- `command_ready = pyqtSignal(dict)` — émis par `CopilotDockWidget` lorsque l'utilisateur confirme une action IA (`navigate` / `optimize` / `create_order`) ; `MainWindow.dispatch_copilot_command()`
- `compare_map_requested = pyqtSignal(dict, dict)` — émis par `ScenariosWidget` ; `MainWindow._on_scenario_compare_map` → `MapWidget.apply_dual_scenario_routes(left, right)`
- `navigate_request = pyqtSignal(int)` — émis par `NotificationsWidget` (ex. liens `citypulse://nav/N`) ; `MainWindow._nav_to`

### Internationalisation UI (`app/i18n.py`) — v5.35

Module statique sans Qt ni DB. Utilisé uniquement par la couche UI.

```python
LANG_CODES: list[str] = ["fr", "en", "ar", "es", "de"]
LANG_DISPLAY: list[str] = ["Français (FR)", "English (EN)", "العربية (AR)", "Español (ES)", "Deutsch (DE)"]

def tr(key: str, lang: str = "fr") -> str: ...
```

- Clés couvrent : `nav.*` (sidebar 16 items), `page.*` (titres pages), `menu.*` (barre de menus), `section.*` (SectionHeader), `drivers.tab.*` / `carriers.tab.*` / `settings.tab.*` (onglets QTabWidget)
- Activation : `MainWindow._apply_language(lang)` — met à jour sidebar, breadcrumb, menu bar, compteurs statut, puis appelle `retranslate_ui(lang)` sur chaque widget de page
- Déclencheur UI : sélecteur « Langue de l’interface » dans `settings_widget.py` onglet Entreprise → `_on_lang_changed(index)` → `_apply_language()`
- Persistance : clé `system.ui_lang` dans `settings.json` (un des 5 codes LANG_CODES)
- Chargement : `MainWindow._load_saved_lang()` au démarrage, `_apply_language()` appelé à la fin de `_build_main_ui()`
- `blockSignals(True/False)` dans `settings_widget._apply_to_widgets()` pour éviter la boucle combo → _apply_language → combo

**Pattern `retranslate_ui(lang)` sur les widgets de page :**
```python
def retranslate_ui(self, lang: str):
    from app.i18n import tr
    if hasattr(self, "_header"):
        self._header.set_title(tr("section.foo", lang))
    # QTabWidget :
    for i, key in enumerate(["foo.tab.a", "foo.tab.b"]):
        if i < self._tabs.count():
            self._tabs.setTabText(i, tr(key, lang))
```

Widgets implémentant `retranslate_ui` : `VehiclesWidget`, `ClientsWidget`, `DepotsWidget`, `OrdersWidget`, `DriversWidget`, `CarriersWidget`, `SettingsWidget`, `OptimizationWidget`, `TrackingWidget`, `MapWidget`, `NotificationsWidget`, `ReportsWidget`, `LogsWidget`.

`NavButton.set_label(text)` — méthode ajoutée à la classe sidebar pour permettre la mise à jour dynamique des libellés.

### Intégration TopBar (main_window.py)
- `self._page_stack_host` (`#pageStackHost`) — `QVBoxLayout` marges **20, 8, 20, 20** autour du `QStackedWidget` pour aérer le contenu des pages (évite l’effet « collé » bord droit / bas)
- Menu latéral : `QScrollArea` nav — barre verticale **ScrollBarAsNeeded** si la liste dépasse la hauteur
- `self._topbar = TopBar(main_window=self)` — instancié dans `_build_main_ui()`
- `self._topbar.refresh_breadcrumb(name)` — appelé dans `_nav_to()` à chaque navigation
- `self._topbar.bell.refresh_from_db()` — appelé par `QTimer` toutes les 30s
- Fade-in page : `QGraphicsOpacityEffect` 0→1 en 150ms sur `self.stack`
- **Navigation (v5.29)** : `NAV_ITEMS` — icônes Lucide par page (`shopping-bag` Commandes, `briefcase` Transporteurs, `file-clock` Journal, etc.) ; sidebar/topbar/menu : tons `#162840` / `#243F58` / `text2` `#7FA8C0` (alignés prototype TourVP) ; accent applicatif reste `#00D4FF` ; `_accent_highlight_rgba()` pour fond item actif

### Copilot (`copilot_widget.py`)
- **Chat** : `MistralWorker` avec `db_stats` agrégés depuis la BDD (UI) ; 6 chips suggestions ; bandeau *Exécuter / Ignorer* si `parse_command` détecte une action
- **Analyse globale** : onglet avec `QPlainTextEdit`, génération longue + export PDF (`reportlab`)
- **Persistance** : table `ai_conversations` (`messages_json` par `user_id`)
- **Langues** : FR / EN / AR / ES / DE (`LANG_MAP`)

---

## Tables SQLite clés

### Tables de base (init_database)

| Table | Rôle | Champs notables |
|-------|------|-----------------|
| `users` | Authentification | `role`, `password_hash`, `salt`, `is_active`, `permissions` (JSON) |
| `clients` | Points de livraison | `archived`, `demand_kg`, `ready_time`, `due_time`, `priority`, `client_type` |
| `vehicles` | Flotte | `status` (disponible/en service/maintenance), `depot_id`, `capacity_kg` |
| `depots` | Centres de distribution | `latitude`, `longitude`, `opening_time`, `closing_time` |
| `scenarios` | Configs d'optimisation sauvegardées | `data_json`, `config_json`, `results_json` |
| `tournees` | Tournées (legacy) | `algorithm`, `total_distance_km`, `respect_rate`, `route_json` |
| `arrets` | Arrêts sur tournées (legacy) | `tournee_id`, `visit_order`, `arrival_time`, `delay_min` |
| `algo_results` | Historique des runs | `algorithm`, `total_distance`, `respect_rate`, `distance_source` |
| `translation_history` | Traductions loggées | `source_lang`, `target_lang`, `quality_score` |
| `logs` | Audit trail complet | `action`, `details`, `user_id`, `created_at` |
| `notifications` | Notifications in-app | `type`, `title` (NOT NULL), `message`, `is_read` + migration 016 : `severity`, `related_table`, `related_id`, `user_id`, `action_url` |
| `anomalies` | Anomalies statistiques | `anomaly_type`, `severity`, `tournee_id` |
| `user_sessions` | Dernière page active | `user_id`, `last_page_index` |

### Tables ajoutées par migrations

| Table | Migration | Rôle |
|-------|-----------|------|
| `distance_cache` | 001 | Cache OSRM — clé SHA256 → `dist_json`, `time_json` |
| `translation_glossary` | 002 | Corrections utilisateur — `use_count`, prioritaire sur l'API |
| `drivers` | 009 | Chauffeurs — contrat, horaires légaux, qualifications, dépôt |
| `driver_unavailabilities` | 010 | Absences et indisponibilités chauffeurs |
| `teams` / `team_members` | 011 | Équipes de chauffeurs |
| `orders` | 012 | Commandes de livraison/collecte — `reference`, `status`, `adr_class` |
| `routes` | 013 | Tournées planifiées enrichies — `co2_kg`, `is_locked`, `driver_id` |
| `route_stops` | 014 | Arrêts individuels sur routes — `stop_order`, `actual_arrival`, `status` |
| `carriers` / `carrier_shipments` | 015 | Transporteurs externes et expéditions |
| `zones` | 017 | Zones GeoJSON (ZFE, livraison, exclusion) |
| `reports_history` | 019 | Historique des rapports générés |
| `ai_conversations` | 020 | Historique conversations Copilote Mistral |
| `recurring_order_templates` | 021 | Gabarits de commandes récurrentes |

### Colonnes étendues (migrations 003–008)

| Table | Colonnes ajoutées (exemples) |
|-------|------------------------------|
| `algo_results` | `distance_source`, `co2_total`, `vrp_mode`, `scenario_name` |
| `clients` | `company_name`, `tags`, `adr_class`, `time_window2_start/end`, `is_recurring` |
| `vehicles` | `insurance_expiry`, `technical_inspection_expiry`, `co2_per_km`, `allowed_adr`, `allowed_zfe`, vitesses par type de route |
| `depots` | `manager_name`, `loading_bays`, `is_cross_dock`, `open_time`, `close_time` |
| `users` | `phone`, `permissions` (JSON), `is_active`, `website_user_id` |
| `notifications` | `severity`, `related_table`, `related_id`, `user_id`, `action_url` |

---

## Correctifs v5.41

### 🔴 Bugs corrigés
- **`optimization_widget.py` `_save_as_scenario`** : INSERT dans `scenarios` n'incluait pas `client_count`, `vehicle_count`, `algorithm` → scénarios sauvegardés depuis l'optimisation affichaient 0/0/— dans le tableau. Corrigé.
- **`optimization_widget.py` intégration chauffeurs** : `_get_data` joint désormais chaque véhicule à son chauffeur (`driver_id → drivers`) et vérifie `driver_unavailabilities` pour la date planifiée. Véhicules dont le chauffeur est indisponible exclus automatiquement (log ⚠). Chauffeur injecté comme `_driver` dans le dict véhicule → utilisé par OR-Tools (pauses RSE par véhicule) et `_run_compliance` (violations préfixées immat./chauffeur). Nom du chauffeur affiché dans l'arbre "Détail véhicules" ; orange si aucun chauffeur assigné.
- **`greedy.py` + `two_opt.py`** : stops dict manquaient `"type": "delivery"` → cascadait vers 5 bugs (Détail véhicules vide, CSV vide, conformité statique, CO2 erroné, slider carburant sans effet). Corrigé.
- **`optimization_widget.py` simulation coûts** : proxy dict unique pour tous les véhicules ; `"fuel_consumption_l100km"` absent → `fuel_price` ignoré par `calculate_route_cost`. Corrigé : itération par route avec véhicule réel + valeur fallback 12.0.
- **`optimization_widget.py` CO2 tableau** : `calculate_co2(total_km, {})` avec véhicule vide → remplacé par somme par route avec véhicule réel.
- **`optimization_widget.py` conformité** : violations tronquées à 3 + QLabel non scrollable → `QTextEdit` (read-only, 90–220px) dans `QScrollArea`, toutes violations affichées.
- **`optimization_widget.py` verrouillage route** : stub `show_toast`. Remplacé par implémentation SQL complète (`routes.is_locked=1` + `route_stops` avec `client_id`, `order_id`, timings HH:MM).
- **`vehicles_widget.py`** : ajout champ `fuel_consumption_l100km` (QDoubleSpinBox + bouton ⟳ Estimer, `_CONSO_TABLE` ~20 entrées type×motorisation).
- **`drivers_widget.py` `StatusBadge`** : arguments inversés — `StatusBadge(st, var)` → `StatusBadge(var, st)` ; badge affichait la variant string ("success") au lieu du libellé ("Actif").
- **`drivers_widget.py` qualifications** : affichage brut JSON `["MATIÈRES_DANGEREUSES"]` → parsing JSON + mapping vers codes widget (`POIDS_LOURD→Permis_poids_lourd`, `MATIÈRES_DANGEREUSES→ADR`, `FRIGO→HAZMAT`) avant affichage dans la table.
- **`drivers_widget.py` `_show_credentials_dialog`** : `from ..components` → `from .components` (remontait à `app.components` inexistant → erreur critique au clic "Compte web").
- **`citypulse-web/apps/api/views.py` `sync_clients`** : `payload.get()` plantait si payload était une liste JSON (AttributeError 500) → vérification `isinstance(payload, list)` avant.
- **`optimization_service.py` `save_plan` assignation commandes** : la requête per-stop ne cherchait que `scheduled_date=planned_date OR NULL`, laissant 146/159 `route_stops` sans `order_id`. Corrigé : (1) la requête per-stop cherche désormais TOUTE commande pending pour le client, triée par priorité de date (date exacte > NULL > autre) ; (2) second pass après insertion des route_stops : pour chaque client routé, assigne toutes ses commandes pending restantes avec `scheduled_date=planned_date OR NULL`. Résultat : 83/132 clients ont une commande assignée (vs 13 avant).

### 🟢 Nouvelles fonctionnalités
- **`optimization_service.py` priorité commandes** : `run_optimization()` trie désormais les clients par `priority` avant dispatch (`priority 1` = urgent = servi en premier).
- **`optimization_service.py` `save_plan(result, planned_date)`** : persistance complète du plan optimisé — INSERT `routes` + `route_stops`, UPDATE `orders.status='assigned'`, INSERT `vehicle_unavailabilities` (bloque le calendrier véhicule), INSERT `notifications`. Colonnes ajoutées idempotent via ALTER TABLE.
- **`optimization_widget.py` bouton "✅ Confirmer le plan"** : apparu dans la barre post-run ; confirme le meilleur algorithme via `save_plan()` après `QMessageBox.question` ; bouton désactivé après confirmation.
- **`optimization_widget.py` planificateur hebdomadaire** : bouton "Planifier la semaine" (bas du panneau gauche) → `_WeeklyPlannerDialog` + `_WeekPlanThread`. Deux modes : (1) distribuer automatiquement toutes les commandes `pending` par priorité décroissante sur N jours, (2) respecter `scheduled_date` par commande. Filtre `driver_unavailabilities` par jour, marque les commandes assignées (`status='assigned'`), résumé final dans QMessageBox. Validation appelle `save_plan()` par jour.
- **Intégration web complète** : `save_plan()` appelle `_sync_plan_to_web()` après confirmation — push `sync_routes()` vers portail chauffeur + `push_delivery_tracking()` vers portail client (statut + ETA + nom chauffeur). `TrackingWidget._sync_timer` (60s) appelle `_pull_web_confirmations()` → met à jour `orders.status` dans le desktop depuis les confirmations chauffeur web. Clé secrète Django stockée dans keyring (`citypulse_django` / `django_api_secret`). `django_sync_service.push_delivery_tracking(orders)` → `POST api/deliveries/confirm/` pour chaque commande.

### 🟡 UX
- **`scenarios_widget.py`** : redesign complet — QSplitter table/détail, Tags+Description dans panneau droit (plus au bas de page), profil trafic CSV déplacé en bas, bouton "Ouvrir" renommé "Restaurer" (orange, tooltip explicatif), comparaison étendue (coût + ponctualité + bar_label).
- **`help_dialog.py` "scenarios"** : aide réécrite — distingue snapshot données vs sauvegarde depuis optimisation, décrit accuratement les colonnes du tableau et le bouton "Restaurer".

---

## Correctifs v5.40 (audit complet)

### 🔴 Bugs cassés corrigés
- **`dashboard_widget.py`** : `_table_to_nav` remappé (`clients=1, vehicles=2, drivers=3, depots=4, orders=5, carriers=6, routes=9, scenarios=10, logs=13, algo_results=7`) ; "Voir suivi →" `→ _nav_to(9)` ; "Optimiser →" `→ _nav_to(7)` ; anomalie "Voir →" `→ _nav_to(5)` ; logs "Journal" `→ _nav_to(13)`.
- **`main_window.py`** : Ctrl+N corrigé `→ _nav_to(7)` ; doublon `_show_about` supprimé ; connexion des signaux `tracking_w.route_updated`, `tracking_w.center_on_vehicle`, `map_w.marker_clicked` (étaient connectés mais handlers absents).
- **`vehicles_widget.py`** : `_CalendarDialog._load_month` — SQL paramétré corrigé (fragment littéral dans la requête faisait ignorer le filtre mensuel).
- **`clients_widget.py` / `depots_widget.py`** : `_GeocoderThread` — paramètre Nominatim `"LIMIT ? "` (clé invalide) `→ "limit": 1`.
- **`optimization_widget.py`** : `_load_forced_sequences` lit réellement `route_stops JOIN routes WHERE is_locked=1` ; `OptimizationThread.run()` émet `partial_result` avant `finished`.
- **`tracking_widget.py`** : `_reoptimize()` copie profonde de `_last_result`, filtre les stops `cancelled=True`, réémet le résultat nettoyé + `log_action`.
- **`map_widget.py`** : `address_found` signal connecté dans `_load_map()` ; `_geocode_address()` rendu asynchrone via `_GeocoderThread(QThread)`.
- **`logs_widget.py`** : réécrit — filtre dates (30 derniers jours par défaut), résolution username via `LEFT JOIN users`, export CSV, `retranslate_ui`.
- **`settings_widget.py`** : `retranslate_ui()` complété pour les onglets Utilisateurs et Sauvegarde.
- **`copilot_widget.py`** : `MistralWorker.run()` — `except` émet `error_occurred` au lieu de renvoyer le fallback comme réponse normale.
- **`translation_widget.py`** : toast avertissement quand `method == "hors-ligne"` ; colonne `method` sauvegardée en base ; `_ensure_validated_col()` / `_ensure_method_col()` ; bouton Valider → glossaire auto + `✓` dans historique ; checkbox "Validées uniquement".

### 🟠 Incomplets complétés
- **`reports_widget.py`** : sélection algo runs via `QListWidget` (libellés lisibles) au lieu de champ texte ID brut ; aperçu + bouton télécharger pour XLSX/JSON ; persistance planification dans `settings.json["reports"]["schedule"]`.
- **`translation_widget.py`** : colonne Méthode alimentée (🌐 API / 🤖 Mistral / 📖 Hors-ligne).

### 🟡 Cosmétiques — `retranslate_ui` ajouté
- `OptimizationWidget` : 5 onglets traduits (fr/en/ar/es/de)
- `TrackingWidget` : 2 onglets Gantt/Tableau traduits
- `MapWidget`, `NotificationsWidget`, `ReportsWidget` : stubs `pass`

---

## Points de vigilance

- **WebEngine (v5.20+)** : `Qt.AA_ShareOpenGLContexts` doit être activé via `QCoreApplication.setAttribute(..., True)` **avant** la création de `QApplication` / `QGuiApplication` / `QCoreApplication`, et avant tout import de `PyQt6.QtWebEngineWidgets` si une instance Qt existe déjà. Point d’entrée : `main.py` ; tests : `pytest_configure` dans `tests/conftest.py`.
- **Leaflet dans `setHtml` (dépôts v5.26+)** : comme `map_widget._load_map`, les vues `QWebEngineView` de `depots_widget.py` activent `LocalContentCanAccessRemoteUrls`, passent `QUrl("qrc:///")` à `setHtml`, exposent `window.__citypulseMap` pour `invalidateSize()` au `loadFinished` et au passage sur l’onglet **Carte** (évite tuiles grises si la carte s’initialise avec une taille nulle).
- **`_minimap_html` rayon > 0 (v5.27)** : le fragment `L.circle(...,{...})` ne doit pas se terminer par `}}` dans une sous-chaîne **non** f-string — cela injectait du JavaScript invalide (carte blanche dès que le rayon de couverture ≠ 0).
- **Ne pas bloquer le thread Qt** : toute opération longue → QThread
- **`ORTOOLS_AVAILABLE`** : vérifier avant d'utiliser OR-Tools (dépendance lourde optionnelle)
- **`HAS_MPL` / `HAS_WEB` / `HAS_PDF_VIEW`** : vérifier avant Matplotlib / QWebEngineView / QPdfView. `HAS_PDF_VIEW` = `True` si `PyQt6.QtPdf` + `PyQt6.QtPdfWidgets` importables (PyQt6 6.5+). Préférer `QPdfView` pour les PDF (natif Qt, indépendant du plugin Chromium PDF) ; fallback `QWebEngineView.setUrl(QUrl.fromLocalFile(...))` si `HAS_PDF_VIEW=False`.
- **`MapWidget._load_map`** : centre, zoom et fond de carte viennent uniquement de `settings.json` (`map.default_lat`, `map.default_lon`, `map.default_zoom`, `map.default_layer`). Aucune colonne SQLite `default_lat` / `default_lon` — ne pas exécuter de `SELECT` pour ces valeurs.
- **`PyQt6-WebEngine`** : doit être installé pour **le même interpréteur** que `python main.py` (`python -m pip install PyQt6-WebEngine`). Si pip indique « déjà satisfait » mais la carte reste désactivée, comparer `sys.executable` avec celui du log d’échec dans `citypulse.log` (environnement conda/autre, ou DLL / VC++ / `QtWebEngineProcess` manquant sous Windows).
- **Cache OSRM** : `distance.py` gère 3 niveaux automatiquement — ne pas court-circuiter
- **`archived=0`** : filtre obligatoire sur la table `clients`
- **`log_action()`** : obligatoire après toute mutation BDD
- **Clés API** : toujours via `keyring`, jamais en clair
- **Colonnes étendues clients** : `company_name`, `tags`, `access_code`, `notes`, `preferred_driver_id`, `punctuality_factor`, `delay_penalty_per_hour`, `vehicle_requirement`, `adr_class`, `time_window2_start/end` — mises à jour avec `UPDATE … SET col=? WHERE id=?` isolé dans `try/except` (silencieux si colonne absente en vieux schéma)
- **Nominatim rate limit** : 1 requête/seconde obligatoire — `time.sleep(1.1)` dans `_ImportThread`
- **`_priority_stars`** : priorité 1 = 5 étoiles (urgence haute), priorité 5 = 1 étoile (basse)
- **`get_expiring_documents`** : `_ExpireBanner.refresh()` → **30** j ; agrégat **colonne Docs** (`VehiclesWidget.refresh_data`) → **365** j — retourne list[dict] `vehicle_id`, `registration`, `doc_type`, `expiry_date`, `days_left` ; ne pas confondre les deux seuils.
- **`vehicles.status` (KPI / filtre / stats)** : normaliser via `_normalize_vehicle_status_bucket()` dans `vehicles_widget.py` — la BDD peut stocker `en_service` ou `en service` (espace), etc. ; barre KPI, dialogue stats flotte et filtre « en_service » doivent compter les mêmes variantes que le tableau (`_STATUS_LABEL`).
- **`_VehicleDialog` onglet Dispo & Stats** : contenu dans `QScrollArea` (`widgetResizable`), `QGroupBox` avec marges/titre QSS renforcés, planning hebdo en `QGridLayout` (2 lignes) pour éviter titres tronqués ou chevauchés.
- **`vehicle_unavailabilities`** : table créée à la volée par `_CalendarDialog` — ne pas la créer dans `init_database()` ou les migrations pour éviter les doublons
- **`_ensure_column()`** : helper local dans `vehicles_widget.py` pour `ALTER TABLE ADD COLUMN` idempotent
- **`notifications.title`** : colonne `NOT NULL` — tout INSERT doit inclure `title` (ex. type de l'incident)
- **`sqlite3.Row.get()`** : n'existe pas — utiliser `row["col"] if "col" in row.keys() else default`
- **`KPICard`** : constructeur `(title, value, unit="", icon="📊", trend="", trend_up=True)` — pas de paramètre `variant` ni `color=` (styling : `icon`, `unit`, ou QSS sur le parent)
- **Véhicules / FK** : `depot_id` nullable — ne pas utiliser `depot_id or 1` ; valider `depot_id` et `driver_id` contre la BDD avant commit ; en cas d’échec, capturer `sqlite3.IntegrityError` et afficher un message lisible
- **`_VehicleDialog` combo chauffeur** : requête directe sur colonnes standard `first_name`, `last_name`, `license_number` avec `COALESCE` ; filtre `COALESCE(archived,0)=0` (inclut le chauffeur courant même si archivé) ; tout échec logué via `logger.exception()` — **ne pas** utiliser `except Exception: pass` ni détection PRAGMA (anti-pattern silencieux).
- **`_DriverDialog` onglet Affectation combo véhicule** : requête sans filtre `WHERE status=’disponible’` (excluait tous les non-disponibles) ; inclut tous les véhicules, triés disponibles en premier ; libellé = `immatriculation (statut en français)` pour les non-disponibles.
- **`SearchBar`** : le texte saisi est dans **`_edit`** (pas `_input`). Lire avec **`get_text()`** ou **`text()`** — ne jamais utiliser `search_bar._input` (attribut absent → filtre SQL toujours vide).
- **`PaginationBar`** : constructeur `(page_size=20)` — paramètre `limit` n'existe pas
- **`GanttWidget`** : nécessite `setFocusPolicy(StrongFocus)` pour que Ctrl+Z fonctionne; `_gantt_vehicles` doit être initialisé à `[]` dans `__init__` avant `_setup_ui()`
- **QSS `border-radius` multi-valeurs** : le parseur QSS Qt ne supporte qu'un seul `Radius` pour le raccourci `border-radius`. Pour les coins partiellement arrondis (ex. onglets, champ de recherche), utiliser les propriétés individuelles : `border-top-left-radius`, `border-top-right-radius`, `border-bottom-left-radius`, `border-bottom-right-radius`. Ne jamais écrire `border-radius:6px 6px 0 0` dans un `setStyleSheet()` Qt.
- **`QSpinBox.setValue`** : n'accepte que des `int` — les valeurs SQLite/JSON souvent `float` doivent être arrondies et bornées (`int(round(float(v)))` puis clamp au `min`/`max` du widget) ; `QDoubleSpinBox` uniquement pour les champs décimaux (`_ClientDialog._spin(..., dec>0)`).
- **`ConfirmDialog` / QSS global** : `styles.py` définit les états complets des boutons nommés + `QMessageBox QPushButton` + `QDialog QDialogButtonBox QPushButton`. `confirm_dialog._dialog_qss()` (alias `dialog_base_qss()`) duplique ces règles (y compris `#ghostBtn`, `#iconBtn`, `QDialogButtonBox`) sur les `QDialog` qui appliquent une feuille locale — à fusionner systématiquement sur les boîtes de dialogue avec actions nommées. **Dialogs fond clair** : `light_dialog_buttons_qss()`. Un QSS invalide plus bas dans la feuille peut empêcher le parseur d'appliquer les règles suivantes — ne pas utiliser `border-radius` avec plusieurs longueurs dans une seule propriété Qt. Même recours sur l’onglet **Équipes** (`drivers_widget._build_tab_teams`) : `setStyleSheet(_dialog_qss())` sur le `QWidget` racine de l’onglet.
- **`TrackingWidget` timers** : `_live_timer` et `_sim_timer` sont arrêtés dans `hideEvent` et `_live_timer` est relancé dans `showEvent`. Ne pas retirer ces handlers — ils évitent le `KeyboardInterrupt` CRITICAL lors de la fermeture de l'app.

---

## vehicles_widget.py — Architecture v2.0

### Layout principal (`VehiclesWidget`)
| Zone | Composant | Rôle |
|------|-----------|------|
| Bannière alertes | `_ExpireBanner` | Rouge/orange : assurance/CT expirant dans ≤30 j |
| En-tête | `SectionHeader` | Titre + bouton "+ Ajouter véhicule" |
| Toolbar | `SearchBar` + filtres | Recherche texte + filtre statut |
| Table | `QTableWidget` 9 col. | Immat., Marque, Type, Chauffeur, Cap.kg, CO2, Statut, Docs, Actions |
| KPI bar | 4 compteurs inline | Total / Disponibles / En service / Maintenance — comptages via `_normalize_vehicle_status_bucket()` (alignés sur le tableau) |
| Calendrier | `_CalendarDialog` | Grille mensuelle, clic → toggle indisponibilité (table `vehicle_unavailabilities`) |
| Stats flotte | `_FleetStatsDialog` | KPICards + camembert Matplotlib par statut |

### StatusBadge statuts
- **disponible** → `#00FF88` (success)
- **en_service** / **en tournée** → `#00D4FF` (accent)
- **maintenance** → `#FFB800` (warning)
- **hors_service** → `#FF4757` (danger)

### Colonne Docs
- `✓` vert : aucune alerte dans la fenêtre **365** j (`get_expiring_documents(365)` — échéance au-delà ou pas de date / hors critère)
- `⚠` orange : assurance ou CT avec échéance **dans les 365 j** et **non expirée** (le bandeau du haut de page reste à **30** j)
- `✗` rouge : document expiré (`days_left` négatif)

### Fiche `_VehicleDialog` (7 onglets)
| Onglet | Champs clés |
|--------|-------------|
| Identité | registration*, brand, model, year, type, fuel_type, photo (browse + aperçu 120×120), persistance `vehicles.photo_url` → copie sous `data/photos/vehicle_{id}_*` (.png/.jpg/.jpeg/.webp/.bmp) ; URL http inchangée |
| Capacités | capacity_kg, capacity_m3, palettes, H/L/Lo cm, co2_per_km, ADR, ZFE |
| Vitesses | speed_highway, speed_national, speed_urban, speed_zone30 (QSpinBox km/h) |
| Coûts | cost_per_km, cost_per_hour, cost_fixed_daily, cost_non_utilisation |
| Chauffeur | QComboBox cherchable drivers + open_start/open_stop/reload_allowed ; chargement depuis `drivers` actifs (`archived=0`) avec fallback ancien schéma (sans `archived`) ; libellé = `first_name last_name (license_number)` |
| Documents | insurance_expiry, technical_inspection_expiry + alertes inline, insurance_number |
| Dispo & Stats | `QScrollArea` + depot_id QComboBox, planning hebdo 7 cases (`QGridLayout`, JSON `weekly_schedule`), stats km/tours/coût |

### Colonnes étendues ajoutées dynamiquement
`brand`, `palettes`, `cost_non_utilisation`, `weekly_schedule`, `driver_id` — ajoutées via `_ensure_column()` si absentes.  
**Photo :** colonne SQLite `photo_url` (migration 005) ; valeur stockée = chemin relatif `data/photos/...` ou URL.

### Table `vehicle_unavailabilities`
Créée à la volée dans `_CalendarDialog._ensure_table()` :
```sql
vehicle_unavailabilities(id, vehicle_id, date TEXT, reason TEXT, UNIQUE(vehicle_id,date))
```

---

## clients_widget.py — Architecture v2.0

### Layout principal (`ClientsWidget`)
| Zone | Composant | Rôle |
|------|-----------|------|
| En-tête | `SectionHeader` | Titre + bouton "+ Ajouter" |
| Recherche | `SearchBar` (300ms debounce) | Filtre nom, entreprise, tél, tags |
| Filtres | `CollapsibleSection` (collapsed=True) | Type multi-select, priorité slider, tag texte |
| Table | `QTableWidget` 100/page | ID, Nom, Entreprise, Tél, Demande kg, Créneaux, Priorité★, Tags, Statut, Actions |
| Pagination | `PaginationBar` | SQL LIMIT/OFFSET — signal `page_changed(page, offset, limit)` |
| Overlay | `LoadingOverlay` | Import + détection anomalies |

### Colonnes table
- **Priorité★** : `★★★☆☆` (priorité 1 = 5 étoiles, priorité 5 = 1 étoile)
- **Statut** : `client_type` coloré par `_TYPE_COLORS` dict
- **Actions** : ✏ éditer, 🗺 carte, 🗑 archiver (cellWidget QWidget)

### Dialogue `_ClientDialog` (5 onglets)
| Onglet | Champs clés |
|--------|-------------|
| Général | nom*, company_name, client_type, statut, tags (chips `_TagsInput`) |
| Adresse | address, lat/lon, `_GeocoderThread` (Nominatim), minimap Leaflet 300×200 (`HAS_WEB`) |
| Livraison | demand_kg, demand_m3, service_time, créneaux 1+2 (HH:MM), ADR, vehicle_requirement, ponctualité slider, pénalité €/h |
| Contact | contact, phone, email, notes, preferred_driver_id (QComboBox drivers) |
| Historique | 10 derniers orders (`orders WHERE client_id=?`) |

### Import CSV/Excel (`_ImportMappingDialog` + `_ImportThread`)
1. `QFileDialog` → `_ImportMappingDialog` (preview 5 lignes + mapping colonnes via `_ALIASES`)
2. **QSS** : feuille = `confirm_dialog._dialog_qss()` + styles table/combos (bouton **Importer** `#primaryBtn` lisible si QSS global cassé) ; validation **Importer** : aperçu 5 lignes, champs numériques (`_IMPORT_NUMERIC_FIELDS`) → `QMessageBox` si texte non convertible
3. **Parsing sûr** : `_import_parse_float` / `_import_coerce_int` pour lat/lon, `demand_kg`, `demand_m3`, créneaux, `service_time`, `priorité` — valeur par défaut + message par ligne dans `error_list` si cellule non numérique (plus de crash `float('alimentaire,supermarche')`) ; **INSERT/UPDATE** inclut `demand_m3`
4. **Alias** : pas de `x`/`y` seuls pour lon/lat (ambigüité) ; `demand_m3` ↔ `volume_m3`, `m3`, …
5. Option géocodage (Nominatim, 1 req/s)
6. `_ImportThread(QThread)` : lecture → matching colonnes → INSERT/UPDATE → signal `finished(dict)`
7. `_ImportReportDialog` : résumé X créés / Y mis à jour / Z erreurs (+ avertissements parsing)

### Threads Qt
| Thread | Signal émis | Usage |
|--------|-------------|-------|
| `_GeocoderThread` | `result(lat, lon, name)`, `error(str)` | Géocodage unitaire (onglet Adresse) |
| `_ImportThread` | `progress(msg, cur, tot)`, `finished(dict)` | Import CSV/Excel en lot |
| `_AnomalyThread` | `finished(list)` | Z-score sur demand_kg, service_time, coords, créneaux |

### Vue Carte (`_MapDialog`)
- `QDialog` 820×620 avec `QWebEngineView` (fallback texte si `HAS_WEB=False`)
- Leaflet + marqueurs colorés par `client_type` + `fitBounds`
- Légende types en bas + bouton Fermer

### Export
- CSV : `open(path, "w")` + `csv.writer`
- Excel : `openpyxl` (requiert `HAS_OPENPYXL`)
- JSON : `json.dump(list[dict(row)])`

---

## Commandes utiles

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python main.py

# Lancer les tests
pytest tests/ -v

# Lancer un test spécifique
pytest tests/unit/test_greedy.py -v

# Vérifier OR-Tools
python -c "from ortools.constraint_solver import routing_enums_pb2; print('OK')"

# Générer données de démo (CLI autonome — sans Qt)
python scripts/generate_demo_data.py --dataset casablanca --db citypulse.db --reset
python scripts/generate_demo_data.py --dataset paris      --db citypulse.db --append
python scripts/generate_demo_data.py --dataset benchmark  --db citypulse.db
python scripts/generate_demo_data.py --dataset all        --export ./demo_data/ --reset
```

---

## Génération de données de démo

### Script CLI (`scripts/generate_demo_data.py`)

Script autonome sans Qt. Appelle `init_database()` + `run_migrations()` automatiquement.

| Dataset | Contenu |
|---------|---------|
| `casablanca` | 3 dépôts · 8 véhicules · 8 chauffeurs · 2 équipes · 80 clients · 200 commandes · routes 30j · 5 zones GeoJSON · 20 notifs · 3 scénarios · 150 logs · 2 conversations IA |
| `paris` | 2 dépôts · 5 véhicules · 50 clients · 80 commandes |
| `benchmark` | 1 dépôt · 20 véhicules · 500 clients · sans créneaux/ADR |
| `all` | Casablanca + Paris + Benchmark |

Options CLI : `--db <path>`, `--reset` (vide les tables), `--append` (conserve l'existant), `--export <dir>` (CSV + Excel).

### DemoLoaderDialog (`app/ui/demo_loader.py`)

- `DemoLoaderDialog(QDialog)` : sélection dataset + options reset/export + QProgressBar + log temps réel
- Thread dédié : `_GeneratorThread(QThread)` → signaux `progress_signal`, `finished_signal`
- Point d'entrée : `show_demo_loader(main_window)`
- Accessible depuis : menu **Fichier → Charger données de démo** (Ctrl+D), EmptyState dashboard, page Paramètres

### Menu Fichier (main_window.py)

Menu bar QMenuBar avec :
- **Fichier** : Charger données démo (Ctrl+D), Exporter rapport PDF, Quitter (Ctrl+Q)
- **Outils** : Chauffeurs (3), Commandes (5), Transporteurs (6), Optimisation (7), Carte (8), Scénarios (10), Traduction (11), Journaux (13), Paramètres (14)
- **Aide** : Guide utilisateur (F1), À propos v5.8

---

## drivers_widget.py — Architecture v1.0

### Structure globale
`DriversWidget(QWidget)` contient un `QTabWidget` 4 onglets. Navigation inter-onglets via `_on_tab_changed(idx)`.

### Onglet 0 — 👤 Chauffeurs
- `_ExpireLicenseBanner` : alerte rouge/orange pour chaque permis expirant dans ≤ 30j
- `SectionHeader` + `SearchBar` (filtre nom / permis / zone)
- `QTableWidget` 9 colonnes : Photo (QPixmap 36×36 rond) | Nom | Permis/Cat. | Qualifs | Véhicule | Équipe | Statut (`StatusBadge`) | Exp. | Actions (✏📅🗑)
- Double-clic → `_DriverDialog` | Clic droit → menu contextuel | bouton 📅 → switch vers onglet Indispos

### `_DriverDialog` (5 onglets)
| Onglet | Contenu |
|--------|---------|
| Personnel | photo (browse, extensions .png/.jpg/.jpeg/.webp/.bmp) → `data/photos/driver_{id}_*` ; chargement via `photo_path` **ou** `photo_url` ; INSERT/UPDATE persistants ; tableau : `resolve_stored_photo()` |
| Permis & Qualifs | n° permis, catégorie (B/C/C1/CE/D/D1/DE), date expiration + alerte live, checkboxes ADR/CACES/FCO/FIMO/HAZMAT/Permis_poids_lourd, type contrat (CDI/CDD/…) |
| Horaires | plage travail (HH:MM→HH:MM), pause déjeuner (heure+durée), max heures/jour, heures supp niveau 1 (durée+taux), niveau 2 (durée+taux) |
| RSE | max conduite avant pause (min), pause minimum (min), repos journalier minimum (min), note légale CE 561/2006 |
| Affectation | dépôt (QComboBox), véhicule (QComboBox cherchable) filtré sur statuts **disponibles** (normalisation casse/espaces), conserve le véhicule déjà assigné même indisponible, option "— Non assigné", zone, open_start/open_stop (QCheckBox), stats (tournées, km total, retard moyen) |

### Onglet 1 — 📅 Indisponibilités
- `QComboBox` sélection chauffeur
- `_CalendarGrid(QWidget)` : grille 6×7 mensuelle, navigation mois ◀/▶, cellules colorées (rouge = indisponible, orange = route planifiée)
- Clic sur une cellule → `_UnavailDialog` : date, raison, notes + bouton "Supprimer" si existant (retourne code 2)
- Après création d'indisponibilité sur date avec route planifiée → `_suggest_replacement()` : liste les chauffeurs disponibles ce jour

### Onglet 2 — 👥 Équipes
- Gauche : `QListWidget` des équipes + bouton « + Nouvelle équipe » (`#primaryBtn`) + suppression
- Droite : nom équipe + `QComboBox` manager (✓ sauvegarder) + deux `QListWidget` (membres / tous chauffeurs) + boutons « Ajouter → » / « ← Retirer » (`#primaryBtn` / `#secondaryBtn`) ; racine onglet : `setStyleSheet(_dialog_qss())` pour contraste boutons si QSS global dégradé
- CRUD complet sur tables `teams` et `team_members`

### Onglet 3 — 📊 Performance
- Filtres : chauffeur (QComboBox) + période (QDateEdit De/À) + bouton Actualiser + bouton 📤 CSV
- `QTableWidget` 7 colonnes : Chauffeur | Tournées | Km total | Km moy/tour | Retard moy | Taux ponctualité (coloré) | Dernière tournée
- Graphique barres Matplotlib (Km total par chauffeur, fond sombre)
- Export CSV via `csv.DictWriter`

### Colonnes étendues drivers (ajoutées via `_ensure_driver_cols`)
`open_start INTEGER DEFAULT 0`, `open_stop INTEGER DEFAULT 0`, `photo_path TEXT` — synchronisée avec `photo_url` (schéma migration 009) à l’enregistrement.

### Module `app/utils/photo_storage.py`
`is_allowed_image_filename`, `resolve_stored_photo`, `save_user_photo`, `finalize_stored_path` — dossier `data/photos/` créé via `project_root()` (PyInstaller : à côté de l’exe).

---

## depots_widget.py — Architecture v2.0

### Layout
- `SectionHeader` + bouton "+ Ajouter dépôt"
- `SearchBar` (filtre sur nom / adresse / responsable) + bouton "Vue Carte globale"
- `QTableWidget` 8 colonnes : Nom | Adresse | Responsable | Horaires | Quais | Capacité | Rayon km | Actions (✏🗺🗑)
- `EmptyState` si aucun dépôt
- Double-clic → édition | Clic droit → menu contextuel

### `_DepotDialog` (3 onglets)
| Onglet | Contenu |
|--------|---------|
| Infos | nom*, adresse, responsable, tél, lat/lon + 🔍 Géocoder (`_GeocoderThread`), horaires, quais, capacité, notes |
| Carte | Rayon couverture (km) + minimap Leaflet (`QWebEngineView`, min. hauteur 300px) — `setHtml(..., qrc)` + accès URL distantes ; `invalidateSize` à l’affichage onglet / fin de chargement |
| Stats | Véhicules attachés, clients actifs, tournées optimisées |

### `_GlobalMapDialog`
- `QDialog` 820×620 avec `QWebEngineView` (fallback texte si `HAS_WEB=False`) — même config WebEngine + base `qrc` que la minimap
- Leaflet : marqueurs couleur par dépôt + cercle rayon couverture + `fitBounds`
- Légende dépôts + bouton Fermer

### Colonnes étendues (ajoutées via `_ensure_column`)
`manager_name TEXT`, `phone TEXT`, `coverage_radius_km REAL DEFAULT 20`,
`open_time TEXT DEFAULT '08:00'`, `close_time TEXT DEFAULT '20:00'`

---

## orders_widget.py — Architecture v1.0

### Layout
- `SectionHeader` + bouton "+ Nouvelle commande"
- **5 KPICards** : `_load_kpis()` — requêtes `COUNT` avec statuts normalisés (vide/`pending`, `assigned`, `in_progress`+`in_transit`, livrées **du jour** `delivered|success|completed`, `failed`) ; mise à jour via `KPICard.set_value()` (alias de `update()`)
- Toolbar : `SearchBar` + filtre statut + boutons 🔄/📅/📤/📥
- Barre d'actions en lot (visible si >1 sélection)
- `QTableWidget` 9 colonnes paginé (`PaginationBar`, 80/page) : Réf | Client | Type (`operation_type`, alias `collection`→Collecte) | Statut (`StatusBadge(variant, label)` après `_normalize_order_status`) | Date | kg | ADR (vide→—) | Priorité ★/☆ | Actions Lucide — **BL** = `ReportService.generate_delivery_note`

### `_OrderDialog` (4 onglets)
| Onglet | Contenu |
|--------|---------|
| Commande | référence auto (`ORD-YYYYMMDD-NNNN`), client QComboBox cherchable, type (livraison/collecte/échange/retour), statut, date prévue, priorité |
| Marchandises | kg, m³, unités, catégorie, température (ambient/chilled/frozen), classe ADR, valeur déclarée |
| Créneaux | créneau 1 (obligatoire), créneau 2 optionnel, durée visite, instructions, code accès |
| Assignation | véhicule & chauffeur : `QComboBox` éditable — **`_wire_order_assign_combo` avant `_set_assign_combo_by_id`** + `_sync_assign_combo_line_edit` pour afficher l’intitulé choisi ; placeholders recherche ; libellés véhicule `immat · marque`, chauffeur `prénom nom` ; `QCompleter`, `InsertPolicy.NoInsert`, QSS `orderAssign*` ; FK `0` = non assigné ; vérif ADR/temp |

### Commandes récurrentes
- `_RecurringDialog` : CRUD table `recurring_order_templates` avec `_TemplateEditDialog` (nom, client, type récurrence, jours actifs checkboxes, créneaux, kg/m³, actif)
- `_GenerateWeekThread` : crée les commandes pour la semaine courante depuis les templates actifs (lundi = day 0), évite les doublons `(client_id, scheduled_date, is_recurring=1)`

### Actions en lot
- Marquer livrées (status → `delivered`)
- Réassigner (`_BatchReassignDialog` → vehicle + driver)
- Archiver (soft delete → `archived=1`)

### Import/Export
- Export CSV/Excel (`HAS_OPENPYXL`) via `QFileDialog`
- Import : `_ImportMappingDialog` (mapping 5 colonnes) → `_ImportThread` (background) → rapport créés/màj/erreurs

### Statuts commandes
| Code | Label | Variant badge |
|------|-------|---------------|
| `pending` | En attente | warning |
| `assigned` | Assignée | info |
| `in_progress` | En cours | info |
| `delivered` | Livrée | success |
| `failed` | Échec | danger |
| `cancelled` | Annulée | danger |

---

## Navigation — Index des pages (v5.17)

| Index | Widget | Page |
|-------|--------|------|
| 0 | `DashboardWidget` | Tableau de bord |
| 1 | `ClientsWidget` | Clients |
| 2 | `VehiclesWidget` | Véhicules |
| 3 | `DriversWidget` | Chauffeurs |
| 4 | `DepotsWidget` | Dépôts |
| 5 | `OrdersWidget` | Commandes |
| 6 | `CarriersWidget` | Transporteurs |
| 7 | `OptimizationWidget` | Optimisation |
| 8 | `MapWidget` | Carte |
| 9 | `TrackingWidget` | Suivi en temps réel |
| 10 | `ScenariosWidget` | Scénarios |
| 11 | `TranslationWidget` | Traduction |
| 12 | `ReportsWidget` | Rapports |
| 13 | `LogsWidget` | Journal |
| 14 | `NotificationsWidget` | Notifications |
| 15 | `SettingsWidget` | Paramètres |

---

## carriers_widget.py — Architecture v1.0

### Structure globale
`CarriersWidget(QWidget)` contient un `QTabWidget` 4 onglets. Navigation inter-onglets via `_on_tab(idx)` qui déclenche le refresh approprié.

### Onglet 0 — 🚛 Transporteurs
- `SectionHeader` + bouton "+ Ajouter transporteur"
- `SearchBar` + bouton **« Simuler coûts… »** (`setCurrentIndex(2)`) — raccourci vers l’onglet simulation
- `QTabWidget.setUsesScrollButtons(True)` si libellés longs
- `QTableWidget` 9 colonnes : Nom | Contact | Zones | Types | €/km | Note ★/☆ | Ponctualité % | API | Actions (✏📦🗑)
- Double-clic → `_CarrierDialog` | Clic droit → menu contextuel
- Bouton 📦 dans actions → bascule vers onglet Expéditions filtré sur ce transporteur

### `_CarrierDialog` (3 onglets)
| Onglet | Contenu |
|--------|---------|
| Infos | nom*, contact, tél, email, site, notes |
| Capacités & Tarifs | zones (tags editables `_TagsInput`), types véhicules (checkboxes 9 types), coût/km, coût/kg, coût fixe |
| Performance | `StarRating(rating, 5, read_only=False)` + `get_rating()` ; ponctualité % ; URL API ; clé → **keyring** `citypulse_carrier` |

### Onglet 1 — 📦 Expéditions sous-traitées
- Filtre `QComboBox` transporteur + bouton "🔄 Rafraîchir statuts"
- `QProgressBar` (indéterminé, masqué hors refresh)
- `QTableWidget` 8 colonnes : N° Tracking | Commande | Transporteur | Statut (`StatusBadge`) | Livraison est. | Coût (€) | Créé le | Actions
- Double-clic → `_ShipmentDialog`
- **Refresh statuts** : `_StatusRefreshThread(QThread)` → GET `api_tracking_url/{tracking_number}` avec header `Authorization: Bearer {api_key}` (depuis keyring), émet `result(dict)` → mise à jour BDD

### `_ShipmentDialog`
Formulaire : transporteur (QComboBox cherchable), commande (QComboBox cherchable — exclut livrées/annulées), n° tracking, statut, livraison estimée (QDateEdit), coût €, notes

### Onglet 2 — 💰 Simulation flotte propre vs sous-traitance
- Libellé d’onglet : **« Simuler (flotte vs S/T) »**
- Table de commandes en attente (sélection multiple `ExtendedSelection`)
- Bouton **« Lancer la simulation »** → `_SimulationDialog(QDialog)`
  - Sélection transporteur (QComboBox)
  - 3 `KPICard` : Flotte propre (€) | Sous-traitance (€) | Économie estimée (€)
  - Tableau comparatif : Commande | Client | kg | Dist. est. (km) | Coût flotte | Coût transporteur
  - Recommandation colorée (vert = flotte, orange = sous-traitance)
  - Camembert Matplotlib (fonds sombres) : "Flotte propre" vs "Transporteur"
- Calcul coût flotte : dist_aller_retour × avg_cost_per_km des véhicules
- Calcul coût transporteur : cost_fixed + dist × cost_per_km + kg × cost_per_kg

### Onglet 3 — 📊 Évaluation transporteurs
- Filtres période (QDateEdit De/À) + bouton Actualiser
- Boutons export : 📤 Excel (openpyxl) + 📄 PDF (reportlab)
- `QTableWidget` 7 colonnes : Transporteur | Expéditions | Livrées | Taux livr. % | Coût total (€) | Ponctualité % | Note ★
- Graphique double Matplotlib : barres Coût total (gauche) + barres Note (droite)

### Sécurité API keys
- Service keyring : `citypulse_carrier`, username = `str(carrier_id)`
- Fonctions : `_key_set(cid, key)`, `_key_get(cid) -> str`, `_key_del(cid)`
- Fallback silencieux si module `keyring` non disponible

### Flags de disponibilité
| Flag | Condition | Impact |
|------|-----------|--------|
| `HAS_REQUESTS` | `import requests` | Refresh statuts tracking désactivé |
| `HAS_KEYRING` | `import keyring` | Clé API non persistée (note affichée dans dialog) |
| `HAS_MPL` | `import matplotlib` | Graphiques désactivés |
| `HAS_OPENPYXL` | `import openpyxl` | Export Excel désactivé |
| `HAS_REPORTLAB` | `import reportlab` | Export PDF désactivé |

---

## Engine — Extensions v2.0

### ortools_solver.py — Modes VRP

| `vrp_mode` | Description | Paramètre spécifique |
|------------|-------------|----------------------|
| `standard` | VRPTW classique un dépôt (défaut) | — |
| `multi_depot` | M-DVRPTW : affectation véhicule → dépôt par modulo | `depots: list[dict]` |
| `open` | OVRP : retour au dépôt supprimé (dist retour = 0) | — |
| `pickup_delivery` | PDPTW : contraintes précédence + même véhicule | `pickup_delivery_pairs: list[(i,j)]` |
| `reload` | VRPR : rechargement intermédiaire si charge < 20% | — |

### Contraintes avancées ortools_solver.py

| Contrainte | Paramètre | Mécanisme |
|------------|-----------|-----------|
| Compétences | `_vehicle_can_serve(v, c)` | `allowed_adr`, `temperature_type`, `vehicle_requirement` → `SetAllowedVehiclesForIndex` |
| ZFE | `zones: list[dict]` | `_build_zfe_pairs()` → `_apply_zfe_penalty()` ×1.5 |
| Pauses RSE | `legal_break=True` + `_driver` dans véhicule | Dimension `DriveTime` avec slack = min_break_s |
| Pause déjeuner | `lunch_window=(720,840)` | Fenêtres horaires coupées sur 12h-14h |
| Séquences forcées | `forced_sequence: list[(a,b)]` | `routing.solver().Add(NextVar(a) == b)` |
| Multi-objectifs | `objective_weights: dict` | Arc cost = distance×w_d + money×w_c + CO2×w_co2 |
| CO2 dans résultat | — | `total_co2_kg` + `co2_kg` par route |

### cost_calculator.py — Fonctions

| Fonction | Retour | Description |
|----------|--------|-------------|
| `calculate_route_cost(stops, vehicle, driver, fuel_price, toll_factor)` | dict 10 clés | fuel_cost, labor_cost, fixed_cost, toll_estimate, total_cost, cost_per_stop, cost_per_km, co2_kg, total_km, total_h |
| `calculate_co2(distance_km, vehicle)` | float kg | Facteur par motorisation + ajustement PTAC |
| `calculate_eta_sequence(stops, departure_time, travel_times, traffic_factor)` | list[str HH:MM] | ETA séquentielle avec temps de service |
| `check_rse_compliance(route_stops, driver, departure_time)` | dict | compliant, violations, warnings, total_drive_h, breaks_count, regulation CE 561/2006 |
| `check_adr_compliance(orders, vehicle, driver)` | dict | compliant, violations, warnings, adr_classes_found + incompatibilités inter-classes |
| `check_zfe_compliance(route_stops, vehicle, zones)` | dict | compliant, violations, warnings, zfe_zones_entered |

### traffic_adjuster.py — Fonctions

| Fonction | Retour | Description |
|----------|--------|-------------|
| `classify_day_type(date, country)` | str | 'weekday'\|'saturday'\|'sunday'\|'holiday' selon jours fériés MA/FR |
| `get_traffic_coefficient(hour, day_type, zone_type)` | float | Coefficient depuis JSON × multiplicateur zone |
| `adjust_matrix_for_traffic(matrix, hour, day_type, zone_type)` | matrix | Matrice × coeff (format secondes) |
| `get_optimal_departure_hour(matrix, stops, time_windows, ...)` | int | Score = temps total × coeff + pénalités fenêtres |
| `get_traffic_profile(day_type)` | list[float] × 24 | Profil horaire complet |
| `reload_coefficients()` | dict | Force rechargement du JSON |

### data/traffic_coefficients.json — Structure

```json
{
  "weekday":  { "0": 0.85, "7": 1.55, "8": 1.75, "17": 1.80, ... },
  "saturday": { ... },
  "sunday":   { ... },
  "holiday":  { ... },
  "peak_multipliers": { "city_center":1.2, "periurban":1.05, "highway":0.9 },
  "day_type_rules": {
    "public_holidays_MA": ["01-01","01-11","05-01",...],
    "public_holidays_FR": ["01-01","05-01","07-14",...]
  }
}
```

### Nouvelles fixtures conftest.py

| Fixture | Contenu |
|---------|---------|
| `drivers_3` | 3 chauffeurs (RSE, qualifs ADR/FIMO/FCO, taux horaires) |
| `zones_2` | 1 ZFE centre Casablanca (r=2km) + 1 zone livraison |
| `orders_30` | 30 commandes variées (ADR classes 3/8, temp ambiant/frigo, statuts mixtes) |

---

## optimization_widget.py — Architecture v3.0

### Layout général
`QSplitter` horizontal **30 / 70** :
- **Gauche** : `QScrollArea` 320px — panneau de configuration (+ **bandeau warning** si `weather_service.get_traffic_factor` > 1.1 après fetch OWM en thread)
- **Droite** : `QTabWidget` 5 onglets — résultats et analyses
- **Bas** : barre progression + `QTextEdit` log auto-scroll + boutons actions post-run

### Panneau gauche — Configuration

| Section | Widgets |
|---------|---------|
| Données | Labels clients/véhicules/dépôts + `QDateEdit` date + bouton Actualiser |
| Algorithmes | Checkboxes Greedy / 2-opt / OR-Tools |
| Mode VRP | 5 `QRadioButton` : standard / multi_depot / open / pickup_delivery / reload |
| Objectif | 4 `QRadioButton` + frame 4 sliders pondérés (visible si Équilibré) |
| Options avancées | Clustering KMeans, trafic auto, pauses RSE, compétences ADR/ZFE, créneaux, déjeuner 12h-14h, séquences forcées |
| Météo / trafic | 4 `QRadioButton` météo + `QDoubleSpinBox` trafic manuel + bouton "Auto" (`classify_day_type` + `get_traffic_coefficient`) |
| Limites | `QSpinBox` temps OR-Tools (s) + `QSpinBox` itérations 2-opt |
| Lancement | `QPushButton` "🚀 Lancer" (primaryBtn h=48px) + "⏹ Arrêter" (danger, visible pendant calcul) + "Planifier la semaine" (`_WeeklyPlannerDialog` + `_WeekPlanThread`) |

### Panneau droit — 5 onglets

| Onglet | Contenu |
|--------|---------|
| **📊 Comparaison** | `QTableWidget` 4 colonnes (Métrique \| Greedy \| 2-opt \| OR-Tools), mise à jour live, meilleure valeur surlignée en vert+gras, bandeau "🏆 Meilleur algo" |
| **🚗 Détail véhicules** | `QComboBox` algo + `QTreeWidget` (véhicule → arrêts) ; colonne actions : **🔒** verrouiller, **📋** manifeste PDF (`generate_load_manifest` si `routes` en base sinon `generate_load_manifest_from_optimization_route`), **📄** CMR (`generate_cmr` si `order_id` sur `route_stops` sinon `generate_cmr_from_optimization_route`) + export PDF/CSV barre du haut |
| **📈 Graphiques** | 3 graphiques Matplotlib fond sombre : Radar (distance/coût/respect/CO₂), Histogramme distances, Camembert utilisation flotte |
| **💰 Simulation coûts** | 3 sliders (prix carburant, péages, taux horaire) → recalcul immédiat via `calculate_route_cost` + tableau coût détaillé (carburant/MO/fixe/péages/CO₂/TOTAL) |
| **⚠ Conformité RSE/ADR/ZFE** | `QComboBox` algo + 3 panneaux (RSE/ADR/ZFE) avec statut ✅/❌ + liste violations + bouton "🔧 Suggestions" |

### `OptimizationThread` — Signaux

| Signal | Type | Description |
|--------|------|-------------|
| `progress` | `str` | Message d'avancement |
| `partial_result` | `(str, dict)` | Résultat intermédiaire (algo, dict) |
| `finished` | `(str, dict)` | Résultat final (algo, dict) |
| `error` | `(str, str)` | Erreur (algo, message) |
| `compliance` | `(str, dict)` | Conformité post-run : `{rse, adr, zfe}` |

### Flux d'exécution

1. `_run_selected()` — valide données, construit liste algos sélectionnés
2. `_launch_next()` — lance le premier thread (chaîne séquentielle)
3. `_on_result()` — met à jour tableau + arbre + coûts + émet `routes_ready` → MapWidget
4. Après dernier algo : `_draw_charts()` + `_show_post_actions()` + `_update_best_banner()`
5. `_on_compliance()` — stocke dict RSE/ADR/ZFE → rafraîchit onglet conformité

### Actions post-run

- **🗺 Carte** → `_nav_to(8)` (MapWidget)
- **📍 Suivi** → `_nav_to(9)` (TrackingWidget)
- **📁 Scénario** → INSERT dans `scenarios` avec JSON résumé
- **📄 PDF** → reportlab (tableau comparaison)
- **📤 CSV** → tableau comparaison exporté

### Intégration engine v2

- `objective_weights` transmis au solveur OR-Tools via `params`
- `zones`, `forced_sequence`, `lunch_window` transmis si checkboxes cochées
- `calculate_route_cost` + `calculate_co2` utilisés dans la simulation coûts
- `check_rse/adr/zfe_compliance` appelés dans le thread après résolution

---

## tracking_widget.py — Architecture v3.0

### Vue d'ensemble

`TrackingWidget` est la page de suivi en temps réel des tournées (index 9).
Elle reçoit les résultats d'optimisation via `set_routes(result)` et permet de les simuler, visualiser et corriger à chaud.

### Layout QVBoxLayout

```
┌─ Barre simulation (44px) ──────────────────────────────────────────────┐
│  ▶ ⏸ ⏹ | ⏩×2 ⏩⏩×5 | ×N | Slider progression | HH:MM              │
├─ Barre météo (38px) ───────────────────────────────────────────────────┤
│  QComboBox conditions | 🌤 Météo réelle (OWM) | Trafic ×N.NN | Auto   │
├─ 5 KPICards mini (64px) ───────────────────────────────────────────────┤
│  Véhicules actifs | Livraisons | En retard | Km | CO₂ kg               │
└─ QSplitter horizontal 70/30 ───────────────────────────────────────────┘
     GAUCHE QTabWidget :
       📅 Gantt — GanttWidget (QPainter pur)
       📋 Tableau — QTableWidget live (QTimer 1s)
     DROITE Incidents :
       Notifications non lues + signalement + bandeau re-optim
```

### GanttWidget (QPainter pur)

- **Plage horaire** : 06:00 → 20:00 (840 min)
- **Zoom molette** : `Ctrl+molette` → zoom horizontal (×0.5 à ×8), molette seule = scroll
- **Types de blocs** :
  - `travel` → bleu `#1A6CF6`
  - `visit` → vert `#00CC66`
  - `pause` → gris `#5A6A7A`
  - `reload` → orange `#FF8C00`
  - `delay` → rouge hachures `#FF4757`
  - `locked` → violet `#8B5CF6`
- **Ligne rouge** : heure simulation courante (triangle indicateur)
- **Hover** → `QToolTip` (type, début, durée, client)
- **Clic droit** → `QMenu` : Détails / Annuler arrêt / Réaffecter / Verrouiller
- **Drag & drop** blocs → `ConfirmDialog` → émission `block_moved` + `log_action` (delta en px converti en minutes sans biais scroll)
- **Ctrl+Z** : pile d'annulation (20 entrées max, `deque`) — nécessite focus clavier (`StrongFocus`)
- **Annulation arrêt** → émet `block_cancelled(v_idx, b_idx)` → bandeau re-optimisation automatique
- **Pause RSE** : ajoutée **après** la visite si `cursor > 270 min`, `cursor` avancé de 45 min

### Simulation

| Contrôle | Action |
|----------|--------|
| ▶ | Démarrer (QTimer 1s) |
| ⏸ | Pause/Reprendre |
| ⏹ | Reset à 06:00 |
| ⏩×2 / ⏩⏩×5 | Multiplier vitesse |
| Slider | Sauter à une heure |

### Gestion des timers (hideEvent / showEvent)
`_live_timer` (1s, `_update_table_live`) et `_sim_timer` (1s, `_sim_tick`) sont arrêtés dans `hideEvent` quand la page n'est plus visible (navigation vers une autre page), et `_live_timer` est redémarré dans `showEvent`. Ceci évite le `KeyboardInterrupt` CRITICAL loggé par le handler global de `main.py` lors de la fermeture.

### Météo / Trafic

- **QComboBox** : ☀ ×1.0 / 🌧 ×1.1 / ⛈ ×1.25 / ❄ ×1.6
- **🌤 Météo réelle** : `app.services.weather_service` (`get_current`, `get_traffic_factor`) — lat/lon 1er dépôt, clé keyring `citypulse_owm` / `citypulse`
- **Auto** : `get_traffic_coefficient()` + `classify_day_type()` pour l'heure courante
- Ajuste `_traffic_factor` → recalcule durées Gantt

### Signaux

| Signal | Signature | Destinataire |
|--------|-----------|--------------|
| `route_updated` | `(int, str)` | `MapWidget` |
| `center_on_vehicle` | `(int,)` | `MapWidget` |
| `reoptimization_done` | `(dict,)` | `OptimizationWidget` |

**Signaux internes GanttWidget :**

| Signal | Signature | Usage |
|--------|-----------|-------|
| `block_moved` | `(v_idx, b_idx, new_start_min)` | Déplacement drag & drop confirmé |
| `block_locked` | `(v_idx, locked)` | Verrouillage/déverrouillage véhicule |
| `block_cancelled` | `(v_idx, b_idx)` | Annulation arrêt → bandeau re-optim |

### Panneau Incidents (30%)

- Notifications non lues depuis la table `notifications` (filtre `is_read=0`)
- "+ Signaler incident" → `QDialog` (type, immatriculation, description) → INSERT `notifications`
- Bandeau re-optimisation affiché après annulation d'arrêt ou déplacement de bloc

---

## weather_service.py — Service météo (sans Qt)

Module `app/services/weather_service.py` : **cache mémoire TTL 15 min** pour appels OpenWeatherMap.

| Fonction | Comportement |
|----------|----------------|
| `get_current(lat, lng, api_key)` | `dict \| None` — `None` si pas de clé ou erreur réseau |
| `get_forecast_5days(lat, lng, api_key)` | `list[dict]` — liste vide sans clé |
| `get_traffic_factor(weather)` | `float` entre **1.0 et 1.5** (pluie, vent, neige, orage) |
| `get_route_alerts(stops_coords, api_key)` | `list[str]` — alertes texte selon conditions sur le trajet |
| `resolve_owm_api_key()` | Clé explicite ou keyring (`citypulse_owm`, fallback `citypulse`) |

**Intégration UI :** bandeau HTML Leaflet (`MapWidget`), mini-widget dashboard 48px, optimisation, tracking.

---

## notifications_widget.py — Page Notifications (index 14)

- **Filtres** : type, sévérité, non lus seulement, recherche texte
- **Liste** : `QListWidget` items colorés + **panneau détail ~280px**
- **Double-clic** : `QDialog` détail + liens navigation (`navigate_request` → `_nav_to`)
- **Résumé journalier** : `QTimer` toutes les heures — si `notifications.daily_hour` (ou racine `notif_daily_hour`) et `notifications.daily_summary` / `notif_daily_summary` actifs
- **Aide** : clé `notifications` dans `help_dialog.py`
- **Paramètres** : onglet Entreprise dans `settings_widget.py`

---

## settings_widget.py — Paramètres v2 (index 15)

`QTabWidget` **5 onglets** + barre **💾 Sauvegarder** fixée en bas. Persistance `settings.json` (fusion avec défauts, migration clés plates legacy). Duplication racine `notif_daily_*` pour compatibilité. Clés API (Mistral, OWM, OSRM_URL) chargées depuis `.env` au démarrage via `main.py._load_dotenv()` — onglets "API & Intégrations", "Algorithmes" et "Site Web Django" supprimés.

| Onglet | Contenu | Clé JSON |
|--------|---------|----------|
| 🏢 Entreprise | nom, adresse, tél, email, devise MAD/EUR/USD, timezone, logo → `assets/logo.png`, aperçu ; thème UI ; **Langue de l'interface** (`sys_lang` QComboBox 5 langues LANG_DISPLAY → `system.ui_lang`) ; seuils ; résumé notif ; Copilote IA (modèle Mistral + langue) | `company`, `system`, `notifications`, `mistral` |
| 🗺 Carte | fond Standard/Dark/Satellite/Terrain, lat/lon, 📍 dépôt principal, zoom, 10 couleurs (`QColorDialog`), labels / ordre | `map` |
| 📄 Rapports | couleur thème, en-tête, pied, logo, dossier, tableau planifications +/− | `reports` |
| 👤 Utilisateurs | visible si rôle admin/administrateur : tableau CRUD, rôles admin/planner/dispatcher/viewer, soft delete `is_active=0` | BDD `users` |
| 💾 Sauvegarde | export snapshot JSON (`ReportService.generate_full_snapshot`), import snapshot, reset données métier, chargeur démo, `PRAGMA integrity_check` + taille fichier, OSRM URL + timeout + test | `osrm` |

**Threads** : `_OsrmTestThread` — test connexion OSRM (`_HAS_REQUESTS`).

---

## django_sync_service.py — Client HTTP Django (sans Qt)

`DjangoSyncService(base_url, secret_key)` — header **`X-CityPulse-Secret`**, `timeout=10s`, `HTTPError` / `RequestException` capturés.

| Méthode | Rôle |
|---------|------|
| `health_check()` | `GET …/api/health/` → `bool` |
| `sync_clients(data)` | `POST …/api/sync/clients/` → `dict` `{ok, data\|error,…}` |
| `sync_routes(data)` | `POST …/api/sync/routes/` |
| `pull_confirmations()` | `GET …/api/deliveries/confirmations/` → `list[dict]` |
| `pull_proofs()` | `GET …/api/deliveries/proofs/` → `list[dict]` |

---

## scenarios_widget.py — Architecture v2 (compare / what-if / JSON)

### Layout principal
`QSplitter` horizontal **70/30** :
- **Gauche** : tableau scénarios 8 colonnes + toolbar (Import/Export/Dupliquer)
- **Droite** : panneau détail — info-rows (nom, clients, véhicules, algo, date) + éditeur **Tags** (QLineEdit + Sauver) + éditeur **Description** (QTextEdit + Sauvegarder). Se remplit au clic sur une ligne du tableau.

Sections en dessous du splitter : **Comparer deux scénarios** → **Analyse What-If** → **Profil trafic CSV** (avancé, en bas).

### Boutons d'action par scénario
- **Restaurer** (orange) : remplace tous les clients/véhicules/dépôts actuels (confirmation demandée, message ⚠ explicite)
- **Suppr.** : suppression définitive

### Comparaison
Tableau + graphique Matplotlib barres distances avec `bar_label`. Métriques : clients, véhicules, distance km, coût, ponctualité par algo (depuis `results_json`).

### Bugs corrigés v5.41
- **`_save_as_scenario`** (optimization_widget) : INSERT inclut désormais `client_count`, `vehicle_count`, `algorithm` → scénarios sauvegardés depuis l'optimisation n'affichent plus 0/0
- **`_save_current`** : confirmation étendue avec nb clients ET véhicules
- **Help "scenarios"** : aide réécrite pour distinguer les deux sources de sauvegarde (snapshot données vs résultat optimisation)

### Signal
`compare_map_requested = pyqtSignal(dict)` — émet `{"left": payload, "right": payload}` pour `MapWidget._on_scenario_compare_map`

---

## map_widget.py — Météo & comparaison scénarios

- **`_load_map()`** : construit le HTML Leaflet à partir de `settings.json` (`map.*` défauts) ; les dépôts (`latitude`/`longitude`) servent pour les marqueurs / routes, pas pour le centre initial de la carte.
- **`refresh_data()`** : met à jour une **bannière météo** Leaflet (HTML) via `weather_service` + coordonnées dépôt
- **`apply_dual_scenario_routes(left, right)`** : affichage **split** deux jeux de routes (comparaison depuis `ScenariosWidget`)

---

## report_service.py — ReportService v2.0

Classe `ReportService` (reportlab, openpyxl, matplotlib optionnel, qrcode). Chaque export réussi enregistre `reports_history` + `log_action`.

### Internationalisation des rapports (v5.36)

Tous les `generate_*` acceptent un paramètre `lang: str = "fr"` (codes : `fr` / `en` / `es` / `de` / `ar`).  
Mécanisme : dictionnaire `_RL_DATA[lang][key]` (~80 clés) + helper `_RL(lang, key)` avec fallback français.  
Chaque méthode définit `L = lambda k: _RL(lang, k)` pour des appels concis.  
`_header_table(reg, v_type, cap, algo, now_str, lang="fr")` traduit également la bannière d'en-tête.

Dans `reports_widget.py` : `QComboBox` **Langue du rapport** (5 items FR/EN/ES/DE/AR, stocké `self._report_lang_combo`) affiché dans le panneau gauche ; toutes les méthodes `_gen_*` passent `lang=self._report_lang_combo.currentData()` au service.

| Méthode | Sortie | Description |
|---------|--------|-------------|
| `generate_driver_roadbook(route_id, output_path, lang='fr')` | PDF | En-tête logo texte + chauffeur + véhicule, tableau arrêts avec **QR** (payload JSON stop), pied de page |
| `generate_fleet_daily_report(date_str, output_path, lang='fr')` | PDF | Page de garde, graphique Matplotlib barres km/véhicule, tableau comparatif routes du jour |
| `generate_kpi_report(start, end, output_path, fmt='pdf', lang='fr')` | PDF ou XLSX | Évolution quotidienne + tableau comparatif **période vs S-1** (même durée avant `start`) |
| `generate_algo_comparison_report(result_ids, output_path, lang='fr')` | PDF | Tableau `algo_results` + graphique barres distances |
| `generate_client_report(client_id, output_path)` | PDF | Fiche client + 30 dernières commandes |
| `generate_driver_performance_report(period_days, output_path, fmt='pdf')` | PDF/XLSX | Agrégation `routes` × `drivers` |
| `generate_rse_compliance_report(start_date, end_date, output_path)` | PDF | Seuils RSE chauffeurs vs durée routes agrégée |
| `generate_carrier_report(carrier_id=None, output_path=…)` | PDF | Synthèse transporteurs (ou un seul si `id`) |
| `export_to_excel(output_path)` | XLSX | Onglets : Clients, Véhicules, Chauffeurs, Commandes, Tournees (`routes`), Journal (5000 lignes) |
| `generate_full_snapshot(output_path)` | JSON | Dump multi-tables (clients, vehicles, depots, drivers, orders, routes, route_stops, algo_results, carriers, …) |
| `generate_legal_notice_pdf(output_path, doc_type, lang=’fr’)` | PDF | Modèle CGU / confidentialité (synthèse) |
| `generate_delivery_note(order_id, output_path, lang=’fr’)` | PDF | **BL** : en-tête, n° auto `BL-{id}-{timestamp}`, expéditeur dépôt, destinataire client, tableau qté cmd/livrée/obs., signature |
| `generate_cmr(order_id, output_path, lang=’fr’)` | PDF | **CMR** : cases 1–3, 6, 11–13, 18, 23–24 (tables reportlab) |
| `generate_cmr_from_optimization_route(route_info, output_path)` | PDF | CMR synthétique depuis résultat VRP en mémoire (pas d’`order_id` en base) |
| `generate_adr_document(order_id, output_path, lang=’fr’)` | PDF | Uniquement si `orders.adr_class` non vide — désignation ONU, n° UN, classe, groupe emballage, déclaration type |
| `generate_load_manifest(route_id, output_path, lang=’fr’)` | PDF | Manifeste chargement : lignes `route_stops` + commandes, totaux poids/volume/coliss, taux remplissage, signature chef de quai |
| `generate_load_manifest_from_optimization_route(route_info, output_path, lang=’fr’)` | PDF | Même mise en page depuis tournée optimisée en mémoire |

**Compatibilité :** `generate_route_pdf(…, lang=’fr’)`, `generate_all_vehicles_pdf()`, `REPORTLAB_OK`, `OPENPYXL_OK` exportés au niveau module. Le paramètre `lang` est facultatif (défaut `"fr"`) sur toutes les méthodes — les appelants existants qui ne le passent pas continuent à générer des rapports en français.

---

## reports_widget.py — Architecture v2.0

- **Layout** : `QSplitter` **30 / 70** — gauche `QListWidget` (catégories) + sélecteur langue, droite `QStackedWidget` (formulaires) + **aperçu propre à chaque catégorie** + historique.
- **Catégories** : Opérationnels | Analytiques | Clients | Transporteurs | Conformité | **📝 Documents légaux** (CGU + BL / CMR / ADR / manifeste) | Exports.
- **Aperçu par catégorie** : chaque sous-page possède sa propre instance `_PreviewPane` (`_ops_preview`, `_an_preview`, `_cl_preview`, `_car_preview`, `_co_preview`, `_leg_preview`, `_exp_preview`) — **aucune zone partagée**.
- **`_PreviewPane`** : widget unifié (`QStackedWidget` interne) — pages : placeholder (idx 0) + `QPdfView`/`QPdfDocument` (PDF natif Qt, idx dynamique `_pdf_view_idx`) + `QWebEngineView` (HTML/XLSX, idx dynamique `_web_idx`). Indices stockés dynamiquement via `addWidget()` return value (pas de hardcode). Flag `HAS_PDF_VIEW` (`PyQt6.QtPdf` / `PyQt6.QtPdfWidgets`).
- **`_load_preview(preview, path)`** : PDF → `preview.show_pdf()` (QPdfView, fallback QWebEngine) ; XLSX → openpyxl → HTML tableau → `preview.setHtml()`.
- **Langue rapport** : `QComboBox` `self._report_lang_combo` dans le panneau gauche — 5 items (FR/EN/ES/DE/AR, data = code `"fr"/"en"/"es"/"de"/"ar"`). Toutes les méthodes `_gen_*` lisent `lang = self._report_lang_combo.currentData()` et le passent au service.
- **Génération** : `_ReportWorker(QThread)` + `LoadingOverlay` plein parent.
- **Sélection résultats algo (Analytiques)** : `_an_algo_pick` (QComboBox searchable, label lisible algo+km+date) → ajoute dans `_an_algo_list` (QListWidget, `ExtendedSelection`) ; bouton "✕ Retirer" (`_algo_list_remove`) ; `_gen_algo_cmp` lit les IDs depuis `_an_algo_list.item(i).data(UserRole)` — plus de champ texte ID brut.
- **Sélection commande/tournée (Documents légaux)** : `_leg_order_combo` (référence + client + ID) et `_leg_route_combo` (date + immat + ID) — combos searchables avec QCompleter `MatchContains`.
- **Sélection client** : `_cl_combo` (nom + entreprise + ID) ; **transporteur** : `_car_combo` (nom + ID) ; **tournée opérationnelle** : `_op_route_combo` (date + immat + ID).
- **Historique** : `reports_history` (25 derniers), double-clic → rechargement aperçu.
- **Planification** : `QTimer` **60 s** — si option cochée + heure = `QTimeEdit`, export KPI PDF 7 jours dans le dossier configuré (une fois par jour).