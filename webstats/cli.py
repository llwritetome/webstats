"""CLI: py -m webstats <příkaz> --help"""
import argparse
import datetime as dt
import sys

import requests

from . import ahrefs, auth, ga, gsc, sites, updates
from .auth import ApiError, AuthError
from .util import (PERCENT_METRICS, UsageError, add_period_args, dump_json, fmt_delta, fmt_int, fmt_metric, fmt_pct,
                   periods, table, today, warn)

GA_LAG, GSC_LAG = 1, 3  # poslední dokončený den: GA včera, GSC před 3 dny
PCT_LIKE = PERCENT_METRICS | {"position"}
ORGANIC = "sessionDefaultChannelGroup==Organic Search"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _check_end(p, lag, source):
    if p.end > today() - dt.timedelta(days=lag):
        warn(f"{source}: období končí {p.end}, data za poslední {lag} d můžou být neúplná.")


def _merge(cur, prev):
    """[(key, cur_metrics, prev_metrics)] přes sjednocení klíčů, v pořadí cur."""
    prev_map = dict(prev)
    out = [(k, m, prev_map.pop(k, {})) for k, m in cur]
    out += [(k, {}, m) for k, m in prev_map.items()]
    return out


# ---------------------------------------------------------------- check

def cmd_check(args):
    reg = sites.build_registry()
    print(f"Klíč: {auth.key_source}\n")
    table(["#", "doména", "GA4 property", "GA název", "GSC web"],
          [[i, e["domain"], e["ga"] or "—", e["ga_name"] or "", e["gsc"] or "—"] for i, e in enumerate(reg, 1)],
          right={0})
    n_ga = sum(1 for e in reg if e["ga"])
    n_gsc = sum(1 for e in reg if e["gsc"])
    print(f"\n{len(reg)} webů, {n_ga} s GA4, {n_gsc} s GSC.")
    for e in reg:
        if len(e["ga_all"]) > 1:
            warn(f"{e['domain']}: víc GA property {e['ga_all']}, používám {e['ga']}")
        if not e["ga"] or not e["gsc"]:
            warn(f"{e['domain']}: chybí {'GA4' if not e['ga'] else 'GSC'}")


# ---------------------------------------------------------------- traffic

def cmd_traffic(args):
    p = periods(args, GA_LAG)
    _check_end(p, GA_LAG, "GA")
    filters = ([ORGANIC] if args.organic else []) + args.filter
    flt = ga.build_filter(filters, args.exclude_country)
    rows, sum_cur, sum_prev = [], 0, 0
    for e in sites.registry():
        if not e["ga"]:
            continue
        try:
            cur = ga.total(e["ga"], p.start, p.end, args.metric, flt)
            prev = ga.total(e["ga"], p.prev_start, p.prev_end, args.metric, flt) if p.has_prev else None
        except ApiError as ex:
            warn(f"{e['domain']}: {ex}")
            continue
        sum_cur += cur
        sum_prev += prev or 0
        rows.append((e["domain"], cur, prev))
    if args.json:
        return dump_json([{"domain": d, "current": c, "previous": pr} for d, c, pr in rows])
    title = f"{args.metric}{' – Organic Search' if args.organic else ''}"
    if args.exclude_country:
        title += f" bez {', '.join(args.exclude_country)}"
    print(f"{title}: {p.label()}\n")
    if p.has_prev:
        rows.sort(key=lambda r: (r[1] - r[2]))
        table(["web", "předch.", "teď", "Δ", "Δ %"],
              [[d, fmt_int(pr), fmt_int(c), fmt_delta(c, pr), fmt_pct(c, pr)] for d, c, pr in rows]
              + [["CELKEM", fmt_int(sum_prev), fmt_int(sum_cur), fmt_delta(sum_cur, sum_prev), fmt_pct(sum_cur, sum_prev)]])
    else:
        rows.sort(key=lambda r: -r[1])
        table(["web", "teď"], [[d, fmt_int(c)] for d, c, _ in rows] + [["CELKEM", fmt_int(sum_cur)]])


# ---------------------------------------------------------------- ga / gsc

