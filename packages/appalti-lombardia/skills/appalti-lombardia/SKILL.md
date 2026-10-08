---
name: appalti-lombardia
description: Daily report of works tenders on Lombardy comuni sites.
version: "2.0.0"
author: Vadim Comanescu, NadicodeAI
platforms: [linux, macos, windows]
compatibility: Requires terminal, web_extract and the browser tools.
metadata:
  category: business
allowed-tools: terminal process web_extract browser_navigate browser_snapshot read_file write_file cronjob
---

# Appalti Lombardia Skill

Every day, find the public works notices that the 1,502 comuni of Lombardy published on their own
websites, keep the ones the company can bid for, and send the owner a report with a web page of
everything currently open. Since the 2024 correttivo (D.Lgs. 36/2023, art. 50 c. 2-bis) a comune
announces a negotiated procedure, works from €150,000 to €1 million, on its own site, and often
nowhere else, so the comuni's sites are the source. Read-only: never submit a form, register, sign
in or change anything on a site.

## When to Use

- The scheduled daily run.
- The owner asks what was published, what is open, or for the page of current tenders.
- The owner asks to set the monitor up, or to change the company's categories, value range or provinces.

Don't use for: tenders of regions, ASL, utilities or the State, which publish on their own
platforms; this skill reads comuni.

## Prerequisites

- Python 3.10 or later on the Agent's computer; the scripts use the standard library only.
- `HERMES_HOME` set in the terminal, which Nadia does for every Agent. The scripts keep their state
  in `appalti-lombardia/` inside it: `settings.json`, `state.json`, `last-run.json`, `bandi.json`
  and the page `appalti.html`.
- The company's settings (see Quick Reference). Without SOA categories every works notice is `altro`.

## How to Run

Run the scripts with the `terminal` tool from this skill's absolute directory; `<state_dir>` is the
folder of the `settings_file` the scanner prints:

```
terminal(command="python <skill_dir>/scripts/scan.py", timeout=900)
terminal(command="python <skill_dir>/scripts/report.py --add <state_dir>/judged-<date>.json", timeout=60)
```

`scan.py` reads every mapped page of every comune (about 4,200 pages) in about eight minutes; when the
`terminal` call returns a background session instead of the output, wait for it with `process(action="wait")`. It prints
JSON: `settings`, `coverage` per province, `new_items` ranked by `hint.punteggio`, `browser_today`
(the pages whose list is built by JavaScript that are due for a read today), `pages_failed` and
`last_run_file`. `report.py` stores the judged records and rebuilds the page; it prints `page`, the
page's absolute path.

## Quick Reference

- `scan.py --baseline`: first run; records everything as seen and prints as `current_items` only what was published in the last 60 days (`--recent N` to change).
- `scan.py --provincia brescia`: one province. `--only 016024,016025`: a few comuni by ISTAT code.
- `report.py`: rebuild the page from what is stored.
- Settings, `settings.json`:

```json
{
  "azienda": "Ragione sociale",
  "attivita": "What the company builds, in one sentence",
  "province": [],
  "min_eur": 150000,
  "max_eur": 1000000,
  "soa": {"OG3": "VI", "OG6": "VIII"},
  "parole_chiave": ["fognatura", "teleriscaldamento"],
  "escludi": ["sfalcio"]
}
```

  An empty `province` means all twelve. Provinces: bergamo, brescia, como, cremona, lecco, lodi,
  mantova, milano, monza-brianza, pavia, sondrio, varese.
- Judged record, one per kept item, in a JSON list:

```json
{"id": "<item id>", "provincia": "Bergamo", "comune": "Zogno", "oggetto": "...", "esito": "in_linea",
 "importo_eur": 544348, "scadenza": "2026-10-19", "procedura": "Procedura negoziata, art. 50 c.1 lett. c",
 "categorie": ["OG8"], "cig": "...", "rup": "...", "url": "<the notice>", "pubblicato": "2026-09-29",
 "aggiudicatario": null, "nota": "OG8 III-bis copre l'importo."}
```

  `esito` is `in_linea`, `altro` or `aggiudicazione`. Dates are `YYYY-MM-DD`. Leave unknown fields `null`.

