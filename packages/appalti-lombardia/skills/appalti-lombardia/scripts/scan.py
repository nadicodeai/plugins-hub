#!/usr/bin/env python3
"""Read every mapped tender page of the configured provinces' comuni and print what is new since the last run.

Standard library only. The model never reads these pages itself: this script fetches them, keeps the links
that look like public works procurement, ranks them against the company's settings, and prints only the
ones it has not seen before.
"""

import argparse
import concurrent.futures
import hashlib
import html
import http.cookiejar
import json
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (compatible; NadiaAppalti/2.0; monitoraggio avvisi pubblici)"
HOST_DELAY_SECONDS = 0.5
TIMEOUT_SECONDS = 25
RETRY_TIMEOUT_SECONDS = 45
RETRY = re.compile(r"timed out|HTTP Error 5\d\d|Connection reset|Remote end closed", re.I)
MAX_BYTES = 3_000_000
KEEP_SEEN_DAYS = 400
BROWSER_QUOTA = 30
RECENT_DAYS = 60
SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"

DEFAULT_SETTINGS = {
    "azienda": "",
    "attivita": "",
    "province": [],
    "min_eur": 150000,
    "max_eur": 1000000,
    "soa": {},
    "parole_chiave": [],
    "escludi": [],
}

PROCUREMENT = re.compile(
    r"procedura negoziata|manifestazion\w* d[i']\s*interesse|indagine (?:di mercato|esplorativa)|avviso|affidament|"
    r"\bgara\b|\bbando\b|appalt|determin\w* a contrarre|decisione a contrattare|art\.?\s*50|consultazione|esito|"
    r"aggiudica|\bcig\b|lettera d[i']\s*invito|elenco operatori|procedura aperta",
    re.I,
)
WORKS = re.compile(
    r"lavor|\bopere\b|impiant|riqualificazion|ristrutturazion|efficientament|adeguament|messa in sicurezza|"
    r"manutenzione straordinaria|fotovoltaic|antincendi|strad|asfalt|marciapied|ciclabil|ciclopedonal|fognatur|"
    r"acquedott|rete idrica|teleriscaldament|sottoservizi|bonific|idrogeolog|consolidament|frana|parcheggi|"
    r"urbanizzazion|demolizion|\bOG\s?\d|\bOS\s?\d",
    re.I,
)
SERVICES = re.compile(
    r"servizi?o?\b|fornitur|noleggi|concession|alienazion|pulizi|refezion|trasporto|assicurativ|software|"
    r"stampant|incarico|progettazione|direzione lavori|collaudo|coordinamento della sicurezza|frazionamento|"
    r"perizia|relazione geologica|prestazion\w* professional",
    re.I,
)
NOT_TENDER = re.compile(
    r"concorso pubblico|bando di concorso|assunzion|mobilit[aà] volontaria|contribut|borsa di studio|"
    r"selezione di personale|apprendista|tirocini|leva civica|interruzione|sotto-sezion|^ordina per|"
    r"^bandi di gara(?: e contratti)?$|^atti relativi alle|^avvisi$|^opere pubbliche$|^affidamento$|"
    r"^affidamenti diretti di lavori, servizi e forniture di somma urgenza|^lavoro$|^informazioni sulle singole|"
    r"programma triennale|non ha prodotto avvisi|pari opportunit|gara ciclistica|circolazione stradale|spettacol|"
    r"associazion\w* di volontariato|comodato",
    re.I,
)
LINK_NOISE = re.compile(
    r"^(?:fai click qui per andare al dettaglio|fare click sul testo per accedere al dettaglio(?: del contratto pubblico| dell'atto)?|"
    r"visualizza il dettaglio del bando|visualizza contenuto|scarica (?:questo |il )?file:?|leggi di pi[uù]|leggi tutto|"
    r"dettaglio|vai al dettaglio)\s*[:\-]?\s*",
    re.I,
)
AMOUNT = re.compile(r"(?:€|euro|eur)\s*([0-9]{1,3}(?:[.\s][0-9]{3})+(?:,[0-9]{1,2})?|[0-9]{4,}(?:,[0-9]{1,2})?)", re.I)
JS_HINT = re.compile(r"enable javascript|abilita(?:re)? javascript|javascript (?:is )?required", re.I)
CATEGORY = re.compile(r"\b(O[GS])\s?-?\s?(\d{1,2})(?:\s?-?\s?([AB])\b)?", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}
DATE_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b")
DATE_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
DATE_TXT = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b", re.I)
YEAR = re.compile(r"\b(20[12]\d)\b")
BLOCKS = {"tr", "li", "article", "dd", "p", "td"}

