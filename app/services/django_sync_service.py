"""
django_sync_service.py — Appels HTTP vers API Django CityPulse (sans Qt).
Header : X-CityPulse-Secret
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
  import requests
  from requests.exceptions import HTTPError, RequestException

  HAS_REQUESTS = True
except ImportError: # pragma: no cover
  requests = None # type: ignore

  class HTTPError(Exception):
    pass

  class RequestException(Exception):
    pass

  HAS_REQUESTS = False


def get_django_service() -> "DjangoSyncService":
  """Construit un DjangoSyncService depuis settings.json + keyring."""
  import json, os
  try:
    from app.paths import settings_json_path
    path = settings_json_path()
  except Exception:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "settings.json")
  url = ""
  try:
    with open(path, encoding="utf-8") as f:
      cfg = json.load(f)
    url = cfg.get("django", {}).get("url", "")
  except Exception:
    pass
  secret = ""
  try:
    import keyring
    secret = keyring.get_password("citypulse_django", "django_api_secret") or ""
  except Exception:
    pass
  return DjangoSyncService(url, secret)


class DjangoSyncService:
  """Client synchro : health, push clients/routes, pull confirmations/proofs."""

  def __init__(self, base_url: str, secret_key: str):
    self.base_url = (base_url or "").strip().rstrip("/")
    self.secret_key = (secret_key or "").strip()

  def _headers(self, json_body: bool = False) -> dict[str, str]:
    h = {"X-CityPulse-Secret": self.secret_key}
    if json_body:
      h["Content-Type"] = "application/json"
    return h

  def health_check(self) -> bool:
    if not HAS_REQUESTS or not self.base_url or not self.secret_key:
      return False
    try:
      r = requests.get(
        f"{self.base_url}/api/health/",
        headers=self._headers(),
        timeout=10,
      )
      return r.status_code == 200
    except RequestException as e:
      logger.debug("health_check: %s", e)
      return False

  def sync_clients(self, clients_data: list[dict] | dict) -> dict[str, Any]:
    if not HAS_REQUESTS or not self.base_url or not self.secret_key:
      return {"ok": False, "error": "missing_url_secret_or_requests"}
    payload: Any = (
      clients_data if isinstance(clients_data, dict) else {"clients": clients_data}
    )
    try:
      r = requests.post(
        f"{self.base_url}/api/sync/clients/",
        headers=self._headers(json_body=True),
        json=payload,
        timeout=10,
      )
      r.raise_for_status()
      if r.content:
        try:
          return {"ok": True, "data": r.json()}
        except Exception:
          return {"ok": True, "data": r.text}
      return {"ok": True, "data": None}
    except HTTPError as e:
      body = ""
      if e.response is not None:
        try:
          body = e.response.text[:500]
        except Exception:
          body = str(e)
      return {
        "ok": False,
        "error": str(e),
        "status": getattr(e.response, "status_code", None),
        "body": body,
      }
    except RequestException as e:
      return {"ok": False, "error": str(e)}

  def sync_routes(self, routes_data: list[dict] | dict) -> dict[str, Any]:
    if not HAS_REQUESTS or not self.base_url or not self.secret_key:
      return {"ok": False, "error": "missing_url_secret_or_requests"}
    payload: Any = (
      routes_data if isinstance(routes_data, dict) else {"routes": routes_data}
    )
    try:
      r = requests.post(
        f"{self.base_url}/api/sync/routes/",
        headers=self._headers(json_body=True),
        json=payload,
        timeout=10,
      )
      r.raise_for_status()
      if r.content:
        try:
          return {"ok": True, "data": r.json()}
        except Exception:
          return {"ok": True, "data": r.text}
      return {"ok": True, "data": None}
    except HTTPError as e:
      body = ""
      if e.response is not None:
        try:
          body = e.response.text[:500]
        except Exception:
          body = str(e)
      return {
        "ok": False,
        "error": str(e),
        "status": getattr(e.response, "status_code", None),
        "body": body,
      }
    except RequestException as e:
      return {"ok": False, "error": str(e)}

  def pull_confirmations(self) -> list[dict]:
    if not HAS_REQUESTS or not self.base_url or not self.secret_key:
      return []
    try:
      r = requests.get(
        f"{self.base_url}/api/deliveries/confirmations/",
        headers=self._headers(),
        timeout=10,
      )
      r.raise_for_status()
      data = r.json()
      if isinstance(data, list):
        return data
      if isinstance(data, dict):
        for k in ("results", "confirmations", "data", "items"):
          v = data.get(k)
          if isinstance(v, list):
            return v
      return []
    except HTTPError as e:
      logger.warning("pull_confirmations HTTPError: %s", e)
      return []
    except RequestException as e:
      logger.warning("pull_confirmations: %s", e)
      return []

  def create_web_user(self, desktop_id: int, role: str, first_name: str,
                       last_name: str, email: str = "", password: str = "") -> dict[str, Any]:
    if not HAS_REQUESTS or not self.base_url or not self.secret_key:
      return {"ok": False, "error": "missing_url_secret_or_requests"}
    import secrets, string, unicodedata
    if not password:
      alphabet = string.ascii_letters + string.digits
      password = "".join(secrets.choice(alphabet) for _ in range(10))
    def _slug(s: str) -> str:
      s = unicodedata.normalize("NFD", s)
      s = "".join(c for c in s if unicodedata.category(c) != "Mn")
      return "".join(c for c in s.lower() if c.isalnum())
    username = (_slug(first_name) + "." + _slug(last_name)).strip(".")
    if not username:
      username = f"{role}{desktop_id}"
    try:
      r = requests.post(
        f"{self.base_url}/api/users/create/",
        headers=self._headers(json_body=True),
        json={
          "username": username,
          "password": password,
          "role": role,
          "first_name": first_name,
          "last_name": last_name,
          "email": email,
          "desktop_id": desktop_id,
        },
        timeout=10,
      )
      r.raise_for_status()
      result = r.json()
      result["_password"] = password
      return result
    except HTTPError as e:
      body = ""
      if e.response is not None:
        try:
          body = e.response.json().get("error", e.response.text[:200])
        except Exception:
          body = str(e)
      return {"ok": False, "error": body}
    except RequestException as e:
      return {"ok": False, "error": str(e)}

  def pull_proofs(self) -> list[dict]:
    if not HAS_REQUESTS or not self.base_url or not self.secret_key:
      return []
    try:
      r = requests.get(
        f"{self.base_url}/api/deliveries/proofs/",
        headers=self._headers(),
        timeout=10,
      )
      r.raise_for_status()
      data = r.json()
      if isinstance(data, list):
        return data
      if isinstance(data, dict):
        for k in ("results", "proofs", "data", "items"):
          v = data.get(k)
          if isinstance(v, list):
            return v
      return []
    except HTTPError as e:
      logger.warning("pull_proofs HTTPError: %s", e)
      return []
    except RequestException as e:
      logger.warning("pull_proofs: %s", e)
      return []

  def push_delivery_tracking(self, orders: list[dict]) -> dict[str, Any]:
    """
    Pousse les infos de suivi initiales vers le portail web (statut assigned + ETA + chauffeur).
    Appelé depuis save_plan() pour que les clients voient leur commande dès la confirmation.
    orders : liste de {order_ref, order_id_ext, status, driver_first_name, eta}
    """
    if not HAS_REQUESTS or not self.base_url or not self.secret_key:
      return {"ok": False, "error": "missing_url_secret_or_requests"}
    ok = 0
    errors = 0
    for o in orders:
      try:
        r = requests.post(
          f"{self.base_url}/api/deliveries/confirm/",
          headers=self._headers(json_body=True),
          json=o,
          timeout=10,
        )
        r.raise_for_status()
        ok += 1
      except Exception as e:
        logger.warning("push_delivery_tracking: %s — %s", o.get("order_ref"), e)
        errors += 1
    return {"ok": True, "pushed": ok, "errors": errors}
