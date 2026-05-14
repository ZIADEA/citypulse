# Guide de déploiement — CityPulse Logistics v5.41

Ce document couvre l'installation, le packaging, la configuration des services externes et la mise en production de l'ensemble de la solution : **application desktop PyQt6** + **portail web Django**.

---

## Table des matières

1. [Prérequis système](#1-prérequis-système)
2. [Installation environnement de développement](#2-installation-environnement-de-développement)
3. [Vérification de l'environnement](#3-vérification-de-lenvironnement)
4. [Build PyInstaller (exécutable Windows)](#4-build-pyinstaller-exécutable-windows)
5. [Installateur Inno Setup](#5-installateur-inno-setup)
6. [Installation sur poste utilisateur](#6-installation-sur-poste-utilisateur)
7. [Configuration initiale (première utilisation)](#7-configuration-initiale-première-utilisation)
8. [Clés API et secrets (keyring)](#8-clés-api-et-secrets-keyring)
9. [OSRM — distances routières](#9-osrm--distances-routières)
10. [Portail web Django — installation locale](#10-portail-web-django--installation-locale)
11. [Portail web Django — déploiement production](#11-portail-web-django--déploiement-production)
12. [Connexion desktop ↔ portail web](#12-connexion-desktop--portail-web)
13. [Données de démonstration](#13-données-de-démonstration)
14. [Mises à jour et maintenance](#14-mises-à-jour-et-maintenance)
15. [FAQ / Dépannage](#15-faq--dépannage)

---

## 1. Prérequis système

### Machine de développement / build

| Élément | Requis | Notes |
|---------|--------|-------|
| OS | Windows 10/11 x64 | L'application desktop est conçue pour Windows |
| Python | **3.11 ou 3.12** | `python --version` — éviter 3.13+ (compat PyQt6 variable) |
| pip | 23+ | `python -m pip install --upgrade pip` |
| Git | n'importe | Pour cloner le dépôt |
| Visual C++ Redistributable | 2022 | Requis par PyQt6-WebEngine — [télécharger](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| Inno Setup 6 | Optionnel | Uniquement pour générer l'installateur `.exe` |

### Poste utilisateur final

| Élément | Requis |
|---------|--------|
| Windows 10/11 x64 | |
| Visual C++ Redistributable 2022 | Inclus dans l'installateur Inno Setup |
| Connexion internet | Optionnelle — uniquement pour OSRM public, OWM, Mistral AI, synchro web |

---

## 2. Installation environnement de développement

### 2.1 Cloner le projet

```bash
git clone <url-du-repo> Tour
cd Tour
```

### 2.2 Créer un environnement virtuel (recommandé)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1    # PowerShell
# ou
.venv\Scripts\activate.bat    # cmd
```

### 2.3 Installer les dépendances desktop

```bash
pip install -r requirements.txt
```

Packages installés (principaux) :

| Package | Usage |
|---------|-------|
| `PyQt6 >= 6.5` | Interface graphique |
| `PyQt6-WebEngine` | Carte Leaflet + aperçu PDF natif |
| `ortools >= 9.7` | Algorithme OR-Tools VRP |
| `scikit-learn` | KMeans, IsolationForest |
| `pandas`, `openpyxl` | Import/export Excel |
| `reportlab` | Génération PDF |
| `requests` | OSRM, OWM, API Django |
| `keyring` | Stockage sécurisé des clés API |
| `mistralai` | Copilot IA |
| `deep-translator`, `sacrebleu` | Traduction + score BLEU |
| `pyinstaller >= 6.0` | Packaging Windows |
| `Pillow` | Génération de l'icône |
| `python-dotenv` | Variables d'environnement |
| `pytest`, `pytest-qt`, `pytest-timeout` | Tests |

### 2.4 Lancer en développement

```bash
python main.py
```

La base SQLite `citypulse.db` et le fichier `settings.json` sont créés dans le dossier du projet au premier lancement.

---

## 3. Vérification de l'environnement

```bash
python scripts/check_environment.py
```

Ce script vérifie : Python ≥ 3.11, PyQt6, WebEngine, OR-Tools, SQLite, droits d'écriture disque, keyring, test HTTP vers OSRM public.

Vérifications manuelles supplémentaires :

```bash
# OR-Tools
python -c "from ortools.constraint_solver import routing_enums_pb2; print('OR-Tools OK')"

# WebEngine
python -c "from PyQt6.QtWebEngineWidgets import QWebEngineView; print('WebEngine OK')"

# Keyring
python -c "import keyring; print('Keyring OK')"

# Mistral AI
python -c "import mistralai; print('Mistral OK')"
```

---

## 4. Build PyInstaller (exécutable Windows)

### 4.1 Lancer le build

```bash
python build.py
```

Le script `build.py` :

1. Vérifie que tous les imports critiques sont disponibles
2. Génère `assets/icon.ico` avec Pillow si absent
3. Nettoie `dist/` et `build/`
4. Lance `pyinstaller citypulse.spec` (mode **onedir**)
5. Vérifie que `dist/citypulse/citypulse.exe` existe
6. Calcule le SHA256 de l'exe → `build_report.txt`

### 4.2 Résultat

```
dist/
└── citypulse/
    ├── citypulse.exe          ← exécutable principal
    ├── _internal/             ← bibliothèques Python et Qt
    ├── data/                  ← données packagées (photos placeholder, .gitkeep)
    └── assets/                ← icon.ico, logo.png
```

Les fichiers **utilisateur** (`citypulse.db`, `settings.json`, `citypulse.log`) sont créés **à côté de `citypulse.exe`**, pas dans `_internal/`. Ne pas les supprimer entre les mises à jour — ils contiennent les données de l'entreprise.

### 4.3 Spec PyInstaller (`citypulse.spec`)

Points clés du spec :

- Mode **onedir** (pas onefile) — démarrage rapide, débogage facilité
- `datas` : `settings.json`, `data/`, `assets/`, `app/ui/components/`
- `hiddenimports` : WebEngine, OR-Tools, keyring Windows backend
- `excludes` : tkinter, tests (allège le build)
- Icône : `assets/icon.ico`
- Métadonnées Windows : ProductName = *CityPulse Logistics*, version 1.0.0.0

---

## 5. Installateur Inno Setup

### 5.1 Prérequis

Installer [Inno Setup 6](https://jrsoftware.org/isdl.php).

### 5.2 Générer l'installateur

1. Exécuter `python build.py` (section 4)
2. Ouvrir `installer.iss` dans Inno Setup Compiler
3. Compiler (`F9` ou menu Build → Compile)

Sortie : `installer_output/CityPulseSetup.exe`

### 5.3 Ce que l'installateur fait

- Copie tout `dist/citypulse/` dans `C:\Program Files\CityPulse Logistics\`
- Crée un raccourci dans le menu Démarrer
- Propose un raccourci Bureau (tâche optionnelle)
- Installe les redistribuables VC++ si absent
- Crée un désinstalleur visible dans « Ajouter ou supprimer des programmes »

---

## 6. Installation sur poste utilisateur

### Option A — Via l'installateur (recommandé)

1. Copier `CityPulseSetup.exe` sur le poste
2. Exécuter en tant qu'administrateur
3. Suivre l'assistant

### Option B — Copie manuelle (déploiement silencieux)

1. Copier **tout** le dossier `dist/citypulse/` vers le poste (ex. `C:\CityPulse\`)
2. Créer un raccourci vers `citypulse.exe`

> Ne jamais copier `citypulse.exe` seul — il a besoin de `_internal/`.

### Premier lancement

Au premier lancement :

- `citypulse.db` est créée (21 migrations SQLite)
- `settings.json` est créé avec les valeurs par défaut
- Le compte `admin / admin` est créé
- L'interface s'ouvre sur le **Tableau de bord**

---

## 7. Configuration initiale (première utilisation)

### 7.1 Changer le mot de passe admin

**Paramètres → Utilisateurs** → sélectionner `admin` → modifier le mot de passe.

### 7.2 Renseigner les informations de l'entreprise

**Paramètres → Entreprise** : nom, adresse, téléphone, email, devise, timezone, logo.

### 7.3 Configurer la carte

**Paramètres → Carte** : latitude/longitude du centre par défaut (correspondant à la zone d'activité), zoom, fond de carte.

### 7.4 Créer les dépôts

**Page Dépôts → + Ajouter dépôt** : au moins un dépôt avec coordonnées valides est requis pour l'optimisation.

### 7.5 Importer les données

Deux méthodes :

| Méthode | Commande |
|---------|---------|
| Interface | Fichier → Charger données de démo (`Ctrl+D`) |
| CSV/Excel | Page Clients → Importer · Page Commandes → Importer |
| Ligne de commande | `python scripts/generate_demo_data.py --dataset casablanca --db citypulse.db --reset` |

### 7.6 Langue de l'interface

**Paramètres → Entreprise → Langue de l'interface** : FR / EN / AR / ES / DE — changement instantané sans redémarrage.

### 7.7 Créer les comptes utilisateurs supplémentaires

**Paramètres → Utilisateurs** (visible uniquement si rôle admin) :

| Rôle | Accès |
|------|-------|
| `admin` | Toutes les pages + gestion utilisateurs + snapshot BDD |
| `planner` | Optimisation, carte, scénarios, rapports, traduction |
| `dispatcher` | Clients, véhicules, commandes, chauffeurs, suivi, notifications |
| `viewer` | Lecture seule |

---

## 8. Clés API et secrets (keyring)

Toutes les clés sont stockées dans le **Gestionnaire des informations d'identification Windows** via la bibliothèque `keyring`. Elles ne sont **jamais** écrites en clair dans les fichiers.

### 8.1 Tableau des services keyring

| Service keyring | Username | Valeur stockée | Où configurer |
|----------------|----------|----------------|---------------|
| `citypulse_django` | `django_api_secret` | Secret partagé desktop ↔ web | Paramètres → Sauvegarde |
| `citypulse` | `mistral_api_key` | Clé API Mistral AI | Paramètres → Entreprise |
| `citypulse_owm` | `citypulse` | Clé OpenWeatherMap | Paramètres → Entreprise |
| `citypulse_carrier` | `<carrier_id>` | Clé API par transporteur | Transporteurs → fiche → Perf |

### 8.2 Générer un secret partagé (desktop ↔ web)

```python
import secrets
print(secrets.token_hex(32))
# ex : f0ee885b99a3ca6d92dc90080cc1d95b8b6bf31d2c2b88d5411709bf6c263836
```

Copier la valeur :
- Dans `citypulse-web/.env` : `CITYPULSE_API_SECRET=<valeur>`
- Dans l'application desktop : **Paramètres → Sauvegarde → Clé secrète Django** → coller → Sauvegarder

### 8.3 Lire/écrire le keyring manuellement (dépannage)

```python
import keyring

# Lire
print(keyring.get_password("citypulse_django", "django_api_secret"))

# Écrire
keyring.set_password("citypulse_django", "django_api_secret", "ma-cle-secrete")

# Supprimer
keyring.delete_password("citypulse_django", "django_api_secret")
```

### 8.4 Obtenir les clés API

| API | Usage | Lien |
|-----|-------|------|
| **Mistral AI** | Copilot, traduction fallback, analyse | [console.mistral.ai](https://console.mistral.ai) |
| **OpenWeatherMap** | Météo dashboard, carte, Gantt | [openweathermap.org/api](https://openweathermap.org/api) |
| **OSRM** | Matrices distances/temps | Instance publique ou locale (section 9) |

---

## 9. OSRM — distances routières

### 9.1 Instance publique (développement)

L'application utilise par défaut `http://router.project-osrm.org`. Elle est limitée en débit et ne convient pas à la production.

**Paramètres → Sauvegarde → OSRM URL** : laisser vide ou `http://router.project-osrm.org`

### 9.2 Instance locale Docker (production recommandée)

#### Maroc (Casablanca)

```bash
# 1. Télécharger les données OSM
curl -O https://download.geofabrik.de/africa/morocco-latest.osm.pbf

# 2. Préparer
docker run -t -v "%cd%:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/morocco-latest.osm.pbf
docker run -t -v "%cd%:/data" osrm/osrm-backend osrm-partition /data/morocco-latest.osrm
docker run -t -v "%cd%:/data" osrm/osrm-backend osrm-customize /data/morocco-latest.osrm

# 3. Lancer (port 5000)
docker run -t -i -p 5000:5000 -v "%cd%:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/morocco-latest.osrm
```

#### France (Paris)

```bash
curl -O https://download.geofabrik.de/europe/france/ile-de-france-latest.osm.pbf
# Même procédure avec ile-de-france-latest.osm.pbf
```

#### Configurer l'URL dans l'app

**Paramètres → Sauvegarde → OSRM URL** : `http://localhost:5000` → **Tester la connexion**

### 9.3 Fallback automatique

Si OSRM est inaccessible, `distance.py` bascule automatiquement :

```
OSRM HTTP  →  Cache SQLite (distance_cache)  →  Haversine ×1.3
```

La colonne `distance_source` dans `algo_results` indique la source utilisée pour chaque run.

---

## 10. Portail web Django — installation locale

### 10.1 Prérequis

- Python 3.11+ (peut être le même venv que le desktop, ou un venv dédié)
- Pas de Java, pas de Node — Tailwind CSS est chargé via CDN

### 10.2 Installation

```bash
cd citypulse-web
python -m venv .venv-web
.venv-web\Scripts\activate

pip install -r requirements.txt
```

### 10.3 Fichier `.env`

```bash
copy .env.example .env
```

Éditer `.env` :

```env
# Obligatoires
SECRET_KEY_DJANGO=<generer avec : python -c "import secrets; print(secrets.token_hex(32))">
CITYPULSE_API_SECRET=<meme valeur que dans le keyring desktop>
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Optionnel (production)
DATABASE_URL=postgres://user:password@host:5432/citypulse
```

### 10.4 Migrations et superutilisateur

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 10.5 Lancer le serveur de développement

```bash
python manage.py runserver
```

Portail : **http://127.0.0.1:8000**

### 10.6 Charger les données de démo web

```bash
python manage.py seed_demo
```

Crée :
- Chauffeur `souleymane.diallo` / `Livraison2026`
- Client `amina.benali` / `Suivi2026`
- Tournées + historique 5 jours

### 10.7 Structure du portail web

| URL | Description | Accès |
|-----|-------------|-------|
| `/accounts/login/` | Connexion | Public |
| `/driver/` | Mes tournées du jour | Chauffeur |
| `/driver/route/<id>/` | Détail tournée + carte + confirmation + photo | Chauffeur |
| `/client/` | Mes commandes | Client |
| `/track/<ref>/` | Suivi public d'une commande | Public |
| `/admin/` | Administration Django | Superuser |
| `/api/health/` | Health check | Header secret |
| `/api/sync/clients/` | Sync clients ← desktop | Header secret |
| `/api/sync/routes/` | Sync tournées ← desktop | Header secret |
| `/api/deliveries/confirmations/` | Confirmations → desktop | Header secret |
| `/api/deliveries/proofs/` | Preuves photo/signature → desktop | Header secret |
| `/api/deliveries/confirm/` | Enregistrer confirmation chauffeur | Header secret |
| `/api/users/create/` | Créer/mettre à jour compte web | Header secret |

---

## 11. Portail web Django — déploiement production

### 11.1 Variables d'environnement communes

```env
SECRET_KEY_DJANGO=<token_hex(32)>
CITYPULSE_API_SECRET=<meme que keyring desktop>
DEBUG=False
ALLOWED_HOSTS=<votre-domaine.com>
DATABASE_URL=<url postgres ou sqlite>
```

### 11.2 Vercel (recommandé pour démo / staging)

Le fichier `vercel.json` est fourni dans `citypulse-web/`.

1. Importer le projet depuis `citypulse-web/` dans Vercel
2. Ajouter les variables d'environnement (Settings → Environment Variables)
3. Déployer

> Limitation Vercel : le système de fichiers est en lecture seule — utiliser PostgreSQL (ex. Supabase, Neon) pour la base de données.

### 11.3 Railway

```bash
# Procfile (fourni)
web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn citypulse_web.wsgi
```

Ajouter les variables d'environnement dans le dashboard Railway + plugin PostgreSQL.

### 11.4 Serveur Windows local (production interne)

```bash
pip install waitress
python manage.py collectstatic --noinput
waitress-serve --port=8000 citypulse_web.wsgi:application
```

### 11.5 HTTPS (production)

Placer un reverse proxy (Nginx, Caddy, IIS) devant Django pour terminer TLS.

Exemple Caddy minimal :

```
votre-domaine.com {
    reverse_proxy localhost:8000
}
```

---

## 12. Connexion desktop ↔ portail web

### 12.1 Configuration côté desktop

1. Démarrer le portail web (local ou distant)
2. **Paramètres → Sauvegarde** → renseigner l'URL Django (ex. `http://127.0.0.1:8000`) → **Tester la connexion** → doit afficher ✅
3. La clé secrète est lue automatiquement depuis le keyring (`citypulse_django` / `django_api_secret`)

### 12.2 Flux de synchronisation automatique

| Déclencheur | Sens | Endpoint | Données |
|------------|------|----------|---------|
| ✅ Confirmer le plan | Desktop → Web | `POST /api/sync/routes/` | Tournées du jour (véhicule, chauffeur, arrêts, ETA) |
| ✅ Confirmer le plan | Desktop → Web | `POST /api/deliveries/confirm/` | Statut `assigned` + ETA + nom chauffeur par commande |
| Timer 60s (page Suivi) | Web → Desktop | `GET /api/deliveries/confirmations/` | Statut livraisons confirmées par les chauffeurs |
| Bouton 🌐 (client/chauffeur) | Desktop → Web | `POST /api/users/create/` | Création/mise à jour compte web |

### 12.3 Sécurité API

Tous les endpoints API exigent le header :

```
X-CityPulse-Secret: <CITYPULSE_API_SECRET>
```

Sans ce header, le portail retourne `401 Unauthorized`.

### 12.4 Tester la connexion manuellement

```bash
# Health check
curl -H "X-CityPulse-Secret: votre-secret" http://127.0.0.1:8000/api/health/

# Attendu : {"ok": true, "service": "citypulse-web", "timestamp": "..."}
```

---

## 13. Données de démonstration

### 13.1 Via l'interface (recommandé)

Menu **Fichier → Charger données de démo** (`Ctrl+D`)

| Dataset | Véhicules | Chauffeurs | Clients | Commandes | Notes |
|---------|-----------|-----------|---------|-----------|-------|
| **Casablanca** | 13 | 13 | 80 | 200 | 3 dépôts, 2 équipes, 5 zones GeoJSON, 3 scénarios, 30j de routes |
| **Paris** | 5 | 5 | 50 | 80 | 2 dépôts, Île-de-France |
| **Benchmark** | 20 | 20 | 500 | — | 1 dépôt, sans créneaux ni ADR, pour tester les performances algo |

### 13.2 Via la ligne de commande (CLI autonome, sans Qt)

```bash
# Casablanca uniquement (reset complet)
python scripts/generate_demo_data.py --dataset casablanca --db citypulse.db --reset

# Ajouter Paris sans effacer Casablanca
python scripts/generate_demo_data.py --dataset paris --db citypulse.db --append

# Tout générer + exporter CSV/Excel
python scripts/generate_demo_data.py --dataset all --db citypulse.db --reset --export ./demo_data/
```

### 13.3 Portail web

```bash
cd citypulse-web
python manage.py seed_demo
```

---

## 14. Mises à jour et maintenance

### 14.1 Mettre à jour l'application desktop

1. Arrêter l'application sur tous les postes
2. Rebuilder : `python build.py`
3. Remplacer `dist/citypulse/` sur chaque poste (ou regénérer l'installateur Inno Setup)
4. **Ne pas supprimer** `citypulse.db` ni `settings.json` — ils contiennent les données
5. Au premier lancement, les nouvelles migrations SQLite s'appliquent automatiquement

### 14.2 Sauvegarder la base de données

**Méthode recommandée** : **Paramètres → Sauvegarde → Exporter snapshot JSON** — export complet multi-tables.

**Méthode brute** (fermer l'application avant) :
```bash
copy citypulse.db citypulse_backup_%date:~-4%-%date:~3,2%-%date:~0,2%.db
```

### 14.3 Vérifier l'intégrité de la base

Via l'interface : **Paramètres → Sauvegarde → Vérifier intégrité BDD**

Via la ligne de commande :
```bash
python -c "import sqlite3; c=sqlite3.connect('citypulse.db'); print(c.execute('PRAGMA integrity_check').fetchone())"
# Attendu : ('ok',)
```

### 14.4 Réinitialiser complètement la base

```bash
del citypulse.db
python main.py    # recréée avec admin/admin et 21 migrations
# Puis : Fichier → Charger données de démo
```

### 14.5 Mettre à jour le portail web

```bash
cd citypulse-web
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
# Redémarrer le serveur (waitress, gunicorn, etc.)
```

---

## 15. FAQ / Dépannage

### L'exe ne démarre pas ou crash immédiatement

- Vérifier que le dossier complet `dist/citypulse/` est présent (ne pas copier `citypulse.exe` seul)
- Installer [Visual C++ Redistributable 2022 x64](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- Consulter `citypulse.log` pour l'erreur exacte

### La carte Leaflet affiche des tuiles grises

```bash
python -c "from PyQt6.QtWebEngineWidgets import QWebEngineView; print('OK')"
```

Si erreur : PyQt6-WebEngine doit être installé dans **le même interpréteur** que celui utilisé pour lancer `main.py`.

```bash
python -m pip install PyQt6-WebEngine
# Vérifier quel Python est utilisé :
python -c "import sys; print(sys.executable)"
```

Consulter `citypulse.log` — l'application y journalise l'exception WebEngine exacte (DLL manquante, plugin, etc.).

### OR-Tools non disponible

```bash
pip install ortools
python -c "from ortools.constraint_solver import routing_enums_pb2; print('OK')"
```

### Le Copilot IA ne répond pas

1. Vérifier la clé Mistral : **Paramètres → Entreprise → Clé API Mistral**
2. `pip install mistralai`
3. Tester la clé : `python -c "from mistralai import Mistral; print('OK')"`

### La météo n'apparaît pas

1. Vérifier la clé OWM : **Paramètres → Entreprise → Clé OpenWeatherMap**
2. Vérifier que les dépôts ont des coordonnées valides (la météo utilise le 1er dépôt)

### Le portail web retourne 401 Unauthorized

La valeur `CITYPULSE_API_SECRET` dans `.env` ne correspond pas au keyring desktop.

```python
# Vérifier la valeur dans le keyring :
import keyring
print(keyring.get_password("citypulse_django", "django_api_secret"))
```

Copier cette valeur dans `citypulse-web/.env` → redémarrer Django.

### La synchro web ne se déclenche pas après "Confirmer le plan"

1. Vérifier que l'URL Django est renseignée : **Paramètres → Sauvegarde → URL Django** → **Tester la connexion**
2. Vérifier que le portail web est démarré et accessible
3. Consulter `citypulse.log` — les erreurs de synchro sont loggées en `WARNING`

### Les commandes restent "En attente" après confirmation du plan

Deux causes :

**A. Le client n'était pas dans l'optimisation** — vérifier :
- Coordonnées valides (lat/lon non nuls dans la fiche client)
- Demande kg ≤ capacité du plus grand véhicule (`Page Véhicules → Cap. kg`)
- Fenêtre horaire compatible avec les créneaux de la flotte

**B. Capacité totale flotte insuffisante** — la demande totale des clients dépasse la somme des capacités. Réduire le périmètre de l'optimisation ou ajouter des véhicules.

### Base de données introuvable après déplacement de l'exe

`citypulse.db` est toujours **à côté** de `citypulse.exe`. Déplacer l'ensemble du dossier d'installation, jamais l'exe seul.

### OSRM : erreur 429 ou timeouts

- Basculer vers une instance OSRM locale (section 9.2)
- Le cache SQLite (`distance_cache`) évite les appels répétés pour les mêmes paires

### Erreur Unicode dans la console Windows

```powershell
$env:PYTHONIOENCODING = "utf-8"
python main.py
```

### Personnaliser l'icône de l'application

Remplacer `assets/icon.ico` (256×256 minimum) avant `python build.py`.

### Personnaliser le logo dans les rapports PDF

Remplacer `assets/logo.png` (fond transparent recommandé). L'aperçu est visible dans **Paramètres → Entreprise → Logo**.

---

*CityPulse Logistics v5.41 — ENSAM Meknès 2025-2026*  
*Référence API : `citypulse-web/SYNC_API.md` · Guide utilisateur : `README.md`*
