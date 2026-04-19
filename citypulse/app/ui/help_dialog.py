"""
Dialogue d'aide contextuelle pour chaque page de CityPulse.

Chaque page appelle  show_help(parent, PAGE_KEY)  pour ouvrir un guide
d'utilisation adapté au contexte.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextBrowser, QPushButton, QFrame,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt


# ═══════════════════════════════════════════════════════════════════
#  Contenu d'aide — rédigé avec une vraie expertise logistique VRP
# ═══════════════════════════════════════════════════════════════════

HELP_CONTENT: dict[str, dict] = {

    # ── Guide complet ─────────────────────────────────────────────
    "guide": {
        "title": "Guide Complet — CityPulse Logistics",
        "body": """
<h2>CityPulse Logistics — Guide d'utilisation complet</h2>

<hr>
<h3>1. Présentation générale</h3>
<p><b>CityPulse Logistics</b> est une application desktop d'optimisation
de tournées de véhicules (<i>Vehicle Routing Problem — VRP</i>) avec
fenêtres de temps. Elle permet de planifier, optimiser et suivre les
livraisons d'une flotte logistique.</p>

<p><b>Fonctionnalités principales :</b></p>
<ul>
<li>Gestion des clients, véhicules et dépôts</li>
<li>Import/export de données (CSV et Excel XLS/XLSX)</li>
<li>3 algorithmes d'optimisation (Glouton, 2-opt, OR-Tools)</li>
<li>Carte interactive avec itinéraires</li>
<li>Suivi en temps réel des livraisons</li>
<li>Sauvegarde/restauration de scénarios</li>
<li>Traduction multilingue (FR, EN, AR, ES, DE)</li>
<li>Rapports exportables (CSV, TXT, JSON, PDF)</li>
<li>Journal complet des opérations</li>
</ul>

<hr>
<h3>2. Démarrage rapide (5 étapes)</h3>
<table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background-color:#f0f0f0;">
    <td><b>Étape</b></td><td><b>Page</b></td><td><b>Action</b></td></tr>
<tr><td>1</td><td>Clients</td>
    <td>Importez vos clients via <b>Importer</b> (CSV ou Excel) ou ajoutez-les
        manuellement. Vérifiez les coordonnées GPS.</td></tr>
<tr><td>2</td><td>Véhicules</td>
    <td>Déclarez votre flotte : immatriculation, capacité kg/m³,
        vitesse, coût/km. Statut = <i>disponible</i>.</td></tr>
<tr><td>3</td><td>Dépôts</td>
    <td>Configurez au moins un dépôt (point de départ des tournées)
        avec ses coordonnées et horaires d'ouverture.</td></tr>
<tr><td>4</td><td>Optimisation</td>
    <td>Cliquez sur <b>Comparer les 3</b> pour lancer les 3 algorithmes
        et voir lequel donne le meilleur résultat.</td></tr>
<tr><td>5</td><td>Carte / Dashboard</td>
    <td>Visualisez les itinéraires sur la carte et consultez les KPI
        sur le dashboard.</td></tr>
</table>

<hr>
<h3>3. Import de données — Formats supportés</h3>

<h4>3.1 Fichiers CSV</h4>
<p>Le format CSV est détecté automatiquement. Formats acceptés :</p>
<ul>
<li><b>Format CityPulse</b> : colonnes <code>name, latitude, longitude,
    demand_kg, ready_time, due_time, service_time, priority, client_type</code></li>
<li><b>Format Solomon (VRPTW)</b> : colonnes <code>CUST NO., XCOORD., YCOORD.,
    DEMAND, READY TIME, DUE DATE, SERVICE TIME</code> — les coordonnées X/Y
    sont converties automatiquement en lat/lon.</li>
</ul>

<h4>3.2 Fichiers Excel (XLS / XLSX) — NOUVEAU</h4>
<p>Vous pouvez maintenant importer directement des fichiers Excel.
Les en-têtes de colonnes sont détectés automatiquement :</p>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background-color:#f0f0f0;">
    <td><b>Données</b></td><td><b>Colonnes reconnues</b></td></tr>
<tr><td>Clients</td>
    <td><code>CUSTOMER_CODE</code>, <code>LATITUDE</code>, <code>LONGITUDE</code>,
        <code>DEMAND_KG</code> / <code>QUANTITY_KG</code>,
        <code>READY_TIME</code> / <code>TIME_FROM</code>,
        <code>DUE_TIME</code> / <code>TIME_TO</code>,
        <code>SERVICE_TIME</code> / <code>UNLOADING_TIME_MIN</code></td></tr>