def _print_report(dims, metrics, merged, has_prev, limit, sort_delta):
    m0 = metrics[0]
    if sort_delta and has_prev:
        merged.sort(key=lambda r: r[1].get(m0, 0) - r[2].get(m0, 0))
    headers, right = list(dims), set()
    for m in metrics:
        headers += [m, f"{m} předch.", "Δ %" if m not in PCT_LIKE else "Δ"] if has_prev else [m]
    rows = []
    for k, c, pr in merged[:limit]:
        r = list(k)
        for m in metrics:
            r.append(fmt_metric(m, c.get(m)))
            if has_prev:
                r.append(fmt_metric(m, pr.get(m)))
                r.append(fmt_delta(c.get(m), pr.get(m), m) if m in PCT_LIKE else fmt_pct(c.get(m), pr.get(m)))
        rows.append(r)
    right = set(range(len(dims), len(headers)))
    table(headers, rows, right)
    if len(merged) > limit:
        print(f"… a dalších {len(merged) - limit} řádků (--limit)")


def _json_rows(dims, merged):
    return [{**dict(zip(dims, k)), "current": c, "previous": pr} for k, c, pr in merged]


def cmd_ga(args):
    site = sites.resolve(args.site, "ga")
    p = periods(args, GA_LAG)
    _check_end(p, GA_LAG, "GA")
    dims = [d for d in args.dims.split(",") if d]
    metrics = [m for m in args.metrics.split(",") if m]
    flt = ga.build_filter(([ORGANIC] if args.organic else []) + args.filter, args.exclude_country)
    cur = ga.report(site["ga"], p.start, p.end, dims, metrics, flt, args.fetch)
    prev = ga.report(site["ga"], p.prev_start, p.prev_end, dims, metrics, flt, args.fetch) if p.has_prev else []
    merged = _merge(cur, prev)
    if args.json:
        return dump_json(_json_rows(dims, merged))
    print(f"GA4 {site['domain']} ({site['ga']}): {p.label()}\n")
    _print_report(dims, metrics, merged, p.has_prev, args.limit, args.sort == "delta")


def cmd_gsc(args):
    site = sites.resolve(args.site, "gsc")
    p = periods(args, GSC_LAG)
    _check_end(p, GSC_LAG, "GSC")
    dims = [d for d in args.dims.split(",") if d]
    flt = gsc.build_filters(args.filter)
    kw = dict(limit=args.fetch, search_type=args.type)
    cur = gsc.query(site["gsc"], p.start, p.end, dims, flt, **kw)
    prev = gsc.query(site["gsc"], p.prev_start, p.prev_end, dims, flt, **kw) if p.has_prev else []
    merged = _merge(cur, prev)
    if args.json:
        return dump_json(_json_rows(dims, merged))
    print(f"GSC {site['gsc']}: {p.label()}\n")
    _print_report(dims, gsc.METRICS, merged, p.has_prev, args.limit, args.sort == "delta")


# ---------------------------------------------------------------- drill

def _drill_table(name, merged, metric, total_delta, top, gains, extra=None):
    merged = [r for r in merged if (r[1].get(metric, 0) - r[2].get(metric, 0)) != 0]
    merged.sort(key=lambda r: r[1].get(metric, 0) - r[2].get(metric, 0), reverse=gains)
    rows = []
    for k, c, pr in merged[:top]:
        d = c.get(metric, 0) - pr.get(metric, 0)
        share = f"{d / total_delta * 100:.0f} %" if total_delta and (d * total_delta) > 0 else ""
        r = [" | ".join(k), fmt_int(pr.get(metric, 0)), fmt_int(c.get(metric, 0)), fmt_delta(c.get(metric), pr.get(metric)),
             fmt_pct(c.get(metric), pr.get(metric)), share]
        rows.append(r + (extra(c, pr) if extra else []))
    print(f"\n## {name}")
    headers = [name, "předch.", "teď", "Δ", "Δ %", "podíl na Δ"]
    if extra:
        headers += ["zobrazení Δ %", "pozice"]
    table(headers, rows) if rows else print("(beze změn)")


