"""Období, filtry, formátování čísel a tabulek."""
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass


class UsageError(RuntimeError):
    pass


def today():
    return dt.date.today()


def parse_date(s):
    s = s.strip().lower()
    if s == "today":
        return today()
    if s == "yesterday":
        return today() - dt.timedelta(days=1)
    m = re.fullmatch(r"(\d+)daysago", s)
    if m:
        return today() - dt.timedelta(days=int(m.group(1)))
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise UsageError(f"Neplatné datum: {s} (čekám YYYY-MM-DD, today, yesterday, NdaysAgo)") from None


@dataclass
class Periods:
    start: dt.date
    end: dt.date
    prev_start: dt.date = None
    prev_end: dt.date = None

    @property
    def days(self):
        return (self.end - self.start).days + 1

    @property
    def has_prev(self):
        return self.prev_start is not None

    def label(self):
        s = f"{self.start} – {self.end} ({self.days} d)"
        if self.has_prev:
            s += f"  vs  {self.prev_start} – {self.prev_end}"
        return s


def add_period_args(p, days=7):
    g = p.add_argument_group("období")
    g.add_argument("--days", type=int, default=days, help=f"délka období ve dnech (výchozí {days})")
    g.add_argument("--start", help="začátek (YYYY-MM-DD); jinak end - days + 1")
    g.add_argument("--end", help="konec (YYYY-MM-DD); výchozí poslední dokončený den")
    g.add_argument(
        "--compare", default="prev",
        help="prev = předchozí stejně dlouhé období posunuté o celé týdny (stejné dny v týdnu), "
             "yoy = o 52 týdnů zpět, none = bez srovnání, nebo datum začátku srovnávacího období",
    )


def periods(args, lag_days):
    """lag_days: kolik posledních dní je neúplných (GSC 3, GA 1)."""
    end = parse_date(args.end) if args.end else today() - dt.timedelta(days=lag_days)
    start = parse_date(args.start) if args.start else end - dt.timedelta(days=args.days - 1)
    if start > end:
        raise UsageError("Začátek období je po konci.")
    p = Periods(start, end)
    n = p.days
    cmp = (args.compare or "none").lower()
    if cmp == "prev":
        shift = dt.timedelta(days=-(-n // 7) * 7)  # zaokrouhleno nahoru na celé týdny
        p.prev_start, p.prev_end = start - shift, end - shift
    elif cmp == "yoy":
        shift = dt.timedelta(weeks=52)
        p.prev_start, p.prev_end = start - shift, end - shift
    elif cmp != "none":
        p.prev_start = parse_date(cmp)
        p.prev_end = p.prev_start + dt.timedelta(days=n - 1)
    return p


def warn(msg):
    sys.stdout.flush()
    print(f"! {msg}", file=sys.stderr)


# ---------- filtry: dim==x, dim!=x, dim~x (obsahuje), dim!~x, dim=~regex, dim!=~regex, dim^=začátek

_OPS = {"!=~": "nregex", "=~": "regex", "!~": "ncontains", "!=": "neq", "==": "eq", "^=": "begins", "~": "contains"}


def parse_filter(s):
    best = None
    for tok, op in _OPS.items():
        i = s.find(tok)
        if i > 0 and (best is None or i < best[0] or (i == best[0] and len(tok) > len(best[1]))):
            best = (i, tok, op)
    if not best:
        raise UsageError(f"Neplatný filtr '{s}'. Použij dim==x, dim!=x, dim~x, dim!~x, dim=~regex, dim!=~regex, dim^=x")
    i, tok, op = best
    return s[:i].strip(), op, s[i + len(tok):].strip()


# ---------- čísla

PERCENT_METRICS = {"ctr", "engagementRate", "bounceRate", "sessionKeyEventRate", "userKeyEventRate"}


def fmt_int(v):
    return f"{v:,.0f}".replace(",", " ")


def fmt_metric(name, v):
    if v is None:
        return "—"
    if name in PERCENT_METRICS:
        return f"{v * 100:.2f} %"
    if name == "position":
        return f"{v:.1f}"
    if abs(v - round(v)) < 1e-9:
        return fmt_int(v)
    return f"{v:,.2f}".replace(",", " ")


def fmt_delta(cur, prev, name=""):
    cur, prev = cur or 0, prev or 0
    if name in PERCENT_METRICS:
        return f"{(cur - prev) * 100:+.2f} pb"
    if name == "position":
        return f"{cur - prev:+.1f}"
    d = cur - prev
    sign = "+" if d > 0 else ""
    return f"{sign}{fmt_metric(name, d)}"


def fmt_pct(cur, prev):
    cur, prev = cur or 0, prev or 0
    if prev == 0:
        return "nové" if cur else "—"
    return f"{(cur - prev) / prev * 100:+.1f} %"


def table(headers, rows, right=None):
    """Jednoduchá textová tabulka; right = množina indexů zarovnaných doprava."""
    rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    if right is None:
        right = set(range(1, len(headers)))
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    widths = [min(w, 90) for w in widths]

    def line(cells):
        out = []
        for i, c in enumerate(cells):
            c = c if len(c) <= widths[i] else c[: widths[i] - 1] + "…"
            out.append(c.rjust(widths[i]) if i in right else c.ljust(widths[i]))
        return "  ".join(out).rstrip()

    print(line(headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))


def dump_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