<tr><td>Véhicules</td>
    <td><code>VEHICLE_CODE</code>, <code>VEHICLE_TYPE</code>,
        <code>CAPACITY_WEIGHT_KG</code>, <code>CAPACITY_VOLUME_M3</code>,
        <code>MAX_SPEED_KMH</code>, <code>COST_PER_KM</code> / <code>VARIABLE_COST_KM</code>,
        <code>DRIVER_NAME</code></td></tr>
</table>
<p><b>Astuce</b> : les fichiers <code>2_detail_table_customers.xls</code>,
<code>3_detail_table_vehicles.xls</code> du dataset réel sont directement
importables via le bouton Importer.</p>

<hr>
<h3>4. Pages de l'application</h3>

<h4>4.1 Dashboard</h4>
<p>Tableau de bord avec 6 KPI temps réel (distance, coût, livraisons,
retard, respect horaire, utilisation flotte) et 4 graphiques
(comparaison algorithmes, convergence, répartition, scalabilité CPU).
Les données se remplissent après avoir lancé une optimisation.</p>

<h4>4.2 Gestion des Clients</h4>
<p>Table éditable type Excel : double-cliquez sur une cellule pour la
modifier directement. Les modifications sont sauvegardées automatiquement
en base de données. La barre de formule en haut affiche la référence
de la cellule sélectionnée et son contenu.</p>
<ul>
<li><b>Rechercher</b> : filtre instantané par texte</li>
<li><b>Filtre type</b> : Standard / Prioritaire / Occasionnel</li>
<li><b>Actions</b> : Edit (dialogue), Suppr (archive), Dupl (copie)</li>
</ul>

<h4>4.3 Gestion des Véhicules</h4>
<p>Même fonctionnement que les clients : table éditable, import
CSV/Excel, recherche, filtre par type, actions (Edit, Suppr, Dupl).</p>
<p><b>Important</b> : seuls les véhicules avec le statut <i>disponible</i>
sont pris en compte par l'optimiseur.</p>

<h4>4.4 Gestion des Dépôts</h4>
<p>Configurez vos entrepôts. Le dépôt principal (ID 1) ne peut pas
être supprimé. Chaque véhicule part du dépôt et y revient.</p>

<h4>4.5 Optimisation IA</h4>
<p>Le cœur de l'application. Trois algorithmes disponibles :</p>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background-color:#f0f0f0;">
    <td><b>Algorithme</b></td><td><b>Vitesse</b></td><td><b>Qualité</b></td></tr>
<tr><td>Glouton (Greedy)</td><td>Ultra-rapide (&lt; 1s)</td><td>Baseline</td></tr>
<tr><td>2-opt local search</td><td>Rapide (1-5s)</td><td>5 à 15% mieux</td></tr>
<tr><td>OR-Tools (Google)</td><td>Variable (5-120s)</td><td>Optimal ou quasi-optimal</td></tr>
</table>
<p>Paramètres : coefficient trafic (1.0 = fluide, 1.5 = embouteillage),
coefficient météo, temps max OR-Tools, itérations 2-opt.</p>
<p><b>Stratégie recommandée</b> : lancez « Comparer les 3 » puis utilisez l'algo
qui offre le meilleur compromis distance/temps de calcul.</p>

<h4>4.6 Carte Interactive</h4>
<p>Carte Leaflet avec marqueurs pour les dépôts (rouge) et clients (bleu).
Les itinéraires optimisés apparaissent en polylignes colorées (une
couleur par véhicule). Zoom avec la molette.</p>

<h4>4.7 Suivi en Temps Réel</h4>
<p>Simulation du suivi des livraisons : état des véhicules en transit,
progression des tournées, alertes retard. Marquez les livraisons comme
réussies ou échouées.</p>

<h4>4.8 Scénarios</h4>
<p>Sauvegardez des « snapshots » de vos données pour comparer
différentes configurations. Utile avant un import massif ou
pour tester l'impact d'un changement de flotte.</p>

<h4>4.9 Traduction IA</h4>
<p>Traduisez vos contenus entre FR, EN, AR, ES, DE.
Pipeline 3 niveaux : glossaire local → API en ligne → fallback hors-ligne.</p>

<h4>4.10 Rapports</h4>
<p>Générez des rapports en CSV, TXT, JSON ou PDF : rapport clients,
véhicules, tournées, KPI, comparaison algorithmes, anomalies, ou complet.</p>

<h4>4.11 Journal des Opérations</h4>
<p>Traçabilité complète : chaque action (création, modification,
suppression, optimisation, export) est horodatée avec l'utilisateur.</p>

<h4>4.12 Paramètres</h4>
<p>Configuration de l'algorithme par défaut, temps max, itérations,
traduction, carte, thème, alertes.</p>

