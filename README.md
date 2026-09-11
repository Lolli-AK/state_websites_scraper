# state_websites_scraper

Snapshots the **state-level election pages for Florida and Texas** on a schedule
and stores each run as a **git commit**, so their content can be diffed over
time — the same ["git scraping"](https://simonwillison.net/2020/Oct/9/git-scraping/)
pattern as its two county siblings, one level up the federal structure.

This is the state counterpart to `fl-county-watch` (67 Supervisors of Elections)
and `tx-county-watch` (254 county governments). The snapshot pipeline
(`snapshot.py`, `normalize.py`, `noncitizen.py`) is shared with them almost
verbatim; the manifest and its column names are the only real difference.

## One repo, two independent scrapers

`tx/` and `fl/` each hold a manifest, a copy of the pipeline, a snapshot tree, a
test suite and a workflow. They share nothing but the repository they commit to.

The two states are on different statutory calendars, so they raise capture
cadence on different days, and neither should be able to change the other's
behaviour. What that costs is duplication: **`normalize.py` and `noncitizen.py`
exist twice**, and a rule fixed in one copy and not the other will drift without
anything failing. Nothing in the four scripts is state-specific — the state
comes from the manifest and from which directory the run happens in — so they
are byte-identical today and should stay that way:

```bash
diff -r -x '__pycache__' tx/scripts fl/scripts    # expected: no output
```

The county repos' determinism rules transfer between states precisely because
they are identical; output from that command is drift, not configuration.

## Layout

| path | role |
|---|---|
| `tx/`, `fl/` | one self-contained scraper per state |
| `{state}/manifest/states.csv` | the state covered, and which office runs elections |
| `{state}/manifest/targets.csv` | one row per page_type — the scrape list |
| `{state}/scripts/snapshot.py` | fetch → normalize → 3 artifacts → one commit per run |
| `{state}/scripts/normalize.py` | strip volatile markup so an unchanged site diffs to zero |
| `{state}/scripts/noncitizen.py` | the non-citizen-voting flag written into `meta.json` |
| `{state}/scripts/scan_noncitizen.py` | that flag over the working tree or all history |
| `{state}/snapshots/{state}/{page_type}/` | `page.html`, `page.txt`, `meta.json` |
| `.github/workflows/snapshot-{state}.yml` | that state's schedule and cadence window |

The state appears twice in a snapshot path — `tx/snapshots/tx/results/` — and
that is deliberate rather than tidy. `snapshot.py` and `scan_noncitizen.py` are
the county repos' files with `county` renamed to `state`, and both derive the
unit from the first path segment under `snapshots/`. Flattening the inner level
would fork them from their county counterparts and cost the panel its `unit`
column, for no gain beyond a shorter path.

## Cadence, and why the two states differ

Both scrapers run a daily baseline and raise to every three hours inside an
automatic window. The windows are **not** the same, because early voting is not:

| | early voting, 2026 general | window opens | window closes |
|---|---|---|---|
| Texas | Oct 19 – Oct 30 | **Oct 15** | Nov 17 |
| Florida | Oct 24 – Oct 31 | **Oct 20** | Nov 17 |

Each start is four days before that state's own early voting opens, matching
the lead its county repo uses, so a state series and its county series raise
cadence on the same day. Both windows close Nov 17: election day is Nov 3 in
both states, and the tail exists for the post-election takedown curve.

The dates are hardcoded in each workflow's gate step with the statute cited.
`ELECTION_WINDOW_TX` / `ELECTION_WINDOW_FL` are per-state manual overrides and
still work in both directions. Neither requires a human to remember anything.

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
cd tx        # or: cd fl
python scripts/scan_noncitizen.py                     # working tree
python scripts/scan_noncitizen.py --history           # every snapshot commit
python scripts/scan_noncitizen.py --history --csv /tmp/panel.csv
```

**It is a tripwire, and `false` is the expected reading.** 0 of 12 state pages
match. Across the full history of the two county repos it is 0 of 28,821
Texas page-observations and 19 of 46,221 in Florida — and those 19 are all one
page. Indian River County's homepage carried a news headline about a new
proof-of-citizenship law from 2026-08-24 to 08-26, but the release itself is
dated **22 April**: it surfaced only because the county's post-primary news
carousel rotated older items back into view, and rotated away again by 09-01.
On a homepage this flag measures carousel position, not what a county is
saying. Read a `true` on a rotating page against the item's own publication
date before treating it as a change.

Three known false negatives, all on Florida county registration pages:
Miami-Dade names the federal SAVE
verification service but writes "online service (SAVE)", which the
`save_program` pattern misses because it requires SAVE to be followed by
program/database/system; and Columbia and Marion both state that a lawful
permanent resident cannot register or vote, which the eligibility-boilerplate
exclusion drops.

## Running it

Each state is its own working directory. There is no top-level entry point.

```bash
cd tx        # or: cd fl
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium

.venv/bin/python scripts/snapshot.py --no-commit   # write artifacts only
.venv/bin/python scripts/snapshot.py               # write + one commit
.venv/bin/python scripts/snapshot.py --page-type results
```

`--state` still works, but a manifest here holds one state, so it has nothing
to filter. `snapshot.py` stages with `git add -A .` scoped to
its own directory, so a Texas run cannot commit Florida's tree.

Determinism is the property everything else rests on: re-running against an
unchanged site produces byte-identical `page.html` and `page.txt`. The only
volatile field is `fetched_at`, and it lives in `meta.json` alone. Verified on
the first two runs of all twelve targets.
