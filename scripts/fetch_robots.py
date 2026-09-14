#!/usr/bin/env python3
"""Fetch and parse /robots.txt for every host in the TX + FL target manifests.

Writes:
  data/robots/<host>.txt   raw body, when a real robots.txt was served
  output/robots_index.csv  one row per host, parsed + derived fields

A 200 that returns HTML is a SOFT 404, not a robots.txt. Counting those as
"has a robots.txt" would be the single biggest error available here: most
county CMSs serve their 404 page with a 200 status, so a naive audit would
report near-universal robots.txt coverage.
"""

from __future__ import annotations

import concurrent.futures as cf
import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT.parent
RAW = ROOT / "data" / "robots"
OUT = ROOT / "output"

# Crawlers whose treatment is itself a finding: the generative-AI cohort, the
# archival cohort (Internet Archive underpins most longitudinal web research),
# and the generic-tool cohort that catches unsophisticated blanket bans.
AI_BOTS = ["gptbot", "chatgpt-user", "oai-searchbot", "claudebot", "anthropic-ai",
           "claude-web", "ccbot", "google-extended", "perplexitybot", "bytespider",
           "applebot-extended", "cohere-ai", "meta-externalagent", "facebookbot",
           "diffbot", "imagesiftbot", "amazonbot", "youbot", "timpibot",
           "omgilibot", "petalbot", "ai2bot"]
ARCHIVE_BOTS = ["ia_archiver", "archive.org_bot", "wayback", "heritrix"]
TOOL_BOTS = ["wget", "curl", "python-requests", "python-urllib", "scrapy",
             "httrack", "libwww-perl", "java", "go-http-client", "node-fetch"]


def hosts_from_manifests() -> dict[str, dict]:
    """Unique hosts, tagged with state and which page types they serve."""
    hosts: dict[str, dict] = {}
    for state, repo in (("TX", "tx-county-watch"), ("FL", "fl-county-watch")):
        path = REPOS / repo / "manifest" / "targets.csv"
        for row in csv.DictReader(path.open()):
            url = (row.get("url") or "").strip()
            if not url:
                continue
            host = urlparse(url).netloc.lower()
            if not host:
                continue
            rec = hosts.setdefault(host, {
                "host": host, "states": set(), "counties": set(),
                "page_types": set(), "urls": [], "external": set(),
            })
            rec["states"].add(state)
            rec["counties"].add(row.get("county", ""))
            rec["page_types"].add(row.get("page_type", ""))
            rec["urls"].append(url)
            rec["external"].add((row.get("external") or "").strip().lower())
    return hosts


def looks_like_robots(text: str, content_type: str) -> bool:
    """A real robots.txt, or a CMS 404 page served with status 200?"""
    head = text[:4000].lstrip().lower()
    if head.startswith("<!doctype") or head.startswith("<html") or "<body" in head:
        return False
    if "html" in (content_type or "").lower():
        return False
    # Must contain at least one recognised directive.
    return bool(re.search(r"^\s*(user-agent|disallow|allow|sitemap|crawl-delay)\s*:",
                          text, re.I | re.M))


def parse_robots(text: str) -> dict:
    """Group directives by user-agent. Returns {agent: {...}} plus sitemaps."""
    groups: dict[str, dict] = {}
    sitemaps: list[str] = []
    current: list[str] = []
    # A blank line ends a group; consecutive User-agent lines share one group.
    starting_group = True
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            starting_group = True
            continue
        if ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "sitemap":
            if value:
                sitemaps.append(value)
            continue
        if field == "user-agent":
            if starting_group:
                current = []
                starting_group = False
            agent = value.lower()
            current.append(agent)
            groups.setdefault(agent, {"disallow": [], "allow": [], "crawl_delay": None})
            continue
        starting_group = False
        for agent in current:
            g = groups.setdefault(agent, {"disallow": [], "allow": [], "crawl_delay": None})
            if field == "disallow":
                g["disallow"].append(value)
            elif field == "allow":
                g["allow"].append(value)
            elif field == "crawl-delay":
                try:
                    g["crawl_delay"] = float(value)
                except ValueError:
                    pass
    return {"groups": groups, "sitemaps": sitemaps}


def _rule_matches(path: str, pattern: str) -> bool:
    """robots.txt path matching with * and $ wildcards."""
    if pattern == "":
        return False
    regex = "".join(".*" if c == "*" else ("$" if c == "$" else re.escape(c))
                    for c in pattern)
    return re.match(regex, path) is not None


