#!/usr/bin/env python3
"""Join the robots.txt and ToS audits into one county-level table + a summary.

The headline comparison is POLICY vs PRACTICE: what a county's machine-readable
(robots.txt) and human-readable (terms of use) policies say about automated
access, against what its server actually did when we fetched it.
"""

from __future__ import annotations

import collections
import csv
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT.parent
OUT = ROOT / "output"


def main() -> None:
    robots = {r["host"]: r for r in csv.DictReader((OUT / "robots_index.csv").open())}
    tos = collections.defaultdict(list)
    for r in csv.DictReader((OUT / "tos_clauses.csv").open()):
        tos[(r["state"], r["county"])].append(r)

    rows = []
    for state, repo in (("TX", "tx-county-watch"), ("FL", "fl-county-watch")):
        targets = collections.defaultdict(list)
        for t in csv.DictReader((REPOS / repo / "manifest" / "targets.csv").open()):
            targets[t["county"].strip().lower()].append(t)
        for county, ts in sorted(targets.items()):
            hosts = {urlparse(t["url"]).netloc.lower() for t in ts if t.get("url")}
            rs = [robots[h] for h in hosts if h in robots]
            legal = tos.get((state, county), [])
            usable = [l for l in legal
                      if l["http_status"] == "200" and l["is_pdf"] == "false"
                      and int(l["n_chars"]) > 200]
            rows.append({
                "state": state, "county": county,
                "n_hosts": len(hosts),
                "n_targets_captured": sum(t["verify_status"] == "ok" for t in ts),
                "n_targets_gap": sum(t["verify_status"] == "gap" for t in ts),
                "any_robots": "true" if any(r["has_robots"] == "true" for r in rs) else "false",
                "all_hosts_robots": "true" if rs and all(r["has_robots"] == "true" for r in rs) else "false",
                "crawl_delay": max((float(r["crawl_delay_star"]) for r in rs
                                    if r["crawl_delay_star"]), default=""),
                "blocks_all_star": "true" if any(r["blocks_all_star"] == "true" for r in rs) else "false",
                "n_targets_disallowed": sum(int(r["n_targets_disallowed"]) for r in rs),
                "blocks_ai_bots": "true" if any(int(r["n_ai_blocked"]) > 0 for r in rs) else "false",
                "robots_403": "true" if any(r["http_status"] == "403" for r in rs) else "false",
                "has_legal_page": "true" if usable else "false",
                "legal_403": "true" if any(l["http_status"] == "403" for l in legal) else "false",
                "tos_anti_scraping": "true" if any(l["anti_scraping"] == "true" for l in usable) else "false",
                "tos_permission_required": "true" if any(l["permission_required"] == "true" for l in usable) else "false",
                "tos_commercial_use": "true" if any(l["commercial_use"] == "true" for l in usable) else "false",
            })

    with (OUT / "scrapeability_policy_by_county.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT/'scrapeability_policy_by_county.csv'} ({len(rows)} counties)")

    print("\n=== POLICY vs PRACTICE ===")
    for state in ("TX", "FL"):
        sub = [r for r in rows if r["state"] == state]
        n = len(sub)
        def p(f):
            k = sum(1 for r in sub if f(r))
            return f"{k:>3} ({100*k/n:4.1f}%)"
        print(f"\n{state} (n={n})")
        print(f"  any robots.txt                 {p(lambda r: r['any_robots']=='true')}")
        print(f"  robots.txt disallows a page we capture  {p(lambda r: r['n_targets_disallowed']>0)}")
        print(f"  robots.txt blocks >=1 AI crawler        {p(lambda r: r['blocks_ai_bots']=='true')}")
        print(f"  publishes a readable legal page         {p(lambda r: r['has_legal_page']=='true')}")
        print(f"  ToS forbids robots/automated access     {p(lambda r: r['tos_anti_scraping']=='true')}")
        print(f"  ToS requires prior written permission   {p(lambda r: r['tos_permission_required']=='true')}")
        print(f"  NO policy of either kind                {p(lambda r: r['any_robots']=='false' and r['has_legal_page']=='false')}")

    print("\n=== the two policies disagree ===")
    both = [r for r in rows if r["tos_anti_scraping"] == "true"]
    print(f"{len(both)} counties forbid robots in their ToS; of those:")
    print(f"  publish a robots.txt:            {sum(r['any_robots']=='true' for r in both)}")
    print(f"  robots.txt actually disallows us:{sum(r['n_targets_disallowed']>0 for r in both)}")
    print(f"  pages we successfully captured:  {sum(r['n_targets_captured'] for r in both)}")


if __name__ == "__main__":
    main()
