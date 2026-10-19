"""Google Search Console: Search Analytics a URL Inspection."""
import re
from urllib.parse import quote

from .auth import call
from .util import parse_filter

GSC = "https://www.googleapis.com/webmasters/v3"
INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
METRICS = ["clicks", "impressions", "ctr", "position"]

_OPS = {"eq": "equals", "neq": "notEquals", "contains": "contains", "ncontains": "notContains",
        "regex": "includingRegex", "nregex": "excludingRegex"}


def build_filters(filters=()):
    out = []
    for f in filters:
        dim, op, val = parse_filter(f)
        if dim == "country":
            val = val.lower()
        if op == "begins":
            out.append({"dimension": dim, "operator": "includingRegex", "expression": "^" + re.escape(val)})
        else:
            out.append({"dimension": dim, "operator": _OPS[op], "expression": val})
    return out


def query(site, start, end, dims, filters=None, limit=25000, search_type="web", data_state="final"):
    """Vrátí [(tuple klíčů, {clicks, impressions, ctr, position})], stránkuje po 25 000."""
    rows, start_row = [], 0
    url = f"{GSC}/sites/{quote(site, safe='')}/searchAnalytics/query"
    while len(rows) < limit:
        batch_size = min(25000, limit - len(rows))
        body = {"startDate": str(start), "endDate": str(end), "dimensions": dims, "rowLimit": batch_size,
                "startRow": start_row, "type": search_type, "dataState": data_state}
        if filters:
            body["dimensionFilterGroups"] = [{"groupType": "and", "filters": filters}]
        batch = call("POST", url, json=body).get("rows", [])
        rows += [(tuple(r.get("keys", [])), {m: float(r.get(m, 0)) for m in METRICS}) for r in batch]
        if len(batch) < batch_size:
            break
        start_row += len(batch)
    return rows


def total(site, start, end, filters=None):
    rows = query(site, start, end, [], filters, limit=1)
    return rows[0][1] if rows else {m: 0.0 for m in METRICS}


def inspect(site, url):
    d = call("POST", INSPECT, json={"inspectionUrl": url, "siteUrl": site, "languageCode": "cs"})
    return d.get("inspectionResult", {})
