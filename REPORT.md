# What county election websites tell voters — and whether the state covers for them

**Data:** all snapshots current as of **2026-09-11** (TX 756 pages/254 counties,
FL 314 pages/67 counties, state sites 6 pages each). All three repos verified in
sync with origin.
**Status:** §3 retracted and rewritten (see §3a). **Four extractor recall
defects found and fixed** 2026-09-11 and 2026-09-14; every number below is
post-fix. **The staleness claim was hand-validated 2026-09-14 and fell from 27
to 11** (§5). Remaining known gaps in §7.

---

## 1. What I refreshed, and what was broken

The stored outputs were stale, one was silently frozen, and the extractors were
under-counting on four separate paths.

- **`tx_facts.csv` / `fl-consistency.csv` re-run** against 2026-09-11 snapshots.
- **`coverage_over_time.py` had a hardcoded commit list** and had stopped at
  2026-08-20 while three more weeks of daily runs accumulated. Replaced with
  auto-discovery; the series now runs **47 daily observations, 2026-07-29 →
  2026-09-11**.
- **The 90-vs-137 discrepancy flagged earlier was pure staleness.** The frozen
  series reported July 29's value against a current fact table. They reconcile.
- **Four recall defects fixed** — see §3a. 51 county-facts were recovered (TX
  +39, FL +12). Verification was uneven and is worth knowing: **all 19 TX
  polling-hours recoveries were audited individually** against the raw page
  window, as were the two false-positive classes; of the 21 TX date recoveries
  and 12 FL recoveries, roughly half were checked against raw page text and the
  rest only against the extracted evidence line. No incorrect recovery was
  found in what was checked.

## 2. Headline: counties state very little

Counting **only** verdicts the checker judged correct:

| fact | TX (n=254) | FL (n=67) | comparable? |
|---|---|---|---|
| Polling hours | 70 (27.6%) | 11 (16.4%) | yes — bias runs against |
| Election date | 162 (63.8%) | 53 (79.1%) | **no — confounded** |
| Registration deadline | 65 (25.6%) | 12 (17.9%) | yes — bias runs against |
| Early voting window | 49 (19.3%) | 11 (16.4%) | yes — bias runs against |

**Facts stated per county:**

- **TX — 26 of 254 counties (10.2%) state all four. 75 (29.5%) state none.**
- **FL — zero of 67 counties state all four.** Best any county manages is three
  (8 counties). 14 (20.9%) state none.

On the EAC's own two questions, Texas: **25.6%** of counties state the
registration deadline, **27.6%** state polling hours.

**Why the election-date column is not comparable.** Florida's `judge()` asks
whether `2026-11-03` appears *anywhere* among extracted values — a membership
test. Texas judges which election a sentence refers to before accepting it.
Florida's instrument is systematically more permissive, so where Florida is
nonetheless *lower* (three of four facts) the bias runs against the finding and
the gap is safe. Where Florida is higher, it is confounded and is not reported.

## 3. The backstop

When a county is silent, does the state site cover it?

| fact | TX counties silent | TX state site | FL counties silent | FL state site |
|---|---|---|---|---|
| Polling hours | 184/254 | **states it** | 56/67 | not in our targets* |
| Election date | 72/254 | states it | 3/67 | states it |
| Registration deadline | 181/254 | **states it** | 54/67 | **states it** |
| Early voting | 185/254 | states it† | 55/67 | **states it** |

\* Florida's DOE *does* state polling hours, on a page outside our six FL state
targets — see §3a. † The checker flags TX early voting as "states something
else"; **I verified by hand that the checker is wrong** — the TX SoS calendar
carries the correct window (Mon Oct 19 – Fri Oct 30, 2026, lines 229/236 of the
captured page). It mis-assigns because a statewide calendar lists several
elections. Still open; see §7.

**Both states have a state-level backstop. The asymmetry reported in the first
draft of this section does not exist.**

## 3a. Why §3 was wrong — four recall defects

The original §3 concluded Florida had no backstop for polling hours or early
voting. Both cells were wrong, for two different reasons, and chasing them
turned up two more defects.

**Defect A — target selection, not extraction.** The Florida Division of
Elections states polling hours verbatim — *"The polls are open on Election Day,
from 7 a.m. until 7 p.m. (local time)"* — on a page **not among our six FL state
targets**. Texas's target set happens to include its equivalent. The two states'
state-level targets were chosen independently, so that comparison was never
apples-to-apples. **Unfixed**; it is a sampling-frame problem, not a bug.

**Defect B — compact date ranges.** The FL state page says *"Early voting period
(mandatory period): October 24 - 31, 2026"* and the checker returned nothing. A
range in English elides the repeats; both checkers required month+day+year
adjacent. Fixed with `DATE_RANGE_RE`/`NUMRANGE_RE` plus de-duplication in TX's
`parse_dates` (callers test `len(dates) >= 2`, so a double-counted single date
read as a pair). The FL state site now reads "matches".