def cmd_ga_drill(args):
    site = sites.resolve(args.site, "ga")
    p = periods(args, GA_LAG)
    if not p.has_prev:
        raise UsageError("Drill potřebuje srovnání (--compare).")
    _check_end(p, GA_LAG, "GA")
    flt = ga.build_filter(([ORGANIC] if args.organic else []) + args.filter, args.exclude_country)
    m = args.metric
    cur_t = ga.total(site["ga"], p.start, p.end, m, flt)
    prev_t = ga.total(site["ga"], p.prev_start, p.prev_end, m, flt)
    print(f"GA4 {site['domain']}: {m} {p.label()}")
    print(f"Celkem: {fmt_int(prev_t)} → {fmt_int(cur_t)}  ({fmt_delta(cur_t, prev_t)}, {fmt_pct(cur_t, prev_t)})")
    for dim in args.dims.split(","):
        cur = ga.report(site["ga"], p.start, p.end, [dim], [m], flt, 10000)
        prev = ga.report(site["ga"], p.prev_start, p.prev_end, [dim], [m], flt, 10000)
        _drill_table(dim, _merge(cur, prev), m, cur_t - prev_t, args.top, args.gains)


def cmd_gsc_drill(args):
    site = sites.resolve(args.site, "gsc")
    p = periods(args, GSC_LAG)
    if not p.has_prev:
        raise UsageError("Drill potřebuje srovnání (--compare).")
    _check_end(p, GSC_LAG, "GSC")
    flt = gsc.build_filters(args.filter)
    cur_t = gsc.total(site["gsc"], p.start, p.end, flt)
    prev_t = gsc.total(site["gsc"], p.prev_start, p.prev_end, flt)
    print(f"GSC {site['gsc']}: {p.label()}")
    for m in gsc.METRICS:
        print(f"  {m:12} {fmt_metric(m, prev_t[m]):>12} → {fmt_metric(m, cur_t[m]):>12}  "
              f"{fmt_pct(cur_t[m], prev_t[m]) if m in ('clicks', 'impressions') else fmt_delta(cur_t[m], prev_t[m], m)}")

    def extra(c, pr):
        pos = f"{pr['position']:.1f} → {c['position']:.1f}" if c.get("position") and pr.get("position") else ""
        return [fmt_pct(c.get("impressions"), pr.get("impressions")), pos]

    for dim in args.dims.split(","):
        cur = gsc.query(site["gsc"], p.start, p.end, [dim], flt, limit=args.fetch)
        prev = gsc.query(site["gsc"], p.prev_start, p.prev_end, [dim], flt, limit=args.fetch)
        _drill_table(dim, _merge(cur, prev), "clicks", cur_t["clicks"] - prev_t["clicks"], args.top, args.gains, extra)


# ---------------------------------------------------------------- gsc-pages

def http_status(url):
    try:
        r = requests.get(url, allow_redirects=False, timeout=20, stream=True, headers={"User-Agent": UA})
        r.close()
        return r.status_code, r.headers.get("Location")
    except requests.RequestException as ex:
        return None, type(ex).__name__


def diagnose(site, url, cur, prev):
    code, info = http_status(url)
    out = {"http": code}
    if code is None:
        return {**out, "cause": f"nedostupná ({info})"}
    if code >= 400:
        return {**out, "cause": f"HTTP {code}"}
    if 300 <= code < 400:
        return {**out, "cause": f"přesměrování {code} → {info}"}
    try:
        res = gsc.inspect(site, url).get("indexStatusResult", {})
    except ApiError as ex:
        return {**out, "cause": f"HTTP {code}, inspekce selhala: {ex}"}
    out.update(verdict=res.get("verdict"), coverage=res.get("coverageState"),
               last_crawl=res.get("lastCrawlTime"), google_canonical=res.get("googleCanonical"))
    if res.get("verdict") != "PASS":
        return {**out, "cause": f"není v indexu: {res.get('coverageState') or res.get('verdict')}"}
    canon = res.get("googleCanonical")
    if canon and canon.rstrip("/") != url.rstrip("/"):
        return {**out, "cause": f"Google zvolil jinou kanonickou: {canon}"}
    if not cur.get("impressions"):
        return {**out, "cause": "DMCA / ruční odstranění?"}
    pos = f"{prev.get('position', 0):.1f} → {cur.get('position', 0):.1f}"
    return {**out, "cause": f"v indexu, pozice {pos}, zobrazení {fmt_pct(cur.get('impressions'), prev.get('impressions'))}"}


