#!/usr/bin/env python3
"""Date-range recall for both fact checkers.

A date range in English elides the repeated parts - the year, and often the
month, appear only on the LAST endpoint. Both checkers' date regexes required
month+day+year adjacent, so they saw one endpoint or none. This is what made the
FL state site's literal "Early voting period (mandatory period): October 24 - 31,
2026" read as "not stated".

Run:  python comparative/tests/test_date_ranges.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPOS = Path(__file__).resolve().parent.parent.parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


TX = load("check_facts", REPOS / "tx-county-watch" / "analysis" / "check_facts.py")
FL = load("check_consistency", REPOS / "fl-county-watch" / "scripts" / "check_consistency.py")

OCT19, OCT30 = (2026, 10, 19), (2026, 10, 30)

# (label, text, expected dates present)
RANGE_CASES = [
    ("compact, month once",      "Early voting October 19 - 30, 2026", [OCT19, OCT30]),
    ("compact, en dash",         "Early voting October 19 – 30, 2026", [OCT19, OCT30]),
    ("compact, em dash",         "Early voting October 19 — 30, 2026", [OCT19, OCT30]),
    ("month repeated",           "Early voting October 19 - October 30, 2026", [OCT19, OCT30]),
    ("word 'through'",           "Early voting October 19 through 30, 2026", [OCT19, OCT30]),
    ("word 'to'",                "Early voting October 19 to October 30, 2026", [OCT19, OCT30]),
    ("abbreviated month",        "Early voting Oct. 19 - 30, 2026", [OCT19, OCT30]),
    ("both years (regression)",  "Early voting October 19, 2026 through October 30, 2026",
     [OCT19, OCT30]),
    ("numeric range",            "Early voting 10/19 - 10/30/2026", [OCT19, OCT30]),
    ("cross-month",              "Early voting October 19 - November 1, 2026",
     [OCT19, (2026, 11, 1)]),
]

# Must NOT produce a spurious pair: two unrelated dates in separate sentences.
NEGATIVE_CASES = [
    ("separate sentences",
     "Register by October 5. Early voting ends October 30, 2026.", OCT19),
    ("single date only", "Early voting ends October 30, 2026", OCT19),
]


# --- bare dates: month + day, no year anywhere on the phrase ---------------
# "Register by October 5" is a complete claim to a human because the year is
# established elsewhere on the page. Neither checker saw it at all. The year is
# RESOLVED FROM THE TEXT, never guessed: a bare date is emitted only when the
# surrounding text pins exactly one year (or the caller supplies a hint).
BARE_CASES = [
    ("bare day, year later in text",
     "Election Day is November 3, 2026. Register by October 5.", [(2026, 10, 5)]),
    ("bare day, year earlier in text",
     "The November 3, 2026 General Election. Last day to register: October 5.",
     [(2026, 10, 5)]),
    ("bare range, year elsewhere",
     "Early voting runs October 19-30. Election Day is November 3, 2026.",
     [OCT19, OCT30]),
    ("bare cross-month range",
     "Early voting October 19 - November 1. General Election November 3, 2026.",
     [OCT19, (2026, 11, 1)]),
    ("bare with ordinal suffix",
     "General Election November 3, 2026. Register by October 5th.", [(2026, 10, 5)]),
]

# A year must never be INVENTED. No year in the text -> no date.
BARE_NEGATIVE = [
    ("no year anywhere",        "Register by October 5.", (2026, 10, 5)),
    ("no year, range",          "Early voting October 19-30.", OCT19),
    ("two years = ambiguous",
     "Archive from November 4, 2024. See the 2026 calendar. Register by October 5.",
     (2026, 10, 5)),
]


def tx_dates(text):
    return TX.parse_dates(text)


def fl_dates(text):
    got = FL.extract(text, "elections")
    vals = got["early_voting"] + got["election_date"] + got["registration_deadline"]
    out = []
    for v in vals:
        y, m, d = v.split("-")
        out.append((int(y), int(m), int(d)))
    return out


def main() -> None:
    fails = 0
    print(f"{'case':<28}{'TX':>8}{'FL':>8}")
    for label, text, expected in RANGE_CASES:
        t, f = tx_dates(text), fl_dates(text)
        tok = all(e in t for e in expected)
        fok = all(e in f for e in expected)
        fails += (not tok) + (not fok)
        print(f"{label:<28}{'PASS' if tok else 'FAIL':>8}{'PASS' if fok else 'FAIL':>8}")

    print(f"\n{'negative (must NOT appear)':<28}{'TX':>8}{'FL':>8}")
    for label, text, forbidden in NEGATIVE_CASES:
        t, f = tx_dates(text), fl_dates(text)
        tok, fok = forbidden not in t, forbidden not in f
        fails += (not tok) + (not fok)
        print(f"{label:<28}{'PASS' if tok else 'FAIL':>8}{'PASS' if fok else 'FAIL':>8}")

    print(f"\n{'bare date (year from text)':<28}{'TX':>8}{'FL':>8}")
    for label, text, expected in BARE_CASES:
        t, f = tx_dates(text), fl_dates(text)
        tok = all(e in t for e in expected)
        fok = all(e in f for e in expected)
        fails += (not tok) + (not fok)
        print(f"{label:<28}{'PASS' if tok else 'FAIL':>8}{'PASS' if fok else 'FAIL':>8}")

    print(f"\n{'bare negative (no invented yr)':<28}{'TX':>8}{'FL':>8}")
    for label, text, forbidden in BARE_NEGATIVE:
        t, f = tx_dates(text), fl_dates(text)
        tok, fok = forbidden not in t, forbidden not in f
        fails += (not tok) + (not fok)
        print(f"{label:<28}{'PASS' if tok else 'FAIL':>8}{'PASS' if fok else 'FAIL':>8}")

    print(f"\n{fails} failing assertion(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