<hr>
<h3>5. Édition inline (style Excel / Minitab)</h3>
<p>Les tables Clients, Véhicules et Dépôts supportent l'édition
directe dans les cellules :</p>
<ol>
<li><b>Double-cliquez</b> sur une cellule pour l'éditer</li>
<li>Modifiez la valeur et appuyez sur <b>Entrée</b></li>
<li>La modification est <b>sauvegardée automatiquement</b> en base</li>
<li>La <b>barre de formule</b> en haut affiche la cellule active
    et permet aussi d'éditer (tapez puis Entrée)</li>
</ol>
<p><b>Note</b> : la colonne <i>ID</i> est en lecture seule. La colonne
<i>Actions</i> contient les boutons Edit/Suppr/Dupl.</p>

<hr>
<h3>6. Raccourcis clavier</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background-color:#f0f0f0;">
    <td><b>Raccourci</b></td><td><b>Action</b></td></tr>
<tr><td>Ctrl+Shift+C</td><td>Ouvrir/fermer l'assistant Copilot IA</td></tr>
<tr><td>Double-clic sur cellule</td><td>Éditer la cellule</td></tr>
<tr><td>Entrée</td><td>Valider l'édition / Appliquer la barre de formule</td></tr>
<tr><td>Clic sur en-tête</td><td>Trier par colonne</td></tr>
</table>

<hr>
<h3>7. Datasets inclus</h3>

<h4>7.1 Solomon VRPTW Benchmarks (archive/solomon_dataset/)</h4>
<p>56 fichiers CSV classiques pour le benchmarking VRP :</p>
<ul>
<li><b>C1/C2</b> : clients regroupés (clustered)</li>
<li><b>R1/R2</b> : clients dispersés (random)</li>
<li><b>RC1/RC2</b> : mixte clustered + random</li>
</ul>
<p>~100 clients par fichier. Importez-les directement via le bouton Importer
sur la page Clients.</p>

<h4>7.2 Dataset réel (data/)</h4>
<p>Données réelles d'une entreprise de distribution en Bosnie-Herzégovine :</p>
<ul>
<li><code>2_detail_table_customers.xls</code> → page Clients</li>
<li><code>3_detail_table_vehicles.xls</code> → page Véhicules</li>
<li><code>4_detail_table_depots.xls</code> → page Dépôts</li>
<li><code>10_REAL_GPS_DATA_...csv</code> → données GPS réelles (tracking)</li>
</ul>

<hr>
<h3>8. Conseils & bonnes pratiques</h3>
<ol>
<li><b>Toujours sauvegarder un scénario</b> avant un import massif</li>
<li><b>Vérifier les coordonnées GPS</b> : une erreur de virgule
    peut placer un client à des milliers de km</li>
<li><b>Fenêtres horaires</b> : éviter des fenêtres &lt; 30 min
    qui rendent le problème sous-contraint</li>
<li><b>Flotte minimale</b> : si le solveur n'arrive pas à servir
    tous les clients, ajoutez un véhicule</li>
<li><b>Comparer</b> : lancez toujours les 3 algos pour identifier
    le meilleur compromis qualité/vitesse</li>
<li><b>Exporter un rapport</b> avant/après optimisation pour
    quantifier le gain</li>
</ol>