**Defect C — bare dates with no year.** *"Register by October 5"* parsed as
nothing in either repo. This was the larger hole. Fixed with `BARE_DATE_RE` /
`BARE_RANGE_RE` under a rule that **resolves** the year and never guesses it: a
bare date is emitted only when the surrounding text pins exactly **one** year
(TX: the line, then a ±2 window; FL: a ±2 window). Two years in scope means
ambiguous, and nothing is emitted — so a 2024 archive link cannot drag an
undated deadline into the current cycle. Negative tests enforce this.

**Defect D — the polling-hours vetoes.** `check_polling_hours` skipped the whole
`early_voting` page and vetoed any line near early-voting language. A census of
all 202 TX counties scored "never states polling hours" found **10 that state
the statutory 7–7 in so many words**: 6 lost to the page-type skip (counties
routinely put an "Election Day" block on their early-voting page), 3 to the
early-voting veto firing on an adjacent nav label ("Early Voting Reports"), 1 to
the poll-context test not recognising "General Election Tuesday 11/03/2026".
Fixed by letting a line that **names election day** and states the statutory
value bypass the vetoes.

**Effect of defects C and D, all hand-verified** (B was fixed in the previous
pass, so the "before" column already includes it):

| | before | after |
|---|---|---|
| TX polling hours | 52 | **70** |
| TX election date | 158 | **162** |
| TX registration deadline | 59 | **65** |
| TX early voting | 38 | **49** |
| FL matches (all facts) | 75 | **87** |

**Precision was checked, not assumed.** Two false-positive classes were found
and closed in the process: Freestone's early-voting 7–7 row being captured by an
"ELECTION DAY HOURS:" heading on the next line, and 11 counties that list
early-voting days one-per-line being reported as stating a *conflicting* window
when every date was inside the correct one.

**Residual recall risk is now small and measured.** Re-running the over-broad
census against the 184 counties still scored silent on polling hours leaves **2
candidates, both statements about past 2026 elections**. For the current cycle
the residual false-negative count is **0 of 184**.

## 4. Coverage rises as the election nears — except the one evergreen fact

Texas, 47 daily observations, 2026-07-29 → 2026-09-11, recomputed end to end
with the repaired extractors:

| measure | Jul 29 | Sep 11 |
|---|---|---|
| mean facts stated per county | 1.00 | **1.44** |
| counties stating none | 126 | **75** |
| counties stating all four | 19 | **26** |
| — Election date | 91 | **163** |
| — Registration deadline | 44 | **67** |
| — Early voting window | 48 | **67** |
| — **Polling hours** | 72 | **70** |

Every calendar-driven fact climbs by 40–79%. **Polling hours does not move** —
and it is the only fact that is evergreen, fixed by statute at 7 a.m.–7 p.m.,
true at every election.

**This finding survived the instrument repair, which is the strongest thing that
can be said for it.** The fixes raised the polling-hours level at *both*
endpoints (53→72 in July, 52→70 in September) and left the slope flat. A finding
that were an extractor artifact would have moved when the extractor did.

The mechanism is legible: these pages get edited when a date forces someone to
touch them, and nothing forces anyone to add what is permanently true. It also
means **any single-snapshot audit of election websites reports a number that
depends entirely on when it looked** — including the EAC's 2005–06 study. That
is a methods contribution the longitudinal data supports and a one-shot audit
cannot.

## 5. Failure modes: silence is not the only way to fail a voter

| | TX | FL |
|---|---|---|
| stale (shows only a past election) | **11** county-facts (validated, was 27) | — |
| conflicts / internally inconsistent | — | 2 |
| not-named (names a past election, not the general) | — | 11 |

**All 27 TX "stale" rows were read against their raw page context on
2026-09-14. Only 11 are real** (`comparative/output/stale_validation.csv`):

| adjudication | n | what it is |
|---|---|---|
| genuine stale | **11** | a live block on the page presents a past election as current |
| archive artifact | **14** | the matched line is a results/records file listing |
| checker error | 2 | see §7 |

**The 14 archive artifacts are counties doing something RIGHT.** Castro's line
is "Post Election Hand Count Summary & Certification May 26 Runoff (PDF)";
Young's is "Public Notice of LAT of Pollbook - 04/08/2026"; Willacy's is a set
of daily early-voting rosters. Those are statutory election records, correctly
published and correctly dated. The checker read a filing cabinet as a claim
about the next election. This is the same defect fixed on the Florida side for
Hamilton and it is **still live in the Texas checker**.

