"""
CityPulse — Client Mistral AI
Gère la connexion à l'API Mistral, le chargement sécurisé de la clé,
la construction du system prompt contextuel et l'envoi des requêtes.
"""
import os
from typing import Optional

from dotenv import load_dotenv

# ── Chargement de la clé API depuis le .env du projet ──────────────
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)
load_dotenv(_ENV_PATH)

MISTRAL_API_KEY: Optional[str] = os.getenv("MISTRAL_API_KEY")

# ── SDK Mistral ────────────────────────────────────────────────────
try:
    from mistralai.client import Mistral

    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

# ── Modèle par défaut ─────────────────────────────────────────────
DEFAULT_MODEL = "mistral-small-latest"

# ── System prompts multilingues ───────────────────────────────────
SYSTEM_PROMPTS: dict[str, str] = {
    "fr": (
        "Tu es CityPulse Copilot, un assistant expert en logistique urbaine et "
        "optimisation de tournées de véhicules (VRP). Tu travailles à l'intérieur "
        "de l'application CityPulse Logistics. Réponds de façon concise, "
        "professionnelle et utile. Utilise les données contextuelles fournies "
        "pour personnaliser tes réponses. Réponds en français."
    ),
    "en": (
        "You are CityPulse Copilot, an expert assistant in urban logistics and "
        "vehicle routing problem (VRP) optimization. You work inside the CityPulse "
        "Logistics application. Answer concisely, professionally and helpfully. "
        "Use the contextual data provided to personalize your answers. Respond in English."
    ),
    "ar": (
        "أنت CityPulse Copilot، مساعد خبير في اللوجستيات الحضرية وتحسين مسارات "
        "المركبات (VRP). أنت تعمل داخل تطبيق CityPulse Logistics. أجب بإيجاز "
        "واحترافية. استخدم البيانات السياقية المقدمة لتخصيص إجاباتك. أجب بالعربية."
    ),
    "es": (
        "Eres CityPulse Copilot, un asistente experto en logística urbana y "
        "optimización de rutas de vehículos (VRP). Trabajas dentro de la aplicación "
        "CityPulse Logistics. Responde de forma concisa, profesional y útil. "
        "Usa los datos contextuales proporcionados para personalizar tus respuestas. "
        "Responde en español."
    ),
    "de": (
        "Du bist CityPulse Copilot, ein Experten-Assistent für urbane Logistik und "
        "Fahrzeugroutenoptimierung (VRP). Du arbeitest innerhalb der CityPulse "
        "Logistics Anwendung. Antworte prägnant, professionell und hilfreich. "
        "Nutze die bereitgestellten Kontextdaten, um deine Antworten zu personalisieren. "
        "Antworte auf Deutsch."
    ),
}


def get_app_context(main_window) -> str:
    """Génère un résumé textuel de l'état courant de l'application.

    Interroge la base de données pour fournir au LLM un contexte RAG léger
    sur les clients, véhicules, dépôts, scénarios, etc.
    """
    from ..database.db_manager import get_connection

    ctx_parts: list[str] = ["=== Contexte applicatif CityPulse ==="]

    try:
        conn = get_connection()

        # Clients
        row = conn.execute(
            "SELECT COUNT(*) AS total, SUM(demand_kg) AS total_kg "
            "FROM clients WHERE archived = 0"
        ).fetchone()
        ctx_parts.append(
            f"• Clients actifs : {row['total']}  |  Demande totale : "
            f"{row['total_kg'] or 0:.0f} kg"
        )

        # Véhicules
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status='disponible' THEN 1 ELSE 0 END) AS dispo "
            "FROM vehicles"
        ).fetchone()
        ctx_parts.append(
            f"• Véhicules : {row['total']}  (disponibles : {row['dispo'] or 0})"
        )

        # Dépôts
        nb_depots = conn.execute("SELECT COUNT(*) AS n FROM depots").fetchone()["n"]
        ctx_parts.append(f"• Dépôts enregistrés : {nb_depots}")

        # Scénarios
        nb_sc = conn.execute("SELECT COUNT(*) AS n FROM scenarios").fetchone()["n"]
        ctx_parts.append(f"• Scénarios sauvegardés : {nb_sc}")

        # Derniers résultats d'optimisation
        last = conn.execute(
            "SELECT algo, total_distance, total_time, nb_routes "
            "FROM algo_results ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if last:
            ctx_parts.append(
                f"• Dernière optimisation ({last['algo']}) : "
                f"{last['total_distance']:.1f} km, {last['total_time']:.0f} min, "
                f"{last['nb_routes']} tournées"
            )

        conn.close()
    except Exception:
        ctx_parts.append("• (Données non disponibles)")

    # État de la fenêtre
    if main_window:
        page_names = [
            "Dashboard", "Clients", "Véhicules", "Dépôts",
            "Optimisation IA", "Carte", "Suivi Temps Réel", "Scénarios",
            "Traduction IA", "Rapports", "Journal", "Paramètres",
        ]
        idx = main_window.stack.currentIndex() if hasattr(main_window, "stack") else -1
        if 0 <= idx < len(page_names):
            ctx_parts.append(f"• Page active : {page_names[idx]}")
    return "\n".join(ctx_parts)


def build_messages(
    user_message: str,
    history: list[dict],
    main_window=None,
    language: str = "fr",
) -> list[dict]:
    """Construit la liste de messages (system + historique + user) pour Mistral."""
    system_text = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["fr"])
    context = get_app_context(main_window)
    system_content = f"{system_text}\n\n{context}"

    messages: list[dict] = [{"role": "system", "content": system_content}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def send_message(
    user_message: str,
    history: list[dict],
    main_window=None,
    language: str = "fr",
    model: str = DEFAULT_MODEL,
) -> str:
    """Envoie un message à Mistral et renvoie la réponse (bloquant).

    Cette fonction est destinée à être appelée depuis un QThread.
    """
    if not MISTRAL_AVAILABLE:
        raise RuntimeError("Le package 'mistralai' n'est pas installé.")
    if not MISTRAL_API_KEY:
        raise RuntimeError(
            "Clé API Mistral introuvable. Vérifiez le fichier .env "
            f"({_ENV_PATH})."
        )

    client = Mistral(api_key=MISTRAL_API_KEY)
    messages = build_messages(user_message, history, main_window, language)

    response = client.chat.complete(model=model, messages=messages)
    return response.choices[0].message.content