<hr>
<p style="color:#888; font-size:11px; text-align:center;">
CityPulse Logistics v1.0 — Optimisation de tournées VRP avec IA<br>
Chaque page dispose d'un bouton <b>?</b> pour l'aide contextuelle.
</p>
""",
    },

    # ── Dashboard ─────────────────────────────────────────────────
    "dashboard": {
        "title": "Aide — Dashboard",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Le <b>Dashboard</b> est votre tableau de bord décisionnel. Il résume en un
coup d'œil la performance globale de vos tournées de livraison.</p>

<h3>Indicateurs clés (KPI)</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Distance totale</b></td>
    <td>Somme des kilomètres parcourus par l'ensemble de la flotte.
        Un chiffre élevé peut indiquer des tournées à ré-optimiser.</td></tr>
<tr><td><b>Coût total</b></td>
    <td>Coût d'exploitation (carburant + coût/km de chaque véhicule).
        Comparez-le au budget prévu pour évaluer la rentabilité.</td></tr>
<tr><td><b>Livraisons</b></td>
    <td>Nombre de clients effectivement desservis par rapport au total.
        Un écart signale des clients non assignés (capacité insuffisante ?).</td></tr>
<tr><td><b>Retard moyen</b></td>
    <td>Retard moyen en minutes par rapport aux fenêtres horaires.
        <b>Objectif cible</b> : &lt; 5 min. Au-delà, revoyez les priorités.</td></tr>
<tr><td><b>Respect horaire</b></td>
    <td>Pourcentage de livraisons arrivées dans la fenêtre demandée.
        <b>Objectif cible</b> : &gt; 90 %. En dessous, élargissez les fenêtres
        ou ajoutez des véhicules.</td></tr>
<tr><td><b>Utilisation flotte</b></td>
    <td>Pourcentage de capacité de charge utilisée. Un taux &lt; 60 %
        signifie que vous pourriez réduire la flotte ou consolider
        des livraisons.</td></tr>
</table>

<h3>Graphiques</h3>
<ul>
<li><b>Comparaison d'algorithmes</b> : barres montrant la distance
    obtenue par chaque solveur (Glouton, 2-opt, OR-Tools). Plus
    la barre est basse, meilleur est le résultat.</li>
<li><b>Convergence</b> : courbe d'amélioration au fil des itérations.
    Si la courbe se stabilise très tôt, augmentez le nombre d'itérations
    pour obtenir de meilleures solutions.</li>
</ul>

<h3>Conseils d'analyse</h3>
<ol>
<li>Commencez par vérifier le <b>taux de respect horaire</b> : c'est
   le premier indicateur de qualité de service.</li>
<li>Si le coût est trop élevé mais le respect horaire est bon,
   essayez de réduire le nombre de véhicules.</li>
<li>Un retard moyen élevé combiné à une utilisation flotte haute
   indique un manque de véhicules.</li>
</ol>
""",
    },

    # ── Clients ───────────────────────────────────────────────────
    "clients": {
        "title": "Aide — Gestion des Clients",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Gestion complète de votre base clients : les points de livraison
que vos véhicules doivent desservir.</p>

<h3>Colonnes du tableau</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>ID</b></td><td>Identifiant unique, généré automatiquement.</td></tr>
<tr><td><b>Nom</b></td><td>Nom ou raison sociale du client.</td></tr>
<tr><td><b>Latitude / Longitude</b></td>
    <td>Coordonnées GPS en degrés décimaux (ex. 33.5731, −7.5898 pour
        Casablanca). Utilisées pour calculer les distances.</td></tr>
<tr><td><b>Demande (kg)</b></td>
    <td>Poids de la marchandise à livrer. Le solveur vérifie qu'un
        véhicule ne dépasse jamais sa capacité maximale.</td></tr>
<tr><td><b>Début</b></td>
    <td>Heure la plus tôt à laquelle le client accepte la livraison,
        exprimée en <b>minutes depuis minuit</b>
        (ex. 480 = 08:00, 720 = 12:00).</td></tr>
<tr><td><b>Fin</b></td>
    <td>Heure limite de livraison (même format). Un véhicule arrivant
        après cette heure génère un <i>retard</i>.</td></tr>
<tr><td><b>Service</b></td>
    <td>Temps de déchargement ou service chez le client, en minutes.
        Le solveur l'ajoute au temps de trajet.</td></tr>
<tr><td><b>Priorité</b></td>
    <td>De 1 (urgente) à 5 (basse). Les clients prioritaires sont
        servis en premier par l'algorithme.</td></tr>
<tr><td><b>Type</b></td>
    <td><i>standard</i>, <i>prioritaire</i> ou <i>fragile</i> — permet
        de filtrer et d'appliquer des règles métier spécifiques.</td></tr>
</table>

<h3>Actions</h3>
<ul>
<li><b>Edit</b> : modifier les informations du client.</li>
<li><b>Suppr</b> : archiver le client (il ne sera plus inclus dans
    les optimisations mais reste en base).</li>
<li><b>Dupl</b> : dupliquer un client — utile pour créer un point
    de livraison proche avec des paramètres similaires.</li>
</ul>

<h3>Import (CSV / Excel)</h3>
<p>Le bouton <b>Importer</b> accepte les fichiers <b>CSV</b>, <b>XLS</b> et <b>XLSX</b>.</p>
<p>Colonnes attendues (CSV) : <code>name, latitude, longitude, demand_kg,
ready_time, due_time, service_time, priority, client_type</code>.</p>
<p>Pour les fichiers Excel, les colonnes sont détectées automatiquement
(format CityPulse, Solomon ou générique).</p>

<h3>Bonnes pratiques</h3>
<ol>
<li>Vérifiez toujours la cohérence des coordonnées GPS avant de
   lancer une optimisation.</li>
<li>Une fenêtre trop étroite (Fin − Début &lt; 30 min) rend le
   problème plus difficile et peut générer des retards.</li>
<li>Utilisez le filtre par type pour isoler les clients fragiles
   et leur affecter des véhicules adaptés.</li>
</ol>
""",
    },

    # ── Véhicules ─────────────────────────────────────────────────
    "vehicles": {
        "title": "Aide — Gestion des Véhicules",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Déclarez et gérez votre flotte de véhicules. Chaque véhicule
est affecté aux tournées par le moteur d'optimisation.</p>

<h3>Colonnes du tableau</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>ID</b></td><td>Identifiant unique.</td></tr>
<tr><td><b>Immatriculation</b></td><td>Plaque du véhicule.</td></tr>
<tr><td><b>Type</b></td>
    <td>Catégorie : fourgon, camionnette, poids-lourd…
        Influe sur la capacité et le coût.</td></tr>
<tr><td><b>Capacité kg</b></td>
    <td>Charge utile maximale en kilogrammes. Le solveur
        ne dépassera jamais cette limite.</td></tr>
<tr><td><b>Capacité m³</b></td>
    <td>Volume maximal disponible. Utile pour les
        marchandises volumineuses mais légères.</td></tr>
<tr><td><b>Vitesse</b></td>
    <td>Vitesse moyenne en km/h, utilisée pour estimer
        les temps de trajet entre les clients.</td></tr>
<tr><td><b>Coût/km</b></td>
    <td>Coût d'exploitation par kilomètre (carburant +
        usure + péages). Sert au calcul du coût total.</td></tr>
<tr><td><b>Chauffeur</b></td><td>Nom du conducteur affecté.</td></tr>
<tr><td><b>Statut</b></td>
    <td><i>disponible</i> = prêt à rouler,
        <i>maintenance</i> = en réparation,
        <i>hors service</i> = retiré de la flotte.
        Seuls les véhicules <i>disponibles</i> sont
        pris en compte par le solveur.</td></tr>
</table>

<h3>Import (CSV / Excel)</h3>
<p>Le bouton <b>Importer</b> accepte les fichiers <b>CSV</b>, <b>XLS</b>
et <b>XLSX</b>. Les colonnes sont détectées automatiquement
(format CityPulse avec VEHICLE_CODE, ou format générique).</p>

<h3>Conseils</h3>
<ul>
<li>Si toutes vos tournées sont presque pleines, ajoutez
    un véhicule ou augmentez la capacité.</li>
<li>Un coût/km élevé pénalise le coût total : vérifiez
    vos tarifs carburant régulièrement.</li>
<li>Mettez les véhicules en <i>maintenance</i> plutôt
    que de les supprimer — ainsi l'historique est préservé.</li>
</ul>
""",
    },

    # ── Dépôts ────────────────────────────────────────────────────
    "depots": {
        "title": "Aide — Gestion des Dépôts",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Un dépôt est le point de départ et d'arrivée de chaque tournée.
Le solveur calcule les distances depuis/vers le dépôt.</p>

<h3>Colonnes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Nom</b></td><td>Nom de l'entrepôt ou du hub logistique.</td></tr>
<tr><td><b>Adresse</b></td><td>Adresse postale (informative).</td></tr>
<tr><td><b>Latitude / Longitude</b></td>
    <td>Position GPS exacte — c'est elle qui est utilisée dans
        les calculs de distance.</td></tr>
<tr><td><b>Ouverture / Fermeture</b></td>
    <td>Plage horaire du dépôt (HH:MM). Les véhicules doivent
        partir après l'ouverture et revenir avant la fermeture.</td></tr>
</table>

<h3>Bonnes pratiques</h3>
<ul>
<li>Si vos clients sont répartis sur une grande zone, envisagez
    plusieurs dépôts pour réduire les distances.</li>
<li>Le dépôt principal est utilisé par défaut pour toutes les
    tournées. Vérifiez ses coordonnées avec soin.</li>
</ul>
""",
    },

    # ── Optimisation IA ───────────────────────────────────────────
    "optimization": {
        "title": "Aide — Moteur d'Optimisation IA",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>C'est le cœur de l'application : configurer et lancer les
algorithmes de résolution du <b>Vehicle Routing Problem (VRP)</b>
avec fenêtres de temps.</p>

<h3>Les 3 algorithmes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Glouton (Greedy)</b></td>
    <td>Rapide (~&lt; 1 s). Affecte chaque client au véhicule le
        plus proche qui a encore de la capacité. Bon pour un
        premier aperçu, mais rarement optimal.</td></tr>
<tr><td><b>2-opt local search</b></td>
    <td>Prend la solution gloutonne puis tente des milliers
        d'inversions de segments pour réduire la distance.
        Résultats souvent <b>5 à 15 %</b> meilleurs que le glouton.</td></tr>
<tr><td><b>OR-Tools (Google)</b></td>
    <td>Solveur industriel avec méta-heuristiques avancées.
        Donne la meilleure solution, mais peut prendre plus
        de temps sur de gros jeux de données.</td></tr>
</table>

<h3>Paramètres de configuration</h3>
<ul>
<li><b>Coefficient trafic</b> : multiplie les temps de trajet.
    1.0 = fluide, 1.3 = heure de pointe, 1.5 = embouteillage sévère.</li>
<li><b>Coefficient météo</b> : 1.0 = beau temps, 1.2 = pluie,
    1.5 = neige / verglas.</li>
<li><b>Temps max OR-Tools</b> : durée maximale de recherche (secondes).
    Augmenter → meilleure solution, mais plus lent.</li>
<li><b>Itérations 2-opt</b> : nombre de tentatives d'amélioration.
    Plus d'itérations → meilleur résultat.</li>
</ul>

<h3>Tableau de résultats — comment lire les métriques</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Distance (km)</b></td><td>Plus bas = mieux.</td></tr>
<tr><td><b>Durée (min)</b></td><td>Temps total de toutes les tournées.</td></tr>
<tr><td><b>Coût (€)</b></td><td>= Distance × coût/km de chaque véhicule.</td></tr>
<tr><td><b>Clients servis</b></td><td>Doit idéalement être = 100 %.</td></tr>
<tr><td><b>Respect horaire</b></td><td>% de clients livrés dans leur fenêtre.</td></tr>
<tr><td><b>Retard moy.</b></td><td>Minutes de retard en moyenne.</td></tr>
<tr><td><b>Temps CPU</b></td><td>Temps de calcul en millisecondes.</td></tr>
<tr><td><b>Gain vs Glouton</b></td><td>Économie par rapport à la solution
    de base. Un gain de 12 % signifie 12 % de km en moins.</td></tr>
</table>

<h3>Stratégie recommandée</h3>
<ol>
<li>Lancez d'abord <b>Comparer les 3</b> pour voir les écarts.</li>
<li>Si OR-Tools est nettement meilleur, utilisez-le pour la
   solution finale.</li>
<li>Si 2-opt est proche d'OR-Tools, privilégiez-le pour sa
   rapidité en opérationnel quotidien.</li>
</ol>
""",
    },

    # ── Carte ─────────────────────────────────────────────────────
    "map": {
        "title": "Aide — Carte Interactive",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Visualisation géographique de vos dépôts, clients et itinéraires
optimisés sur une carte Leaflet interactive.</p>

<h3>Éléments affichés</h3>
<ul>
<li><b>Marqueurs rouges</b> : dépôts (point de départ/arrivée).</li>
<li><b>Marqueurs bleus</b> : clients à livrer.</li>
<li><b>Polylignes colorées</b> : chaque couleur = une tournée
    (un véhicule). Suivez la ligne pour voir l'ordre de visite.</li>
</ul>

<h3>Contrôles</h3>
<ul>
<li><b>Recentrer</b> : remet la vue centrée sur Casablanca (ou votre
    dépôt principal).</li>
<li><b>Rafraîchir</b> : recharge les données depuis la base pour
    afficher les derniers clients/résultats.</li>
<li><b>Zoom</b> : molette souris ou boutons +/−. Double-clic pour
    zoomer sur un point.</li>
</ul>

<h3>Comment analyser la carte</h3>
<ol>
<li>Des tournées qui se croisent signalent un potentiel
    d'amélioration — le solveur pourrait mieux répartir.</li>
<li>Un client isolé loin du groupe principal coûte cher :
    envisagez un véhicule dédié ou un dépôt satellite.</li>
<li>Superposez mentalement les zones de livraison : idéalement
    chaque véhicule couvre un « secteur » géographique distinct.</li>
</ol>
""",
    },

    # ── Suivi temps réel ──────────────────────────────────────────
    "tracking": {
        "title": "Aide — Suivi en Temps Réel",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Simulation du suivi de vos livraisons en temps réel : état des
véhicules, progression des tournées et alertes.</p>

<h3>Cartes KPI</h3>
<ul>
<li><b>En transit</b> : véhicules actuellement sur la route.</li>
<li><b>Livrés</b> : clients déjà desservis.</li>
<li><b>En retard</b> : véhicules hors fenêtre horaire.</li>
<li><b>En attente</b> : véhicules pas encore partis.</li>
</ul>

<h3>Tableau des véhicules</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Véhicule</b></td><td>Immatriculation.</td></tr>
<tr><td><b>Chauffeur</b></td><td>Nom du conducteur.</td></tr>
<tr><td><b>Client en cours</b></td><td>Prochain point de livraison.</td></tr>
<tr><td><b>ETA</b></td><td>Heure estimée d'arrivée au client.</td></tr>
<tr><td><b>Progression</b></td><td>Nombre de clients livrés / total.</td></tr>
<tr><td><b>Barre</b></td><td>Avancement visuel de la tournée.</td></tr>
<tr><td><b>OK / X</b></td><td>Marquer la livraison comme réussie
    ou échouée.</td></tr>
</table>

<h3>Notifications</h3>
<p>Le tableau de notifications affiche les alertes en temps réel :
retards, livraisons réussies, fenêtres horaires bientôt expirées.
Cliquez sur « Non lu » pour marquer comme traité.</p>
""",
    },

    # ── Scénarios ─────────────────────────────────────────────────
    "scenarios": {
        "title": "Aide — Gestion des Scénarios",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Sauvegardez et restaurez des « photos » de vos données
(clients + véhicules + dépôts) pour comparer différentes
configurations sans perdre votre travail.</p>

<h3>Colonnes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Nom</b></td><td>Nom que vous avez donné au scénario.</td></tr>
<tr><td><b>Clients / Véhicules</b></td>
    <td>Nombre d'éléments inclus dans le snapshot.</td></tr>
<tr><td><b>Algorithme</b></td><td>Algorithme utilisé (si applicable).</td></tr>
<tr><td><b>Date</b></td><td>Date de création du scénario.</td></tr>
</table>

<h3>Actions</h3>
<ul>
<li><b>Sauvegarder</b> : capture l'état actuel de la base.</li>
<li><b>Ouvrir</b> : restaure les données du scénario sélectionné
    (⚠ écrase les données actuelles).</li>
<li><b>Suppr</b> : supprime le scénario de la base.</li>
</ul>

<h3>Cas d'usage typiques</h3>
<ol>
<li>Sauvegardez avant d'importer un gros CSV — vous pourrez
   revenir en arrière.</li>
<li>Créez un scénario « haute saison » avec plus de clients
   et comparez avec le scénario normal.</li>
<li>Testez l'impact de la suppression d'un véhicule sur les
   performances.</li>
</ol>
""",
    },

    # ── Traduction IA ─────────────────────────────────────────────
    "translation": {
        "title": "Aide — Module de Traduction IA",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Traduisez vos contenus logistiques (rapports, noms de clients,
instructions de livraison) entre 5 langues : FR, EN, AR, ES, DE.</p>

<h3>Comment utiliser</h3>
<ol>
<li>Sélectionnez la langue <b>source</b> et la langue <b>cible</b>.</li>
<li>Collez ou saisissez le texte à gauche.</li>
<li>Cliquez sur <b>Traduire</b>. Le résultat apparaît à droite.</li>
<li>Utilisez <b>Valider</b> pour enregistrer la traduction dans
   l'historique (glossaire).</li>
</ol>

<h3>Pipeline de traduction 3 niveaux</h3>
<p>Le système essaie d'abord le <b>glossaire local</b> (traductions
déjà validées), puis l'<b>API en ligne</b>, puis un <b>fallback
hors-ligne</b> si la connexion est indisponible.</p>

<h3>Boutons de chargement rapide</h3>
<p>Les boutons en haut chargent automatiquement un contenu type
(liste des clients, rapport…) pour traduction en un clic.</p>
""",
    },

    # ── Rapports ──────────────────────────────────────────────────
    "reports": {
        "title": "Aide — Génération de Rapports",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Exportez vos données et résultats d'optimisation dans différents
formats exploitables.</p>

<h3>Types de rapports</h3>
<ul>
<li><b>Rapport Clients</b> : liste complète avec coordonnées et
    fenêtres horaires.</li>
<li><b>Rapport Véhicules</b> : état de la flotte et kilométrage.</li>
<li><b>Rapport Tournées</b> : détail de chaque itinéraire optimisé.</li>
<li><b>Rapport KPI</b> : synthèse des indicateurs de performance.</li>
<li><b>Rapport Comparaison</b> : benchmark des 3 algorithmes.</li>
<li><b>Rapport Anomalies</b> : incidents détectés.</li>
<li><b>Rapport Complet</b> : tout en un seul document.</li>
</ul>

<h3>Formats d'export</h3>
<ul>
<li><b>CSV</b> : pour Excel ou Google Sheets.</li>
<li><b>TXT</b> : texte brut, facile à imprimer.</li>
<li><b>JSON</b> : pour intégration avec d'autres systèmes.</li>
<li><b>PDF</b> : rapport formaté prêt à présenter.</li>
</ul>

<h3>Conseil</h3>
<p>Exportez un rapport <b>avant et après</b> l'optimisation pour
montrer le gain à votre direction.</p>
""",
    },

    # ── Journal ───────────────────────────────────────────────────
    "logs": {
        "title": "Aide — Journal des Opérations",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Traçabilité complète de toutes les actions effectuées dans
l'application : connexions, créations, modifications,
suppressions, optimisations, exports.</p>

<h3>Colonnes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Date/Heure</b></td><td>Horodatage précis de l'action.</td></tr>
<tr><td><b>Niveau</b></td>
    <td><i>INFO</i> = opération normale,
        <i>WARNING</i> = attention requise,
        <i>ERROR</i> = erreur survenue.</td></tr>
<tr><td><b>Action</b></td><td>Code de l'opération (SESSION_START,
    CLIENT_CREATE, OPTIMIZE, EXPORT…).</td></tr>
<tr><td><b>Détails</b></td><td>Description humaine de l'action.</td></tr>
<tr><td><b>Utilisateur</b></td><td>Qui a effectué l'action.</td></tr>
</table>

<h3>Utilisation</h3>
<ul>
<li>Filtrez par niveau pour ne voir que les erreurs.</li>
<li>Filtrez par date pour auditer une période précise.</li>
<li>En cas de problème, consultez les dernières entrées ERROR
    pour diagnostiquer la cause.</li>
</ul>
""",
    },

    # ── Paramètres ────────────────────────────────────────────────
    "settings": {
        "title": "Aide — Paramètres & Configuration",
        "body": """
<h3>À quoi sert cette page ?</h3>
<p>Personnalisez le comportement de l'application selon vos besoins.</p>

<h3>Sections</h3>

<h4>Configuration IA</h4>
<ul>
<li><b>Algorithme par défaut</b> : celui lancé quand vous cliquez sur
    « Optimiser » sans choisir explicitement.</li>
<li><b>Temps max OR-Tools</b> : durée de recherche. 30 s est un bon
    compromis ; montez à 120 s pour de gros problèmes.</li>
<li><b>Itérations 2-opt</b> : 1000 par défaut. Montez à 5000 pour
    des jeux de données &gt; 50 clients.</li>
<li><b>Seuil priorité</b> : les clients avec une priorité ≤ ce seuil
    sont traités en premier.</li>
</ul>

<h4>Configuration Traduction</h4>
<ul>
<li><b>Clé API</b> : votre clé pour le service de traduction en ligne.</li>
<li><b>Mode hors-ligne</b> : si activé, seul le glossaire local est
    utilisé (pas d'appel réseau).</li>
</ul>

<h4>Configuration Carte</h4>
<ul>
<li><b>Fournisseur de tuiles</b> : OpenStreetMap (défaut), Satellite,
    ou autres. Choisissez selon votre préférence visuelle.</li>
<li><b>Zoom par défaut</b> : niveau de zoom initial de la carte.</li>
</ul>

<h4>Configuration Système</h4>
<ul>
<li><b>Thème</b> : apparence de l'application.</li>
<li><b>Langue</b> : langue de l'interface.</li>
<li><b>Seuil alerte</b> : minutes de retard au-delà desquelles
    une notification est générée.</li>
</ul>
""",
    },
}