def cmd_gsc_pages(args):
    p = periods(args, GSC_LAG)
    if not p.has_prev:
        raise UsageError("gsc-pages potřebuje srovnání (--compare).")
    _check_end(p, GSC_LAG, "GSC")
    targets = [sites.resolve(s, "gsc") for s in args.site] if args.site else [e for e in sites.registry() if e["gsc"]]
    report = []
    print(f"Stránky s propadem na ~0 / prudkým růstem: {p.label()}")
    for e in targets:
        site = e["gsc"]
        try:
            cur = {k[0]: m for k, m in gsc.query(site, p.start, p.end, ["page"], limit=args.fetch)}
            prev = {k[0]: m for k, m in gsc.query(site, p.prev_start, p.prev_end, ["page"], limit=args.fetch)}
        except ApiError as ex:
            warn(f"{site}: {ex}")
            continue
        empty = {"clicks": 0.0, "impressions": 0.0}
        dropped = [(u, cur.get(u, empty), m) for u, m in prev.items()
                   if m["clicks"] >= args.min_clicks and cur.get(u, empty)["clicks"] <= m["clicks"] * args.drop_ratio]
        grown = [(u, m, prev.get(u, empty)) for u, m in cur.items()
                 if m["clicks"] >= args.min_clicks and m["clicks"] >= max(prev.get(u, empty)["clicks"], 1) * args.grow_factor]
        dropped.sort(key=lambda r: -r[2]["clicks"])
        grown.sort(key=lambda r: -(r[1]["clicks"] - r[2]["clicks"]))
        if not dropped and not grown:
            continue
        print(f"\n# {e['domain']}  ({site})  – spadlo {len(dropped)}, vyrostlo {len(grown)}")
        site_rep = {"site": site, "dropped": [], "grown": []}
        if dropped:
            rows = []
            for i, (u, c, pr) in enumerate(dropped[:args.top]):
                d = diagnose(site, u, c, pr) if i < args.inspect else {"cause": "(neověřeno, --inspect)"}
                site_rep["dropped"].append({"url": u, "current": c, "previous": pr, **d})
                rows.append([u, fmt_int(pr["clicks"]), fmt_int(c["clicks"]), fmt_int(c.get("impressions", 0)), d["cause"]])
            print("\nSpadlé:")
            table(["URL", "kliky předch.", "teď", "zobrazení teď", "příčina"], rows, right={1, 2, 3})
        if grown:
            rows = []
            for u, c, pr in grown[:args.top]:
                site_rep["grown"].append({"url": u, "current": c, "previous": pr})
                rows.append([u, fmt_int(pr["clicks"]), fmt_int(c["clicks"]), fmt_pct(c["clicks"], pr["clicks"]),
                             f"{pr['position']:.1f} → {c['position']:.1f}" if pr.get("position") else f"nová, {c['position']:.1f}"])
            print("\nVyrostlé:")
            table(["URL", "kliky předch.", "teď", "Δ %", "pozice"], rows)
        report.append(site_rep)
    if args.json:
        dump_json(report)


# ---------------------------------------------------------------- updates

def cmd_updates(args):
    p = periods(args, 0)
    items = updates.incidents(p.start, p.end)
    if args.json:
        return dump_json(items)
    print(f"Google Search incidenty a updaty {p.start} – {p.end}:\n")
    if not items:
        return print("(žádné)")
    table(["začátek", "konec", "služba", "název", "stav"],
          [[i["begin"], i["end"] or "probíhá", i["service"], i["name"], i["status"][:80]] for i in items], right=set())


# ---------------------------------------------------------------- ahrefs

def _ahrefs_print(data, fields):
    lists = [v for v in data.values() if isinstance(v, list)]
    if lists:
        rows = lists[0]
        cols = fields or (list(rows[0].keys()) if rows else [])
        table(cols, [[r.get(c) for c in cols] for r in rows], right=set())
    else:
        dump_json(data)


