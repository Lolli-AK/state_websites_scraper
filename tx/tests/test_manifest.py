"""Manifest integrity tests for state-watch.

The same invariants the county repos assert, minus the ones about discovery
provenance: these twelve targets were pinned by hand, so there is no batch
label and no seed-versus-draft reconciliation to check.

Run:  .venv/bin/python -m pytest tests/ -q
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STATES = ROOT / "manifest" / "states.csv"
TARGETS = ROOT / "manifest" / "targets.csv"
SNAPSHOTS = ROOT / "snapshots"

# The six page types, in the order they are meant to read. The first five match
# the county repos exactly so a state row and a county row stay comparable.
PAGE_TYPES = ["homepage", "elections", "voter_registration", "polling",
              "early_voting", "results"]


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def states() -> list[dict]:
    assert STATES.exists(), f"missing seed file: {STATES}"
    return _rows(STATES)


@pytest.fixture(scope="module")
def targets() -> list[dict]:
    assert TARGETS.exists(), f"missing manifest: {TARGETS}"
    return _rows(TARGETS)


def test_state_codes_are_two_letter_and_unique(states):
    codes = [r["state"].strip() for r in states]
    assert len(codes) == len(set(codes)), "duplicate state in states.csv"
    assert all(len(c) == 2 and c.isupper() for c in codes), codes


def test_every_state_has_every_page_type(states, targets):
    want = {(r["state"].strip(), pt) for r in states for pt in PAGE_TYPES}
    have = {(r["state"].strip(), r["page_type"].strip()) for r in targets}
    assert have == want, f"missing {want - have}, unexpected {have - want}"


def test_no_unknown_page_types(targets):
    unknown = {r["page_type"] for r in targets} - set(PAGE_TYPES)
    assert not unknown, unknown


def test_every_target_has_a_url(targets):
    """Unlike the county repos, a gap here is a mistake, not data.

    A county legitimately may not publish an early-voting page. A state
    election authority publishes all six, so a blank means discovery was not
    finished rather than that the page does not exist.
    """
    blank = [(r["state"], r["page_type"]) for r in targets if not r["url"].strip()]
    assert not blank, blank


def test_urls_are_http(targets):
    bad = [r["url"] for r in targets if not r["url"].startswith("http")]
    assert not bad, bad


def test_external_flag_is_boolean(targets):
    bad = [r["external"] for r in targets if r["external"] not in ("true", "false")]
    assert not bad, bad


def test_external_flag_matches_the_url(states, targets):
    """`external` must mean "off the state authority's own host", not a guess."""
    def host(u: str) -> str:
        return u.split("/")[2].lower().removeprefix("www.")

    homes = {r["state"].strip(): host(r["homepage"]) for r in states}
    for r in targets:
        expected = host(r["url"]) != homes[r["state"].strip()]
        assert (r["external"] == "true") == expected, \
            f"{r['state']}/{r['page_type']}: external={r['external']} but " \
            f"host is {host(r['url'])} vs home {homes[r['state'].strip()]}"


def test_no_url_is_used_twice(targets):
    """Two page types resolving to one URL means one of them is not distinct."""
    seen: dict[str, str] = {}
    for r in targets:
        key = r["url"].rstrip("/")
        assert key not in seen, \
            f"{r['state']}/{r['page_type']} reuses the URL of {seen[key]}"
        seen[key] = f"{r['state']}/{r['page_type']}"


def test_every_target_has_three_artifacts(targets):
    for r in targets:
        d = SNAPSHOTS / r["state"].strip().lower() / r["page_type"].strip()
        for name in ("page.html", "page.txt", "meta.json"):
            assert (d / name).exists(), f"missing {d / name}"


def test_meta_json_is_wellformed_and_matches_its_row(targets):
    for r in targets:
        path = (SNAPSHOTS / r["state"].strip().lower()
                / r["page_type"].strip() / "meta.json")
        meta = json.loads(path.read_text(encoding="utf-8"))
        assert meta["state"] == r["state"].strip()
        assert meta["page_type"] == r["page_type"].strip()
        assert meta["requested_url"] == r["url"].strip()
        assert (meta["external"] is True) == (r["external"] == "true")


def test_meta_json_carries_the_noncitizen_flag(targets):
    for r in targets:
        path = (SNAPSHOTS / r["state"].strip().lower()
                / r["page_type"].strip() / "meta.json")
        flag = json.loads(path.read_text(encoding="utf-8"))["noncitizen_voting"]
        assert isinstance(flag["present"], bool)
        assert isinstance(flag["terms"], list)
        assert flag["present"] == bool(flag["terms"])
        assert (flag["count"] > 0) == flag["present"]


def test_the_flag_agrees_with_a_fresh_scan_of_page_txt(targets):
    """The stored flag must be reproducible from the committed text.

    This is what lets scan_noncitizen.py rebuild the flag over history: if a
    stored value could drift from what page.txt implies, a historical row and
    a live row would no longer mean the same thing.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import noncitizen

    for r in targets:
        d = SNAPSHOTS / r["state"].strip().lower() / r["page_type"].strip()
        stored = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        fresh = noncitizen.scan((d / "page.txt").read_text(encoding="utf-8"))
        assert stored["noncitizen_voting"] == fresh, f"{d} flag is stale"


def test_artifacts_contain_no_fetch_timestamp(targets):
    """page.html / page.txt must be byte-stable across runs.

    fetched_at is the one volatile field and it belongs to meta.json alone;
    a timestamp leaking into the page artifacts would make every run diff.
    """
    for r in targets:
        d = SNAPSHOTS / r["state"].strip().lower() / r["page_type"].strip()
        stamp = json.loads((d / "meta.json").read_text(encoding="utf-8"))["fetched_at"]
        for name in ("page.html", "page.txt"):
            assert stamp not in (d / name).read_text(encoding="utf-8"), \
                f"{d / name} embeds the fetch timestamp"