# Words that name each SOA category's work in a notice title, used to rank items against the company's
# categories. The full table, with the classification limits, is references/selezione.md.
CATEGORY_WORDS = {
    "OG1": r"edifici|scuol|palestr|municipio|fabbricat|immobil|ampliament|nuova sede|asilo|spogliato|centro sportivo|cimiter",
    "OG2": r"restauro|tutelat|chiesa|beni culturali|storic",
    "OG3": r"strad|asfalt|marciapied|ciclabil|ciclopedonal|viabilit|rotatori|ponte|parcheggi|piazza|incrocio|pavimentazion|barriere architettoniche|percorso pedonal",
    "OG4": r"galleri|sottopass|tunnel",
    "OG6": r"acquedott|fognatur|rete idrica|reti idriche|gasdott|teleriscaldament|sottoservizi|irrigazion|scarich|collettor|tubazion|reti? (?:di )?distribuzion",
    "OG8": r"idrogeolog|idraulic|torrente|fiume|alveo|argin|tombott|esondazion|vasca di laminazione|regimazione",
    "OG10": r"illuminazione pubblica|pubblica illuminazione|cabina elettrica|media tensione|linee elettriche",
    "OG11": r"impianti tecnologici|impianto (?:elettrico|termico|meccanico)",
    "OG12": r"bonific|amianto|protezione ambientale|discarica|siti contaminati",
    "OG13": r"ingegneria naturalistica",
    "OS21": r"consolidament|frana|versante|paratie|micropali|muro di sostegno|muri di sostegno|scogliera",
    "OS24": r"verde|parco|giardin|arredo urbano|aree verdi",
    "OS28": r"impianti termici|climatizzazion|caldai|riscaldament",
    "OS30": r"impianti elettrici|impianto elettrico",
    "OS12": r"guard ?rail|barriere stradali|barriere di sicurezza|paramassi",
    "OS9": r"semafor|segnaletica luminosa",
    "OS10": r"segnaletica",
    "OS23": r"demolizion",
    "OS29": r"ferrovi|binari|armamento",
}


class LinkParser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.links = []
        self._href = None
        self._text = []
        self._blocks = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCKS:
            self._blocks.append([])
        if tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                self._href = urllib.parse.urljoin(self.base, href.strip())
                self._text = [dict(attrs).get("title") or ""]

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            # the enclosing block keeps filling after the link closes; finish() joins it
            self.links.append((self._href, squash(" ".join(self._text)), self._blocks[-1] if self._blocks else []))
            self._href = None
        if tag in BLOCKS and self._blocks:
            text = self._blocks.pop()
            if self._blocks:
                self._blocks[-1].extend(text)

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
        if self._blocks:
            self._blocks[-1].append(data)

    def finish(self):
        return [(href, text, squash(" ".join(block))[:600]) for href, text, block in self.links]


def squash(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def amount_eur(text):
    values = []
    for raw in AMOUNT.findall(text):
        digits = raw.replace(" ", "").replace(".", "").split(",")[0]
        if digits.isdigit():
            values.append(int(digits))
    return max(values) if values else None


def latest_date(text):
    """The latest date written in the text, as ISO, or None."""
    found = []
    for d, m, y in DATE_NUM.findall(text):
        found.append((int(y), int(m), int(d)))
    for y, m, d in DATE_ISO.findall(text):
        found.append((int(y), int(m), int(d)))
    for d, m, y in DATE_TXT.findall(text):
        found.append((int(y), MONTHS[m.lower()], int(d)))
    valid = []
    for y, m, d in found:
        try:
            valid.append(date(y, m, d))
        except ValueError:
            continue
    return max(valid).isoformat() if valid else None


def categories_in(text):
    return sorted({f"{k.upper()}{n}{(s or '').upper()}" for k, n, s in CATEGORY.findall(text)})


def hint(subject, context, settings):
    """What in the item points at the company's work: SOA categories named or implied, and its own keywords."""
    named = categories_in(context)
    soa = {k.upper().replace(" ", "") for k in settings.get("soa", {})}
    implied = [cat for cat, words in CATEGORY_WORDS.items() if re.search(words, subject, re.I)]
    words = [w for w in settings.get("parole_chiave", []) if w and re.search(re.escape(w), subject, re.I)]
    score = 3 * len(soa.intersection(named)) + 2 * len(soa.intersection(implied)) + 2 * len(words)
    return {"categorie_citate": named, "categorie_probabili": implied, "parole": words, "punteggio": score}


class Fetcher:
    """One request at a time per host, HOST_DELAY_SECONDS apart; hosts run in parallel."""

    def __init__(self):
        self._locks = defaultdict(threading.Lock)
        self._last = {}
        self._cookies = http.cookiejar.CookieJar()
        # Some comuni serve expired, mismatched or weak-key certificates; the pages are public.
        self._insecure = ssl.create_default_context()
        self._insecure.check_hostname = False
        self._insecure.verify_mode = ssl.CERT_NONE
        self._insecure.set_ciphers("DEFAULT:@SECLEVEL=0")

    def get(self, url, timeout=TIMEOUT_SECONDS):
        url = urllib.parse.quote(url.strip(), safe=":/?&=%#+,;@!~*'()$[]")
        host = urllib.parse.urlsplit(url).hostname or ""
        with self._locks[host]:
            wait = self._last.get(host, 0) + HOST_DELAY_SECONDS - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                return self._open(url, None, timeout)
            except urllib.error.URLError as error:
                if isinstance(error.reason, ssl.SSLError):
                    return self._open(url, self._insecure, timeout)
                raise
            finally:
                self._last[host] = time.monotonic()

    def _open(self, url, context, timeout):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "it-IT,it;q=0.9"})
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies), urllib.request.HTTPSHandler(context=context)
        )
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            return response.geturl(), body.decode(charset, errors="replace")


