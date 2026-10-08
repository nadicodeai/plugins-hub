---
name: appalti-lombardia
description: Monitor the websites of Lombardy's comuni every day for new public works tenders and send a report of the ones that fit the company's work and value range.
version: "1.0.0"
author: Vadim Comanescu, NadicodeAI
platforms: [linux, macos, windows]
compatibility: Requires terminal, web_extract and the browser tools.
metadata:
  category: business
allowed-tools: terminal web_extract browser_navigate browser_snapshot read_file
---

# Appalti dei comuni lombardi

Every day, find the works tenders that the comuni of the configured provinces
published on their own websites since the last run, and report the ones the
company could bid for. Since the 2024 correttivo (art. 50, comma 2-bis, D.Lgs.
36/2023) a comune announces a negotiated procedure, the band from €150,000 to
€1 million for works, on its own site; often that is the only public place it
appears, so the comuni's sites are the source, not a central database.

Read-only. Never submit a form, register, sign in, download an executable or
change anything on a site.

## When to use

Use this skill in the scheduled daily run, and when the owner asks what was
published recently, or asks to set the daily run up.

## Procedure

1. **Scan.** Run the scanner with the terminal tool, using this skill's
   absolute directory:

   ```
   python <skill_dir>/scripts/scan.py
   ```

   It prints the company's `settings` (provinces, `min_eur`, `max_eur`,
   `activity`, `categories`) from `settings.json` in
   `$HERMES_HOME/appalti-lombardia/`, which it creates with defaults on its
   first run, and one report per province. For each province it reads every mapped page of every comune in that province (the tender
   list in Amministrazione trasparente, the albo pretorio, the news) in about
   three minutes, remembers what it has seen in `$HERMES_HOME/appalti-lombardia/`,
   and prints JSON: `new_items` (links that are new since the last run and look
   like works procurement), `needs_browser` (pages whose list is built by
   JavaScript) and `pages_failed`. Do not open the pages yourself: the scanner
   already did.

   The first run on a new Installation or a new province records everything
   already published: run it once with `--baseline`, and say in that day's
   report that monitoring started and the next reports will carry only new
   notices.

2. **Judge each new item.** Its `title` and `context` usually say what it is.
   Keep an item only when it is public works procurement (lavori or opere):
   a notice of the start of a consultation (art. 50 c. 2-bis), a market survey
   or call for expressions of interest, a negotiated procedure, a call for
   tenders, a determina a contrarre, or an award. Drop services, supplies,
   concessions, staff competitions, grants and section headings.

3. **Read what the list does not say.** For a kept item whose value, deadline,
   category or subject is unknown and could fit, open its `url` with
   `web_extract` (it reads PDFs too), or with the browser when the page needs
   it. Take the estimated value of the works, the deadline for expressions of
   interest or bids, the SOA category or CPV code, the procedure, and the
   RUP's contact. Open at most 40 items in one run, the most promising first;
   name any left unread in the report.

4. **Read the pages the scanner could not.** For each `needs_browser` page,
   open it with `browser_navigate` and read only the newest entries, at most
   the first screen of the list. Treat an entry as new only when it is dated
   after the previous report, which your previous run's output gives you.

5. **Match.** An item is a lead when it is works, its value is within
   `min_eur` and `max_eur` (or unknown but plausibly within),
   and its subject or category fits `activity` or `categories`.
   An award is never a lead, but it is market information worth one line.

6. **Report**, in Italian, in this order:
   - **Da valutare**: each lead with comune, subject, value, procedure, deadline,
     category, and the link to the notice. A deadline within seven days comes
     first, marked as urgent.
   - **Altri lavori pubblicati**: works items outside the range or the
     company's field, one line each.
   - **Aggiudicazioni**: who won what, one line each.
   - **Copertura**: how many comuni and pages were read, which failed, and any
     item left unread.

   When nothing new fits, say so in one sentence and still give the coverage
   line: the daily report doubles as proof the monitor ran.

## Settings

When the owner tells you what the company does, its SOA categories, the value
range or the provinces, write them into `settings.json` (the path the scanner
prints as `settings_file`) and show the owner the result. A province can be
monitored only when its file `assets/comuni-<province>.json` exists.

## Setting up the daily run

When the owner asks for it, create one scheduled task with the cron tool:
schedule `0 7 * * 1-6` (07:00 Monday to Saturday) or what the owner asks,
skill `appalti-lombardia`, `continuity` on so each run sees the previous
report, delivered to the channel the owner names. Before it, run step 1 once
with `--baseline` for every configured province.

## Pitfalls

- A list page shows the publication date of the notice, not the deadline: read
  the deadline from the notice itself.
- The same tender appears on the tender list, the albo and the news: report it
  once, with the most specific link.
- A determina a contrarre with a direct award to a named company is not an
  opportunity; a determina that starts a negotiated procedure is.
- An unknown value is not a reason to drop a works notice that fits the field.
- A province file lists each comune's pages as they were mapped; when a comune
  changes its site the scanner reports the page as failed. Report it under
  Copertura; do not guess a new address.

## Verification

Before sending, check that every lead has a working link to the comune's own
notice, that every value and deadline was read from the notice and not
inferred, and that the coverage line matches the scanner's counts.
