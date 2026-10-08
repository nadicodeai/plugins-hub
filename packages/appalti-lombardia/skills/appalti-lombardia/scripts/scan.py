#!/usr/bin/env python3
"""Read every mapped tender page of a province's comuni and print what is new since the last run.

Standard library only. The model never reads the pages itself: this script fetches them, keeps the
links that look like works procurement, and prints only the ones it has not seen before.
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

USER_AGENT = "Mozilla/5.0 (compatible; NadiaAppalti/1.0; monitoraggio avvisi pubblici)"
HOST_DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 25
MAX_BYTES = 3_000_000
KEEP_SEEN_DAYS = 180
DEFAULT_SETTINGS = {
    "province": ["bergamo"],
    "min_eur": 150000,
    "max_eur": 1000000,
    "activity": "impianti elettrici, termoidraulici, di climatizzazione, antincendio, illuminazione pubblica, fotovoltaico",
    "categories": ["OG11", "OS28", "OS30", "OS3", "OG10", "45310000", "45330000", "45331000", "45316000", "45343000"],
}

PROCUREMENT = re.compile(
    r"procedura negoziata|manifestazion\w* d[i']\s*interesse|indagine di mercato|avviso|affidament|"
    r"\bgara\b|\bbando\b|appalt|determin\w* a contrarre|art\.?\s*50|consultazione|esito|aggiudica|"
    r"\bcig\b|lettera d[i']\s*invito|elenco operatori",
    re.I,
)
WORKS = re.compile(
    r"lavor|\bopere\b|impiant|riqualificazion|ristrutturazion|efficientament|adeguament|"
    r"messa in sicurezza|manutenzione straordinaria|fotovoltaic|antincendi|\bOG\s?\d|\bOS\s?\d",
    re.I,
)
SERVICES = re.compile(
    r"servizi?o?\b|fornitur|noleggi|concession|alienazion|pulizi|refezion|trasporto|assicurativ|"
    r"software|stampant|impianti sportivi",
    re.I,
)
NOT_TENDER = re.compile(
    r"concorso pubblico|bando di concorso|assunzion|mobilit[aà] volontaria|contribut|borsa di studio|"
    r"interruzione|sotto-sezion|^bandi di gara(?: e contratti)?$|^atti relativi alle procedure|^avvisi$|"
    r"^affidamenti diretti di lavori, servizi e forniture di somma urgenza|^lavoro$",
    re.I,
)
AMOUNT = re.compile(r"(?:€|euro|eur)\s*([0-9]{1,3}(?:[.\s][0-9]{3})+(?:,[0-9]{1,2})?|[0-9]{4,}(?:,[0-9]{1,2})?)", re.I)
JS_HINT = re.compile(r"enable javascript|abilita(?:re)? javascript|javascript (?:is )?required", re.I)
BLOCKS = {"tr", "li", "article", "dd", "p", "td"}
LINK_NOISE = re.compile(
    r"^(?:fai click qui per andare al dettaglio|visualizza il dettaglio del bando|visualizza contenuto|"
    r"scarica questo file|leggi di pi[uù]|leggi tutto|dettaglio|vai al dettaglio)\s*[:\-]?\s*",
    re.I,
)


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

    def get(self, url):
        url = urllib.parse.quote(url.strip(), safe=":/?&=%#+,;@!~*'()$[]")
        host = urllib.parse.urlsplit(url).hostname or ""
        with self._locks[host]:
            wait = self._last.get(host, 0) + HOST_DELAY_SECONDS - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                return self._open(url, None)
            except urllib.error.URLError as error:
                if isinstance(error.reason, ssl.SSLError):
                    return self._open(url, self._insecure)
                raise
            finally:
                self._last[host] = time.monotonic()

    def _open(self, url, context):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "it-IT,it;q=0.9"})
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies), urllib.request.HTTPSHandler(context=context)
        )
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            return response.geturl(), body.decode(charset, errors="replace")


def read_page(fetcher, comune, page):
    try:
        final_url, body = fetcher.get(page["url"])
    except Exception as error:  # every failure is reported, never fatal to the run
        return {"comune": comune["comune"], "kind": page["kind"], "url": page["url"], "error": str(error)[:200]}, []
    parser = LinkParser(final_url)
    try:
        parser.feed(body)
    except Exception as error:
        return {"comune": comune["comune"], "kind": page["kind"], "url": page["url"], "error": f"parse: {error}"[:200]}, []
    links = parser.finish()
    status = {"comune": comune["comune"], "kind": page["kind"], "url": page["url"], "links": len(links)}
    if comune.get("browser") or len(links) < 5 or JS_HINT.search(body[:20000]):
        status["needs_browser"] = True
    items = []
    for href, text, block in links:
        context = block if len(block) > len(text) else text
        text = LINK_NOISE.sub("", text).strip()
        subject = text if len(text) >= 20 else context
        if len(subject) < 20 or href.rstrip("/") == final_url.rstrip("/"):
            continue
        if not PROCUREMENT.search(context) or not WORKS.search(subject) or NOT_TENDER.search(text):
            continue
        if SERVICES.search(subject) and not re.search(r"lavor", subject, re.I):
            continue
        key = hashlib.sha1(f"{comune['istat']}|{href}|{text}".encode()).hexdigest()[:16]
        items.append({
            "id": key,
            "istat": comune["istat"],
            "comune": comune["comune"],
            "kind": page["kind"],
            "title": text or context[:160],
            "context": context,
            "amount_eur": amount_eur(context),
            "url": href,
            "page": page["url"],
        })
    return status, items


def load_state(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"seen": {}}


def main():
    skill_dir = Path(__file__).resolve().parent.parent
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provincia", help="name of assets/comuni-<provincia>.json; default: every province in settings.json")
    ap.add_argument("--state-dir", default=str(home / "appalti-lombardia"))
    ap.add_argument("--baseline", action="store_true", help="record everything as seen and report nothing new")
    ap.add_argument("--only", help="comma-separated ISTAT codes, for a check of a few comuni")
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()

    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    settings_path = state_dir / "settings.json"
    if not settings_path.exists():
        settings_path.write_text(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False, indent=1))
    settings = {**DEFAULT_SETTINGS, **json.loads(settings_path.read_text())}
    reports = [scan(skill_dir, state_dir, provincia.lower(), args) for provincia in ([args.provincia] if args.provincia else settings["province"])]
    json.dump({"settings": settings, "settings_file": str(settings_path), "provinces": reports}, sys.stdout, ensure_ascii=False)
    print()


def scan(skill_dir, state_dir, provincia, args):
    data = json.loads((skill_dir / "assets" / f"comuni-{provincia}.json").read_text())
    comuni = data["comuni"]
    if args.only:
        wanted = set(args.only.split(","))
        comuni = [c for c in comuni if c["istat"] in wanted]

    state_path = state_dir / f"state-{provincia}.json"
    state = load_state(state_path)
    seen = state["seen"]

    started = time.monotonic()
    fetcher = Fetcher()
    jobs = [(c, p) for c in comuni for p in c["pages"]]
    statuses, found = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for status, items in pool.map(lambda job: read_page(fetcher, *job), jobs):
            statuses.append(status)
            found.extend(items)

    today = date.today().isoformat()
    new, ids = [], set()
    for item in found:
        if item["id"] in ids:
            continue
        ids.add(item["id"])
        if item["id"] not in seen:
            seen[item["id"]] = today
            if not args.baseline:
                new.append(item)
    cutoff = (date.today() - timedelta(days=KEEP_SEEN_DAYS)).isoformat()
    state["seen"] = {k: v for k, v in seen.items() if v >= cutoff}
    state["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state_path.write_text(json.dumps(state))

    failed = [s for s in statuses if "error" in s]
    report = {
        "provincia": data["provincia"],
        "run_at": state["last_run"],
        "baseline": args.baseline,
        "seconds": round(time.monotonic() - started),
        "comuni": len(comuni),
        "pages": len(statuses),
        "pages_failed": failed,
        "needs_browser": [s for s in statuses if s.get("needs_browser")],
        "new_items": new,
    }
    (state_dir / f"last-run-{provincia}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    main()