def items_from(links, final_url, comune, page, provincia, settings):
    items = []
    exclude = [w for w in settings.get("escludi", []) if w]
    for href, text, block in links:
        context = block if len(block) > len(text) else text
        text = LINK_NOISE.sub("", text).strip()
        if 0 < len(text) < 20:  # a category or tag link ("Acqua", "Categoria: Avviso"), not a notice
            continue
        subject = text or LINK_NOISE.sub("", context).strip()
        if len(subject) < 20 or href.rstrip("/") == final_url.rstrip("/"):
            continue
        if not PROCUREMENT.search(context) or not WORKS.search(subject) or NOT_TENDER.search(text or subject):
            continue
        if SERVICES.search(subject) and not re.search(r"\blavori\b|\bopere\b", subject, re.I):
            continue
        if any(re.search(re.escape(w), subject, re.I) for w in exclude):
            continue
        key = hashlib.sha1(f"{comune['istat']}|{href}|{text}".encode()).hexdigest()[:16]
        items.append({
            "id": key,
            "provincia": provincia,
            "istat": comune["istat"],
            "comune": comune["comune"],
            "kind": page["kind"],
            "title": (text or subject)[:300],
            "context": context[:400] if context != text else "",
            "amount_eur": amount_eur(context),
            "date": latest_date(context),
            "url": href,
            "page": page["url"],
            "hint": hint(subject, context, settings),
        })
    return items


def read_page(fetcher, comune, page, provincia, settings, timeout=TIMEOUT_SECONDS):
    base = {"provincia": provincia, "comune": comune["comune"], "kind": page["kind"], "url": page["url"]}
    try:
        final_url, body = fetcher.get(page["url"], timeout)
    except Exception as error:  # every failure is reported, never fatal to the run
        return {**base, "error": str(error)[:200]}, []
    parser = LinkParser(final_url)
    try:
        parser.feed(body)
    except Exception as error:
        return {**base, "error": f"parse: {error}"[:200]}, []
    links = parser.finish()
    status = {**base, "links": len(links)}
    if page.get("browser") or comune.get("browser") or len(links) < 5 or JS_HINT.search(body[:20000]):
        status["needs_browser"] = True
    return status, items_from(links, final_url, comune, page, provincia, settings)


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def available_provinces():
    return sorted(p.stem.removeprefix("comuni-") for p in ASSETS.glob("comuni-*.json"))


def is_current(item, today, recent_days):
    """Whether a baseline item is recent enough to judge: dated within recent_days, or undated but naming this year."""
    if item["date"]:
        return item["date"] >= (today - timedelta(days=recent_days)).isoformat()
    years = [int(y) for y in YEAR.findall(item["title"] + " " + item["context"])]
    return bool(years) and max(years) >= today.year


