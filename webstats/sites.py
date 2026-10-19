"""Seznam webů: GA4 property (Admin API) spárované s GSC weby podle domény."""
import json
import re

from .auth import ROOT, call
from .util import UsageError

ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
GSC = "https://www.googleapis.com/webmasters/v3"
CACHE = ROOT / ".cache" / "sites.json"


def norm_domain(u):
    u = (u or "").strip().lower()
    if u.startswith("sc-domain:"):
        u = u[len("sc-domain:"):]
    u = re.sub(r"^[a-z]+://", "", u).split("/")[0].split(":")[0]
    return u[4:] if u.startswith("www.") else u


def ga_properties():
    props, token = [], None
    while True:
        params = {"pageSize": 200}
        if token:
            params["pageToken"] = token
        d = call("GET", f"{ADMIN}/accountSummaries", params=params)
        for acc in d.get("accountSummaries", []):
            for p in acc.get("propertySummaries", []):
                props.append({
                    "account": acc.get("displayName"),
                    "property": p["property"].split("/")[-1],
                    "name": p.get("displayName"),
                })
        token = d.get("nextPageToken")
        if not token:
            break
    for p in props:
        streams = call("GET", f"{ADMIN}/properties/{p['property']}/dataStreams", params={"pageSize": 200})
        uris = [s["webStreamData"]["defaultUri"] for s in streams.get("dataStreams", [])
                if s.get("webStreamData", {}).get("defaultUri")]
        p["uris"] = uris
        guess = norm_domain(p["name"]) if "." in (p["name"] or "") and " " not in p["name"] else None
        p["domain"] = norm_domain(uris[0]) if uris else guess
    return props


def gsc_sites():
    d = call("GET", f"{GSC}/sites")
    return [s for s in d.get("siteEntry", []) if s.get("permissionLevel") != "siteUnverifiedUser"]


def build_registry():
    props = ga_properties()
    sites = gsc_sites()
    reg = {}
    for p in props:
        key = p["domain"] or f"ga:{p['property']}"
        e = reg.setdefault(key, {"domain": key, "ga": None, "ga_name": None, "gsc": None, "gsc_all": [], "ga_all": []})
        e["ga_all"].append(p["property"])
        if e["ga"] is None:
            e["ga"], e["ga_name"] = p["property"], p["name"]
    for s in sites:
        key = norm_domain(s["siteUrl"])
        e = reg.setdefault(key, {"domain": key, "ga": None, "ga_name": None, "gsc": None, "gsc_all": [], "ga_all": []})
        e["gsc_all"].append(s["siteUrl"])
    for e in reg.values():
        # doménová property má přednost před URL-prefix
        dom = [u for u in e["gsc_all"] if u.startswith("sc-domain:")]
        e["gsc"] = (dom or e["gsc_all"] or [None])[0]
    out = sorted(reg.values(), key=lambda e: e["domain"])
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
    return out


def registry(refresh=False):
    if not refresh and CACHE.exists():
        return json.loads(CACHE.read_text("utf-8"))
    return build_registry()


def resolve(query, need):
    """Najde web podle (části) domény. need = 'ga' nebo 'gsc'."""
    if need == "ga" and query.isdigit():
        return {"domain": f"ga:{query}", "ga": query}
    if need == "gsc" and (query.startswith("sc-domain:") or query.startswith("http")):
        hit = [e for e in registry() if query in e["gsc_all"]]
        if hit:
            return {**hit[0], "gsc": query}
    q = norm_domain(query)
    reg = registry()
    cands = [e for e in reg if e["domain"] == q] or [e for e in reg if q in e["domain"]]
    cands = [e for e in cands if e.get(need)]
    if len(cands) == 1:
        return cands[0]
    if not cands:
        raise UsageError(f"Web '{query}' nemá {need.upper()} (zkus `check` pro obnovení seznamu).")
    raise UsageError(f"'{query}' odpovídá víc webům: " + ", ".join(e["domain"] for e in cands))