## Procedure

### Set up, once

1. **Settings.** Ask the owner for the company's website or its SOA certificate if you were not
   given them. Read them with `web_extract` and write `settings.json` (`scan.py --show-settings`
   creates it and prints its path): the legal name, one sentence
   of activity, every SOA category with its class exactly as the certificate states, keywords for
   the work the company does, and the value range the owner wants. Show the owner the file. Done
   when every category on the certificate is in `soa`.
2. **Baseline.** Run `scan.py --baseline`, then judge `current_items` and the `browser_today` pages
   as in the daily run, steps 2 to 5. The first report says monitoring started and from now on
   carries only new notices. Done when the page exists and the owner has it.
3. **Daily job.** Create one task with the `cronjob` tool: schedule `0 7 * * 1-6` (07:00 Monday to
   Saturday) or what the owner asks, this skill by the full name the skill list shows for it
   (installed from the hub it reads `agent-plugin-appalti-lombardia-<id>:appalti-lombardia`), `continuity` on so each run sees
   the previous report, delivered to the channel the owner names. Done when the job is listed.

### Every day

1. **Scan.** Run `scan.py`. Do not open the comuni's list pages yourself: the scanner read them.
2. **Judge.** Read `references/selezione.md` with `read_file`. Judge every item in `new_items` from
   its `title`, `context`, `amount_eur`, `date` and `hint` (the SOA categories named or implied and
   the company's keywords it matches). Drop what the reference says to drop. Done when every item
   is dropped or has a verdict.
3. **Read the notice.** For each item that could be `in_linea`, and each `altro` whose value or
   category is unknown, open its `url` with `web_extract` (it reads PDFs) or the browser, and take
   the value, deadline, procedure, categories, CIG and RUP from the notice and its attached avviso.
   Open at most 40 notices in one run, highest `hint.punteggio` first; name any left unread in the
   report.
4. **Read the JavaScript pages.** Open each `browser_today` page with `browser_navigate`, read the
   first screen of the list with `browser_snapshot`, and judge the entries dated after the previous
   report (on the baseline run, within the last 60 days) the same way. Use the entry's link as
   `url` and the SHA-1 of that link, first 16 hex characters, as `id`.
5. **Store and build the page.** Write the judged records with `write_file` to
   `<state_dir>/judged-<YYYY-MM-DD>.json` and run `report.py --add` on it. Done when `refused` is
   empty; fix and re-add any refused record.
6. **Report**, in Italian:
   - **Da valutare**: each `in_linea` notice with comune, subject, value, procedure, deadline,
     categories and the link; a deadline within seven days first, marked *urgente*.
   - **Altri lavori pubblicati**: one line each.
   - **Aggiudicazioni**: who won what, one line each.
   - **Copertura**: comuni and pages read per the scanner's `coverage`, pages failed, JavaScript
     pages read today and still queued, notices left unread.
   - End with the page's absolute path on its own line, so the channel attaches the page.

   When nothing new fits, say so in one sentence and still give the coverage and the page: the
   daily report is also the proof that the monitor ran.

### When the owner asks for the current tenders

Run `report.py` and give the page's path; summarise the open `in_linea` notices from `bandi.json`.

## Pitfalls

- A list page shows the publication date, not the deadline: read the deadline from the notice.
- The same tender appears on the tender list, the albo and the news: report it once, with the
  most specific link, and store it once.
- An unknown value is not a reason to drop a works notice that fits the categories.
- A comune that changes its site makes its page fail; it shows under Copertura. Do not guess a
  new address.
- About one page in eight is built with JavaScript; the scanner hands out 30 a day, least recently
  read first, so each is read every few weeks. Say so when the owner asks about a comune on one.
- `hint` is a ranking aid from the title's words, not a verdict: an OG3 hint on "barriere
  architettoniche" in a school is OG1 work.

## Verification

Before sending, check that every `in_linea` notice has a working link to the comune's own notice,
that every value and deadline was read from the notice and not inferred, that the coverage line
matches the scanner's counts, and that `report.py` printed no refused record.
