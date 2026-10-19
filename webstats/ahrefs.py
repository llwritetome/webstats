"""Ahrefs API v3.

Každý požadavek stojí API units (min. 50), dotazy na ahrefs.com / wordcount.com
jsou zdarma (na testování). Proto: vždy `select` jen s potřebnými poli,
rozumný `limit` a u velkých dotazů nejdřív odhad a potvrzení (--yes).
"""
import os

import requests

from .auth import ROOT
from .util import UsageError, warn

BASE = "https://api.ahrefs.com/v3"
FREE_TARGETS = {"ahrefs.com", "wordcount.com"}
MIN_UNITS = 50
UNITS_PER_FIELD = 5  # naměřeno: řádek s 5 poli stojí 14–23 units (hlavička x-api-units-cost-row)
CONFIRM_UNITS = int(os.environ.get("AHREFS_CONFIRM_UNITS", "1000"))


def api_key():
    key = os.environ.get("AHREFS_API_KEY", "").strip()
    # Windows Poznámkový blok rád přidá .txt, proto i varianty .env.txt
    for env in (ROOT / ".env", ROOT / "secrets" / ".env", ROOT / ".env.txt", ROOT / "secrets" / ".env.txt"):
        if key or not env.exists():
            continue
        for line in env.read_text("utf-8-sig").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "AHREFS_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key:
        raise UsageError("Chybí AHREFS_API_KEY (proměnná prostředí nebo řádek AHREFS_API_KEY=... v .env / secrets/.env).")
    return key


def is_free(target):
    t = (target or "").lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
    return t in FREE_TARGETS


def estimate(requests_plan):
    """Horní odhad units: pro každý požadavek max(50, řádky × pole × 5)."""
    total = 0
    for target, rows, fields in requests_plan:
        if not is_free(target):
            total += max(MIN_UNITS, rows * fields * UNITS_PER_FIELD)
    return total


def guard(requests_plan, yes):
    units = estimate(requests_plan)
    n = len(requests_plan)
    warn(f"Ahrefs: {n} požadavek/ů, odhad ≈ {units} units (min. {MIN_UNITS} za požadavek, zdarma pro ahrefs.com).")
    if units > CONFIRM_UNITS and not yes:
        raise UsageError(f"Odhad {units} units je nad limitem {CONFIRM_UNITS}. Potvrď spuštění přidáním --yes.")


def get(endpoint, **params):
    params = {k: v for k, v in params.items() if v not in (None, "")}
    r = requests.get(f"{BASE}/{endpoint.lstrip('/')}", params=params, timeout=120,
                     headers={"Authorization": f"Bearer {api_key()}", "Accept": "application/json"})
    unit_headers = {k: v for k, v in r.headers.items() if "unit" in k.lower()}
    if unit_headers:
        warn("Ahrefs units: " + ", ".join(f"{k}={v}" for k, v in unit_headers.items()))
    try:
        data = r.json()
    except ValueError:
        data = {"error": r.text[:500]}
    if r.status_code >= 400:
        raise UsageError(f"Ahrefs {r.status_code} {endpoint}: {data.get('error', data)}")
    return data
