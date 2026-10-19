"""GA4 Data API."""
from .auth import call
from .util import parse_filter, warn

DATA = "https://analyticsdata.googleapis.com/v1beta"

_MATCH = {"eq": "EXACT", "neq": "EXACT", "contains": "CONTAINS", "ncontains": "CONTAINS",
          "regex": "PARTIAL_REGEXP", "nregex": "PARTIAL_REGEXP", "begins": "BEGINS_WITH"}


def build_filter(filters=(), exclude_countries=()):
    exprs = []
    for f in filters:
        dim, op, val = parse_filter(f)
        e = {"filter": {"fieldName": dim, "stringFilter": {"matchType": _MATCH[op], "value": val, "caseSensitive": False}}}
        exprs.append({"notExpression": e} if op.startswith("n") else e)
    for c in exclude_countries:
        exprs.append({"notExpression": {"filter": {"fieldName": "country", "stringFilter": {"matchType": "EXACT", "value": c}}}})
    if not exprs:
        return None
    return exprs[0] if len(exprs) == 1 else {"andGroup": {"expressions": exprs}}


def report(prop, start, end, dims, metrics, dim_filter=None, limit=10000, order=None):
    """Vrátí [(tuple dimenzí, {metrika: float})]."""
    body = {
        "dateRanges": [{"startDate": str(start), "endDate": str(end)}],
        "dimensions": [{"name": d} for d in dims],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
        "orderBys": order or [{"metric": {"metricName": metrics[0]}, "desc": True}],
    }
    if dim_filter:
        body["dimensionFilter"] = dim_filter
    d = call("POST", f"{DATA}/properties/{prop}:runReport", json=body)
    meta = d.get("metadata", {})
    if meta.get("dataLossFromOtherRow"):
        warn(f"GA {prop}: část řádků je sloučena do (other) – zkrať období nebo uber dimenze.")
    if meta.get("samplingMetadatas"):
        warn(f"GA {prop}: data jsou vzorkovaná.")
    rows = []
    for r in d.get("rows", []):
        key = tuple(v.get("value", "") for v in r.get("dimensionValues", []))
        rows.append((key, {m: float(v.get("value") or 0) for m, v in zip(metrics, r.get("metricValues", []))}))
    return rows


def total(prop, start, end, metric="sessions", dim_filter=None):
    rows = report(prop, start, end, [], [metric], dim_filter, limit=1, order=[])
    return rows[0][1][metric] if rows else 0.0