def allowed(parsed: dict, path: str, agent: str = "*") -> bool | None:
    """Is `path` crawlable by `agent`? None when no applicable group exists."""
    groups = parsed["groups"]
    group = groups.get(agent.lower()) or groups.get("*")
    if group is None:
        return None
    best_dis = max((len(p) for p in group["disallow"] if _rule_matches(path, p)),
                   default=-1)
    best_allow = max((len(p) for p in group["allow"] if _rule_matches(path, p)),
                     default=-1)
    if best_dis < 0:
        return True
    return best_allow >= best_dis  # longest match wins; ties go to Allow


def agents_blocked(parsed: dict, names: list[str]) -> list[str]:
    """Which of `names` have a group that disallows the site root."""
    out = []
    for agent, g in parsed["groups"].items():
        if agent == "*":
            continue
        if not any(n in agent for n in names):
            continue
        if any(p in ("/", "*") for p in g["disallow"]):
            out.append(agent)
    return sorted(set(out))


def process(rec: dict) -> dict:
    host = rec["host"]
    res = fetch(f"https://{host}/robots.txt", accept="text/plain,*/*;q=0.8")
    row = {
        "host": host,
        "states": "|".join(sorted(rec["states"])),
        "n_targets": len(rec["urls"]),
        "page_types": "|".join(sorted(t for t in rec["page_types"] if t)),
        "external_host": "true" if rec["external"] == {"true"} else "false",
        "http_status": res["http_status"],
        "http_version": res["http_version"],
        "redirects": res["redirects"],
        "final_url": res["final_url"],
        "content_type": (res["content_type"] or "").split(";")[0],
        "server": res["server"],
        "cdn_headers": res["cdn_headers"],
        "error": res["error"] or "",
    }
    text = res["text"] or ""
    real = res["http_status"] == 200 and looks_like_robots(text, res["content_type"])
    row["has_robots"] = "true" if real else "false"
    row["soft_404"] = "true" if (res["http_status"] == 200 and not real) else "false"

    if not real:
        row.update({"n_bytes": 0, "n_groups": 0, "star_disallow": 0, "star_allow": 0,
                    "blocks_all_star": "", "crawl_delay_star": "", "n_sitemaps": 0,
                    "sitemaps": "", "ai_bots_blocked": "", "n_ai_blocked": 0,
                    "archive_bots_blocked": "", "tool_bots_blocked": "",
                    "n_targets_disallowed": 0, "targets_disallowed": ""})
        return row

    (RAW / f"{host}.txt").write_text(text, encoding="utf-8")
    parsed = parse_robots(text)
    star = parsed["groups"].get("*", {"disallow": [], "allow": [], "crawl_delay": None})

    disallowed_targets = []
    for url in sorted(set(rec["urls"])):
        p = urlparse(url)
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
        if allowed(parsed, path) is False:
            disallowed_targets.append(url)

    row.update({
        "n_bytes": len(text.encode()),
        "n_groups": len(parsed["groups"]),
        "star_disallow": len(star["disallow"]),
        "star_allow": len(star["allow"]),
        "blocks_all_star": "true" if any(p in ("/", "*") for p in star["disallow"]) else "false",
        "crawl_delay_star": star["crawl_delay"] if star["crawl_delay"] is not None else "",
        "n_sitemaps": len(parsed["sitemaps"]),
        "sitemaps": "|".join(parsed["sitemaps"][:5]),
        "ai_bots_blocked": "|".join(agents_blocked(parsed, AI_BOTS)),
        "n_ai_blocked": len(agents_blocked(parsed, AI_BOTS)),
        "archive_bots_blocked": "|".join(agents_blocked(parsed, ARCHIVE_BOTS)),
        "tool_bots_blocked": "|".join(agents_blocked(parsed, TOOL_BOTS)),
        "n_targets_disallowed": len(disallowed_targets),
        "targets_disallowed": "|".join(disallowed_targets[:5]),
    })
    return row


def main() -> None:
    hosts = hosts_from_manifests()
    print(f"{len(hosts)} unique hosts", flush=True)
    rows = []
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(process, rec): rec["host"] for rec in hosts.values()}
        for i, fut in enumerate(cf.as_completed(futures), 1):
            rows.append(fut.result())
            if i % 25 == 0:
                print(f"  {i}/{len(hosts)}", flush=True)
    rows.sort(key=lambda r: (r["states"], r["host"]))
    OUT.mkdir(exist_ok=True)
    with (OUT / "robots_index.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT/'robots_index.csv'} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
