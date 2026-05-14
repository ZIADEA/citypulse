# CityPulse Logistics — Prompts Agents Codeurs DÉFINITIFS (VS Code)
> **Version DÉFINITIVE — 100% des fonctionnalités du .md spécifications incluses**
> **PC :** ASUS TUF Gaming F16 · i7-14650HX · 16 GB RAM · ~924 GB SSD · Windows 11
> **Contrainte :** Desktop PyQt6 + SQLite uniquement (pas de PostgreSQL)
> **Base :** MVP v5.0 fonctionnel (12 pages, 3 algos VRP, SQLite, OR-Tools, Mistral)
> **Site web chauffeurs/clients :** Django séparé → Vercel/Railway (prompt dédié en fin)
> **Pas de :** multi-tenant, 2FA TOTP, app mobile native

---

## 📋 COMMENT UTILISER CES PROMPTS

1. Ouvre VS Code dans le dossier `Tour/`
2. Lance l'agent codeur (Copilot, Continue, Cursor, ou autre)
3. Colle le prompt de la phase souhaitée **tel quel** dans le chat
4. L'agent lit `CLAUDE.md` en premier — source de vérité absolue
5. Exécute les phases **dans l'ordre**
6. Après chaque phase : `pytest tests/ -v` + `python main.py`

---

## ⚠️ RÈGLE GLOBALE POUR TOUS LES AGENTS

> Lis **CLAUDE.md** en entier avant de commencer.
> - Pattern widget : `_setup_ui()` construction UI / `refresh_data()` requêtes BDD
> - Ne jamais bloquer le thread Qt (op > 50ms → QThread)
> - Toujours `get_connection()`, jamais `sqlite3.connect()` directement
> - Toujours `log_action()` après toute mutation BDD
> - Soft delete uniquement (`archived=1`)
> - Clés API via `keyring` uniquement
> - SQLite uniquement — pas de SQLAlchemy
> - Mettre à jour CLAUDE.md après chaque phase

---

## ⚡ ORDRE D'EXÉCUTION COMPLET

```
PHASE 0-A   Schéma BDD complet — toutes les tables
PHASE 0-B   Design System + composants UI réutilisables
PHASE 1-A   Dashboard KPIs temps réel
PHASE DS    Données de test réalistes (injecter tôt !)
PHASE 2-A   Gestion clients avancée
PHASE 2-B   Gestion véhicules & flotte
PHASE 2-C   Gestion dépôts & commandes
PHASE 2-D   Gestion chauffeurs & équipes          [NOUVEAU]
PHASE 2-E   Gestion transporteurs & sous-traitants [NOUVEAU]
PHASE 3-A   Moteur VRP étendu + RSE + ADR + ZFE   [ENRICHI]
PHASE 3-B   Interface optimisation avancée
PHASE 4-A   Carte interactive multi-couches
PHASE 4-B   Tracking temps réel + Gantt interactif
PHASE 5-A   Rapports enterprise complets           [ENRICHI]
PHASE 5-B   Documents légaux (CMR, BL, ADR)        [NOUVEAU]
PHASE 6-A   IA avancée + Copilote enrichi
PHASE 6-B   Météo service + Notifications + Scénarios
PHASE 6-C   Paramètres avancés + Sync Django       [NOUVEAU]
PHASE 7-A   Suite de tests complète
PHASE 7-B   Packaging Windows
PHASE DJ    Site web Django chauffeurs (projet séparé)
```

---

# PHASE 0-A — SCHÉMA BDD COMPLET

## PROMPT 0-A : Schéma SQLite complet & migrations robustes

