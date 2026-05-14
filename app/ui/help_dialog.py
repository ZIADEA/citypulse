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

from .components.confirm_dialog import light_dialog_buttons_qss


# ═══════════════════════════════════════════════════════════════════
#  Contenu d'aide — synchronisé avec l'état réel de l'application
# ═══════════════════════════════════════════════════════════════════

HELP_CONTENT: dict[str, dict] = {

    # ── Guide complet ─────────────────────────────────────────────
    "guide": {
        "title": "Guide — CityPulse Logistics v5",
        "body": """
<h2>CityPulse Logistics — Guide d'utilisation</h2>

<hr>
<h3>1. Présentation</h3>
<p><b>CityPulse Logistics</b> est une application desktop d'optimisation
de tournées de véhicules (<i>VRP — Vehicle Routing Problem</i>) avec fenêtres
de temps, IA embarquée (Mistral), météo temps réel (OpenWeatherMap) et
conformité RSE/ADR/ZFE.</p>

<h3>2. Workflow typique</h3>
<table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background:#f0f0f0;"><td><b>Étape</b></td><td><b>Page</b></td><td><b>Action clé</b></td></tr>
<tr><td>1</td><td>Dépôts</td><td>Configurez au moins un dépôt (coordonnées GPS, horaires)</td></tr>
<tr><td>2</td><td>Clients</td><td>Importez (CSV/Excel) ou ajoutez vos points de livraison</td></tr>
<tr><td>3</td><td>Véhicules</td><td>Déclarez la flotte (capacité kg, coût/km, statut disponible)</td></tr>
<tr><td>4</td><td>Chauffeurs</td><td>Créez les profils et assignez aux véhicules</td></tr>
<tr><td>5</td><td>Commandes</td><td>Créez ou importez les commandes du jour</td></tr>
<tr><td>6</td><td>Optimisation</td><td>Lancez les 3 algorithmes et comparez</td></tr>
<tr><td>7</td><td>Carte / Suivi</td><td>Visualisez les itinéraires et suivez en temps réel</td></tr>
</table>

<h3>3. Pages de l'application</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background:#f0f0f0;"><td><b>Page</b></td><td><b>Rôle</b></td></tr>
<tr><td><b>Dashboard</b></td><td>5 KPI + 2 graphiques + météo + alertes + activité récente</td></tr>
<tr><td><b>Clients</b></td><td>Base clients, import CSV/Excel, géocodage, anomalies, vue carte</td></tr>
<tr><td><b>Véhicules</b></td><td>Flotte, 7 onglets fiche, alertes documents, stats</td></tr>
<tr><td><b>Chauffeurs</b></td><td>Profils, permis, qualifs ADR, calendrier indispos, équipes, perf</td></tr>
<tr><td><b>Dépôts</b></td><td>Entrepôts, minimap Leaflet, rayon couverture, vue globale</td></tr>
<tr><td><b>Commandes</b></td><td>5 KPI, commandes paginées, récurrentes, actions en lot</td></tr>
<tr><td><b>Transporteurs</b></td><td>Sous-traitants, expéditions, simulation coûts, évaluation</td></tr>
<tr><td><b>Optimisation</b></td><td>3 algos VRP, 5 onglets résultats, conformité RSE/ADR/ZFE</td></tr>
<tr><td><b>Carte</b></td><td>Leaflet interactif, itinéraires colorés, bannière météo</td></tr>
<tr><td><b>Suivi</b></td><td>Gantt temps réel, simulation, météo OWM, incidents</td></tr>
<tr><td><b>Scénarios</b></td><td>Snapshots, comparaison 2 scénarios, what-if, carte scindée</td></tr>
<tr><td><b>Traduction</b></td><td>FR/EN/AR/ES/DE, glossaire métier, score BLEU, historique</td></tr>
<tr><td><b>Rapports</b></td><td>7 catégories, PDF/Excel, BL/CMR/ADR, planification auto</td></tr>
<tr><td><b>Journal</b></td><td>Audit trail complet, filtres niveau/date/texte</td></tr>
<tr><td><b>Notifications</b></td><td>Centre de notifs, filtres, liens navigation, résumé journalier</td></tr>
<tr><td><b>Paramètres</b></td><td>5 onglets : Entreprise, Carte, Rapports, Utilisateurs, Sauvegarde</td></tr>
</table>

<h3>4. Algorithmes VRP</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background:#f0f0f0;"><td><b>Algo</b></td><td><b>Vitesse</b></td><td><b>Qualité</b></td></tr>
<tr><td>Glouton (Greedy)</td><td>&lt; 1 s</td><td>Baseline — solution de référence</td></tr>
<tr><td>2-opt local search</td><td>1–5 s</td><td>5 à 15 % mieux que le glouton</td></tr>
<tr><td>OR-Tools (Google)</td><td>5–120 s</td><td>Optimal ou quasi-optimal</td></tr>
</table>

<h3>5. Conseils</h3>
<ol>
<li>Sauvegardez un <b>scénario</b> avant tout import massif.</li>
<li>Vérifiez les <b>coordonnées GPS</b> des clients : une erreur de virgule peut fausser tout le calcul.</li>
<li>Seuls les véhicules avec statut <b>disponible</b> sont pris en compte.</li>
<li>Le <b>Copilot IA</b> (Ctrl+Shift+C) peut naviguer, optimiser et créer des commandes sur instruction.</li>
</ol>
""",
    },

    # ── Dashboard ─────────────────────────────────────────────────
    "dashboard": {
        "title": "Aide — Tableau de bord",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Vue synthétique de la performance de vos tournées : 5 KPI, 2 graphiques
Matplotlib, un panneau météo/alertes et un tableau d'activité récente.</p>

<h3>Indicateurs KPI (ligne du haut)</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Livraisons aujourd'hui</b></td>
    <td>Nombre de livraisons avec statut livré/complété dans la journée.
        Comparez avec le total des commandes du jour.</td></tr>
<tr><td><b>Véhicules actifs</b></td>
    <td>Véhicules avec au moins une route planifiée aujourd'hui.
        Un taux bas indique une sous-utilisation de la flotte.</td></tr>
<tr><td><b>Taux ponctualité</b></td>
    <td>% de livraisons effectuées dans les fenêtres horaires.
        <b>Cible :</b> &gt; 90 %. En dessous, réviser les créneaux ou ajouter des véhicules.</td></tr>
<tr><td><b>Coût moyen tournée</b></td>
    <td>Coût total divisé par le nombre de tournées actives.
        Utile pour suivre la rentabilité opérationnelle.</td></tr>
<tr><td><b>CO₂ économisé</b></td>
    <td>Réduction CO₂ estimée par rapport à une tournée naïve (sans optimisation).
        Indicateur RSE/développement durable.</td></tr>
</table>

<h3>Graphiques (zone centrale)</h3>
<ul>
<li><b>Livraisons / Distance — 7 derniers jours</b> : barres bleues = livraisons,
    courbe orange = km parcourus. Corrélation utile pour détecter les jours chargés.</li>
<li><b>Comparaison algorithmes (7J)</b> : barres par algorithme (Glouton, 2-opt,
    OR-Tools) montrant distance moyenne et coût moyen. La colonne la plus basse
    identifie l'algorithme le plus efficace sur la semaine.</li>
</ul>

<h3>Panneau droite</h3>
<ul>
<li><b>Mini-météo</b> : température, description et icône depuis OpenWeatherMap
    (nécessite une clé OWM dans Paramètres).</li>
<li><b>Alertes / Notifications</b> : jusqu'à 15 notifications récentes, colorées
    par sévérité. Cliquez sur une alerte pour accéder à la page concernée.</li>
<li><b>Stats rapides</b> : Prévision J+1 (commandes), Commandes en attente,
    Véhicules disponibles demain, Alertes non lues.</li>
</ul>

<h3>Tableau d'activité récente</h3>
<p>3 colonnes : <b>Date/Heure</b> | <b>Action</b> | <b>Détails</b>.
Liste les 50 dernières actions enregistrées dans le journal.</p>

<h3>Bouton Actualiser</h3>
<p>Recharge tous les KPI, graphiques et alertes depuis la base de données.
Les données se remplissent automatiquement après chaque optimisation.</p>
""",
    },

    # ── Clients ───────────────────────────────────────────────────
    "clients": {
        "title": "Aide — Gestion des Clients",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Base de données des points de livraison : ajout, édition, import/export,
géocodage GPS, détection d'anomalies et vue cartographique.</p>

<h3>Tableau principal — colonnes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>ID</b></td><td>Identifiant unique auto-généré.</td></tr>
<tr><td><b>Nom</b></td><td>Nom ou raison sociale du client.</td></tr>
<tr><td><b>Entreprise</b></td><td>Société (champ company_name).</td></tr>
<tr><td><b>Téléphone</b></td><td>Contact téléphonique.</td></tr>
<tr><td><b>Demande kg</b></td><td>Poids à livrer. Le solveur ne dépassera jamais la capacité véhicule.</td></tr>
<tr><td><b>Créneaux</b></td><td>Fenêtre(s) horaire(s) acceptée(s) (format HH:MM–HH:MM).</td></tr>
<tr><td><b>Priorité</b></td><td>1 etoile = basse, 5 etoiles = urgente (priorité 1 en base = 5 etoiles).</td></tr>
<tr><td><b>Tags</b></td><td>Étiquettes libres pour filtrer (ex. fragile, adr, vip).</td></tr>
<tr><td><b>Statut</b></td><td>Type client coloré (supermarché, restaurant, bureau…).</td></tr>
<tr><td><b>Actions</b></td><td>Modifier | Carte | Archiver (soft delete).</td></tr>
</table>

<h3>Recherche &amp; Filtres</h3>
<p><b>SearchBar</b> : filtre instantané sur nom, entreprise, téléphone et tags.
<br><b>Filtres avancés</b> (section repliable) : type multi-sélection, priorité slider, tag texte.</p>

<h3>Dialogue client — 5 onglets</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Général</b></td><td>Nom, entreprise, type client, statut, tags (chips)</td></tr>
<tr><td><b>Adresse</b></td><td>Adresse postale, lat/lon, bouton Géocoder (Nominatim), minimap Leaflet</td></tr>
<tr><td><b>Livraison</b></td><td>Demande kg/m³, durée service, créneaux 1+2, classe ADR, véhicule requis, ponctualité, pénalité €/h</td></tr>
<tr><td><b>Contact</b></td><td>Interlocuteur, téléphone, email, notes, chauffeur préféré</td></tr>
<tr><td><b>Historique</b></td><td>10 dernières commandes de ce client</td></tr>
</table>

<h3>Import CSV / Excel</h3>
<p>Cliquez sur <b>Importer</b> : sélectionnez un fichier CSV, XLS ou XLSX.
Une fenêtre affiche 5 lignes d'aperçu et permet de mapper les colonnes.
Le géocodage Nominatim est optionnel (1 req/s). Un rapport créés/mis à jour/erreurs
est affiché à la fin.</p>

<h3>Export</h3>
<p>Bouton <b>Exporter</b> → menu : CSV, Excel (openpyxl), JSON.</p>

<h3>Vue Carte</h3>
<p>Bouton <b>Vue Carte</b> : carte Leaflet avec marqueurs colorés par type client,
<code>fitBounds</code> automatique et légende.</p>

<h3>Anomalies</h3>
<p>Bouton <b>Anomalies</b> : détection z-score sur demande_kg, service_time,
coordonnées et créneaux. Les cas suspects sont listés avec une suggestion.</p>
""",
    },

    # ── Véhicules ─────────────────────────────────────────────────
    "vehicles": {
        "title": "Aide — Gestion des Véhicules",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Déclarez et gérez votre flotte. Seuls les véhicules avec statut
<b>disponible</b> sont pris en compte par l'optimiseur.</p>

<h3>Bandeau alertes documents (haut de page)</h3>
<p>S'affiche si des documents expirent dans les <b>30 jours</b> : immatriculation,
type de document (assurance / CT), jours restants et date exacte.
Limité à 6 alertes visibles.</p>

<h3>Tableau principal — 9 colonnes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Immat.</b></td><td>Plaque d'immatriculation (identifiant principal).</td></tr>
<tr><td><b>Marque</b></td><td>Constructeur du véhicule.</td></tr>
<tr><td><b>Type</b></td><td>Fourgon, camionnette, poids-lourd, etc.</td></tr>
<tr><td><b>Chauffeur</b></td><td>Conducteur actuellement assigné.</td></tr>
<tr><td><b>Cap. kg</b></td><td>Charge utile maximale. Le solveur ne dépassera jamais cette limite.</td></tr>
<tr><td><b>CO2/km</b></td><td>Émissions en kg/km (critère RSE et rapport CO₂).</td></tr>
<tr><td><b>Statut</b></td><td>Badge coloré : disponible (vert) | en service (cyan) | maintenance (orange) | hors service (rouge).</td></tr>
<tr><td><b>Docs</b></td><td>OK = documents valides | Alerte = expire dans l'année | Expiré = document échu. Survolez pour le détail.</td></tr>
<tr><td><b>Actions</b></td><td>Modifier | Calendrier | Stats | Archiver.</td></tr>
</table>

<h3>Barre KPI (sous le tableau)</h3>
<p>4 compteurs en temps réel : <b>Total flotte</b> | <b>Disponibles</b> | <b>En service</b> | <b>Maintenance</b>.</p>

<h3>Fiche véhicule — 7 onglets</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Identité</b></td><td>Immat.*, marque, modèle, année, type, motorisation, photo (aperçu 120×120)</td></tr>
<tr><td><b>Capacités</b></td><td>kg, m³, palettes, dimensions H/L/Lo, CO2/km, ADR (checkbox), ZFE (checkbox)</td></tr>
<tr><td><b>Vitesses</b></td><td>Autoroute / Nationale / Urbaine / Zone 30 (km/h)</td></tr>
<tr><td><b>Coûts</b></td><td>Coût/km, coût/heure, coût fixe/jour, coût non-utilisation/jour</td></tr>
<tr><td><b>Chauffeur</b></td><td>Combo chauffeur cherchable, open start/stop, rechargement autorisé</td></tr>
<tr><td><b>Documents</b></td><td>Date expiration assurance, CT, numéro assurance + alertes inline colorées</td></tr>
<tr><td><b>Dispo &amp; Stats</b></td><td>Dépôt d'attache, planning hebdo (7 checkboxes), km totaux / nb tournées / coût total</td></tr>
</table>

<h3>Calendrier indisponibilités</h3>
<p>Bouton Calendrier → grille mensuelle. Cliquez sur un jour pour le marquer indisponible
(table <code>vehicle_unavailabilities</code>). Navigation mensuelle ◀/▶.</p>

<h3>Stats flotte</h3>
<p>Bouton <b>Stats flotte</b> → dialogue avec 5 KPICards (total, disponibles,
en service, maintenance, hors service) + 2 KPI extras (km / CO₂) + camembert Matplotlib.</p>
""",
    },

    # ── Chauffeurs ────────────────────────────────────────────────
    "drivers": {
        "title": "Aide — Gestion des Chauffeurs",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Gestion complète de l'équipe de conducteurs : profils, permis, qualifications
ADR/CACES, indisponibilités, équipes et performances. La page est structurée en
<b>4 onglets</b>.</p>

<h3>Onglet Chauffeurs</h3>
<p><b>Bandeau alertes permis</b> (rouge/orange) : s'affiche si un permis expire dans &lt;= 30 jours.</p>
<p><b>Tableau — 9 colonnes</b> : Photo (36x36) | Nom | Permis/Cat. | Qualifications | Véhicule | Equipe | Statut | Expiration | Actions (Modifier / Calendrier / Archiver).</p>
<p><b>Double-clic</b> → fiche chauffeur (5 onglets) :</p>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Personnel</b></td><td>Photo, nom, prénom, date de naissance</td></tr>
<tr><td><b>Permis &amp; Qualifs</b></td><td>N° permis, catégorie (B/C/CE/D…), expiration + alerte live, ADR/CACES/FCO/FIMO/HAZMAT</td></tr>
<tr><td><b>Horaires</b></td><td>Plage travail HH:MM→HH:MM, pause déjeuner, max heures/jour, heures supp niveaux 1 et 2</td></tr>
<tr><td><b>RSE</b></td><td>Max conduite avant pause, pause min, repos journalier min (conformité CE 561/2006)</td></tr>
<tr><td><b>Affectation</b></td><td>Dépôt, véhicule (combo cherchable), zone, open start/stop, stats (tournées, km, retard moyen)</td></tr>
</table>

<h3>Onglet Indisponibilités</h3>
<p>Sélectionnez un chauffeur dans le combo, puis naviguez dans le calendrier mensuel.
<b>Clic sur un jour</b> → dialogue : date, raison, notes + bouton Supprimer si existant.
<br>Jours <b>rouge</b> = indisponible | <b>orange</b> = route planifiée ce jour.
<br>Si absence posée sur un jour planifié : liste automatique de remplaçants disponibles.</p>

<h3>Onglet Equipes</h3>
<p>Gauche : liste des équipes + « + Nouvelle équipe ». Droite : nom + manager (combo) +
deux listes (membres / tous chauffeurs) + boutons « Ajouter → » / « ← Retirer ».
CRUD complet sur tables <code>teams</code> et <code>team_members</code>.</p>

<h3>Onglet Performance</h3>
<p>Filtres chauffeur + période (De/À). Tableau 7 cols : Chauffeur | Tournées | Km total
| Km moy./tournée | Retard moy. | Taux ponctualité (coloré) | Dernière tournée.
<br>Graphique barres Matplotlib (km par chauffeur). Export CSV.</p>
""",
    },

    # ── Dépôts ────────────────────────────────────────────────────
    "depots": {
        "title": "Aide — Gestion des Dépôts",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Un dépôt est le point de départ et d'arrivée de chaque tournée.
Le solveur calcule les distances depuis/vers le dépôt choisi.</p>

<h3>Tableau principal — 8 colonnes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Nom</b></td><td>Nom de l'entrepôt ou hub logistique.</td></tr>
<tr><td><b>Adresse</b></td><td>Adresse postale (informative).</td></tr>
<tr><td><b>Responsable</b></td><td>Manager du dépôt.</td></tr>
<tr><td><b>Horaires</b></td><td>Ouverture → fermeture (HH:MM). Les véhicules doivent partir après l'ouverture et revenir avant la fermeture.</td></tr>
<tr><td><b>Quais</b></td><td>Nombre de quais de chargement disponibles.</td></tr>
<tr><td><b>Capacité</b></td><td>Capacité de stockage en tonnes.</td></tr>
<tr><td><b>Rayon km</b></td><td>Zone de couverture affichée sur la carte (cercle Leaflet).</td></tr>
<tr><td><b>Actions</b></td><td>Modifier | Carte | Archiver.</td></tr>
</table>

<h3>Fiche dépôt — 3 onglets</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Infos</b></td><td>Nom*, adresse, responsable, tél, lat/lon, Géocoder, horaires, quais, capacité, notes</td></tr>
<tr><td><b>Carte</b></td><td>Rayon couverture (km) + minimap Leaflet avec marqueur + cercle. La carte se charge à l'affichage de l'onglet.</td></tr>
<tr><td><b>Stats</b></td><td>Véhicules attachés, clients actifs dans le rayon, tournées optimisées depuis ce dépôt</td></tr>
</table>

<h3>Vue Carte globale</h3>
<p>Bouton <b>Vue Carte globale</b> : dialogue Leaflet avec tous les dépôts,
cercles de couverture colorés par dépôt et légende. Utilisez <code>fitBounds</code>
pour centrer sur l'ensemble.</p>

<h3>Conseils</h3>
<ul>
<li>Si vos clients sont très dispersés, créez plusieurs dépôts pour réduire les distances.</li>
<li>Le rayon de couverture est purement visuel — il n'est pas utilisé par le solveur.</li>
<li>Vérifiez bien les coordonnées GPS : toutes les distances sont calculées à partir de là.</li>
</ul>
""",
    },

    # ── Commandes ─────────────────────────────────────────────────
    "orders": {
        "title": "Aide — Gestion des Commandes",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Créez, assignez et suivez les commandes de livraison, collecte, échange ou retour.
Les commandes sont les unités de travail distribuées par le solveur VRP.</p>

<h3>KPI (barre du haut)</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>En attente</b></td><td>Commandes créées mais pas encore assignées à un véhicule.</td></tr>
<tr><td><b>Assignées</b></td><td>Liées à un véhicule et un chauffeur, pas encore démarrées.</td></tr>
<tr><td><b>En cours</b></td><td>Tournée démarrée, livraison en route.</td></tr>
<tr><td><b>Livrées aujourd'hui</b></td><td>Confirmées livrées dans la journée en cours.</td></tr>
<tr><td><b>Échecs</b></td><td>Livraisons ratées ou annulées.</td></tr>
</table>

<h3>Tableau paginé — 9 colonnes (80 lignes/page)</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Référence</b></td><td>N° auto <code>ORD-YYYYMMDD-NNNN</code>.</td></tr>
<tr><td><b>Client</b></td><td>Destinataire.</td></tr>
<tr><td><b>Type</b></td><td>Livraison / Collecte / Échange / Retour.</td></tr>
<tr><td><b>Statut</b></td><td>Badge coloré (En attente / Assignée / En cours / Livrée / Échec).</td></tr>
<tr><td><b>Date</b></td><td>Date prévue d'exécution.</td></tr>
<tr><td><b>kg</b></td><td>Poids total de la commande.</td></tr>
<tr><td><b>ADR</b></td><td>Classe de matière dangereuse (vide si non applicable).</td></tr>
<tr><td><b>Priorité</b></td><td>1 à 5 etoiles (5 = urgence maximale).</td></tr>
<tr><td><b>Actions</b></td><td>Modifier | BL PDF | CMR | Archiver.</td></tr>
</table>

<h3>Fiche commande — 4 onglets</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Commande</b></td><td>Référence auto, client*, type, statut, date prévue, priorité</td></tr>
<tr><td><b>Marchandises</b></td><td>kg, m³, unités/palettes, catégorie, température (ambiant/frigo/congelé), classe ADR (14 options), valeur déclarée €</td></tr>
<tr><td><b>Créneaux</b></td><td>Créneau 1* (obligatoire) + créneau 2 optionnel (HH:MM–HH:MM), durée visite min, instructions, code accès</td></tr>
<tr><td><b>Assignation</b></td><td>Véhicule (combo éditable + compléteur automatique) + chauffeur + dépôt. Alerte si véhicule non habilité ADR ou température incompatible.</td></tr>
</table>

<h3>Commandes récurrentes</h3>
<p>Bouton <b>Récurrentes</b> → gestionnaire de gabarits : nom, client, fréquence,
jours actifs, créneaux, kg, m³, actif/inactif.<br>
Bouton <b>Générer semaine</b> → crée automatiquement les commandes de la semaine
depuis les gabarits actifs (doublons évités).</p>

<h3>Actions en lot</h3>
<p>Sélectionnez plusieurs lignes (Shift+clic) → barre d'actions :
<b>Marquer livrées</b> | <b>Réassigner</b> (véhicule + chauffeur) | <b>Archiver</b>.</p>

<h3>Import / Export</h3>
<p>Import CSV/Excel avec mapping colonnes. Export CSV et Excel.
Les boutons <b>BL</b> et <b>CMR</b> dans Actions génèrent les documents PDF via ReportService.</p>
""",
    },

    # ── Transporteurs ─────────────────────────────────────────────
    "carriers": {
        "title": "Aide — Gestion des Transporteurs",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Gérez vos transporteurs partenaires (sous-traitants), suivez leurs expéditions,
comparez les coûts flotte propre vs sous-traitance et évaluez leurs performances.
La page est structurée en <b>4 onglets</b>.</p>

<h3>Onglet Transporteurs</h3>
<p>Tableau 8 cols : Nom | Contact | Zones | Types | €/km | Note | Ponctualité % | Actions.
<br>Double-clic → fiche transporteur (3 onglets) :</p>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Infos</b></td><td>Nom*, contact, tél, email, site, notes</td></tr>
<tr><td><b>Capacités &amp; Tarifs</b></td><td>Zones couvertes (tags), types véhicules (9 checkboxes), coût/km, coût/kg, coût fixe</td></tr>
<tr><td><b>Performance</b></td><td>Note (etoiles), ponctualité %, URL API de suivi, clé API (keyring OS)</td></tr>
</table>
<p>Bouton <b>Simuler coûts…</b> dans la toolbar → bascule vers l'onglet Simulation.</p>

<h3>Onglet Expéditions sous-traitées</h3>
<p>Tableau 8 cols : N° Tracking | Commande | Transporteur | Statut | Livraison est. | Coût € | Créé le | Actions.
<br>Bouton <b>Rafraîchir statuts</b> : interroge l'API de chaque transporteur en arrière-plan
(thread Qt) pour mettre à jour les statuts.</p>

<h3>Onglet Simuler (flotte vs sous-traitance)</h3>
<ol>
<li>Sélectionnez les commandes en attente dans la liste (multi-sélection).</li>
<li>Cliquez sur <b>Lancer la simulation</b>.</li>
<li>Choisissez un transporteur et comparez :<br>
    – <b>Coût flotte propre</b> = distance × coût/km moyen des véhicules<br>
    – <b>Coût sous-traitance</b> = tarif fixe + km × €/km + poids × €/kg</li>
<li>Tableau comparatif par commande + recommandation colorée + camembert Matplotlib.</li>
</ol>

<h3>Onglet Evaluation transporteurs</h3>
<p>Filtres période (De/À). Tableau 7 cols : Transporteur | Expéditions | Livrées | Taux livr. % | Coût total € | Ponctualité % | Note.
<br>Graphique double Matplotlib (coût + note). Export <b>Excel</b> et <b>PDF</b>.</p>

<h3>Sécurité des clés API</h3>
<p>Les clés API sont stockées dans le <b>keyring OS</b> (Windows Credential Manager /
macOS Keychain) — jamais en clair dans la base ni dans les fichiers.</p>
""",
    },

    # ── Optimisation IA ───────────────────────────────────────────
    "optimization": {
        "title": "Aide — Moteur d'Optimisation VRP",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Configurez et lancez les algorithmes VRP. Le résultat est envoyé automatiquement
à la Carte et au Suivi. La page est divisée en deux panneaux (QSplitter 30/70).</p>

<h3>Panneau GAUCHE — Configuration</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Date</b></td><td>Date de planification + bouton Actualiser les données.</td></tr>
<tr><td><b>Algorithmes</b></td><td>Cochez : Glouton / 2-opt / OR-Tools (un ou plusieurs).</td></tr>
<tr><td><b>Mode VRP</b></td><td>Standard (un dépôt) | Multi-dépôt | Open (sans retour) | Pickup &amp; Delivery | Rechargement.</td></tr>
<tr><td><b>Objectif</b></td><td>Distance min | Coût min | CO₂ min | Équilibré (4 sliders pondérés).</td></tr>
<tr><td><b>Options</b></td><td>Clustering KMeans, trafic auto, pauses RSE, compétences ADR/ZFE, créneaux, déjeuner 12h–14h.</td></tr>
<tr><td><b>Météo / Trafic</b></td><td>Conditions météo (×1.0 à ×1.6) + facteur manuel + bouton Auto (trafic horaire réel).</td></tr>
<tr><td><b>Limites</b></td><td>Temps max OR-Tools (secondes) + itérations 2-opt.</td></tr>
</table>
<p>Bouton <b>Lancer</b> (primaire) → lance séquentiellement les algos sélectionnés.
Bouton <b>Arrêter</b> (visible pendant le calcul).</p>

<h3>Panneau DROIT — 5 onglets résultats</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Comparaison</b></td>
    <td>Tableau 4 cols (Métrique | Glouton | 2-opt | OR-Tools). La meilleure valeur est surlignée vert+gras. Bandeau Meilleur algo.</td></tr>
<tr><td><b>Détail véhicules</b></td>
    <td>Combo algo + arbre véhicule → arrêts. Boutons : Verrouiller, Manifeste PDF, CMR.</td></tr>
<tr><td><b>Graphiques</b></td>
    <td>3 graphiques Matplotlib : Radar (distance/coût/ponctualité/CO2), Histogramme distances, Camembert utilisation flotte.</td></tr>
<tr><td><b>Simulation coûts</b></td>
    <td>3 sliders (prix carburant, péages, taux horaire) → tableau coûts détaillé (carburant/MO/fixe/péages/CO2/TOTAL) recalculé en temps réel.</td></tr>
<tr><td><b>Conformité RSE/ADR/ZFE</b></td>
    <td>Combo algo + 3 panneaux (RSE : pauses légales | ADR : classes dangereuses | ZFE : zones à faibles émissions). Statut OK/Echec + liste violations + bouton Suggestions.</td></tr>
</table>

<h3>Actions post-run</h3>
<p>Après le dernier algorithme : <b>Carte</b> | <b>Suivi</b> | <b>Scénario</b> | <b>PDF</b> | <b>CSV</b>.</p>

<h3>Métriques du tableau de comparaison</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Distance (km)</b></td><td>Plus bas = mieux.</td></tr>
<tr><td><b>Coût (€)</b></td><td>Distance × coût/km de chaque véhicule.</td></tr>
<tr><td><b>Clients servis</b></td><td>Doit idéalement être 100 %.</td></tr>
<tr><td><b>Respect horaire</b></td><td>% de livraisons dans la fenêtre demandée.</td></tr>
<tr><td><b>CO₂ (kg)</b></td><td>Émissions calculées par motorisation et PTAC.</td></tr>
<tr><td><b>Temps CPU</b></td><td>Durée de calcul en millisecondes.</td></tr>
</table>
""",
    },

    # ── Carte ─────────────────────────────────────────────────────
    "map": {
        "title": "Aide — Carte Interactive",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Visualisation géographique Leaflet des dépôts, clients et itinéraires optimisés.
La carte est mise à jour automatiquement après chaque optimisation.</p>

<h3>Éléments affichés</h3>
<ul>
<li><b>Marqueurs rouges</b> : dépôts (point de départ/arrivée des tournées).</li>
<li><b>Marqueurs bleus</b> : clients à livrer.</li>
<li><b>Polylignes colorées</b> : une couleur par véhicule/tournée. Survolez une polyligne pour voir les détails du trajet.</li>
</ul>

<h3>Bannière météo</h3>
<p>Si une clé OpenWeatherMap est configurée, une bannière affiche les conditions
actuelles au dépôt principal (température, description, facteur de trafic météo).</p>

<h3>Toolbar (droite)</h3>
<ul>
<li><b>Rafraîchir</b> : recharge les données depuis la base et recentre la carte.</li>
<li><b>Paramètres carte</b> : accès direct à l'onglet Carte des Paramètres (fond de carte, lat/lon/zoom par défaut, couleurs).</li>
<li><b>? Aide</b> : ce dialogue.</li>
</ul>

<h3>Fonds de carte disponibles</h3>
<p>Configurés dans <b>Paramètres → Carte</b> : Standard (OpenStreetMap), Dark,
Satellite, Terrain. La sélection est persistée dans <code>settings.json</code>.</p>

<h3>Comparaison scénarios (carte scindée)</h3>
<p>Depuis la page <b>Scénarios</b>, le bouton <b>Carte scindée</b> envoie deux
jeux d'itinéraires : les routes gauche apparaissent en pointillés, les routes
droite en lignes pleines — pour comparer visuellement deux configurations.</p>

<h3>Conseils d'analyse</h3>
<ol>
<li>Des tournées qui se croisent signalent un potentiel d'amélioration.</li>
<li>Un client isolé loin du groupe coûte cher : envisagez un dépôt satellite.</li>
<li>Idéalement, chaque véhicule couvre un secteur géographique distinct.</li>
</ol>
""",
    },

    # ── Suivi temps réel ──────────────────────────────────────────
    "tracking": {
        "title": "Aide — Suivi en Temps Réel",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Simulez et suivez vos tournées en temps réel : diagramme de Gantt interactif,
tableau live, gestion des incidents. Reçoit les résultats d'optimisation directement.</p>

<h3>Barre de simulation (en haut)</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Démarrer</b></td><td>Lance la simulation (QTimer 1s).</td></tr>
<tr><td><b>Pause / Reprendre</b></td><td>Gèle ou reprend la simulation.</td></tr>
<tr><td><b>Stop</b></td><td>Remet l'heure à 06:00.</td></tr>
<tr><td><b>Vitesse x2 / x5</b></td><td>Multiplie la vitesse de simulation.</td></tr>
<tr><td><b>Slider</b></td><td>Sauter directement à une heure (06:00 → 20:00).</td></tr>
</table>

<h3>Barre météo/trafic</h3>
<p>Combo conditions météo (Ensoleillé x1.0 | Pluie x1.1 | Orage x1.25 | Neige x1.6) + bouton
<b>Météo réelle</b> (appel OpenWeatherMap, clé requise) + bouton <b>Auto</b>
(trafic horaire selon heure et type de jour) + facteur affiché.</p>

<h3>5 KPI Cards</h3>
<p><b>Véhicules actifs</b> | <b>Livraisons</b> | <b>En retard</b> | <b>Km</b> | <b>CO₂ kg</b></p>

<h3>Gantt (onglet gauche)</h3>
<p>Plage horaire 06:00 → 20:00. Blocs colorés par type :</p>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Bleu</b></td><td>Travel — transit entre deux points</td></tr>
<tr><td><b>Vert</b></td><td>Visit — service chez le client</td></tr>
<tr><td><b>Gris</b></td><td>Pause RSE</td></tr>
<tr><td><b>Orange</b></td><td>Reload — rechargement intermédiaire</td></tr>
<tr><td><b>Rouge hachures</b></td><td>Delay — retard</td></tr>
<tr><td><b>Violet</b></td><td>Locked — bloc verrouillé</td></tr>
</table>
<p><b>Interactions :</b> Ctrl+molette = zoom horizontal | Hover = tooltip | Clic droit = menu (Détails / Annuler / Réaffecter / Verrouiller) | Drag &amp; drop = déplacer un bloc (avec confirmation) | Ctrl+Z = annuler (20 niveaux).</p>

<h3>Tableau live (onglet gauche)</h3>
<p>QTableWidget mis à jour chaque seconde : état de chaque véhicule (en transit,
ETA, progression N/total, dernière livraison).</p>

<h3>Panneau Incidents (droite)</h3>
<p>Notifications non lues depuis la base. Bouton <b>+ Signaler incident</b> →
dialogue (type, immatriculation, description). Un bandeau de re-optimisation
s'affiche si un bloc est annulé ou déplacé.</p>
""",
    },

    # ── Scénarios ─────────────────────────────────────────────────
    "scenarios": {
        "title": "Aide — Gestion des Scénarios",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Sauvegardez et restaurez des snapshots de vos données (clients, véhicules, dépôts)
ou des résultats d'optimisation complets. Comparez deux scénarios côte à côte,
testez des hypothèses (what-if) ou visualisez les deux sur la carte scindée.</p>

<h3>Deux façons de créer un scénario</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr style="background:#f0f0f0;">
  <td><b>Source</b></td><td><b>Ce qui est enregistré</b></td><td><b>Algorithme affiché</b></td>
</tr>
<tr>
  <td><b>Bouton « Sauvegarder scénario actuel »</b> (cette page)</td>
  <td>Snapshot clients + véhicules + dépôts (données BDD à l'instant T)</td>
  <td>—</td>
</tr>
<tr>
  <td><b>Bouton « Scénario »</b> (page Optimisation, après un run)</td>
  <td>Routes du meilleur algorithme + métriques comparatives de tous les algos</td>
  <td>Algo gagnant (Glouton / 2-opt / OR-Tools)</td>
</tr>
</table>

<h3>Liste des scénarios (tableau)</h3>
<p>Colonnes : <b>ID</b> | <b>Nom</b> | <b>Clients</b> | <b>Véhicules</b> |
<b>Algorithme</b> | <b>Date</b> | <b>Tags</b> | <b>Actions</b>.<br>
Cliquez sur une ligne pour afficher ses détails dans le panneau de droite
(tags, description — modifiables et sauvegardables).</p>

<h3>Boutons par ligne</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Restaurer</b></td>
    <td>Remplace tous les clients/véhicules/dépôts actuels par ceux du snapshot.
    <b>⚠ Action irréversible</b> — une confirmation est demandée.</td></tr>
<tr><td><b>Suppr.</b></td>
    <td>Supprime définitivement le scénario de la base.</td></tr>
</table>

<h3>Comparer deux scénarios</h3>
<p>Sélectionnez <b>A</b> et <b>B</b> dans les combos, puis cliquez sur
<b>Comparer (tableau + graphique)</b> → dialogue avec tableau comparatif
(clients, véhicules, distance km, coût, ponctualité par algorithme) et
graphique Matplotlib.<br>
<i>Note : les métriques distance/coût ne s'affichent que si le scénario
a été créé depuis la page Optimisation (résultats enregistrés).</i></p>

<h3>Carte scindée</h3>
<p>Bouton <b>Carte scindée</b> → ouvre la page Carte avec les points clients
des deux scénarios affichés simultanément (deux couleurs distinctes).</p>

<h3>Analyse What-If (estimation rapide)</h3>
<p>Choisissez un scénario, un paramètre à modifier et une valeur, puis cliquez
<b>Simuler</b>. Le résultat est une <b>estimation linéaire</b>, pas une
ré-optimisation complète — utilisez-la pour orienter une décision, pas comme
résultat final.</p>

<h3>Import / Export JSON</h3>
<p>Exportez un scénario en fichier JSON (partage entre postes).
Importez un fichier JSON pour le rejouter à la liste.</p>

<h3>Profil de trafic horaire (avancé)</h3>
<p>Importez un CSV <code>heure,coefficient</code> (ex. 08h → 1.75) pour que
l'optimiseur applique automatiquement ce profil selon l'heure de départ.
Le profil est persisté et sera rechargé au prochain démarrage.</p>

<h3>Cas d'usage typiques</h3>
<ol>
<li>Sauvegardez avant un import massif — vous pourrez restaurer rapidement.</li>
<li>Lancez 2 optimisations avec des configs différentes, sauvegardez-les
    et comparez les distances et coûts.</li>
<li>Testez l'impact d'un véhicule en moins (What-If) pour décider si vous
    pouvez réduire la flotte.</li>
</ol>
""",
    },

    # ── Traduction IA ─────────────────────────────────────────────
    "translation": {
        "title": "Aide — Module de Traduction IA",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Traduisez vos contenus logistiques entre 5 langues (FR / EN / AR / ES / DE)
avec un pipeline multi-niveaux et un glossaire métier persistant.</p>

<h3>Les 3 onglets</h3>

<h4>Onglet Traduction</h4>
<p>1. Choisissez la langue <b>Source</b> et la langue <b>Cible</b> (ou cliquez <b>Inverser</b>).<br>
2. Utilisez les boutons de chargement rapide (<b>Feuille de route</b>, <b>Dernier rapport</b>)
ou collez votre texte à gauche.<br>
3. Cliquez sur <b>Traduire</b> — la traduction apparaît à droite avec un <b>score BLEU-1</b>
(qualité estimée : plus c'est proche de 1.0, mieux c'est).<br>
4. Cliquez <b>Valider</b> pour enregistrer dans l'historique.<br>
5. Si un terme est mal traduit, renseignez le champ <b>Corriger</b> (terme original → correction)
puis <b>Mémoriser</b> : le glossaire BDD l'utilisera en priorité à l'avenir.</p>

<h4>Pipeline de traduction (4 niveaux)</h4>
<ol>
<li><b>Glossaire BDD utilisateur</b> (corrections mémorisées — priorité maximale)</li>
<li><b>Glossaire métier intégré</b> (termes logistiques FR/EN/AR/ES/DE)</li>
<li><b>API en ligne</b> (deep-translator / Mistral)</li>
<li><b>Fallback hors-ligne</b> (si connexion indisponible)</li>
</ol>

<h4>Onglet Glossaire métier</h4>
<p>Consultez, modifiez ou supprimez les paires de termes mémorisées.
Filtrez par langue source/cible. Chaque terme indique son compteur d'utilisation.</p>

<h4>Onglet Historique</h4>
<p>Liste des dernières traductions effectuées : langue source → cible, extrait du texte,
score BLEU, date. Cliquez sur une ligne pour recharger le texte dans l'onglet Traduction.</p>
""",
    },

    # ── Rapports ──────────────────────────────────────────────────
    "reports": {
        "title": "Aide — Génération de Rapports",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Générez des rapports PDF/Excel depuis 7 catégories, prévisualisez-les intégrés
dans la page et planifiez des exports automatiques quotidiens.</p>

<h3>Sélecteur de langue</h3>
<p>Combo <b>Langue du rapport</b> en haut à gauche : FR | EN | ES | DE | AR.
Tous les rapports générés utilisent cette langue pour les intitulés et contenus.</p>

<h3>7 catégories de rapports</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Opérationnels</b></td>
    <td>Road-book chauffeur (PDF + QR code par arrêt), rapport flotte quotidien (graphique km/véhicule)</td></tr>
<tr><td><b>Analytiques</b></td>
    <td>KPI période (PDF ou Excel, comparaison vs S-1), comparaison algorithmes (barres distances), performances chauffeurs</td></tr>
<tr><td><b>Clients</b></td>
    <td>Fiche client + 30 dernières commandes, rapport anomalies clients</td></tr>
<tr><td><b>Transporteurs</b></td>
    <td>Synthèse transporteurs (tous ou un seul), expéditions et coûts</td></tr>
<tr><td><b>Conformité</b></td>
    <td>Conformité RSE (pauses légales vs réel), rapport ADR (matières dangereuses)</td></tr>
<tr><td><b>Documents légaux</b></td>
    <td>CGU/confidentialité, Bon de livraison (BL) par ID commande, CMR, document ADR, Manifeste de chargement</td></tr>
<tr><td><b>Exports</b></td>
    <td>Excel multi-feuilles (Clients, Véhicules, Chauffeurs, Commandes, Tournées, Journal), snapshot JSON complet</td></tr>
</table>

<h3>Aperçu intégré</h3>
<p>Après génération, le PDF s'affiche directement dans la page droite
(nécessite PyQt6-WebEngine). Les fichiers Excel affichent un message informatif.</p>

<h3>Historique des rapports</h3>
<p>Les 25 derniers rapports générés sont listés en bas du panneau gauche.
Double-cliquez sur un rapport pour recharger son aperçu sans le régénérer.</p>

<h3>Planification automatique</h3>
<p>Section <b>Planification</b> (panneau gauche) : cochez <b>Export KPI quotidien (PDF)</b>,
choisissez le dossier de sortie. Un timer vérifie toutes les 60 secondes si l'heure
planifiée est atteinte et exporte automatiquement.</p>
""",
    },

    # ── Journal ───────────────────────────────────────────────────
    "logs": {
        "title": "Aide — Journal des Opérations",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Traçabilité complète de toutes les actions effectuées dans l'application :
connexions, créations, modifications, suppressions, optimisations, exports.
Chaque entrée est horodatée et liée à un utilisateur.</p>

<h3>Tableau — 5 colonnes</h3>
<table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse; width:100%;">
<tr><td><b>Date/Heure</b></td><td>Horodatage précis de l'action (format ISO).</td></tr>
<tr><td><b>Niveau</b></td>
    <td><i>INFO</i> = opération normale |
        <i>WARNING</i> = attention requise |
        <i>ERROR</i> = erreur survenue |
        <i>CRITICAL</i> = erreur grave.</td></tr>
<tr><td><b>Action</b></td><td>Code de l'opération (SESSION_START, CLIENT_CREATE, OPTIMIZE, EXPORT, REPORT_GENERATE…).</td></tr>
<tr><td><b>Détails</b></td><td>Description lisible de l'action (colonne extensible).</td></tr>
<tr><td><b>Utilisateur</b></td><td>Identifiant de l'utilisateur qui a effectué l'action.</td></tr>
</table>

<h3>Filtres disponibles</h3>
<ul>
<li><b>Niveau</b> : Tous | INFO | WARNING | ERROR | CRITICAL</li>
<li><b>Date De/À</b> : filtrer sur une période précise</li>
<li><b>Recherche texte</b> : filtre sur Action et Détails</li>
</ul>

<h3>Utilisation pratique</h3>
<ul>
<li>En cas de problème, filtrez sur <b>ERROR</b> pour voir la cause.</li>
<li>Pour auditer une période, utilisez les filtres De/À.</li>
<li>Cherchez <code>OPTIMIZE</code> pour retrouver tous les runs d'optimisation.</li>
<li>Cherchez <code>LOGIN</code> ou <code>SESSION</code> pour auditer les connexions.</li>
</ul>
""",
    },

    # ── Notifications ─────────────────────────────────────────────
    "notifications": {
        "title": "Aide — Centre de Notifications",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Centralisez et gérez toutes les alertes de l'application : retards, documents
expirants, anomalies, confirmations de livraison, résumés journaliers.</p>

<h3>Filtres</h3>
<ul>
<li><b>Type</b> : tous les types ou un type spécifique (retard, document, anomalie…).</li>
<li><b>Sévérité</b> : info | avertissement | critique.</li>
<li><b>Non lus seulement</b> : masque les notifications déjà lues.</li>
<li><b>Recherche texte</b> : filtre sur le titre et le message.</li>
</ul>

<h3>Liste + Panneau détail (280px)</h3>
<p>Cliquez sur une notification pour afficher son détail complet dans le panneau droit.
<b>Double-clic</b> → fenêtre de détail et marquage automatique comme lu.</p>

<h3>Liens de navigation</h3>
<p>Certaines notifications contiennent des liens de navigation
(ex. <code>citypulse://nav/7</code>) qui ouvrent directement la page concernée
(7 = Optimisation dans cet exemple).</p>

<h3>Résumé journalier</h3>
<p>Si activé dans <b>Paramètres → Entreprise</b> (option résumé + heure configurée),
une notification récapitulative est créée automatiquement à l'heure choisie.</p>

<h3>Cloche de notification (TopBar)</h3>
<p>La cloche en haut à droite de l'application affiche un badge avec le nombre
de notifications non lues. Le menu déroulant montre les 5 dernières.
Il se rafraîchit toutes les 30 secondes automatiquement.</p>
""",
    },

    # ── Paramètres ────────────────────────────────────────────────
    "settings": {
        "title": "Aide — Paramètres & Configuration",
        "body": """
<h3>À quoi sert cette page</h3>
<p>Configuration complète de l'application en <b>5 onglets</b>. Le bouton
<b>Sauvegarder</b> fixé en bas enregistre toutes les modifications dans
<code>settings.json</code>.</p>

<h3>Onglet Entreprise</h3>
<ul>
<li>Identité : nom, adresse, téléphone, email.</li>
<li>Devise (MAD / EUR / USD), fuseau horaire.</li>
<li>Logo : chemin vers votre logo (copié vers <code>assets/logo.png</code>), aperçu inline.</li>
<li>Thème UI : Dark (défaut) | Light — appliqué instantanément.</li>
<li><b>Langue de l'interface</b> : FR / EN / AR / ES / DE — traduit la sidebar, les titres de pages et les onglets.</li>
<li>Copilot IA : modèle Mistral + langue de conversation.</li>
<li>Notifications : seuils d'alerte, résumé journalier (heure + activation).</li>
</ul>

<h3>Onglet Carte</h3>
<ul>
<li>Fond de carte : Standard / Dark / Satellite / Terrain.</li>
<li>Coordonnées par défaut (lat/lon) + zoom initial.</li>
<li>Bouton <b>Dépôt principal</b> : remplace lat/lon par les coordonnées du dépôt ID 1.</li>
<li>10 couleurs véhicules (QColorDialog) pour les itinéraires Leaflet.</li>
<li>Affichage labels et ordre de visites sur la carte.</li>
</ul>

<h3>Onglet Rapports</h3>
<ul>
<li>Couleur thème, texte en-tête, texte pied de page, inclusion logo.</li>
<li>Dossier de sortie par défaut, taille papier.</li>
<li>Planification automatique : liste des exports programmés (heure + type + activé).
    Bouton + pour ajouter, bouton Supprimer pour retirer.</li>
</ul>

<h3>Onglet Utilisateurs (admin uniquement)</h3>
<ul>
<li>Tableau CRUD des comptes utilisateurs.</li>
<li>Rôles : admin | planner | dispatcher | viewer.</li>
<li>Soft delete (<code>is_active=0</code>) — l'historique est conservé.</li>
<li>Bouton <b>Modifier</b> : dialogue nom, email, rôle, reset mot de passe.</li>
</ul>

<h3>Onglet Sauvegarde</h3>
<ul>
<li><b>Snapshot BDD</b> : export JSON complet (toutes tables) via ReportService.</li>
<li><b>Importer snapshot</b> : restauration depuis un fichier JSON.</li>
<li><b>Reset données métier</b> : supprime clients/véhicules/commandes/routes (avec confirmation).</li>
<li><b>Charger données démo</b> : ouvre le DemoLoader (datasets Casablanca / Paris / Benchmark).</li>
<li><b>Vérifier intégrité</b> : lance <code>PRAGMA integrity_check</code> + affiche la taille du fichier SQLite.</li>
<li><b>OSRM</b> : URL du serveur + timeout + bouton Test (HTTP test sur itinéraire réel).</li>
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
            "QDialog { background-color: #ffffff; color: #1a1a2e; }"
            "QLabel#helpTitle { font-size: 18px; font-weight: bold; color: #1a1a1a; }"
            + light_dialog_buttons_qss()
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
