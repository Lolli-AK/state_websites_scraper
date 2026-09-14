# scrapeability — robots.txt and terms-of-use audit

Cross-repo analysis over the **362 unique hosts** and **321 counties**
(254 TX + 67 FL) in `tx-county-watch` and `fl-county-watch`. Answers one
question: **what do county election sites say about automated access, and does
it match what their servers actually do?**

Run order:

```bash
python scripts/fetch_robots.py    # 362 hosts -> output/robots_index.csv
python scripts/discover_tos.py    # local homepages -> output/tos_candidates.csv
python scripts/fetch_tos.py       # county legal pages -> output/tos_clauses.csv
python scripts/build_summary.py   # join -> output/scrapeability_policy_by_county.csv
```

## Method notes that change the numbers

**HTTP/2 first, 1.1 on a 4xx** (`scripts/common.py`). `httpx` defaults to 1.1
and several Akamai/Granicus-fronted county sites answer 403 to 1.1 while
serving 200 to h2. In `tx-county-watch`, 14 of 15 apparent "blocks" were this
artifact. An audit of *who blocks crawlers* that manufactures its own blocks is
worthless, so this is not optional.

**A 200 that returns HTML is a soft 404, not a robots.txt.** Most county CMSs
serve their 404 page with status 200. Counting those would report near-universal
robots.txt coverage; 9 of 170 apparent hits were soft 404s.

**"Terms" and "Policies" are load-bearing elsewhere in county government.**
Before gating, `terms` matched *Terms of Court*, *term of office* and *Purchase
Order Terms and Conditions*; `legal_other` matched employee handbooks,
investment policies and animal-control ordinances. Both now require an explicit
website-policy signal (`TERMS_NEGATIVE` / `TERMS_POSITIVE` in
`discover_tos.py`). This is the same failure mode as the check-register trap in
`tx-county-watch/scripts/discover_registration.py`.

**Vendor-owned legal links are recorded but not credited to the county.** A
CivicPlus footer's "Terms" often points at `civicplus.com`; two FL counties
point at `policies.google.com`. That is the vendor's policy, not the county's.

## Known limits

- **ToS discovery is homepage-footer-only.** Only 254 of 321 counties had a
  captured homepage to parse, so legal-page coverage is a **lower bound**.
- **Clause detection is regex over fetched text**, tuned for recall; every hit
  is stored with its sentence in `tos_clauses.csv` for reading.
- **5 legal pages returned 403 and 6 were PDFs** and are unparsed. Of the PDFs
  only Jim Hogg's and Victoria's are plausibly website disclaimers; the rest
  are HR/procurement documents that survived the gate.
- **robots.txt rules are evaluated for user-agent `*`.**
- The 7 counties with anti-scraping terms share **one** vendor template, so
  n = 7 counties but n = 1 document.
