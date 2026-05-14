"""
mistral_client.py — Client Mistral AI sécurisé
===============================================
 - Clé API : keyring / .env
 - build_context(db_stats) : contexte système sans accès BDD (stats fournies par l'UI)
 - parse_command(response) : actions navigate / optimize / create_order
 - get_fallback_response(question) : réponses locales si API indisponible
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "citypulse_logistics"
KEYRING_USER = "mistral_api_key"


def _load_api_key() -> Optional[str]:
  try:
    import keyring
    key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if key:
      logger.debug("Clé Mistral chargée depuis le keyring OS")
      return key
  except Exception:
    logger.debug("keyring indisponible — fallback .env")

  try:
    from dotenv import load_dotenv
    _env = os.path.join(
      os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
      ".env",
    )
    load_dotenv(_env)
  except Exception:
    logger.debug("dotenv indisponible")

  key = os.getenv("MISTRAL_API_KEY")
  if key:
    logger.debug("Clé Mistral chargée depuis .env")
  return key


def save_api_key(key: str) -> bool:
  try:
    import keyring
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key)
    logger.info("Clé Mistral sauvegardée dans le keyring OS")
    return True
  except Exception:
    logger.exception("Impossible de sauvegarder la clé dans le keyring")
    return False


MISTRAL_API_KEY: Optional[str] = _load_api_key()

try:
  from mistralai.client import Mistral as _MistralSDK
  _HAS_SDK = True
except ImportError:
  _MistralSDK = None  # type: ignore
  _HAS_SDK = False

try:
  import requests as _requests
  _HAS_REQUESTS = True
except ImportError:
  _requests = None  # type: ignore
  _HAS_REQUESTS = False

MISTRAL_AVAILABLE = _HAS_SDK or _HAS_REQUESTS

DEFAULT_MODEL = "mistral-small-latest"

_JSON_CMD_HINT = (
  "Quand l'utilisateur demande une action dans l'application, ajoute en fin de réponse "
  "un bloc JSON sur une ligne : "
  '{"action":"navigate","page_index":0} ou {"action":"optimize"} ou '
  '{"action":"create_order","client_id":123} - uniquement si pertinent.'
)

SYSTEM_PROMPTS: dict = {
  "fr": (
    "Tu es CityPulse Copilot, un assistant expert en logistique urbaine et "
    "optimisation de tournées de véhicules (VRP). Réponds de façon concise, "
    "professionnelle et utile. Utilise les données contextuelles fournies "
    "pour personnaliser tes réponses. Réponds en français.\n" + _JSON_CMD_HINT
  ),
  "en": (
    "You are CityPulse Copilot, an expert assistant in urban logistics and "
    "vehicle routing problem (VRP) optimization. Answer concisely and professionally. "
    "Respond in English.\n" + _JSON_CMD_HINT
  ),
  "ar": (
    "أنت CityPulse Copilot، مساعد خبير في اللوجستيات الحضرية وتحسين مسارات "
    "المركبات (VRP). أجب بإيجاز واحترافية. أجب بالعربية.\n" + _JSON_CMD_HINT
  ),
  "es": (
    "Eres CityPulse Copilot, un asistente experto en logística urbana y "
    "optimización de rutas de vehículos (VRP). Responde en español.\n" + _JSON_CMD_HINT
  ),
  "de": (
    "Du bist CityPulse Copilot, ein Experten-Assistent für urbane Logistik "
    "und VRP-Optimierung. Antworte auf Deutsch.\n" + _JSON_CMD_HINT
  ),
}


def build_context(db_stats: dict) -> str:
  """Formate un bloc de contexte à partir de statistiques réelles (aucune requête SQL ici)."""
  lines = ["=== Contexte applicatif CityPulse (données réelles) ==="]
  if not db_stats:
    lines.append("• (Aucune statistique fournie)")
    return "\n".join(lines)

  if "clients_active" in db_stats:
    lines.append(
      f"• Clients actifs : {db_stats.get('clients_active')} | "
      f"Demande totale : {db_stats.get('total_demand_kg', 0):.0f} kg"
    )
  if "vehicles_total" in db_stats:
    lines.append(
      f"• Véhicules : {db_stats.get('vehicles_total')} "
      f"(disponibles : {db_stats.get('vehicles_available', 0)})"
    )
  if "depots" in db_stats:
    lines.append(f"• Dépôts : {db_stats.get('depots')}")
  last = db_stats.get("last_optimization")
  if last:
    lines.append(
      f"• Dernière optimisation ({last.get('algorithm', '')}) : "
      f"{last.get('total_distance', 0):.1f} km, {last.get('client_count', 0)} clients"
    )
  ap = db_stats.get("active_page")
  if ap:
    lines.append(f"• Page active : {ap}")
  return "\n".join(lines)


def build_messages(
  user_message: str,
  history: list[dict],
  db_stats: Optional[dict] = None,
  language: str = "fr",
) -> list[dict]:
  system_text = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["fr"])
  extra = ""
  if db_stats:
    extra = "\n\n" + build_context(db_stats)
  messages = [{"role": "system", "content": f"{system_text}{extra}"}]
  messages.extend(history)
  messages.append({"role": "user", "content": user_message})
  return messages


def parse_command(response: str) -> Optional[dict[str, Any]]:
  """
  Extrait une commande JSON depuis la réponse modèle.
  Schémas : navigate (page_index ou page), optimize, create_order (client_id optionnel).
  """
  if not response:
    return None
  text = response.strip()
  candidates: list[str] = []

  fence = re.search(r"```(:json)\s*(\{[^`]+\})\s*```", text, re.DOTALL | re.IGNORECASE)
  if fence:
    candidates.append(fence.group(1))

  for m in re.finditer(r"\{[^{}]*\"action\"\s*:\s*\"[^\"]+\"[^{}]*\}", text):
    candidates.append(m.group(0))

  loose = re.search(
    r"\{[\s\S]*\"action\"\s*:\s*\"(navigate|optimize|create_order)\"[\s\S]*\}",
    text,
  )
  if loose:
    candidates.append(loose.group(0))

  for raw in candidates:
    try:
      obj = json.loads(raw)
    except json.JSONDecodeError:
      continue
    action = obj.get("action")
    if action == "navigate":
      out: dict[str, Any] = {"action": "navigate"}
      if "page_index" in obj:
        out["page_index"] = int(obj["page_index"])
      if obj.get("page"):
        out["page"] = str(obj["page"])
      if "page_index" in out or "page" in out:
        return out
    elif action == "optimize":
      return {"action": "optimize"}
    elif action == "create_order":
      out = {"action": "create_order"}
      if "client_id" in obj:
        out["client_id"] = int(obj["client_id"])
      return out
  return None


_FALLBACKS_FR = [
  "Je ne peux pas joindre le service Mistral pour le moment. Vérifiez la clé API dans Paramètres, puis réessayez.",
  "Sans connexion à l'IA, je peux quand même vous rappeler : lancez une optimisation depuis le menu Optimisation (Ctrl+N).",
  "Astuce : chargez des données de démo (Fichier → Charger données de démo) pour tester les scénarios VRP.",
  "Pour réduire les distances, comparez Greedy, 2-opt et OR-Tools sur la page Optimisation.",
  "Les créneaux horaires clients sont pris en compte par OR-Tools en mode standard ou multi-dépôt.",
  "Pensez à géocoder les clients (0,0) avant d'optimiser pour des matrices réalistes.",
  "Le suivi temps réel permet de simuler la journée et détecter les retards sur le Gantt.",
  "Les rapports PDF sont disponibles depuis la page Rapports ou l'export optimisation.",
  "En cas de erreur réseau, vos données restent en local dans citypulse.db.",
  "Réessayez dans quelques instants ; si le problème persiste, utilisez le journal (menu Outils → Journaux).",
]


def get_fallback_response(question: str) -> str:
  """Réponse prédéfinie déterministe si l'API est indisponible."""
  q = (question or "").strip().lower()
  h = int(hashlib.sha256(q.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)
  idx = h % len(_FALLBACKS_FR)
  base = _FALLBACKS_FR[idx]
  if any(k in q for k in ("optim", "vrp", "tournée", "route")):
    return _FALLBACKS_FR[3]
  if any(k in q for k in ("client", "livraison")):
    return _FALLBACKS_FR[5]
  if any(k in q for k in ("carte", "map")):
    return _FALLBACKS_FR[6]
  return base


def send_message(
  user_message: str,
  history: list[dict],
  db_stats: Optional[dict] = None,
  language: str = "fr",
  model: str = DEFAULT_MODEL,
) -> str:
  """Envoie un message à Mistral (bloquant — appeler depuis un QThread).
  Utilise le SDK mistralai si disponible, sinon requests HTTP directement.
  """
  api_key = _load_api_key()
  if not api_key:
    raise RuntimeError(
      "Clé API Mistral introuvable.\n"
      "Allez dans Paramètres > Clé API Mistral pour la configurer."
    )
  messages = build_messages(user_message, history, db_stats, language)

  if _HAS_SDK:
    client = _MistralSDK(api_key=api_key)
    response = client.chat.complete(model=model, messages=messages)
    return response.choices[0].message.content

  if _HAS_REQUESTS:
    resp = _requests.post(
      "https://api.mistral.ai/v1/chat/completions",
      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
      json={"model": model, "messages": messages, "max_tokens": 1024},
      timeout=30,
    )
    if resp.status_code != 200:
      raise RuntimeError(f"Mistral API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]

  raise RuntimeError("Ni 'mistralai' ni 'requests' ne sont disponibles.")


def get_app_context(main_window) -> str:
  """
  Déprécié : ne plus utiliser depuis app/ai pour respecter l'absence de BDD.
  Conservé pour compatibilité ; retourne un message minimal sans SQL.
  """
  _ = main_window
  return build_context({})