```
Tu es un expert Python/SQLite. Lis CLAUDE.md et METIER.md en entier.

OBJECTIF : Reconstruire db_manager.py avec le schéma complet de CityPulse Logistics.
Garder SQLite + pattern get_connection() existants.

1. SYSTÈME DE MIGRATIONS VERSIONNÉ
   - Table schema_version : id, version INTEGER, applied_at TEXT, description TEXT
   - Chaque migration = fonction migrate_XXX(conn) numérotée 001, 002...
   - Idempotente (IF NOT EXISTS partout)
   - init_database() applique toutes les migrations manquantes dans l'ordre

2. COLONNES AJOUTÉES AUX TABLES EXISTANTES (migration idempotente)

TABLE clients — ajouter :
  company_name TEXT, contact_phone TEXT, contact_email TEXT,
  access_code TEXT, notes TEXT, photo_url TEXT,
  service_duration_minutes INTEGER DEFAULT 15,
  preferred_driver_id INTEGER, vehicle_requirement TEXT,
  tags TEXT, client_type TEXT DEFAULT 'standard',
  punctuality_factor REAL DEFAULT 1.0,
  delay_penalty_per_hour REAL DEFAULT 0.0,
  is_recurring INTEGER DEFAULT 0, recurrence_pattern TEXT,
  website_client_id TEXT, adr_class TEXT,
  time_window2_start TEXT, time_window2_end TEXT

TABLE vehicles — ajouter :
  registration_plate TEXT, brand TEXT, model TEXT, year INTEGER,
  vehicle_type TEXT DEFAULT 'van',
  fuel_type TEXT DEFAULT 'diesel',
  co2_per_km REAL DEFAULT 0.21,
  max_height_cm INTEGER, max_width_cm INTEGER, max_length_cm INTEGER,
  max_weight_kg REAL, insurance_expiry TEXT,
  technical_inspection_expiry TEXT, insurance_number TEXT,
  allowed_adr INTEGER DEFAULT 0, allowed_zfe INTEGER DEFAULT 1,
  daily_km_limit REAL, open_start INTEGER DEFAULT 0,
  open_stop INTEGER DEFAULT 0, reload_allowed INTEGER DEFAULT 1,
  cost_per_hour REAL DEFAULT 15.0, cost_fixed_daily REAL DEFAULT 50.0,
  speed_highway REAL DEFAULT 110, speed_national REAL DEFAULT 80,
  speed_urban REAL DEFAULT 45, speed_zone30 REAL DEFAULT 25,
  photo_url TEXT

TABLE depots — ajouter :
  manager_name TEXT, phone TEXT,
  open_time TEXT DEFAULT '06:00', close_time TEXT DEFAULT '20:00',
  max_vehicles INTEGER DEFAULT 50, loading_bays INTEGER DEFAULT 4,
  loading_time_minutes INTEGER DEFAULT 30,
  unloading_time_per_kg REAL DEFAULT 0.001,
  notes TEXT, photo_url TEXT, is_cross_dock INTEGER DEFAULT 0

TABLE algo_results — ajouter :
  co2_total REAL, cost_total REAL, vehicles_used INTEGER,
  stops_count INTEGER, on_time_rate REAL, scenario_name TEXT,
  created_by INTEGER, objective_weights TEXT,
  vrp_mode TEXT DEFAULT 'standard'

TABLE users — ajouter :
  role TEXT DEFAULT 'planner',
  full_name TEXT, email TEXT, phone TEXT,
  permissions TEXT, last_login TEXT,
  is_active INTEGER DEFAULT 1, website_user_id TEXT

3. NOUVELLES TABLES À CRÉER

TABLE drivers :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  first_name TEXT NOT NULL, last_name TEXT NOT NULL,
  company_name TEXT, phone TEXT, email TEXT, photo_url TEXT,
  license_number TEXT, license_category TEXT, license_expiry TEXT,
  qualifications TEXT,
  contract_type TEXT DEFAULT 'CDI',
  work_start_time TEXT DEFAULT '07:00',
  work_end_time TEXT DEFAULT '17:00',
  lunch_time TEXT DEFAULT '12:00',
  lunch_duration_minutes INTEGER DEFAULT 60,
  max_daily_hours REAL DEFAULT 10.0,
  overtime_level1_hours REAL DEFAULT 1.0,
  overtime_level1_rate REAL DEFAULT 1.25,
  overtime_level2_hours REAL DEFAULT 2.0,
  overtime_level2_rate REAL DEFAULT 1.5,
  max_drive_before_break_min INTEGER DEFAULT 270,
  min_break_minutes INTEGER DEFAULT 45,
  min_daily_rest_minutes INTEGER DEFAULT 660,
  home_depot_id INTEGER, vehicle_id INTEGER,
  zone_assignment TEXT, notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  archived INTEGER DEFAULT 0

TABLE driver_unavailabilities :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  driver_id INTEGER NOT NULL, date TEXT NOT NULL,
  reason TEXT, notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))

TABLE teams :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, manager_driver_id INTEGER,
  description TEXT, created_at TEXT DEFAULT (datetime('now')),
  archived INTEGER DEFAULT 0

TABLE team_members :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL, driver_id INTEGER NOT NULL,
  joined_at TEXT DEFAULT (datetime('now'))

TABLE orders :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reference TEXT UNIQUE, client_id INTEGER NOT NULL,
  vehicle_id INTEGER, driver_id INTEGER, depot_id INTEGER,
  operation_type TEXT DEFAULT 'delivery',
  status TEXT DEFAULT 'pending',
  quantity_kg REAL DEFAULT 0, volume_m3 REAL DEFAULT 0,
  units_count INTEGER DEFAULT 1,
  goods_category TEXT DEFAULT 'standard',
  adr_class TEXT, temperature_required TEXT DEFAULT 'ambient',
  declared_value REAL, time_window_start TEXT, time_window_end TEXT,
  time_window2_start TEXT, time_window2_end TEXT,
  planned_arrival TEXT, actual_arrival TEXT, actual_departure TEXT,
  visit_duration_minutes INTEGER DEFAULT 15,
  visit_duration_per_kg_seconds REAL DEFAULT 0,
  priority INTEGER DEFAULT 5, delivery_notes TEXT,
  access_instructions TEXT, proof_photo_path TEXT, signature_path TEXT,
  failure_reason TEXT, is_recurring INTEGER DEFAULT 0,
  parent_order_id INTEGER, created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  scheduled_date TEXT, created_by INTEGER, archived INTEGER DEFAULT 0

TABLE routes :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  algo_result_id INTEGER, vehicle_id INTEGER NOT NULL,
  driver_id INTEGER, depot_start_id INTEGER, depot_end_id INTEGER,
  planned_date TEXT NOT NULL,
  status TEXT DEFAULT 'planned',
  is_locked INTEGER DEFAULT 0,
  total_km REAL, total_duration_min REAL, total_cost REAL, co2_kg REAL,
  stops_count INTEGER, on_time_count INTEGER, notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))

TABLE route_stops :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  route_id INTEGER NOT NULL, order_id INTEGER,
  stop_type TEXT DEFAULT 'delivery',
  stop_order INTEGER NOT NULL,
  planned_arrival TEXT, planned_departure TEXT,
  actual_arrival TEXT, actual_departure TEXT,
  duration_min INTEGER DEFAULT 15,
  distance_from_prev_km REAL,
  status TEXT DEFAULT 'pending',
  notes TEXT, is_locked INTEGER DEFAULT 0

TABLE carriers :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, contact_name TEXT, phone TEXT, email TEXT,
  website TEXT, zones_covered TEXT, vehicle_types TEXT,
  cost_per_km REAL, cost_per_kg REAL, cost_fixed REAL,
  rating REAL DEFAULT 3.0, on_time_rate REAL,
  api_tracking_url TEXT, api_key_encrypted TEXT, notes TEXT,
  created_at TEXT DEFAULT (datetime('now')), archived INTEGER DEFAULT 0

TABLE carrier_shipments :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  carrier_id INTEGER NOT NULL, order_id INTEGER NOT NULL,
  tracking_number TEXT, status TEXT DEFAULT 'pending',
  estimated_delivery TEXT, actual_delivery TEXT, cost REAL, notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))

TABLE notifications :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL, severity TEXT DEFAULT 'info',
  title TEXT NOT NULL, message TEXT,
  related_table TEXT, related_id INTEGER,
  is_read INTEGER DEFAULT 0, user_id INTEGER, action_url TEXT,
  created_at TEXT DEFAULT (datetime('now'))

TABLE zones :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  zone_type TEXT DEFAULT 'delivery',
  geojson TEXT NOT NULL, color TEXT DEFAULT '#FF6B6B',
  description TEXT, is_active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))

TABLE scenarios :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, description TEXT, tags TEXT,
  config_json TEXT NOT NULL, results_json TEXT,
  created_at TEXT DEFAULT (datetime('now')), created_by INTEGER

TABLE reports_history :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_type TEXT NOT NULL, parameters_json TEXT,
  file_path TEXT, file_size_kb INTEGER,
  generated_at TEXT DEFAULT (datetime('now')), generated_by INTEGER

TABLE ai_conversations :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER, messages_json TEXT NOT NULL,
  context_json TEXT, created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))

TABLE recurring_order_templates :
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, client_id INTEGER NOT NULL,
  operation_type TEXT DEFAULT 'delivery',
  quantity_kg REAL, volume_m3 REAL, units_count INTEGER,
  goods_category TEXT, time_window_start TEXT, time_window_end TEXT,
  visit_duration_minutes INTEGER DEFAULT 15, priority INTEGER DEFAULT 5,
  recurrence_type TEXT, recurrence_days TEXT,
  recurrence_day_of_month INTEGER, is_active INTEGER DEFAULT 1,
  notes TEXT, created_at TEXT DEFAULT (datetime('now'))

4. NOUVELLES FONCTIONS db_manager.py

def has_permission(user_id, module, action) -> bool:
  # admin=tout | planner=lect+écrit sauf users | dispatcher=lect+statuts | viewer=lecture

def get_expiring_documents(days_ahead=30) -> list:
  # Véhicules avec assurance ou CT expirant dans X jours

def generate_order_reference() -> str:
  # Génère ORD-YYYY-XXXXXX

def create_notification(type_, title, message, severity='info',
                        related_table=None, related_id=None, user_id=None) -> int:
  # Crée notification + log_action automatique

def get_unread_notifications_count(user_id=None) -> int

5. FICHIERS À MODIFIER
   - app/database/db_manager.py : réécriture complète
   - requirements.txt : ajouter loguru>=0.7, Pillow>=10.0, qrcode>=7.4,
                        python-dateutil>=2.8, faker>=20.0
   - settings.json : étendre avec company{}, map{}, reports{}, notifications{},
                     website{django_url}. Défaults Casablanca (33.5731, -7.5898)
   - .env.example : créer (voir GUIDE_API_KEYS)
   - .gitignore : créer (.env, *.db, *.log, __pycache__, dist/, build/)
   - CLAUDE.md : mettre à jour

Lancer pytest tests/ -v après pour valider les tests existants.
```