# ═══════════════════════════════════════════════════════════════════
#  Dialogue réutilisable
# ═══════════════════════════════════════════════════════════════════

class HelpDialog(QDialog):
    """Fenêtre d'aide contextuelle avec contenu HTML riche."""

    def __init__(self, parent, page_key: str):
        super().__init__(parent)
        data = HELP_CONTENT.get(page_key, {
            "title": "Aide",
            "body": "<p>Aucune aide disponible pour cette page.</p>",
        })

        self.setWindowTitle(data["title"])
        if page_key == "guide":
            self.setMinimumSize(780, 620)
            self.resize(900, 750)
        else:
            self.setMinimumSize(620, 520)
            self.resize(680, 580)
        self.setStyleSheet(
            "QDialog { background-color: #ffffff; }"
            "QLabel#helpTitle { font-size: 18px; font-weight: bold; color: #1a1a1a; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel(data["title"])
        title.setObjectName("helpTitle")
        layout.addWidget(title)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #d8dce3;")
        layout.addWidget(sep)

        # Content
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet(
            "QTextBrowser { border: none; background-color: #ffffff; "
            "color: #2c2c2c; font-size: 13px; }"
        )
        browser.setHtml(data["body"])
        layout.addWidget(browser, 1)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Fermer")
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


def show_help(parent, page_key: str):
    """Raccourci pour afficher l'aide d'une page."""
    dlg = HelpDialog(parent, page_key)
    dlg.exec()
