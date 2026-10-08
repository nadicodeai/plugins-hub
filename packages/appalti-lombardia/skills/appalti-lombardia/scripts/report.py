#!/usr/bin/env python3
"""Keep the judged tenders and build the report page from them.

    python report.py --add judged.json    merge the model's judgements, then build the page
    python report.py                      build the page from what is stored

The page is one self-contained HTML file, appalti.html in the state directory, that opens offline in any
browser and can be sent as an attachment. Standard library only.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FIELDS = ("id", "provincia", "comune", "oggetto", "esito", "importo_eur", "scadenza", "procedura", "categorie",
          "cig", "rup", "url", "nota", "pubblicato", "aggiudicatario")
VERDICTS = ("in_linea", "altro", "aggiudicazione")
KEEP_DAYS = 120
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "appalti.html"


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def merge(store, judged, today):
    """Add or update judged records; return how many were accepted and the reasons for any refused."""
    accepted, refused = 0, []
    for record in judged:
        if not isinstance(record, dict) or not record.get("id") or not record.get("url"):
            refused.append(f"{record!r:.80}: needs id and url")
            continue
        if record.get("esito") not in VERDICTS:
            refused.append(f"{record['id']}: esito must be one of {', '.join(VERDICTS)}")
            continue
        clean = {k: record.get(k) for k in FIELDS if record.get(k) not in (None, "", [])}
        previous = store.get(record["id"], {})
        clean["trovato"] = previous.get("trovato") or today.isoformat()
        store[record["id"]] = {**previous, **clean}
        accepted += 1
    return accepted, refused


def prune(store, today):
    """Drop records whose deadline, or whose finding date when undated, is older than KEEP_DAYS."""
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    return {k: v for k, v in store.items() if (v.get("scadenza") or v.get("trovato") or "") >= cutoff}


def build(state_dir, store, today):
    settings = load_json(state_dir / "settings.json", {})
    last_run = load_json(state_dir / "last-run.json", {})
    data = {
        "generato": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "oggi": today.isoformat(),
        "azienda": settings.get("azienda") or "",
        "attivita": settings.get("attivita") or "",
        "soa": settings.get("soa") or {},
        "min_eur": settings.get("min_eur"),
        "max_eur": settings.get("max_eur"),
        "copertura": last_run.get("coverage", []),
        "ultima_lettura": last_run.get("run_at"),
        "pagine_fallite": len(last_run.get("pages_failed", [])) if isinstance(last_run.get("pages_failed"), list)
        else last_run.get("pages_failed", 0),
        "browser_arretrato": last_run.get("browser_backlog", 0),
        "bandi": sorted(store.values(), key=lambda r: (r.get("scadenza") or "9999", r.get("comune") or "")),
    }
    page = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = state_dir / "appalti.html"
    out.write_text(page.replace("/*__DATA__*/null", payload), encoding="utf-8")
    return out


def main():
    # The Agent's own home, which Nadia passes to every command it runs (~/.nadia, or ~/.nadia/profiles/<Agent>)
    home = os.environ.get("HERMES_HOME", "").strip()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--add", help="JSON file with a list of judged records")
    ap.add_argument("--state-dir", default=str(Path(home) / "appalti-lombardia") if home else None,
                    help="default: appalti-lombardia in the Agent's home (HERMES_HOME)")
    args = ap.parse_args()
    if not args.state_dir:
        raise SystemExit("HERMES_HOME is not set: run this from the Agent's terminal, or pass --state-dir")

    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    store_path = state_dir / "bandi.json"
    today = date.today()
    store = load_json(store_path, {})
    accepted, refused = 0, []
    if args.add:
        judged = load_json(args.add, None)
        if not isinstance(judged, list):
            raise SystemExit(f"{args.add} must hold a JSON list of records")
        accepted, refused = merge(store, judged, today)
    store = prune(store, today)
    store_path.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    page = build(state_dir, store, today)
    counts = {v: sum(1 for r in store.values() if r.get("esito") == v) for v in VERDICTS}
    json.dump({"page": str(page), "accepted": accepted, "refused": refused, "stored": counts}, sys.stdout,
              ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
