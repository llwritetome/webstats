"""Google Search updaty a incidenty ze status.search.google.com."""
import datetime as dt

import requests

URL = "https://status.search.google.com/incidents.json"


def incidents(start, end):
    """Incidenty, které se překrývají s obdobím <start, end> (data)."""
    data = requests.get(URL, timeout=30).json()
    out = []
    for i in data:
        b = dt.datetime.fromisoformat(i["begin"]).date()
        e = dt.datetime.fromisoformat(i["end"]).date() if i.get("end") else None
        if b <= end and (e is None or e >= start):
            out.append({
                "begin": b, "end": e, "name": i.get("external_desc"), "service": i.get("service_name"),
                "status": (i.get("most_recent_update") or {}).get("text", "").strip(),
                "url": "https://status.search.google.com/" + i.get("uri", ""),
            })
    return sorted(out, key=lambda x: x["begin"])