---

# PHASE 0-B — DESIGN SYSTEM

## PROMPT 0-B : Design System & composants UI réutilisables

```
Tu es un expert PyQt6 UI/UX. Lis CLAUDE.md.

OBJECTIF : Refaire styles.py + créer app/ui/components/.

1. DEUX THÈMES — get_stylesheet(theme='dark') dans styles.py

DARK (défaut) :
  bg_main=#0D1B2A  bg_sidebar=#0A1628  bg_panel=#112240  bg_input=#1A2E4A
  accent=#00D4FF   success=#00FF88     warning=#FFB800   danger=#FF4757
  text=#E8F4FD     text_sec=#8899AA    border=#1E3A5F    hover=#1A3A5C

LIGHT :
  bg_main=#F0F4F8  bg_sidebar=#1565C0  bg_panel=#FFFFFF  bg_input=#F8FAFC
  accent=#1565C0   success=#2E7D32     warning=#E65100   danger=#C62828
  text=#1A1A2E     text_sec=#546E7A    border=#CFD8DC    hover=#E3F2FD

QSS complet pour : QMainWindow, QWidget, QFrame, QDialog,
  Sidebar (item h=52px, hover animé, sélection accent),
  QPushButton #primaryBtn #secondaryBtn #dangerBtn #ghostBtn #iconBtn,
  QTableWidget + QHeaderView (header sombre, alternance, hover, sélection),
  QLineEdit QComboBox QSpinBox QDoubleSpinBox QDateEdit QTimeEdit (h=38px, r=6px),
  QTabWidget (underline accent), QProgressBar (gradient animé),
  QScrollBar (8px fine), QLabel #heading #subheading #caption,
  QGroupBox, QCheckBox, QRadioButton, QSlider,
  QTextEdit, QSplitter handle, QMenuBar, QMenu, QToolBar, QStatusBar,
  QTreeWidget, QListWidget, QMessageBox, QDockWidget

2. COMPOSANTS CUSTOM — app/ui/components/__init__.py + fichiers séparés :

kpi_card.py → KPICard(QFrame)
  __init__(title, value, unit='', icon='📊', trend='', trend_up=True)
  update(value, trend, trend_up) | taille min 200×110px | hover animé

status_badge.py → StatusBadge(QLabel)
  status: success/warning/danger/info/neutral/pending/active
  update_status(status, text)

section_header.py → SectionHeader(QWidget)
  __init__(title, subtitle='', action_text='', action_callback=None)
  Ligne séparatrice accent

search_bar.py → SearchBar(QWidget)
  Signal search_changed(str) debounce 300ms
  clear(), set_placeholder(text), get_text()

confirm_dialog.py → ConfirmDialog(QDialog)
  @staticmethod ask(parent, title, msg, type='warning') -> bool

empty_state.py → EmptyState(QWidget)
  __init__(icon, title, subtitle='', action_text='', action_callback=None)

notification_bell.py → NotificationBell(QPushButton)
  Badge rouge compteur non lu | dropdown 5 dernières notifs
  update_count(n), refresh_from_db()

loading_spinner.py → LoadingSpinner(QWidget)
  QPainter pur (arc tournant, QTimer 50ms)
  start(msg), stop()

pagination_bar.py → PaginationBar(QWidget)
  Signal page_changed(page, offset, limit)
  update_total(total)

collapsible_section.py → CollapsibleSection(QWidget)
  En-tête cliquable ▶/▼ + animation 150ms

star_rating.py → StarRating(QWidget)
  Signal rating_changed(int) | ★/☆ unicode

topbar.py → TopBar(QWidget)
  Fil d'Ariane + NotificationBell + utilisateur + déconnexion | h=48px

3. INTÉGRATION main_window.py
   - Ajouter TopBar entre sidebar et QStackedWidget
   - Sidebar collapse/expand : QPropertyAnimation 200ms
   - Fade-in page : QGraphicsOpacityEffect 0→1, 150ms
   - TopBar.refresh_breadcrumb(name) dans _nav_to()
   - NotificationBell.refresh_from_db() toutes 30s (QTimer)

Mettre à jour CLAUDE.md avec structure components/.
```

---

# PHASE 1-A — DASHBOARD

## PROMPT 1-A : Dashboard temps réel enterprise

```
Tu es un expert PyQt6/Matplotlib. Lis CLAUDE.md.

LAYOUT :
En-tête 48px : "Bonjour [full_name]" + date + heure (QTimer 1s)
               + indicateur OSRM 🟢/🔴 + indicateur Mistral 🟢/🔴

Ligne 1 — 5 KPICards :
  📦 Livraisons aujourd'hui (delivered/total, tendance vs hier)
  🚗 Véhicules actifs (en_service/total)
  ⏱ Taux ponctualité (% créneaux, 7j glissants)
  💰 Coût moyen tournée (avg algo_results, 7j, tendance vs S-1)
  🌱 CO₂ économisé (OR-Tools vs Greedy, 7j)

Ligne 2 — QSplitter 60/40 + panneau alertes 280px :
  Graphique 1 (60%) Matplotlib : barres nb livraisons/j + courbe distance/j
  Graphique 2 (40%) Matplotlib : barres groupées Greedy/2-opt/OR-Tools
  Panneau alertes : notifications is_read=0, clic → navigate, "✓ Tout lu"
  Widget météo mini 48px si OWM configuré (temp + icône + condition)

Ligne 3 — QSplitter 65/35 :
  Tableau activité récente : 10 dernières lignes logs
  Stats rapides : prévisions J+1, commandes en attente, véhicules dispo demain
                  Bouton "📊 Analyser patterns" → route_analyzer → QDialog

QTimer refresh 30s. "⟳ Mis à jour il y a Xs".
Empty state → bouton "Charger données démo" → DemoLoaderDialog.
Toutes requêtes BDD dans refresh_data().
```

