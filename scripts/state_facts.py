#!/usr/bin/env python3
"""Run each state's OWN fact checker against that state's SECRETARY OF STATE site.

The backstop question: when a county does not state an operational election
fact, does the state site state it? Counties and the state are only comparable
if they are judged by the same instrument, so this reuses the county checkers
verbatim rather than writing a third one:

  TX  tx-county-watch/analysis/check_facts.py   (CHECKS, load_pages)
  FL  fl-county-watch/scripts/check_consistency.py (extract, judge)

Each checker carries its own state's authoritative values, which is why they
cannot be swapped: the Texas early-voting window is not Florida's.

Input : state-watch/{tx,fl}/snapshots/{tx,fl}/<page_type>/page.txt
Output: comparative/output/state_facts.csv
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT.parent
OUT = ROOT / "output"
STATE_WATCH = REPOS / "state-watch"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def texas() -> list[dict]:
    """Point the TX county checker at the TX SoS snapshots."""
    tx_analysis = REPOS / "tx-county-watch" / "analysis"
    sys.path.insert(0, str(tx_analysis))
    cf = load_module("check_facts", tx_analysis / "check_facts.py")
    cf.SNAP = STATE_WATCH / "tx" / "snapshots"
    pages = cf.load_pages("tx")
    rows = []
    for fact in cf.FACTS:
        verdict, evidence, why = cf.CHECKS[fact](pages)
        rows.append({
            "state": "TX", "level": "state", "fact": fact,
            "verdict": verdict, "matched_text": evidence[:300], "why": why[:200],
            "pages_captured": len(pages),
        })
    return rows


def florida() -> list[dict]:
    """Run the FL county extractor/judge over the FL DOE snapshots."""
    fl_scripts = REPOS / "fl-county-watch" / "scripts"
    sys.path.insert(0, str(fl_scripts))
    cc = load_module("check_consistency", fl_scripts / "check_consistency.py")
    snap = STATE_WATCH / "fl" / "snapshots" / "fl"
    seen: dict[str, dict[str, list[str]]] = {f: defaultdict(list) for f in cc.FACTS}
    pages = 0
    for f in sorted(snap.glob("*/page.txt")):
        pages += 1
        got = cc.extract(f.read_text(encoding="utf-8", errors="ignore"), f.parent.name)
        for fact, vals in got.items():
            for v in vals:
                seen[fact][v].append(f.parent.name)
    rows = []
    for fact in cc.FACTS:
        values = list(seen[fact])
        verdict, detail = cc.judge(fact, values)
        rows.append({
            "state": "FL", "level": "state", "fact": fact,
            "verdict": verdict, "matched_text": " | ".join(values)[:300],
            "why": detail[:200], "pages_captured": pages,
        })
    return rows


def main() -> None:
    rows = texas() + florida()
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "state_facts.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {dest} ({len(rows)} rows)\n")
    for r in rows:
        print(f"  {r['state']}  {r['fact']:<24} {r['verdict']:<26} "
              f"pages={r['pages_captured']}")
        if r["matched_text"]:
            print(f"        evidence: {r['matched_text'][:150]}")


if __name__ == "__main__":
    main()
