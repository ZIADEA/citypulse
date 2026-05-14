"""
app/i18n.py — Internationalisation CityPulse Logistics
=======================================================
Dictionnaire statique pour 5 langues : fr / en / ar / es / de
Usage : from app.i18n import tr, LANG_CODES, LANG_DISPLAY
"""

LANG_CODES: list[str] = ["fr", "en", "ar", "es", "de"]

LANG_DISPLAY: list[str] = [
    "Français (FR)",
    "English (EN)",
    "العربية (AR)",
    "Español (ES)",
    "Deutsch (DE)",
]

_T: dict[str, dict[str, str]] = {

    # ── Sidebar / navigation ──────────────────────────────────────────────
    "nav.dashboard":     {"fr": "Tableau de bord",   "en": "Dashboard",       "ar": "لوحة التحكم",     "es": "Panel de control",   "de": "Dashboard"},
    "nav.clients":       {"fr": "Clients",            "en": "Clients",         "ar": "العملاء",          "es": "Clientes",            "de": "Kunden"},
    "nav.vehicles":      {"fr": "Véhicules",          "en": "Vehicles",        "ar": "المركبات",         "es": "Vehículos",           "de": "Fahrzeuge"},
    "nav.drivers":       {"fr": "Chauffeurs",         "en": "Drivers",         "ar": "السائقون",         "es": "Conductores",         "de": "Fahrer"},
    "nav.depots":        {"fr": "Dépôts",             "en": "Depots",          "ar": "المستودعات",       "es": "Depósitos",           "de": "Depots"},
    "nav.orders":        {"fr": "Commandes",          "en": "Orders",          "ar": "الطلبات",          "es": "Pedidos",             "de": "Aufträge"},
    "nav.carriers":      {"fr": "Transporteurs",      "en": "Carriers",        "ar": "شركات النقل",     "es": "Transportistas",      "de": "Transportunternehmen"},
    "nav.optimization":  {"fr": "Optimisation",       "en": "Optimization",    "ar": "التحسين",          "es": "Optimización",        "de": "Optimierung"},
    "nav.map":           {"fr": "Carte",              "en": "Map",             "ar": "الخريطة",          "es": "Mapa",                "de": "Karte"},
    "nav.tracking":      {"fr": "Suivi",              "en": "Tracking",        "ar": "التتبع",           "es": "Seguimiento",         "de": "Verfolgung"},
    "nav.scenarios":     {"fr": "Scénarios",          "en": "Scenarios",       "ar": "السيناريوهات",     "es": "Escenarios",          "de": "Szenarien"},
    "nav.translation":   {"fr": "Traduction",         "en": "Translation",     "ar": "الترجمة",          "es": "Traducción",          "de": "Übersetzung"},
    "nav.reports":       {"fr": "Rapports",           "en": "Reports",         "ar": "التقارير",         "es": "Informes",            "de": "Berichte"},
    "nav.logs":          {"fr": "Journal",            "en": "Logs",            "ar": "السجلات",          "es": "Registros",           "de": "Protokolle"},
    "nav.notifications": {"fr": "Notifications",      "en": "Notifications",   "ar": "الإشعارات",        "es": "Notificaciones",      "de": "Benachrichtigungen"},
    "nav.settings":      {"fr": "Paramètres",         "en": "Settings",        "ar": "الإعدادات",        "es": "Configuración",       "de": "Einstellungen"},

    # ── Page names (breadcrumb) ───────────────────────────────────────────
    "page.dashboard":    {"fr": "Tableau de bord",       "en": "Dashboard",             "ar": "لوحة التحكم",          "es": "Panel de control",          "de": "Dashboard"},
    "page.clients":      {"fr": "Clients",                "en": "Clients",               "ar": "العملاء",               "es": "Clientes",                  "de": "Kunden"},
    "page.vehicles":     {"fr": "Véhicules",              "en": "Vehicles",              "ar": "المركبات",              "es": "Vehículos",                 "de": "Fahrzeuge"},
    "page.drivers":      {"fr": "Chauffeurs",             "en": "Drivers",               "ar": "السائقون",              "es": "Conductores",               "de": "Fahrer"},
    "page.depots":       {"fr": "Dépôts",                 "en": "Depots",                "ar": "المستودعات",            "es": "Depósitos",                 "de": "Depots"},
    "page.orders":       {"fr": "Commandes",              "en": "Orders",                "ar": "الطلبات",               "es": "Pedidos",                   "de": "Aufträge"},
    "page.carriers":     {"fr": "Transporteurs",          "en": "Carriers",              "ar": "شركات النقل",          "es": "Transportistas",            "de": "Transportunternehmen"},
    "page.optimization": {"fr": "Optimisation",           "en": "Optimization",          "ar": "التحسين",               "es": "Optimización",              "de": "Optimierung"},
    "page.map":          {"fr": "Carte",                  "en": "Map",                   "ar": "الخريطة",               "es": "Mapa",                      "de": "Karte"},
    "page.tracking":     {"fr": "Suivi en temps réel",   "en": "Live Tracking",         "ar": "التتبع المباشر",        "es": "Seguimiento en tiempo real", "de": "Echtzeit-Verfolgung"},
    "page.scenarios":    {"fr": "Scénarios",              "en": "Scenarios",             "ar": "السيناريوهات",          "es": "Escenarios",                "de": "Szenarien"},
    "page.translation":  {"fr": "Traduction",             "en": "Translation",           "ar": "الترجمة",               "es": "Traducción",                "de": "Übersetzung"},
    "page.reports":      {"fr": "Rapports",               "en": "Reports",               "ar": "التقارير",              "es": "Informes",                  "de": "Berichte"},
    "page.logs":         {"fr": "Journal",                "en": "Logs",                  "ar": "السجلات",               "es": "Registros",                 "de": "Protokolle"},
    "page.notifications":{"fr": "Notifications",          "en": "Notifications",         "ar": "الإشعارات",             "es": "Notificaciones",            "de": "Benachrichtigungen"},
    "page.settings":     {"fr": "Paramètres",             "en": "Settings",              "ar": "الإعدادات",             "es": "Configuración",             "de": "Einstellungen"},

    # ── Menu bar ─────────────────────────────────────────────────────────
    "menu.file":         {"fr": "Fichier",                        "en": "File",                    "ar": "ملف",                      "es": "Archivo",                   "de": "Datei"},
    "menu.tools":        {"fr": "Outils",                         "en": "Tools",                   "ar": "أدوات",                    "es": "Herramientas",              "de": "Werkzeuge"},
    "menu.help":         {"fr": "Aide",                           "en": "Help",                    "ar": "مساعدة",                   "es": "Ayuda",                     "de": "Hilfe"},
    "menu.load_demo":    {"fr": "Charger données de démo…",       "en": "Load Demo Data…",         "ar": "تحميل بيانات تجريبية…",   "es": "Cargar datos demo…",        "de": "Demodaten laden…"},
    "menu.export_pdf":   {"fr": "Exporter rapport PDF…",          "en": "Export PDF Report…",      "ar": "تصدير تقرير PDF…",         "es": "Exportar informe PDF…",     "de": "PDF-Bericht exportieren…"},
    "menu.quit":         {"fr": "Quitter",                        "en": "Quit",                    "ar": "خروج",                     "es": "Salir",                     "de": "Beenden"},
    "menu.help_guide":   {"fr": "Guide utilisateur (F1)",         "en": "User Guide (F1)",         "ar": "دليل المستخدم (F1)",       "es": "Guía del usuario (F1)",     "de": "Benutzerhandbuch (F1)"},
    "menu.about":        {"fr": "À propos de CityPulse",          "en": "About CityPulse",         "ar": "حول CityPulse",            "es": "Acerca de CityPulse",       "de": "Über CityPulse"},

    # ── Section headers (SectionHeader.set_title) ─────────────────────────
    "section.dashboard":    {"fr": "Tableau de bord",         "en": "Dashboard",             "ar": "لوحة التحكم",      "es": "Panel de control",       "de": "Dashboard"},
    "section.clients":      {"fr": "Gestion des Clients",     "en": "Client Management",     "ar": "إدارة العملاء",     "es": "Gestión de Clientes",    "de": "Kundenverwaltung"},
    "section.vehicles":     {"fr": "Gestion de la Flotte",    "en": "Fleet Management",      "ar": "إدارة الأسطول",     "es": "Gestión de Flota",       "de": "Flottenmanagement"},
    "section.drivers":      {"fr": "Chauffeurs",              "en": "Drivers",               "ar": "السائقون",          "es": "Conductores",            "de": "Fahrer"},
    "section.depots":       {"fr": "Gestion des Dépôts",      "en": "Depot Management",      "ar": "إدارة المستودعات",  "es": "Gestión de Depósitos",   "de": "Depotverwaltung"},
    "section.orders":       {"fr": "Gestion des Commandes",   "en": "Order Management",      "ar": "إدارة الطلبات",     "es": "Gestión de Pedidos",     "de": "Auftragsverwaltung"},
    "section.carriers":     {"fr": "Transporteurs partenaires","en": "Partner Carriers",      "ar": "شركات النقل",      "es": "Transportistas socios",  "de": "Partnerunternehmen"},
    "section.shipments":    {"fr": "Expéditions sous-traitées","en": "Outsourced Shipments",  "ar": "الشحنات المُستعان",  "es": "Expediciones subcontratadas","de": "Ausgelagerte Sendungen"},
    "section.optimization": {"fr": "Optimisation des Tournées","en": "Route Optimization",   "ar": "تحسين المسارات",    "es": "Optimización de Rutas",  "de": "Routenoptimierung"},
    "section.map":          {"fr": "Carte Logistique",        "en": "Logistics Map",         "ar": "الخريطة اللوجستية", "es": "Mapa Logístico",         "de": "Logistik-Karte"},
    "section.tracking":     {"fr": "Suivi en Temps Réel",     "en": "Live Tracking",         "ar": "التتبع المباشر",    "es": "Seguimiento en Tiempo Real","de": "Echtzeit-Verfolgung"},
    "section.scenarios":    {"fr": "Gestion des Scénarios",   "en": "Scenario Management",   "ar": "إدارة السيناريوهات","es": "Gestión de Escenarios",  "de": "Szenarienverwaltung"},
    "section.translation":  {"fr": "Traduction",              "en": "Translation",           "ar": "الترجمة",           "es": "Traducción",             "de": "Übersetzung"},
    "section.reports":      {"fr": "Rapports & Exports",      "en": "Reports & Exports",     "ar": "التقارير والصادرات","es": "Informes y Exportaciones","de": "Berichte & Exporte"},
    "section.logs":         {"fr": "Journal des Actions",     "en": "Action Log",            "ar": "سجل الإجراءات",     "es": "Registro de Acciones",   "de": "Aktionsprotokoll"},
    "section.notifications":{"fr": "Centre de Notifications", "en": "Notification Center",   "ar": "مركز الإشعارات",    "es": "Centro de Notificaciones","de": "Benachrichtigungszentrum"},
    "section.settings":     {"fr": "Paramètres",              "en": "Settings",              "ar": "الإعدادات",         "es": "Configuración",          "de": "Einstellungen"},

    # ── Onglets DriversWidget ─────────────────────────────────────────────
    "drivers.tab.drivers":       {"fr": "Chauffeurs",         "en": "Drivers",       "ar": "السائقون",     "es": "Conductores",    "de": "Fahrer"},
    "drivers.tab.unavail":       {"fr": "Indisponibilités",   "en": "Unavailability","ar": "الغياب",       "es": "Indisponibilidades","de": "Abwesenheiten"},
    "drivers.tab.teams":         {"fr": "Équipes",            "en": "Teams",         "ar": "الفرق",        "es": "Equipos",        "de": "Teams"},
    "drivers.tab.perf":          {"fr": "Performance",        "en": "Performance",   "ar": "الأداء",       "es": "Rendimiento",    "de": "Leistung"},

    # ── Onglets CarriersWidget ────────────────────────────────────────────
    "carriers.tab.carriers":     {"fr": "Transporteurs",               "en": "Carriers",            "ar": "شركات النقل",      "es": "Transportistas",           "de": "Transportunternehmen"},
    "carriers.tab.shipments":    {"fr": "Expéditions sous-traitées",   "en": "Outsourced Shipments","ar": "الشحنات",           "es": "Expediciones",             "de": "Sendungen"},
    "carriers.tab.sim":          {"fr": "Simuler (flotte vs S/T)",     "en": "Simulate (fleet vs outsource)","ar": "محاكاة",    "es": "Simular (flota vs subcontratación)","de": "Simulation (Flotte vs. Outsourcing)"},
    "carriers.tab.eval":         {"fr": "Évaluation transporteurs",    "en": "Carrier Evaluation",  "ar": "تقييم شركات النقل","es": "Evaluación transportistas","de": "Transportunternehmen-Bewertung"},

    # ── Onglets SettingsWidget ────────────────────────────────────────────
    "settings.tab.company":  {"fr": "Entreprise",         "en": "Company",          "ar": "الشركة",           "es": "Empresa",            "de": "Unternehmen"},
    "settings.tab.map":      {"fr": "Carte",              "en": "Map",              "ar": "الخريطة",          "es": "Mapa",               "de": "Karte"},
    "settings.tab.algo":     {"fr": "Algorithmes",        "en": "Algorithms",       "ar": "الخوارزميات",      "es": "Algoritmos",         "de": "Algorithmen"},
    "settings.tab.reports":  {"fr": "Rapports",           "en": "Reports",          "ar": "التقارير",         "es": "Informes",           "de": "Berichte"},
    "settings.tab.api":      {"fr": "API & Intégrations", "en": "API & Integrations","ar": "API والتكاملات", "es": "API e Integraciones","de": "API & Integrationen"},
    "settings.tab.django":   {"fr": "Site Web Django",    "en": "Django Website",   "ar": "موقع Django",      "es": "Sitio Web Django",   "de": "Django Website"},
    "settings.tab.users":    {"fr": "Utilisateurs",       "en": "Users",            "ar": "المستخدمون",       "es": "Usuarios",           "de": "Benutzer"},
    "settings.tab.backup":   {"fr": "Sauvegarde",         "en": "Backup",           "ar": "النسخ الاحتياطي",  "es": "Copia de seguridad", "de": "Sicherung"},

    # ── Labels communs ────────────────────────────────────────────────────
    "settings.ui_language":  {"fr": "Langue de l'interface", "en": "UI Language",   "ar": "لغة الواجهة",      "es": "Idioma de interfaz", "de": "Oberflächensprache"},

    # ── Barre de statut ───────────────────────────────────────────────────
    "status.clients":  {"fr": "Clients",   "en": "Clients",  "ar": "عملاء",    "es": "Clientes",  "de": "Kunden"},
    "status.vehicles": {"fr": "Véhicules", "en": "Vehicles", "ar": "مركبات",   "es": "Vehículos", "de": "Fahrzeuge"},
    "status.depots":   {"fr": "Dépôts",    "en": "Depots",   "ar": "مستودعات", "es": "Depósitos", "de": "Depots"},
    "status.opts":     {"fr": "Opts",      "en": "Opts",     "ar": "تحسينات",  "es": "Opts",      "de": "Opts"},

    # ── Dashboard — KPI ───────────────────────────────────────────────────
    "dash.kpi.deliveries": {"fr": "Livraisons aujourd'hui",  "en": "Today's Deliveries",            "ar": "توصيلات اليوم",        "es": "Entregas hoy",              "de": "Heutige Lieferungen"},
    "dash.kpi.vehicles":   {"fr": "Véhicules actifs",        "en": "Active Vehicles",               "ar": "مركبات نشطة",          "es": "Vehículos activos",         "de": "Aktive Fahrzeuge"},
    "dash.kpi.punctuality":{"fr": "Taux ponctualité",        "en": "Punctuality Rate",              "ar": "معدل الانتظام",        "es": "Tasa puntualidad",          "de": "Pünktlichkeitsrate"},
    "dash.kpi.avg_cost":   {"fr": "Coût moyen tournée",      "en": "Avg. Route Cost",               "ar": "متوسط تكلفة الرحلة",   "es": "Coste medio ruta",          "de": "Ø Tourkosten"},
    "dash.kpi.co2":        {"fr": "CO₂ économisé",           "en": "CO₂ Saved",                     "ar": "CO₂ موفَّر",            "es": "CO₂ ahorrado",              "de": "CO₂ eingespart"},

    # ── Dashboard — Charts ────────────────────────────────────────────────
    "dash.chart.activity":   {"fr": "LIVRAISONS / DISTANCE — 7 DERNIERS JOURS", "en": "DELIVERIES / DISTANCE — LAST 7 DAYS", "ar": "التوصيلات / المسافة — آخر 7 أيام", "es": "ENTREGAS / DISTANCIA — 7 ÚLTIMOS DÍAS", "de": "LIEFERUNGEN / DISTANZ — LETZTE 7 TAGE"},
    "dash.chart.algos":      {"fr": "COMPARAISON ALGORITHMES (7J)",              "en": "ALGORITHM COMPARISON (7D)",           "ar": "مقارنة الخوارزميات (7 أيام)",       "es": "COMPARACIÓN ALGORITMOS (7D)",           "de": "ALGORITHMEN-VERGLEICH (7T)"},
    "dash.action.tracking":  {"fr": "Voir suivi →",   "en": "View tracking →",  "ar": "عرض التتبع →",   "es": "Ver seguimiento →", "de": "Tracking →"},
    "dash.action.optimize":  {"fr": "Optimiser →",    "en": "Optimize →",       "ar": "التحسين →",      "es": "Optimizar →",       "de": "Optimieren →"},

    # ── Dashboard — Logs / Stats ──────────────────────────────────────────
    "dash.logs.title":       {"fr": "ACTIVITÉ RÉCENTE",       "en": "RECENT ACTIVITY",          "ar": "النشاط الأخير",        "es": "ACTIVIDAD RECIENTE",    "de": "LETZTE AKTIVITÄT"},
    "dash.logs.link":        {"fr": "Journal complet →",      "en": "Full log →",               "ar": "السجل الكامل →",       "es": "Registro completo →",   "de": "Protokoll →"},
    "dash.logs.col.date":    {"fr": "Date",                   "en": "Date",                     "ar": "التاريخ",              "es": "Fecha",                 "de": "Datum"},
    "dash.logs.col.action":  {"fr": "Action",                 "en": "Action",                   "ar": "الإجراء",              "es": "Acción",                "de": "Aktion"},
    "dash.logs.col.detail":  {"fr": "Détails",                "en": "Details",                  "ar": "التفاصيل",             "es": "Detalles",              "de": "Details"},
    "dash.stats.title":      {"fr": "STATS RAPIDES",          "en": "QUICK STATS",              "ar": "إحصاءات سريعة",       "es": "ESTADÍSTICAS RÁPIDAS",  "de": "SCHNELLSTATISTIKEN"},
    "dash.stats.forecast":   {"fr": "Prévision J+1",          "en": "Tomorrow forecast",        "ar": "توقعات الغد",          "es": "Previsión mañana",      "de": "Prognose morgen"},
    "dash.stats.pending":    {"fr": "Commandes en attente",   "en": "Pending orders",           "ar": "الطلبات المعلقة",      "es": "Pedidos pendientes",    "de": "Offene Aufträge"},
    "dash.stats.veh_dispo":  {"fr": "Véhicules dispo demain", "en": "Vehicles avail. tomorrow", "ar": "مركبات متاحة غداً",   "es": "Vehículos disp. mañana","de": "Fahrzeuge morgen"},
    "dash.stats.alerts":     {"fr": "Alertes non lues",       "en": "Unread alerts",            "ar": "تنبيهات غير مقروءة",  "es": "Alertas sin leer",      "de": "Ungelesene Meldungen"},

    # ── Dashboard — Alertes panel ─────────────────────────────────────────
    "dash.alerts.title":     {"fr": "Alertes",               "en": "Alerts",              "ar": "التنبيهات",           "es": "Alertas",               "de": "Benachrichtigungen"},
    "dash.alerts.mark_read": {"fr": "Tout lu",               "en": "Mark all read",       "ar": "تعليم الكل مقروءاً",  "es": "Marcar leído",          "de": "Alle gelesen"},
    "dash.alerts.empty":     {"fr": "Aucune alerte non lue", "en": "No unread alerts",    "ar": "لا تنبيهات جديدة",   "es": "Sin alertas nuevas",    "de": "Keine neuen Meldungen"},
    "dash.btn.analyze":      {"fr": "Analyser patterns",     "en": "Analyze patterns",    "ar": "تحليل الأنماط",       "es": "Analizar patrones",     "de": "Muster analysieren"},
    "dash.greeting.day":     {"fr": "Bonjour",               "en": "Hello",               "ar": "مرحباً",               "es": "Hola",                  "de": "Hallo"},
    "dash.greeting.evening": {"fr": "Bonsoir",               "en": "Good evening",        "ar": "مساء الخير",           "es": "Buenas tardes",         "de": "Guten Abend"},

    # ── Clients — Barre d'outils ──────────────────────────────────────────
    "clients.btn.import":    {"fr": "Importer",    "en": "Import",         "ar": "استيراد",        "es": "Importar",        "de": "Importieren"},
    "clients.btn.export":    {"fr": "Exporter",    "en": "Export",         "ar": "تصدير",          "es": "Exportar",        "de": "Exportieren"},
    "clients.btn.map":       {"fr": "Vue Carte",   "en": "Map View",       "ar": "عرض الخريطة",    "es": "Vista Mapa",      "de": "Kartenansicht"},
    "clients.btn.anomalies": {"fr": "Anomalies",   "en": "Anomalies",      "ar": "الشذوذات",       "es": "Anomalías",       "de": "Anomalien"},
    "clients.batch.default": {"fr": "Action lot…", "en": "Batch action…",  "ar": "إجراء جماعي…",  "es": "Acción lote…",    "de": "Stapelakt…"},
    "clients.btn.apply":     {"fr": "Appliquer",   "en": "Apply",          "ar": "تطبيق",          "es": "Aplicar",         "de": "Anwenden"},
    "clients.subtitle":      {"fr": "Livraisons, fenêtres horaires, géocodage, anomalies", "en": "Deliveries, time windows, geocoding, anomalies", "ar": "التوصيلات، النوافذ الزمنية، الترميز الجغرافي، الشذوذات", "es": "Entregas, ventanas horarias, geocodificación, anomalías", "de": "Lieferungen, Zeitfenster, Geocodierung, Anomalien"},
    "clients.filter.title":  {"fr": "Filtres avancés", "en": "Advanced filters", "ar": "فلاتر متقدمة", "es": "Filtros avanzados", "de": "Erweiterte Filter"},

    # ── Vehicles — Barre d'outils ─────────────────────────────────────────
    "vehicles.btn.export_csv": {"fr": "Exporter CSV",  "en": "Export CSV",    "ar": "تصدير CSV",           "es": "Exportar CSV",    "de": "CSV exportieren"},
    "vehicles.btn.stats":      {"fr": "Stats flotte",  "en": "Fleet stats",   "ar": "إحصاءات الأسطول",    "es": "Stats flota",     "de": "Flottenstatistiken"},
    "vehicles.filter.all":     {"fr": "Tous statuts",  "en": "All statuses",  "ar": "جميع الحالات",        "es": "Todos los estados","de": "Alle Status"},

    # ── Scenarios ─────────────────────────────────────────────────────────
    "scenarios.subtitle":        {"fr": "Sauvegardez, chargez et comparez vos scénarios d'optimisation", "en": "Save, load and compare your optimization scenarios", "ar": "احفظ وحمّل وقارن سيناريوهات التحسين", "es": "Guarda, carga y compara tus escenarios de optimización", "de": "Szenarien speichern, laden und vergleichen"},
    "scenarios.btn.save":        {"fr": "Sauvegarder scénario actuel", "en": "Save current scenario",     "ar": "حفظ السيناريو الحالي",  "es": "Guardar escenario actual",  "de": "Szenario speichern"},
    "scenarios.section.traffic": {"fr": "Profil de trafic horaire (CSV)", "en": "Hourly traffic profile (CSV)", "ar": "ملف حركة المرور الساعي", "es": "Perfil de tráfico horario (CSV)", "de": "Stündliches Verkehrsprofil (CSV)"},
    "scenarios.traffic.empty":   {"fr": "Aucun profil chargé",   "en": "No profile loaded",    "ar": "لا يوجد ملف محمّل",    "es": "Sin perfil cargado",    "de": "Kein Profil geladen"},
    "scenarios.btn.import_csv":  {"fr": "Importer CSV",           "en": "Import CSV",           "ar": "استيراد CSV",           "es": "Importar CSV",          "de": "CSV importieren"},
    "scenarios.btn.clear":       {"fr": "Effacer",                "en": "Clear",                "ar": "مسح",                   "es": "Borrar",                "de": "Löschen"},
    "scenarios.section.saved":   {"fr": "Scénarios sauvegardés",  "en": "Saved scenarios",      "ar": "السيناريوهات المحفوظة", "es": "Escenarios guardados",  "de": "Gespeicherte Szenarien"},
    "scenarios.col.name":        {"fr": "Nom",                    "en": "Name",                 "ar": "الاسم",                 "es": "Nombre",                "de": "Name"},
    "scenarios.col.clients":     {"fr": "Clients",                "en": "Clients",              "ar": "العملاء",               "es": "Clientes",              "de": "Kunden"},
    "scenarios.col.vehicles":    {"fr": "Véhicules",              "en": "Vehicles",             "ar": "المركبات",              "es": "Vehículos",             "de": "Fahrzeuge"},
    "scenarios.col.algo":        {"fr": "Algorithme",             "en": "Algorithm",            "ar": "الخوارزمية",            "es": "Algoritmo",             "de": "Algorithmus"},
    "scenarios.col.date":        {"fr": "Date",                   "en": "Date",                 "ar": "التاريخ",               "es": "Fecha",                 "de": "Datum"},
    "scenarios.col.tags":        {"fr": "Tags",                   "en": "Tags",                 "ar": "التصنيفات",             "es": "Etiquetas",             "de": "Tags"},
    "scenarios.col.actions":     {"fr": "Actions",                "en": "Actions",              "ar": "الإجراءات",             "es": "Acciones",              "de": "Aktionen"},
    "scenarios.btn.import_json": {"fr": "Importer JSON",          "en": "Import JSON",          "ar": "استيراد JSON",          "es": "Importar JSON",         "de": "JSON importieren"},
    "scenarios.btn.export_json": {"fr": "Exporter JSON",          "en": "Export JSON",          "ar": "تصدير JSON",            "es": "Exportar JSON",         "de": "JSON exportieren"},
    "scenarios.btn.duplicate":   {"fr": "Dupliquer",              "en": "Duplicate",            "ar": "تكرار",                 "es": "Duplicar",              "de": "Duplizieren"},
    "scenarios.section.compare": {"fr": "Comparer deux scénarios", "en": "Compare two scenarios","ar": "مقارنة سيناريوهين",   "es": "Comparar dos escenarios","de": "Zwei Szenarien vergleichen"},
    "scenarios.btn.compare":     {"fr": "Comparer (tableau + graphique)", "en": "Compare (table + chart)", "ar": "مقارنة (جدول + مخطط)", "es": "Comparar (tabla + gráfico)", "de": "Vergleichen (Tabelle + Diagramm)"},
    "scenarios.btn.map_split":   {"fr": "Carte scindée",          "en": "Split map",            "ar": "خريطة مقسمة",           "es": "Mapa dividido",         "de": "Geteilte Karte"},
    "scenarios.section.whatif":  {"fr": "Analyse What-If (1 paramètre)", "en": "What-If Analysis (1 parameter)", "ar": "تحليل ماذا لو", "es": "Análisis What-If (1 parámetro)", "de": "Was-wäre-wenn-Analyse"},
    "scenarios.btn.simulate":    {"fr": "Simuler",                "en": "Simulate",             "ar": "محاكاة",                "es": "Simular",               "de": "Simulieren"},
    "scenarios.section.desc":    {"fr": "Description & tags (sélection)", "en": "Description & tags (selection)", "ar": "الوصف والتصنيفات", "es": "Descripción & etiquetas (selección)", "de": "Beschreibung & Tags (Auswahl)"},
}


def tr(key: str, lang: str = "fr") -> str:
    """Retourne la chaîne traduite pour `key` dans `lang`.

    Repli : français → clé brute.
    """
    entry = _T.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry.get("fr") or key