---

# PHASE DS — DONNÉES DE TEST

## PROMPT DS : Générateur de données réalistes

```
Tu es un expert Python data engineering. Lis CLAUDE.md.

OBJECTIF : scripts/generate_demo_data.py couvrant TOUTES les tables.

DATASET CASABLANCA (principal) :
  Centre 33.5731°N -7.5898°W, rayon 35km

  3 Dépôts réels de Casablanca avec toutes les colonnes remplies
  
  8 Véhicules (2 frigos Renault Master, 3 Sprinter, 2 Berlingo, 1 vélo cargo)
  avec immatriculations MA-XXXXX-X, toutes colonnes remplies
  
  8 Chauffeurs correspondants (prénoms marocains réalistes, permis, qualifs)
  
  2 Équipes avec membres et managers
  
  80 Clients dans quartiers réels de Casablanca :
    24 supermarchés (Marjane, Label Vie, Carrefour...) : 200-1000kg, 06h-10h
    20 restaurants : 20-80kg, 08h-12h ou 14h-18h
    16 bureaux : 5-30kg, 08h-17h
    12 pharmacies : 10-50kg, 09h-13h ou 15h-19h
    8 particuliers : 5-20kg, 10h-14h
  
  3 Transporteurs (DHL Maroc, Amana Express, CTM Messagerie)
  
  200 Commandes sur J à J+14 (50% pending, 20% assigned, 20% delivered, 10% failed)
  References ORD-2026-000001 à ORD-2026-000200
  15 commandes récurrentes + 5 recurring_order_templates
  20 carrier_shipments
  
  Routes + route_stops (30 jours historique, 5-8 routes/jour)
  
  5 Zones GeoJSON valides
  
  20 Notifications non lues variées
  3 Scénarios sauvegardés
  150 logs audit sur 30 jours, 3 utilisateurs
  2 conversations IA exemples

DATASET PARIS (secondaire) :
  Centre 48.8566°N 2.3522°E, rayon 20km
  50 clients, 5 véhicules, 2 dépôts, 80 commandes

DATASET BENCHMARK :
  500 clients random, 20 véhicules, 1 dépôt
  Pas de contraintes créneaux/ADR

CLI :
  python scripts/generate_demo_data.py --dataset casablanca --db citypulse.db --reset
  python scripts/generate_demo_data.py --dataset paris --db citypulse.db --append
  python scripts/generate_demo_data.py --dataset benchmark --db citypulse.db
  python scripts/generate_demo_data.py --dataset all --export ./demo_data/ --reset

Fichiers CSV/Excel dans demo_data/
app/ui/demo_loader.py → DemoLoaderDialog(QDialog) avec barre progression
Accessible : EmptyState dashboard + menu Fichier + page Paramètres
Script autonome (sans Qt). Faker si disponible, sinon listes hardcodées.
```

---

# PHASE 2-A — CLIENTS

## PROMPT 2-A : Gestion clients avancée

```
Tu es un expert PyQt6. Lis CLAUDE.md.

OBJECTIF : Refaire clients_widget.py complet.

LAYOUT :
  SectionHeader + bouton "+ Ajouter"
  SearchBar + CollapsibleSection filtres avancés
  QTableWidget paginé (PaginationBar 100/page)
  Colonnes : ID | Nom | Entreprise | Tél | Demande kg | Créneaux | Priorité★ | Tags | Statut | Actions
  StarRating readonly, StatusBadge, boutons ✏🗺🗑, sélection multiple + lots
  Double-clic → édition | Clic droit → menu contextuel

DIALOGUE (5 onglets) :
  "Général" : nom*, entreprise, type, statut, tags (chips éditables)
  "Adresse" : adresse*, lat/lng + 🔍 Géocoder (QThread Nominatim),
              minimap Leaflet 300×200 (QWebEngineView), code accès, instructions
  "Livraison" : kg, m3, durée visite, créneau 1, créneau 2 optionnel,
                ADR, température, ponctualité (slider 0-5), pénalité €/h,
                vehicle_requirement (QComboBox)
  "Contact" : nom, tél, email, notes, chauffeur préféré (QComboBox drivers)
  "Historique" : 10 derniers orders ce client

FILTRES (CollapsibleSection) :
  Type multi-select | Priorité slider | Tags | Rayon km | Créneau compatible | Statut
  Bouton "💾 Sauvegarder filtre"

IMPORT CSV/EXCEL :
  ColumnSelectionDialog + prévisualisation 5 lignes
  Géocodage en lot (QThread) + LoadingOverlay
  Rapport : X créés, Y mis à jour, Z erreurs

DÉTECTION ANOMALIES :
  Bouton "🔍 Détecter anomalies" → QThread anomaly_detection → QDialog résultats

EXPORT : CSV, Excel, JSON
VUE CARTE : QDialog 800×600 Leaflet avec markers colorés par type

Test unitaire import CSV.
```

---

# PHASE 2-B — VÉHICULES

## PROMPT 2-B : Gestion véhicules & flotte

```
Tu es un expert PyQt6. Lis CLAUDE.md.

LAYOUT :
  Bandeau alertes documents expirés (get_expiring_documents(30))
  SectionHeader + "+ Ajouter véhicule"
  Tableau : Immatriculation | Marque | Type | Chauffeur | Capacité | CO2/km | Statut | Docs | Actions
  StatusBadge : disponible(success)/en_service(info)/maintenance(warning)/hors_service(danger)

FICHE VÉHICULE (7 onglets) :
  "Identité"    : immatriculation, marque, modèle, année, type, motorisation, photo upload
  "Capacités"   : poids max, volume, palettes, dimensions (cm), CO2/km, ADR, ZFE
  "Vitesses"    : autoroute/nationale/urbaine/zone30 (QSpinBox km/h)
  "Coûts"       : coût/km, coût/h, coût fixe/j, coût non-utilisation/j
  "Chauffeur"   : QComboBox cherchable drivers + open_start/stop/reload checkboxes
  "Documents"   : assurance (date + alerte <30j), CT, carte grise, n° assurance
  "Dispo & Stats" : dépôt attache, planning hebdo 7 checkboxes,
                    km total, nb tournées, coût total

CALENDRIER DISPONIBILITÉ :
  Grille mensuelle, clic → créer/supprimer indisponibilité

ALERTES MAINTENANCE + STATS FLOTTE (KPICards + camembert Matplotlib)
```

---

# PHASE 2-C — DÉPÔTS & COMMANDES

## PROMPT 2-C : Gestion dépôts & commandes

