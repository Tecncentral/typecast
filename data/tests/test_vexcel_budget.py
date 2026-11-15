"""Vexcel spending guard: caps, daily rollover, ledger contents. Offline, ledger in a temp dir."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from data import vexcel_budget as budget
from data.vexcel_client import ProviderError

DEFAULT_LEDGER = budget.LEDGER
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "cache" / "vexcel" / "ledger.jsonl"
    monkeypatch.setattr(budget, "LEDGER", path)
    return path


@pytest.fixture
def clock(monkeypatch):
    now = {"value": datetime(2026, 11, 15, 12, 0, tzinfo=UTC)}
    monkeypatch.setattr(budget, "_now", lambda: now["value"])
    return now


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_caps_are_the_agreed_block():
    assert budget.CAPS["embedding"] == {"per_search": 5, "per_day": 40}
    assert budget.CAPS["images"] == {"per_day": 60}
    assert budget.CAPS["elevation"] == {"per_day": 120}
    assert budget.CATEGORY == {
        "embedding/extract": "embedding",
        "oriented/extract": "images",
        "dtm/elevation": "elevation",
        "dsm/elevation": "elevation",
    }


def test_embedding_per_search_cap(ledger, clock):
    budget.check_and_record("embedding/extract", 5)
    with pytest.raises(budget.BudgetExceeded, match="per-search cap of 5"):
        budget.check_and_record("embedding/extract", 6)
    assert len(rows(ledger)) == 1, "a refused call is never recorded"


def test_embedding_daily_cap_refuses_before_the_call(ledger, clock):
    for _ in range(8):
        budget.check_and_record("embedding/extract", 5)
    with pytest.raises(budget.BudgetExceeded, match="daily cap of 40"):
        budget.check_and_record("embedding/extract", 1)
    assert sum(r["count"] for r in rows(ledger)) == 40


def test_images_daily_cap(ledger, clock):
    budget.check_and_record("oriented/extract", 59)
    budget.check_and_record("oriented/extract", 1)
    with pytest.raises(budget.BudgetExceeded, match="daily cap of 60"):
        budget.check_and_record("oriented/extract", 1)


def test_dtm_and_dsm_share_the_elevation_cap(ledger, clock):
    budget.check_and_record("dtm/elevation", 60)
    budget.check_and_record("dsm/elevation", 60)
    for endpoint in ("dtm/elevation", "dsm/elevation"):
        with pytest.raises(budget.BudgetExceeded):
            budget.check_and_record(endpoint, 1)


def test_categories_do_not_spend_each_others_budget(ledger, clock):
    for _ in range(8):
        budget.check_and_record("embedding/extract", 5)
    budget.check_and_record("oriented/extract", 1)
    budget.check_and_record("dtm/elevation", 1)


def test_daily_rollover_resets_the_cap_and_keeps_history(ledger, clock):
    for _ in range(8):
        budget.check_and_record("embedding/extract", 5)
    clock["value"] = datetime(2026, 11, 15, 23, 59, 59, tzinfo=UTC)
    with pytest.raises(budget.BudgetExceeded):
        budget.check_and_record("embedding/extract", 1)
    clock["value"] += timedelta(seconds=1)
    budget.check_and_record("embedding/extract", 5)
    recorded = rows(ledger)
    assert len(recorded) == 9
    assert {r["ts"][:10] for r in recorded} == {"2026-11-15", "2026-11-16"}
    assert recorded[-1]["ts"].startswith("2026-11-16T00:00:00")


def test_ledger_lines_have_only_timestamp_endpoint_and_count(
    ledger, clock, monkeypatch
):
    monkeypatch.setenv("VEXCEL_API_KEY", "SECRET-KEY-VALUE")
    budget.check_and_record("oriented/extract", 1)
    text = ledger.read_text()
    (row,) = rows(ledger)
    assert set(row) == {"ts", "endpoint", "count"}
    assert row == {
        "ts": "2026-11-15T12:00:00Z",
        "endpoint": "oriented/extract",
        "count": 1,
    }
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", row["ts"])
    assert not any(
        word in text.lower() for word in ("secret", "api_key", "http", "wkt", "bbox")
    )


def test_ledger_is_append_only(ledger, clock):
    ledger.parent.mkdir(parents=True)
    existing = (
        '{"count": 3, "endpoint": "oriented/extract", "ts": "2026-11-15T01:00:00Z"}\n'
    )
    ledger.write_text(existing)
    budget.check_and_record("oriented/extract", 2)
    text = ledger.read_text()
    assert text.startswith(existing) and len(text.splitlines()) == 2
    with pytest.raises(budget.BudgetExceeded):
        budget.check_and_record(
            "oriented/extract", 56
        )  # 5 used earlier today + 56 > 60
    budget.check_and_record("oriented/extract", 55)


@pytest.mark.parametrize(
    "endpoint",
    ["embedding/refine", "oriented/query", "dtm/extract", "ortho/extract", "", "../x"],
)
def test_unlisted_endpoints_are_refused_and_never_recorded(ledger, clock, endpoint):
    with pytest.raises(ValueError):
        budget.check_and_record(endpoint, 1)
    assert not ledger.exists()


@pytest.mark.parametrize("count", [0, -1, 1.5, True, "5", None])
def test_bad_counts_are_refused(ledger, clock, count):
    with pytest.raises(ValueError):
        budget.check_and_record("oriented/extract", count)
    assert not ledger.exists()


@pytest.mark.parametrize(
    "content",
    [
        "not json\n",
        '{"ts": "2026-11-15T01:00:00Z"}\n',
        '{"ts": 1, "endpoint": "x", "count": 1}\n',
        '{"ts": "2026-11-15T01:00:00Z", "endpoint": "oriented/extract", "count": true}\n',
    ],
)
def test_a_corrupt_ledger_refuses_every_call_instead_of_guessing(
    ledger, clock, content
):
    ledger.parent.mkdir(parents=True)
    ledger.write_text(content)
    with pytest.raises(budget.LedgerError):
        budget.check_and_record("oriented/extract", 1)
    assert ledger.read_text() == content


def test_blank_lines_are_tolerated(ledger, clock):
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        '\n{"count": 1, "endpoint": "oriented/extract", "ts": "2026-11-15T01:00:00Z"}\n\n'
    )
    budget.check_and_record("oriented/extract", 1)


def test_concurrent_callers_cannot_overspend(ledger, clock):
    def attempt(_):
        try:
            budget.check_and_record("oriented/extract", 5)
            return True
        except budget.BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(24)))
    assert sum(results) == 12, "60 images a day at 5 each is exactly 12 calls"
    assert sum(r["count"] for r in rows(ledger)) == 60


def test_errors_are_provider_errors_without_urls(ledger, clock):
    assert issubclass(budget.BudgetExceeded, ProviderError) and issubclass(
        budget.LedgerError, ProviderError
    )
    with pytest.raises(budget.BudgetExceeded) as error:
        budget.check_and_record("embedding/extract", 6)
    assert (
        "http" not in str(error.value).lower() and "key" not in str(error.value).lower()
    )


def test_default_ledger_is_private_cache():
    assert DEFAULT_LEDGER == ROOT / "cache" / "vexcel" / "ledger.jsonl"
    assert re.search(r"^cache/?$", (ROOT / ".gitignore").read_text(), re.MULTILINE), (
        "cache/ must be git-ignored"
    )


def test_environment_overrides_raise_caps_without_changing_the_defaults(ledger, clock, monkeypatch):
    monkeypatch.setenv("TYPECAST_VEXCEL_EMBEDDING_PER_DAY", "2000")
    monkeypatch.setenv("TYPECAST_VEXCEL_EMBEDDING_PER_SEARCH", "16")
    monkeypatch.setenv("TYPECAST_VEXCEL_IMAGES_PER_DAY", "not a number")
    assert budget.caps("embedding") == {"per_search": 16, "per_day": 2000}
    assert budget.caps("images") == {"per_day": 60}  # an invalid override is ignored
    assert budget.CAPS["embedding"] == {"per_search": 5, "per_day": 40}
    for _ in range(10):
        budget.check_and_record("embedding/extract", 16)  # 160 > 40: allowed only by the override
    assert sum(r["count"] for r in rows(ledger)) == 160
