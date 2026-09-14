#!/usr/bin/env python3
"""County vs county, state vs county: what do election sites actually state?

Joins the current TX and FL fact verdicts to their covariates and prints every
table the report is built from. Nothing here re-extracts; it reads the outputs
of each repo's own checker so the numbers can be traced back to auditable rows.

THE ONE COMPARISON THAT IS NOT CLEAN. The two checkers are not equally strict.
Florida's judge() asks whether the expected value appears ANYWHERE among the
values a county stated (a membership test). Texas asks which election a sentence
refers to before accepting it. So Florida's "matches" rate is biased UPWARD
relative to Texas's. Where Florida is nonetheless LOWER, the bias runs against
the finding and the gap is safe to report; where Florida is higher
(election_date) it is confounded and is not compared.
"""

from __future__ import annotations

import collections
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT.parent
OUT = ROOT / "output"

TX_N, FL_N = 254, 67
# The two repos name the same fact differently.
FACT_PAIRS = [("polling_hours", "poll_hours", "Polling hours"),
              ("election_date", "election_date", "Election date"),
              ("registration_deadline", "registration_deadline", "Registration deadline"),
              ("early_voting_window", "early_voting", "Early voting window")]
TX_STATED = ("Matches expected", "States something else")


def load():
    tx = list(csv.DictReader((REPOS / "tx-county-watch" / "analysis" / "output"
                              / "tx_facts.csv").open()))
    fl = list(csv.DictReader((REPOS / "fl-county-watch" / "manifest"
                              / "fl-consistency.csv").open()))
    cov = {r["county"]: r for r in csv.DictReader(
        (REPOS / "tx-county-watch" / "analysis" / "output" / "tx_covariates.csv").open())}
    att = {r["county"].strip().lower(): r for r in csv.DictReader(
        (REPOS / "fl-county-watch" / "manifest" / "fl-county-attributes.csv").open())}
    st = list(csv.DictReader((OUT / "state_facts.csv").open()))
    return tx, fl, cov, att, st


def pct(n, d):
    return f"{n:>4} ({100*n/d:4.1f}%)"


def main() -> None:
    tx, fl, cov, att, st = load()

    print("=" * 78)
    print("1. DOES THE COUNTY STATE THE FACT CORRECTLY? (current, 2026-09-11)")
    print("=" * 78)
    print(f"{'fact':<24}{'TX (n=254)':>18}{'FL (n=67)':>18}   comparable?")
    for txf, flf, label in FACT_PAIRS:
        t = sum(1 for r in tx if r["fact"] == txf and r["verdict"] == "Matches expected")
        f = sum(1 for r in fl if r["fact"] == flf and r["verdict"] == "matches")
        note = "confounded" if (100*f/FL_N) > (100*t/TX_N) else "safe (bias against)"
        print(f"{label:<24}{pct(t,TX_N):>18}{pct(f,FL_N):>18}   {note}")

    print("\n" + "=" * 78)
    print("2. FAILURE MODES — silence is not the only way to fail a voter")
    print("=" * 78)
    for txf, flf, label in FACT_PAIRS:
        t = collections.Counter(r["verdict"] for r in tx if r["fact"] == txf)
        f = collections.Counter(r["verdict"] for r in fl if r["fact"] == flf)
        print(f"\n  {label}")
        print(f"    TX  correct={t['Matches expected']:>3}  "
              f"wrong-value={t['States something else']:>3}  "
              f"stale={t['Shows only a past election']:>3}  "
              f"silent={t['Never states it']:>3}")
        print(f"    FL  correct={f['matches']:>3}  "
              f"conflicts={f['conflicts']:>3}  "
              f"not-named={f['next election not named']:>3}  "
              f"silent={f['not stated']:>3}")

    print("\n" + "=" * 78)
    print("3. HOW MANY FACTS DOES A COUNTY STATE AT ALL?")
    print("=" * 78)
    txc = collections.Counter()
    for c in {r["county"] for r in tx}:
        txc[sum(1 for r in tx if r["county"] == c and r["verdict"] in TX_STATED)] += 1
    flc = collections.Counter()
    for c in {r["county"] for r in fl}:
        flc[sum(1 for r in fl if r["county"] == c and r["verdict"] == "matches")] += 1
    print("  TX facts stated:", ", ".join(f"{k}:{txc[k]}" for k in sorted(txc, reverse=True)))
    print("  FL facts stated:", ", ".join(f"{k}:{flc[k]}" for k in sorted(flc, reverse=True)))

    print("\n" + "=" * 78)
    print("4. THE BACKSTOP — does the STATE state what counties omit?")
    print("=" * 78)
    for txf, flf, label in FACT_PAIRS:
        srow = next((r for r in st if r["fact"] in (txf, flf) and r["state"] == "TX"), None)
        frow = next((r for r in st if r["fact"] in (txf, flf) and r["state"] == "FL"), None)
        tsil = sum(1 for r in tx if r["fact"] == txf and r["verdict"] == "Never states it")
        fsil = sum(1 for r in fl if r["fact"] == flf and r["verdict"] == "not stated")
        print(f"\n  {label}")
        print(f"    TX  counties silent: {tsil:>3}/254   state site: {srow['verdict'] if srow else '?'}")
        print(f"    FL  counties silent: {fsil:>3}/67    state site: {frow['verdict'] if frow else '?'}")

    print("\n" + "=" * 78)
    print("5. WHAT PREDICTS STATING FACTS? (TX; vendor first)")
    print("=" * 78)
    by_plat = collections.defaultdict(list)
    by_rucc = collections.defaultdict(list)
    for c, r in cov.items():
        n = sum(1 for x in tx if x["county"] == c and x["verdict"] in TX_STATED)
        by_plat[r["platform"]].append(n)
        by_rucc[r["rucc_band"]].append(n)
    print(f"\n  {'platform':<32}{'n':>5}{'mean facts':>12}")
    for k, v in sorted(by_plat.items(), key=lambda x: -len(x[1])):
        print(f"  {k[:31]:<32}{len(v):>5}{sum(v)/len(v):>12.2f}")
    print(f"\n  {'rurality (RUCC band)':<32}{'n':>5}{'mean facts':>12}")
    for k, v in sorted(by_rucc.items(), key=lambda x: -len(x[1])):
        print(f"  {k[:31]:<32}{len(v):>5}{sum(v)/len(v):>12.2f}")

    print(f"\n  {'FL platform':<32}{'n':>5}{'mean facts':>12}")
    by_fp = collections.defaultdict(list)
    for c, r in att.items():
        n = sum(1 for x in fl if x["county"].strip().lower() == c
                and x["verdict"] == "matches")
        by_fp[r.get("platform", "?")].append(n)
    for k, v in sorted(by_fp.items(), key=lambda x: -len(x[1])):
        print(f"  {k[:31]:<32}{len(v):>5}{sum(v)/len(v):>12.2f}")


if __name__ == "__main__":
    main()