```
Tu es un expert PyQt6. Lis CLAUDE.md.

DÉPÔTS — depots_widget.py :
  Tableau + Fiche (3 onglets : Infos | Carte Leaflet minimap | Stats)
  Vue globale tous dépôts + zones couverture

COMMANDES — orders_widget.py (index 3 QStackedWidget) :
  5 KPICards : En attente | Assignées | En cours | Livrées aujourd'hui | Échecs
  Tableau paginé avec StatusBadge
  
  DIALOGUE (4 onglets) :
    "Commande" : référence auto, client (QComboBox cherchable), type, statut, date, priorité
    "Marchandises" : kg, m3, unités, catégorie, température, ADR, valeur
    "Créneaux" : créneau 1+2, durée visite, instructions, code accès
    "Assignation" : véhicule (+ vérif compatibilité ADR/temp), chauffeur, dépôt
  
  COMMANDES RÉCURRENTES :
    Bouton "🔄 Templates récurrents" → CRUD recurring_order_templates
    Bouton "📅 Générer semaine" → crée orders depuis templates actifs
  
  Import/Export CSV/Excel + actions en lot

Mettre à jour main_window.py + CLAUDE.md.
```

---

# PHASE 2-D — CHAUFFEURS & ÉQUIPES (NOUVEAU)

## PROMPT 2-D : Gestion chauffeurs & équipes

```
Tu es un expert PyQt6. Lis CLAUDE.md.

OBJECTIF : Créer drivers_widget.py. Insérer après Véhicules. MAJ main_window.py.

QTabWidget (4 onglets) :

Onglet "👤 Chauffeurs" :
  Bandeau alertes permis expirants (<30j)
  Tableau : Photo | Nom | Permis | Qualifications | Véhicule | Équipe | Statut | Actions
  
  FICHE (5 onglets) :
    "Personnel" : photo upload, prénom*, nom*, tél, email
    "Permis & Qualifs" : numéro, catégorie (B/C/CE/D), expiration (alerte <30j),
                         checkboxes ADR/CACES/FCO/FIMO, type contrat
    "Horaires" : début/fin, pause, max/jour,
                 overtime niveau 1 (durée+taux), niveau 2 (durée+taux)
    "RSE" : max conduite avant pause (min), pause mini (min), repos journalier (min)
    "Affectation" : dépôt, véhicule, zone, open_start/stop,
                    stats : nb tournées, km total, retard moyen

Onglet "📅 Indisponibilités" :
  QComboBox chauffeur + grille calendrier mensuel (QPainter ou tableau)
  Clic → QDialog : date, raison, notes
  Suggestion remplacement si indisponibilité sur date avec route planifiée

Onglet "👥 Équipes" :
  QListWidget équipes | Pour équipe sélectionnée : CRUD membres
  QListWidget membres ← Retirer / Ajouter → QListWidget tous chauffeurs
  Manager (QComboBox sur membres)

Onglet "📊 Performance" :
  Filtres chauffeur + période
  Tableau + graphique barres Matplotlib + export CSV
```

---

# PHASE 2-E — TRANSPORTEURS (NOUVEAU)

## PROMPT 2-E : Gestion transporteurs & sous-traitants

```
Tu es un expert PyQt6. Lis CLAUDE.md.

OBJECTIF : Créer carriers_widget.py. MAJ main_window.py.

QTabWidget (4 onglets) :

Onglet "🚛 Transporteurs" :
  Tableau : Nom | Contact | Zones | Types | Coût/km | Note★ | Ponctualité | Actions
  
  FICHE (3 onglets) :
    "Infos" : nom*, contact, tél, email, site, notes
    "Capacités & Tarifs" : zones (tags), types véhicules (checkboxes),
                           coût/km, coût/kg, coût fixe
    "Performance" : StarRating éditable, ponctualité %, URL API suivi,
                    clé API (masquée → keyring)

Onglet "📦 Expéditions sous-traitées" :
  Tableau + DIALOGUE (commande + transporteur + tracking + coût)
  Bouton "🔄 Rafraîchir statuts" → QThread HTTP si api_tracking_url

Onglet "💰 Simulation flotte propre vs sous-traitance" :
  Multi-select commandes → comparer coût flotte vs transporteur
  Tableau comparatif + recommandation + camembert Matplotlib

Onglet "📊 Évaluation transporteurs" :
  Tableau récap + graphique barres + export PDF/Excel
```

---

# PHASE 3-A — MOTEUR VRP ENRICHI

## PROMPT 3-A : Moteur VRP + RSE + ADR + ZFE

```
Tu es un expert Python optimisation. Lis CLAUDE.md.
Règle : engine/ sans PyQt6 ni DB directe.

engine/ortools_solver.py — extensions :

1. VARIANTES (paramètre vrp_mode) :
   'standard', 'multi_depot', 'open', 'pickup_delivery', 'reload'

2. CONTRAINTES :
   - Compétences véhicule/commande (temp/ADR/vehicle_requirement)
   - Zones interdites/ZFE (pénalité ×1.5 sur distance si traversée)
   - Pauses RSE automatiques (max_drive_before_break_min + min_break_minutes)
   - Pause déjeuner fenêtre interdite 12h-14h (configurable settings)
   - Séquence forcée : forced_sequence list[tuple]
   - Verrouillage arrêts : is_locked=1 → position fixe
   - Rechargement intermédiaire si capacité < 20%

3. MULTI-OBJECTIFS (objective_weights: dict)
   distance/cost/delays/co2, défaut {'distance':1.0,'cost':0.5,'delays':2.0,'co2':0.3}

4. CALLBACK PROGRESSION (SolutionCallback toutes 500ms)

engine/cost_calculator.py (NOUVEAU) :
  calculate_route_cost(stops, vehicle, driver, fuel_price, toll_factor) → dict
    fuel_cost, labor_cost, fixed_cost, toll_estimate, total_cost, cost_per_stop, cost_per_km
  calculate_co2(distance_km, vehicle) → float
  calculate_eta_sequence(stops, departure_time, travel_times, traffic_factor) → list[str]
  check_rse_compliance(route_stops, driver, departure_time) → dict
  check_adr_compliance(orders, vehicle, driver) → dict
  check_zfe_compliance(route_stops, vehicle, zones) → dict

engine/traffic_adjuster.py (NOUVEAU) :
  data/traffic_coefficients.json (coefficients par heure, weekday/weekend/holiday)
  adjust_matrix_for_traffic(matrix, hour, day_type) → matrix
  get_optimal_departure_hour(matrix, stops, time_windows) → int

TESTS :
  test_ortools_mdvrp.py, test_ortools_open.py
  test_cost_calculator.py (coûts + CO2 + RSE + ADR + ZFE)
  test_traffic_adjuster.py
  conftest.py : ajouter drivers_3, zones_2, orders_30
```

---

# PHASE 3-B — INTERFACE OPTIMISATION

## PROMPT 3-B : Interface optimisation avancée