def scan(state_dir, settings, provinces, args):
    today = date.today()
    jobs = []
    counts = {}
    for provincia in provinces:
        data = load_json(ASSETS / f"comuni-{provincia}.json", None)
        if data is None:
            raise SystemExit(f"no map for province '{provincia}': available are {', '.join(available_provinces())}")
        comuni = data["comuni"]
        if args.only:
            wanted = set(args.only.split(","))
            comuni = [c for c in comuni if c["istat"] in wanted]
        counts[provincia] = {"provincia": data["provincia"], "comuni": len(comuni)}
        jobs += [(c, p, provincia) for c in comuni for p in c["pages"]]

    state_path = state_dir / "state.json"
    state = load_json(state_path, {"seen": {}, "browser_read": {}})
    seen = state.setdefault("seen", {})

    started = time.monotonic()
    fetcher = Fetcher()
    statuses, found = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda job: read_page(fetcher, *job, settings), jobs))
    # Many comuni share one vendor's servers, which time out under the first pass's load: retry those slowly.
    again = [i for i, (status, _) in enumerate(results) if RETRY.search(status.get("error", ""))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for i, result in zip(again, pool.map(lambda i: read_page(fetcher, *jobs[i], settings, RETRY_TIMEOUT_SECONDS), again)):
            results[i] = result
    by_link = {}
    for status, items in results:
        statuses.append(status)
        for item in items:  # the same notice is often linked twice on one page, once with its date block
            by_link.setdefault((item["istat"], item["url"]), item)
    found = list(by_link.values())

    new, current, ids = [], [], set()
    for item in found:
        if item["id"] in ids:
            continue
        ids.add(item["id"])
        if item["id"] not in seen:
            seen[item["id"]] = today.isoformat()
            if not args.baseline:
                new.append(item)
            elif is_current(item, today, args.recent):
                current.append(item)
    cutoff = (today - timedelta(days=KEEP_SEEN_DAYS)).isoformat()
    state["seen"] = {k: v for k, v in seen.items() if v >= cutoff}

    # JavaScript-built lists are read by the model in the browser, a few each day, least recently read first.
    browser_read = state.setdefault("browser_read", {})
    needs_browser = [s for s in statuses if s.get("needs_browser")]
    needs_browser.sort(key=lambda s: browser_read.get(s["url"], ""))
    browser_today = needs_browser[: args.browser_quota]
    for s in browser_today:
        browser_read[s["url"]] = today.isoformat()
    state["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state_path.write_text(json.dumps(state), encoding="utf-8")

    by_province = defaultdict(lambda: {"pages": 0, "failed": 0, "needs_browser": 0, "new": 0})
    for s in statuses:
        row = by_province[s["provincia"]]
        row["pages"] += 1
        row["failed"] += "error" in s
        row["needs_browser"] += bool(s.get("needs_browser"))
    for item in new or current:
        by_province[item["provincia"]]["new"] += 1
    coverage = [{**counts[p], **by_province[p]} for p in provinces]

    ranked = sorted(new or current, key=lambda i: (-i["hint"]["punteggio"], i["date"] or "", i["comune"]))
    report = {
        "run_at": state["last_run"],
        "baseline": args.baseline,
        "seconds": round(time.monotonic() - started),
        "coverage": coverage,
        "pages_failed": [s for s in statuses if "error" in s],
        "browser_today": [{k: s[k] for k in ("provincia", "comune", "kind", "url")} for s in browser_today],
        "browser_backlog": len(needs_browser) - len(browser_today),
        ("current_items" if args.baseline else "new_items"): ranked,
    }
    (state_dir / "last-run.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main():
    # The Agent's own home, which Nadia passes to every command it runs (~/.nadia, or ~/.nadia/profiles/<Agent>)
    home = os.environ.get("HERMES_HOME", "").strip()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provincia", help="one province, e.g. bergamo; default: the settings' provinces, or all")
    ap.add_argument("--state-dir", default=str(Path(home) / "appalti-lombardia") if home else None,
                    help="default: appalti-lombardia in the Agent's home (HERMES_HOME)")
    ap.add_argument("--baseline", action="store_true",
                    help="record everything as seen; print as current_items only what was published recently")
    ap.add_argument("--recent", type=int, default=RECENT_DAYS, help="days that count as recent for --baseline")
    ap.add_argument("--only", help="comma-separated ISTAT codes, for a check of a few comuni")
    ap.add_argument("--browser-quota", type=int, default=BROWSER_QUOTA)
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--show-settings", action="store_true", help="print the settings and their file, scan nothing")
    ap.add_argument("--max-items", type=int, default=400, help="items printed; the rest stay in last-run.json")
    args = ap.parse_args()
    if not args.state_dir:
        raise SystemExit("HERMES_HOME is not set: run this from the Agent's terminal, or pass --state-dir")

    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    settings_path = state_dir / "settings.json"
    if not settings_path.exists():
        settings_path.write_text(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False, indent=1), encoding="utf-8")
    settings = {**DEFAULT_SETTINGS, **load_json(settings_path, {})}
    if args.show_settings:
        json.dump({"settings": settings, "settings_file": str(settings_path), "provinces": available_provinces()},
                  sys.stdout, ensure_ascii=False)
        print()
        return
    provinces = [args.provincia.lower()] if args.provincia else (settings["province"] or available_provinces())

    report = scan(state_dir, settings, provinces, args)
    key = "current_items" if args.baseline else "new_items"
    total = len(report[key])
    report[key] = report[key][: args.max_items]
    report["items_total"] = total
    report["pages_failed"] = len(report["pages_failed"])
    json.dump({"settings": settings, "settings_file": str(settings_path),
               "last_run_file": str(state_dir / "last-run.json"), **report}, sys.stdout, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
