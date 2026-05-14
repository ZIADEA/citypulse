# CityPulse Logistics v5.41 — Guide Utilisateur

Application desktop PyQt6 d'optimisation de tournées de livraison (VRP) avec IA embarquée, cartographie Leaflet et portail web chauffeurs/clients.

---

## Table des matières

1. [Démarrage et navigation](#1-démarrage-et-navigation)
2. [Tableau de bord (page 0)](#2-tableau-de-bord-page-0)
3. [Clients (page 1)](#3-clients-page-1)
4. [Véhicules (page 2)](#4-véhicules-page-2)
5. [Chauffeurs (page 3)](#5-chauffeurs-page-3)
6. [Dépôts (page 4)](#6-dépôts-page-4)
7. [Commandes (page 5)](#7-commandes-page-5)
8. [Transporteurs (page 6)](#8-transporteurs-page-6)
9. [Optimisation (page 7)](#9-optimisation-page-7)
10. [Carte (page 8)](#10-carte-page-8)
11. [Suivi en temps réel (page 9)](#11-suivi-en-temps-réel-page-9)
12. [Scénarios (page 10)](#12-scénarios-page-10)
13. [Traduction (page 11)](#13-traduction-page-11)
14. [Rapports (page 12)](#14-rapports-page-12)
15. [Journal (page 13)](#15-journal-page-13)
16. [Notifications (page 14)](#16-notifications-page-14)
17. [Paramètres (page 15)](#17-paramètres-page-15)
18. [Copilote IA](#18-copilote-ia)
19. [Portail web chauffeurs et clients](#19-portail-web-chauffeurs-et-clients)
20. [Flux de travail complet](#20-flux-de-travail-complet)
21. [Bonnes pratiques](#21-bonnes-pratiques)
22. [FAQ](#22-faq)

---

## 1. Démarrage et navigation

### 1.1 Connexion

Au lancement, une fenêtre de connexion s'affiche.

| Identifiant | Mot de passe | Rôle |
|------------|-------------|------|
| `admin` | `admin` | Administrateur — accès complet |
| `planificateur` | `admin` | Planner — optimisation, rapports |
| `dispatcher` | `admin` | Dispatcher — clients, commandes, suivi |

> Modifier les mots de passe dans **Paramètres → Utilisateurs** après le premier lancement.

### 1.2 Interface principale

```
┌─ Barre latérale (sidebar) ──┬─ Zone de contenu ──────────────────┐
│  Logo CityPulse             │  TopBar (fil d'ariane + cloche +   │
│  ─────────────              │  compte utilisateur + déconnexion)  │
│  🏠 Tableau de bord         ├─────────────────────────────────────┤
│  👥 Clients                 │                                     │
│  🚛 Véhicules               │   Page active                       │
│  👤 Chauffeurs              │                                     │
│  🏢 Dépôts                  │                                     │
│  📦 Commandes               │                                     │
│  🚚 Transporteurs           │                                     │
│  ⚡ Optimisation            │                                     │
│  🗺 Carte                   │                                     │
│  📍 Suivi                   │                                     │
│  📋 Scénarios               │                                     │
│  🌐 Traduction              │                                     │
│  📄 Rapports                │                                     │
│  📜 Journal                 │                                     │
│  🔔 Notifications           │                                     │
│  ⚙ Paramètres              │                                     │
└─────────────────────────────┴─────────────────────────────────────┘
```

- **Clic sur un élément de la sidebar** → navigation vers la page
- **Cloche 🔔** dans la TopBar → 5 dernières notifications + badge numérique
- **Thème** dark/light → **Paramètres → Entreprise → Thème**
- **Langue** de l'interface → **Paramètres → Entreprise → Langue** (FR/EN/AR/ES/DE)
- **Copilote IA** → icône IA dans la sidebar (dock flottant, persistant)

### 1.3 Charger des données de test

Menu **Fichier → Charger données de démo** (`Ctrl+D`)

Choisir un dataset :

| Dataset | Contenu |
|---------|---------|
| **Casablanca** | 80 clients, 13 véhicules, 13 chauffeurs, 200 commandes, 3 dépôts, 5 zones |
| **Paris** | 50 clients, 5 véhicules, 80 commandes, 2 dépôts |
| **Benchmark** | 500 clients, 20 véhicules — pour tester les performances des algorithmes |

---

## 2. Tableau de bord (page 0)

Vue synthétique de l'activité logistique.

### 2.1 Barre de KPI (5 indicateurs)

| KPI | Signification |
|-----|---------------|
| Clients actifs | Nombre de clients non archivés |
| Véhicules disponibles | Flotte avec statut "disponible" |
| Commandes en attente | Commandes à planifier |
| Livraisons du jour | Commandes livrées/complétées aujourd'hui |
| Taux de ponctualité | % livraisons dans les créneaux (30 derniers jours) |

### 2.2 Graphiques Matplotlib

- **Distances par algorithme** : comparaison des 10 dernières runs
- **Évolution quotidienne** : distance + coût sur les 7 derniers jours

### 2.3 Mini-météo

Bandeau 48px avec les conditions actuelles (température, pluie, vent) depuis OpenWeatherMap — utilise les coordonnées du premier dépôt. Nécessite une clé OWM configurée.

### 2.4 Alertes documents

Bandeau rouge/orange si des véhicules ont une assurance ou un contrôle technique expirant dans ≤ 30 jours.

### 2.5 Tableau des dernières runs

10 dernières optimisations avec : date, algorithme, distance (km), coût (€), clients servis, respect horaires (%), source distance.

Double-clic sur une ligne → navigation vers la page concernée.

### 2.6 Anomalies

Si des anomalies statistiques sont détectées sur l'historique (Z-score / IsolationForest), un bandeau s'affiche avec un lien vers les commandes concernées.

---

## 3. Clients (page 1)

Gestion de tous les points de livraison.

### 3.1 Vue tableau

- Table paginée **100 lignes / page** avec navigation bas de page
- Colonnes : ID, Nom, Entreprise, Tél, Demande kg, Créneaux, Priorité ★, Tags, Statut, Actions
- **Priorité** : ★★★★★ = priorité 1 (urgent) → ★☆☆☆☆ = priorité 5 (basse)
- **SearchBar** : filtre instantané sur nom, entreprise, téléphone, tags (debounce 300ms)
- **Filtres avancés** (panneau collapsible) : type de client, priorité, tag texte

### 3.2 Ajouter / modifier un client

Bouton **+ Ajouter** ou double-clic sur une ligne → dialogue 5 onglets :

| Onglet | Champs |
|--------|--------|
| **Général** | Nom*, entreprise, type (supermarché/pharmacie/bureau/…), statut, tags |
| **Adresse** | Adresse, latitude/longitude, bouton 🔍 Géocoder (Nominatim), minimap Leaflet |
| **Livraison** | Demande kg, demande m³, temps de service (min), créneau 1 (HH:MM→HH:MM), créneau 2 optionnel, classe ADR, exigence véhicule, ponctualité, pénalité €/h |
| **Contact** | Contact, téléphone, email, notes, chauffeur préféré |
| **Historique** | 10 dernières commandes de ce client |

> Le bouton **Géocoder** convertit l'adresse en coordonnées via Nominatim (1 req/s — ne pas cliquer plusieurs fois rapidement).

### 3.3 Actions sur un client

| Bouton | Action |
|--------|--------|
| ✏ | Ouvrir la fiche de modification |
| 🗺 | Voir ce client sur la carte Leaflet |
| 🗑 | Archiver le client (soft delete — récupérable) |

### 3.4 Importer des clients (CSV / Excel)

1. Bouton **Importer** → sélectionner le fichier `.csv`, `.xls` ou `.xlsx`
2. Fenêtre de mapping : aperçu 5 lignes + association de chaque colonne du fichier avec le champ CityPulse
3. Option **Géocoder les adresses** : remplit lat/lon automatiquement (lent, 1 req/s)
4. Cliquer **Importer** → rapport final (créés / mis à jour / erreurs)

Colonnes reconnues automatiquement : `name`, `latitude`, `longitude`, `demand_kg`, `ready_time`, `due_time`, `service_time`, `address`, `phone`, `email`, `priority`, `tags`, et leurs variantes en français/anglais.

### 3.5 Exporter des clients

Bouton **Exporter** → choisir le format :
- **CSV** : toujours disponible
- **Excel (.xlsx)** : requiert openpyxl
- **JSON** : dump complet

### 3.6 Vue Carte clients

Bouton **🗺 Vue Carte** → dialogue 820×620 avec tous les clients sur Leaflet. Marqueurs colorés par type. Cliquer **Fermer** pour revenir.

### 3.7 Détection d'anomalies

Bouton **⚠ Anomalies** → analyse Z-score sur demande kg, temps de service, coordonnées et créneaux. Les clients anormaux sont listés avec une suggestion.

---

## 4. Véhicules (page 2)

Gestion de la flotte.

### 4.1 Vue tableau

9 colonnes : Immat., Marque, Type, Chauffeur assigné, Capacité kg, CO₂ g/km, Statut (badge coloré), Docs, Actions.

**Bandeau alertes** en haut : assurance ou contrôle technique expirant dans ≤ 30 jours.

**KPI bar** : Total / Disponibles / En service / Maintenance.

**Colonne Docs** :
- ✓ vert : aucune alerte
- ⚠ orange : document expirant dans l'année
- ✗ rouge : document expiré

### 4.2 Fiche véhicule (7 onglets)

| Onglet | Contenu |
|--------|---------|
| **Identité** | Immatriculation*, marque, modèle, année, type (fourgon/camion/vélo/…), motorisation, photo |
| **Capacités** | Capacité kg, m³, palettes, hauteur/largeur/longueur cm, CO₂ g/km, autorisé ADR, autorisé ZFE |
| **Vitesses** | Autoroute, nationale, urbaine, zone 30 (km/h) |
| **Coûts** | €/km, €/h, coût fixe journalier, coût non-utilisation |
| **Chauffeur** | Sélectionner le chauffeur assigné, horaires d'ouverture, rechargement autorisé |
| **Documents** | N° assurance, date expiration assurance, date contrôle technique + alertes live |
| **Dispo & Stats** | Dépôt d'attache, planning hebdomadaire (7 cases), statistiques km/tours/coût |

### 4.3 Calendrier d'indisponibilités

Bouton 📅 dans les actions → grille mensuelle. Clic sur une date → marquer comme indisponible (raison optionnelle). Les jours avec tournée confirmée apparaissent en orange.

### 4.4 Statuts véhicule

| Statut | Badge |
|--------|-------|
| disponible | Vert |
| en service / en tournée | Bleu |
| maintenance | Orange |
| hors service | Rouge |

### 4.5 Stats flotte

Bouton **📊 Stats flotte** → dialogue avec 4 KPICards + camembert Matplotlib par statut.

---

## 5. Chauffeurs (page 3)

Gestion des chauffeurs, indisponibilités, équipes et performances.

### 5.1 Onglet Chauffeurs

Tableau 9 colonnes : Photo (rond 36px), Nom, Permis/Catégorie, Qualifications, Véhicule assigné, Équipe, Statut, Expiration permis, Actions.

**Qualifications affichées** : ADR, CACES, FCO, FIMO, HAZMAT, Permis poids lourd.

**Bandeau alertes** : permis expirant dans ≤ 30 jours → liste rouge/orange.

#### Fiche chauffeur (5 onglets)

| Onglet | Contenu |
|--------|---------|
| **Personnel** | Photo (browse .png/.jpg/.jpeg/.webp/.bmp), prénom*, nom*, date naissance, type contrat |
| **Permis & Qualifs** | N° permis, catégorie (B/C/C1/CE/D…), date expiration + alerte live, checkboxes ADR/CACES/FCO/FIMO/HAZMAT/Permis poids lourd |
| **Horaires** | Plage travail (HH:MM→HH:MM), pause déjeuner (heure + durée), max heures/jour, heures supplémentaires (taux niveau 1 et 2) |
| **RSE** | Durée max conduite avant pause (min), durée pause minimum (min), repos journalier minimum (min) — réglementation CE 561/2006 |
| **Affectation** | Dépôt, véhicule (tous statuts, triés disponibles en premier), zone, stats (tournées, km, retard moyen) |

#### Bouton "Compte web"

Crée ou met à jour un compte sur le portail web pour que le chauffeur accède à ses tournées via navigateur/mobile. Un dialogue affiche l'identifiant et le mot de passe généré.

### 5.2 Onglet Indisponibilités

1. Sélectionner le chauffeur dans le QComboBox
2. Naviguer au mois avec ◀/▶
3. Cliquer sur une date → marquer absent (raison + notes)
4. Si une tournée est planifiée ce jour → suggestion de remplacement automatique

Les cellules sont colorées : rouge = indisponible, orange = tournée planifiée.

### 5.3 Onglet Équipes

- Gauche : liste des équipes + bouton **+ Nouvelle équipe**
- Droite : nom de l'équipe, manager (QComboBox), membres
- Boutons **Ajouter →** / **← Retirer** pour gérer les membres

### 5.4 Onglet Performance

- Filtres : chauffeur + période (date De/À) + bouton Actualiser
- Tableau : tournées, km total, km moyen/tour, retard moyen, taux ponctualité
- Graphique Matplotlib barres km par chauffeur
- Export CSV

---

## 6. Dépôts (page 4)

Gestion des centres de distribution (point de départ des tournées).

### 6.1 Tableau

8 colonnes : Nom, Adresse, Responsable, Horaires, Quais, Capacité kg, Rayon km, Actions.

### 6.2 Fiche dépôt (3 onglets)

| Onglet | Contenu |
|--------|---------|
| **Infos** | Nom*, adresse, responsable, téléphone, lat/lon + 🔍 Géocoder, horaires ouverture/fermeture, nombre de quais, capacité de stockage, notes |
| **Carte** | Rayon de couverture (km) + minimap Leaflet interactive — cercle de couverture visible |
| **Stats** | Véhicules attachés, clients actifs dans le rayon, tournées optimisées |

### 6.3 Vue Carte globale

Bouton **🗺 Vue Carte globale** → tous les dépôts sur une seule carte Leaflet avec cercles de couverture et légende.

> Au moins un dépôt avec des coordonnées valides est obligatoire pour lancer l'optimisation.

---

## 7. Commandes (page 5)

Gestion des commandes de livraison et de collecte.

### 7.1 Vue tableau

**5 KPICards** en haut : En attente / Assignées / En cours / Livrées (aujourd'hui) / Échecs.

Table paginée **80 lignes / page** — colonnes : Réf., Client, Type, Statut (badge), Date prévue, kg, ADR, Priorité ★, Actions.

**Statuts des commandes** :

| Statut | Badge | Signification |
|--------|-------|---------------|
| En attente | Orange | Pas encore planifiée |
| Assignée | Bleu | Incluse dans un plan confirmé |
| En cours | Bleu | En cours de livraison (chauffeur sur route) |
| Livrée | Vert | Confirmée livrée |
| Échec | Rouge | Livraison échouée |
| Annulée | Rouge | Annulée manuellement |

### 7.2 Créer / modifier une commande

Bouton **+ Nouvelle commande** ou double-clic → dialogue 4 onglets :

| Onglet | Contenu |
|--------|---------|
| **Commande** | Référence auto (`ORD-YYYYMMDD-NNNN`), client (cherchable), type (livraison/collecte/échange/retour), statut, date prévue, priorité |
| **Marchandises** | kg, m³, unités, catégorie, température (ambiant/réfrigéré/surgelé), classe ADR, valeur déclarée |
| **Créneaux** | Créneau 1 (obligatoire HH:MM→HH:MM), créneau 2 optionnel, durée visite (min), instructions, code accès |
| **Assignation** | Véhicule (cherchable), chauffeur (cherchable) — vérification automatique ADR/température |

### 7.3 Actions par commande

- **📄 BL** : générer le bon de livraison PDF
- **✏** : modifier
- **🗑** : archiver

### 7.4 Actions en lot

Cocher plusieurs commandes → barre d'actions en lot :
- **Marquer livrées** → status = `delivered`
- **Réassigner** → choisir nouveau véhicule + chauffeur
- **Archiver** → soft delete

### 7.5 Commandes récurrentes

Bouton **📅 Récurrents** → gérer les templates :
- Nom du template, client, type de récurrence (quotidien/hebdomadaire/mensuel)
- Jours actifs (case à cocher Lun→Dim)
- Créneaux, poids, volume
- Bouton **Générer pour la semaine** → crée les commandes de la semaine courante depuis les templates actifs

### 7.6 Import / Export

- **📥 Importer** → CSV ou Excel avec mapping des colonnes
- **📤 Exporter** → CSV ou Excel (openpyxl)

---

## 8. Transporteurs (page 6)

Gestion de la sous-traitance logistique.

### 8.1 Onglet Transporteurs

Table : Nom, Contact, Zones, Types véhicules, €/km, Note ★, Ponctualité %, API connectée, Actions.

#### Fiche transporteur (3 onglets)

| Onglet | Contenu |
|--------|---------|
| **Infos** | Nom*, contact, téléphone, email, site web, notes |
| **Capacités & Tarifs** | Zones desservies (tags), types de véhicules acceptés (9 checkboxes), coût/km, coût/kg, coût fixe |
| **Performance** | Note ★/☆ (1-5 étoiles, modifiable), ponctualité %, URL API tracking, clé API (stockée dans keyring) |

### 8.2 Onglet Expéditions

Suivi des commandes confiées aux transporteurs.

- Filtre par transporteur
- Bouton **🔄 Rafraîchir statuts** → appelle l'API tracking du transporteur (QThread)
- Table : N° tracking, commande, transporteur, statut, livraison estimée, coût, actions

### 8.3 Onglet Simulation (flotte propre vs sous-traitance)

1. Sélectionner des commandes en attente dans la table (sélection multiple)
2. Cliquer **Lancer la simulation**
3. Dans le dialogue :
   - Sélectionner le transporteur à comparer
   - 3 KPICards : Coût flotte propre / Coût transporteur / Économie estimée
   - Tableau comparatif commande par commande
   - Recommandation colorée + camembert Matplotlib

### 8.4 Onglet Évaluation

- Filtres période
- Tableau : taux livraison %, coût total, ponctualité, note
- Graphique Matplotlib double barre (coût + note)
- Export **Excel** et **PDF**

---

## 9. Optimisation (page 7)

Cœur du système — calcul des tournées VRP et confirmation du plan.

### 9.1 Panneau de configuration (gauche)

#### Section Données

- Labels : nombre de clients / véhicules / dépôts chargés
- **QDateEdit** : date de la tournée à planifier
- Bouton **Actualiser** : recharge les données depuis la base

#### Section Algorithmes

Cocher un ou plusieurs algorithmes à comparer :

| Algorithme | Description | Durée |
|-----------|-------------|-------|
| **Greedy** | Voisin le plus proche — rapide, solution de référence | < 1s |
| **2-opt** | Amélioration locale — meilleur que Greedy | quelques secondes |
| **OR-Tools** | Solveur VRPTW exact Google — optimal | 5 à 300s |

#### Section Mode VRP

| Mode | Usage |
|------|-------|
| Standard | Un seul dépôt, retour obligatoire |
| Multi-dépôts | Plusieurs dépôts, chaque véhicule part de son dépôt |
| Open (sans retour) | Les véhicules ne reviennent pas au dépôt |
| Pickup & Delivery | Contraintes de ramasse + livraison, même véhicule |
| Rechargement | Les véhicules peuvent se recharger en cours de route |

#### Section Objectif

- Minimiser distance
- Minimiser coût
- Minimiser retards
- **Équilibré** (pondéré) : 4 sliders distance/coût/CO₂/respect

#### Section Options avancées

- Clustering KMeans (pré-segmentation géographique, recommandé ≥ 20 clients)
- Trafic automatique (heure courante + type de jour → coefficient)
- Pauses RSE (réglementation CE 561/2006)
- Compétences ADR / ZFE
- Fenêtres horaires
- Pause déjeuner 12h-14h
- Séquences forcées (lire depuis tournées verrouillées)

#### Section Météo / Trafic

| Réglage météo | Coefficient |
|--------------|-------------|
| ☀ Ensoleillé | ×1.0 |
| 🌧 Pluie | ×1.1 |
| ⛈ Orage | ×1.25 |
| ❄ Neige/Verglas | ×1.6 |

Bouton **Auto** : calcule le coefficient depuis la date/heure sélectionnée (traffic_adjuster).

#### Boutons de lancement

- **🚀 Lancer l'optimisation** (principal)
- **⏹ Arrêter** (visible pendant le calcul)
- **📅 Planifier la semaine** → mode hebdomadaire

### 9.2 Panneau de résultats (droite — 5 onglets)

#### Onglet 📊 Comparaison

Tableau 4 colonnes (Métrique | Greedy | 2-opt | OR-Tools) mis à jour en temps réel pendant les calculs. La meilleure valeur par ligne est surlignée en vert+gras.

Métriques affichées : distance totale (km), durée totale (min), coût total (€), clients servis, respect horaires (%), retard moyen (min), CO₂ total (kg), temps CPU (ms), gain vs Greedy (%), utilisation flotte (%).

Bandeau **🏆 Meilleur algorithme** avec le verdict après le dernier run.

#### Onglet 🚗 Détail véhicules

- QComboBox pour sélectionner l'algorithme à inspecter
- QTreeWidget : un nœud par véhicule → arrêts avec heure d'arrivée, client, km depuis l'arrêt précédent
- Actions par véhicule :
  - 🔒 **Verrouiller** → les arrêts de ce véhicule seront des séquences forcées au prochain run
  - 📋 **Manifeste** → PDF liste de chargement
  - 📄 **CMR** → document de transport

#### Onglet 📈 Graphiques

3 graphiques Matplotlib sur fond sombre :
- **Radar** : distance / coût / respect / CO₂ (comparaison des 3 algos)
- **Histogramme** : distribution des distances par véhicule
- **Camembert** : taux d'utilisation de la flotte

#### Onglet 💰 Simulation coûts

3 sliders : prix carburant (€/L), péages (%), taux horaire (€/h).

Recalcul immédiat → tableau : Carburant / Main d'œuvre / Fixe / Péages / CO₂ / **TOTAL** par algorithme.

#### Onglet ⚠ Conformité RSE/ADR/ZFE

3 panneaux (RSE, ADR, ZFE) avec statut ✅/❌, liste des violations détaillées et bouton **🔧 Suggestions**.

### 9.3 Barre post-run

Après le calcul, une barre d'actions apparaît :

| Bouton | Action |
|--------|--------|
| ✅ Confirmer le plan | Persiste le meilleur algorithme en base + synchro web |
| 🗺 Carte | Navigation vers la page Carte |
| 📍 Suivi | Navigation vers le Gantt |
| 📁 Scénario | Sauvegarder comme scénario |
| 📄 PDF | Rapport de comparaison PDF |
| 📤 CSV | Tableau de comparaison en CSV |

### 9.4 Confirmer le plan

Après **✅ Confirmer le plan** (confirmation QMessageBox) :

1. Routes et arrêts inscrits en base (`routes` + `route_stops`)
2. Commandes des clients routés passées en statut **Assignée** avec `vehicle_id` + `driver_id`
3. Calendriers véhicules bloqués pour ce jour
4. Notification créée dans la cloche
5. **Synchro automatique portail web** : tournées envoyées aux chauffeurs + statut/ETA envoyé aux clients

Le bouton est désactivé après confirmation pour éviter les doublons.

### 9.5 Planifier la semaine

Bouton **📅 Planifier la semaine** :

1. Choisir la date de début et le nombre de jours (1-14)
2. Choisir la stratégie :
   - **Distribuer automatiquement** : répartit toutes les commandes pending par priorité décroissante
   - **Respecter les dates prévues** : planifie chaque commande selon sa date `scheduled_date`
3. Cliquer **Analyser** → tableau récapitulatif jour par jour
4. Double-clic sur un jour → popup détail 4 onglets (résumé, véhicules, commandes, conformité)
5. Cliquer **✅ Valider** → même effet que "Confirmer le plan" pour chaque jour

---

## 10. Carte (page 8)

Visualisation cartographique Leaflet.

### 10.1 Contenu de la carte

- **Dépôts** : marqueurs avec popup (nom, adresse, horaires)
- **Clients** : marqueurs colorés par véhicule assigné, popup au clic (nom, demande, créneau, statut)
- **Routes** : polylignes colorées par véhicule
- **Zones GeoJSON** : ZFE (zone faibles émissions), zones livraison, zones exclusion — calques activables
- **Bannière météo** en haut si OWM configuré

### 10.2 Fond de carte

Sélectionner dans **Paramètres → Carte** ou via le menu de la carte :

| Fond | Source |
|------|--------|
| Standard | OpenStreetMap |
| Dark | CartoDB Dark Matter |
| Satellite | Esri World Imagery |
| Terrain | Stamen Terrain |

### 10.3 Géocodage d'adresse

Champ de recherche en haut → saisir une adresse → la carte se centre dessus.

### 10.4 Comparaison split scénarios

Depuis la page **Scénarios** → bouton **Comparer sur la carte** → la carte s'affiche en mode split : routes du scénario A à gauche, scénario B à droite.

---

## 11. Suivi en temps réel (page 9)

Gantt interactif et simulation des tournées confirmées.

### 11.1 Barre de simulation

| Contrôle | Action |
|----------|--------|
| ▶ | Démarrer la simulation (avance d'1 minute par seconde réelle) |
| ⏸ | Pause / Reprendre |
| ⏹ | Réinitialiser à 06:00 |
| ⏩×2 | Vitesse ×2 |
| ⏩⏩×5 | Vitesse ×5 |
| Slider | Sauter directement à une heure (06h → 20h) |
| HH:MM | Heure de simulation courante |

### 11.2 Barre météo / trafic

- QComboBox conditions météo → coefficient appliqué aux durées Gantt
- Bouton **🌤 Météo réelle** → appel OWM en temps réel (lat/lon du 1er dépôt)
- Bouton **Auto** → coefficient calculé depuis l'heure et le type de jour

### 11.3 Barre de sélection journée (mode semaine)

Si plusieurs journées ont été planifiées (planificateur hebdomadaire), une barre apparaît pour naviguer entre les jours. Chaque bouton affiche : date, nombre de commandes, km total, algorithme.

### 11.4 KPICards mini

5 indicateurs : Véhicules actifs / Livraisons planifiées / En retard / Km total / CO₂ (kg).

### 11.5 Gantt (onglet 📅)

Diagramme de Gantt dessiné au QPainter — plage 06:00 → 20:00.

**Types de blocs** :

| Couleur | Type |
|---------|------|
| Bleu | Trajet |
| Vert | Visite client |
| Gris | Pause RSE |
| Orange | Rechargement |
| Rouge hachuré | Retard |
| Violet | Arrêt verrouillé |

**Interactions** :

| Action | Résultat |
|--------|---------|
| Survol bloc | Tooltip : type, heure début, durée, client |
| Clic droit → Détails | Informations complètes |
| Clic droit → Annuler arrêt | Supprime l'arrêt + bandeau re-optimisation |
| Clic droit → Réaffecter | Déplacer vers un autre véhicule |
| Clic droit → Verrouiller | Bloc violet — figé pour le prochain run |
| Drag & drop d'un bloc | Déplacer dans le temps (confirmation avant validation) |
| Ctrl+Z | Annuler le dernier déplacement (pile 20 entrées) |
| Ctrl + molette | Zoom horizontal (×0.5 à ×8) |
| Molette seule | Scroll horizontal |

**Ligne rouge** : heure de simulation courante avec triangle indicateur.

### 11.6 Tableau live (onglet 📋)

Mise à jour toutes les secondes pendant la simulation :

| Colonne | Contenu |
|---------|---------|
| Véhicule | Immatriculation |
| Arrêt actuel | Nom du client en cours |
| Statut | En route / En visite / Pause / Terminé |
| Avance/Retard | Minutes (+ = avance, - = retard) |
| Progression | Barre % arrêts complétés |

### 11.7 Panneau Incidents (droite)

- Notifications non lues depuis la table `notifications`
- Bouton **+ Signaler incident** → dialogue (type, immatriculation, description) → INSERT en base
- Bandeau re-optimisation après annulation d'arrêt → bouton **🔄 Re-optimiser**

### 11.8 Rapport PDF / CSV

- **📄 Rapport PDF** → rapport de la journée sélectionnée (ou de la semaine en mode hebdo)
- **📤 CSV** → export de toutes les tournées affichées

### 11.9 Synchro web automatique

Un timer invisible (60 secondes) récupère les confirmations de livraison depuis le portail web et met à jour les statuts des commandes dans le desktop. Aucune action manuelle requise.

---

## 12. Scénarios (page 10)

Sauvegarder et comparer des configurations d'optimisation.

### 12.1 Vue tableau / détail

Splitter horizontal 70/30 :
- **Gauche** : tableau des scénarios 8 colonnes (Nom, Clients, Véhicules, Algo, Date, Distance, Coût, Tags)
- **Droite** : panneau détail — infos, éditeur Tags, éditeur Description

### 12.2 Deux sources de scénarios

| Source | Comment sauvegarder |
|--------|---------------------|
| **Snapshot données** | Page Scénarios → bouton **💾 Sauvegarder l'état actuel** — capture clients + véhicules + dépôts |
| **Résultat optimisation** | Page Optimisation → bouton **📁 Scénario** après un run — capture le résultat VRP |

### 12.3 Actions

- **Restaurer** (orange) : recharge les données du scénario dans l'application (confirmation requise)
- **Suppr.** : suppression définitive

### 12.4 Comparer deux scénarios

1. Sélectionner le scénario A dans le premier QComboBox
2. Sélectionner le scénario B dans le second
3. Bouton **Comparer** → tableau de différences + graphique barres Matplotlib
4. Bouton **🗺 Voir sur la carte** → carte en mode split

### 12.5 Analyse What-If

Section en dessous du splitter : modifier un paramètre (nb véhicules, trafic, météo) et voir l'impact estimé sur la distance et le coût.

### 12.6 Import / Export JSON

- **Exporter JSON** : télécharger le scénario sélectionné en `.json`
- **Importer JSON** : charger un scénario depuis un fichier partagé

---

## 13. Traduction (page 11)

Traduction de textes logistiques avec glossaire métier et score de qualité.

### 13.1 Traduire un texte

1. Sélectionner la langue source (FR / EN / AR / ES / DE)
2. Sélectionner la langue cible
3. Saisir le texte dans la zone gauche
4. Cliquer **Traduire**

**Ordre de priorité** :
1. Glossaire utilisateur (termes exacts mémorisés)
2. Glossaire métier intégré (500+ termes logistiques)
3. API Mistral AI (traduction contextuelle)
4. deep-translator (fallback)

La méthode utilisée est affichée : 🌐 API / 🤖 Mistral / 📖 Hors-ligne.

### 13.2 Score BLEU

Après chaque traduction, un score BLEU-1 (0.0 → 1.0) est calculé et affiché. Score > 0.7 = traduction de bonne qualité.

### 13.3 Valider et mémoriser

Si la traduction est incorrecte :
1. Corriger dans le champ de droite
2. Cliquer **Valider** → ajout au glossaire + ✓ dans l'historique

### 13.4 Historique

Tableau : texte source, traduction, langues, méthode, score BLEU, validée (✓/—).

- Case **Validées uniquement** : filtrer l'historique
- Double-clic sur une ligne → re-remplir les champs

### 13.5 Onglet Glossaire

CRUD complet sur les paires source→cible mémorisées :
- Recherche par texte
- Compteur d'utilisations
- Suppression

---

## 14. Rapports (page 12)

Génération de documents PDF, Excel et JSON.

### 14.1 Structure

Splitter gauche (liste catégories) / droite (formulaire + aperçu).

**Langue du rapport** : sélecteur FR / EN / ES / DE / AR — indépendant de la langue de l'interface.

### 14.2 Catégories de rapports

#### Opérationnels

| Rapport | Description |
|---------|-------------|
| Roadbook chauffeur | PDF par tournée : arrêts + QR code par arrêt + carte |
| Rapport journalier flotte | Toutes les routes d'une journée + graphique km par véhicule |

#### Analytiques

| Rapport | Description |
|---------|-------------|
| KPI période | Évolution quotidienne + comparaison avec la période précédente |
| Comparaison algorithmes | Tableau + graphique sur les runs sélectionnées |

#### Clients

Fiche client individuelle : informations + 30 dernières commandes.

#### Transporteurs

Synthèse un ou tous les transporteurs : expéditions, taux livraison, coûts, note.

#### Conformité

| Rapport | Description |
|---------|-------------|
| RSE | Durées conduite par chauffeur vs réglementation CE 561/2006 |
| Performances chauffeurs | Km, tournées, retards, ponctualité par chauffeur |

#### Documents légaux

| Document | Usage |
|----------|-------|
| **Bon de livraison (BL)** | Accompagne la livraison : expéditeur, destinataire, quantités, signature |
| **CMR** | Document de transport international (cases 1-3, 6, 11-13, 18, 23-24) |
| **Document ADR** | Matières dangereuses : désignation ONU, classe, groupe emballage |
| **Manifeste de chargement** | Liste de chargement véhicule : arrêts, poids, volume, taux remplissage |
| **CGU** | Notice légale de l'entreprise |

#### Exports

Export complet multi-tables Excel (.xlsx) ou snapshot JSON de toute la base.

### 14.3 Aperçu intégré

Chaque catégorie possède son propre panneau d'aperçu :
- **PDF** : visualisé nativement avec QPdfView (ou QWebEngineView en fallback)
- **Excel** : converti en tableau HTML et affiché dans QWebEngineView
- Double-clic dans l'historique → recharger l'aperçu d'un rapport précédent

### 14.4 Planification automatique

Option cochable → heure configurée → génère automatiquement le rapport KPI journalier dans le dossier de sortie configuré.

---

## 15. Journal (page 13)

Audit trail complet de toutes les actions effectuées dans l'application.

### 15.1 Filtre par défaut

30 derniers jours. Modifier avec les sélecteurs de date De/À.

### 15.2 Colonnes

Date/Heure | Utilisateur | Action | Détails

### 15.3 Actions loggées (exemples)

- `LOGIN` / `LOGOUT`
- `CLIENT_CREATE` / `CLIENT_UPDATE` / `CLIENT_ARCHIVE`
- `OPTIMIZATION` (algo, distance, clients)
- `PLAN_CONFIRMED` (date, routes, arrêts, commandes)
- `WEB_SYNC_CONFIRMATIONS` (mises à jour depuis le portail)
- `REPORT_GENERATED`
- `SETTINGS_SAVED`

### 15.4 Export CSV

Bouton **📤 Exporter CSV** → fichier avec toutes les entrées filtrées.

---

## 16. Notifications (page 14)

Centre de notifications in-app.

### 16.1 Filtres

- Type (plan, optimisation, alerte, incident, synchro web, …)
- Sévérité (info, warning, danger)
- Non lus seulement (case à cocher)
- Recherche texte libre

### 16.2 Liste + détail

Splitter : liste à gauche, panneau détail 280px à droite. Clic sur une notification → affiche le message complet et les liens de navigation.

Les liens `citypulse://nav/N` dans les messages naviguent directement vers la page N.

### 16.3 Types de notifications créées automatiquement

| Type | Créateur |
|------|---------|
| Plan confirmé | save_plan() — ✅ Confirmer le plan |
| Synchro web | Timer 60s — confirmations chauffeurs reçues |
| Alerte document | Assurance/CT expirant ≤ 30j |
| Incident | Bouton "+ Signaler incident" dans le Suivi |
| Optimisation | Chaque run algo |

### 16.4 Résumé journalier

Si activé dans **Paramètres → Entreprise → Résumé quotidien**, un résumé s'envoie chaque jour à l'heure configurée.

---

## 17. Paramètres (page 15)

Configuration complète de l'application. Barre **💾 Sauvegarder** fixée en bas — cliquer pour persister les modifications.

### 17.1 Onglet Entreprise

| Paramètre | Description |
|-----------|-------------|
| Nom, adresse, téléphone, email | Apparaissent dans les en-têtes des rapports PDF |
| Devise | MAD / EUR / USD |
| Timezone | Fuseau horaire pour les calculs ETA |
| Logo | Remplace le logo dans les rapports (assets/logo.png) |
| Thème UI | Dark (défaut) / Light |
| **Langue de l'interface** | FR / EN / AR / ES / DE — instantané |
| Clé API Mistral | Stockée dans le keyring OS |
| Modèle Mistral | ex. `mistral-small-latest` |
| Clé OpenWeatherMap | Stockée dans le keyring OS |
| Résumé quotidien notif | Heure d'envoi du résumé journalier |

### 17.2 Onglet Carte

| Paramètre | Description |
|-----------|-------------|
| Fond de carte | Standard / Dark / Satellite / Terrain |
| Latitude / Longitude | Centre par défaut de la carte |
| 📍 Dépôt principal | Centrer sur le premier dépôt |
| Zoom | Niveau de zoom par défaut (1-18) |
| 10 couleurs véhicules | QColorDialog pour chaque véhicule |

### 17.3 Onglet Rapports

| Paramètre | Description |
|-----------|-------------|
| Couleur thème PDF | Couleur principale des en-têtes |
| Texte d'en-tête | Ligne supplémentaire sous le logo |
| Pied de page | Texte bas de page PDF |
| Dossier de sortie | Répertoire par défaut pour l'enregistrement |
| Planification | Tableau des rapports automatiques configurés |

### 17.4 Onglet Utilisateurs (admin uniquement)

- Tableau : Identifiant, Nom, Rôle, Actif
- Bouton **+ Créer utilisateur** → nom, identifiant, mot de passe, rôle
- Modifier : changer mot de passe, rôle, activer/désactiver
- Soft delete : `is_active=0` (l'utilisateur ne peut plus se connecter)

### 17.5 Onglet Sauvegarde

| Action | Description |
|--------|-------------|
| **Exporter snapshot JSON** | Dump complet multi-tables (clients, véhicules, chauffeurs, commandes, routes, …) |
| **Importer snapshot** | Restaurer depuis un snapshot JSON |
| **Réinitialiser données métier** | Vide les tables (confirmation double requise) |
| **Charger données démo** | Raccourci vers le chargeur de datasets |
| **Vérifier intégrité BDD** | `PRAGMA integrity_check` + taille du fichier |
| **URL OSRM** | Champ texte + timeout + bouton **Tester la connexion** |
| **URL portail web Django** | URL du portail + bouton **Tester la connexion** (✅ / ❌) |
| **Clé secrète Django** | Stockée dans le keyring — partagée avec le portail web |

---

## 18. Copilote IA

Dock flottant accessible depuis la sidebar (icône IA) ou avec **Ctrl+Shift+C**.

### 18.1 Chat contextuel

- Saisir une question ou commande → **Entrée** ou bouton Envoyer
- Le copilote reçoit automatiquement des statistiques de la base (clients, routes, KPIs)
- Réponses en FR / EN / AR / ES / DE (configurable dans Paramètres → Entreprise)

**Exemples de questions** :
- "Quel algorithme a donné le meilleur résultat ?"
- "Combien de clients n'ont pas été livrés cette semaine ?"
- "Suggère un plan pour demain"
- "Optimise mes paramètres de trafic"

### 18.2 Chips de suggestions

6 boutons de suggestions rapides sous le champ de saisie — clic → pré-remplit la question.

### 18.3 Commandes IA détectées

Si Mistral détecte une action dans la réponse, un bandeau **Exécuter / Ignorer** s'affiche :

| Commande | Action |
|----------|--------|
| `navigate` | Navigation vers une page de l'app |
| `optimize` | Lancement d'une optimisation |
| `create_order` | Création d'une commande |

### 18.4 Analyse globale

Onglet **Analyse** dans le Copilote → génération d'une analyse longue de l'activité → export PDF.

### 18.5 Historique

Les conversations sont persistées par utilisateur dans la table `ai_conversations`.

---

## 19. Portail web chauffeurs et clients

Interface web accessible depuis n'importe quel navigateur (PC, tablette, mobile).

### 19.1 Chauffeurs

URL : `http://votre-portail/driver/`

| Page | Fonctionnalité |
|------|---------------|
| Mes tournées | Liste des tournées assignées pour aujourd'hui et les jours à venir |
| Détail tournée | Carte Leaflet avec les arrêts, ETA, adresses clientes |
| Confirmation livraison | Bouton **Livré** + possibilité de saisir une raison d'échec |
| Preuve photo | Prise de photo ou upload depuis la galerie |

Quand le chauffeur confirme une livraison → le statut remonte automatiquement dans le desktop (timer 60s page Suivi).

### 19.2 Clients

URL : `http://votre-portail/client/`

| Page | Fonctionnalité |
|------|---------------|
| Mes commandes | Tableau statut de toutes les commandes en cours |
| Détail commande | Statut actuel, nom du chauffeur, ETA estimée |

### 19.3 Suivi public

URL : `http://votre-portail/track/<référence-commande>/`

Accessible sans connexion — affiche le statut et l'ETA de la commande identifiée par sa référence.

### 19.4 Comptes web

Créer un compte web pour un chauffeur ou un client :
- **Page Chauffeurs / Clients** → fiche → bouton **🌐 Créer compte web**
- Un dialogue affiche l'identifiant et le mot de passe généré
- Le compte est immédiatement actif sur le portail

---

## 20. Flux de travail complet

### 20.1 Flux quotidien recommandé

```
Matin
 1. Ouvrir CityPulse → Tableau de bord
    → Vérifier les alertes (docs, retards, anomalies)
    → Consulter les commandes du jour (Page Commandes)

 2. Page Optimisation
    → Sélectionner la date du jour
    → Vérifier clients / véhicules / chauffeurs chargés
    → Choisir algorithmes (recommandé : cocher les 3)
    → [🚀 Lancer l'optimisation]

 3. Analyser les résultats
    → Onglet Comparaison : quel algo est le meilleur ?
    → Onglet Conformité : y a-t-il des violations RSE/ADR/ZFE ?
    → Onglet Détail véhicules : la répartition semble-t-elle raisonnable ?

 4. [✅ Confirmer le plan]
    → Les tournées sont envoyées aux chauffeurs sur le portail web
    → Les clients voient leur ETA sur le portail

Journée
 5. Page Suivi (Gantt)
    → Suivre l'avancement en temps réel
    → Les confirmations de livraison remontent automatiquement
    → En cas d'incident : signaler + re-optimiser si nécessaire

Soir
 6. Page Rapports → Rapport journalier flotte (PDF)
 7. Page Tableau de bord → KPIs du jour
```

### 20.2 Flux hebdomadaire

```
Lundi matin
 1. Page Commandes → vérifier les commandes de la semaine
 2. Page Optimisation → Planifier la semaine
    → Choisir la stratégie (distribuer ou respecter les dates)
    → [Analyser] → vérifier le tableau jour par jour
    → [✅ Valider] → tout est planifié pour la semaine

 En cours de semaine
 3. Page Suivi → sélectionner le jour dans la barre de navigation
 4. Les chauffeurs reçoivent leurs tournées chaque matin

Vendredi soir
 5. Page Rapports → Rapport KPI semaine → comparer avec S-1
 6. Page Scénarios → sauvegarder la configuration si elle a bien fonctionné
```

---

## 21. Bonnes pratiques

### Données

- **Coordonnées clients** : toujours renseigner latitude/longitude (utiliser le bouton Géocoder si l'adresse est connue). Un client avec (0,0) est exclu de l'optimisation.
- **Demande kg** : vérifier que la demande d'un client ne dépasse pas la capacité du plus grand véhicule. Un client avec 1000 kg ne peut pas être livré par un camion de 800 kg.
- **Fenêtres horaires** : `ready_time` doit être < `due_time`. Une fenêtre inversée exclut le client.
- **Archiver plutôt que supprimer** : les clients archivés peuvent être restaurés.

### Véhicules

- Assigner un chauffeur à chaque véhicule (onglet Chauffeur de la fiche) avant d'optimiser.
- Renseigner les qualifications ADR dans la fiche chauffeur si des matières dangereuses sont transportées.
- Marquer les indisponibilités dans le calendrier — les véhicules dont le chauffeur est absent sont exclus automatiquement.

### Optimisation

- Utiliser les **3 algorithmes** la première fois pour un nouveau jeu de données — OR-Tools est généralement le meilleur mais le plus lent.
- Activer la **pré-segmentation KMeans** pour ≥ 20 clients — réduit le temps OR-Tools significativement.
- Vérifier l'onglet **Conformité RSE/ADR/ZFE** avant de confirmer le plan.
- **Verrouiller** les tournées qui fonctionnent bien → elles seront conservées au prochain run.

### Rapports

- Utiliser **BL + CMR** pour les livraisons avec trace légale.
- Générer le **roadbook chauffeur** avec QR codes pour faciliter le scan à chaque arrêt.
- Configurer la **planification automatique** pour recevoir le rapport KPI quotidien sans action manuelle.

---

## 22. FAQ

### Je ne vois pas la carte (tuiles grises)

PyQt6-WebEngine n'est pas installé ou n'est pas dans le bon environnement Python. Vérifier dans `citypulse.log` le message d'erreur exact. Installer avec : `python -m pip install PyQt6-WebEngine`.

### L'optimisation tourne mais ne donne pas de résultat

Vérifier que : (1) au moins un dépôt a des coordonnées valides, (2) des clients sont chargés avec coordonnées non nulles, (3) des véhicules sont disponibles. Le log d'exécution (zone texte en bas de la page Optimisation) indique l'étape échouée.

### OR-Tools ne figure pas dans la liste des algorithmes

OR-Tools n'est pas installé. Lancer `pip install ortools` puis redémarrer l'application.

### Une commande reste "En attente" après confirmation du plan

Deux causes possibles :
- Le client n'était pas inclus dans l'optimisation (coordonnées invalides, demande trop élevée, fenêtre horaire incompatible)
- Le client était dans la tournée mais n'avait aucune commande pending pour cette date

Vérifier la fiche du client et sa demande kg vs la capacité de la flotte.

### Le Copilote répond "Je ne peux pas me connecter"

La clé Mistral AI n'est pas configurée. Aller dans **Paramètres → Entreprise → Clé API Mistral** et saisir la clé (obtenue sur console.mistral.ai).

### La météo n'apparaît pas sur le dashboard

Configurer la clé OpenWeatherMap dans **Paramètres → Entreprise → Clé OpenWeatherMap** et vérifier qu'au moins un dépôt a des coordonnées valides.

### Le portail web ne reçoit pas les tournées

1. Vérifier que l'URL Django est correcte : **Paramètres → Sauvegarde → Tester la connexion** → doit afficher ✅
2. Vérifier que la clé secrète est la même des deux côtés (desktop keyring = variable `.env` du portail)
3. Consulter `citypulse.log` pour les messages `WARNING` de synchro

### Le chauffeur ne peut pas se connecter au portail web

Vérifier que son compte web a été créé (Page Chauffeurs → fiche → bouton **🌐 Créer compte web**). Lui communiquer l'identifiant et le mot de passe affichés dans le dialogue.

### La base de données est lente ou volumineuse

**Paramètres → Sauvegarde → Vérifier intégrité BDD** → affiche la taille. Si > 100 Mo, envisager d'archiver les anciennes données ou d'exporter un snapshot puis réinitialiser.

### Changer la langue de l'interface

**Paramètres → Entreprise → Langue de l'interface** → sélectionner FR/EN/AR/ES/DE → **💾 Sauvegarder**. Changement immédiat, sans redémarrage.

### Les rapports s'affichent en français même après changement de langue

La langue de l'interface et la langue des rapports sont indépendantes. Changer le sélecteur **Langue du rapport** dans la Page Rapports (panneau gauche).

---

*CityPulse Logistics v5.41 — ENSAM Meknès 2025-2026*  
*Guide déploiement : `README_DEPLOYMENT.md` · Guide technique : `README.md`*
