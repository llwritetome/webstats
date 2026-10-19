"""Přihlášení přes service account a společné volání Google API.

Klíč se bere z proměnné GA_SERVICE_ACCOUNT_JSON (JSON nebo base64),
jinak ze souboru secrets/ga-service-account.json (případně jediného
service-account JSONu v secrets/). Obsah klíče se nikdy nevypisuje.
"""
import base64
import json
import os
import time
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


class AuthError(RuntimeError):
    pass


class ApiError(RuntimeError):
    pass


def _is_service_account(path):
    try:
        return json.loads(path.read_text("utf-8")).get("type") == "service_account"
    except (OSError, ValueError, AttributeError):
        return False


def _load_info():
    raw = os.environ.get("GA_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        if not raw.startswith("{"):
            try:
                raw = base64.b64decode(raw).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                raise AuthError("GA_SERVICE_ACCOUNT_JSON není platný JSON ani base64.") from None
        try:
            return json.loads(raw), "proměnná GA_SERVICE_ACCOUNT_JSON"
        except ValueError:
            raise AuthError("GA_SERVICE_ACCOUNT_JSON neobsahuje platný JSON.") from None

    path = SECRETS / "ga-service-account.json"
    if not path.exists():
        candidates = [p for p in sorted(SECRETS.glob("*.json")) if _is_service_account(p)] if SECRETS.is_dir() else []
        if len(candidates) != 1:
            raise AuthError(
                "Chybí klíč: nastav GA_SERVICE_ACCOUNT_JSON nebo ulož klíč do secrets/ga-service-account.json."
            )
        path = candidates[0]
    try:
        return json.loads(path.read_text("utf-8")), f"soubor {path.relative_to(ROOT).as_posix()}"
    except ValueError:
        raise AuthError(f"{path.name} není platný JSON.") from None


_session = None
key_source = None


def session():
    global _session, key_source
    if _session is None:
        info, key_source = _load_info()
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        _session = AuthorizedSession(creds)
    return _session


def call(method, url, retries=4, **kw):
    """Zavolá Google API a vrátí JSON; při 429/5xx to zkusí znovu."""
    for attempt in range(retries + 1):
        r = session().request(method, url, timeout=120, **kw)
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(2 ** attempt * 2)
            continue
        if r.status_code >= 400:
            try:
                msg = r.json().get("error", {}).get("message") or r.text[:500]
            except ValueError:
                msg = r.text[:500]
            raise ApiError(f"{r.status_code} {method} {url.split('?')[0]}: {msg}")
        return r.json() if r.content else {}