What survives is a cleaner and smaller claim. The 11 real cases are pages where
a voter arriving today is actively misinformed — Roberts still says
"-ELECTION DAY VOTING- FOR PRIMARY ELECTION Tuesday, March 3, 2026";
Schleicher still runs an "Election Dates" block for the May 26 runoff;
Childress's "VOTING HOURS AND POLL PLACE INFORMATION" still describes February
early voting. A blank page tells a voter nothing; these tell them something
false with the county's authority behind it. **These are different harms and
the literature does not separate them** -- but the honest magnitude is 11 of
254 counties, not 27 county-facts.

## 6. What does NOT hold

**Vendor does not predict content.** Mean facts stated by platform (TX): ezTask
1.34 (n=167), CivicPlus 1.67 (n=39), WordPress 2.12 (n=8), Revize 2.29 (n=7),
Granicus/Vision 0.50 (n=6). Florida: WordPress 1.45 (n=22), CivicPlus 1.13
(n=15), Revize 1.33 (n=9). Cells outside the top two are too small to carry
weight, and the ordering is not stable across states.

This is a real refinement, not a failure. **Vendor sharply determines
infrastructure policy — robots.txt was 42/42 CivicPlus vs 8/165 ezTask — and
does not determine what the county says.** Content is county-staff behavior; the
platform sets what the site *can* do, not what gets written on it.

**Rurality shows no gradient.** Nonmetro rural 1.38 (n=92), nonmetro urban core
1.50 (n=76), medium metro 1.14 (n=35), large metro 1.71 (n=34), small metro 1.65
(n=17). Non-monotonic; medium metros are the worst performers. There is no clean
rural-deficit story here.

## 7. QA — read before presenting

**Defect 1 (open): `early_voting_window` "States something else" (18 TX
counties) is still mostly noise.** Down from 37 after the repairs, but the
remainder pairs unrelated dates near loose early-voting language — Caldwell and
Nolan pair the Oct 5 registration deadline with the Oct 19 EV start; Coke,
Collingsworth, Edwards and Shackelford pair Nov 3 with a past runoff; Gillespie
pairs January 1 with October 5. None is a claim about a *window*.

**This changes the headline.** Counting that class as "stated" gives 30 TX
counties stating all four. Excluding it gives **26**. Every number in this
report uses the strict count.

**Defect 2 (open): the state-level early-voting mis-assignment** described in §3
— the checker cannot pick the right election from a multi-election calendar.

**Defect 3 (open): FL/TX instrument asymmetry.** FL's `judge()` is a membership
test; TX judges election context. Resolving it means running one checker's logic
over both states — real work, not a flag. Until then the election-date
comparison stays out of the report.

**Defect 4 (open): FL state-target sampling frame** (§3a, Defect A). The six FL
state targets do not functionally match the six TX ones.

**Now validated, previously listed here as the gating risk:** recall on TX
polling hours. A census — not a sample — of all 202 counties scored "never
states it" found 10 genuine false negatives, all now fixed, with 0 residual for
the current cycle (§3a). **The headline no longer rests on an unvalidated
null.**

**Defect 5 (open, TX only): results archives read as stale claims.** 14 of the
27 rows scored "shows only a past election" are matches against a results or
records file listing -- "Post Election Hand Count Summary ... (PDF)", "Notice of
Canvassing", "EARLY VOTING ROSTERS", "Public Notice of LAT of Pollbook". Those
are statutory records, published correctly. The Florida checker was fixed for
exactly this (Hamilton's 2007 book-closing dates); **Texas has not been.**
Fixing it moves those 14 from "stale" to "never states it", which lowers the
staleness count and raises silence by the same amount.

**Defect 6 (open, small): bare-date year resolution can pick a stale year.**
Panola's "November 3rd Uniform Election" resolved to 2025 from a "Printing
Friendly Nov Schedule 2025" filename two lines away; Nov 3 2025 was a Monday and
not an election date, so the county almost certainly means Nov 3 2026 and the
row should be a match. Measured blast radius: **1 wrong in the 25 verdicts that
depend on bare-date resolution** -- the other 24 are correct, including 21
hand-verified recoveries. Tightening the year source to the same line was tested
and rejected: it costs two verified-correct matches (Angelina, Maverick) to fix
this one.

**Now validated, and it cut the claim by 60%:** the "stale" rows. All 27 were
read against raw page context; 11 are genuine, 14 are archive artifacts, 2 are
checker errors. See §5 and `comparative/output/stale_validation.csv`.

**Numbers safe to use now:** TX counties stating all four (26), stating none
(75), the four TX correct-rates, the 47-day time series, the backstop
comparison, the recall census, and the validated staleness count (11).

**Numbers not safe yet:** anything derived from "States something else", and
TX-vs-FL election date.

---

*Scripts: `comparative/scripts/state_facts.py` (state-level extraction, reusing
each state's own checker), `comparative/scripts/compare.py` (all tables above).
Tests: `comparative/tests/test_date_ranges.py`, 34 assertions covering both
repos. Outputs: `comparative/output/state_facts.csv`.*