```
Tu es un expert PyQt6. Lis CLAUDE.md.

LAYOUT QSplitter horizontal 30/70 :

GAUCHE — Configuration (QScrollArea 320px) :
  Données (nb clients/véhicules/dépôts, QDateEdit date)
  Algorithmes (checkboxes Greedy/2-opt/OR-Tools)
  Mode VRP (QRadioButton : standard/multi_depot/open/pickup_delivery/reload)
  Objectif (QRadioButton + 4 sliders si Équilibré)
  Options avancées (clustering, trafic, pauses RSE, ADR/ZFE/compétences,
                    contraintes créneaux, séquences forcées)
  Limites (temps OR-Tools, itérations 2-opt)
  Bouton "🚀 Lancer" (primaryBtn h=48px)
  Bouton "⏹ Arrêter" (dangerBtn, visible pendant calcul)

DROITE — Résultats (QTabWidget 5 onglets) :
  "📊 Comparaison temps réel" : tableau 3 colonnes, mise à jour live, meilleur surligné
  "🚗 Détail par véhicule" : QTreeWidget + boutons PDF/CSV/Lock par véhicule
  "📈 Graphiques" : radar + histogramme + camembert (Matplotlib)
  "💰 Simulation coûts" : sliders recalcul immédiat sans relancer VRP
  "⚠ Conformité RSE/ADR/ZFE" : check_compliance() résultats + bouton corriger

BARRE PROGRESSION : ProgressBar + log QTextEdit auto-scroll
ACTIONS POST : carte | scénario | rapports PDF | CSV

Threads : un OptimizationThread par algo (en parallèle)
Signaux : progress(str), partial_result(dict), finished(dict), error(str), compliance(dict)
```

---

# PHASE 4-A — CARTE

## PROMPT 4-A : Carte interactive multi-couches

```
Tu es un expert PyQt6 + Leaflet.js. Lis CLAUDE.md.

LAYOUT :
  Toolbar verticale gauche (48px, boutons icônes)
  QDockWidget couches gauche (200px) : QCheckBox 9 couches + QComboBox fond de carte
  QWebEngineView centrale (carte Leaflet)
  QDockWidget info droite (280px, s'ouvre au clic)

COUCHES :
  🚩 Dépôts (markers étoile, popup infos+stats)
  📦 Clients (markers numérotés+colorés, markercluster, popup HTML+bouton Éditer)
  🛣 Routes (polylines colorées par véhicule, flèches direction, popup)
  🚗 Véhicules live (markers animés, clignotants si retard)
  🌡 Heatmap (Leaflet.heat)
  📐 Zones (polygones depuis table zones)
  ⚠ Alertes (markers rouges clignotants)
  🌤 Météo (bannière HTML si OWM configuré)
  🚦 Trafic (placeholder HERE)

OUTILS (toolbar) :
  Mesure distance (Leaflet.draw polyline)
  Dessiner zone (polygon/rectangle → dialogue Python → sauvegarde zones)
  Recherche adresse (input Nominatim → coords Python)
  Centrer tout (fitBounds) | Export PNG | Plein écran

VUE COMPARATIVE : QSplitter 2 cartes iframes HTML

ANIMATION HISTORIQUE : slider 06h-20h, vitesse x1/x5/x10

MapBridge(QObject) + QWebChannel :
  Python→JS : update_routes, update_markers, toggle_layer, set_basemap, center_on
  JS→Python : on_marker_clicked(table,id), on_map_rightclick(lat,lng),
              on_zone_drawn(geojson), on_address_found(lat,lng)

Leaflet 1.9.4 depuis cdnjs.cloudflare.com
Plugins : Leaflet.heat, Leaflet.draw, Leaflet.markercluster
LEAFLET_HTML complet dans constante du widget.
```

---

# PHASE 4-B — TRACKING

## PROMPT 4-B : Tracking temps réel + Gantt interactif

```
Tu es un expert PyQt6 + QPainter. Lis CLAUDE.md.

LAYOUT QVBoxLayout :

BARRE SIMULATION : ▶ ⏸ ⏹ ⏩x2 ⏩⏩x5 | slider progression | heure HH:MM
PANNEAU MÉTÉO : QComboBox + bouton météo réelle (si OWM) + traffic_factor
5 KPICards mini

QSplitter horizontal 70/30 :

  GAUCHE (70%) QTabWidget :
    
    Tab "📅 Gantt" — GanttWidget(QWidget) QPainter pur :
      Header timeline 06:00→20:00
      Une ligne par véhicule
      Blocs : trajet(bleu) | visite(vert) | pause(gris) | rechargement(orange) | retard(rouge hachures)
      Ligne rouge = heure simulation (update 1s)
      Hover → QToolTip | Clic droit → QMenu (Annuler/Détails/Réaffecter/Verrouiller)
      Drag & drop → ConfirmDialog → route_stops UPDATE
      Ctrl+Z undo (pile 20) | Molette → zoom horizontal
      Boutons Lock/Unlock tournée
    
    Tab "📋 Tableau" :
      Colonnes + code couleur + QTimer 1s + double-clic → center_on_vehicle

  DROITE (30%) Incidents :
    Notifications non lues + bouton "+ Signaler incident"
    Bandeau re-optimisation si arrêt annulé

Signal route_updated(vehicle_id, stops_json) → MapWidget
Signal center_on_vehicle(id) → MapWidget
```

---

# PHASE 5-A — RAPPORTS

## PROMPT 5-A : Système de rapports enterprise

```
Tu es un expert Python reportlab/openpyxl. Lis CLAUDE.md.

app/services/report_service.py — classe ReportService :

1. generate_driver_roadbook(route_id, output_path) → str PDF
   En-tête logo+chauffeur+véhicule | tableau arrêts | QR code par arrêt | pied de page

2. generate_fleet_daily_report(date_str, output_path) → str PDF
   Page garde + par véhicule + graphique Matplotlib → Image reportlab + tableau comparatif

3. generate_kpi_report(start_date, end_date, output_path, fmt='pdf') → str PDF/XLSX
   Graphiques évolution + comparaison S-1

4. generate_algo_comparison_report(result_ids, output_path) → str PDF
5. generate_client_report(client_id, output_path) → str PDF
6. generate_driver_performance_report(period_days, output_path, fmt='pdf') → str
7. generate_rse_compliance_report(start_date, end_date, output_path) → str PDF
8. generate_carrier_report(carrier_id=None, output_path=None) → str PDF
9. export_to_excel(output_path) → str XLSX (onglets Clients/Véhicules/Chauffeurs/Commandes/Tournées/Journal)
10. generate_full_snapshot(output_path) → str JSON

app/ui/reports_widget.py :
  QSplitter 30/70 : Catalogue (QListWidget catégories) | Config + Aperçu
  Catégories : Opérationnels | Analytiques | Clients | Transporteurs | Conformité |
               📝 Documents légaux | Exports
  Génération QThread + LoadingOverlay
  Aperçu QWebEngineView + Historique reports_history
  Planification automatique (QTimer 60s)
```