def cmd_ahrefs(args):
    a = args.action
    target = args.target
    date = args.date or str(today() - dt.timedelta(days=1))
    common = dict(mode=args.mode, protocol="both")
    if a == "limits":
        return dump_json(ahrefs.get("subscription-info/limits-and-usage"))
    if not target and a != "raw":
        raise UsageError("Zadej cíl, např. `ahrefs overview punishworld.com`.")
    targets = [target] + (args.vs or [])

    if a == "overview":
        ahrefs.guard([(t, 1, 1) for t in targets for _ in range(3)], args.yes)
        rows = []
        for t in targets:
            m = ahrefs.get("site-explorer/metrics", target=t, date=date, country=args.country, **common).get("metrics", {})
            dr = ahrefs.get("site-explorer/domain-rating", target=t, date=date).get("domain_rating", {})
            bl = ahrefs.get("site-explorer/backlinks-stats", target=t, date=date, **common).get("metrics", {})
            rows.append([t, dr.get("domain_rating"), dr.get("ahrefs_rank"), fmt_int(m.get("org_traffic") or 0),
                         fmt_int(m.get("org_keywords") or 0), fmt_int(m.get("org_keywords_1_3") or 0),
                         fmt_int(bl.get("live_refdomains") or 0), fmt_int(bl.get("live") or 0)])
        print(f"Ahrefs k {date}{' (' + args.country + ')' if args.country else ''}:\n")
        return table(["web", "DR", "Ahrefs rank", "org. traffic", "klíč. slova", "TOP3", "refdomény", "backlinky"], rows)

    if a == "history":
        start = str(today() - dt.timedelta(days=30 * args.months))
        fields = ["date", "org_traffic"]
        ahrefs.guard([(t, args.months, len(fields)) for t in targets] + [(t, args.months, 2) for t in targets], args.yes)
        series = {}
        for t in targets:
            h = ahrefs.get("site-explorer/metrics-history", target=t, date_from=start, history_grouping=args.grouping,
                           select=",".join(fields), country=args.country, **common).get("metrics", [])
            d = ahrefs.get("site-explorer/domain-rating-history", target=t, date_from=start,
                           history_grouping=args.grouping).get("domain_ratings", [])
            for r in h:
                series.setdefault(r["date"][:10], {})[f"{t} traffic"] = fmt_int(r.get("org_traffic") or 0)
            for r in d:
                series.setdefault(r["date"][:10], {})[f"{t} DR"] = r.get("domain_rating")
        cols = [c for t in targets for c in (f"{t} traffic", f"{t} DR")]
        return table(["datum"] + cols, [[k] + [v.get(c, "") for c in cols] for k, v in sorted(series.items())])

    lists = {
        "keywords": ("site-explorer/organic-keywords",
                     "keyword,volume,best_position,best_position_url,sum_traffic", "sum_traffic:desc"),
        "pages": ("site-explorer/top-pages", "url,sum_traffic,keywords,top_keyword,top_keyword_best_position", "sum_traffic:desc"),
        "competitors": ("site-explorer/organic-competitors",
                        "competitor_domain,keywords_common,keywords_competitor,share,traffic,domain_rating", "share:desc"),
        "refdomains": ("site-explorer/refdomains", "domain,domain_rating,links_to_target,first_seen,traffic_domain",
                       "domain_rating:desc"),
    }
    if a in lists:
        endpoint, select, order = lists[a]
        select = args.select or select
        ahrefs.guard([(t, args.limit, len(select.split(","))) for t in targets], args.yes)
        params = dict(select=select, limit=args.limit, order_by=args.order_by or order, **common)
        if a != "refdomains":
            params.update(date=date, country=args.country)
        if args.where:
            params["where"] = args.where
        for t in targets:
            print(f"\n# {a}: {t}")
            _ahrefs_print(ahrefs.get(endpoint, target=t, **params), select.split(","))
        return

    if a == "raw":
        params = dict(kv.split("=", 1) for kv in args.params)
        rows = int(params.get("limit", 1))
        fields = len(params.get("select", "x").split(","))
        ahrefs.guard([(params.get("target"), rows, fields)], args.yes)
        return dump_json(ahrefs.get(target, **params))
    raise UsageError(f"Neznámá akce {a}")


# ---------------------------------------------------------------- parser

