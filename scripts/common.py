#!/usr/bin/env python3
"""Shared fetch layer for the scrapeability audit.

Deliberately mirrors tx-county-watch/scripts/snapshot.py rather than using a
naive client. Two things there are load-bearing and would corrupt this audit if
dropped:

  * HTTP/2 first, falling back to 1.1 on a 4xx. Akamai/Granicus-fronted county
    sites answer 403 to HTTP/1.1 and 200 to HTTP/2 (and Wichita does the
    reverse). 14 of 15 apparent "blocks" in tx-county-watch were this artifact.
    An audit of who blocks crawlers must not manufacture its own blocks.
  * A complete browser header set. Being a standards-normal client, not evading
    anything.
"""

from __future__ import annotations

import random
import time

import httpx

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
}

TIMEOUT = 30.0
RETRIES = 2
DELAY_MS, JITTER_MS = 300, 300


def throttle() -> None:
    time.sleep((DELAY_MS + random.uniform(0, JITTER_MS)) / 1000.0)


def _fetch_once(url: str, http2: bool, accept: str | None) -> dict:
    throttle()
    headers = dict(HEADERS)
    if accept:
        headers["Accept"] = accept
    with httpx.Client(headers=headers, follow_redirects=True,
                      timeout=TIMEOUT, verify=True, http2=http2) as client:
        resp = client.get(url)
    return {
        "text": resp.text,
        "final_url": str(resp.url),
        "redirects": len(resp.history),
        "http_status": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "server": resp.headers.get("server", ""),
        # CDN/WAF fingerprints, for the bot-protection half of the audit.
        "cdn_headers": ";".join(sorted(
            h.lower() for h in resp.headers
            if h.lower().startswith(("cf-", "x-akamai", "x-iinfo", "x-cdn",
                                     "x-sucuri", "x-amz-cf", "x-served-by",
                                     "x-cache", "x-azure"))
        )),
        "http_version": "h2" if http2 else "1.1",
        "error": None,
    }


def fetch(url: str, accept: str | None = None) -> dict:
    """h2 first, 1.1 on a 4xx, same protocol retried on 5xx. Never raises."""
    last_exc = None
    last_result = None
    for http2 in (True, False):
        for attempt in range(1, RETRIES + 1):
            try:
                result = _fetch_once(url, http2=http2, accept=accept)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                continue
            if result["http_status"] >= 500 and attempt < RETRIES:
                continue
            last_result = result
            if result["http_status"] < 400:
                return result
            break
        if last_result is not None and last_result["http_status"] < 400:
            return last_result
    if last_result is not None:
        return last_result
    return {"text": "", "final_url": url, "redirects": 0, "http_status": None,
            "content_type": "", "server": "", "cdn_headers": "",
            "http_version": "", "error": f"{type(last_exc).__name__}: {last_exc}"}