---

# PHASE 5-B — DOCUMENTS LÉGAUX (NOUVEAU)

## PROMPT 5-B : Documents légaux transport

```
Tu es un expert Python reportlab. Lis CLAUDE.md.

Ajouter dans ReportService :

generate_delivery_note(order_id, output_path) → str PDF
  BL : en-tête logo, numéro BL auto, expéditeur (dépôt), destinataire (client),
  tableau articles (qté commandée/livrée/observations), zone signature client

generate_cmr(order_id, output_path) → str PDF
  Lettre de voiture CMR — formulaire standardisé A4 avec cases numérotées :
  Case 1 expéditeur | Case 2 destinataire | Case 3 lieu livraison
  Case 6 transporteur | Cases 11-13 marchandises
  Case 18 réserves | Cases 23-24 signatures
  Utiliser tables reportlab pour mise en page formulaire

generate_adr_document(order_id, output_path) → str PDF
  Uniquement si order.adr_class non null
  Désignation ONU, n° ONU, classe, groupe emballage, déclaration légale ADR

generate_load_manifest(route_id, output_path) → str PDF
  Manifeste chargement : tous les colis dans le véhicule au départ
  Tableau client/référence/quantité/poids/instructions
  Totaux (poids, volume, nb colis, taux remplissage), zone signature chef de quai

Intégrer dans :
  reports_widget.py : catégorie "📝 Documents légaux"
  orders_widget.py : bouton "📄 BL" dans colonne Actions
  optimization_widget.py : boutons "📋 Manifeste" et "📄 CMR" par véhicule

Archivage dans reports_history après chaque génération.
```

---

# PHASE 6-A — IA AVANCÉE

## PROMPT 6-A : IA avancée + Copilote enrichi

```
Tu es un expert Python ML/IA. Lis CLAUDE.md.
Règle : app/ai/ sans PyQt6 ni DB directe.

demand_forecast.py :
  ForecastEngine.predict_client_demand(client_id, history_data, days=7) → list[dict]
  ForecastEngine.predict_fleet_demand(clients_data, days=7) → dict
  EWMA + saisonnalité jour semaine (+ ARIMA si statsmodels disponible)

clustering.py :
  GeoClusterer : find_optimal_k, cluster_kmeans, cluster_dbscan, export_clusters_geojson

anomaly_detection.py — enrichi :
  detect_all(clients_data, orders_data) → list[dict] avec 'suggestion' ajouté

app/ai/route_analyzer.py (NOUVEAU) :
  RouteAnalyzer.analyze_patterns(routes, stops, drivers) → dict
  Insights : durées réelles vs planifiées, patterns retard, regroupements possibles

mistral_client.py — enrichi :
  build_context(db_stats: dict) → str (contexte système avec données réelles)
  parse_command(response: str) → dict | None (actions: navigate/optimize/create_order)
  get_fallback_response(question: str) → str (10 réponses prédéfinies si API down)

copilot_widget.py — enrichi :
  1. Chips suggestions rapides (6 boutons préremplis)
  2. Exécution commandes IA : bandeau proposal + Exécuter/Ignorer
     main_window reçoit command_ready(dict) et dispatche
  3. Mode analyse globale → QTextEdit large + export PDF
  4. Historique persisté ai_conversations
  5. Langues FR/EN/AR/ES/DE
```

---

# PHASE 6-B — MÉTÉO + NOTIFICATIONS + SCÉNARIOS

## PROMPT 6-B : Météo service + Notifications + Scénarios enrichis

```
Tu es un expert PyQt6/Python. Lis CLAUDE.md.

app/services/weather_service.py (NOUVEAU, sans Qt) :
  Cache mémoire TTL 15min
  get_current(lat, lng, api_key) → dict | None
  get_forecast_5days(lat, lng, api_key) → list[dict]
  get_traffic_factor(weather) → float (1.0-1.5)
  get_route_alerts(stops_coords, api_key) → list[str]
  Si api_key=None → retourne None

Intégration météo :
  Dashboard : widget mini 48px | Optimization : bandeau warning si factor>1.1
  Tracking : bouton "🌤 Météo réelle" | Map : bannière HTML Leaflet

notifications_widget.py (NOUVEAU, insérer après Journal) :
  Filtres type/sévérité/non lus/recherche
  QListWidget items colorés + panneau détail 280px
  Double-clic → QDialog détail + navigation
  Résumé journalier automatique à 18h (QTimer toutes les heures)
  Paramètres notifs dans settings_widget.py

scenarios_widget.py — enrichi :
  1. Comparaison côte à côte 2 scénarios (tableau + graphique + signal map split)
  2. What-If analysis (variante avec 1 paramètre modifié)
  3. Import/Export JSON + duplication + tags + description
```

---

# PHASE 6-C — PARAMÈTRES + DJANGO (NOUVEAU)

## PROMPT 6-C : Paramètres avancés + service sync Django

```
Tu es un expert PyQt6. Lis CLAUDE.md.

settings_widget.py — QTabWidget 8 onglets :

"🏢 Entreprise" : nom, adresse, tél, email, devise (QComboBox MAD/EUR/USD),
  timezone, logo upload → copie assets/logo.png + aperçu
  → settings['company']

"🗺 Carte" : provider défaut, lat/lng défaut + btn "📍 Dépôt principal",
  zoom défaut, 10 couleurs véhicules (QColorDialog)
  → settings['map']

"⚙ Algorithmes" : algo défaut, temps OR-Tools, itérations 2-opt,
  4 coefficients multi-objectifs, mode VRP défaut, clustering, heure départ
  → settings['optimization']

"📄 Rapports" : couleur thème, en-tête, pied de page, afficher logo,
  dossier sauvegarde, rapports planifiés (QTableWidget + / -)
  → settings['reports']

"🔌 API & Intégrations" :
  OSRM : URL + timeout + bouton "🔍 Tester" (QThread → StatusBadge)
  Mistral : clé masquée (toggle 👁) → keyring + modèle + langue + Tester
  OpenWeatherMap : clé → keyring + Tester (affiche météo Casablanca)
  HERE Maps : clé → keyring + Tester
  Traduction : provider (QComboBox) + clé DeepL → keyring + Tester

"🌐 Site Web Django" :
  URL site + clé secrète partagée (→ keyring['django_api_secret'])
  Bouton "🔍 Tester connexion" → QThread GET /api/health/
  
  Export :
    "📤 Clients" → QThread POST /api/sync/clients/
    "📤 Feuilles de route du jour" → POST /api/sync/routes/
    ☐ Sync ETA automatique depuis tracking
  
  Import :
    "📥 Confirmations" → GET /api/deliveries/confirmations/
                        → update orders.status + route_stops.status
    "📥 Photos/Signatures" → GET /api/deliveries/proofs/
                            → update proof_photo_path, signature_path
    Tableau "Synchronisations récentes" (5 dernières)
  
  Bouton "📋 Documentation API" → QDialog texte endpoints attendus

"👤 Utilisateurs" (admin uniquement) :
  CRUD users avec rôles admin/planner/dispatcher/viewer
  Soft delete (is_active=0)

"💾 Sauvegarde" :
  Export/Import JSON BDD | Reset | Démo | Santé système (integrity_check + taille)

Bouton "💾 Sauvegarder" sticky bas.

app/services/django_sync_service.py (NOUVEAU, sans Qt) :
  class DjangoSyncService(base_url, secret_key) :
    health_check() → bool
    sync_clients(clients_data) → dict
    sync_routes(routes_data) → dict
    pull_confirmations() → list[dict]
    pull_proofs() → list[dict]
  Header : 'X-CityPulse-Secret: SECRET'
  requests + timeout=10s + try/except HTTPError
```