def build_parser():
    ap = argparse.ArgumentParser(prog="webstats", description="Analýza návštěvnosti webů z GA4, GSC a Ahrefs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def ga_filters(p):
        p.add_argument("-f", "--filter", action="append", default=[], help="filtr dimenze, např. 'country==France', 'landingPage~/fr/'")
        p.add_argument("--organic", action="store_true", help="jen Organic Search")
        p.add_argument("--exclude-country", action="append", default=[], metavar="ZEMĚ",
                       help="vyřadit zemi (GA název, např. Singapore) – opakovatelné")

    sub.add_parser("check", help="seznam GA4 property a GSC webů").set_defaults(func=cmd_check)

    p = sub.add_parser("traffic", help="sessions všech webů vs. předchozí období")
    add_period_args(p)
    ga_filters(p)
    p.add_argument("-m", "--metric", default="sessions")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_traffic)

    p = sub.add_parser("ga", help="libovolný GA4 report jednoho webu")
    p.add_argument("site")
    p.add_argument("-d", "--dims", default="sessionDefaultChannelGroup", help="dimenze oddělené čárkou ('' = žádná)")
    p.add_argument("-m", "--metrics", default="sessions,totalUsers,engagementRate")
    ga_filters(p)
    add_period_args(p)
    p.add_argument("--limit", type=int, default=50, help="kolik řádků vypsat")
    p.add_argument("--fetch", type=int, default=10000, help="kolik řádků stáhnout")
    p.add_argument("--sort", choices=["value", "delta"], default="value")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ga)

    p = sub.add_parser("gsc", help="libovolný GSC report jednoho webu")
    p.add_argument("site")
    p.add_argument("-d", "--dims", default="query", help="query,page,country,device,date,searchAppearance")
    p.add_argument("-f", "--filter", action="append", default=[], help="např. 'country==fra', 'query~dark porn', 'page~/fr/'")
    p.add_argument("--type", default="web", help="web, image, video, news, discover, googleNews")
    add_period_args(p)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--fetch", type=int, default=25000)
    p.add_argument("--sort", choices=["value", "delta"], default="value")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_gsc)

    p = sub.add_parser("ga-drill", help="kde spadla návštěvnost v GA4")
    p.add_argument("site")
    p.add_argument("-m", "--metric", default="sessions")
    p.add_argument("--dims", default="sessionDefaultChannelGroup,sessionSource,country,deviceCategory,landingPage")
    ga_filters(p)
    add_period_args(p)
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--gains", action="store_true", help="místo propadů ukázat růsty")
    p.set_defaults(func=cmd_ga_drill)

    p = sub.add_parser("gsc-drill", help="kde spadly kliky v GSC")
    p.add_argument("site")
    p.add_argument("--dims", default="country,device,page,query")
    p.add_argument("-f", "--filter", action="append", default=[])
    add_period_args(p)
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--fetch", type=int, default=25000)
    p.add_argument("--gains", action="store_true")
    p.set_defaults(func=cmd_gsc_drill)

    p = sub.add_parser("gsc-pages", help="URL, které spadly na ~0 kliků nebo prudce vyrostly (všechny weby)")
    p.add_argument("site", nargs="*", help="jen tyto weby (výchozí všechny)")
    add_period_args(p)
    p.add_argument("--min-clicks", type=float, default=20, help="min. kliků v referenčním období")
    p.add_argument("--drop-ratio", type=float, default=0.1, help="spadlá = teď ≤ ratio × předtím (výchozí 0.1)")
    p.add_argument("--grow-factor", type=float, default=3, help="vyrostlá = teď ≥ faktor × předtím")
    p.add_argument("--top", type=int, default=20, help="max. URL na web a typ")
    p.add_argument("--inspect", type=int, default=10, help="kolik spadlých URL na web ověřit (HTTP + URL Inspection)")
    p.add_argument("--fetch", type=int, default=50000)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_gsc_pages)

    p = sub.add_parser("updates", help="Google Search updaty/incidenty v období")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_updates, compare="none")

    p = sub.add_parser("ahrefs", help="Ahrefs: overview, history, keywords, pages, competitors, refdomains, limits, raw")
    p.add_argument("action", choices=["limits", "overview", "history", "keywords", "pages", "competitors", "refdomains", "raw"])
    p.add_argument("target", nargs="?", help="doména (u raw název endpointu)")
    p.add_argument("params", nargs="*", help="raw: parametry klíč=hodnota")
    p.add_argument("--vs", action="append", help="konkurent pro srovnání (opakovatelné)")
    p.add_argument("--mode", default="subdomains", choices=["exact", "prefix", "domain", "subdomains"])
    p.add_argument("--country", help="dvoupísmenný kód země, např. fr")
    p.add_argument("--date", help="datum dat (YYYY-MM-DD), výchozí včera")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--select", help="vlastní seznam polí")
    p.add_argument("--order-by")
    p.add_argument("--where", help="Ahrefs filtr (JSON)")
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--grouping", default="monthly", choices=["daily", "weekly", "monthly"])
    p.add_argument("--yes", action="store_true", help="potvrdit dotaz nad limitem odhadu units")
    p.set_defaults(func=cmd_ahrefs)
    return ap


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (UsageError, AuthError, ApiError) as ex:
        print(f"Chyba: {ex}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0
