#!/usr/bin/env python3
"""Fetch the county-owned legal pages found by discover_tos.py and scan their
text for clauses that bear on automated access.

Only `terms`, `disclaimer` and `legal_other` are fetched — an accessibility
statement or a public-records notice is a different document and does not
govern crawling. Vendor-owned links are skipped: they are the CMS vendor's
policy, recorded in the candidate file but not attributable to the county.
"""

from __future__ import annotations

import concurrent.futures as cf
import csv
import hashlib
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "tos"
OUT = ROOT / "output"
FETCH_KINDS = {"terms", "disclaimer", "legal_other"}

# Clause families that speak to automated collection. Deliberately broad on
# recall; every hit is stored with its surrounding sentence so it can be read.
CLAUSES = {
    "anti_scraping": r"\b(scrap(e|ing)|spider|crawl(er|ing)?|robot|bot\b|harvest|"
                     r"data\s*min(e|ing)|automated\s*(means|process|system|tool|"
                     r"agent|script|query|retrieval)|screen[-\s]?scrap)",
    "no_bulk_download": r"\b(bulk\s*(download|copy|extract)|mass\s*download|"
                        r"systematic(ally)?\s*(download|retriev|collect|copy))",
    "commercial_use": r"\b(commercial\s*(use|purpose)|resale|redistribut|"
                      r"republish)",
    "rate_limit": r"\b(excessive\s*(traffic|requests?|load)|overburden|"
                  r"interfere\s*with\s*the\s*(proper\s*)?(working|operation)|"
                  r"undue\s*burden|denial\s*of\s*service)",
    "permission_required": r"\b(prior\s*written\s*(consent|permission|approval)|"
                           r"express\s*written\s*(consent|permission))",
    "ai_training": r"\b(machine\s*learning|artificial\s*intelligence|\bA\.?I\.?\b\s*"
                   r"(training|model)|train(ing)?\s*(of\s*)?(an?\s*)?(AI|model|"
                   r"language\s*model))",
}


def sentences_for(text: str, rx: str) -> list[str]:
    out = []
    for m in re.finditer(rx, text, re.I):
        lo = text.rfind(".", 0, m.start()) + 1
        hi = text.find(".", m.end())
        hi = hi if hi != -1 else min(len(text), m.end() + 200)
        s = " ".join(text[lo:hi + 1].split())
        if 20 < len(s) < 400:
            out.append(s)
    # de-dup, keep order
    seen, uniq = set(), []
    for s in out:
        if s.lower() not in seen:
            seen.add(s.lower())
            uniq.append(s)
    return uniq


def process(cand: dict) -> dict:
    res = fetch(cand["url"])
    row = dict(cand)
    row.update({"http_status": res["http_status"], "error": res["error"] or "",
                "final_url": res["final_url"], "n_chars": 0, "is_pdf": "false"})
    ctype = (res["content_type"] or "").lower()
    if res["http_status"] != 200 or res["error"]:
        for k in CLAUSES:
            row[k] = ""
            row[f"{k}_quote"] = ""
        return row
    if "pdf" in ctype or cand["url"].lower().endswith(".pdf"):
        row["is_pdf"] = "true"
        for k in CLAUSES:
            row[k] = ""
            row[f"{k}_quote"] = ""
        return row

    soup = BeautifulSoup(res["text"], "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    row["n_chars"] = len(text)
    digest = hashlib.sha256(cand["url"].encode()).hexdigest()[:12]
    (RAW / f"{cand['state']}_{cand['county']}_{cand['kind']}_{digest}.txt").write_text(
        text, encoding="utf-8")
    for k, rx in CLAUSES.items():
        hits = sentences_for(text, rx)
        row[k] = "true" if hits else "false"
        row[f"{k}_quote"] = hits[0][:300] if hits else ""
    return row


def main() -> None:
    cands = [r for r in csv.DictReader((OUT / "tos_candidates.csv").open())
             if r["kind"] in FETCH_KINDS and r["owner"] == "county"]
    # one fetch per URL
    seen, uniq = set(), []
    for c in cands:
        if c["url"] not in seen:
            seen.add(c["url"])
            uniq.append(c)
    print(f"fetching {len(uniq)} county legal pages", flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        for i, row in enumerate(pool.map(process, uniq), 1):
            rows.append(row)
            if i % 20 == 0:
                print(f"  {i}/{len(uniq)}", flush=True)
    cols = (["state", "county", "kind", "owner", "link_text", "url", "final_url",
             "http_status", "error", "is_pdf", "n_chars"]
            + [c for k in CLAUSES for c in (k, f"{k}_quote")])
    with (OUT / "tos_clauses.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT/'tos_clauses.csv'} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