---

# PHASE 7-A — TESTS

## PROMPT 7-A : Suite de tests complète

```
Tu es un expert pytest/pytest-qt. Lis CLAUDE.md.

Structure tests/ :
  conftest.py
  unit/ : test_greedy, test_two_opt, test_ortools_standard, test_ortools_mdvrp [NEW],
           test_ortools_open [NEW], test_ortools_pickup [NEW], test_distance,
           test_cost_calculator [NEW], test_traffic_adjuster [NEW], test_anomaly,
           test_clustering [NEW], test_demand_forecast [NEW], test_route_analyzer [NEW],
           test_weather_service [NEW mock], test_rse_compliance [NEW],
           test_django_sync_service [NEW mock], test_bleu, test_validation
  integration/ : test_db_manager, test_optimization_service, test_report_service
  ui/ : test_login_widget, test_clients_widget, test_orders_widget [NEW], test_dashboard_widget

conftest.py enrichi :
  db_memory, db_populated, depot_casablanca (33.5731,-7.5898), depot_rabat,
  clients_10, clients_50, vehicles_3, driver_1, orders_20,
  route_sample, qtapp

Règles : Arrange/Act/Assert commentés | pas de réseau (mock requests)
tmp_path pour fichiers temporaires | temps total < 90s
Couverture : engine 100% | services 85% | ai 75% | db 90% | ui 50%
```

---

# PHASE 7-B — PACKAGING WINDOWS

## PROMPT 7-B : Packaging & déploiement Windows 11

```
Tu es un expert Python packaging. Lis CLAUDE.md.

1. citypulse.spec (PyInstaller onedir) :
   datas : settings.json, data/, assets/, app/ui/components/
   hiddenimports : PyQt6.QtWebEngineWidgets, QtWebEngineCore, QtWebChannel,
                   QtPrintSupport, ortools, keyring, keyring.backends.Windows
   excludes : tkinter, matplotlib.tests, numpy.tests
   icône : assets/icon.ico (générer avec PIL si absent)
   Version info Windows : ProductName="CityPulse Logistics" FileVersion="1.0.0.0"

2. build.py : vérif imports + nettoyage + génération icône + PyInstaller +
   vérif exe + SHA256 + rapport

3. installer.iss (Inno Setup 6) :
   AppName="CityPulse Logistics" AppVersion=1.0
   Menu Démarrer + Bureau + désinstalleur

4. scripts/check_environment.py :
   Python>=3.11 | PyQt6 | WebEngine | OR-Tools | SQLite | écriture dossier
   keyring | OSRM public (test HTTP)

5. README_DEPLOYMENT.md : prérequis + installation + première utilisation +
   config OSRM local + clés API + FAQ

6. CLAUDE.md + METIER.md finaux complets

requirements.txt : ajouter pyinstaller>=6.0
```

---

# PHASE DJ — SITE WEB DJANGO (PROJET SÉPARÉ)

## PROMPT DJ : Site web Django chauffeurs & clients

```
PROJET SÉPARÉ : créer répertoire citypulse-web/ indépendant de Tour/.
Tu es un expert Django.

Déploiement : Vercel (vercel-python) ou Railway
Stack : Django 5.x, SQLite propre, Tailwind CSS CDN, vanilla JS

Structure citypulse-web/ :
  manage.py, requirements.txt, vercel.json, .env.example
  apps/ : accounts/ | routes/ | tracking/ | api/

Modèles :
  CustomUser (AbstractUser + role driver/client + phone + desktop_id)
  DriverRoute (vehicle_id_ext, driver_id_ext, planned_date, stops_json)
  DeliveryTracking (order_id_ext, order_ref, status, eta, last_update)
  DeliveryProof (order_id_ext, photo, signature, confirmed_at)
  SyncLog (direction, type, records_count, status, error_msg)

Endpoints API (sync avec desktop — DjangoSyncService) :
  GET  /api/health/
  POST /api/sync/clients/           Auth: X-CityPulse-Secret header
  POST /api/sync/routes/
  GET  /api/deliveries/confirmations/
  GET  /api/deliveries/proofs/
  POST /api/deliveries/confirm/

Pages chauffeur (login, role=driver) :
  /driver/         : dashboard tournées du jour
  /driver/route/<id>/  : Leaflet + liste arrêts + bouton confirmer livraison + photo
  /driver/history/ : 30 derniers jours

Pages client (login, role=client) :
  /client/         : liste commandes
  /client/track/<ref>/ : suivi ETA temps réel

Page publique :
  /track/<ref>/    : suivi sans compte (lien SMS partageable)
                     statut + ETA + prénom chauffeur + Leaflet mini

Auth : Django allauth + email verification
Mobile-first Tailwind CSS

vercel.json :
  {"version":2,"builds":[{"src":"citypulse_web/wsgi.py","use":"@vercel/python"}],
   "routes":[{"src":"/(.*)","dest":"citypulse_web/wsgi.py"}]}

Variables env : SECRET_KEY_DJANGO, CITYPULSE_API_SECRET, DEBUG, ALLOWED_HOSTS

Créer : README.md (setup + déploiement) + SYNC_API.md (doc endpoints)
```

---

## 🧪 PROMPT VALIDATION (entre chaque phase)

```
Valide la phase qui vient d'être implémentée :

1. pytest tests/ -v --tb=short   → 0 FAILED. Si erreur : corriger avant de continuer.
2. python main.py                 → démarre proprement, navigue vers la page modifiée.
3. python scripts/generate_demo_data.py --dataset casablanca --db citypulse.db --reset
   → charge sans erreur, données visibles dans l'app.
4. CLAUDE.md mis à jour : structure + tables + widgets + index QStackedWidget.
5. Rapport : nb tests, console propre, fonctionnalités validées visuellement.
```
