# state-watch

Snapshots the **state-level election pages for Florida and Texas** on a schedule
and stores each run as a **git commit**, so their content can be diffed over
time — the same ["git scraping"](https://simonwillison.net/2020/Oct/9/git-scraping/)
pattern as its two county siblings, one level up the federal structure.

This is the state counterpart to `fl-county-watch` (67 Supervisors of Elections)
and `tx-county-watch` (254 county governments). The snapshot pipeline
(`snapshot.py`, `normalize.py`, `noncitizen.py`) is shared with them almost
verbatim; the manifest and its column names are the only real difference.

## Why one repo for both states, and not `fl-state-watch` + `tx-state-watch`

Each state contributes six targets, not three hundred. Splitting them would
mean two more copies of the pipeline and two more schedulers to keep in sync
for a dozen pages between them, and every future state would cost another
repo. Here a new state is a row in `manifest/states.csv` and six rows in
`manifest/targets.csv`.

The county repos are split for the opposite reason: their *discovery* problem
is state-specific and their manifests are large and independently audited.
Neither is true at this level, where the targets were verified by hand.

## Layout

| path | role |
|---|---|
| `manifest/states.csv` | the states covered, and which office runs elections |
| `manifest/targets.csv` | one row per (state, page_type) — the scrape list |
| `scripts/snapshot.py` | fetch → normalize → 3 artifacts → one commit per run |
| `scripts/normalize.py` | strip volatile markup so an unchanged site diffs to zero |
| `scripts/noncitizen.py` | the non-citizen-voting flag written into `meta.json` |
| `scripts/scan_noncitizen.py` | that flag over the working tree or all history |
| `snapshots/{state}/{page_type}/` | `page.html`, `page.txt`, `meta.json` |

`state` is the lowercased postal code (`fl`, `tx`), so the tree is
`snapshots/tx/voter_registration/`.

## The six page types

Five match the county repos exactly, so a state row and a county row are
comparable. `voter_registration` is the sixth, added across all three repos at
the same time.

| page_type | FL | TX |
|---|---|---|
| `homepage` | Division of Elections landing | SOS Elections Division landing |
| `elections` | statewide election calendar | Important Election Dates |
| `voter_registration` | how to register / update | VoteTexas.gov register to vote |
| `polling` | voter & polling-place lookup | VoteTexas.gov polling-place finder |
| `early_voting` | early voting & intake stations | VoteTexas.gov early voting |
| `results` | Florida Election Watch | SOS Election Results/Data |

## What is different about each state

**Florida** runs everything from one host, `dos.fl.gov`. The exception is
results: Florida Election Watch is a separate domain, so that row is
`external`. The nav on `dos.fl.gov` is JavaScript-built and yields almost no
links to a plain crawl, which is why these targets were pinned by hand rather
than discovered — a link-scoring crawl finds nothing to score.

**Texas** splits its material across two domains owned by the same office: the
Secretary of State site for administrators, and `votetexas.gov` for voters.
Three of the six targets are therefore `external` without leaving the state's
own control. Two further traps are recorded in the manifest notes:

- `sos.state.tx.us` **403s a plain non-browser request** (a bare `curl` gets
  nothing). The complete browser header set in `snapshot.py` clears it, which
  is exactly what that header block exists for. If a run starts reporting 403s
  on Texas, suspect the headers before suspecting the state.
- `laws/current-elections-information.shtml` looks like the elections landing
  page and **redirects back to the division index**, so it is not used. The
  distinct calendar page is `voter/important-election-dates.shtml`.
- The live results app (`goelect.txelections.civixapps.com`) is a JavaScript
  shell that normalizes to roughly 800 characters. It would diff as noise
  around an election rather than signal, so `results` points at the SOS
  results/data page instead.

## The non-citizen-voting flag

Every `meta.json` carries:

```json
"noncitizen_voting": { "present": false, "terms": [], "count": 0 }
```

`present` is the binary answer. `terms` names which families matched, because
a `true` that cannot be explained six months later is barely better than no
flag. See `scripts/noncitizen.py` for what is matched and, more importantly,
for the two families deliberately **not** matched — "you must be a U.S.
citizen" and bare "citizenship" are eligibility boilerplate and would fire on
every registration page in the manifest.

It is computed from `page.txt`, never from the raw HTML or the live response,
so it is reproducible for any past commit:

```bash
python scripts/scan_noncitizen.py                     # working tree
python scripts/scan_noncitizen.py --history           # every snapshot commit
python scripts/scan_noncitizen.py --history --csv /tmp/panel.csv
```

As of the first run, 0 of 12 state pages match. Across the two county repos it
is 1 of 1,070 — an Indian River County news release about a new proof-of-
citizenship law, which first appeared on 2026-08-24. The flag is a tripwire;
`false` almost everywhere is the expected reading and the reason a `true` is
worth looking at.

## Running it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium

.venv/bin/python scripts/snapshot.py --no-commit   # write artifacts only
.venv/bin/python scripts/snapshot.py               # write + one commit
.venv/bin/python scripts/snapshot.py --state TX
.venv/bin/python scripts/snapshot.py --state TX --page-type results
```

Determinism is the property everything else rests on: re-running against an
unchanged site produces byte-identical `page.html` and `page.txt`. The only
volatile field is `fetched_at`, and it lives in `meta.json` alone. Verified on
the first two runs of all twelve targets.
