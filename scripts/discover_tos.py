#!/usr/bin/env python3
"""Find each county's terms-of-use / legal / privacy page.

Candidates come from the homepages ALREADY captured in the two watch repos, so
discovery costs no requests. Only the legal pages themselves are fetched
(fetch_tos.py).

Two traps, both of which would inflate the count:
  * "Terms" in a county CMS footer often links to the CMS VENDOR's own terms
    (civicplus.com/terms), not the county's. That is the vendor's policy, and
    it is recorded as such rather than credited to the county.
  * ADA/accessibility statements and public-records notices sit in the same
    footer and match loosely on "policy". They are a different document and are
    classified separately.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT.parent
OUT = ROOT / "output"

# "Terms" is load-bearing elsewhere in Texas county government and a bare match
# on the word is noise, not a website policy. Rejected before any classification:
# a district judge's "Terms of Court", an elected official's "term of office",
# and "Purchase Order Terms and Conditions" from the purchasing department.
TERMS_NEGATIVE = re.compile(
    r"terms?\s*of\s*(court|office)|term\s*limits?|offices?\s*and\s*terms|"
    r"(purchase|purchasing|payment|sale|contract|bid|lease)\s*(order\s*)?terms|"
    r"terms\s*(and\s*conditions\s*)?of\s*(purchase|sale|payment)|"
    # href path context: /departments/purchasing/terms is the purchasing
    # department's boilerplate, not the website's policy.
    r"/(purchasing|purchase|procurement|bids?|finance|auditor)/[^ ]*terms", re.I)

# ...so a `terms` hit must also carry a website-policy signal.
TERMS_POSITIVE = re.compile(
    r"terms\s*of\s*(use|service)|terms\s*(and|&)\s*conditions\s*of\s*use|"
    r"conditions\s*of\s*use|user\s*agreement|acceptable\s*use|"
    r"(website|site|web)\s*terms|terms.{0,20}(website|site|web)|"
    r"/(tou|terms[-_]?of[-_]?(use|service)|termsandconditions|terms)\b", re.I)

# (kind, regex over link text and href). Order matters: first match classifies.
PATTERNS = [
    ("terms",        r"terms\s*(of\s*(use|service|agreement))?|terms[-_]?(and|&)?[-_]?conditions|conditions\s*of\s*use|user\s*agreement|acceptable\s*use"),
    ("disclaimer",   r"disclaimer|legal\s*notice|legal\s*disclaimer"),
    ("privacy",      r"privacy(\s*(policy|statement|notice))?"),
    ("copyright",    r"copyright|intellectual\s*property"),
    ("accessibility", r"accessibility|ada\s*(compliance|notice|policy)|section\s*508"),
    ("records",      r"public\s*(information|records)\s*(act|request)|open\s*records|foia"),
    # A bare "Policies" link in a Texas county footer is an employee handbook,
    # an investment policy or an animal-control ordinance far more often than a
    # website policy, so this requires explicit web context.
    ("legal_other",  r"^\s*legal\s*(notices?)?\s*$|(web\s*site|website|site|web)\s*polic|"
                     r"polic(y|ies)\s*(for\s*)?(this\s*)?(web\s*site|website)|"
                     r"/(website|site)[-_]?polic"),
]

VENDOR_HOSTS = ("civicplus.com", "eztasktitanium.com", "revize.com", "granicus.com",
                "vision internet", "visioninternet.com", "wix.com", "squarespace.com",
                "govoffice.com", "evogov.com", "tylertech.com", "wordpress.org",
                "automattic.com", "audioeye.com", "accessibe.com", "userway.org",
                "google.com", "adobe.com")


def classify(text: str, href: str) -> str | None:
    blob = f"{text} {href}".lower()
    if TERMS_NEGATIVE.search(blob):
        return None
    for kind, rx in PATTERNS:
        if re.search(rx, blob, re.I):
            if kind == "terms" and not TERMS_POSITIVE.search(blob):
                continue  # bare "terms" without a website-policy signal
            return kind
    return None


def homepages() -> list[dict]:
    """Every captured homepage across both repos."""
    out = []
    for state, repo in (("TX", "tx-county-watch"), ("FL", "fl-county-watch")):
        for html in sorted((REPOS / repo / "snapshots").glob("*/homepage/page.html")):
            meta_path = html.parent / "meta.json"
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            out.append({
                "state": state,
                "county": html.parent.parent.name,
                "base": meta.get("final_url") or meta.get("requested_url") or "",
                "html": html,
            })
    return out


def main() -> None:
    rows = []
    for hp in homepages():
        soup = BeautifulSoup(hp["html"].read_text(encoding="utf-8", errors="replace"),
                             "html.parser")
        base = hp["base"]
        base_host = urlparse(base).netloc.lower().removeprefix("www.")
        seen = set()
        found = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            text = " ".join(a.get_text(" ", strip=True).split())[:120]
            kind = classify(text, href)
            if not kind:
                continue
            url = urljoin(base, href)
            host = urlparse(url).netloc.lower()
            if (url, kind) in seen:
                continue
            seen.add((url, kind))
            third_party = any(v in host for v in VENDOR_HOSTS)
            same_site = host.removeprefix("www.") == base_host
            found.append({
                "state": hp["state"], "county": hp["county"], "homepage": base,
                "kind": kind, "link_text": text, "url": url,
                "owner": "vendor/third-party" if third_party else
                         ("county" if same_site else "other-host"),
            })
        rows.extend(found)
    OUT.mkdir(exist_ok=True)
    with (OUT / "tos_candidates.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["state", "county", "homepage", "kind",
                                           "owner", "link_text", "url"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} candidate links from "
          f"{len({(r['state'], r['county']) for r in rows})} counties")


if __name__ == "__main__":
    main()
