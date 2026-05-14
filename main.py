import sys
import os
import logging


def _project_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# ── Chemin projet (sources : dossier du dépôt ; PyInstaller : dossier de l’exe) ─
PROJECT_DIR = _project_dir()
if not getattr(sys, "frozen", False):
    sys.path.insert(0, PROJECT_DIR)

# ── Logging structuré JSON ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(PROJECT_DIR, "citypulse.log"), encoding= "utf-8"),
    ]
)
logger = logging.getLogger("citypulse.main")


def _check_dependencies() -> list[str]:
    """Vérifie les dépendances critiques et retourne les manquantes."""
    missing = []
    required = {
        "PyQt6":       "pip install PyQt6",
        "matplotlib":  "pip install matplotlib",
        "numpy":       "pip install numpy",
        "sklearn":     "pip install scikit-learn",
        "requests":    "pip install requests",
        "reportlab":   "pip install reportlab",
    }
    for pkg, install_cmd in required.items():
        try:
            __import__(pkg)
        except ImportError:
            missing.append(f"  * {pkg:15s} -> {install_cmd}")
    return missing


def _setup_global_exception_handler(app):
    """Handler global pour les exceptions non capturées dans les threads Qt."""
    import traceback
    from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

    def qt_message_handler(mode, context, message):
        if mode == QtMsgType.QtWarningMsg:
            logger.warning("Qt: %s", message)
        elif mode == QtMsgType.QtCriticalMsg:
            logger.error("Qt CRITICAL: %s", message)
        elif mode == QtMsgType.QtFatalMsg:
            logger.critical("Qt FATAL: %s", message)

    qInstallMessageHandler(qt_message_handler)

    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("Exception non capturée :\n%s", tb)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None,
            "Erreur critique — CityPulse",
            f"Une erreur inattendue s'est produite :\n\n{exc_value}\n\n"
            "Consultez citypulse.log pour les détails.",
        )

    sys.excepthook = excepthook


def _load_dotenv() -> None:
    """Charge le fichier .env du projet dans os.environ (sans dépendance python-dotenv)."""
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
        # distance.py lit CITYPULSE_OSRM_URL ; on mappe OSRM_URL si présent
        if "OSRM_URL" in os.environ and "CITYPULSE_OSRM_URL" not in os.environ:
            os.environ["CITYPULSE_OSRM_URL"] = os.environ["OSRM_URL"]
        logger.info("Fichier .env chargé")
    except Exception as e:
        logger.warning("Chargement .env échoué : %s", e)


def _run_migrations():
    """Lance les migrations BDD au démarrage."""
    try:
        from app.database.db_manager import init_database, run_migrations
        init_database()
        run_migrations()
        logger.info("Base de données initialisée")
    except Exception as e:
        logger.exception("Erreur initialisation BDD : %s", e)
        raise


def main():
    # ── Vérification dépendances ─────────────────────────────────────────────
    missing = _check_dependencies()
    if missing:
        print("\n Dépendances manquantes :\n")
        for m in missing:
            print(m)
        print(f"\nInstallez toutes les dépendances :\n  pip install -r requirements.txt\n")
        sys.exit(1)

    # ── PyQt6 ────────────────────────────────────────────────────────────────
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QCoreApplication
    from PyQt6.QtGui import QFont

    # WebEngine (QtWebEngineWidgets) : obligatoire avant QApplication
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    # High DPI
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("CityPulse Logistics")
    app.setOrganizationName("CityPulse")
    app.setApplicationVersion("5.0")
    app.setStyle("Fusion")

    # Police globale
    app.setFont(QFont("Segoe UI", 10))

    # Handler global exceptions
    _setup_global_exception_handler(app)

    # ── Chargement .env ──────────────────────────────────────────────────────
    _load_dotenv()

    # ── Migrations BDD ───────────────────────────────────────────────────────
    try:
        _run_migrations()
    except Exception as e:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "Erreur BDD",
            f"Impossible d'initialiser la base de données :\n{e}"
        )
        sys.exit(1)

    # ── Splash Screen ─────────────────────────────────────────────────────────
    from app.ui.splash_screen import SplashScreen
    from app.ui.main_window import MainWindow

    splash = SplashScreen()

    def show_main():
        # Appliquer le thème professionnel
        try:
            from app.ui.styles import get_stylesheet
            app.setStyleSheet(get_stylesheet())
        except Exception:
            logger.warning("Impossible de charger le thème")

        window = MainWindow()
        window.show()
        app._main_window = window   # Garder la référence vivante
        logger.info("Application démarrée — version 5.0")

    splash.finished.connect(show_main)
    splash.start()

    exit_code = app.exec()
    logger.info("Application fermée (code %d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
